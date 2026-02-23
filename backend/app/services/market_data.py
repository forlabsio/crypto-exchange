"""
market_data.py
- REST helpers (fetch_ticker, fetch_klines, etc.) for initial page load
- BinanceStreamManager: connects to Binance WebSocket streams for real-time data,
  stores each update in Redis AND broadcasts to all connected browser clients
"""
import json
import asyncio
import httpx
import websockets
from typing import List, Optional, Callable, Awaitable
from app.config import settings
from app.core.redis import get_redis

PAIR_MAP = {
    "BTC_USDT": "btcusdt",
    "ETH_USDT": "ethusdt",
    "BNB_USDT": "bnbusdt",
    "SOL_USDT": "solusdt",
}

PAIR_MAP_UPPER = {
    "BTC_USDT": "BTCUSDT",
    "ETH_USDT": "ETHUSDT",
    "BNB_USDT": "BNBUSDT",
    "SOL_USDT": "SOLUSDT",
}

BINANCE_WS_BASE = "wss://stream.binance.com:9443"

# ──────────────────────────────────────────────
# REST helpers (used for klines and initial load)
# ──────────────────────────────────────────────

async def fetch_ticker(pair: str) -> dict:
    symbol = PAIR_MAP_UPPER.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{settings.BINANCE_BASE_URL}/api/v3/ticker/24hr",
            params={"symbol": symbol},
        )
        data = r.json()
    return {
        "pair": pair,
        "last_price": data["lastPrice"],
        "change_pct": data["priceChangePercent"],
        "high": data["highPrice"],
        "low": data["lowPrice"],
        "volume": data["volume"],
    }

async def fetch_klines(pair: str, interval: str = "1m", limit: int = 500) -> list:
    symbol = PAIR_MAP_UPPER.get(pair, pair.replace("_", ""))
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{settings.BINANCE_BASE_URL}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        data = r.json()
    return [
        {
            "time": k[0] // 1000,
            "open": k[1],
            "high": k[2],
            "low": k[3],
            "close": k[4],
            "volume": k[5],
        }
        for k in data
    ]

async def sync_market_to_redis(pair: str):
    """One-shot REST fetch for initial cache warm-up."""
    redis = await get_redis()
    ticker = await fetch_ticker(pair)
    await redis.set(f"market:{pair}:ticker", json.dumps(ticker), ex=60)


# ──────────────────────────────────────────────
# Binance WebSocket Stream Manager
# ──────────────────────────────────────────────

# Broadcast callback type: async (pair, payload_dict) -> None
BroadcastCb = Callable[[str, dict], Awaitable[None]]


async def _stream_pair(
    pair: str,
    broadcast_cb: BroadcastCb,
    retry_delay: float = 3.0,
):
    """
    Subscribe to Binance combined stream for one pair:
      - @miniTicker  → ticker (price, 24h stats)
      - @depth20@100ms → orderbook top-20 (updated every 100ms)
      - @trade        → individual trades

    On each message:
      1. Update Redis
      2. Call broadcast_cb to push to connected browser clients
    """
    sym = PAIR_MAP.get(pair, pair.lower().replace("_", ""))
    stream = f"{sym}@miniTicker/{sym}@depth20@100ms/{sym}@trade"
    url = f"{BINANCE_WS_BASE}/stream?streams={stream}"

    redis = await get_redis()

    # Cached snapshots (rebuilt incrementally)
    ticker_cache: dict = {}
    orderbook_cache: dict = {"bids": [], "asks": []}
    trades_cache: list = []

    while True:
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                print(f"[Binance WS] Connected: {stream}")
                async for raw in ws:
                    try:
                        envelope = json.loads(raw)
                        data = envelope.get("data", {})
                        stream_name = envelope.get("stream", "")

                        if "@miniTicker" in stream_name:
                            ticker_cache = {
                                "pair": pair,
                                "last_price": data["c"],
                                "change_pct": data["P"],
                                "high": data["h"],
                                "low": data["l"],
                                "volume": data["v"],
                            }
                            await redis.set(
                                f"market:{pair}:ticker",
                                json.dumps(ticker_cache),
                                ex=60,
                            )
                            # Push ticker update to clients
                            await broadcast_cb(pair, {
                                "type": "ticker",
                                "ticker": ticker_cache,
                            })

                        elif "@depth20" in stream_name:
                            orderbook_cache = {
                                "pair": pair,
                                "bids": data.get("bids", []),
                                "asks": data.get("asks", []),
                            }
                            await redis.set(
                                f"market:{pair}:orderbook",
                                json.dumps(orderbook_cache),
                                ex=30,
                            )
                            # Push orderbook update to clients
                            await broadcast_cb(pair, {
                                "type": "orderbook",
                                "orderbook": orderbook_cache,
                            })

                        elif "@trade" in stream_name:
                            trade = {
                                "price": data["p"],
                                "qty": data["q"],
                                "time": data["T"],
                                "is_buyer_maker": data["m"],
                            }
                            trades_cache.insert(0, trade)
                            trades_cache = trades_cache[:50]
                            await redis.set(
                                f"market:{pair}:trades",
                                json.dumps(trades_cache),
                                ex=30,
                            )
                            # Push trade to clients
                            await broadcast_cb(pair, {
                                "type": "trade",
                                "trade": trade,
                            })

                    except Exception as parse_err:
                        print(f"[Binance WS] Parse error {pair}: {parse_err}")

        except Exception as conn_err:
            print(f"[Binance WS] Connection error {pair}: {conn_err}. Retrying in {retry_delay}s…")
            await asyncio.sleep(retry_delay)


async def market_data_loop(
    pairs: List[str],
    broadcast_cb: Optional[BroadcastCb] = None,
    interval_sec: int = 5,  # kept for compat, unused
):
    """
    Launch one Binance WS stream per pair concurrently.
    broadcast_cb is called for every real-time update.
    """
    if broadcast_cb is None:
        # No-op fallback (stores to Redis only)
        async def _noop(pair: str, data: dict):
            pass
        broadcast_cb = _noop

    # Initial REST warm-up so Redis has data before first WS message
    for pair in pairs:
        try:
            await sync_market_to_redis(pair)
        except Exception as e:
            print(f"[Warm-up] {pair}: {e}")

    # Run all pair streams concurrently
    await asyncio.gather(*[_stream_pair(pair, broadcast_cb) for pair in pairs])
