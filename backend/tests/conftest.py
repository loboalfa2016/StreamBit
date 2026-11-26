import uuid
from typing import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User


@pytest.fixture
async def test_session_factory():
    test_engine = create_async_engine(settings.DATABASE_URI, poolclass=NullPool)
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        await test_engine.dispose()


@pytest.fixture
async def client(test_session_factory) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=15.0,
    ) as ac:
        yield ac


@pytest.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def user_factory(db_session: AsyncSession):
    created_ids: list[int] = []

    async def _create_user(role: str = "user") -> tuple[User, str]:
        uid = uuid.uuid4().hex[:8]
        raw_password = "TestPassword123!"
        user = User(
            username=f"test_{role}_{uid}",
            email=f"test_{role}_{uid}@example.com",
            hashed_password=get_password_hash(raw_password),
            role=role,
            is_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        created_ids.append(user.id)
        return user, raw_password

    yield _create_user

    for uid in created_ids:
        u = (
            await db_session.execute(select(User).where(User.id == uid))
        ).scalar_one_or_none()
        if u:
            await db_session.delete(u)
    await db_session.commit()
