"""
FastAPI Backend Application Entrypoint.
Hệ thống API Gợi ý Bạn bè Không Gian lận (No-Fraud Friend Recommendation Service).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import health_router, trust_router
from src.api.deps import get_trust_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event: Nạp trước hồ sơ tín nhiệm vào bộ nhớ lúc khởi động ứng dụng."""
    service = get_trust_service()
    if not service.is_loaded:
        try:
            count = service.load_profiles()
            print(f"[API Startup] Da nap {count:,} ho so tin nhiem vao In-Memory Cache.")
        except Exception as e:
            print(f"[API Startup Warning] Khong the nap ho so tu dong: {e}")
    yield


def create_app() -> FastAPI:
    """Factory khởi tạo ứng dụng FastAPI."""
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

    # Cấu hình CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Đăng ký các Routers
    app.include_router(health_router)
    app.include_router(trust_router)

    @app.get("/", tags=["Hệ thống"])
    def root():
        return {
            "name": "No-Fraud Friend Recommendation API",
            "version": "2.0.0",
            "status": "online",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104
