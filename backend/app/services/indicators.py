import math
from typing import List, Tuple


def calc_rsi(closes: List[float], period: int = 14) -> float:
    """Compute RSI from a list of closing prices. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [max(d, 0.0) for d in recent]
    losses = [abs(min(d, 0.0)) for d in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_ma(closes: List[float], period: int) -> float:
    """Simple moving average of the last `period` prices."""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period


def calc_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Tuple[float, float]:
    """Return (lower_band, upper_band). Falls back to +-5% if insufficient data."""
    if len(closes) < period:
        last = closes[-1] if closes else 100.0
        return (last * 0.95, last * 1.05)
    window = closes[-period:]
    ma = sum(window) / period
    variance = sum((p - ma) ** 2 for p in window) / period
    std = math.sqrt(variance)
    return (ma - std_dev * std, ma + std_dev * std)
