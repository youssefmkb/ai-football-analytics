"""Tenant isolation enforced by PostgreSQL row-level security.

Club-scoped tables carry an ``organization_id`` column and a policy that only
lets a row through when it matches ``app.current_organization_id``. The API
connects as the database owner, which bypasses row-level security, so every
club-scoped request switches to the restricted ``afa_app`` role for the length
of each transaction. A query that forgets its ``WHERE organization_id = ...``
then returns nothing from other clubs instead of leaking them.

This is a second line of defence. Endpoints still filter by organization.
"""

import uuid

from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session

APP_ROLE = "afa_app"
_INFO_KEY = "organization_id"


def _apply(connection: Connection, organization_id: uuid.UUID) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    connection.execute(
        text("SELECT set_config('app.current_organization_id', :org, true)"),
        {"org": str(organization_id)},
    )


def bind_tenant(db: Session, organization_id: uuid.UUID) -> None:
    """Scope this session, now and for its later transactions, to one club."""
    db.info[_INFO_KEY] = organization_id
    _apply(db.connection(), organization_id)


@event.listens_for(Session, "after_begin")
def _reapply_on_new_transaction(session: Session, _transaction, connection: Connection) -> None:
    # SET LOCAL ends with the transaction, so a commit drops the scoping.
    organization_id = session.info.get(_INFO_KEY)
    if organization_id is not None:
        _apply(connection, organization_id)
