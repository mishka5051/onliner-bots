"""Event enrichment and scoring fields.

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("event_candidates", sa.Column("is_minsk", sa.Boolean(), nullable=True))
    op.add_column("event_candidates", sa.Column("estimated_attendance", sa.Integer(), nullable=True))
    op.add_column("event_candidates", sa.Column("attendance_source", sa.String(length=50), nullable=True))
    op.add_column("event_candidates", sa.Column("event_type", sa.String(length=50), nullable=True))
    op.add_column("event_candidates", sa.Column("theme_tags", sa.JSON(), nullable=True))
    op.add_column("event_candidates", sa.Column("is_free", sa.Boolean(), nullable=True))
    op.add_column("event_candidates", sa.Column("ticket_info", sa.Text(), nullable=True))
    op.add_column("event_candidates", sa.Column("is_recurring", sa.Boolean(), nullable=True))
    op.add_column("event_candidates", sa.Column("edition_label", sa.String(length=50), nullable=True))
    op.add_column("event_candidates", sa.Column("parent_event_key", sa.String(length=255), nullable=True))
    op.add_column(
        "event_candidates",
        sa.Column("partner_participation_possible", sa.Boolean(), nullable=True),
    )
    op.add_column("event_candidates", sa.Column("partner_formats", sa.JSON(), nullable=True))
    op.add_column("event_candidates", sa.Column("organizer_benefits", sa.Text(), nullable=True))
    op.add_column("event_candidates", sa.Column("onliner_fit_score", sa.Integer(), nullable=True))
    op.add_column("event_candidates", sa.Column("trend_score", sa.Integer(), nullable=True))
    op.add_column("event_candidates", sa.Column("relevance_score", sa.Integer(), nullable=True))
    op.add_column("event_candidates", sa.Column("score_breakdown", sa.JSON(), nullable=True))
    op.add_column(
        "event_candidates",
        sa.Column("enrichment_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column("event_candidates", sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("event_candidates", sa.Column("page_text", sa.Text(), nullable=True))
    op.add_column("event_candidates", sa.Column("page_fetch_error", sa.Text(), nullable=True))
    op.add_column("event_candidates", sa.Column("lead_time_days", sa.Integer(), nullable=True))
    op.add_column("event_candidates", sa.Column("is_enough_lead_time", sa.Boolean(), nullable=True))

    op.create_index("ix_event_candidates_relevance_score", "event_candidates", ["relevance_score"])
    op.create_index("ix_event_candidates_enrichment_status", "event_candidates", ["enrichment_status"])
    op.create_index("ix_event_candidates_parent_event_key", "event_candidates", ["parent_event_key"])
    op.create_index("ix_event_candidates_is_minsk", "event_candidates", ["is_minsk"])


def downgrade() -> None:
    op.drop_index("ix_event_candidates_is_minsk", table_name="event_candidates")
    op.drop_index("ix_event_candidates_parent_event_key", table_name="event_candidates")
    op.drop_index("ix_event_candidates_enrichment_status", table_name="event_candidates")
    op.drop_index("ix_event_candidates_relevance_score", table_name="event_candidates")

    for column in (
        "is_enough_lead_time",
        "lead_time_days",
        "page_fetch_error",
        "page_text",
        "enriched_at",
        "enrichment_status",
        "score_breakdown",
        "relevance_score",
        "trend_score",
        "onliner_fit_score",
        "organizer_benefits",
        "partner_formats",
        "partner_participation_possible",
        "parent_event_key",
        "edition_label",
        "is_recurring",
        "ticket_info",
        "is_free",
        "theme_tags",
        "event_type",
        "attendance_source",
        "estimated_attendance",
        "is_minsk",
    ):
        op.drop_column("event_candidates", column)
