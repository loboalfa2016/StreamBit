"""BE-10 provider and source management

Revision ID: a4b10f6c2d01
Revises: 1039076a3a14
Create Date: 2026-11-23 15:05:19.550000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b10f6c2d01"
down_revision: Union[str, None] = "1039076a3a14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_providers_name"),
    )
    op.create_index("ix_providers_id", "providers", ["id"], unique=False)
    op.create_index("ix_providers_code", "providers", ["code"], unique=True)

    op.add_column("sources", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.add_column(
        "sources",
        sa.Column("resource_identifier", sa.String(length=500), nullable=True),
    )
    op.add_column("sources", sa.Column("territories", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("languages", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("subtitles", sa.JSON(), nullable=True))
    op.add_column(
        "sources",
        sa.Column("authorization_reference", sa.String(length=255), nullable=True),
    )
    op.add_column("sources", sa.Column("authorization_terms", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column(
        "sources",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        INSERT INTO providers (name, code, is_active, created_at)
        SELECT provider_name,
               'legacy-' || CAST(row_number() OVER (ORDER BY provider_name) AS text),
               TRUE,
               CURRENT_TIMESTAMP
        FROM (SELECT DISTINCT provider_name FROM sources) AS legacy_providers
        """
    )
    op.execute(
        """
        UPDATE sources
        SET provider_id = providers.id
        FROM providers
        WHERE providers.name = sources.provider_name
        """
    )

    op.execute(
        """
        UPDATE sources
        SET resource_identifier = resource_url,
            territories = '[]'::json,
            languages = COALESCE(
                (SELECT json_agg(l.code)::json FROM languages AS l
                 WHERE l.id = sources.audio_language_id),
                '[]'::json
            ),
            subtitles = COALESCE(
                (SELECT json_agg(l.code)::json FROM languages AS l
                 WHERE l.id = sources.subtitle_language_id),
                '[]'::json
            ),
            authorization_reference = CASE
                WHEN authorization_ref IS NOT NULL
                     AND length(trim(authorization_ref)) >= 3
                THEN left(trim(authorization_ref), 255)
                ELSE 'legacy-unverified-' || id::text
            END,
            updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
        """
    )
    op.execute(
        """
        UPDATE sources
        SET is_verified = FALSE
        WHERE authorization_ref IS NULL OR length(trim(authorization_ref)) < 3
        """
    )

    op.alter_column("sources", "provider_id", nullable=False)
    op.alter_column("sources", "resource_identifier", nullable=False)
    op.alter_column("sources", "territories", nullable=False)
    op.alter_column("sources", "languages", nullable=False)
    op.alter_column("sources", "subtitles", nullable=False)
    op.alter_column("sources", "authorization_reference", nullable=False)
    op.alter_column("sources", "updated_at", nullable=False)

    op.create_foreign_key(
        "fk_sources_provider_id_providers",
        "sources",
        "providers",
        ["provider_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_sources_created_by_user_id_users",
        "sources",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sources_provider_id", "sources", ["provider_id"], unique=False)
    op.create_index(
        "ix_sources_created_by_user_id",
        "sources",
        ["created_by_user_id"],
        unique=False,
    )

    for column in (
        "provider_name",
        "resource_url",
        "audio_language_id",
        "subtitle_language_id",
        "authorization_ref",
    ):
        op.drop_column("sources", column)


def downgrade() -> None:
    op.add_column("sources", sa.Column("provider_name", sa.String(length=100), nullable=True))
    op.add_column("sources", sa.Column("resource_url", sa.String(length=500), nullable=True))
    op.add_column("sources", sa.Column("audio_language_id", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("subtitle_language_id", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("authorization_ref", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_sources_audio_language_id_languages",
        "sources",
        "languages",
        ["audio_language_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_sources_subtitle_language_id_languages",
        "sources",
        "languages",
        ["subtitle_language_id"],
        ["id"],
    )
    op.execute(
        """
        UPDATE sources
        SET provider_name = left(
                (SELECT name FROM providers WHERE providers.id = sources.provider_id),
                100
            ),
            resource_url = resource_identifier,
            authorization_ref = authorization_reference,
            audio_language_id = (
                SELECT id FROM languages
                WHERE languages.code = sources.languages->>0
                LIMIT 1
            ),
            subtitle_language_id = (
                SELECT id FROM languages
                WHERE languages.code = sources.subtitles->>0
                LIMIT 1
            )
        """
    )
    op.alter_column("sources", "provider_name", nullable=False)
    op.alter_column("sources", "resource_url", nullable=False)

    op.drop_index("ix_sources_created_by_user_id", table_name="sources")
    op.drop_index("ix_sources_provider_id", table_name="sources")
    op.drop_constraint("fk_sources_created_by_user_id_users", "sources", type_="foreignkey")
    op.drop_constraint("fk_sources_provider_id_providers", "sources", type_="foreignkey")
    for column in (
        "updated_at",
        "created_by_user_id",
        "authorization_terms",
        "authorization_reference",
        "subtitles",
        "languages",
        "territories",
        "resource_identifier",
        "provider_id",
    ):
        op.drop_column("sources", column)

    op.drop_index("ix_providers_code", table_name="providers")
    op.drop_index("ix_providers_id", table_name="providers")
    op.drop_table("providers")
