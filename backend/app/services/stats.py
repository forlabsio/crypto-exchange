"""Shared bot statistics calculation used by both the API and the daily aggregation job."""
import json
from datetime import datetime
from decimal import Decimal
from statistics import mean, stdev as _stdev
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.order import Order, Trade
from app.core.redis import get_redis


async def calc_bot_stats(
    db: AsyncSession,
    user_id: int,
    bot_id: int,
    allocated: Decimal,
    pair: str,
    cutoff: Optional[datetime] = None,
) -> dict:
    """Calculate P&L, win rate, MDD, Sharpe for one user-bot subscription.

    Args:
        cutoff: If set, only consider orders created strictly before this datetime.
                Used by the daily aggregation job to snapshot yesterday's data.
    """
    query = (
        select(Order)
        .where(
            Order.user_id == user_id,
            Order.bot_id == bot_id,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
    )
    if cutoff:
        query = query.where(Order.created_at < cutoff)

    orders = list(await db.scalars(query))

    buy_cost = Decimal("0")
    sell_proceeds = Decimal("0")
    buy_qty_total = Decimal("0")
    net_qty = Decimal("0")
    running_usdt = allocated
    running_base = Decimal("0")
    wins = 0
    total_sells = 0
    trade_returns: list[float] = []
    portfolio_history: list[float] = []

    for o in orders:
        trade = await db.scalar(select(Trade).where(Trade.order_id == o.id))
        fill_price = Decimal(str(trade.price)) if trade else Decimal(str(o.price or 0))
        if fill_price == 0:
            continue
        qty = Decimal(str(o.filled_quantity or 0))

        if o.side == "buy":
            buy_cost += qty * fill_price
            buy_qty_total += qty
            net_qty += qty
            running_usdt -= qty * fill_price
            running_base += qty
        else:
            avg_cost = buy_cost / buy_qty_total if buy_qty_total > 0 else Decimal("0")
            sell_proceeds += qty * fill_price
            net_qty -= qty
            running_usdt += qty * fill_price
            running_base = max(running_base - qty, Decimal("0"))
            total_sells += 1
            if fill_price > avg_cost:
                wins += 1
            if avg_cost > 0:
                trade_returns.append(float((fill_price - avg_cost) / avg_cost * 100))

        portfolio_history.append(float(running_usdt + running_base * fill_price))

    net_qty = max(net_qty, Decimal("0"))

    # Current price for unrealized P&L (skip if cutoff snapshot)
    current_price = Decimal("0")
    if cutoff is None:
        try:
            redis = await get_redis()
            ticker = await redis.get(f"market:{pair}:ticker")
            if ticker:
                current_price = Decimal(json.loads(ticker)["last_price"])
        except Exception:
            pass

    unrealized = net_qty * current_price
    pnl = sell_proceeds + unrealized - buy_cost
    pnl_pct = float(pnl / allocated * 100) if allocated > 0 else 0.0
    win_rate = float(wins / total_sells * 100) if total_sells > 0 else 0.0

    max_dd = 0.0
    if portfolio_history:
        peak = portfolio_history[0]
        for val in portfolio_history:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak * 100
                if dd > max_dd:
                    max_dd = dd

    sharpe = 0.0
    if len(trade_returns) >= 2:
        avg_r = mean(trade_returns)
        std_r = _stdev(trade_returns)
        sharpe = avg_r / std_r if std_r > 0 else 0.0

    return {
        "pnl_usdt": float(pnl),
        "pnl_pct": pnl_pct,
        "win_rate": win_rate,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "trade_count": len(orders),
    }
