from fastapi.testclient import TestClient

PASSWORD = "a-long-enough-password"


def register(client: TestClient, email: str, full_name: str = "Test User") -> dict[str, str]:
    """Register a user and return the Authorization header for them."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
