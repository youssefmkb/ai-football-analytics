from fastapi import APIRouter

from app.api.v1 import auth, health, matches, members, organizations, teams

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(teams.router)
api_router.include_router(matches.router)
api_router.include_router(members.club_router)
api_router.include_router(members.public_router)
