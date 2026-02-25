import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from eth_account import Account
from eth_account.messages import encode_defunct

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.wallet import Wallet

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
    yield SessionLocal
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. POST /api/auth/metamask/nonce with a valid address → 200 with nonce and message
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_nonce_valid_address(test_db):
    account = Account.create()
    address = account.address.lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/metamask/nonce", json={"address": address})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "nonce" in data
        assert "message" in data
        assert data["nonce"] in data["message"]


# ---------------------------------------------------------------------------
# 2. POST /api/auth/metamask/nonce with an invalid address → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_nonce_invalid_address(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/metamask/nonce", json={"address": "not_an_address"})
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 3. POST /api/auth/metamask/nonce for a new address creates a USDT wallet
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_nonce_creates_usdt_wallet(test_db):
    account = Account.create()
    address = account.address.lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/metamask/nonce", json={"address": address})
        assert r.status_code == 200, r.text

    # Check DB directly for the wallet
    async with test_db() as session:
        user = await session.scalar(select(User).where(User.wallet_address == address))
        assert user is not None, "User should have been created"
        wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT"))
        assert wallet is not None, "USDT wallet should have been created"


# ---------------------------------------------------------------------------
# 4. POST /api/auth/metamask/verify with a valid signature → returns access_token
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_verify_valid_signature(test_db):
    account = Account.create()
    address = account.address.lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: get nonce
        r = await client.post("/api/auth/metamask/nonce", json={"address": address})
        assert r.status_code == 200, r.text
        data = r.json()
        nonce = data["nonce"]
        message = data["message"]

        # Step 2: sign the message
        msg = encode_defunct(text=message)
        signed = account.sign_message(msg)
        signature = signed.signature.hex()

        # Step 3: verify
        r = await client.post("/api/auth/metamask/verify", json={
            "address": address,
            "signature": signature,
        })
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()


# ---------------------------------------------------------------------------
# 5. POST /api/auth/metamask/verify with an invalid signature → 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_verify_invalid_signature(test_db):
    account = Account.create()
    address = account.address.lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get a valid nonce first
        r = await client.post("/api/auth/metamask/nonce", json={"address": address})
        assert r.status_code == 200, r.text

        # Submit a garbage signature
        r = await client.post("/api/auth/metamask/verify", json={
            "address": address,
            "signature": "0x" + "ab" * 65,
        })
        assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 6. POST /api/auth/metamask/verify with an expired nonce → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metamask_verify_expired_nonce(test_db):
    account = Account.create()
    address = account.address.lower()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get a valid nonce
        r = await client.post("/api/auth/metamask/nonce", json={"address": address})
        assert r.status_code == 200, r.text
        data = r.json()
        nonce = data["nonce"]
        message = data["message"]

        # Sign it
        msg = encode_defunct(text=message)
        signed = account.sign_message(msg)
        signature = signed.signature.hex()

    # Manually back-date nonce_created_at in the DB to simulate expiry
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=11)
    async with test_db() as session:
        user = await session.scalar(select(User).where(User.wallet_address == address))
        assert user is not None
        # SQLite stores as naive datetime; strip tzinfo to match SQLite behaviour
        user.nonce_created_at = expired_time.replace(tzinfo=None)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/metamask/verify", json={
            "address": address,
            "signature": signature,
        })
        assert r.status_code == 400, r.text
