from fastapi import APIRouter

from app.api.routes import health, knowledge, projects, sessions, sources

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(sources.router, tags=["sources"])
