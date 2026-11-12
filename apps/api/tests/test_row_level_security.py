"""The database itself must keep clubs apart, even when a query forgets to filter."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.db.tenant import APP_ROLE, bind_tenant
from tests.conftest import requires_postgres
from tests.helpers import create_club, create_team

pytestmark = requires_postgres

PLAYER = {"first_name": "Sam", "last_name": "Keeper"}
TABLES = ("teams", "players", "team_memberships")


@pytest.fixture
def two_clubs(client: TestClient) -> tuple[uuid.UUID, uuid.UUID]:
    """Two clubs, each with one team and one player."""
    ids = []
    for email, name in (("alice@example.com", "Club A"), ("bob@example.com", "Club B")):
        headers, club_id = create_club(client, email, name)
        team_id = create_team(client, headers)
        client.post(f"/api/v1/teams/{team_id}/players", json=PLAYER, headers=headers)
        ids.append(uuid.UUID(club_id))
    return ids[0], ids[1]


def _organizations_visible(db: Session, table: str) -> set[uuid.UUID]:
    # Deliberately unfiltered: this is the query a careless endpoint would run.
    return set(db.scalars(text(f"SELECT organization_id FROM {table}")))


def test_unfiltered_queries_only_return_the_bound_club(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    club_a, club_b = two_clubs
    with session_factory() as db:
        # Without scoping, the owner role sees both clubs: the data really is there.
        assert _organizations_visible(db, "players") == {club_a, club_b}
    for club in (club_a, club_b):
        with session_factory() as db:
            bind_tenant(db, club)
            assert db.scalar(text("SELECT current_user")) == APP_ROLE
            for table in TABLES:
                assert _organizations_visible(db, table) == {club}


def test_scoping_survives_a_commit(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    club_a, _ = two_clubs
    with session_factory() as db:
        bind_tenant(db, club_a)
        db.commit()
        assert _organizations_visible(db, "players") == {club_a}
        db.rollback()
        assert _organizations_visible(db, "players") == {club_a}


def test_scoping_does_not_leak_to_the_next_session_on_the_same_connection(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    club_a, club_b = two_clubs
    with session_factory() as db:
        bind_tenant(db, club_a)
        db.execute(text("SELECT 1"))
    with session_factory() as db:
        bind_tenant(db, club_b)
        assert _organizations_visible(db, "players") == {club_b}
    with session_factory() as db:
        assert db.scalar(text("SELECT current_user")) != APP_ROLE


def test_writing_into_another_club_is_refused(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    club_a, club_b = two_clubs
    insert = text(
        "INSERT INTO teams (id, organization_id, name, default_format) "
        "VALUES (:id, :org, 'Intruder', 7)"
    )
    with session_factory() as db:
        bind_tenant(db, club_a)
        with pytest.raises(DBAPIError, match="row-level security"):
            db.execute(insert, {"id": uuid.uuid4(), "org": club_b})
        db.rollback()
        db.execute(insert, {"id": uuid.uuid4(), "org": club_a})
        db.rollback()


def test_updates_and_deletes_cannot_reach_another_club(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    club_a, club_b = two_clubs
    with session_factory() as db:
        bind_tenant(db, club_a)
        updated = db.execute(text("UPDATE players SET last_name = 'Hacked'"))
        deleted = db.execute(text("DELETE FROM team_memberships"))
        assert (updated.rowcount, deleted.rowcount) == (1, 1)
        db.commit()
    with session_factory() as db:
        names = db.execute(
            text("SELECT organization_id, last_name FROM players ORDER BY last_name")
        ).all()
        assert sorted(names, key=lambda row: row[1]) == [(club_a, "Hacked"), (club_b, "Keeper")]
        remaining = _organizations_visible(db, "team_memberships")
        assert remaining == {club_b}


def test_the_restricted_role_sees_nothing_without_a_club(
    session_factory: sessionmaker[Session], two_clubs: tuple[uuid.UUID, uuid.UUID]
) -> None:
    with session_factory() as db:
        db.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
        for table in TABLES:
            assert _organizations_visible(db, table) == set()
