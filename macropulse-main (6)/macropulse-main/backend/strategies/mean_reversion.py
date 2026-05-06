import logging
import numpy as np
from services.data_fetcher import get_historical_dataframe
from strategies.config import (
    MEAN_REV_MIN_PERIODS,
    MEAN_REV_STD_WINDOW,
    MEAN_REV_MEAN_LOOKBACK,
    MEAN_REV_BOLLINGER_STD,
    MEAN_REV_ZSCORE_DIVISOR,
    MEAN_REV_RSI_PERIOD,
    MEAN_REV_RSI_CENTER,
    MEAN_REV_RSI_SCALE,
    MEAN_REV_WEIGHT_ZSCORE,
    MEAN_REV_WEIGHT_BOLLINGER,
    MEAN_REV_WEIGHT_RSI,
    MEAN_REV_WEIGHT_ZSCORE_NO_RSI,
    MEAN_REV_WEIGHT_BOLLINGER_NO_RSI,
    MEAN_REV_ZONE_OVERSOLD,
    MEAN_REV_ZONE_OVERBOUGHT,
    MEAN_REV_ZONE_NEUTRAL,
    SIGNAL_BUY_THRESHOLD,
    SIGNAL_SELL_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _calculate_rsi(closes, period=MEAN_REV_RSI_PERIOD):
    """Calculate RSI using Wilder's smoothing method. Returns RSI value or None."""
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_mean_reversion(symbol):
    """
    Z-Score Mean Reversion Strategy:
    - Z-score of current price vs 50-day mean / 20-day std
    - Bollinger Band position (%B indicator)
    - RSI (14-period): RSI < 30 → oversold, RSI > 70 → overbought
    - Z < -2 → oversold (buy), Z > 2 → overbought (sell)
    - Score from -1 (strong sell) to +1 (strong buy)
    """
    try:
        df = get_historical_dataframe(symbol, period="6mo")
        if df is None or len(df) < MEAN_REV_MIN_PERIODS:
            return None

        closes = df["Close"].values

        # Use a longer lookback for the mean so a recent crash/spike is
        # measured against a longer baseline (more sensitive to reversions).
        # Keep a shorter window for std to reflect recent volatility.
        window   = MEAN_REV_STD_WINDOW
        lookback = min(MEAN_REV_MEAN_LOOKBACK, len(closes))
        rolling_mean = np.mean(closes[-lookback:])
        rolling_std  = np.std(closes[-window:], ddof=1)

        if rolling_std == 0:
            return {"score": 0.0, "signal": "HOLD",
                    "details": "Insufficient price variation"}

        current_price = closes[-1]

        # Z-score
        z_score = (current_price - rolling_mean) / rolling_std

        # Bollinger Bands
        upper_band = rolling_mean + MEAN_REV_BOLLINGER_STD * rolling_std
        lower_band = rolling_mean - MEAN_REV_BOLLINGER_STD * rolling_std
        band_width = upper_band - lower_band

        # %B indicator: position within Bollinger Bands (0 = lower, 1 = upper)
        pct_b = (current_price - lower_band) / band_width if band_width > 0 else 0.5

        # RSI signal (inverted: low RSI = oversold = buy)
        rsi = _calculate_rsi(closes)
        rsi_signal = float(np.clip((MEAN_REV_RSI_CENTER - rsi) / MEAN_REV_RSI_SCALE, -1, 1)) if rsi is not None else None

        # Mean reversion signal (inverted: oversold = buy opportunity)
        z_signal = float(np.clip(-z_score / MEAN_REV_ZSCORE_DIVISOR, -1, 1))

        # %B signal (inverted: near lower band = buy)
        b_signal = float(np.clip((0.5 - pct_b) * 2, -1, 1))

        # Combined score — include RSI if available, else fall back to original weights
        if rsi_signal is not None:
            score = MEAN_REV_WEIGHT_ZSCORE * z_signal + MEAN_REV_WEIGHT_BOLLINGER * b_signal + MEAN_REV_WEIGHT_RSI * rsi_signal
        else:
            score = MEAN_REV_WEIGHT_ZSCORE_NO_RSI * z_signal + MEAN_REV_WEIGHT_BOLLINGER_NO_RSI * b_signal
        score = float(np.clip(score, -1, 1))

        if score > SIGNAL_BUY_THRESHOLD:
            signal = "BUY"
        elif score < SIGNAL_SELL_THRESHOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Zone description
        if z_score < MEAN_REV_ZONE_OVERSOLD:
            zone = "oversold"
        elif z_score > MEAN_REV_ZONE_OVERBOUGHT:
            zone = "overbought"
        elif abs(z_score) < MEAN_REV_ZONE_NEUTRAL:
            zone = "neutral zone"
        elif z_score > 0:
            zone = "slightly overbought"
        else:
            zone = "slightly oversold"

        rsi_str = f", RSI: {rsi:.1f}" if rsi is not None else ""
        details = f"Z-score: {z_score:.2f}, {zone}, %B: {pct_b:.2f}{rsi_str}"

        return {
            "score": round(score, 2),
            "signal": signal,
            "details": details,
        }
    except Exception:
        logger.exception("Error calculating mean reversion for %s", symbol)
        return None
