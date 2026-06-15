"""Initial schema with seed search queries.

Revision ID: 001
Revises:
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_QUERIES = [
    ("конференция Минск 2026", "конференция"),
    ("бизнес форум Беларусь 2026", "бизнес"),
    ("IT мероприятие Минск 2026", "IT"),
    ("выставка Беларусь 2026", "выставка"),
    ("образовательный форум Минск", "образование"),
    ("фестиваль Минск партнеры", "фестиваль"),
    ("мероприятие инфопартнер Беларусь", "инфопартнерство"),
]


def upgrade() -> None:
    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_text"),
    )

    op.create_table(
        "search_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_results", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_runs_status", "search_runs", ["status"])

    op.create_table(
        "event_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("relevance_status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("source_query", sa.String(length=512), nullable=False),
        sa.Column("search_run_id", sa.Uuid(), nullable=False),
        sa.Column("duplicate_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["search_run_id"], ["search_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duplicate_key"),
    )
    op.create_index("ix_event_candidates_source_domain", "event_candidates", ["source_domain"])
    op.create_index("ix_event_candidates_category", "event_candidates", ["category"])
    op.create_index("ix_event_candidates_relevance_status", "event_candidates", ["relevance_status"])
    op.create_index("ix_event_candidates_source_query", "event_candidates", ["source_query"])
    op.create_index("ix_event_candidates_search_run_id", "event_candidates", ["search_run_id"])
    op.create_index("ix_event_candidates_duplicate_key", "event_candidates", ["duplicate_key"])

    op.create_table(
        "event_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_candidate_id"], ["event_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_reviews_event_candidate_id", "event_reviews", ["event_candidate_id"])

    seed_table = sa.table(
        "search_queries",
        sa.column("query_text", sa.String),
        sa.column("category", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        seed_table,
        [
            {"query_text": text, "category": category, "is_active": True}
            for text, category in SEED_QUERIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_event_reviews_event_candidate_id", table_name="event_reviews")
    op.drop_table("event_reviews")
    op.drop_index("ix_event_candidates_duplicate_key", table_name="event_candidates")
    op.drop_index("ix_event_candidates_search_run_id", table_name="event_candidates")
    op.drop_index("ix_event_candidates_source_query", table_name="event_candidates")
    op.drop_index("ix_event_candidates_relevance_status", table_name="event_candidates")
    op.drop_index("ix_event_candidates_category", table_name="event_candidates")
    op.drop_index("ix_event_candidates_source_domain", table_name="event_candidates")
    op.drop_table("event_candidates")
    op.drop_index("ix_search_runs_status", table_name="search_runs")
    op.drop_table("search_runs")
    op.drop_table("search_queries")
