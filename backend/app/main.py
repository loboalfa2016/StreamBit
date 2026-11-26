from fastapi import FastAPI
from app.core.config import settings
from app.api import auth, admin, movies 
from app.api.v1.endpoints import availability
from app.api.v1.endpoints import sources
from app.api.v1.endpoints import playback
from app.api.v1.endpoints import collections
from app.api.v1.endpoints import user_lists
from app.api.v1.endpoints import history
from app.api.v1.endpoints import ratings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API REST para el catálogo y reproducción de StreamBit",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(movies.router)
app.include_router(availability.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(playback.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(user_lists.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(ratings.router, prefix="/api/v1")
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "message": "StreamBit API is running"
    }