"""create matches and match lineups with row-level security

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12 18:37:08.424872
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("opponent_name", sa.String(length=120), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.SmallInteger(), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("competition", sa.String(length=120), nullable=True),
        sa.Column("pitch_length_m", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("pitch_width_m", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("team_color", sa.String(length=7), nullable=True),
        sa.Column("opponent_color", sa.String(length=7), nullable=True),
        sa.Column("score_team", sa.SmallInteger(), nullable=True),
        sa.Column("score_opponent", sa.SmallInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "in_review", "published", name="matchstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("format IN (5, 7, 8, 11)", name="ck_matches_format"),
        sa.CheckConstraint("score_opponent BETWEEN 0 AND 99", name="ck_matches_score_opponent"),
        sa.CheckConstraint("score_team BETWEEN 0 AND 99", name="ck_matches_score_team"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_matches_kickoff_at"), "matches", ["kickoff_at"], unique=False)
    op.create_index(
        op.f("ix_matches_organization_id"), "matches", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_matches_team_id"), "matches", ["team_id"], unique=False)
    op.create_table(
        "match_lineups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("is_starter", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "player_id"),
    )
    op.create_index(op.f("ix_match_lineups_match_id"), "match_lineups", ["match_id"], unique=False)
    op.create_index(
        op.f("ix_match_lineups_organization_id"), "match_lineups", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_match_lineups_player_id"), "match_lineups", ["player_id"], unique=False
    )
    _enable_row_level_security()


TENANT_TABLES = ("matches", "match_lineups")
TENANT_MATCH = (
    "organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
)


def _enable_row_level_security() -> None:
    """Per-club policies (PostgreSQL only). The afa_app role and its default
    privileges on new tables were set up in revision 0002."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({TENANT_MATCH}) WITH CHECK ({TENANT_MATCH})"
        )


def _disable_row_level_security() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    _disable_row_level_security()
    op.drop_index(op.f("ix_match_lineups_player_id"), table_name="match_lineups")
    op.drop_index(op.f("ix_match_lineups_organization_id"), table_name="match_lineups")
    op.drop_index(op.f("ix_match_lineups_match_id"), table_name="match_lineups")
    op.drop_table("match_lineups")
    op.drop_index(op.f("ix_matches_team_id"), table_name="matches")
    op.drop_index(op.f("ix_matches_organization_id"), table_name="matches")
    op.drop_index(op.f("ix_matches_kickoff_at"), table_name="matches")
    op.drop_table("matches")
