"""DB-33: JSON columns default to a real dict/list, not the JSON string "{}"/"[]".

A string default is JSON-encoded as a string, so an omitted field read back as
the str '{}' on both SQLite and PostgreSQL. Request-side length limits for
registration already live in schemas/auth.py and services/auth_service.py.
"""
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, AuditLogEntry, Base, CovarianceMatrix  # pyright: ignore[reportMissingImports]


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_omitted_json_fields_read_back_as_containers():
    s = _session()
    s.add_all([
        AnalysisHistory(ticker="TCS", analysis_date="2026-10-10", signal="HOLD", full_json="{}", raw_output=""),
        AuditLogEntry(user_id=1, action="test"),
        CovarianceMatrix(matrix_type="nifty"),
    ])
    s.commit()
    s.expire_all()

    hist: Any = s.query(AnalysisHistory).one()
    for value in (hist.confidence_math_breakdown, hist.quantitative_drivers, hist.tail_risk_flags):
        assert isinstance(value, dict) and value == {}
    details: Any = s.query(AuditLogEntry).one().details
    assert isinstance(details, dict) and details == {}
    cov: Any = s.query(CovarianceMatrix).one()
    assert isinstance(cov.tickers_list, list) and cov.tickers_list == []
    assert isinstance(cov.data_matrix, list) and cov.data_matrix == []
    s.close()


def test_defaults_are_not_shared_between_rows():
    s = _session()
    a: Any = AuditLogEntry(user_id=1, action="a")
    b: Any = AuditLogEntry(user_id=1, action="b")
    s.add_all([a, b])
    s.commit()
    assert a.details is not b.details
    s.close()
