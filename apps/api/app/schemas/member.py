import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, EmailStr, Field

from app.models.membership import Role


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


InvitableRole = Literal["coach", "player"]


class InvitationCreate(BaseModel):
    role: InvitableRole
    label: Annotated[str | None, Field(max_length=120), AfterValidator(_blank_to_none)] = None


class InvitationOut(BaseModel):
    id: uuid.UUID
    role: Role
    label: str | None
    expires_at: AwareDatetime
    created_at: datetime


class InvitationCreated(InvitationOut):
    """Returned once, at creation: the only response that carries the token."""

    token: str


class InvitationPreview(BaseModel):
    """What someone holding the link may see before joining."""

    organization_name: str
    role: Role
    expires_at: AwareDatetime


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: EmailStr
    role: Role
    is_self: bool


class MemberUpdate(BaseModel):
    role: Role
