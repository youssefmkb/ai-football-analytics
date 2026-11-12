import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.team import Player, Team


class MatchStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"


class Match(Base):
    """A match played by one of the club's teams against a named opponent."""

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("format IN (5, 7, 8, 11)", name="ck_matches_format"),
        CheckConstraint("score_team BETWEEN 0 AND 99", name="ck_matches_score_team"),
        CheckConstraint("score_opponent BETWEEN 0 AND 99", name="ck_matches_score_opponent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # A team with matches cannot be deleted: its history would go with it.
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    opponent_name: Mapped[str] = mapped_column(String(120))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    format: Mapped[int] = mapped_column(SmallInteger)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    competition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Pitch size and shirt colours feed calibration and team classification later.
    pitch_length_m: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    pitch_width_m: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    team_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    opponent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    score_team: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    score_opponent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(
            MatchStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=MatchStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped[Team] = relationship()
    lineup: Mapped[list["MatchLineup"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchLineup(Base):
    """A player present at a match, as a starter or a substitute."""

    __tablename__ = "match_lineups"
    __table_args__ = (UniqueConstraint("match_id", "player_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    # A player who appears in a lineup cannot be deleted, for the same reason.
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    is_starter: Mapped[bool] = mapped_column(Boolean)

    match: Mapped[Match] = relationship(back_populates="lineup")
    player: Mapped[Player] = relationship()
