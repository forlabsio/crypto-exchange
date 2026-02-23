import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.database import Base, get_db
from app.main import app

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async def override_get_db():
        async with SessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_register_returns_201(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={
            "email": "testuser@example.com",
            "password": "password123"
        })
        assert r.status_code == 201, r.text

@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        assert r.status_code == 401, r.text

@pytest.mark.asyncio
async def test_register_then_login_succeeds(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register
        r = await client.post("/api/auth/register", json={
            "email": "login_test@example.com",
            "password": "mypassword"
        })
        assert r.status_code == 201, r.text
        # Login
        r = await client.post("/api/auth/login", json={
            "email": "login_test@example.com",
            "password": "mypassword"
        })
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()
