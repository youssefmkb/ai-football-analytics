import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_membership, get_tenant_db, require_staff
from app.core.security import as_utc
from app.models import Match, MatchLineup, Membership, Team, TeamMembership
from app.schemas.match import (
    LineupEntryOut,
    LineupUpdate,
    MatchCreate,
    MatchDetailOut,
    MatchOut,
    MatchUpdate,
)

router = APIRouter(prefix="/matches", tags=["matches"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
NULLABLE = (
    "location",
    "competition",
    "pitch_length_m",
    "pitch_width_m",
    "team_color",
    "opponent_color",
)
REQUIRED = ("opponent_name", "kickoff_at", "format")


def _get_match(db: Session, organization_id: uuid.UUID, match_id: uuid.UUID) -> Match:
    match = db.scalar(
        select(Match)
        .where(Match.id == match_id, Match.organization_id == organization_id)
        .options(joinedload(Match.team))
    )
    if match is None:
        raise NOT_FOUND
    return match


def _match_fields(match: Match) -> dict[str, object]:
    return {
        "id": match.id,
        "team_id": match.team_id,
        "team_name": match.team.name,
        "opponent_name": match.opponent_name,
        "kickoff_at": as_utc(match.kickoff_at),
        "format": match.format,
        "location": match.location,
        "competition": match.competition,
        "pitch_length_m": match.pitch_length_m,
        "pitch_width_m": match.pitch_width_m,
        "team_color": match.team_color,
        "opponent_color": match.opponent_color,
        "score_team": match.score_team,
        "score_opponent": match.score_opponent,
        "status": match.status,
    }


def _detail(db: Session, match: Match) -> MatchDetailOut:
    rows = db.execute(
        select(MatchLineup, TeamMembership.shirt_number)
        .join(MatchLineup.player)
        .outerjoin(
            TeamMembership,
            (TeamMembership.player_id == MatchLineup.player_id)
            & (TeamMembership.team_id == match.team_id),
        )
        .where(MatchLineup.match_id == match.id)
        .options(joinedload(MatchLineup.player))
    ).all()
    lineup = [
        LineupEntryOut(
            player_id=entry.player_id,
            first_name=entry.player.first_name,
            last_name=entry.player.last_name,
            shirt_number=shirt_number,
            is_starter=entry.is_starter,
        )
        for entry, shirt_number in rows
    ]
    lineup.sort(
        key=lambda e: (not e.is_starter, e.shirt_number is None, e.shirt_number or 0, e.last_name)
    )
    return MatchDetailOut(**_match_fields(match), lineup=lineup)


@router.post("", response_model=MatchDetailOut, status_code=status.HTTP_201_CREATED)
def create_match(
    payload: MatchCreate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> MatchDetailOut:
    team = db.scalar(
        select(Team).where(
            Team.id == payload.team_id, Team.organization_id == membership.organization_id
        )
    )
    if team is None:
        # The team id is client input: another club's team must look missing.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    data = payload.model_dump(exclude={"team_id", "format"})
    match = Match(
        organization_id=membership.organization_id,
        team_id=team.id,
        format=payload.format or team.default_format,
        **data,
    )
    db.add(match)
    db.commit()
    return _detail(db, _get_match(db, membership.organization_id, match.id))


@router.get("", response_model=list[MatchOut])
def list_matches(
    team_id: uuid.UUID | None = None,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_tenant_db),
) -> list[MatchOut]:
    query = (
        select(Match)
        .where(Match.organization_id == membership.organization_id)
        .options(joinedload(Match.team))
        .order_by(Match.kickoff_at.desc(), Match.created_at.desc())
    )
    if team_id is not None:
        query = query.where(Match.team_id == team_id)
    return [MatchOut(**_match_fields(match)) for match in db.scalars(query)]


@router.get("/{match_id}", response_model=MatchDetailOut)
def get_match(
    match_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_tenant_db),
) -> MatchDetailOut:
    return _detail(db, _get_match(db, membership.organization_id, match_id))


@router.patch("/{match_id}", response_model=MatchDetailOut)
def update_match(
    match_id: uuid.UUID,
    payload: MatchUpdate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> MatchDetailOut:
    match = _get_match(db, membership.organization_id, match_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in REQUIRED:
        if changes.get(field) is not None:
            setattr(match, field, changes[field])
    for field in NULLABLE:
        if field in changes:
            setattr(match, field, changes[field])

    score_team = changes.get("score_team", match.score_team)
    score_opponent = changes.get("score_opponent", match.score_opponent)
    if (score_team is None) != (score_opponent is None):
        raise HTTPException(
            status_code=422,
            detail="Give both scores or neither",
        )
    match.score_team, match.score_opponent = score_team, score_opponent
    db.commit()
    return _detail(db, _get_match(db, membership.organization_id, match_id))


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_match(
    match_id: uuid.UUID,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> None:
    db.delete(_get_match(db, membership.organization_id, match_id))
    db.commit()


@router.put("/{match_id}/lineup", response_model=MatchDetailOut)
def set_lineup(
    match_id: uuid.UUID,
    payload: LineupUpdate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> MatchDetailOut:
    """Replace the whole lineup of the match."""
    match = _get_match(db, membership.organization_id, match_id)
    squad = set(
        db.scalars(
            select(TeamMembership.player_id).where(
                TeamMembership.team_id == match.team_id,
                TeamMembership.organization_id == membership.organization_id,
            )
        )
    )
    if any(entry.player_id not in squad for entry in payload.players):
        raise HTTPException(
            status_code=422,
            detail="Every player must belong to the team of the match",
        )
    starters = sum(entry.is_starter for entry in payload.players)
    if starters > match.format:
        raise HTTPException(
            status_code=422,
            detail=f"At most {match.format} starters",
        )
    match.lineup.clear()
    db.flush()
    match.lineup.extend(
        MatchLineup(
            organization_id=membership.organization_id,
            player_id=entry.player_id,
            is_starter=entry.is_starter,
        )
        for entry in payload.players
    )
    db.commit()
    return _detail(db, _get_match(db, membership.organization_id, match_id))
