"""GH-630: /trade-journal/{user_id}/stats serves only the path user, and only to that user.

Before the fix a mismatched path returned the caller's stats labelled with another id.
No LLM call: DEEPSEEK_API_KEY is removed, so patterns stay [].
"""


def test_stats_rejects_mismatched_path_user(client, auth_headers, test_user_id):
    resp = client.get(f"/trade-journal/{test_user_id + 100000}/stats", headers=auth_headers)
    assert resp.status_code == 403


def test_stats_returns_own_user_id(client, auth_headers, test_user_id, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    resp = client.get(f"/trade-journal/{test_user_id}/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == test_user_id
    assert body["patterns"] == []
