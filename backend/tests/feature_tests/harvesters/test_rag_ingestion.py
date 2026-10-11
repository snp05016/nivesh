"""REL-21 — incremental RAG ingestion: chunk ids carry the source row id, and a run with
no new rows does no embedding work."""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# Heavy/optional deps: use the real module when installed, otherwise a stub. Every call
# into them below is patched, so the tests behave the same either way.
for _name in ("sentence_transformers", "langchain_text_splitters", "psycopg2",
              "psycopg2.extras", "pgvector", "pgvector.psycopg2"):
    try:
        importlib.import_module(_name)
    except ImportError:
        sys.modules[_name] = MagicMock()

from services import rag_ingestion  # noqa: E402
from services.rag_ingestion import _make_chunk_id, ingest_new  # noqa: E402


@pytest.fixture
def fake_env():
    """Patch the splitter, model and vector store; yield (model, upsert mock)."""
    splitter = MagicMock()
    splitter.split_text.side_effect = lambda text: [text]  # one chunk per row
    model = MagicMock()
    model.encode.side_effect = lambda docs: MagicMock(tolist=lambda: [[0.1, 0.2, 0.3]] * len(docs))
    with patch.object(rag_ingestion, "RecursiveCharacterTextSplitter", return_value=splitter), \
         patch.object(rag_ingestion, "_get_embedding_model", return_value=model), \
         patch.object(rag_ingestion, "upsert_documents") as upsert, \
         patch.object(rag_ingestion, "collection_count", return_value=0), \
         patch.object(rag_ingestion, "delete_legacy_chunks", return_value=0):
        yield model, upsert


def test_chunk_ids_include_row_id():
    assert _make_chunk_id("news_article", 1, 0) != _make_chunk_id("news_article", 2, 0)
    assert _make_chunk_id("news_article", 7, 3) == "news_article:7:3"


def test_same_ticker_same_day_articles_not_overwritten(fake_env):
    _model, upsert = fake_env
    news_rows = [
        (1, "TCS", "first article body", "2026-01-05", "https://a"),
        (2, "TCS", "second article body", "2026-01-05", "https://b"),
    ]

    def fetch(doc_type, after_id, limit=200):
        return news_rows if doc_type == "news_article" and after_id == 0 else []

    with patch.object(rag_ingestion, "max_ingested_row_id", return_value=None), \
         patch.object(rag_ingestion, "_fetch_batch", side_effect=fetch):
        total = ingest_new()

    ids = [cid for call in upsert.call_args_list for cid in call.args[0]]
    assert total == 2
    assert len(set(ids)) == 2
    assert set(ids) == {"news_article:1:0", "news_article:2:0"}


def test_second_run_no_new_rows_zero_encode(fake_env):
    model, upsert = fake_env
    with patch.object(rag_ingestion, "max_ingested_row_id", return_value=2), \
         patch.object(rag_ingestion, "_fetch_batch", return_value=[]) as fetch:
        total = ingest_new()

    assert total == 0
    assert model.encode.call_count == 0
    upsert.assert_not_called()
    # resumes after the watermark for both doc types
    assert {c.args[:2] for c in fetch.call_args_list} == {("news_article", 2), ("advisor_transcript", 2)}
