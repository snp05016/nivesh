"""ARCH-18: one KYC gate (kyc_consent_service.check_kyc_gate) serves loans and FDs."""
import pytest

import services.fixed_deposit_service as fd_service
import services.kyc_consent_service as kyc
import services.loan_marketplace_service as loan_service


@pytest.fixture
def gate(monkeypatch):
    """Point the gate at in-memory consent/binding stubs; returns a setter."""
    state = {"consents": [], "verified": True}
    monkeypatch.setattr(kyc, "get_active_consents",
                        lambda user_id: [{"consent_type": t} for t in state["consents"]])
    monkeypatch.setattr(kyc, "verify_device_binding",
                        lambda user_id, device_id: {"verified": state["verified"], "reason": "stub"})
    return state


@pytest.mark.parametrize("consent_type,action", [("credit_check", "application"), ("sim_binding", "booking")])
def test_gate_requires_consent_device_and_binding(gate, consent_type, action):
    ok, reason = kyc.check_kyc_gate(1, "dev-1", consent_type, action)
    assert not ok and consent_type in reason

    gate["consents"] = ["some_other_consent"]
    assert kyc.check_kyc_gate(1, "dev-1", consent_type, action)[0] is False

    gate["consents"] = [consent_type]
    ok, reason = kyc.check_kyc_gate(1, None, consent_type, action)
    assert not ok and action in reason

    gate["verified"] = False
    ok, reason = kyc.check_kyc_gate(1, "dev-1", consent_type, action)
    assert not ok and "device binding check failed" in reason

    gate["verified"] = True
    assert kyc.check_kyc_gate(1, "dev-1", consent_type, action)[0] is True


def test_services_share_one_gate():
    assert loan_service.check_kyc_gate is kyc.check_kyc_gate
    assert fd_service.check_kyc_gate is kyc.check_kyc_gate
    assert not hasattr(loan_service, "_check_kyc_gate")
    assert not hasattr(fd_service, "_check_kyc_gate")
    assert loan_service.REQUIRED_CONSENT_TYPE == "credit_check"
    assert fd_service.REQUIRED_CONSENT_TYPE == "sim_binding"
