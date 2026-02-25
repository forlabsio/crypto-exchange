from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models.user import User
from app.models.bot import Bot, BotSubscription, BotStatus, BotPerformance
from app.models.order import Order, Trade
from app.models.wallet import Wallet
from app.models.deposit import FeeIncome
from app.services.stats import calc_bot_stats


class SubscribeRequest(BaseModel):
    allocated_usdt: float = Field(default=100.0, gt=0)


router = APIRouter(prefix="/api/bots", tags=["bots"])


def _perf_dict(perf) -> dict:
    if not perf:
        return {
            "win_rate": 0.0, "monthly_return_pct": 0.0,
            "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0,
            "calculated_at": None,
        }
    return {
        "win_rate": float(perf.win_rate) if perf.win_rate is not None else 0.0,
        "monthly_return_pct": float(perf.monthly_return_pct) if perf.monthly_return_pct is not None else 0.0,
        "max_drawdown_pct": float(perf.max_drawdown_pct) if perf.max_drawdown_pct is not None else 0.0,
        "sharpe_ratio": float(perf.sharpe_ratio) if perf.sharpe_ratio is not None else 0.0,
        "calculated_at": perf.calculated_at.isoformat() if perf.calculated_at else None,
    }


async def _bot_dict(db: AsyncSession, bot: Bot, user: Optional[User] = None) -> dict:
    # Bot market shows the most recently aggregated performance (set by daily_performance_update)
    perf = await db.scalar(
        select(BotPerformance)
        .where(BotPerformance.bot_id == bot.id)
        .order_by(desc(BotPerformance.calculated_at))
        .limit(1)
    )
    sub_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(
            BotSubscription.bot_id == bot.id,
            BotSubscription.is_active == True,
        )
    )
    is_subscribed = False
    if user:
        existing = await db.scalar(
            select(BotSubscription).where(
                BotSubscription.user_id == user.id,
                BotSubscription.bot_id == bot.id,
                BotSubscription.is_active == True,
            )
        )
        is_subscribed = existing is not None

    operation_days = 0
    if bot.created_at:
        delta = datetime.utcnow() - bot.created_at.replace(tzinfo=None)
        operation_days = delta.days

    return {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "strategy_type": bot.strategy_type or "alternating",
        "status": bot.status,
        "monthly_fee": float(bot.monthly_fee) if bot.monthly_fee is not None else 0.0,
        "subscriber_count": sub_count or 0,
        "operation_days": operation_days,
        "performance": _perf_dict(perf),
        "is_subscribed": is_subscribed,
    }


@router.get("")
async def list_bots(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
    return [await _bot_dict(db, b, user) for b in bots]


@router.get("/my")
async def my_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subs = await db.scalars(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.is_active == True,
        )
    )
    result = []
    for sub in subs:
        bot = await db.get(Bot, sub.bot_id)
        if not bot:
            continue
        d = await _bot_dict(db, bot, user)
        d["subscribed_at"] = sub.started_at.isoformat() if sub.started_at else None
        d["allocated_usdt"] = float(sub.allocated_usdt) if sub.allocated_usdt is not None else 100.0
        config = bot.strategy_config or {}
        pair = config.get("pair", "BTC_USDT")
        allocated = Decimal(str(sub.allocated_usdt or 100))
        live = await calc_bot_stats(db, user.id, bot.id, allocated, pair)
        d["pnl_usdt"] = live["pnl_usdt"]
        d["performance"]["monthly_return_pct"] = live["pnl_pct"]
        if live["trade_count"] > 0:
            d["performance"]["win_rate"] = live["win_rate"]
            d["performance"]["max_drawdown_pct"] = live["max_drawdown_pct"]
            if live["sharpe_ratio"] != 0.0:
                d["performance"]["sharpe_ratio"] = live["sharpe_ratio"]
        result.append(d)
    return result


@router.get("/{bot_id}/position")
async def bot_position(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    config = bot.strategy_config or {}
    pair = config.get("pair", "BTC_USDT")
    base = pair.split("_")[0]

    orders = await db.scalars(
        select(Order).where(
            Order.user_id == user.id,
            Order.bot_id == bot_id,
            Order.status == "filled",
        )
    )
    net_qty = Decimal("0")
    for o in orders:
        qty = Decimal(str(o.filled_quantity or 0))
        if o.side == "buy":
            net_qty += qty
        else:
            net_qty -= qty
    net_qty = max(net_qty, Decimal("0"))

    redis = await get_redis()
    price_usdt = 0.0
    ticker = await redis.get(f"market:{pair}:ticker")
    if ticker:
        price_usdt = float(json.loads(ticker)["last_price"])

    return {
        "pair": pair,
        "base": base,
        "net_qty": float(net_qty),
        "price_usdt": price_usdt,
        "value_usdt": float(net_qty) * price_usdt,
    }


@router.get("/{bot_id}/trades")
async def bot_trades(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orders = list(await db.scalars(
        select(Order).where(
            Order.bot_id == bot_id,
            Order.user_id == user.id,
        ).order_by(Order.created_at.desc()).limit(50)
    ))
    result = []
    for o in orders:
        trade = await db.scalar(select(Trade).where(Trade.order_id == o.id))
        fill_price = float(trade.price) if trade else (float(o.price) if o.price else None)
        result.append({
            "id": o.id,
            "pair": o.pair,
            "side": o.side,
            "type": o.type,
            "quantity": float(o.quantity),
            "price": fill_price,
            "filled_quantity": float(o.filled_quantity) if o.filled_quantity else 0.0,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return result


@router.post("/{bot_id}/subscribe", status_code=201)
async def subscribe_bot(
    bot_id: int,
    body: SubscribeRequest = SubscribeRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status != BotStatus.active:
        raise HTTPException(404, "Bot not found or inactive")

    existing = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if existing:
        raise HTTPException(409, "Already subscribed")

    monthly_fee = Decimal(str(bot.monthly_fee or 0))
    allocated = Decimal(str(body.allocated_usdt))

    # Get user's USDT wallet with row-level lock to prevent double-spend
    wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT").with_for_update()
    )
    if wallet is None:
        raise HTTPException(400, "USDT 지갑이 없습니다. 먼저 지갑을 생성해주세요.")
    balance = Decimal(str(wallet.balance or 0))

    # Priority: subscription fee first, then investment
    required = monthly_fee + allocated
    if balance < required:
        raise HTTPException(
            400,
            f"잔액 부족: {float(balance):.2f} USDT. 필요: {float(required):.2f} USDT "
            f"(구독료 {float(monthly_fee):.2f} + 투자금 {float(allocated):.2f})"
        )

    now = datetime.now(timezone.utc)

    # Deduct monthly fee immediately
    if monthly_fee > 0:
        wallet.balance = Decimal(str(wallet.balance or 0)) - monthly_fee

    # Lock investment amount
    wallet.balance = Decimal(str(wallet.balance or 0)) - allocated
    wallet.locked_balance = Decimal(str(wallet.locked_balance or 0)) + allocated

    # Create subscription
    sub = BotSubscription(
        user_id=user.id,
        bot_id=bot_id,
        allocated_usdt=allocated,
        next_renewal_at=now + timedelta(days=30),
        fee_paid_usdt=monthly_fee,
    )
    db.add(sub)
    await db.flush()

    # Record fee income
    if monthly_fee > 0:
        period = now.strftime("%Y-%m")
        fee_record = FeeIncome(
            user_id=user.id,
            bot_id=bot_id,
            subscription_id=sub.id,
            amount_usdt=monthly_fee,
            period=period,
        )
        db.add(fee_record)

    await db.commit()
    return {"message": "구독이 완료됐습니다.", "next_renewal_at": sub.next_renewal_at.isoformat()}


@router.delete("/{bot_id}/subscribe")
async def unsubscribe_bot(
    bot_id: int,
    settle: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if settle:
        bot = await db.get(Bot, bot_id)
        config = (bot.strategy_config or {}) if bot else {}
        pair = config.get("pair", "BTC_USDT")

        orders = await db.scalars(
            select(Order).where(
                Order.user_id == user.id,
                Order.bot_id == bot_id,
                Order.status == "filled",
            )
        )
        net_qty = Decimal("0")
        for o in orders:
            qty = Decimal(str(o.filled_quantity or 0))
            if o.side == "buy":
                net_qty += qty
            else:
                net_qty -= qty
        net_qty = max(net_qty, Decimal("0")).quantize(Decimal("0.00001"))

        if net_qty > 0:
            from app.services.matching_engine import try_fill_order
            sell_order = Order(
                user_id=user.id,
                pair=pair,
                side=OrderSide.sell,
                type=OrderType.market,
                quantity=net_qty,
                is_bot_order=True,
                bot_id=bot_id,
            )
            db.add(sell_order)
            await db.flush()
            await try_fill_order(db, sell_order)
            # try_fill_order commits the transaction; start fresh for sub update
            await db.refresh(sub)

    # Return locked investment to available balance
    wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    if wallet and sub.allocated_usdt:
        wallet.locked_balance = max(Decimal(0), Decimal(str(wallet.locked_balance or 0)) - Decimal(str(sub.allocated_usdt)))
        wallet.balance = Decimal(str(wallet.balance or 0)) + Decimal(str(sub.allocated_usdt))

    sub.is_active = False
    sub.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "구독이 해지됐습니다."}
