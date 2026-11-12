from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_user, get_optional_membership
from app.db.session import get_db
from app.models import Membership, Organization, Role, User
from app.schemas.organization import OrganizationCreate, OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    existing: Membership | None = Depends(get_optional_membership),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    """Create a club. Its creator becomes the club admin."""
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already belongs to a club"
        )
    organization = Organization(name=payload.name)
    organization.memberships.append(Membership(user_id=user.id, role=Role.CLUB_ADMIN))
    db.add(organization)
    db.commit()
    return OrganizationOut(id=organization.id, name=organization.name, role=Role.CLUB_ADMIN)


@router.get("/current", response_model=OrganizationOut)
def current_organization(
    membership: Membership = Depends(get_current_membership),
) -> OrganizationOut:
    """The caller's club, resolved from the token and never from a client parameter."""
    return OrganizationOut(
        id=membership.organization_id,
        name=membership.organization.name,
        role=membership.role,
    )
