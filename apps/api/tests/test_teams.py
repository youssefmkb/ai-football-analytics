import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Role
from tests.helpers import add_member, create_club, create_team

PLAYER = {"first_name": "Sam", "last_name": "Keeper", "shirt_number": 1, "position": "goalkeeper"}


def test_create_and_list_teams(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    created = client.post(
        "/api/v1/teams", json={"name": "  Seniors ", "default_format": 7}, headers=headers
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Seniors"
    assert created.json()["default_format"] == 7
    assert created.json()["player_count"] == 0

    teams = client.get("/api/v1/teams", headers=headers).json()
    assert [team["name"] for team in teams] == ["Seniors"]


@pytest.mark.parametrize("default_format", [6, 0, 12, "seven"])
def test_team_format_must_be_5_7_8_or_11(client: TestClient, default_format: object) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    response = client.post(
        "/api/v1/teams", json={"name": "Seniors", "default_format": default_format}, headers=headers
    )
    assert response.status_code == 422


def test_team_name_is_unique_inside_a_club_but_not_across_clubs(client: TestClient) -> None:
    alice, _ = create_club(client, "alice@example.com", "Club A")
    bob, _ = create_club(client, "bob@example.com", "Club B")
    create_team(client, alice, "Seniors")
    duplicate = client.post(
        "/api/v1/teams", json={"name": "Seniors", "default_format": 7}, headers=alice
    )
    assert duplicate.status_code == 409
    create_team(client, bob, "Seniors")


def test_update_team(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    response = client.patch(
        f"/api/v1/teams/{team_id}", json={"default_format": 11}, headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": team_id,
        "name": "Seniors",
        "default_format": 11,
        "player_count": 0,
    }


def test_teams_require_a_club(client: TestClient) -> None:
    from tests.helpers import register

    headers = register(client, "noclub@example.com")
    assert client.get("/api/v1/teams", headers=headers).status_code == 404
    assert client.get("/api/v1/teams").status_code == 401


def test_add_list_update_and_remove_a_player(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    base = f"/api/v1/teams/{team_id}/players"

    added = client.post(base, json=PLAYER, headers=headers)
    assert added.status_code == 201
    player_id = added.json()["id"]
    client.post(base, json={"first_name": "No", "last_name": "Number"}, headers=headers)
    client.post(
        base, json={"first_name": "Zed", "last_name": "Nine", "shirt_number": 9}, headers=headers
    )

    squad = client.get(base, headers=headers).json()
    assert [p["shirt_number"] for p in squad] == [1, 9, None]
    assert client.get(f"/api/v1/teams/{team_id}", headers=headers).json()["player_count"] == 3

    updated = client.patch(
        f"{base}/{player_id}",
        json={"last_name": "Goalie", "shirt_number": 16, "position": None},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "id": player_id,
        "first_name": "Sam",
        "last_name": "Goalie",
        "shirt_number": 16,
        "position": None,
    }

    assert client.delete(f"{base}/{player_id}", headers=headers).status_code == 204
    assert client.delete(f"{base}/{player_id}", headers=headers).status_code == 404
    assert len(client.get(base, headers=headers).json()) == 2


def test_shirt_number_is_unique_inside_a_team(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    base = f"/api/v1/teams/{team_id}/players"
    client.post(base, json=PLAYER, headers=headers)
    other = client.post(
        base, json={"first_name": "A", "last_name": "B", "shirt_number": 2}, headers=headers
    ).json()

    assert client.post(base, json=PLAYER, headers=headers).status_code == 409
    clash = client.patch(f"{base}/{other['id']}", json={"shirt_number": 1}, headers=headers)
    assert clash.status_code == 409
    # The failed requests must not have changed anything.
    assert [p["shirt_number"] for p in client.get(base, headers=headers).json()] == [1, 2]


@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": " ", "last_name": "X"},
        {"first_name": "A", "last_name": "B", "shirt_number": 0},
        {"first_name": "A", "last_name": "B", "shirt_number": 100},
        {"first_name": "A", "last_name": "B", "position": "striker"},
    ],
)
def test_invalid_players_are_rejected(client: TestClient, payload: dict[str, object]) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    response = client.post(f"/api/v1/teams/{team_id}/players", json=payload, headers=headers)
    assert response.status_code == 422


def test_deleting_a_team_removes_its_players(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    client.post(f"/api/v1/teams/{team_id}/players", json=PLAYER, headers=headers)

    assert client.delete(f"/api/v1/teams/{team_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/teams", headers=headers).json() == []
    # The name and the shirt number are free again.
    new_team = create_team(client, headers)
    again = client.post(f"/api/v1/teams/{new_team}/players", json=PLAYER, headers=headers)
    assert again.status_code == 201


def test_another_club_cannot_see_or_touch_a_team(client: TestClient) -> None:
    alice, _ = create_club(client, "alice@example.com", "Club A")
    bob, _ = create_club(client, "bob@example.com", "Club B")
    team_id = create_team(client, alice)
    player_id = client.post(f"/api/v1/teams/{team_id}/players", json=PLAYER, headers=alice).json()[
        "id"
    ]
    team = f"/api/v1/teams/{team_id}"
    player = f"{team}/players/{player_id}"

    assert client.get("/api/v1/teams", headers=bob).json() == []
    attempts = [
        client.get(team, headers=bob),
        client.patch(team, json={"name": "Stolen"}, headers=bob),
        client.delete(team, headers=bob),
        client.get(f"{team}/players", headers=bob),
        client.post(f"{team}/players", json=PLAYER, headers=bob),
        client.patch(player, json={"last_name": "Stolen"}, headers=bob),
        client.delete(player, headers=bob),
    ]
    assert [response.status_code for response in attempts] == [404] * 7

    # Nothing changed for the owner.
    assert client.get(team, headers=alice).json()["name"] == "Seniors"
    assert client.get(f"{team}/players", headers=alice).json()[0]["last_name"] == "Keeper"


def test_a_player_of_one_team_cannot_be_reached_through_another_team(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    first = create_team(client, headers, "First")
    second = create_team(client, headers, "Second")
    player_id = client.post(f"/api/v1/teams/{first}/players", json=PLAYER, headers=headers).json()[
        "id"
    ]
    wrong = client.patch(
        f"/api/v1/teams/{second}/players/{player_id}", json={"last_name": "X"}, headers=headers
    )
    assert wrong.status_code == 404


def test_unknown_ids_answer_404(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    assert client.get(f"/api/v1/teams/{uuid.uuid4()}", headers=headers).status_code == 404
    assert client.get("/api/v1/teams/not-a-uuid", headers=headers).status_code == 422


def test_players_can_read_but_not_write(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    coach, club_id = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, coach)
    player_id = client.post(f"/api/v1/teams/{team_id}/players", json=PLAYER, headers=coach).json()[
        "id"
    ]
    member = add_member(client, session_factory, "player@example.com", club_id, Role.PLAYER)
    team = f"/api/v1/teams/{team_id}"

    assert client.get("/api/v1/teams", headers=member).status_code == 200
    assert client.get(f"{team}/players", headers=member).status_code == 200
    writes = [
        client.post("/api/v1/teams", json={"name": "X", "default_format": 7}, headers=member),
        client.patch(team, json={"name": "X"}, headers=member),
        client.delete(team, headers=member),
        client.post(f"{team}/players", json=PLAYER, headers=member),
        client.patch(f"{team}/players/{player_id}", json={"last_name": "X"}, headers=member),
        client.delete(f"{team}/players/{player_id}", headers=member),
    ]
    assert [response.status_code for response in writes] == [403] * 6


def test_coaches_can_write(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    _, club_id = create_club(client, "admin@example.com", "Club A")
    coach = add_member(client, session_factory, "coach@example.com", club_id, Role.COACH)
    create_team(client, coach)
