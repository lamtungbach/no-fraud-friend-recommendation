"""
FastAPI Backend Application Entrypoint.
Hệ thống API Gợi ý Bạn bè Không Gian lận (No-Fraud Friend Recommendation Service).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.config import ApiSettings
from src.api.routers import health_router, recommendations_router, trust_router
from src.api.runtime import ApiRuntime, build_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Dependencies are composed before startup; liveness remains available if Trust fails."""

    del app
    yield


def create_app(
    *, settings: ApiSettings | None = None, runtime: ApiRuntime | None = None
) -> FastAPI:
    """Factory khởi tạo ứng dụng FastAPI."""
    settings = settings or ApiSettings.from_environment()
    runtime = runtime or build_runtime(settings)
    app = FastAPI(
        title="No-Fraud Friend Recommendation & Trust Agent API",
        description=(
            "Hệ thống Backend Service phục vụ Gợi ý Bạn bè An toàn (No-Fraud Friend Recommendation).\n\n"
            "- Tích hợp Trust & Fraud Detection Agent (R-GCN + 4 Trụ cột Tín nhiệm).\n"
            "- Bộ lọc ứng viên an toàn O(1) cho PYMK Link Prediction Engine.\n"
            "- Multi-step reasoning trace giải thích quyết định loại bỏ tài khoản đáng ngờ."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(trust_router)
    app.include_router(recommendations_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", tags=["Hệ thống"])
    def root():
        return {
            "name": "No-Fraud Friend Recommendation API",
            "version": "2.0.0",
            "status": "online",
            "docs": "/docs",
            "health": "/health/live",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104
