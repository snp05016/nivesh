import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from services.rag_ingestion import ingest_all, ingest_new, _make_chunk_id

@pytest.fixture
def mock_db_session():
    with patch("services.rag_ingestion.get_session") as mock_session_maker:
        session = MagicMock()
        mock_session_maker.return_value.__enter__.return_value = session
        yield session

@pytest.fixture
def mock_vector_store():
    with patch("services.rag_ingestion.upsert_documents") as mock_upsert, \
         patch("services.rag_ingestion.collection_count", return_value=10) as mock_count:
        yield mock_upsert, mock_count

@pytest.fixture
def mock_sentence_transformer():
    with patch("services.rag_ingestion.SentenceTransformer") as mock_st:
        model = MagicMock()
        model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2, 0.3]])
        mock_st.return_value = model
        yield mock_st

def test_make_chunk_id():
    chunk_id = _make_chunk_id("AAPL", "2023-01-01", "news_article", 5)
    assert chunk_id == "AAPL_2023-01-01_news_article_chunk5"

def test_ingest_all(mock_db_session, mock_vector_store, mock_sentence_transformer):
    mock_upsert, _ = mock_vector_store
    
    # Mock data
    class MockArticle:
        ticker = "AAPL"
        body_text = "This is a test article body."
        published_at = datetime(2023, 1, 1)
        article_url = "http://example.com"
        
    class MockInsight:
        ticker = "GOOGL"
        raw_snippet = "This is a test insight."
        published_at = datetime(2023, 1, 2)
        advisor_name = "Test Advisor"
        
    # Setup mock query results
    mock_query = mock_db_session.query.return_value
    mock_query.filter.return_value.all.return_value = [MockArticle()]
    mock_query.all.return_value = [MockInsight()]
    
    total_chunks = ingest_all()
    
    assert total_chunks == 2
    assert mock_upsert.call_count == 2
    
    # Check first upsert call for article
    args, kwargs = mock_upsert.call_args_list[0]
    batch_ids, batch_docs, batch_metas, embeddings = args
    assert len(batch_ids) == 1
    assert "AAPL_2023-01-01_news_article_chunk0" in batch_ids
    assert batch_metas[0]["ticker"] == "AAPL"
    
    # Check second upsert call for insight
    args, kwargs = mock_upsert.call_args_list[1]
    batch_ids, batch_docs, batch_metas, embeddings = args
    assert len(batch_ids) == 1
    assert "GOOGL_2023-01-02_advisor_transcript_chunk0" in batch_ids
    assert batch_metas[0]["ticker"] == "GOOGL"

def test_ingest_new(mock_db_session, mock_vector_store, mock_sentence_transformer):
    mock_upsert, _ = mock_vector_store
    
    with patch("services.rag_ingestion.ingest_all", return_value=5) as mock_ingest_all:
        count = ingest_new()
        assert count == 5
        mock_ingest_all.assert_called_once()
