"""
Binance REST API — real market order execution.
Uses HMAC-SHA256 signed requests (no third-party library).
"""
import logging
import time
import hmac
import hashlib
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _sign(params: str) -> str:
    return hmac.new(
        settings.BINANCE_API_SECRET.encode(), params.encode(), hashlib.sha256
    ).hexdigest()


async def place_market_order(
    symbol: str,       # e.g. "BTCUSDT"
    side: str,         # "BUY" or "SELL"
    quote_qty: float,  # USDT amount to spend (for BUY) or coin qty (for SELL)
    use_quote: bool = True,  # True = quoteOrderQty (spend USDT), False = quantity
) -> dict:
    """
    Place a market order on Binance.
    Returns the Binance order response dict.
    Raises Exception on failure.
    """
    if not settings.BINANCE_API_KEY or not settings.BINANCE_API_SECRET:
        raise Exception("BINANCE_API_KEY / BINANCE_API_SECRET not configured")

    timestamp = int(time.time() * 1000)
    if use_quote:
        params = (
            f"symbol={symbol}&side={side}&type=MARKET"
            f"&quoteOrderQty={quote_qty:.2f}&timestamp={timestamp}&recvWindow=10000"
        )
    else:
        params = (
            f"symbol={symbol}&side={side}&type=MARKET"
            f"&quantity={quote_qty:.6f}&timestamp={timestamp}&recvWindow=10000"
        )

    signature = _sign(params)
    url = f"{settings.BINANCE_BASE_URL}/api/v3/order?{params}&signature={signature}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers={"X-MBX-APIKEY": settings.BINANCE_API_KEY})

    if resp.status_code != 200:
        raise Exception(f"Binance order failed: {resp.status_code} {resp.text}")

    return resp.json()


async def get_account_balance(asset: str = "USDT") -> float:
    """Fetch Binance account balance for an asset."""
    if not settings.BINANCE_API_KEY or not settings.BINANCE_API_SECRET:
        raise Exception("BINANCE_API_KEY / BINANCE_API_SECRET not configured")

    timestamp = int(time.time() * 1000)
    params = f"timestamp={timestamp}&recvWindow=10000"
    signature = _sign(params)
    url = f"{settings.BINANCE_BASE_URL}/api/v3/account?{params}&signature={signature}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers={"X-MBX-APIKEY": settings.BINANCE_API_KEY})

    resp.raise_for_status()
    data = resp.json()
    for b in data.get("balances", []):
        if b["asset"] == asset:
            return float(b["free"])
    return 0.0
