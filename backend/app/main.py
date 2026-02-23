import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth
from app.core.redis import get_redis

SUPPORTED_PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    yield

app = FastAPI(title="CryptoExchange API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
