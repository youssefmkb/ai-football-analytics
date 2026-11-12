"""Members and invitations of the caller's club. Admin only, except accepting."""

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import (
    get_current_user,
    get_optional_membership,
    get_tenant_db,
    require_admin,
)
from app.core.security import as_utc, hash_refresh_token, utcnow
from app.db.session import get_db
from app.models import Invitation, Membership, Role, User
from app.schemas.auth import MembershipOut
from app.schemas.member import (
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    MemberUpdate,
)

INVITATION_LIFETIME = timedelta(days=7)
NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
INVALID_LINK = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found or no longer valid"
)

club_router = APIRouter(prefix="/organizations/current", tags=["members"])
public_router = APIRouter(prefix="/invitations", tags=["invitations"])


def _hash(token: str) -> str:
    return hash_refresh_token(token)


def _invitation_out(invitation: Invitation) -> dict[str, object]:
    return {
        "id": invitation.id,
        "role": invitation.role,
        "label": invitation.label,
        "expires_at": as_utc(invitation.expires_at),
        "created_at": invitation.created_at,
    }


def _admin_count(db: Session, organization_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == Role.CLUB_ADMIN,
            )
        )
        or 0
    )


def _get_member(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    member = db.scalar(
        select(Membership)
        .where(Membership.organization_id == organization_id, Membership.user_id == user_id)
        .options(joinedload(Membership.user))
    )
    if member is None:
        raise NOT_FOUND
    return member


def _member_out(member: Membership, caller: Membership) -> MemberOut:
    return MemberOut(
        user_id=member.user_id,
        full_name=member.user.full_name,
        email=member.user.email,
        role=member.role,
        is_self=member.user_id == caller.user_id,
    )


# --- Members ---------------------------------------------------------------


@club_router.get("/members", response_model=list[MemberOut])
def list_members(
    admin: Membership = Depends(require_admin), db: Session = Depends(get_tenant_db)
) -> list[MemberOut]:
    members = db.scalars(
        select(Membership)
        .join(Membership.user)
        .where(Membership.organization_id == admin.organization_id)
        .options(joinedload(Membership.user))
        .order_by(User.full_name)
    ).all()
    return [_member_out(member, admin) for member in members]


@club_router.patch("/members/{user_id}", response_model=MemberOut)
def update_member(
    user_id: uuid.UUID,
    payload: MemberUpdate,
    admin: Membership = Depends(require_admin),
    db: Session = Depends(get_tenant_db),
) -> MemberOut:
    member = _get_member(db, admin.organization_id, user_id)
    demoting_an_admin = member.role == Role.CLUB_ADMIN and payload.role != Role.CLUB_ADMIN
    if demoting_an_admin and _admin_count(db, admin.organization_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A club keeps at least one admin"
        )
    member.role = payload.role
    db.commit()
    return _member_out(member, admin)


@club_router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: uuid.UUID,
    admin: Membership = Depends(require_admin),
    db: Session = Depends(get_tenant_db),
) -> None:
    member = _get_member(db, admin.organization_id, user_id)
    if member.role == Role.CLUB_ADMIN and _admin_count(db, admin.organization_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A club keeps at least one admin"
        )
    db.delete(member)
    db.commit()


# --- Invitations, admin side ----------------------------------------------


@club_router.post(
    "/invitations", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED
)
def create_invitation(
    payload: InvitationCreate,
    admin: Membership = Depends(require_admin),
    db: Session = Depends(get_tenant_db),
) -> InvitationCreated:
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        organization_id=admin.organization_id,
        token_hash=_hash(token),
        role=Role(payload.role),
        label=payload.label,
        created_by_id=admin.user_id,
        expires_at=utcnow() + INVITATION_LIFETIME,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return InvitationCreated(**_invitation_out(invitation), token=token)


@club_router.get("/invitations", response_model=list[InvitationOut])
def list_invitations(
    admin: Membership = Depends(require_admin), db: Session = Depends(get_tenant_db)
) -> list[InvitationOut]:
    """Pending invitations: not used, not revoked, not expired."""
    invitations = db.scalars(
        select(Invitation)
        .where(
            Invitation.organization_id == admin.organization_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > utcnow(),
        )
        .order_by(Invitation.created_at.desc())
    ).all()
    return [InvitationOut(**_invitation_out(invitation)) for invitation in invitations]


@club_router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: uuid.UUID,
    admin: Membership = Depends(require_admin),
    db: Session = Depends(get_tenant_db),
) -> None:
    invitation = db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == admin.organization_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
    )
    if invitation is None:
        raise NOT_FOUND
    invitation.revoked_at = utcnow()
    db.commit()


# --- Invitations, side of the person who received the link ----------------
#
# These run before the caller belongs to the club, so they cannot use
# get_tenant_db. The token itself is the proof: it is looked up by its hash,
# and only a valid, unused, unrevoked, unexpired invitation is ever returned.


def _find_valid(db: Session, token: str, *, lock: bool = False) -> Invitation:
    query = (
        select(Invitation)
        .where(Invitation.token_hash == _hash(token))
        .options(joinedload(Invitation.organization))
    )
    if lock:
        query = query.with_for_update(of=Invitation)
    invitation = db.scalar(query)
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or as_utc(invitation.expires_at) <= utcnow()
    ):
        raise INVALID_LINK
    return invitation


@public_router.get("/{token}", response_model=InvitationPreview)
def preview_invitation(token: str, db: Session = Depends(get_db)) -> InvitationPreview:
    invitation = _find_valid(db, token)
    return InvitationPreview(
        organization_name=invitation.organization.name,
        role=invitation.role,
        expires_at=as_utc(invitation.expires_at),
    )


@public_router.post("/{token}/accept", response_model=MembershipOut)
def accept_invitation(
    token: str,
    user: User = Depends(get_current_user),
    existing: Membership | None = Depends(get_optional_membership),
    db: Session = Depends(get_db),
) -> MembershipOut:
    # Locked so that two people using the same link at once cannot both join.
    invitation = _find_valid(db, token, lock=True)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already belongs to a club"
        )
    db.add(
        Membership(
            user_id=user.id, organization_id=invitation.organization_id, role=invitation.role
        )
    )
    invitation.accepted_at = utcnow()
    invitation.accepted_by_id = user.id
    db.commit()
    return MembershipOut(
        organization_id=invitation.organization_id,
        organization_name=invitation.organization.name,
        role=invitation.role,
    )
