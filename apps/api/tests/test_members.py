import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import utcnow
from app.models import Invitation, Role
from tests.helpers import Headers, add_member, create_club, create_team, register


def invite(client: TestClient, admin: Headers, role: str = "coach", label: str | None = None):
    response = client.post(
        "/api/v1/organizations/current/invitations",
        json={"role": role, "label": label},
        headers=admin,
    )
    assert response.status_code == 201, response.text
    return response.json()


def accept(client: TestClient, token: str, headers: Headers):
    return client.post(f"/api/v1/invitations/{token}/accept", headers=headers)


# --- Invitations -----------------------------------------------------------


def test_invitation_flow_from_link_to_membership(client: TestClient) -> None:
    admin, club_id = create_club(client, "admin@example.com", "Underdogs")
    created = invite(client, admin, "coach", "  Karim, adjoint ")
    assert created["role"] == "coach"
    assert created["label"] == "Karim, adjoint"
    assert len(created["token"]) >= 40

    # Anyone holding the link can see what it is for, without an account.
    preview = client.get(f"/api/v1/invitations/{created['token']}")
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Underdogs"
    assert preview.json()["role"] == "coach"

    newcomer = register(client, "karim@example.com")
    joined = accept(client, created["token"], newcomer)
    assert joined.status_code == 200
    assert joined.json() == {
        "organization_id": club_id,
        "organization_name": "Underdogs",
        "role": "coach",
    }
    me = client.get("/api/v1/auth/me", headers=newcomer).json()
    assert me["membership"]["organization_id"] == club_id
    assert me["membership"]["role"] == "coach"
    # As a coach, the newcomer now works on the club's data.
    create_team(client, newcomer)


def test_the_token_is_only_returned_at_creation(client: TestClient) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    created = invite(client, admin)
    listed = client.get("/api/v1/organizations/current/invitations", headers=admin).json()
    assert [i["id"] for i in listed] == [created["id"]]
    assert "token" not in listed[0]


def test_a_link_works_only_once(client: TestClient) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    token = invite(client, admin, "player")["token"]
    assert accept(client, token, register(client, "first@example.com")).status_code == 200

    second = register(client, "second@example.com")
    assert accept(client, token, second).status_code == 404
    assert client.get(f"/api/v1/invitations/{token}").status_code == 404
    assert client.get("/api/v1/auth/me", headers=second).json()["membership"] is None
    assert client.get("/api/v1/organizations/current/invitations", headers=admin).json() == []


def test_revoked_and_expired_links_are_refused(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    revoked = invite(client, admin)
    expired = invite(client, admin)
    url = "/api/v1/organizations/current/invitations"
    assert client.delete(f"{url}/{revoked['id']}", headers=admin).status_code == 204
    assert client.delete(f"{url}/{revoked['id']}", headers=admin).status_code == 404
    with session_factory() as db:
        db.execute(
            update(Invitation)
            .where(Invitation.id == uuid.UUID(expired["id"]))
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
        db.commit()

    newcomer = register(client, "late@example.com")
    for token in (revoked["token"], expired["token"], "not-a-real-token"):
        assert client.get(f"/api/v1/invitations/{token}").status_code == 404
        assert accept(client, token, newcomer).status_code == 404
    assert client.get(url, headers=admin).json() == []


def test_someone_already_in_a_club_cannot_join_another(client: TestClient) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    other, _ = create_club(client, "other@example.com", "Club B")
    token = invite(client, admin)["token"]
    assert accept(client, token, other).status_code == 409
    # The link was not consumed by the refused attempt.
    assert accept(client, token, register(client, "free@example.com")).status_code == 200


def test_accepting_requires_an_account(client: TestClient) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    token = invite(client, admin)["token"]
    assert client.post(f"/api/v1/invitations/{token}/accept").status_code == 401


@pytest.mark.parametrize("role", ["club_admin", "owner", ""])
def test_invitations_are_for_coaches_and_players_only(client: TestClient, role: str) -> None:
    admin, _ = create_club(client, "admin@example.com", "Club A")
    response = client.post(
        "/api/v1/organizations/current/invitations", json={"role": role}, headers=admin
    )
    assert response.status_code == 422


# --- Members ---------------------------------------------------------------


def test_list_members(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    admin, club_id = create_club(client, "admin@example.com", "Club A")
    add_member(client, session_factory, "coach@example.com", club_id, Role.COACH)
    members = client.get("/api/v1/organizations/current/members", headers=admin).json()
    assert {(m["email"], m["role"], m["is_self"]) for m in members} == {
        ("admin@example.com", "club_admin", True),
        ("coach@example.com", "coach", False),
    }
    assert "password_hash" not in members[0]


def test_change_role_and_remove_member(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin, club_id = create_club(client, "admin@example.com", "Club A")
    coach = add_member(client, session_factory, "coach@example.com", club_id, Role.COACH)
    coach_id = client.get("/api/v1/auth/me", headers=coach).json()["user"]["id"]
    member_url = f"/api/v1/organizations/current/members/{coach_id}"

    demoted = client.patch(member_url, json={"role": "player"}, headers=admin)
    assert demoted.json()["role"] == "player"
    # The change applies to the next request of that user.
    assert (
        client.post(
            "/api/v1/teams", json={"name": "X", "default_format": 7}, headers=coach
        ).status_code
        == 403
    )

    assert client.delete(member_url, headers=admin).status_code == 204
    assert client.get("/api/v1/auth/me", headers=coach).json()["membership"] is None
    assert client.get("/api/v1/teams", headers=coach).status_code == 404
    assert client.delete(member_url, headers=admin).status_code == 404


def test_a_club_keeps_at_least_one_admin(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin, club_id = create_club(client, "admin@example.com", "Club A")
    admin_id = client.get("/api/v1/auth/me", headers=admin).json()["user"]["id"]
    url = f"/api/v1/organizations/current/members/{admin_id}"
    assert client.patch(url, json={"role": "coach"}, headers=admin).status_code == 409
    assert client.delete(url, headers=admin).status_code == 409

    second = add_member(client, session_factory, "second@example.com", club_id, Role.COACH)
    second_id = client.get("/api/v1/auth/me", headers=second).json()["user"]["id"]
    client.patch(
        f"/api/v1/organizations/current/members/{second_id}",
        json={"role": "club_admin"},
        headers=admin,
    )
    # With two admins, the first may step down.
    assert client.patch(url, json={"role": "coach"}, headers=admin).status_code == 200
    assert client.get("/api/v1/organizations/current/members", headers=admin).status_code == 403


@pytest.mark.parametrize("role", [Role.COACH, Role.PLAYER])
def test_only_admins_manage_members_and_invitations(
    client: TestClient, session_factory: sessionmaker[Session], role: Role
) -> None:
    admin, club_id = create_club(client, "admin@example.com", "Club A")
    invitation = invite(client, admin)
    admin_id = client.get("/api/v1/auth/me", headers=admin).json()["user"]["id"]
    member = add_member(client, session_factory, "member@example.com", club_id, role)
    base = "/api/v1/organizations/current"
    attempts = [
        client.get(f"{base}/members", headers=member),
        client.patch(f"{base}/members/{admin_id}", json={"role": "player"}, headers=member),
        client.delete(f"{base}/members/{admin_id}", headers=member),
        client.post(f"{base}/invitations", json={"role": "coach"}, headers=member),
        client.get(f"{base}/invitations", headers=member),
        client.delete(f"{base}/invitations/{invitation['id']}", headers=member),
    ]
    assert [response.status_code for response in attempts] == [403] * 6


def test_another_club_cannot_see_or_touch_members_and_invitations(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    alice, alice_club = create_club(client, "alice@example.com", "Club A")
    bob, _ = create_club(client, "bob@example.com", "Club B")
    coach = add_member(client, session_factory, "coach@example.com", alice_club, Role.COACH)
    coach_id = client.get("/api/v1/auth/me", headers=coach).json()["user"]["id"]
    invitation = invite(client, alice)
    base = "/api/v1/organizations/current"

    assert [m["email"] for m in client.get(f"{base}/members", headers=bob).json()] == [
        "bob@example.com"
    ]
    assert client.get(f"{base}/invitations", headers=bob).json() == []
    attempts = [
        client.patch(f"{base}/members/{coach_id}", json={"role": "player"}, headers=bob),
        client.delete(f"{base}/members/{coach_id}", headers=bob),
        client.delete(f"{base}/invitations/{invitation['id']}", headers=bob),
    ]
    assert [response.status_code for response in attempts] == [404] * 3
    assert client.get("/api/v1/auth/me", headers=coach).json()["membership"]["role"] == "coach"
    assert len(client.get(f"{base}/invitations", headers=alice).json()) == 1
