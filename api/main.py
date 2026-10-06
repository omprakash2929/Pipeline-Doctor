"""FastAPI application entry point."""

from fastapi import FastAPI
from api.routes.analyze import router as analyze_router
from models.schemas import HealthResponse

app = FastAPI(
    title="Pipeline Doctor",
    description="AI-powered CI/CD failure analyzer",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="healthy")


app.include_router(analyze_router, prefix="/api", tags=["analyze"])
