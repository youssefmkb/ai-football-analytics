import uuid

from pydantic import BaseModel, Field, field_validator

from app.models.membership import Role


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    role: Role
