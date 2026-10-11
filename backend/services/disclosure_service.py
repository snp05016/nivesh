"""Disclosure content service — compliance/regulatory-style disclosure copy
+ Key Fact Statement (KFS) computation for the loan & FD marketplaces.

Controller-Service-Repository: routers/compliance.py must only validate
HTTP input and call functions here.

DEMO-GRADE / ILLUSTRATIVE CONTENT ONLY
---------------------------------------
Every disclosure body below is clearly-labelled placeholder/demo copy for a
portfolio project. It is NOT real legal advice, NOT a real regulatory
filing, and does NOT reference any real SEBI/RBI registration or license
number. Nothing in this module should be treated as compliant legal text
for an actual regulated lending/fintech product.
"""
from decimal import Decimal
from typing import Optional, cast

from database import get_session
from models.db_models import FixedDepositScheme, LoanOffer
from services.product_bounds import check_product_bounds

_MOCK_DISCLAIMER = (
    "MOCK/DEMO CONTENT — illustrative placeholder text for a portfolio "
    "project only. This is NOT real legal advice, NOT a real regulatory "
    "filing, and does not reflect any real SEBI/RBI registration or "
    "license number."
)


def _section(heading: str, text: str) -> dict:
    return {"heading": heading, "text": text}


STATIC_DISCLOSURES = {
    "privacy_policy": {
        "title": "Privacy Policy (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "What we collect",
                "In this demo app, account details, portfolio holdings, watchlist "
                "activity, and (for the mock loan/FD marketplace) KYC consent "
                "records and a device identifier are stored. No real government "
                "ID or biometric data is collected.",
            ),
            _section(
                "How we use it",
                "Data is used only to render the demo app's features (portfolio "
                "tracking, mock loan/FD marketplace, forum, alerts). There is no "
                "real advertising, profiling, or resale of user data.",
            ),
            _section(
                "Retention & deletion",
                "See GET/POST /api/v1/compliance/deletion-requests for the demo "
                "right-to-erasure workflow (DEMO-GRADE — a state-machine record "
                "only, not real irreversible deletion).",
            ),
        ],
    },
    "data_sharing_governance": {
        "title": "Third-Party Data Sharing Governance (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "Third parties in this demo",
                "This demo app does not call any real third-party data broker, "
                "ad network, or analytics reseller. Market data (prices, "
                "fundamentals) is fetched from public market-data sources for "
                "display purposes only.",
            ),
            _section(
                "Mock lending-marketplace partners",
                "NBFC/bank names shown in the loan and FD marketplaces (e.g. "
                "'HDFC Bank (mock)', 'Bajaj Finserv (mock)') are illustrative "
                "labels on hand-seeded demo data — no real data-sharing "
                "agreement or integration exists with any real institution.",
            ),
            _section(
                "Consent-based sharing",
                "The KYC consent ledger (see services/kyc_consent_service.py) "
                "models what a real consent-gated data-sharing flow would look "
                "like: a 'data_sharing' consent type must be granted (and not "
                "revoked) before any downstream sharing would be simulated.",
            ),
        ],
    },
    "digital_lending_compliance": {
        "title": "RBI Digital Lending Guidelines — Illustrative Compliance Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            "This demo app's mock loan marketplace illustrates several "
            "concepts from RBI's Digital Lending Guidelines for demo/portfolio "
            "purposes: upfront Key Fact Statement disclosure (see "
            "GET /api/v1/compliance/key-fact-statement), explicit consent "
            "capture before underwriting (services/kyc_consent_service.py), "
            "and no automatic recurring/undisclosed charges.",
            "This is NOT a real RBI-regulated digital lending product and "
            "carries no real Lending Service Provider (LSP) or NBFC "
            "registration. See also the 'lending_service_provider' disclosure.",
        ],
    },
    "lending_service_provider": {
        "title": "Lending Service Provider (LSP) Role — Illustrative Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "Illustrative LSP role",
                "In this demo, the app plays the illustrative role of a "
                "'Lending Service Provider' — a marketplace surface that lists "
                "mock NBFC loan offers and mock FD schemes — without itself "
                "being the lender.",
            ),
            _section(
                "No real LSP registration",
                "There is no real LSP registration, no real co-lending "
                "agreement, and no real NBFC partnership backing this demo. "
                "All 'nbfc_name' / 'issuer_name' values in loan_offers and "
                "fixed_deposit_schemes are MOCK DATA.",
            ),
        ],
    },
    "apr_disclosure": {
        "title": "How APR Is Calculated In This App (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "Formula used",
                "For loan offers, this demo computes an illustrative Annual "
                "Percentage Rate (APR) as: "
                "APR = interest_rate_pct + (processing_fee_pct / tenure_years). "
                "This amortizes the one-time processing fee evenly over the "
                "loan's tenure and adds it to the nominal annual interest rate. "
                "It is a simplified illustrative approximation, not the exact "
                "IRR-based APR a real lender would be required to disclose.",
            ),
            _section(
                "Fixed deposits",
                "For FD schemes, no fees are charged, so the disclosed APR "
                "equals the scheme's nominal annual interest_rate_pct.",
            ),
            _section(
                "Where this is used",
                "See GET /api/v1/compliance/key-fact-statement for the computed, "
                "per-offer/per-scheme breakdown (loan_amount, interest_rate, "
                "all_fees, apr, tenure).",
            ),
        ],
    },
    "sim_binding_fraud_prevention": {
        "title": "SIM/Device-Binding Fraud Prevention — Illustrative Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "This is a MOCK check",
                "The 'sim_binding' / device-binding check used to gate loan "
                "and FD confirmations (see services/kyc_consent_service.py:"
                "verify_device_binding()) is a MOCK DATA check — simulated for "
                "demo purposes — that only compares a submitted device_id "
                "against rows this app stored itself.",
            ),
            _section(
                "Not real telecom fraud detection",
                "There is no real telecom carrier integration, no real "
                "SIM-swap-detection API, and no real signal-based fraud "
                "scoring anywhere in this app. This disclosure exists so the "
                "demo does not misrepresent the strength of this control.",
            ),
        ],
    },
}


def get_disclosure(key: str) -> Optional[dict]:
    """Returns the static disclosure content dict for `key`, or None if the
    key is unknown."""
    content = STATIC_DISCLOSURES.get(key)
    if content is None:
        return None
    return {"key": key, **content}


def _to_float(value) -> float:
    if value is None:
        raise ValueError("expected a non-null numeric field for KFS/APR computation")
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def compute_key_fact_statement(
    loan_offer_id: Optional[int] = None,
    scheme_id: Optional[int] = None,
    amount: Optional[float] = None,
    tenure_months: Optional[int] = None,
) -> Optional[dict]:
    """Computes a structured Key Fact Statement (KFS) breakdown
    (loan_amount, interest_rate, all_fees, apr, tenure) from real
    LoanOffer or FixedDepositScheme data.

    Exactly one of loan_offer_id / scheme_id must be provided by the
    caller (routers/compliance.py enforces this). `amount` and
    `tenure_months` are optional overrides within the offer/scheme's
    allowed range; when omitted, the offer/scheme's minimum amount and
    minimum tenure are used as representative illustrative figures.

    Returns None if the referenced offer/scheme is not found. Raises
    ProductBoundsError when an override is outside the offer/scheme range
    (or the product is inactive).
    """
    if loan_offer_id is not None:
        with get_session() as session:
            offer = session.query(LoanOffer).filter(LoanOffer.id == loan_offer_id).first()
            if offer is None:
                return None

            chosen_amount = amount if amount is not None else _to_float(offer.min_amount)
            chosen_tenure = tenure_months if tenure_months is not None else offer.min_tenure_months
            if amount is not None or tenure_months is not None:
                check_product_bounds(offer, chosen_amount, cast(int, chosen_tenure), "loan offer")
            chosen_tenure = max(1, chosen_tenure)

            interest_rate_pct = _to_float(offer.interest_rate_pct)
            processing_fee_pct = _to_float(offer.processing_fee_pct)
            all_fees = round(chosen_amount * processing_fee_pct / 100, 2)

            tenure_years = chosen_tenure / 12
            fee_annualized_pct = processing_fee_pct / tenure_years if tenure_years > 0 else processing_fee_pct
            apr = round(interest_rate_pct + fee_annualized_pct, 2)

            return {
                "source": "loan_offer",
                "loan_offer_id": offer.id,
                "nbfc_name": offer.nbfc_name,
                "loan_type": offer.loan_type,
                "loan_amount": chosen_amount,
                "interest_rate": interest_rate_pct,
                "all_fees": all_fees,
                "apr": apr,
                "tenure_months": chosen_tenure,
                "disclaimer": _MOCK_DISCLAIMER,
            }

    if scheme_id is not None:
        with get_session() as session:
            scheme = (
                session.query(FixedDepositScheme).filter(FixedDepositScheme.id == scheme_id).first()
            )
            if scheme is None:
                return None

            chosen_amount = amount if amount is not None else _to_float(scheme.min_amount)
            chosen_tenure = tenure_months if tenure_months is not None else scheme.min_tenure_months
            if amount is not None or tenure_months is not None:
                check_product_bounds(scheme, chosen_amount, cast(int, chosen_tenure), "FD scheme")
            chosen_tenure = max(1, chosen_tenure)

            interest_rate_pct = _to_float(scheme.interest_rate_pct)
            # FD schemes charge no fees in this demo marketplace.
            all_fees = 0.0
            apr = interest_rate_pct

            return {
                "source": "fixed_deposit_scheme",
                "scheme_id": scheme.id,
                "issuer_name": scheme.issuer_name,
                "loan_amount": chosen_amount,
                "interest_rate": interest_rate_pct,
                "all_fees": all_fees,
                "apr": apr,
                "tenure_months": chosen_tenure,
                "disclaimer": _MOCK_DISCLAIMER,
            }

    return None
