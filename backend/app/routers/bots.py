from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models.user import User
from app.models.bot import Bot, BotSubscription, BotStatus, BotPerformance
from app.models.order import Order


class SubscribeRequest(BaseModel):
    allocated_usdt: float = 100.0


router = APIRouter(prefix="/api/bots", tags=["bots"])


def _perf_dict(perf) -> dict:
    if not perf:
        return {"win_rate": 0.0, "monthly_return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0}
    return {
        "win_rate": float(perf.win_rate) if perf.win_rate is not None else 0.0,
        "monthly_return_pct": float(perf.monthly_return_pct) if perf.monthly_return_pct is not None else 0.0,
        "max_drawdown_pct": float(perf.max_drawdown_pct) if perf.max_drawdown_pct is not None else 0.0,
        "sharpe_ratio": float(perf.sharpe_ratio) if perf.sharpe_ratio is not None else 0.0,
    }


async def _bot_dict(db: AsyncSession, bot: Bot, user: Optional[User] = None) -> dict:
    period = date.today().strftime("%Y-%m")
    perf = await db.scalar(
        select(BotPerformance).where(
            BotPerformance.bot_id == bot.id,
            BotPerformance.period == period,
        )
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
        result.append(d)
    return result


@router.get("/{bot_id}/trades")
async def bot_trades(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orders = await db.scalars(
        select(Order).where(
            Order.bot_id == bot_id,
            Order.user_id == user.id,
        ).order_by(Order.created_at.desc()).limit(50)
    )
    return [
        {
            "id": o.id,
            "pair": o.pair,
            "side": o.side,
            "type": o.type,
            "quantity": float(o.quantity),
            "price": float(o.price) if o.price else None,
            "filled_quantity": float(o.filled_quantity) if o.filled_quantity else 0.0,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.post("/{bot_id}/subscribe")
async def subscribe_bot(
    bot_id: int,
    body: SubscribeRequest = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body is None:
        body = SubscribeRequest()
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status != BotStatus.active:
        raise HTTPException(404, "Bot not found")
    existing = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if existing:
        raise HTTPException(400, "Already subscribed")
    db.add(BotSubscription(user_id=user.id, bot_id=bot_id, allocated_usdt=body.allocated_usdt))
    await db.commit()
    return {"message": "subscribed"}


@router.delete("/{bot_id}/subscribe")
async def unsubscribe_bot(
    bot_id: int,
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
    sub.is_active = False
    sub.ended_at = datetime.utcnow()
    await db.commit()
    return {"message": "unsubscribed"}
