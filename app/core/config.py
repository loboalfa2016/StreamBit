from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn

class Settings(BaseSettings):
    PROJECT_NAME: str = "StreamBit API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # Configuración de Base de Datos
    POSTGRES_USER: str = "streambit_user"
    POSTGRES_PASSWORD: str = "streambit_secret_dev"
    POSTGRES_SERVER: str = "db" # Este es el nombre del servicio en docker-compose
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "streambit_db"
    
    @property
    def DATABASE_URI(self) -> str:
        # Construye la URL asíncrona: postgresql+asyncpg://user:password@server:port/db
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()