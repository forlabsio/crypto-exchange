import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis import get_redis

router = APIRouter(tags=["websocket"])

class ConnectionManager:
    def __init__(self):
        self.connections = {}

    async def connect(self, pair: str, ws: WebSocket):
        await ws.accept()
        if pair not in self.connections:
            self.connections[pair] = []
        self.connections[pair].append(ws)

    def disconnect(self, pair: str, ws: WebSocket):
        if pair in self.connections:
            try:
                self.connections[pair].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, pair: str, data: dict):
        dead = []
        for ws in self.connections.get(pair, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(pair, ws)

manager = ConnectionManager()

@router.websocket("/ws/market/{pair}")
async def market_ws(pair: str, ws: WebSocket):
    await manager.connect(pair, ws)
    redis = await get_redis()
    try:
        while True:
            ticker = await redis.get(f"market:{pair}:ticker")
            orderbook = await redis.get(f"market:{pair}:orderbook")
            trades = await redis.get(f"market:{pair}:trades")
            await ws.send_json({
                "type": "snapshot",
                "ticker": json.loads(ticker) if ticker else {},
                "orderbook": json.loads(orderbook) if orderbook else {},
                "trades": json.loads(trades) if trades else [],
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(pair, ws)
