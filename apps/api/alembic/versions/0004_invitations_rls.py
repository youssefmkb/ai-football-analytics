"""create invitations with row-level security

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 19:09:42.705279
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "role",
            sa.Enum("club_admin", "coach", "player", name="role", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["accepted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitations_organization_id"), "invitations", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_invitations_token_hash"), "invitations", ["token_hash"], unique=True)
    _enable_row_level_security()


TENANT_MATCH = (
    "organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
)


def _enable_row_level_security() -> None:
    """Admins list and revoke invitations through the club-scoped session.

    Previewing and accepting a link happen before the user belongs to the club,
    on the unscoped session, and rely on the secret token instead.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON invitations "
        f"USING ({TENANT_MATCH}) WITH CHECK ({TENANT_MATCH})"
    )


def _disable_row_level_security() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invitations")
    op.execute("ALTER TABLE invitations DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    _disable_row_level_security()
    op.drop_index(op.f("ix_invitations_token_hash"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_organization_id"), table_name="invitations")
    op.drop_table("invitations")
