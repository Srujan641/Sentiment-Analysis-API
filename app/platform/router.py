from fastapi import APIRouter

from app.platform.routes import account, analyses, auth, keys, products, reviews

platform_router = APIRouter(prefix="/v1")
for module in (auth, keys, account, products, reviews, analyses):
    platform_router.include_router(module.router)
