"""
market_data.py - CoinGecko API Integration
- REST helpers (fetch_ticker, fetch_klines, etc.) for initial page load
- Polling loop for simulated real-time data updates
"""
import json
import asyncio
import httpx
from typing import List, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from app.core.redis import get_redis

# Map internal pairs to CoinGecko IDs
COINGECKO_MAP = {
    "BTC_USDT": "bitcoin",
    "ETH_USDT": "ethereum",
    "BNB_USDT": "binancecoin",
    "SOL_USDT": "solana",
}

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Broadcast callback type: async (pair, payload_dict) -> None
BroadcastCb = Callable[[str, dict], Awaitable[None]]

# In-memory cache to reduce API calls
_ticker_cache: dict = {}
_klines_cache: dict = {}
_cache_duration = 60  # seconds

# ──────────────────────────────────────────────
# REST helpers (used for klines and initial load)
# ──────────────────────────────────────────────

async def fetch_ticker(pair: str) -> dict:
    """Fetch current price and 24h stats from CoinGecko"""
    # Check cache first
    if pair in _ticker_cache:
        cached_data, cached_time = _ticker_cache[pair]
        if (datetime.now().timestamp() - cached_time) < _cache_duration:
            print(f"[CoinGecko] Using cached ticker for {pair}")
            return cached_data

    coin_id = COINGECKO_MAP.get(pair)
    if not coin_id:
        print(f"[ERROR] Unknown pair: {pair}")
        return {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            print(f"[CoinGecko] Fetching ticker for {pair} ({coin_id})")
            r = await client.get(
                f"{COINGECKO_BASE}/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )
            print(f"[CoinGecko] Response status: {r.status_code}")
            data = r.json()
            print(f"[CoinGecko] Got data for {pair}")

        market_data = data.get("market_data", {})
        current_price = market_data.get("current_price", {}).get("usd", 0)
        price_change_24h = market_data.get("price_change_percentage_24h", 0)
        high_24h = market_data.get("high_24h", {}).get("usd", 0)
        low_24h = market_data.get("low_24h", {}).get("usd", 0)
        volume_24h = market_data.get("total_volume", {}).get("usd", 0)

        result = {
            "pair": pair,
            "last_price": str(current_price),
            "change_pct": str(price_change_24h),
            "high": str(high_24h),
            "low": str(low_24h),
            "volume": str(volume_24h),
            "quote_volume": str(volume_24h),
        }

        # Update cache
        _ticker_cache[pair] = (result, datetime.now().timestamp())
        return result
    except Exception as e:
        print(f"[ERROR] fetch_ticker {pair}: {e}")
        # Return cached data if available, even if expired
        if pair in _ticker_cache:
            cached_data, _ = _ticker_cache[pair]
            print(f"[CoinGecko] Returning stale cache for {pair}")
            return cached_data
        return {}

async def fetch_klines(pair: str, interval: str = "1m", limit: int = 500) -> list:
    """
    Fetch OHLC data from CoinGecko
    Note: CoinGecko only provides daily data, so we'll return what we can
    """
    # Check cache first
    cache_key = f"{pair}:{interval}:{limit}"
    if cache_key in _klines_cache:
        cached_data, cached_time = _klines_cache[cache_key]
        if (datetime.now().timestamp() - cached_time) < _cache_duration:
            print(f"[CoinGecko] Using cached klines for {pair}")
            return cached_data

    coin_id = COINGECKO_MAP.get(pair)
    if not coin_id:
        print(f"[ERROR] Unknown pair: {pair}")
        return []

    # Map interval to days (CoinGecko uses days)
    days_map = {
        "1m": 1,
        "5m": 1,
        "15m": 1,
        "1h": 7,
        "4h": 30,
        "1d": 90,
    }
    days = days_map.get(interval, 7)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use market_chart endpoint for price history
            r = await client.get(
                f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": str(days),
                    "interval": "hourly" if days <= 7 else "daily",
                },
            )
            data = r.json()

        prices = data.get("prices", [])

        # Convert to OHLC format (simplified - using price as all values)
        # CoinGecko free API doesn't provide true OHLC, so we approximate
        klines = []
        for i, price_data in enumerate(prices[-limit:]):
            timestamp, price = price_data
            klines.append({
                "time": int(timestamp // 1000),
                "open": float(price),
                "high": float(price * 1.001),  # Approximate
                "low": float(price * 0.999),    # Approximate
                "close": float(price),
                "volume": 1000000.0,  # Placeholder
            })

        # Update cache
        _klines_cache[cache_key] = (klines, datetime.now().timestamp())
        return klines
    except Exception as e:
        print(f"[ERROR] fetch_klines {pair}: {e}")
        # Return cached data if available, even if expired
        if cache_key in _klines_cache:
            cached_data, _ = _klines_cache[cache_key]
            print(f"[CoinGecko] Returning stale cache for {pair} klines")
            return cached_data
        return []

async def sync_market_to_redis(pair: str):
    """One-shot REST fetch for initial cache warm-up."""
    redis = await get_redis()
    ticker = await fetch_ticker(pair)
    if ticker:
        await redis.set(f"market:{pair}:ticker", json.dumps(ticker), ex=60)

# ──────────────────────────────────────────────
# Polling loop for simulated real-time updates
# ──────────────────────────────────────────────

async def _poll_pair(
    pair: str,
    broadcast_cb: BroadcastCb,
    interval_sec: int = 10,
):
    """
    Poll CoinGecko API periodically and broadcast updates
    """
    redis = await get_redis()

    while True:
        try:
            ticker = await fetch_ticker(pair)
            if ticker:
                # Store in Redis
                await redis.set(
                    f"market:{pair}:ticker",
                    json.dumps(ticker),
                    ex=60,
                )

                # Broadcast to connected clients
                await broadcast_cb(pair, {
                    "type": "ticker",
                    "ticker": ticker,
                })

            # Simulate orderbook (placeholder data)
            orderbook = {
                "pair": pair,
                "bids": [[ticker.get("last_price", "0"), "1.0"] for _ in range(20)],
                "asks": [[ticker.get("last_price", "0"), "1.0"] for _ in range(20)],
            }
            await redis.set(
                f"market:{pair}:orderbook",
                json.dumps(orderbook),
                ex=30,
            )
            await broadcast_cb(pair, {
                "type": "orderbook",
                "orderbook": orderbook,
            })

        except Exception as e:
            print(f"[CoinGecko Poll] Error {pair}: {e}")

        await asyncio.sleep(interval_sec)

async def market_data_loop(
    pairs: List[str],
    broadcast_cb: Optional[BroadcastCb] = None,
    interval_sec: int = 10,
):
    """
    Launch polling loops for each pair
    broadcast_cb is called for every update
    """
    if broadcast_cb is None:
        # No-op fallback (stores to Redis only)
        async def _noop(pair: str, data: dict):
            pass
        broadcast_cb = _noop

    # Initial REST warm-up
    for pair in pairs:
        try:
            await sync_market_to_redis(pair)
        except Exception as e:
            print(f"[Warm-up] {pair}: {e}")

    # Run all pair polling loops concurrently
    await asyncio.gather(*[_poll_pair(pair, broadcast_cb, interval_sec) for pair in pairs])
