from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.bot import Bot, BotStatus, BotSubscription, BotPerformance
from app.schemas.bot import CreateBotRequest, UpdateBotRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/bots")
async def list_all_bots(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bots = await db.scalars(select(Bot))
    result = []
    for b in bots:
        sub_count = await db.scalar(
            select(func.count(BotSubscription.id)).where(
                BotSubscription.bot_id == b.id,
                BotSubscription.is_active == True,
            )
        )
        period = date.today().strftime("%Y-%m")
        perf = await db.scalar(
            select(BotPerformance).where(
                BotPerformance.bot_id == b.id,
                BotPerformance.period == period,
            )
        )
        result.append({
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "strategy_type": b.strategy_type,
            "strategy_config": b.strategy_config,
            "status": b.status,
            "max_drawdown_limit": float(b.max_drawdown_limit) if b.max_drawdown_limit else 20.0,
            "monthly_fee": float(b.monthly_fee) if b.monthly_fee else 0.0,
            "subscriber_count": sub_count or 0,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "evicted_at": b.evicted_at.isoformat() if b.evicted_at else None,
            "performance": {
                "win_rate": float(perf.win_rate) if perf else 0.0,
                "monthly_return_pct": float(perf.monthly_return_pct) if perf else 0.0,
                "max_drawdown_pct": float(perf.max_drawdown_pct) if perf else 0.0,
                "sharpe_ratio": float(perf.sharpe_ratio) if perf else 0.0,
            } if perf else None,
        })
    return result


@router.post("/bots", status_code=201)
async def create_bot(
    body: CreateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = Bot(**body.model_dump())
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return {"id": bot.id, "name": bot.name}


@router.put("/bots/{bot_id}")
async def update_bot(
    bot_id: int,
    body: UpdateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(bot, k, v)
    await db.commit()
    return {"message": "updated"}


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.bot_eviction import evict_bot
    await evict_bot(db, bot_id, reason="admin_deleted")
    return {"message": "bot evicted"}


@router.post("/bots/{bot_id}/kill")
async def kill_bot(
    bot_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.bot_eviction import evict_bot
    await evict_bot(db, bot_id, reason="manual_kill")
    return {"message": "bot killed"}


@router.put("/users/{user_id}/subscription")
async def toggle_subscription(
    user_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_subscribed = body.get("is_subscribed", False)
    await db.commit()
    return {"message": "subscription updated"}


from app.models.deposit import FeeIncome
from sqlalchemy import update as sql_update


@router.get("/subscriptions")
async def list_subscriptions(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all active bot subscriptions with user info."""
    subs = list(await db.scalars(
        select(BotSubscription)
        .where(BotSubscription.is_active == True)
        .order_by(BotSubscription.started_at.desc())
    ))
    result = []
    for s in subs:
        user = await db.get(User, s.user_id)
        bot = await db.get(Bot, s.bot_id)
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_email": user.email if user else None,
            "user_wallet": user.wallet_address if user else None,
            "bot_id": s.bot_id,
            "bot_name": bot.name if bot else None,
            "allocated_usdt": float(s.allocated_usdt),
            "fee_paid_usdt": float(s.fee_paid_usdt or 0),
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "next_renewal_at": s.next_renewal_at.isoformat() if s.next_renewal_at else None,
        })
    return result


@router.get("/fee-income")
async def fee_income_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Summary of fee income, split by settled/unsettled."""
    all_fees = list(await db.scalars(select(FeeIncome).order_by(FeeIncome.charged_at.desc())))
    unsettled = [f for f in all_fees if f.settled_at is None]
    settled = [f for f in all_fees if f.settled_at is not None]

    def to_dict(f):
        return {
            "id": f.id,
            "user_id": f.user_id,
            "bot_id": f.bot_id,
            "amount_usdt": float(f.amount_usdt),
            "period": f.period,
            "charged_at": f.charged_at.isoformat() if f.charged_at else None,
            "settled_at": f.settled_at.isoformat() if f.settled_at else None,
        }

    return {
        "unsettled_total": sum(float(f.amount_usdt) for f in unsettled),
        "unsettled": [to_dict(f) for f in unsettled],
        "settled_total": sum(float(f.amount_usdt) for f in settled),
        "settled": [to_dict(f) for f in settled[:50]],
    }


@router.post("/fee-income/settle")
async def settle_fee_income(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark all unsettled FeeIncome records as settled."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    result = await db.execute(
        sql_update(FeeIncome)
        .where(FeeIncome.settled_at.is_(None))
        .values(settled_at=now)
    )
    await db.commit()
    return {"message": f"{result.rowcount}건 정산 완료"}


@router.delete("/subscriptions/{sub_id}")
async def force_cancel_subscription(
    sub_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Force-cancel a subscription and return investment to user."""
    from datetime import datetime, timezone
    from app.models.wallet import Wallet
    sub = await db.get(BotSubscription, sub_id)
    if not sub or not sub.is_active:
        raise HTTPException(404, "Subscription not found or already inactive")

    wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == "USDT")
    )
    if wallet and sub.allocated_usdt:
        from decimal import Decimal
        wallet.locked_balance = max(Decimal(0), Decimal(str(wallet.locked_balance or 0)) - Decimal(str(sub.allocated_usdt)))
        wallet.balance = Decimal(str(wallet.balance or 0)) + Decimal(str(sub.allocated_usdt))

    sub.is_active = False
    sub.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "구독이 강제 해지됐습니다."}
