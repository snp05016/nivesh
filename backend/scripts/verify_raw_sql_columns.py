import logging
#!/usr/bin/env python3
"""
Scan Python source files for raw SQL text() calls and flag any that reference
column names that don't exist in the current SQLAlchemy metadata.

This is a heuristic scanner — it may have false positives for dynamic SQL.
Exit 0 always (informational — does not block health check).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from models.db_models import Base
    model_columns: dict[str, set[str]] = {
        table: {col.name for col in meta.columns}
        for table, meta in Base.metadata.tables.items()
    }
    all_known_columns = {col for cols in model_columns.values() for col in cols}
except Exception as e:
    logging.info(f"[WARN] Could not load model metadata: {e}")
    sys.exit(0)

BACKEND_DIR = Path(__file__).parent.parent

# Patterns that suggest raw SQL column references
RAW_SQL_PATTERN = re.compile(
    r'text\s*\(\s*["\']([^"\']{10,})["\']',
    re.IGNORECASE,
)
# Pattern to extract identifiers that look like column names
COL_PATTERN = re.compile(r'\b([a-z_][a-z0-9_]{2,})\b')

suspicious: list[tuple[str, int, str, str]] = []

for py_file in BACKEND_DIR.rglob("*.py"):
    if "__pycache__" in str(py_file) or "venv" in str(py_file):
        continue
    try:
        content = py_file.read_text(errors="ignore")
    except Exception:
        continue

    for lineno, line in enumerate(content.splitlines(), 1):
        for match in RAW_SQL_PATTERN.finditer(line):
            sql_fragment = match.group(1)
            # Extract potential column refs
            candidates = COL_PATTERN.findall(sql_fragment.lower())
            for cand in candidates:
                # Skip SQL keywords and short tokens
                if cand in {"select", "from", "where", "and", "or", "not", "in",
                            "join", "on", "is", "null", "true", "false", "case",
                            "when", "then", "else", "end", "like", "between",
                            "group", "order", "by", "asc", "desc", "limit", "offset",
                            "inner", "outer", "left", "right", "having", "count",
                            "sum", "avg", "min", "max", "distinct", "exists", "set",
                            "update", "insert", "delete", "into", "values", "create",
                            "table", "index", "alter", "drop", "pragma"}:
                    continue
                # Flag if it looks like a column reference (long enough, contains _)
                if "_" in cand and cand not in all_known_columns:
                    rel_path = py_file.relative_to(BACKEND_DIR)
                    suspicious.append((str(rel_path), lineno, cand, sql_fragment[:60]))

if suspicious:
    logging.info(f"[WARN] {len(suspicious)} potentially stale raw SQL column references:")
    seen = set()
    for path, lineno, col, fragment in suspicious[:20]:  # cap at 20
        key = f"{path}:{col}"
        if key not in seen:
            logging.info(f"  {path}:{lineno} — '{col}' not in model (fragment: {fragment!r})")
            seen.add(key)
    if len(suspicious) > 20:
        logging.info(f"  ... and {len(suspicious)-20} more (run with -v for full list)")
else:
    logging.info("[OK] No obviously stale raw SQL column references found")

sys.exit(0)
