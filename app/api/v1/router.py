from fastapi import APIRouter

from app.api.v1.routes import jobs, monitoring, predict

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(predict.router)
api_router.include_router(jobs.router)
api_router.include_router(monitoring.router)
