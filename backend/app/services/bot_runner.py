import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.bot import Bot, BotSubscription, BotStatus
from app.models.order import Order, OrderSide, OrderType
from app.core.redis import get_redis
from app.services.matching_engine import try_fill_order
from app.services.indicators import calc_rsi, calc_ma, calc_bollinger
from app.services.market_data import fetch_klines
from app.services.binance_trade import place_market_order
from app.config import settings

logger = logging.getLogger(__name__)


async def _execute_real_trade(bot_name: str, bot_id: int, signal: str, total_usdt: float, pair: str):
    """Execute a real Binance market order aggregated across all subscribers."""
    symbol = pair.replace("_", "")  # BTC_USDT -> BTCUSDT
    try:
        if signal.lower() == "buy":
            result = await place_market_order(symbol, "BUY", total_usdt, use_quote=True)
        else:
            # For SELL: we need coin quantity. Skip real SELL if we can't determine it safely.
            # Log the skip for now — real SELL requires knowing the held coin position.
            logger.info(
                "[Binance] %s SELL signal for %s — skipping real order (coin qty unknown)",
                bot_name, symbol,
            )
            return None
        fills = result.get("fills", [])
        if fills:
            total_qty = sum(float(f.get("qty", 0)) for f in fills)
            vwap = (
                sum(float(f.get("price", 0)) * float(f.get("qty", 0)) for f in fills) / total_qty
                if total_qty > 0 else 0
            )
        else:
            vwap = 0
        logger.info(
            "[Binance] %s BUY %s USDT=%.2f vwap=%.4f",
            bot_name, symbol, total_usdt, vwap,
        )
        return result
    except Exception as e:
        logger.error("[Binance] Real trade error bot %s: %s", bot_id, e)
        return None

async def generate_signal(bot: Bot, pair: str) -> Optional[str]:
    redis = await get_redis()
    config = bot.strategy_config or {}
    interval = config.get("signal_interval", 300)

    last_trade_key = f"bot:{bot.id}:last_trade_time"
    last_trade = await redis.get(last_trade_key)
    now = int(time.time())
    if last_trade and now - int(last_trade) < interval:
        return None

    strategy = bot.strategy_type or "alternating"
    signal: Optional[str] = None

    if strategy == "alternating":
        last_side_key = f"bot:{bot.id}:last_side"
        last_side = await redis.get(last_side_key)
        signal = "sell" if last_side == "buy" else "buy"
        await redis.set(last_side_key, signal)

    elif strategy == "rsi":
        period = int(config.get("rsi_period", 14))
        oversold = float(config.get("oversold", 30))
        overbought = float(config.get("overbought", 70))
        try:
            klines = await fetch_klines(pair, "1h", period + 5)
            closes = [float(k["close"]) for k in klines]
            rsi = calc_rsi(closes, period)
            if rsi < oversold:
                signal = "buy"
            elif rsi > overbought:
                signal = "sell"
        except Exception as e:
            logger.error("RSI signal error bot %s: %s", bot.id, e)

    elif strategy == "ma_cross":
        fast = int(config.get("fast_period", 5))
        slow = int(config.get("slow_period", 20))
        if fast >= slow:
            logger.warning(
                "MA cross bot %s: fast_period (%s) must be < slow_period (%s), skipping",
                bot.id, fast, slow,
            )
            return None
        try:
            klines = await fetch_klines(pair, "1h", slow + 5)
            closes = [float(k["close"]) for k in klines]
            if len(closes) < slow + 1:
                return None
            fast_ma = calc_ma(closes, fast)
            slow_ma = calc_ma(closes, slow)
            prev_fast = calc_ma(closes[:-1], fast)
            prev_slow = calc_ma(closes[:-1], slow)
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                signal = "buy"   # golden cross
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                signal = "sell"  # death cross
        except Exception as e:
            logger.error("MA cross signal error bot %s: %s", bot.id, e)

    elif strategy == "boll":
        period = int(config.get("period", 20))
        std_dev = float(config.get("deviation", 2.0))
        try:
            klines = await fetch_klines(pair, "1h", period + 5)
            closes = [float(k["close"]) for k in klines]
            lower, upper = calc_bollinger(closes, period, std_dev)
            current = closes[-1]
            if current <= lower:
                signal = "buy"
            elif current >= upper:
                signal = "sell"
        except Exception as e:
            logger.error("Bollinger signal error bot %s: %s", bot.id, e)

    # Only update the cooldown timer when a real signal was produced.
    # `alternating` always produces a signal; indicator strategies may return None on neutral markets.
    if signal:
        await redis.set(last_trade_key, now)
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
            allocated = Decimal(str(sub.allocated_usdt or 100))

            # Estimate how much USDT the bot has already deployed for this user
            # by summing buy costs and subtracting sell proceeds from filled bot orders
            bot_orders_result = await db.scalars(
                sel(Order).where(
                    Order.user_id == sub.user_id,
                    Order.bot_id == bot.id,
                    Order.status == "filled",
                )
            )
            deployed = Decimal("0")
            for o in bot_orders_result:
                price_val = Decimal(str(o.price or 0))
                qty_val = Decimal(str(o.filled_quantity or 0))
                if o.side == "buy":
                    deployed += qty_val * price_val
                else:
                    deployed -= qty_val * price_val

            redis = await get_redis()
            ticker = await redis.get(f"market:{pair}:ticker")
            if not ticker:
                continue
            price = Decimal(json.loads(ticker)["last_price"])

            if signal == "buy":
                available = allocated - deployed
                if available <= Decimal("0"):
                    continue  # allocation fully deployed
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == quote)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                spend = min(
                    wallet.balance * Decimal(str(trade_pct / 100)),
                    available,
                )
                quantity = (spend / price).quantize(Decimal("0.00001"))
            else:  # sell
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                quantity = (wallet.balance * Decimal(str(trade_pct / 100))).quantize(
                    Decimal("0.00001")
                )

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

        # Execute one real Binance order sized to the total allocation across all subscribers
        total_investment = sum(float(s.allocated_usdt or 0) for s in sub_list)
        if total_investment > 0 and settings.BINANCE_LIVE_TRADING:
            await _execute_real_trade(bot.name, bot.id, signal, total_investment, pair)

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
                logger.error("Bot runner error for bot %s: %s", bot.id, e)

        await asyncio.sleep(10)
