import logging

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from core.bodylimit import BodySizeLimitMiddleware
from core.config import CORS_ORIGINS, IS_PRODUCTION, REDIS_URL
from core.database import init_db
from core.ratelimit import redis_client
from routers.assistant import router as assistant_router
from routers.auth import router as auth_router
from routers.projects import router as projects_router
from services.project_service import init_projects_table

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# 生产环境关闭交互式 API 文档（/docs /redoc /openapi.json），减少攻击面
app = FastAPI(
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)
# add_middleware 后添加的在外层：先加 body 限制、后加 CORS，让 413 响应也经过 CORS 拿到响应头
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"]
)


app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(projects_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def bootstrap() -> None:
    init_db()
    init_projects_table()
    try:
        await redis_client.ping()
    except Exception as exc:
        raise RuntimeError(
            f"无法连接 Redis（{REDIS_URL}），限流功能依赖 Redis，服务拒绝启动。"
            "请先启动 redis-server（WSL: sudo service redis-server start）"
        ) from exc
