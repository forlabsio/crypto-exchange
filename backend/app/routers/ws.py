"""
ws.py — WebSocket endpoints for the exchange frontend.

Architecture:
  Binance WS stream → market_data._stream_pair()
                          → broadcast_cb (below)
                              → ConnectionManager.broadcast()
                                  → all browser clients subscribed to that pair

Browser clients receive typed messages:
  { "type": "ticker",    "ticker": {...} }
  { "type": "orderbook", "orderbook": {...} }
  { "type": "trade",     "trade": {...} }
  { "type": "kline",     "interval": "1h", "kline": {...} }  ← real-time candlestick
  { "type": "snapshot",  "ticker": {...}, "orderbook": {...}, "trades": [...] }  ← on connect
"""
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis import get_redis

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        # pair → list of connected WebSockets
        self.connections: dict = {}

    async def connect(self, pair: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(pair, []).append(ws)

    def disconnect(self, pair: str, ws: WebSocket):
        conns = self.connections.get(pair, [])
        try:
            conns.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, pair: str, data: dict):
        """Push data to every client subscribed to this pair."""
        dead = []
        for ws in list(self.connections.get(pair, [])):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(pair, ws)


manager = ConnectionManager()


async def _binance_broadcast_cb(pair: str, data: dict):
    """Called by market_data._stream_pair() on every Binance message."""
    await manager.broadcast(pair, data)


@router.websocket("/ws/market/{pair}")
async def market_ws(pair: str, ws: WebSocket):
    await ws.accept()
    redis = await get_redis()

    # Send full snapshot BEFORE joining broadcast list (avoids race condition)
    try:
        ticker_raw   = await redis.get(f"market:{pair}:ticker")
        ob_raw       = await redis.get(f"market:{pair}:orderbook")
        trades_raw   = await redis.get(f"market:{pair}:trades")

        orderbook = json.loads(ob_raw) if ob_raw else {"bids": [], "asks": []}

        await ws.send_json({
            "type":      "snapshot",
            "ticker":    json.loads(ticker_raw)  if ticker_raw  else {},
            "orderbook": orderbook,
            "trades":    json.loads(trades_raw)  if trades_raw  else [],
        })
    except Exception as e:
        print(f"[WS] Error sending snapshot for {pair}: {e}")
        return

    # Now add to broadcast list so real-time updates are pushed
    manager.connections.setdefault(pair, []).append(ws)

    # Keep connection alive; updates arrive via broadcast_cb (push, not poll)
    try:
        while True:
            # Block until the client sends something (or disconnects)
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(pair, ws)
    except Exception:
        manager.disconnect(pair, ws)
