import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_membership, get_tenant_db, require_staff
from app.models import Membership, Player, Team, TeamMembership
from app.schemas.team import (
    SquadPlayerCreate,
    SquadPlayerOut,
    SquadPlayerUpdate,
    TeamCreate,
    TeamOut,
    TeamUpdate,
)

router = APIRouter(prefix="/teams", tags=["teams"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _get_team(db: Session, organization_id: uuid.UUID, team_id: uuid.UUID) -> Team:
    # Another club's team answers 404, like a team that does not exist.
    team = db.scalar(
        select(Team).where(Team.id == team_id, Team.organization_id == organization_id)
    )
    if team is None:
        raise NOT_FOUND
    return team


def _get_squad_entry(
    db: Session, organization_id: uuid.UUID, team_id: uuid.UUID, player_id: uuid.UUID
) -> TeamMembership:
    entry = db.scalar(
        select(TeamMembership)
        .where(
            TeamMembership.team_id == team_id,
            TeamMembership.player_id == player_id,
            TeamMembership.organization_id == organization_id,
        )
        .options(joinedload(TeamMembership.player))
    )
    if entry is None:
        raise NOT_FOUND
    return entry


def _team_out(db: Session, team: Team) -> TeamOut:
    count = db.scalar(
        select(func.count()).select_from(TeamMembership).where(TeamMembership.team_id == team.id)
    )
    return TeamOut(
        id=team.id, name=team.name, default_format=team.default_format, player_count=count or 0
    )


def _squad_out(entry: TeamMembership) -> SquadPlayerOut:
    return SquadPlayerOut(
        id=entry.player.id,
        first_name=entry.player.first_name,
        last_name=entry.player.last_name,
        shirt_number=entry.shirt_number,
        position=entry.position,
    )


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> TeamOut:
    team = Team(
        organization_id=membership.organization_id,
        name=payload.name,
        default_format=payload.default_format,
    )
    db.add(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Team name already used"
        ) from exc
    return _team_out(db, team)


@router.get("", response_model=list[TeamOut])
def list_teams(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_tenant_db),
) -> list[TeamOut]:
    teams = db.scalars(
        select(Team).where(Team.organization_id == membership.organization_id).order_by(Team.name)
    ).all()
    return [_team_out(db, team) for team in teams]


@router.get("/{team_id}", response_model=TeamOut)
def get_team(
    team_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_tenant_db),
) -> TeamOut:
    return _team_out(db, _get_team(db, membership.organization_id, team_id))


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> TeamOut:
    team = _get_team(db, membership.organization_id, team_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "default_format"):
        if changes.get(field) is not None:
            setattr(team, field, changes[field])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Team name already used"
        ) from exc
    return _team_out(db, team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: uuid.UUID,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> None:
    team = _get_team(db, membership.organization_id, team_id)
    player_ids = [entry.player_id for entry in team.memberships]
    db.delete(team)
    db.flush()
    _delete_players_without_team(db, membership.organization_id, player_ids)
    db.commit()


def _delete_players_without_team(
    db: Session, organization_id: uuid.UUID, player_ids: list[uuid.UUID]
) -> None:
    """A player only exists through a team for now, so orphans are removed."""
    if not player_ids:
        return
    still_in_a_team = set(
        db.scalars(select(TeamMembership.player_id).where(TeamMembership.player_id.in_(player_ids)))
    )
    for player_id in set(player_ids) - still_in_a_team:
        player = db.scalar(
            select(Player).where(Player.id == player_id, Player.organization_id == organization_id)
        )
        if player is not None:
            db.delete(player)


@router.get("/{team_id}/players", response_model=list[SquadPlayerOut])
def list_squad(
    team_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_tenant_db),
) -> list[SquadPlayerOut]:
    team = _get_team(db, membership.organization_id, team_id)
    entries = db.scalars(
        select(TeamMembership)
        .join(TeamMembership.player)
        .where(TeamMembership.team_id == team.id)
        .options(joinedload(TeamMembership.player))
        .order_by(
            TeamMembership.shirt_number.is_(None),
            TeamMembership.shirt_number,
            Player.last_name,
            Player.first_name,
        )
    ).all()
    return [_squad_out(entry) for entry in entries]


@router.post(
    "/{team_id}/players", response_model=SquadPlayerOut, status_code=status.HTTP_201_CREATED
)
def add_player(
    team_id: uuid.UUID,
    payload: SquadPlayerCreate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> SquadPlayerOut:
    team = _get_team(db, membership.organization_id, team_id)
    player = Player(
        organization_id=membership.organization_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    entry = TeamMembership(
        organization_id=membership.organization_id,
        team=team,
        player=player,
        shirt_number=payload.shirt_number,
        position=payload.position,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Shirt number already used"
        ) from exc
    return _squad_out(entry)


@router.patch("/{team_id}/players/{player_id}", response_model=SquadPlayerOut)
def update_player(
    team_id: uuid.UUID,
    player_id: uuid.UUID,
    payload: SquadPlayerUpdate,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> SquadPlayerOut:
    entry = _get_squad_entry(db, membership.organization_id, team_id, player_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name"):
        if changes.get(field) is not None:
            setattr(entry.player, field, changes[field])
    for field in ("shirt_number", "position"):
        if field in changes:
            setattr(entry, field, changes[field])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Shirt number already used"
        ) from exc
    return _squad_out(_get_squad_entry(db, membership.organization_id, team_id, player_id))


@router.delete("/{team_id}/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_player(
    team_id: uuid.UUID,
    player_id: uuid.UUID,
    membership: Membership = Depends(require_staff),
    db: Session = Depends(get_tenant_db),
) -> None:
    entry = _get_squad_entry(db, membership.organization_id, team_id, player_id)
    db.delete(entry)
    db.flush()
    _delete_players_without_team(db, membership.organization_id, [player_id])
    db.commit()
