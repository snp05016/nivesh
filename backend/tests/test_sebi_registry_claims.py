"""REG-01: SEBI registration claims come only from services/sebi_registry.py.

No endpoint may report a registration number or is_verified=True that the registry
does not back, no other backend module may hold an INH/INA literal, and harvested
cards from unregulated sources must not claim SEBI registration.
"""
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services import harvester_db, harvester_reformatter
from services.sebi_registry import REGISTERED_CHANNELS

BACKEND = Path(__file__).resolve().parents[1]
REGISTRY_FILE = BACKEND / "services" / "sebi_registry.py"
REGISTERED_NUMBERS = {c["sebi_reg"] for c in REGISTERED_CHANNELS}


def test_ideas_advisors_only_registry(client):
    from database import get_session
    from models.db_models import AdvisorBiography

    # A row the old auto-seed could have left behind must never be served.
    stale = f"STALE-{uuid.uuid4().hex[:8]}"
    with get_session() as s:
        s.add(AdvisorBiography(advisor_name="Rajesh Palviya", sebi_reg_number=stale,
                               experience_years=18, full_biography_text="stale seed"))
        s.commit()
    try:
        resp = client.get("/api/v1/ideas/advisors")
        assert resp.status_code == 200, resp.text
        advisors = resp.json()["advisors"]
        assert len(advisors) == len(REGISTERED_CHANNELS)
        assert {a["sebi_reg_number"] for a in advisors} <= REGISTERED_NUMBERS
        assert all(a["advisor_name"] != "Rajesh Palviya" for a in advisors)
    finally:
        with get_session() as s:
            s.query(AdvisorBiography).filter(AdvisorBiography.sebi_reg_number == stale).delete()
            s.commit()


def test_experts_verified_only_for_registry(client):
    from database import get_session
    from models.db_models import AdvisorInsight

    registered = next(c for c in REGISTERED_CHANNELS if c.get("channel_id"))
    unlisted_name = next(c["name"] for c in REGISTERED_CHANNELS if not c.get("channel_id"))
    tag = uuid.uuid4().hex[:8]
    advisors = {
        f"REG01 Registered {tag}": registered["channel_id"],
        f"REG01 Unregistered {tag}": "UCAk_whGHM2aAiZZADLF_GOw",
        # Borrows a registered entity's name from an unknown channel.
        unlisted_name: f"UCfake{tag}",
    }
    video_ids = []
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for name, channel_id in advisors.items():
            for i in range(2):
                vid = f"reg01-{tag}-{len(video_ids)}"
                video_ids.append(vid)
                s.add(AdvisorInsight(
                    ticker="RELIANCE", advisor_name=name, channel_id=channel_id,
                    video_id=vid, video_title="t", video_url=f"https://example.invalid/{vid}",
                    published_at=now, transcript_source="test", stance="BULLISH",
                    confidence="HIGH", catalyst_summary="test", view_count=1,
                ))
        s.commit()
    try:
        resp = client.get("/api/v1/experts")
        assert resp.status_code == 200, resp.text
        experts = {e["name"]: e for e in resp.json()["experts"]}

        reg = experts[f"REG01 Registered {tag}"]
        assert reg["is_verified"] is True
        assert reg["sebi_reg_id"] == registered["sebi_reg"]
        for name in (f"REG01 Unregistered {tag}", unlisted_name):
            assert experts[name]["is_verified"] is False
            assert experts[name]["sebi_reg_id"] is None
        for e in experts.values():
            if e["is_verified"] or e["sebi_reg_id"]:
                assert e["sebi_reg_id"] in REGISTERED_NUMBERS, e
    finally:
        with get_session() as s:
            s.query(AdvisorInsight).filter(AdvisorInsight.video_id.in_(video_ids)).delete(
                synchronize_session=False
            )
            s.commit()


def test_inh_literals_only_in_registry():
    pattern = re.compile(r"IN[AH]\d{9}")
    skip = {"tests", "tradingagents-core", "venv", "__pycache__", "node_modules"}
    offenders = []
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [
            d for d in dirs
            if d not in skip and not d.startswith(".")
            and not (Path(root) / d / "pyvenv.cfg").exists()
        ]
        for name in files:
            path = Path(root) / name
            if name.endswith(".py") and path != REGISTRY_FILE:
                if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                    offenders.append(str(path.relative_to(BACKEND)))
    assert offenders == [], f"INH/INA numbers belong in services/sebi_registry.py only: {offenders}"


def test_youtube_credential_has_no_sebi_claim():
    assert "sebi" not in harvester_reformatter.derive_credential("YOUTUBE").lower()


def test_llm_cannot_raise_credibility_or_claim_registration(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    llm_card = {
        "title": "Reliance outlook", "reformatted_summary": "Bullish on RELIANCE.",
        "key_takeaways": ["x"], "tickers": ["RELIANCE"], "sentiment": "BULLISH",
        "credibility_score": 10, "expert_credential": "SEBI-registered RA",
    }
    monkeypatch.setattr(harvester_reformatter, "deepseek_chat", lambda *a, **k: json.dumps(llm_card))

    card = harvester_reformatter.reformat_single("Video transcript about RELIANCE", "YOUTUBE", "Some Channel")
    assert card is not None
    assert card["credibility_score"] <= harvester_reformatter.DEFAULT_CREDIBILITY["YOUTUBE"]
    assert card["expert_credential"] == harvester_reformatter.derive_credential("YOUTUBE")

    # A regulated source keeps its LLM credential.
    llm_card["expert_credential"] = "CRISIL — SEBI-registered credit rating agency"
    card = harvester_reformatter.reformat_single("Rating action text", "CRISIL_RATING", "CRISIL")
    assert card is not None
    assert card["credibility_score"] == 10
    assert card["expert_credential"] == llm_card["expert_credential"]


def test_scrub_resets_stored_sebi_claims_on_unregulated_cards(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    harvester_db.Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    @contextmanager
    def _session():
        s = session_factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    monkeypatch.setattr(harvester_db, "get_session", _session)
    rows = {
        "YOUTUBE": "SEBI-registered finance creator / market commentator",
        "EXPERT_COLUMN": "SEBI registered analyst at a brokerage",
        "CRISIL_RATING": "CRISIL — SEBI-regulated credit rating agency",
    }
    with _session() as s:
        for i, (source_type, credential) in enumerate(rows.items()):
            s.add(harvester_db.HarvestedCard(
                external_id=f"reg01-{i}", source_type=source_type, source_name="x",
                source_url="https://example.invalid", title="t", raw_text="r",
                credibility_score=6, card_type="EXPERT", expert_credential=credential,
            ))

    harvester_db._scrub_unverified_sebi_claims()

    card = harvester_db.HarvestedCard
    with _session() as s:
        got = {st: cred for st, cred in s.query(card.source_type, card.expert_credential)}
    assert got["YOUTUBE"] == harvester_reformatter.derive_credential("YOUTUBE")
    assert got["EXPERT_COLUMN"] == harvester_reformatter.derive_credential("EXPERT_COLUMN")
    assert got["CRISIL_RATING"] == rows["CRISIL_RATING"]
