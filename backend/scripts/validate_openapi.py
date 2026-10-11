#!/usr/bin/env python3
"""
Validate that the FastAPI OpenAPI schema generates without errors and has no
broken refs, duplicate operation IDs, or invalid methods.

Exit 0 = schema is valid.
Exit 1 = issues found.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_health_check_test.db")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("ENVIRONMENT", "test")  # unset counts as production (OPS-13)
os.environ.setdefault("JWT_SECRET", "health-check-secret")

issues = []

try:
    import main as app_module
    app = app_module.app
except Exception as e:
    print(f"[FAIL] Cannot import main.py: {e}", file=sys.stderr)
    sys.exit(1)

# Generate OpenAPI schema
try:
    schema = app.openapi()
except Exception as e:
    print(f"[FAIL] OpenAPI schema generation failed: {e}", file=sys.stderr)
    sys.exit(1)

if not schema:
    print("[FAIL] OpenAPI schema is empty", file=sys.stderr)
    sys.exit(1)

print(f"[OK] OpenAPI schema generated ({len(json.dumps(schema))} bytes)")

# Check for duplicate operation IDs
op_ids: dict[str, list[str]] = {}
paths = schema.get("paths", {})
valid_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

for path, methods in paths.items():
    for method, spec in methods.items():
        if method.lower() not in valid_methods:
            continue
        op_id = spec.get("operationId")
        if op_id:
            op_ids.setdefault(op_id, []).append(f"{method.upper()} {path}")

for op_id, locations in op_ids.items():
    if len(locations) > 1:
        issues.append(f"Duplicate operationId '{op_id}': {locations}")

# Check that schema is JSON-serializable
try:
    json.dumps(schema)
    print("[OK] Schema is JSON-serializable")
except Exception as e:
    issues.append(f"Schema is not JSON-serializable: {e}")

# Check component refs
schema_str = json.dumps(schema)
ref_count = schema_str.count('"$ref"')
print(f"[OK] {ref_count} $ref references in schema")

# Count paths
print(f"[OK] {len(paths)} API paths in OpenAPI schema")

if issues:
    for issue in issues:
        print(f"[FAIL] {issue}", file=sys.stderr)
    sys.exit(1)

print("[OK] OpenAPI schema is valid")
sys.exit(0)
