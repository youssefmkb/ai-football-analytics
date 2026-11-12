from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import decode_access_token
from app.db.session import get_db
from app.db.tenant import bind_tenant
from app.models import Membership, Role, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def get_optional_membership(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Membership | None:
    """The user's membership, or None when they have not joined a club yet."""
    return db.scalar(
        select(Membership)
        .where(Membership.user_id == user.id)
        .options(joinedload(Membership.organization))
    )


def get_current_membership(
    membership: Membership | None = Depends(get_optional_membership),
) -> Membership:
    """Every club-scoped endpoint depends on this: the club comes from the token only."""
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No club yet")
    return membership


def get_tenant_db(
    membership: Membership = Depends(get_current_membership), db: Session = Depends(get_db)
) -> Session:
    """Session scoped to the caller's club. Use it for every club-scoped query."""
    bind_tenant(db, membership.organization_id)
    return db


def require_staff(membership: Membership = Depends(get_current_membership)) -> Membership:
    """Only club admins and coaches may change club data."""
    if membership.role not in (Role.CLUB_ADMIN, Role.COACH):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    return membership


def require_admin(membership: Membership = Depends(get_current_membership)) -> Membership:
    """Only club admins manage members and invitations."""
    if membership.role != Role.CLUB_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Club admin only")
    return membership
