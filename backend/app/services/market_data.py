import json
import asyncio
import httpx
from typing import List
from app.config import settings
from app.core.redis import get_redis

PAIR_MAP = {
    "BTC_USDT": "BTCUSDT",
    "ETH_USDT": "ETHUSDT",
    "BNB_USDT": "BNBUSDT",
    "SOL_USDT": "SOLUSDT",
}

async def fetch_ticker(pair: str) -> dict:
    symbol = PAIR_MAP.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.BINANCE_BASE_URL}/api/v3/ticker/24hr", params={"symbol": symbol})
        data = r.json()
    return {
        "pair": pair,
        "last_price": data["lastPrice"],
        "change_pct": data["priceChangePercent"],
        "high": data["highPrice"],
        "low": data["lowPrice"],
        "volume": data["volume"],
    }

async def fetch_orderbook(pair: str, limit: int = 20) -> dict:
    symbol = PAIR_MAP.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.BINANCE_BASE_URL}/api/v3/depth", params={"symbol": symbol, "limit": limit})
        data = r.json()
    return {"pair": pair, "bids": data["bids"], "asks": data["asks"]}

async def fetch_recent_trades(pair: str, limit: int = 50) -> list:
    symbol = PAIR_MAP.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.BINANCE_BASE_URL}/api/v3/trades", params={"symbol": symbol, "limit": limit})
        data = r.json()
    return [{"price": t["price"], "qty": t["qty"], "time": t["time"], "is_buyer_maker": t["isBuyerMaker"]} for t in data]

async def fetch_klines(pair: str, interval: str = "1m", limit: int = 500) -> list:
    symbol = PAIR_MAP.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.BINANCE_BASE_URL}/api/v3/klines",
                             params={"symbol": symbol, "interval": interval, "limit": limit})
        data = r.json()
    return [{"time": k[0] // 1000, "open": k[1], "high": k[2], "low": k[3], "close": k[4], "volume": k[5]} for k in data]

async def sync_market_to_redis(pair: str):
    redis = await get_redis()
    ticker = await fetch_ticker(pair)
    orderbook = await fetch_orderbook(pair)
    trades = await fetch_recent_trades(pair)
    await redis.set(f"market:{pair}:ticker", json.dumps(ticker), ex=30)
    await redis.set(f"market:{pair}:orderbook", json.dumps(orderbook), ex=10)
    await redis.set(f"market:{pair}:trades", json.dumps(trades), ex=10)

async def market_data_loop(pairs: List[str], interval_sec: int = 5):
    while True:
        for pair in pairs:
            try:
                await sync_market_to_redis(pair)
            except Exception as e:
                print(f"Market data error for {pair}: {e}")
        await asyncio.sleep(interval_sec)
