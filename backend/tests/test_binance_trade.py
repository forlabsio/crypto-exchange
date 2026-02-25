"""
Tests for binance_trade.py and the _execute_real_trade helper in bot_runner.py.
All network calls are mocked; no real HTTP requests are made.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_data: dict) -> MagicMock:
    """Return a mock httpx.Response with .status_code and .json()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


FAKE_FILLS = [
    {"price": "50000.00", "qty": "0.001"},
    {"price": "50100.00", "qty": "0.002"},
]

FAKE_ORDER_RESPONSE = {
    "orderId": 123456,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "fills": FAKE_FILLS,
}


# ---------------------------------------------------------------------------
# 1. test_place_market_order_buy_success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_place_market_order_buy_success():
    """Mock httpx POST, verify params contain expected fields, return fills."""
    mock_resp = _make_response(200, FAKE_ORDER_RESPONSE)
    mock_post = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.binance_trade.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.BINANCE_API_KEY = "test_key"
        mock_settings.BINANCE_API_SECRET = "test_secret"
        mock_settings.BINANCE_BASE_URL = "https://api.binance.com"

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.binance_trade import place_market_order
        result = await place_market_order("BTCUSDT", "BUY", 100.0, use_quote=True)

    assert result["status"] == "FILLED"
    assert result["fills"] == FAKE_FILLS
    # Verify the URL contained the right params
    call_url = mock_post.call_args[0][0]
    assert "BTCUSDT" in call_url
    assert "BUY" in call_url
    assert "quoteOrderQty=100.00" in call_url
    assert "recvWindow=10000" in call_url


# ---------------------------------------------------------------------------
# 2. test_place_market_order_raises_on_non200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_place_market_order_raises_on_non200():
    """Mock POST returns 400; verify Exception is raised."""
    mock_resp = _make_response(400, {"code": -1100, "msg": "Illegal characters"})
    mock_post = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.binance_trade.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.BINANCE_API_KEY = "test_key"
        mock_settings.BINANCE_API_SECRET = "test_secret"
        mock_settings.BINANCE_BASE_URL = "https://api.binance.com"

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.binance_trade import place_market_order
        with pytest.raises(Exception, match="Binance order failed: 400"):
            await place_market_order("BTCUSDT", "BUY", 100.0, use_quote=True)


# ---------------------------------------------------------------------------
# 3. test_place_market_order_raises_when_not_configured
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_place_market_order_raises_when_not_configured():
    """Settings with empty keys; verify Exception raised before any HTTP call."""
    with patch("app.services.binance_trade.settings") as mock_settings:
        mock_settings.BINANCE_API_KEY = ""
        mock_settings.BINANCE_API_SECRET = ""

        from app.services.binance_trade import place_market_order
        with pytest.raises(Exception, match="not configured"):
            await place_market_order("BTCUSDT", "BUY", 100.0)


# ---------------------------------------------------------------------------
# 4. test_get_account_balance_returns_correct_asset
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_account_balance_returns_correct_asset():
    """Mock GET returns balances list; verify correct float returned for USDT."""
    balance_response = {
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "USDT", "free": "1234.56", "locked": "0.0"},
            {"asset": "ETH", "free": "2.0", "locked": "0.0"},
        ]
    }
    mock_resp = _make_response(200, balance_response)
    mock_resp.raise_for_status = MagicMock()
    mock_get = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.binance_trade.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.BINANCE_API_KEY = "test_key"
        mock_settings.BINANCE_API_SECRET = "test_secret"
        mock_settings.BINANCE_BASE_URL = "https://api.binance.com"

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.binance_trade import get_account_balance
        balance = await get_account_balance("USDT")

    assert balance == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# 5. test_execute_real_trade_buy_calls_place_order
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_real_trade_buy_calls_place_order():
    """Mock place_market_order; verify called with correct args on BUY signal."""
    mock_place = AsyncMock(return_value=FAKE_ORDER_RESPONSE)

    with patch("app.services.bot_runner.place_market_order", mock_place):
        from app.services.bot_runner import _execute_real_trade
        result = await _execute_real_trade("TestBot", 1, "buy", 500.0, "BTC_USDT")

    mock_place.assert_awaited_once_with("BTCUSDT", "BUY", 500.0, use_quote=True)
    assert result == FAKE_ORDER_RESPONSE


# ---------------------------------------------------------------------------
# 6. test_execute_real_trade_sell_skips
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_real_trade_sell_skips():
    """SELL signal must return None without calling place_market_order."""
    mock_place = AsyncMock()

    with patch("app.services.bot_runner.place_market_order", mock_place):
        from app.services.bot_runner import _execute_real_trade
        result = await _execute_real_trade("TestBot", 1, "sell", 500.0, "BTC_USDT")

    mock_place.assert_not_awaited()
    assert result is None


# ---------------------------------------------------------------------------
# 7. test_execute_real_trade_swallows_exception
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_real_trade_swallows_exception():
    """place_market_order raises; _execute_real_trade must swallow and return None."""
    mock_place = AsyncMock(side_effect=Exception("Network timeout"))

    with patch("app.services.bot_runner.place_market_order", mock_place):
        from app.services.bot_runner import _execute_real_trade
        result = await _execute_real_trade("TestBot", 1, "buy", 500.0, "BTC_USDT")

    assert result is None
