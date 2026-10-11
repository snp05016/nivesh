"""GH-694: smoke_all_endpoints.py must list real routes with exact expected statuses."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "smoke_all_endpoints.py"


def _load_endpoints():
    spec = importlib.util.spec_from_file_location("smoke_all_endpoints", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # no side effects: work happens in main()
    return module.ENDPOINTS


def test_smoke_endpoints_return_expected_status(client):
    endpoints = _load_endpoints()
    assert endpoints
    for path, expected in endpoints:
        assert client.get(path).status_code == expected, path


def test_smoke_script_has_shebang_first():
    assert SCRIPT.read_text().splitlines()[0].startswith("#!")
