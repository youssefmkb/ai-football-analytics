import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.membership import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    role: Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str


class MeResponse(BaseModel):
    user: UserOut
    membership: MembershipOut | None
