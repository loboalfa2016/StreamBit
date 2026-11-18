from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Motor asíncrono
engine = create_async_engine(settings.DATABASE_URI, echo=True)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Base para nuestros modelos
Base = declarative_base()

# Dependencia para inyectar la sesión en nuestras rutas de FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session