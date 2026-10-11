"""UX-04: the in-app legal notices are real (interim) text, not demo copy."""
from __future__ import annotations

import json

URL = "/api/v1/compliance/disclosures/{}"


def _get(client, key):
    resp = client.get(URL.format(key))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_privacy_policy_not_demo_and_names_llm_processors(client):
    body = _get(client, "privacy_policy")
    assert "Demo" not in body["title"]
    text = json.dumps(body)
    assert "MOCK" not in text
    for processor in ("DeepSeek", "Anthropic"):
        assert processor in text
    # FINSEC-03: the in-app control exists, so the policy must point to it.
    assert "Delete Account" in text


def test_data_sharing_has_no_false_no_third_party_claim(client):
    body = _get(client, "data_sharing_governance")
    text = json.dumps(body)
    assert "does not call any real third-party" not in text
    assert "Demo" not in body["title"]
    assert "MOCK" not in text
    for processor in ("DeepSeek", "Anthropic"):
        assert processor in text
    # REG-05: no real lender brand used as an example.
    for brand in ("HDFC", "Bajaj"):
        assert brand not in text


def test_terms_of_use_available(client):
    assert _get(client, "terms_of_use")["title"] == "Terms of Use"


def test_unknown_key_still_404(client):
    assert client.get(URL.format("not_a_real_key")).status_code == 404
