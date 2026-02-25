"""
Tests for subscription fee logic: subscribe, unsubscribe, and renewal_check.

Covers:
1. Subscribe deducts fee + locks investment → balances correct
2. Subscribe fails with insufficient balance (fee only, investment only, both)
3. Unsubscribe returns locked_balance to balance
4. renewal_check: free bot just extends next_renewal_at
5. renewal_check: paid bot with sufficient balance → renews, records FeeIncome, extends renewal
6. renewal_check: paid bot with insufficient balance → cancels, returns investment
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.wallet import Wallet
from app.models.bot import Bot, BotSubscription, BotStatus
from app.models.deposit import FeeIncome
from app.services.bot_eviction import renewal_check
from app.database import AsyncSessionLocal

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """Create an isolated in-memory SQLite DB for each test and override get_db."""
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


async def _register_and_login(client: AsyncClient, email: str, password: str = "pass1234") -> str:
    """Register a user (which also creates a USDT wallet with 10000) and return a JWT."""
    r = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _create_bot(session, monthly_fee: float = 0.0) -> Bot:
    """Insert a bot directly into the DB and return it."""
    bot = Bot(name="TestBot", monthly_fee=monthly_fee, status=BotStatus.active)
    session.add(bot)
    await session.commit()
    await session.refresh(bot)
    return bot


async def _get_wallet(session, user_id: int) -> Wallet:
    return await session.scalar(
        select(Wallet).where(Wallet.user_id == user_id, Wallet.asset == "USDT")
    )


async def _get_user(session, email: str) -> User:
    return await session.scalar(select(User).where(User.email == email))


# ---------------------------------------------------------------------------
# 1. Subscribe deducts fee + locks investment → balances correct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_deducts_fee_and_locks_investment(test_db):
    """
    Bot costs 10 USDT/month. User invests 200 USDT.
    After subscribing: balance = 10000 - 10 - 200 = 9790, locked = 200.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _register_and_login(client, "fee_test@example.com")

        async with test_db() as session:
            bot = await _create_bot(session, monthly_fee=10.0)
            bot_id = bot.id
            user = await _get_user(session, "fee_test@example.com")
            user_id = user.id

        r = await client.post(
            f"/api/bots/{bot_id}/subscribe",
            json={"allocated_usdt": 200.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text

    async with test_db() as session:
        wallet = await _get_wallet(session, user_id)
        assert Decimal(str(wallet.balance)) == Decimal("9790.00000000"), (
            f"Expected 9790, got {wallet.balance}"
        )
        assert Decimal(str(wallet.locked_balance)) == Decimal("200.00000000"), (
            f"Expected locked 200, got {wallet.locked_balance}"
        )


# ---------------------------------------------------------------------------
# 2. Subscribe fails with insufficient balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_fails_insufficient_for_fee(test_db):
    """
    User has 10000. Bot fee is 10001 USDT. Should fail with 400.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _register_and_login(client, "insuf_fee@example.com")

        async with test_db() as session:
            # Set balance to 5 so the fee (10) alone exceeds balance
            user = await _get_user(session, "insuf_fee@example.com")
            wallet = await _get_wallet(session, user.id)
            wallet.balance = Decimal("5.00")
            await session.commit()
            bot = await _create_bot(session, monthly_fee=10.0)
            bot_id = bot.id

        r = await client.post(
            f"/api/bots/{bot_id}/subscribe",
            json={"allocated_usdt": 1.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text
        assert "잔액 부족" in r.json()["detail"]


@pytest.mark.asyncio
async def test_subscribe_fails_insufficient_for_investment(test_db):
    """
    User has 15. Fee is 5, investment is 100. Total 105 > 15 → fail.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _register_and_login(client, "insuf_inv@example.com")

        async with test_db() as session:
            user = await _get_user(session, "insuf_inv@example.com")
            wallet = await _get_wallet(session, user.id)
            wallet.balance = Decimal("15.00")
            await session.commit()
            bot = await _create_bot(session, monthly_fee=5.0)
            bot_id = bot.id

        r = await client.post(
            f"/api/bots/{bot_id}/subscribe",
            json={"allocated_usdt": 100.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text
        assert "잔액 부족" in r.json()["detail"]


@pytest.mark.asyncio
async def test_subscribe_fails_zero_balance(test_db):
    """
    User has 0 balance. Even a free bot requiring investment should fail.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _register_and_login(client, "zero_bal@example.com")

        async with test_db() as session:
            user = await _get_user(session, "zero_bal@example.com")
            wallet = await _get_wallet(session, user.id)
            wallet.balance = Decimal("0.00")
            await session.commit()
            bot = await _create_bot(session, monthly_fee=0.0)
            bot_id = bot.id

        r = await client.post(
            f"/api/bots/{bot_id}/subscribe",
            json={"allocated_usdt": 100.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 3. Unsubscribe returns locked_balance to balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsubscribe_returns_locked_balance(test_db):
    """
    Subscribe with 200 allocated (fee=10). Then unsubscribe.
    balance should recover the 200 that was locked.
    Final balance: 9790 + 200 = 9990. locked_balance: 0.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _register_and_login(client, "unsub@example.com")

        async with test_db() as session:
            bot = await _create_bot(session, monthly_fee=10.0)
            bot_id = bot.id
            user = await _get_user(session, "unsub@example.com")
            user_id = user.id

        # Subscribe
        r = await client.post(
            f"/api/bots/{bot_id}/subscribe",
            json={"allocated_usdt": 200.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text

        # Unsubscribe
        r = await client.delete(
            f"/api/bots/{bot_id}/subscribe",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text

    async with test_db() as session:
        wallet = await _get_wallet(session, user_id)
        # fee (10) was charged, investment (200) was returned
        assert Decimal(str(wallet.balance)) == Decimal("9990.00000000"), (
            f"Expected 9990, got {wallet.balance}"
        )
        assert Decimal(str(wallet.locked_balance)) == Decimal("0.00000000"), (
            f"Expected locked 0, got {wallet.locked_balance}"
        )


# ---------------------------------------------------------------------------
# Helpers for renewal_check tests (operate directly on DB, bypassing HTTP)
# ---------------------------------------------------------------------------

async def _setup_renewal_scenario(
    session_factory,
    email: str,
    monthly_fee: float,
    initial_balance: float,
    allocated: float,
    next_renewal_at: datetime,
) -> tuple[int, int, int]:
    """
    Create user + wallet + bot + subscription directly in DB.
    Returns (user_id, bot_id, sub_id).
    """
    async with session_factory() as session:
        user = User(email=email, password_hash="x")
        session.add(user)
        await session.flush()

        wallet = Wallet(
            user_id=user.id,
            asset="USDT",
            balance=Decimal(str(initial_balance)),
            locked_balance=Decimal(str(allocated)),
        )
        session.add(wallet)

        bot = Bot(name=f"Bot-{email}", monthly_fee=monthly_fee, status=BotStatus.active)
        session.add(bot)
        await session.flush()

        sub = BotSubscription(
            user_id=user.id,
            bot_id=bot.id,
            allocated_usdt=Decimal(str(allocated)),
            next_renewal_at=next_renewal_at,
            fee_paid_usdt=Decimal("0"),
            is_active=True,
        )
        session.add(sub)
        await session.commit()

        return user.id, bot.id, sub.id


# ---------------------------------------------------------------------------
# 4. renewal_check: free bot just extends next_renewal_at
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renewal_check_free_bot_extends_renewal(test_db):
    """
    Free bot (monthly_fee=0). renewal_check should just push next_renewal_at
    forward by 30 days without touching the wallet.
    """
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    user_id, bot_id, sub_id = await _setup_renewal_scenario(
        test_db,
        email="free_renewal@example.com",
        monthly_fee=0.0,
        initial_balance=500.0,
        allocated=100.0,
        next_renewal_at=past,
    )

    # Patch AsyncSessionLocal to use the test DB
    import app.services.bot_eviction as eviction_module
    original = eviction_module.AsyncSessionLocal
    eviction_module.AsyncSessionLocal = test_db
    try:
        await renewal_check()
    finally:
        eviction_module.AsyncSessionLocal = original

    async with test_db() as session:
        sub = await session.get(BotSubscription, sub_id)
        wallet = await _get_wallet(session, user_id)
        assert sub.is_active is True
        # SQLite stores naive datetimes; strip tzinfo for comparison
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        renewal_dt = sub.next_renewal_at.replace(tzinfo=None) if sub.next_renewal_at.tzinfo else sub.next_renewal_at
        assert renewal_dt > now_naive, (
            "next_renewal_at should have been extended into the future"
        )
        # Balance and locked should be untouched
        assert Decimal(str(wallet.balance)) == Decimal("500.00000000")
        assert Decimal(str(wallet.locked_balance)) == Decimal("100.00000000")


# ---------------------------------------------------------------------------
# 5. renewal_check: paid bot sufficient balance → renews, records FeeIncome
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renewal_check_paid_bot_sufficient_balance(test_db):
    """
    Bot charges 20 USDT/month. User has 500 USDT.
    After renewal: balance = 500 - 20 = 480, sub still active,
    next_renewal_at extended, FeeIncome record created.
    """
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    user_id, bot_id, sub_id = await _setup_renewal_scenario(
        test_db,
        email="paid_renewal@example.com",
        monthly_fee=20.0,
        initial_balance=500.0,
        allocated=100.0,
        next_renewal_at=past,
    )

    import app.services.bot_eviction as eviction_module
    original = eviction_module.AsyncSessionLocal
    eviction_module.AsyncSessionLocal = test_db
    try:
        await renewal_check()
    finally:
        eviction_module.AsyncSessionLocal = original

    async with test_db() as session:
        sub = await session.get(BotSubscription, sub_id)
        wallet = await _get_wallet(session, user_id)
        fee_records = list(await session.scalars(
            select(FeeIncome).where(FeeIncome.subscription_id == sub_id)
        ))

        assert sub.is_active is True, "Sub should still be active after successful renewal"
        # SQLite stores naive datetimes; strip tzinfo for comparison
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        renewal_dt = sub.next_renewal_at.replace(tzinfo=None) if sub.next_renewal_at.tzinfo else sub.next_renewal_at
        assert renewal_dt > now_naive, "next_renewal_at should be extended"
        assert Decimal(str(wallet.balance)) == Decimal("480.00000000"), (
            f"Expected 480, got {wallet.balance}"
        )
        assert len(fee_records) == 1, "One FeeIncome record should have been created"
        assert Decimal(str(fee_records[0].amount_usdt)) == Decimal("20.00"), (
            f"FeeIncome amount should be 20, got {fee_records[0].amount_usdt}"
        )
        assert Decimal(str(sub.fee_paid_usdt)) == Decimal("20.00"), (
            f"fee_paid_usdt should be 20, got {sub.fee_paid_usdt}"
        )


# ---------------------------------------------------------------------------
# 6. renewal_check: paid bot insufficient balance → cancels, returns investment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renewal_check_paid_bot_insufficient_balance(test_db):
    """
    Bot charges 50 USDT/month. User has only 10 USDT.
    renewal_check should cancel the subscription and return the 100 USDT
    investment from locked_balance back to balance.
    Final: balance = 10 + 100 = 110, locked = 0, is_active = False.
    """
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    user_id, bot_id, sub_id = await _setup_renewal_scenario(
        test_db,
        email="insuf_renewal@example.com",
        monthly_fee=50.0,
        initial_balance=10.0,
        allocated=100.0,
        next_renewal_at=past,
    )

    import app.services.bot_eviction as eviction_module
    original = eviction_module.AsyncSessionLocal
    eviction_module.AsyncSessionLocal = test_db
    try:
        await renewal_check()
    finally:
        eviction_module.AsyncSessionLocal = original

    async with test_db() as session:
        sub = await session.get(BotSubscription, sub_id)
        wallet = await _get_wallet(session, user_id)
        fee_records = list(await session.scalars(
            select(FeeIncome).where(FeeIncome.subscription_id == sub_id)
        ))

        assert sub.is_active is False, "Sub should be cancelled when balance is insufficient"
        assert sub.ended_at is not None, "ended_at should be set"
        assert Decimal(str(wallet.balance)) == Decimal("110.00000000"), (
            f"Expected 110 (10 + 100 returned), got {wallet.balance}"
        )
        assert Decimal(str(wallet.locked_balance)) == Decimal("0.00000000"), (
            f"Expected locked 0, got {wallet.locked_balance}"
        )
        assert len(fee_records) == 0, "No FeeIncome should be recorded on cancellation"
