"""TEST-02: the test suite never starts analysis worker processes.

A real worker re-imports the app without the conftest SDK mocks, loads the .env keys
and runs paid DeepSeek/Claude analyses, so conftest records spawn_job calls instead
and makes multiprocessing's Process.start raise.
"""
import multiprocessing

import pytest


def test_analyze_records_spawn_without_starting_process(client, auth_headers, spawned_jobs):
    response = client.post("/analyze", json={"ticker": "ZZTESTSPAWN", "exchange": "NSE"},
                           headers=auth_headers)

    assert response.status_code == 202, response.text
    assert response.json().get("status") == "QUEUED"  # fresh ticker: cache miss, job queued
    assert len(spawned_jobs) == 1
    args, _kwargs = spawned_jobs[0]
    assert args[1] == "ZZTESTSPAWN"
    assert multiprocessing.active_children() == []


def test_process_start_is_blocked():
    with pytest.raises(RuntimeError, match="must not start real processes"):
        multiprocessing.Process(target=print).start()
