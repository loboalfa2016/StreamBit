from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "StreamBit API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # Configuración de Base de Datos
    POSTGRES_USER: str = "streambit_user"
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "db"  # Este es el nombre del servicio en docker-compose
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "streambit_db"

    # Configuración de JWT
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Configuración de sincronización TMDB (BE-08)
    TMDB_API_KEY: str = ""
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    SYNC_INTERVAL_HOURS: int = 24

    # Configuración de calificaciones (BE-16)
    ALLOW_RATING_EDIT: bool = True

    # Configuración de seguridad, CORS y retención (BE-25)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    HISTORY_RETENTION_DAYS: int = 180
    NOTIFICATIONS_RETENTION_DAYS: int = 90

    @property
    def DATABASE_URI(self) -> str:
        # Construye la URL asíncrona: postgresql+asyncpg://user:password@server:port/db
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()