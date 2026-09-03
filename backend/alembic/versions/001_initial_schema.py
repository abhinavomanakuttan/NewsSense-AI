"""initial_schema

Revision ID: 001
Create Date: 2026-07-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable uuid-ossp extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ─── Users ─────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'user'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("preferences", postgresql.JSON, nullable=True),
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
    )

    # ─── Sources ───────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False, unique=True),
        sa.Column("feed_url", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default=sa.text("'en'")),
        sa.Column("country", sa.String(5), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reputation_score", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column(
            "fetch_interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")
        ),
        sa.Column("last_fetched_at", sa.String(50), nullable=True),
        sa.Column("config", sa.Text(), nullable=True),
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
    )

    # ─── Categories ────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("parent_id", sa.String(50), nullable=True),
        sa.Column("display_order", sa.String(10), nullable=False, server_default=sa.text("'0'")),
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
    )

    # ─── Tags ──────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
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
    )

    # ─── Events ────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True, nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.String(50), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("article_count", sa.String(10), nullable=False, server_default=sa.text("'0'")),
        sa.Column("importance_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("timeline", sa.Text(), nullable=True),
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
    )

    # ─── Articles ──────────────────────────────────────────
    op.create_table(
        "articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True, nullable=False, index=True),
        sa.Column("url", sa.String(1000), unique=True, nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("published_at", sa.String(50), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default=sa.text("'en'")),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("entities", sa.Text(), nullable=True),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("credibility_score", sa.Float(), nullable=True),
        sa.Column("credibility_factors", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(1000), nullable=True),
        sa.Column("view_count", sa.String(10), nullable=False, server_default=sa.text("'0'")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    )

    # ─── Article-Tag Association ───────────────────────────
    op.create_table(
        "article_tags",
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ─── Bookmarks ─────────────────────────────────────────
    op.create_table(
        "bookmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
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
    )

    # ─── Reading History ──────────────────────────────────
    op.create_table(
        "reading_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "read_duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("scroll_depth", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
    )

    # ─── Notifications ────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.String(2000), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    )

    # ─── Search History ───────────────────────────────────
    op.create_table(
        "search_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("filters", sa.String(2000), nullable=True),
        sa.Column("result_count", sa.String(10), nullable=False, server_default=sa.text("'0'")),
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
    )

    # ─── User Preferences ────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        ),
        sa.Column("preferred_categories", postgresql.JSON, nullable=True),
        sa.Column("preferred_sources", postgresql.JSON, nullable=True),
        sa.Column(
            "preferred_languages",
            postgresql.JSON,
            nullable=True,
            server_default=sa.text("'[\"en\"]'"),
        ),
        sa.Column("preferred_regions", postgresql.JSON, nullable=True),
        sa.Column(
            "notification_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("dark_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "email_digest_frequency",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'daily'"),
        ),
        sa.Column("custom_settings", postgresql.JSON, nullable=True),
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
    )

    # ─── Jobs ─────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=False, unique=True),
        sa.Column("salary_range", sa.String(100), nullable=True),
        sa.Column("job_type", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
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
    )

    # ─── Sports ───────────────────────────────────────────
    op.create_table(
        "sports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("sport_type", sa.String(50), nullable=False, index=True),
        sa.Column("league", sa.String(100), nullable=True),
        sa.Column("team1", sa.String(255), nullable=True),
        sa.Column("team2", sa.String(255), nullable=True),
        sa.Column("score", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'upcoming'")),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
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
    )

    # ─── Analytics Events ─────────────────────────────────
    op.create_table(
        "analytics_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            index=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("article_id", sa.String(100), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSON, nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
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
    )

    # ─── Indexes ──────────────────────────────────────────
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_articles_category_id", "articles", ["category_id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read"])
    op.create_index(
        "ix_reading_history_user_article", "reading_history", ["user_id", "article_id"], unique=True
    )
    op.create_index(
        "ix_bookmarks_user_article", "bookmarks", ["user_id", "article_id"], unique=True
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.drop_table("sports")
    op.drop_table("jobs")
    op.drop_table("user_preferences")
    op.drop_table("search_history")
    op.drop_table("notifications")
    op.drop_table("reading_history")
    op.drop_table("bookmarks")
    op.drop_table("article_tags")
    op.drop_table("articles")
    op.drop_table("events")
    op.drop_table("tags")
    op.drop_table("categories")
    op.drop_table("sources")
    op.drop_table("users")
