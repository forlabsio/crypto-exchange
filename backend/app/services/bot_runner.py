import asyncio
import json
import time
from decimal import Decimal
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.bot import Bot, BotSubscription, BotStatus
from app.models.order import Order, OrderSide, OrderType
from app.core.redis import get_redis
from app.services.matching_engine import try_fill_order

async def generate_signal(bot: Bot, pair: str):
    redis = await get_redis()
    config = bot.strategy_config or {}
    interval = config.get("signal_interval", 300)

    last_trade_key = f"bot:{bot.id}:last_trade_time"
    last_trade = await redis.get(last_trade_key)

    now = int(time.time())
    if last_trade and now - int(last_trade) < interval:
        return None

    last_side_key = f"bot:{bot.id}:last_side"
    last_side = await redis.get(last_side_key)
    signal = "sell" if last_side == "buy" else "buy"

    await redis.set(last_trade_key, now)
    await redis.set(last_side_key, signal)
    return signal

async def run_bot(bot: Bot):
    config = bot.strategy_config or {}
    pair = config.get("pair", "BTC_USDT")
    trade_pct = config.get("trade_pct", 10)

    signal = await generate_signal(bot, pair)
    if not signal:
        return

    async with AsyncSessionLocal() as db:
        subs = await db.scalars(
            select(BotSubscription).where(
                BotSubscription.bot_id == bot.id,
                BotSubscription.is_active == True,
            )
        )
        sub_list = list(subs)

        for sub in sub_list:
            from app.models.wallet import Wallet
            from sqlalchemy import select as sel

            base, quote = pair.split("_")
            redis = await get_redis()

            if signal == "buy":
                wallet = await db.scalar(sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == quote))
                if not wallet or wallet.balance <= 0:
                    continue
                ticker = await redis.get(f"market:{pair}:ticker")
                if not ticker:
                    continue
                price = Decimal(json.loads(ticker)["last_price"])
                qty_usdt = wallet.balance * Decimal(str(trade_pct / 100))
                quantity = (qty_usdt / price).quantize(Decimal("0.00001"))
            else:
                wallet = await db.scalar(sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base))
                if not wallet or wallet.balance <= 0:
                    continue
                quantity = (wallet.balance * Decimal(str(trade_pct / 100))).quantize(Decimal("0.00001"))

            if quantity <= 0:
                continue

            order = Order(
                user_id=sub.user_id,
                pair=pair,
                side=OrderSide(signal),
                type=OrderType.market,
                quantity=quantity,
                is_bot_order=True,
                bot_id=bot.id,
            )
            db.add(order)
            await db.flush()
            await try_fill_order(db, order)

async def bot_runner_loop():
    while True:
        async with AsyncSessionLocal() as db:
            bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
            bot_list = list(bots)

        kill_redis = await get_redis()
        for bot in bot_list:
            kill_flag = await kill_redis.get(f"bot:{bot.id}:kill_switch")
            if kill_flag:
                continue
            try:
                await run_bot(bot)
            except Exception as e:
                print(f"Bot runner error for bot {bot.id}: {e}")

        await asyncio.sleep(10)
