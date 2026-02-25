from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from statistics import mean
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.bot import Bot, BotSubscription, BotPerformance, BotStatus
from app.models.order import Order, OrderStatus
from app.models.notification import Notification
from app.models.wallet import Wallet
from app.models.deposit import FeeIncome
from app.core.redis import get_redis
from app.services.stats import calc_bot_stats

def should_evict_bot(performance, max_drawdown_limit: float) -> bool:
    if float(performance.win_rate) < 70.0:
        return True
    if float(performance.monthly_return_pct) < 0:
        return True
    if float(performance.max_drawdown_pct) > max_drawdown_limit:
        return True
    return False

async def evict_bot(db: AsyncSession, bot_id: int, reason: str = "performance"):
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status == BotStatus.evicted:
        return

    redis = await get_redis()
    await redis.set(f"bot:{bot_id}:kill_switch", "1")

    open_orders = await db.scalars(
        select(Order).where(Order.bot_id == bot_id, Order.status == OrderStatus.open)
    )
    for order in open_orders:
        order.status = OrderStatus.cancelled

    subs = await db.scalars(
        select(BotSubscription).where(BotSubscription.bot_id == bot_id, BotSubscription.is_active == True)
    )
    for sub in subs:
        sub.is_active = False
        sub.ended_at = datetime.now(timezone.utc)
        db.add(Notification(
            user_id=sub.user_id,
            type="bot_evicted",
            title=f"봇 '{bot.name}' 이 퇴출되었습니다",
            body=f"사유: {reason}. 해당 봇의 연동이 자동 해제되었습니다.",
        ))

    bot.status = BotStatus.evicted
    bot.evicted_at = datetime.now(timezone.utc)
    await db.commit()

async def monthly_evaluation():
    period = date.today().strftime("%Y-%m")
    async with AsyncSessionLocal() as db:
        bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
        for bot in bots:
            perf = await db.scalar(
                select(BotPerformance).where(
                    BotPerformance.bot_id == bot.id,
                    BotPerformance.period == period,
                )
            )
            if not perf:
                continue
            if should_evict_bot(perf, float(bot.max_drawdown_limit)):
                await evict_bot(db, bot.id, reason=f"월간 성과 미달 ({period})")

async def daily_drawdown_check():
    async with AsyncSessionLocal() as db:
        bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
        for bot in bots:
            redis = await get_redis()
            mdd_str = await redis.get(f"bot:{bot.id}:daily_mdd")
            if mdd_str and float(mdd_str) > 15.0:
                await evict_bot(db, bot.id, reason="일중 MDD 15% 초과")


async def daily_performance_update():
    """Run at 00:05 daily. Aggregate all active subscribers' trade stats for each bot
    and upsert into BotPerformance. This is what the bot market cards display."""
    yesterday = date.today() - timedelta(days=1)
    period = yesterday.strftime("%Y-%m")
    # cutoff = midnight of today (= end of yesterday)
    cutoff = datetime.combine(date.today(), datetime.min.time())

    async with AsyncSessionLocal() as db:
        bots = list(await db.scalars(select(Bot).where(Bot.status == BotStatus.active)))
        for bot in bots:
            subs = list(await db.scalars(
                select(BotSubscription).where(
                    BotSubscription.bot_id == bot.id,
                    BotSubscription.is_active == True,
                )
            ))
            if not subs:
                continue

            config = bot.strategy_config or {}
            pair = config.get("pair", "BTC_USDT")

            pnl_pcts, win_rates, mdds, sharpes = [], [], [], []
            total_trades = 0

            for sub in subs:
                allocated = Decimal(str(sub.allocated_usdt or 100))
                stats = await calc_bot_stats(
                    db=db,
                    user_id=sub.user_id,
                    bot_id=bot.id,
                    allocated=allocated,
                    pair=pair,
                    cutoff=cutoff,
                )
                if stats["trade_count"] > 0:
                    pnl_pcts.append(stats["pnl_pct"])
                    win_rates.append(stats["win_rate"])
                    mdds.append(stats["max_drawdown_pct"])
                    sharpes.append(stats["sharpe_ratio"])
                    total_trades += stats["trade_count"]

            if not pnl_pcts:
                continue

            perf = await db.scalar(
                select(BotPerformance).where(
                    BotPerformance.bot_id == bot.id,
                    BotPerformance.period == period,
                )
            )
            if not perf:
                perf = BotPerformance(bot_id=bot.id, period=period)
                db.add(perf)

            perf.win_rate = mean(win_rates)
            perf.monthly_return_pct = mean(pnl_pcts)
            perf.max_drawdown_pct = mean(mdds)
            perf.sharpe_ratio = mean(sharpes)
            perf.total_trades = total_trades
            perf.calculated_at = datetime.now(timezone.utc)

        await db.commit()


async def renewal_check():
    """
    Run every hour. Find subscriptions where next_renewal_at <= now.
    If user has enough balance: renew and extend 30 days.
    If not: cancel subscription and return investment.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        subs = list(await db.scalars(
            select(BotSubscription).where(
                BotSubscription.is_active == True,
                BotSubscription.next_renewal_at <= now,
                BotSubscription.next_renewal_at.isnot(None),
            )
        ))
        for sub in subs:
            bot = await db.get(Bot, sub.bot_id)
            if not bot:
                continue
            monthly_fee = Decimal(str(bot.monthly_fee or 0))
            if monthly_fee <= 0:
                # Free bot — just extend
                sub.next_renewal_at = now + timedelta(days=30)
                continue

            wallet = await db.scalar(
                select(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == "USDT")
            )
            balance = Decimal(str(wallet.balance or 0)) if wallet else Decimal(0)

            if balance >= monthly_fee:
                # Renew
                wallet.balance = Decimal(str(wallet.balance)) - monthly_fee
                sub.next_renewal_at = now + timedelta(days=30)
                sub.fee_paid_usdt = Decimal(str(sub.fee_paid_usdt or 0)) + monthly_fee
                period = now.strftime("%Y-%m")
                db.add(FeeIncome(
                    user_id=sub.user_id, bot_id=sub.bot_id,
                    subscription_id=sub.id, amount_usdt=monthly_fee, period=period,
                ))
                print(f"[Renewal] sub {sub.id} renewed. Fee: {monthly_fee}")
            else:
                # Cancel — return investment
                if wallet and sub.allocated_usdt:
                    wallet.locked_balance = max(Decimal(0), Decimal(str(wallet.locked_balance or 0)) - Decimal(str(sub.allocated_usdt)))
                    wallet.balance = Decimal(str(wallet.balance)) + Decimal(str(sub.allocated_usdt))
                sub.is_active = False
                sub.ended_at = now
                print(f"[Renewal] sub {sub.id} cancelled (insufficient balance)")

        await db.commit()
