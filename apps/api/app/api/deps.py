from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Membership, User

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
