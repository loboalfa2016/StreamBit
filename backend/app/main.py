from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, admin, movies 
from app.api.v1.endpoints import availability
from app.api.v1.endpoints import sources
from app.api.v1.endpoints import playback
from app.api.v1.endpoints import collections
from app.api.v1.endpoints import user_lists
from app.api.v1.endpoints import history
from app.api.v1.endpoints import ratings
from app.api.v1.endpoints import comments
from app.api.v1.endpoints import moderation
from app.api.v1.endpoints import notifications
from app.api.v1.endpoints import recommendations
from app.api.v1.endpoints import ads
from app.api.v1.endpoints import admin_panel
from app.api.v1.endpoints import reports
from app.api.v1.endpoints import privacy

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "API REST oficial de StreamBit para gestión de catálogo cinematográfico, "
        "disponibilidad por fuentes autorizadas, reproducción pre-roll, comunidad, "
        "notificaciones, recomendaciones, analítica y privacidad."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

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
app.include_router(comments.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(ads.router, prefix="/api/v1")
app.include_router(admin_panel.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(privacy.router, prefix="/api/v1")
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "message": "StreamBit API is running"
    }