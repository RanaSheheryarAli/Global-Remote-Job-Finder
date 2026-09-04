from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.matching import router as matching_router
from app.api.routes.refresh import router as refresh_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(jobs_router)
api_router.include_router(matching_router)
api_router.include_router(refresh_router)
api_router.include_router(sources_router)
