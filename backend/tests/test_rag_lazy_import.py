"""PERF-14 — importing services.rag_ingestion must not import sentence_transformers
(and with it torch) in every web worker; MiniLM loads only when there is text to embed.

The "nothing new -> model.encode is never called" half of PERF-14 is covered by
tests/feature_tests/harvesters/test_rag_ingestion.py::test_second_run_no_new_rows_zero_encode.
"""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import services

MODULE = "services.rag_ingestion"


class _Tripwire(types.ModuleType):
    """Module stub that records (and refuses) any attribute lookup such as
    `from sentence_transformers import SentenceTransformer`."""

    def __init__(self, name):
        super().__init__(name)
        self.touched = []

    def __getattr__(self, attr):
        self.touched.append(attr)
        raise AttributeError(attr)


def test_import_and_empty_run_do_not_touch_sentence_transformers(monkeypatch):
    # Optional deps of the module's other imports: stub only when not installed.
    for name in ("langchain_text_splitters", "psycopg2", "psycopg2.extras",
                 "pgvector", "pgvector.psycopg2"):
        try:
            importlib.import_module(name)
        except ImportError:
            monkeypatch.setitem(sys.modules, name, MagicMock())

    tripwire = _Tripwire("sentence_transformers")
    monkeypatch.setitem(sys.modules, "sentence_transformers", tripwire)
    # Force a fresh import; monkeypatch puts back any previously imported module.
    monkeypatch.setitem(sys.modules, MODULE, None)
    monkeypatch.delitem(sys.modules, MODULE)
    monkeypatch.setattr(services, "rag_ingestion",
                        getattr(services, "rag_ingestion", None), raising=False)

    rag_ingestion = importlib.import_module(MODULE)
    assert tripwire.touched == []

    # A run with no new rows must not load the embedding model either.
    with patch.object(rag_ingestion, "max_ingested_row_id", return_value=5), \
         patch.object(rag_ingestion, "_fetch_batch", return_value=[]), \
         patch.object(rag_ingestion, "collection_count", return_value=0):
        assert rag_ingestion.ingest_new() == 0
    assert tripwire.touched == []
    assert rag_ingestion._model is None
