from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.incidents import router as incidents_router
from app.api.routes.scoring import router as scoring_router
from app.api.routes.trends import router as trends_router

_STATIC = Path(__file__).parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="TrafficMY", version="0.1.0")
    app.include_router(health_router, prefix="/api")
    app.include_router(incidents_router, prefix="/api")
    app.include_router(scoring_router, prefix="/api")
    app.include_router(trends_router, prefix="/api")

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=_STATIC), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(_STATIC / "index.html")

    return app


app = create_app()
