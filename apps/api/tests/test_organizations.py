from fastapi.testclient import TestClient

from tests.helpers import register


def test_creating_a_club_makes_the_creator_club_admin(client: TestClient) -> None:
    headers = register(client, "coach@example.com")
    response = client.post("/api/v1/organizations", json={"name": "  Underdogs  "}, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Underdogs"
    assert response.json()["role"] == "club_admin"

    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["membership"]["organization_name"] == "Underdogs"
    assert me["membership"]["role"] == "club_admin"


def test_a_user_cannot_create_a_second_club(client: TestClient) -> None:
    headers = register(client, "coach@example.com")
    client.post("/api/v1/organizations", json={"name": "First"}, headers=headers)
    second = client.post("/api/v1/organizations", json={"name": "Second"}, headers=headers)
    assert second.status_code == 409


def test_club_endpoints_require_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/organizations", json={"name": "X"}).status_code == 401
    assert client.get("/api/v1/organizations/current").status_code == 401


def test_current_club_is_404_before_any_club_exists(client: TestClient) -> None:
    headers = register(client, "coach@example.com")
    assert client.get("/api/v1/organizations/current", headers=headers).status_code == 404


def test_blank_club_name_is_rejected(client: TestClient) -> None:
    headers = register(client, "coach@example.com")
    response = client.post("/api/v1/organizations", json={"name": "   "}, headers=headers)
    assert response.status_code == 422


def test_each_user_only_sees_their_own_club(client: TestClient) -> None:
    alice = register(client, "alice@example.com")
    client.cookies.clear()
    bob = register(client, "bob@example.com")
    client.cookies.clear()
    club_a = client.post("/api/v1/organizations", json={"name": "Club A"}, headers=alice).json()
    club_b = client.post("/api/v1/organizations", json={"name": "Club B"}, headers=bob).json()

    seen_by_alice = client.get("/api/v1/organizations/current", headers=alice).json()
    seen_by_bob = client.get("/api/v1/organizations/current", headers=bob).json()
    assert seen_by_alice["id"] == club_a["id"] != club_b["id"]
    assert seen_by_bob["id"] == club_b["id"]
