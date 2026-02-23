import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.routers import auth, market, ws, orders, wallet, bots, admin
from app.routers.ws import _binance_broadcast_cb
from app.core.redis import get_redis
from app.services.market_data import market_data_loop
from app.services.bot_runner import bot_runner_loop
from app.services.bot_eviction import daily_drawdown_check, monthly_evaluation

SUPPORTED_PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT"]
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    # Pass broadcast callback so Binance updates are pushed to browser clients instantly
    asyncio.create_task(market_data_loop(SUPPORTED_PAIRS, broadcast_cb=_binance_broadcast_cb))
    asyncio.create_task(bot_runner_loop())
    scheduler.add_job(daily_drawdown_check, "cron", hour=0, minute=0)
    scheduler.add_job(monthly_evaluation, "cron", day="last", hour=23, minute=59)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="CryptoExchange API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(market.router)
app.include_router(ws.router)
app.include_router(orders.router)
app.include_router(wallet.router)
app.include_router(bots.router)
app.include_router(admin.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
