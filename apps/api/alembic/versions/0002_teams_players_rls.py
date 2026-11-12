"""create teams, players and team memberships with row-level security

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12 18:02:39.108119
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_players_organization_id"), "players", ["organization_id"], unique=False
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_format", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("default_format IN (5, 7, 8, 11)", name="ck_teams_default_format"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name"),
    )
    op.create_index(op.f("ix_teams_organization_id"), "teams", ["organization_id"], unique=False)
    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("shirt_number", sa.SmallInteger(), nullable=True),
        sa.Column(
            "position",
            sa.Enum(
                "goalkeeper",
                "defender",
                "midfielder",
                "forward",
                name="position",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "shirt_number BETWEEN 1 AND 99", name="ck_team_memberships_shirt_number"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "player_id"),
        sa.UniqueConstraint("team_id", "shirt_number"),
    )
    op.create_index(
        op.f("ix_team_memberships_organization_id"),
        "team_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_team_memberships_player_id"), "team_memberships", ["player_id"], unique=False
    )
    op.create_index(
        op.f("ix_team_memberships_team_id"), "team_memberships", ["team_id"], unique=False
    )
    _enable_row_level_security()


TENANT_TABLES = ("teams", "players", "team_memberships")
APP_ROLE = "afa_app"
TENANT_MATCH = (
    "organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
)


def _enable_row_level_security() -> None:
    """Create the restricted role and the per-club policies (PostgreSQL only)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"REVOKE ALL ON alembic_version FROM {APP_ROLE}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )
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
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}"
    )
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    # The role is cluster-wide and may serve other databases: it is left in place.


def downgrade() -> None:
    _disable_row_level_security()
    op.drop_index(op.f("ix_team_memberships_team_id"), table_name="team_memberships")
    op.drop_index(op.f("ix_team_memberships_player_id"), table_name="team_memberships")
    op.drop_index(op.f("ix_team_memberships_organization_id"), table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_index(op.f("ix_teams_organization_id"), table_name="teams")
    op.drop_table("teams")
    op.drop_index(op.f("ix_players_organization_id"), table_name="players")
    op.drop_table("players")
