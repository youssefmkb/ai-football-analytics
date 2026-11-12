import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Membership, Role, User

PASSWORD = "a-long-enough-password"
Headers = dict[str, str]


def register(client: TestClient, email: str, full_name: str = "Test User") -> Headers:
    """Register a user and return the Authorization header for them."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_club(client: TestClient, email: str, name: str) -> tuple[Headers, str]:
    """Register a user who creates a club. Return their headers and the club id."""
    headers = register(client, email)
    response = client.post("/api/v1/organizations", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return headers, response.json()["id"]


def create_team(client: TestClient, headers: Headers, name: str = "Seniors") -> str:
    response = client.post(
        "/api/v1/teams", json={"name": name, "default_format": 7}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_member(
    client: TestClient,
    session_factory: sessionmaker[Session],
    email: str,
    organization_id: str,
    role: Role,
) -> Headers:
    """Register a user and attach them to an existing club with the given role.

    Invitations do not exist yet, so the membership is written directly.
    """
    headers = register(client, email)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        db.add(Membership(user_id=user.id, organization_id=uuid.UUID(organization_id), role=role))
        db.commit()
    return headers
