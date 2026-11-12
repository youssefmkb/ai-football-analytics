import uuid
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field, model_validator

from app.models.match import MatchStatus
from app.schemas.team import Format, _stripped


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


OptionalText = Annotated[str | None, Field(max_length=160), AfterValidator(_blank_to_none)]
Competition = Annotated[str | None, Field(max_length=120), AfterValidator(_blank_to_none)]
OpponentName = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_stripped)]
Color = Annotated[str | None, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
PitchLength = Annotated[float | None, Field(ge=15, le=130)]
PitchWidth = Annotated[float | None, Field(ge=10, le=100)]
Score = Annotated[int | None, Field(ge=0, le=99)]


class MatchCreate(BaseModel):
    team_id: uuid.UUID
    opponent_name: OpponentName
    kickoff_at: AwareDatetime
    format: Format | None = None  # defaults to the team's format
    location: OptionalText = None
    competition: Competition = None
    pitch_length_m: PitchLength = None
    pitch_width_m: PitchWidth = None
    team_color: Color = None
    opponent_color: Color = None
    score_team: Score = None
    score_opponent: Score = None

    @model_validator(mode="after")
    def _score_is_complete(self) -> "MatchCreate":
        if (self.score_team is None) != (self.score_opponent is None):
            raise ValueError("give both scores or neither")
        return self


class MatchUpdate(BaseModel):
    """Fields left out stay unchanged. Optional fields accept null to clear them."""

    opponent_name: OpponentName | None = None
    kickoff_at: AwareDatetime | None = None
    format: Format | None = None
    location: OptionalText = None
    competition: Competition = None
    pitch_length_m: PitchLength = None
    pitch_width_m: PitchWidth = None
    team_color: Color = None
    opponent_color: Color = None
    score_team: Score = None
    score_opponent: Score = None


class LineupEntryIn(BaseModel):
    player_id: uuid.UUID
    is_starter: bool


class LineupUpdate(BaseModel):
    players: list[LineupEntryIn] = Field(max_length=40)

    @model_validator(mode="after")
    def _no_duplicates(self) -> "LineupUpdate":
        ids = [entry.player_id for entry in self.players]
        if len(ids) != len(set(ids)):
            raise ValueError("a player appears twice")
        return self


class LineupEntryOut(BaseModel):
    player_id: uuid.UUID
    first_name: str
    last_name: str
    shirt_number: int | None
    is_starter: bool


class MatchOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    opponent_name: str
    kickoff_at: AwareDatetime
    format: int
    location: str | None
    competition: str | None
    pitch_length_m: float | None
    pitch_width_m: float | None
    team_color: str | None
    opponent_color: str | None
    score_team: int | None
    score_opponent: int | None
    status: MatchStatus


class MatchDetailOut(MatchOut):
    lineup: list[LineupEntryOut]
