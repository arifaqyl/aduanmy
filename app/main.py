import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc  # type: ignore[attr-defined]

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.incidents import router as incidents_router
from app.api.routes.journey import router as journey_router
from app.api.routes.scoring import router as scoring_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.trends import router as trends_router
from app.core.config import settings

_STATIC = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db.session import init_db
    from app.services.scheduler_service import maybe_refresh_on_startup, start_scheduler

    init_db()
    maybe_refresh_on_startup()
    start_scheduler()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TrafficMY", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(incidents_router, prefix="/api")
    app.include_router(journey_router, prefix="/api")
    app.include_router(scoring_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    app.include_router(trends_router, prefix="/api")

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=_STATIC), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(_STATIC / "index.html")

        @app.get("/methodology", include_in_schema=False)
        def methodology_page() -> FileResponse:
            return FileResponse(_STATIC / "methodology.html")

        @app.get("/developers", include_in_schema=False)
        def developers_page() -> FileResponse:
            return FileResponse(_STATIC / "developers.html")

        @app.get("/status", include_in_schema=False)
        def status_page() -> FileResponse:
            return FileResponse(_STATIC / "status.html")

        @app.get("/embed", include_in_schema=False)
        def embed_page() -> FileResponse:
            return FileResponse(_STATIC / "embed.html")

        @app.get("/manifest.webmanifest", include_in_schema=False)
        def manifest() -> FileResponse:
            return FileResponse(_STATIC / "manifest.webmanifest", media_type="application/manifest+json")

        @app.get("/sw.js", include_in_schema=False)
        def service_worker() -> FileResponse:
            return FileResponse(
                _STATIC / "sw.js",
                media_type="application/javascript",
                headers={"Cache-Control": "no-cache"},
            )

    return app


app = create_app()
