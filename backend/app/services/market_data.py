"""
market_data.py - Binance API Integration
- REST helpers (fetch_ticker, fetch_klines) via Binance public endpoints
- WebSocket loop for real-time price streaming
"""
import json
import asyncio
import httpx
from typing import List, Optional, Callable, Awaitable
from datetime import datetime
from app.core.redis import get_redis

BINANCE_REST = "https://api.binance.com/api/v3"
BINANCE_WS   = "wss://stream.binance.com:9443/ws"

# Broadcast callback type: async (pair, payload_dict) -> None
BroadcastCb = Callable[[str, dict], Awaitable[None]]

# ── simple in-memory cache ──────────────────────────────────────────────────
_ticker_cache: dict = {}
_klines_cache: dict = {}
_TICKER_TTL  = 10   # seconds
_KLINES_TTL  = 30   # seconds


def _pair_to_symbol(pair: str) -> str:
    """BTC_USDT -> BTCUSDT"""
    return pair.replace("_", "")


# ── REST helpers ──────────────────────────────────────────────────────────────

async def fetch_ticker(pair: str) -> dict:
    """Fetch 24h ticker from Binance."""
    now = datetime.now().timestamp()
    if pair in _ticker_cache:
        data, ts = _ticker_cache[pair]
        if now - ts < _TICKER_TTL:
            return data

    symbol = _pair_to_symbol(pair)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{BINANCE_REST}/ticker/24hr", params={"symbol": symbol})
            r.raise_for_status()
            d = r.json()

        result = {
            "pair": pair,
            "last_price": d["lastPrice"],
            "change_pct": d["priceChangePercent"],
            "high": d["highPrice"],
            "low": d["lowPrice"],
            "volume": d["volume"],
            "quote_volume": d["quoteVolume"],
        }
        _ticker_cache[pair] = (result, now)
        return result
    except Exception as e:
        print(f"[Binance] fetch_ticker {pair}: {e}")
        if pair in _ticker_cache:
            return _ticker_cache[pair][0]
        return {}


async def fetch_klines(pair: str, interval: str = "1h", limit: int = 500) -> list:
    """Fetch OHLCV candlestick data from Binance. Supports any USDT pair."""
    now = datetime.now().timestamp()
    cache_key = f"{pair}:{interval}:{limit}"
    if cache_key in _klines_cache:
        data, ts = _klines_cache[cache_key]
        if now - ts < _KLINES_TTL:
            return data

    symbol = _pair_to_symbol(pair)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BINANCE_REST}/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            raw = r.json()

        klines = [
            {
                "time":   int(k[0] // 1000),  # ms → seconds
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[5]),
            }
            for k in raw
        ]
        _klines_cache[cache_key] = (klines, now)
        return klines
    except Exception as e:
        print(f"[Binance] fetch_klines {pair} {interval}: {e}")
        if cache_key in _klines_cache:
            return _klines_cache[cache_key][0]
        return []


async def sync_market_to_redis(pair: str):
    """One-shot fetch for initial Redis warm-up."""
    redis = await get_redis()
    ticker = await fetch_ticker(pair)
    if ticker:
        await redis.set(f"market:{pair}:ticker", json.dumps(ticker), ex=30)


# ── WebSocket streaming loop ──────────────────────────────────────────────────

async def _ws_pair(pair: str, broadcast_cb: BroadcastCb):
    """
    Connect to Binance combined stream for one pair:
      <symbol>@ticker  – 24h stats (price, change, volume …)
      <symbol>@depth20 – order book top-20
      <symbol>@trade   – individual trades
    Auto-reconnects on disconnect.
    """
    import websockets  # type: ignore

    symbol = _pair_to_symbol(pair).lower()
    # Combined stream URL: wss://stream.binance.com:9443/stream?streams=s1/s2/s3
    # Each message is wrapped: {"stream": "...", "data": {...}}
    streams = f"{symbol}@ticker/{symbol}@depth20@100ms/{symbol}@trade"
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    redis = await get_redis()

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[Binance WS] connected {pair}")
                async for raw in ws:
                    msg = json.loads(raw)
                    stream = msg.get("stream", "")

                    if "@ticker" in stream:
                        d = msg["data"]
                        ticker = {
                            "pair": pair,
                            "last_price": d["c"],
                            "change_pct": d["P"],
                            "high": d["h"],
                            "low": d["l"],
                            "volume": d["v"],
                            "quote_volume": d["q"],
                        }
                        await redis.set(f"market:{pair}:ticker", json.dumps(ticker), ex=30)
                        _ticker_cache[pair] = (ticker, datetime.now().timestamp())
                        await broadcast_cb(pair, {"type": "ticker", "ticker": ticker})

                    elif "@depth" in stream:
                        d = msg["data"]
                        orderbook = {
                            "pair": pair,
                            "bids": d.get("bids", []),
                            "asks": d.get("asks", []),
                        }
                        await redis.set(f"market:{pair}:orderbook", json.dumps(orderbook), ex=10)
                        await broadcast_cb(pair, {"type": "orderbook", "orderbook": orderbook})

                    elif "@trade" in stream:
                        d = msg["data"]
                        trade = {
                            "price": d["p"],
                            "qty": d["q"],
                            "is_buyer_maker": d["m"],   # True = seller is market maker (sell)
                            "time": d["T"],
                        }
                        # Rolling list in Redis (for snapshot on new connections)
                        trades_key = f"market:{pair}:trades"
                        existing_raw = await redis.get(trades_key)
                        trades = json.loads(existing_raw) if existing_raw else []
                        trades.append(trade)
                        trades = trades[-50:]
                        await redis.set(trades_key, json.dumps(trades), ex=60)
                        # Push to connected clients
                        await broadcast_cb(pair, {"type": "trade", "trade": trade})

        except Exception as e:
            print(f"[Binance WS] {pair} error: {e} — reconnecting in 5s")
            await asyncio.sleep(5)


async def market_data_loop(
    pairs: List[str],
    broadcast_cb: Optional[BroadcastCb] = None,
    interval_sec: int = 10,  # kept for API compat, unused
):
    """Launch WS streaming for each pair after an initial REST warm-up."""
    if broadcast_cb is None:
        async def _noop(pair: str, data: dict):
            pass
        broadcast_cb = _noop

    # Initial warm-up via REST so Redis has data immediately
    for pair in pairs:
        try:
            await sync_market_to_redis(pair)
        except Exception as e:
            print(f"[Warm-up] {pair}: {e}")

    # Run all WS loops concurrently (each auto-reconnects)
    await asyncio.gather(*[_ws_pair(pair, broadcast_cb) for pair in pairs])
