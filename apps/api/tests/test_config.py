import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_refuses_the_development_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", cookie_secure=True)


def test_production_refuses_insecure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="x" * 40, cookie_secure=False)


def test_production_accepts_real_settings() -> None:
    settings = Settings(environment="production", secret_key="x" * 40, cookie_secure=True)
    assert settings.cookie_secure is True
