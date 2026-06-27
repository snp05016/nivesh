import os
import re

filepath = "/Users/saumya/Desktop/nivesh-agy-fix-gh-issues-batch-4/backend/services/error_telemetry.py"

with open(filepath, 'r') as f:
    content = f.read()

new_query_logic = """
    try:
        from database import get_session, MarketErrorLog, EarningsErrorLog, NotificationErrorLog, IdeasErrorLog

        with get_session() as session:
            rows_market = (
                session.query(MarketErrorLog)
                .filter(MarketErrorLog.timestamp >= since)
                .all()
            )
            rows_earnings = (
                session.query(EarningsErrorLog)
                .filter(EarningsErrorLog.timestamp >= since)
                .all()
            )
            rows_notif = (
                session.query(NotificationErrorLog)
                .filter(NotificationErrorLog.timestamp >= since)
                .all()
            )
            rows_ideas = (
                session.query(IdeasErrorLog)
                .filter(IdeasErrorLog.timestamp >= since)
                .all()
            )
            
            # Combine into a unified format for digest
            class UnifiedError:
                def __init__(self, timestamp, component, context_ticker, error_message):
                    self.timestamp = timestamp
                    self.component = component
                    self.context_ticker = context_ticker
                    self.error_message = error_message
            
            all_errors = []
            for r in rows_market:
                all_errors.append(UnifiedError(r.timestamp, r.component, r.context_ticker, r.error_message))
            for r in rows_earnings:
                all_errors.append(UnifiedError(r.timestamp, r.module, r.failed_ticker, r.error_trace))
            for r in rows_notif:
                all_errors.append(UnifiedError(r.timestamp, "notification", r.recipient_id, r.error_trace))
            for r in rows_ideas:
                all_errors.append(UnifiedError(r.timestamp, "ideas", r.idea_id, r.error_message))
            
            # Sort descending
            all_errors.sort(key=lambda x: x.timestamp or since, reverse=True)
            rows = all_errors
            
    except Exception as e:
        rows = []
        digest_lines.append(f"[DIGEST] Could not query error logs: {e}")
"""

# Replace the try block
old_query_logic = """
    try:
        from database import get_session, MarketErrorLog

        with get_session() as session:
            rows = (
                session.query(MarketErrorLog)
                .filter(MarketErrorLog.timestamp >= since)
                .order_by(MarketErrorLog.timestamp.desc())
                .all()
            )
    except Exception as e:
        rows = []
        digest_lines.append(f"[DIGEST] Could not query market_error_logs: {e}")
"""

content = content.replace(old_query_logic.strip(), new_query_logic.strip())

with open(filepath, 'w') as f:
    f.write(content)
