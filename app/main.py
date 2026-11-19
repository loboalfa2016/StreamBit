from fastapi import FastAPI
from app.core.config import settings
from app.api import auth

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API REST para el catálogo y reproducción de StreamBit",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(auth.router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "message": "StreamBit API is running"
    }