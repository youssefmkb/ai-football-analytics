from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_membership
from app.core.config import get_settings
from app.core.security import (
    as_utc,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    utcnow,
    verify_password,
)
from app.db.session import get_db
from app.models import Membership, RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    MembershipOut,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "afa_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _issue_tokens(db: Session, response: Response, user: User) -> TokenResponse:
    """Create a refresh token (cookie) and an access token (body) for the user."""
    settings = get_settings()
    token, token_hash = new_refresh_token()
    lifetime = timedelta(days=settings.refresh_token_days)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=utcnow() + lifetime))
    db.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    return TokenResponse(access_token=create_access_token(user.id))


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    return _issue_tokens(db, response, user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not verify_password(payload.password, user.password_hash if user else None) or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return _issue_tokens(db, response, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db),
) -> TokenResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )
    if not refresh_token:
        raise unauthorized
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if stored is None:
        _clear_cookie(response)
        raise unauthorized
    if stored.revoked_at is not None:
        # A rotated token is being replayed: assume theft and end every session.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        db.commit()
        _clear_cookie(response)
        raise unauthorized
    if as_utc(stored.expires_at) <= utcnow():
        _clear_cookie(response)
        raise unauthorized
    user = db.get(User, stored.user_id)
    if user is None:
        raise unauthorized
    stored.revoked_at = utcnow()
    return _issue_tokens(db, response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db),
) -> None:
    if refresh_token:
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        db.commit()
    _clear_cookie(response)


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(get_current_user),
    membership: Membership | None = Depends(get_optional_membership),
) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(user),
        membership=MembershipOut(
            organization_id=membership.organization_id,
            organization_name=membership.organization.name,
            role=membership.role,
        )
        if membership
        else None,
    )
