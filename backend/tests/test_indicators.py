import math
import pytest
from app.services.indicators import calc_rsi, calc_ma, calc_bollinger

def test_calc_rsi_oversold():
    # Steadily declining prices → RSI should be low
    prices = [float(100 - i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi < 30

def test_calc_rsi_overbought():
    # Steadily rising prices → RSI should be high
    prices = [float(100 + i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi > 70

def test_calc_rsi_neutral_returns_50_on_insufficient_data():
    prices = [100.0, 101.0]
    rsi = calc_rsi(prices, period=14)
    assert rsi == 50.0

def test_calc_ma():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calc_ma(prices, period=3) == pytest.approx(4.0)  # avg of last 3: 3,4,5

def test_calc_ma_insufficient_data_returns_last():
    prices = [42.0]
    assert calc_ma(prices, period=5) == 42.0

def test_calc_bollinger_buy_signal():
    # Price well below lower band → should be at or below lower band
    prices = [100.0] * 19 + [70.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] <= lower

def test_calc_bollinger_sell_signal():
    # Price well above upper band → should be at or above upper band
    prices = [100.0] * 19 + [130.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] >= upper

def test_calc_bollinger_normal_price_is_inside_bands():
    prices = [100.0] * 20
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert lower <= 100.0 <= upper
