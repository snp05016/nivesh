"""
test_08_unicode_exceptions.py
==============================
Tests Unicode exception handling for:
- Indian text (₹ symbol, Hindi characters, Devanagari)
- UnicodeEncodeError (non-UTF-8 terminal output)
- UnicodeDecodeError (binary data in text field)
- IndianFormatter number handling with Unicode symbols
- JSON serialization of Unicode strings

The Nivesh app deals with Indian company names, Hindi text in Advisory,
and ₹ currency symbols which can cause issues in:
- File paths (logs on Windows)
- JSON encoding (default encoders)
- SQLite storage (requires UTF-8)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def run():
    runner = TestRunner("08_unicode_exceptions")

    # ---- ₹ symbol round-trip through JSON
    amount_str = "₹2,50,000.00"
    try:
        encoded = json.dumps({"amount": amount_str})
        decoded = json.loads(encoded)
        if decoded["amount"] == amount_str:
            runner.ok("rupee_json_roundtrip", f"₹ symbol survives JSON round-trip: '{decoded['amount']}'")
        else:
            runner.fail("rupee_json_roundtrip", f"₹ symbol changed after JSON round-trip: '{decoded['amount']}'")
    except (UnicodeEncodeError, UnicodeDecodeError, json.JSONDecodeError) as e:
        runner.fail("rupee_json_roundtrip", f"Unicode error in JSON: {e}", e)

    # ---- Hindi text round-trip
    hindi_text = "नमस्ते — यह एक परीक्षण है"
    try:
        encoded = json.dumps({"text": hindi_text}, ensure_ascii=False)
        decoded = json.loads(encoded)
        if decoded["text"] == hindi_text:
            runner.ok("hindi_json_roundtrip", f"Hindi text survives JSON round-trip")
        else:
            runner.fail("hindi_json_roundtrip", "Hindi text changed after JSON round-trip")
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        runner.fail("hindi_json_roundtrip", f"Unicode error with Hindi text: {e}", e)

    # ---- ASCII-only JSON encoding (ensure_ascii=True drops ₹ but doesn't lose data)
    try:
        encoded_ascii = json.dumps({"amount": "₹2,50,000"}, ensure_ascii=True)
        decoded_ascii = json.loads(encoded_ascii)
        # With ensure_ascii=True, ₹ becomes \u20b9
        runner.ok("ensure_ascii_encoding",
                  f"ensure_ascii=True produces: {encoded_ascii[:60]}")
        if decoded_ascii["amount"] == "₹2,50,000":
            runner.ok("ensure_ascii_roundtrip", "₹ decoded back correctly from escaped unicode")
        else:
            runner.fail("ensure_ascii_roundtrip",
                        f"₹ not decoded correctly: '{decoded_ascii['amount']}'")
    except Exception as e:
        runner.fail("ensure_ascii_encoding", f"Unexpected error: {e}", e)

    # ---- UnicodeEncodeError: encode ₹ to ASCII
    try:
        "₹2,50,000".encode("ascii")
        runner.fail("UnicodeEncodeError_rupee_ascii",
                    "₹ encoded to ASCII without error — this should be impossible")
    except UnicodeEncodeError as e:
        runner.ok("UnicodeEncodeError_rupee_ascii",
                  f"UnicodeEncodeError on ₹→ASCII: '{e}'. "
                  f"Always use UTF-8 encoding for Indian financial data.")

    # ---- UnicodeDecodeError: decode binary as UTF-8
    try:
        b"\xff\xfe".decode("utf-8")
        runner.fail("UnicodeDecodeError_binary",
                    "Binary bytes decoded as UTF-8 without error")
    except UnicodeDecodeError as e:
        runner.ok("UnicodeDecodeError_binary",
                  f"UnicodeDecodeError on binary→UTF-8: '{e}'. "
                  f"Never decode yfinance binary responses as UTF-8 without error handling.")

    # ---- ₹ in SQLite (should work fine with UTF-8)
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE symbols (currency TEXT)")
    conn.execute("INSERT INTO symbols VALUES (?)", ("₹",))
    cursor = conn.execute("SELECT currency FROM symbols")
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == "₹":
        runner.ok("rupee_sqlite_storage", "₹ symbol stored and retrieved from SQLite correctly")
    else:
        runner.fail("rupee_sqlite_storage",
                    f"₹ symbol changed in SQLite: '{row}'. "
                    f"Ensure SQLite connection uses UTF-8 (it does by default in Python).")

    # ---- Company names with special characters
    company_names = [
        "Reliance Industries Ltd",
        "भारत पेट्रोलियम कॉर्पोरेशन",  # BPCL in Hindi
        "Tata Elxsi — Tech Company",  # em-dash
        "L&T Finance Holdings Ltd",   # ampersand
        "3M India Ltd",               # starts with number
    ]
    for name in company_names:
        try:
            j = json.dumps({"company": name}, ensure_ascii=False)
            decoded = json.loads(j)
            if decoded["company"] == name:
                runner.ok(f"company_name_unicode:{name[:20]}",
                          f"Company name round-trip OK: '{name[:30]}'")
            else:
                runner.fail(f"company_name_unicode:{name[:20]}",
                            f"Company name changed: '{decoded['company'][:30]}'")
        except Exception as e:
            runner.fail(f"company_name_unicode:{name[:20]}",
                        f"Unicode error with company name: {e}", e)

    # ---- UnicodeError hierarchy
    if issubclass(UnicodeDecodeError, UnicodeError):
        runner.ok("hierarchy:UnicodeDecodeError→UnicodeError")
    if issubclass(UnicodeEncodeError, UnicodeError):
        runner.ok("hierarchy:UnicodeEncodeError→UnicodeError")
    if issubclass(UnicodeTranslateError, UnicodeError):
        runner.ok("hierarchy:UnicodeTranslateError→UnicodeError")
    if issubclass(UnicodeError, ValueError):
        runner.ok("hierarchy:UnicodeError→ValueError")

    # ---- Indian number format strings
    lakhs_str = "₹45.67 L"
    crores_str = "₹1.23 Cr"
    try:
        # These should be storable and retrievable as plain strings
        for s in [lakhs_str, crores_str]:
            encoded = json.dumps(s, ensure_ascii=False)
            decoded = json.loads(encoded)
            assert decoded == s
        runner.ok("indian_format_strings", "Lakhs/Crores format strings JSON-safe")
    except Exception as e:
        runner.fail("indian_format_strings", f"Indian format string error: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
