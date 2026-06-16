"""
test_10_unique_constraints.py
==============================
Exhaustively tests all UniqueConstraints and unique=True columns across
every table in db_models.py.

Tables with unique constraints:
- users.username (unique=True)
- device_tokens.device_token (unique=True)
- news_articles.article_url (unique=True)
- youtube_videos.video_id (unique=True)
- fii_dii_flow.date (unique=True)
- advisor_biographies.sebi_reg_number (unique=True)
- advisor_insights: (video_id, ticker)
- pkscreener_signals: (ticker, signal_date)
- portfolio_valuation_history: (user_id, snapshot_date)
- net_worth_ledger: (user_id, snapshot_date)
- earnings_alerts: (user_id, ticker, earnings_date)
- portfolio: (user_id, ticker, group_name)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone
from _base import (
    TestRunner, User, Portfolio, DeviceToken, NewsArticle, YouTubeVideo,
    FIIDIIFlow, AdvisorBiography, AdvisorInsight, PKScreenerSignal,
    PortfolioValuationHistory, NetWorthLedger, EarningsAlert,
)
from sqlalchemy.exc import IntegrityError


def _now():
    return datetime.now(timezone.utc)


def run():
    runner = TestRunner("10_unique_constraints")
    runner.setup()
    session = runner.session

    # Create test user
    u = User(username="unique_test_user", password_hash="x" * 60, display_name="Unique Test")
    session.add(u)
    session.commit()
    uid = u.id

    def assert_duplicate_rejected(test_name: str, factory, description: str):
        try:
            for _ in range(2):
                session.add(factory())
                session.commit()
            runner.fail(
                test_name,
                f"UniqueConstraint NOT enforced: {description}. "
                f"Duplicate rows accepted. This will cause incorrect data in the application."
            )
        except IntegrityError as e:
            session.rollback()
            runner.ok(test_name, f"Duplicate correctly rejected: {description}")
        except Exception as e:
            session.rollback()
            runner.fail(test_name, f"Unexpected error for {description}: {e}", e)

    # ---- users.username uniqueness
    assert_duplicate_rejected(
        "users_username_unique",
        lambda: User(username="dup_user", password_hash="x" * 60, display_name="Dup"),
        "users.username must be globally unique"
    )

    # ---- device_tokens.device_token uniqueness
    session.add(DeviceToken(user_id=uid, device_token="unique_apns_token_001", platform="ios"))
    session.commit()
    try:
        session.add(DeviceToken(user_id=uid, device_token="unique_apns_token_001", platform="ios"))
        session.commit()
        runner.fail(
            "device_token_unique",
            "Duplicate device_token accepted. Same device would receive duplicate push notifications."
        )
    except IntegrityError:
        session.rollback()
        runner.ok("device_token_unique", "Duplicate device_token correctly rejected")

    # ---- news_articles.article_url uniqueness (prevents duplicate news ingestion)
    assert_duplicate_rejected(
        "news_articles_article_url_unique",
        lambda: NewsArticle(
            source="test", headline="Test Headline",
            article_url="https://example.com/news/001",
            published_at=_now(), sentiment="NEUTRAL"
        ),
        "news_articles.article_url — duplicate articles would inflate news feed"
    )

    # ---- youtube_videos.video_id uniqueness
    assert_duplicate_rejected(
        "youtube_videos_video_id_unique",
        lambda: YouTubeVideo(
            video_id="TEST_VID_001", channel_name="Test Channel",
            title="Test Video", video_url="https://youtube.com/watch?v=TEST_VID_001",
            published_at=_now()
        ),
        "youtube_videos.video_id — duplicate video would show twice in feed"
    )

    # ---- fii_dii_flow.date uniqueness
    assert_duplicate_rejected(
        "fii_dii_flow_date_unique",
        lambda: FIIDIIFlow(
            date="2026-06-17",
            fii_buy=1000.0, fii_sell=800.0, fii_net=200.0,
            dii_buy=500.0, dii_sell=400.0, dii_net=100.0
        ),
        "fii_dii_flow.date — duplicate FII/DII data for same day"
    )

    # ---- advisor_biographies.sebi_reg_number uniqueness
    assert_duplicate_rejected(
        "advisor_biographies_sebi_reg_unique",
        lambda: AdvisorBiography(
            advisor_name="Test Advisor",
            sebi_reg_number="INH000000001",
            full_biography_text="Test biography"
        ),
        "advisor_biographies.sebi_reg_number — same SEBI registration two advisors"
    )

    # ---- pkscreener_signals (ticker, signal_date) unique
    assert_duplicate_rejected(
        "pkscreener_signals_ticker_date_unique",
        lambda: PKScreenerSignal(ticker="RELIANCE", signal_date="2026-06-17"),
        "pkscreener_signals: (ticker, signal_date) composite unique"
    )

    # ---- portfolio_valuation_history (user_id, snapshot_date) unique
    assert_duplicate_rejected(
        "portfolio_valuation_history_user_date_unique",
        lambda: PortfolioValuationHistory(
            user_id=uid, snapshot_date="2026-06-17",
            total_value=100000.0, total_invested=90000.0,
            total_pnl=10000.0, pnl_percent=11.1
        ),
        "portfolio_valuation_history: (user_id, snapshot_date) composite unique"
    )

    # ---- net_worth_ledger (user_id, snapshot_date) unique
    assert_duplicate_rejected(
        "net_worth_ledger_user_date_unique",
        lambda: NetWorthLedger(
            user_id=uid, snapshot_date="2026-06-17", total_value_inr=1000000.0
        ),
        "net_worth_ledger: (user_id, snapshot_date) composite unique"
    )

    # ---- earnings_alerts (user_id, ticker, earnings_date) unique
    assert_duplicate_rejected(
        "earnings_alerts_user_ticker_date_unique",
        lambda: EarningsAlert(user_id=uid, ticker="RELIANCE", earnings_date="2026-07-15"),
        "earnings_alerts: (user_id, ticker, earnings_date) composite unique"
    )

    # ---- portfolio (user_id, ticker, group_name) unique
    assert_duplicate_rejected(
        "portfolio_user_ticker_group_unique",
        lambda: Portfolio(
            user_id=uid, ticker="DUPPER", company_name="Dup Corp",
            shares=10.0, buy_price=100.0, group_name="holdings"
        ),
        "portfolio: (user_id, ticker, group_name) composite unique"
    )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
