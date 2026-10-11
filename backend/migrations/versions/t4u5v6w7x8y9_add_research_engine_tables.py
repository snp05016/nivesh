"""Add Research Engine ledger tables (spec §8.1)

Creates research_runs, research_reports, research_predictions and
research_live_metrics, identical to the ResearchRun, ResearchReportRow,
ResearchPrediction and ResearchLiveMetric models in models/db_models.py.

Idempotent: each table is created only if it does not exist (the initial
revision runs Base.metadata.create_all, so fresh databases already have
them), and downgrade drops only tables that exist.

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t4u5v6w7x8y9"
down_revision: Union[str, Sequence[str], None] = "s3t4u5v6w7x8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    if "research_runs" not in existing_tables:
        op.create_table(
            "research_runs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_uid", sa.String(length=40), nullable=True),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("market_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("stage", sa.String(length=40), nullable=True),
            sa.Column("counts_json", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_uid", name="uq_research_runs_run_uid"),
            sa.CheckConstraint("kind IN ('nightly','outcomes','live_metrics')", name="ck_research_runs_kind"),
            sa.CheckConstraint(
                "status IN ('running','ok','degraded','failed','skipped_holiday')",
                name="ck_research_runs_status",
            ),
        )
        op.create_index(
            "ix_research_runs_kind_market_date", "research_runs", ["kind", "market_date"], unique=False,
        )

    if "research_reports" not in existing_tables:
        op.create_table(
            "research_reports",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("report_uid", sa.String(length=36), nullable=False),
            sa.Column("symbol", sa.String(length=30), nullable=False),
            sa.Column("isin", sa.String(length=12), nullable=True),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("engine_version", sa.String(length=40), nullable=False),
            sa.Column("procedure_id", sa.String(length=40), nullable=True),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("origin", sa.String(length=10), nullable=False),
            sa.Column("status", sa.String(length=10), nullable=False),
            sa.Column("in_universe", sa.Boolean(), nullable=False),
            sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
            sa.Column("report_json", sa.JSON(), nullable=False),
            sa.Column("facts_hash", sa.String(length=64), nullable=True),
            sa.Column("narrative_json", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("narrative_status", sa.String(length=16), nullable=True),
            sa.Column("narrative_attempts", sa.SmallInteger(), server_default="0", nullable=False),
            sa.Column("narrative_failures_json", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("narrative_generated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("report_uid", name="uq_research_reports_report_uid"),
            sa.UniqueConstraint(
                "symbol", "as_of_date", "engine_version", "origin",
                name="uq_research_reports_symbol_date_engine_origin",
            ),
            sa.CheckConstraint("origin IN ('nightly','on_demand')", name="ck_research_reports_origin"),
            sa.CheckConstraint("status IN ('ok','degraded')", name="ck_research_reports_status"),
            sa.CheckConstraint(
                "narrative_status IN ('llm_validated','template')",
                name="ck_research_reports_narrative_status",
            ),
        )
        op.create_index(
            "ix_research_reports_symbol_as_of_date", "research_reports", ["symbol", "as_of_date"], unique=False,
        )

    if "research_predictions" not in existing_tables:
        op.create_table(
            "research_predictions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=30), nullable=False),
            sa.Column("isin", sa.String(length=12), nullable=True),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("horizon_days", sa.SmallInteger(), nullable=False),
            sa.Column("procedure_id", sa.String(length=40), nullable=False),
            sa.Column("model_id", sa.String(length=80), nullable=False),
            sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
            sa.Column("universe_id", sa.String(length=20), nullable=False),
            sa.Column("evidence_tier", sa.String(length=24), nullable=False),
            sa.Column("reason_codes", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("rank_pct", sa.Float(), nullable=False),
            sa.Column("bucket", sa.SmallInteger(), nullable=True),
            sa.Column("p_top_half", sa.Float(), nullable=True),
            sa.Column("entry_close", sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column("feature_hash", sa.String(length=64), nullable=True),
            sa.Column("expected_maturity_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("outcome_status", sa.String(length=10), server_default="pending", nullable=False),
            sa.Column("void_reason", sa.String(length=40), nullable=True),
            sa.Column("realized_return_pct", sa.Float(), nullable=True),
            sa.Column("realized_excess_pp", sa.Float(), nullable=True),
            sa.Column("realized_top_half", sa.Boolean(), nullable=True),
            sa.Column("nifty50_return_pct", sa.Float(), nullable=True),
            sa.Column("stale_exit", sa.Boolean(), nullable=True),
            sa.Column("scored_at", sa.DateTime(), nullable=True),
            sa.Column("scorer_version", sa.String(length=20), nullable=True),
            sa.ForeignKeyConstraint(["report_id"], ["research_reports.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("report_id", "horizon_days", name="uq_research_predictions_report_horizon"),
            sa.UniqueConstraint(
                "symbol", "as_of_date", "horizon_days", "model_id",
                name="uq_research_predictions_symbol_date_horizon_model",
            ),
            sa.CheckConstraint("horizon_days IN (21,63)", name="ck_research_predictions_horizon"),
            sa.CheckConstraint(
                "outcome_status IN ('pending','matured','void')",
                name="ck_research_predictions_outcome_status",
            ),
        )
        op.create_index(
            "ix_research_predictions_outcome_maturity",
            "research_predictions",
            ["outcome_status", "expected_maturity_date"],
            unique=False,
        )
        op.create_index(
            "ix_research_predictions_procedure_horizon_as_of",
            "research_predictions",
            ["procedure_id", "horizon_days", "as_of_date"],
            unique=False,
        )

    if "research_live_metrics" not in existing_tables:
        op.create_table(
            "research_live_metrics",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("procedure_id", sa.String(length=40), nullable=False),
            sa.Column("horizon_days", sa.SmallInteger(), nullable=False),
            sa.Column("computed_on", sa.Date(), nullable=False),
            sa.Column("live_status", sa.String(length=16), nullable=False),
            sa.Column("live_gate_passed", sa.Boolean(), nullable=False),
            sa.Column("matured_n", sa.Integer(), nullable=False),
            sa.Column("matured_dates", sa.Integer(), nullable=False),
            sa.Column("metrics_json", sa.JSON(), nullable=False),
            sa.Column("alarms_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "procedure_id", "horizon_days", "computed_on",
                name="uq_research_live_metrics_procedure_horizon_day",
            ),
            sa.CheckConstraint(
                "live_status IN ('collecting','ok','under_review')",
                name="ck_research_live_metrics_live_status",
            ),
        )


def downgrade() -> None:
    """Downgrade schema (children first; indexes go with their tables)."""
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    for table in ("research_live_metrics", "research_predictions", "research_reports", "research_runs"):
        if table in existing_tables:
            op.drop_table(table)
