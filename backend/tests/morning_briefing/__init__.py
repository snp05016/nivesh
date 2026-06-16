"""
Morning briefing test suite.

Shared constants and helpers for all test modules.
"""

MOCK_MORNING_BRIEF_TEXT = (
    "• RELIANCE is showing strength today, up 2.3% to ₹2,560 — watch for breakout above ₹2,600\n"
    "• TCS is flat after yesterday's rally; IT sector remains cautiously optimistic\n"
    "• Your portfolio P&L is in the green at +₹6,500 overall — solid start to the week\n"
    "• VIX has cooled to 13.2, indicating reduced fear in the market\n"
    "• Nifty 50 opened flat; no major macro triggers today\n"
    "Overall market mood: positive but stay alert for profit booking near resistance levels."
)


def _json_body(response):
    """Safely extract JSON from a TestClient response."""
    try:
        return response.json()
    except Exception:
        return {"_raw": response.text}
