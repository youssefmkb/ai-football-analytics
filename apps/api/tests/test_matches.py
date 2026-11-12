import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Role
from tests.helpers import Headers, add_member, create_club, create_team

KICKOFF = "2026-11-21T15:00:00+01:00"


def add_player(client: TestClient, headers: Headers, team_id: str, number: int) -> str:
    response = client.post(
        f"/api/v1/teams/{team_id}/players",
        json={"first_name": "Player", "last_name": f"N{number}", "shirt_number": number},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_match(client: TestClient, headers: Headers, team_id: str, **extra: object) -> dict:
    payload = {"team_id": team_id, "opponent_name": "FC Rivals", "kickoff_at": KICKOFF, **extra}
    response = client.post("/api/v1/matches", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_match_takes_the_team_format_by_default(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)

    match = create_match(client, headers, team_id, location="  Stade Municipal ", competition=" ")
    assert match["team_name"] == "Seniors"
    assert match["opponent_name"] == "FC Rivals"
    assert match["format"] == 7
    assert match["location"] == "Stade Municipal"
    assert match["competition"] is None
    assert match["status"] == "draft"
    assert match["score_team"] is None
    assert match["lineup"] == []
    # The instant is kept, whatever the offset it was sent with.
    assert match["kickoff_at"] in ("2026-11-21T14:00:00Z", "2026-11-21T15:00:00+01:00")

    assert create_match(client, headers, team_id, format=11)["format"] == 11


@pytest.mark.parametrize(
    "extra",
    [
        {"opponent_name": "  "},
        {"kickoff_at": "2026-11-21T15:00:00"},  # no time zone
        {"kickoff_at": "tomorrow"},
        {"format": 6},
        {"team_color": "red"},
        {"pitch_length_m": 500},
        {"score_team": 2},  # one score without the other
        {"score_team": -1, "score_opponent": 0},
    ],
)
def test_invalid_matches_are_rejected(client: TestClient, extra: dict[str, object]) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    payload = {"team_id": team_id, "opponent_name": "FC Rivals", "kickoff_at": KICKOFF, **extra}
    assert client.post("/api/v1/matches", json=payload, headers=headers).status_code == 422


def test_list_matches_newest_first_and_filter_by_team(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    first_team = create_team(client, headers, "First")
    second_team = create_team(client, headers, "Second")
    create_match(
        client, headers, first_team, opponent_name="Old", kickoff_at="2026-01-10T10:00:00Z"
    )
    create_match(
        client, headers, first_team, opponent_name="New", kickoff_at="2026-03-10T10:00:00Z"
    )
    create_match(client, headers, second_team, opponent_name="Other")

    everything = client.get("/api/v1/matches", headers=headers).json()
    assert [m["opponent_name"] for m in everything] == ["Other", "New", "Old"]
    filtered = client.get(f"/api/v1/matches?team_id={first_team}", headers=headers).json()
    assert [m["opponent_name"] for m in filtered] == ["New", "Old"]
    assert "lineup" not in everything[0]


def test_update_match_and_score(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    match = create_match(client, headers, create_team(client, headers), location="Somewhere")
    url = f"/api/v1/matches/{match['id']}"

    updated = client.patch(
        url,
        json={"score_team": 3, "score_opponent": 1, "location": None, "team_color": "#00aa55"},
        headers=headers,
    ).json()
    assert (updated["score_team"], updated["score_opponent"]) == (3, 1)
    assert updated["location"] is None
    assert updated["team_color"] == "#00aa55"
    assert updated["opponent_name"] == "FC Rivals"

    half = client.patch(url, json={"score_team": None}, headers=headers)
    assert half.status_code == 422
    cleared = client.patch(url, json={"score_team": None, "score_opponent": None}, headers=headers)
    assert cleared.json()["score_team"] is None
    # The rejected request changed nothing.
    assert client.get(url, headers=headers).json()["team_color"] == "#00aa55"


def test_lineup_is_replaced_as_a_whole_and_sorted(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    players = {n: add_player(client, headers, team_id, n) for n in (10, 1, 7)}
    match = create_match(client, headers, team_id)
    url = f"/api/v1/matches/{match['id']}/lineup"

    first = client.put(
        url,
        json={
            "players": [
                {"player_id": players[10], "is_starter": True},
                {"player_id": players[7], "is_starter": False},
                {"player_id": players[1], "is_starter": True},
            ]
        },
        headers=headers,
    )
    assert first.status_code == 200
    assert [(e["shirt_number"], e["is_starter"]) for e in first.json()["lineup"]] == [
        (1, True),
        (10, True),
        (7, False),
    ]

    second = client.put(
        url, json={"players": [{"player_id": players[7], "is_starter": True}]}, headers=headers
    )
    assert [e["shirt_number"] for e in second.json()["lineup"]] == [7]
    stored = client.get(f"/api/v1/matches/{match['id']}", headers=headers).json()
    assert [e["player_id"] for e in stored["lineup"]] == [players[7]]

    empty = client.put(url, json={"players": []}, headers=headers)
    assert empty.json()["lineup"] == []


def test_lineup_rules(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    other_team = create_team(client, headers, "Other")
    outsider = add_player(client, headers, other_team, 99)
    squad = [add_player(client, headers, team_id, n) for n in range(1, 7)]
    match = create_match(client, headers, team_id, format=5)
    url = f"/api/v1/matches/{match['id']}/lineup"

    def put(entries: list[tuple[str, bool]]) -> int:
        body = {"players": [{"player_id": p, "is_starter": s} for p, s in entries]}
        return client.put(url, json=body, headers=headers).status_code

    assert put([(squad[0], True), (squad[0], False)]) == 422  # twice the same player
    assert put([(outsider, True)]) == 422  # not in this team
    assert put([(str(uuid.uuid4()), True)]) == 422  # unknown player
    assert put([(p, True) for p in squad]) == 422  # six starters at five-a-side
    assert put([(p, True) for p in squad[:5]] + [(squad[5], False)]) == 200


def test_history_is_protected(client: TestClient) -> None:
    headers, _ = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, headers)
    in_lineup = add_player(client, headers, team_id, 1)
    not_in_lineup = add_player(client, headers, team_id, 2)
    match = create_match(client, headers, team_id)
    client.put(
        f"/api/v1/matches/{match['id']}/lineup",
        json={"players": [{"player_id": in_lineup, "is_starter": True}]},
        headers=headers,
    )
    players = f"/api/v1/teams/{team_id}/players"

    assert client.delete(f"{players}/{in_lineup}", headers=headers).status_code == 409
    assert client.delete(f"{players}/{not_in_lineup}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/teams/{team_id}", headers=headers).status_code == 409
    assert len(client.get(players, headers=headers).json()) == 1

    # Once the match is gone, both become possible again.
    assert client.delete(f"/api/v1/matches/{match['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/matches/{match['id']}", headers=headers).status_code == 404
    assert client.delete(f"{players}/{in_lineup}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/teams/{team_id}", headers=headers).status_code == 204


def test_another_club_cannot_see_or_touch_a_match(client: TestClient) -> None:
    alice, _ = create_club(client, "alice@example.com", "Club A")
    bob, _ = create_club(client, "bob@example.com", "Club B")
    alice_team = create_team(client, alice)
    alice_player = add_player(client, alice, alice_team, 1)
    bob_team = create_team(client, bob)
    bob_player = add_player(client, bob, bob_team, 1)
    match = create_match(client, alice, alice_team)
    url = f"/api/v1/matches/{match['id']}"
    lineup = {"players": [{"player_id": bob_player, "is_starter": True}]}

    assert client.get("/api/v1/matches", headers=bob).json() == []
    assert client.get(f"/api/v1/matches?team_id={alice_team}", headers=bob).json() == []
    attempts = [
        client.get(url, headers=bob),
        client.patch(url, json={"opponent_name": "Stolen"}, headers=bob),
        client.delete(url, headers=bob),
        client.put(f"{url}/lineup", json=lineup, headers=bob),
        # Bob cannot attach a match to Alice's team.
        client.post(
            "/api/v1/matches",
            json={"team_id": alice_team, "opponent_name": "X", "kickoff_at": KICKOFF},
            headers=bob,
        ),
    ]
    assert [response.status_code for response in attempts] == [404] * 5

    # Alice cannot pull Bob's player into her lineup.
    assert client.put(f"{url}/lineup", json=lineup, headers=alice).status_code == 422
    mine = {"players": [{"player_id": alice_player, "is_starter": True}]}
    assert client.put(f"{url}/lineup", json=mine, headers=alice).status_code == 200
    assert client.get(url, headers=alice).json()["opponent_name"] == "FC Rivals"


def test_players_can_read_matches_but_not_write(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    coach, club_id = create_club(client, "coach@example.com", "Club A")
    team_id = create_team(client, coach)
    match = create_match(client, coach, team_id)
    member = add_member(client, session_factory, "player@example.com", club_id, Role.PLAYER)
    url = f"/api/v1/matches/{match['id']}"

    assert client.get("/api/v1/matches", headers=member).status_code == 200
    assert client.get(url, headers=member).status_code == 200
    writes = [
        client.post(
            "/api/v1/matches",
            json={"team_id": team_id, "opponent_name": "X", "kickoff_at": KICKOFF},
            headers=member,
        ),
        client.patch(url, json={"opponent_name": "X"}, headers=member),
        client.put(f"{url}/lineup", json={"players": []}, headers=member),
        client.delete(url, headers=member),
    ]
    assert [response.status_code for response in writes] == [403] * 4
    assert client.get("/api/v1/matches").status_code == 401
