import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from app.models.team import Position

Format = Literal[5, 7, 8, 11]


def _stripped(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


TeamName = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_stripped)]
PersonName = Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_stripped)]
ShirtNumber = Annotated[int, Field(ge=1, le=99)]


class TeamCreate(BaseModel):
    name: TeamName
    default_format: Format


class TeamUpdate(BaseModel):
    name: TeamName | None = None
    default_format: Format | None = None


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    default_format: int
    player_count: int


class SquadPlayerCreate(BaseModel):
    first_name: PersonName
    last_name: PersonName
    shirt_number: ShirtNumber | None = None
    position: Position | None = None


class SquadPlayerUpdate(BaseModel):
    """Fields left out stay unchanged. Send null to clear number or position."""

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    shirt_number: ShirtNumber | None = None
    position: Position | None = None


class SquadPlayerOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    shirt_number: int | None
    position: Position | None
