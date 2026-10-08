"""FastAPI application entry point."""

import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api.routes.analyze import router as analyze_router
from models.schemas import HealthResponse

app = FastAPI(
    title="Pipeline Doctor",
    description="AI-powered CI/CD failure analyzer",
    version="0.1.0",
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
def serve_dashboard() -> FileResponse:
    index_path = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_path)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="healthy")


app.include_router(analyze_router, prefix="/api", tags=["analyze"])
