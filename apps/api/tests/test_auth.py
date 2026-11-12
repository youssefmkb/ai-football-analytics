from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from app.api.v1.auth import REFRESH_COOKIE
from app.core.config import get_settings
from app.core.security import ALGORITHM, utcnow
from tests.helpers import PASSWORD, register


def test_register_returns_token_and_sets_httponly_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "Coach@Example.com", "full_name": "  Ada Coach ", "password": PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["token_type"] == "bearer"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["user"]["email"] == "coach@example.com"
    assert me["user"]["full_name"] == "Ada Coach"
    assert me["membership"] is None
    assert "password_hash" not in me["user"]


def test_register_rejects_duplicate_email_case_insensitively(client: TestClient) -> None:
    register(client, "coach@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "COACH@example.com", "full_name": "Other", "password": PASSWORD},
    )
    assert response.status_code == 409


def test_register_rejects_short_password_and_blank_name(client: TestClient) -> None:
    short = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "full_name": "A", "password": "short"},
    )
    blank = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "full_name": "   ", "password": PASSWORD},
    )
    assert short.status_code == 422
    assert blank.status_code == 422


def test_login_succeeds_with_right_password(client: TestClient) -> None:
    register(client, "coach@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "coach@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_login_gives_same_error_for_wrong_password_and_unknown_email(client: TestClient) -> None:
    register(client, "coach@example.com")
    wrong = client.post(
        "/api/v1/auth/login", json={"email": "coach@example.com", "password": "wrong-password"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_a_valid_access_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    garbage = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/v1/auth/me", headers=garbage).status_code == 401


def test_me_rejects_expired_and_wrongly_signed_tokens(client: TestClient) -> None:
    headers = register(client, "coach@example.com")
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]
    past = utcnow() - timedelta(minutes=1)
    expired = jwt.encode(
        {"sub": user_id, "exp": past, "type": "access"},
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )
    forged = jwt.encode(
        {"sub": user_id, "exp": utcnow() + timedelta(minutes=5), "type": "access"},
        "another-secret-key-that-is-long-enough",
        algorithm=ALGORITHM,
    )
    for token in (expired, forged):
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_refresh_rotates_the_token(client: TestClient) -> None:
    register(client, "coach@example.com")
    first_cookie = client.cookies.get(REFRESH_COOKIE)

    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    second_cookie = client.cookies.get(REFRESH_COOKIE)
    assert second_cookie and second_cookie != first_cookie
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_replaying_a_rotated_refresh_token_ends_every_session(client: TestClient) -> None:
    register(client, "coach@example.com")
    stolen = client.cookies.get(REFRESH_COOKIE)
    assert client.post("/api/v1/auth/refresh").status_code == 200
    current = client.cookies.get(REFRESH_COOKIE)

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, stolen)
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, current)
    after = client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    register(client, "coach@example.com")
    token = client.cookies.get(REFRESH_COOKIE)

    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token)
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
