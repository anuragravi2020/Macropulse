import logging
import numpy as np
from services.data_fetcher import get_historical_dataframe
from strategies.config import (
    MOMENTUM_MIN_PERIODS,
    MOMENTUM_ROC_SHORT_WINDOW,
    MOMENTUM_ROC_LONG_WINDOW,
    MOMENTUM_ABS_MULTIPLIER,
    MOMENTUM_ROC_SHORT_WEIGHT,
    MOMENTUM_ROC_LONG_WEIGHT,
    MOMENTUM_ROC_DIVISOR,
    MOMENTUM_REL_MULTIPLIER,
    MOMENTUM_WEIGHT_ABS,
    MOMENTUM_WEIGHT_ROC,
    MOMENTUM_WEIGHT_REL,
    SIGNAL_BUY_THRESHOLD,
    SIGNAL_SELL_THRESHOLD,
)

logger = logging.getLogger(__name__)


def calculate_momentum(symbol):
    """
    Dual Momentum Strategy:
    - Absolute momentum: 12-month return > 0 → bullish
    - Relative momentum: Compare ROC vs SPY benchmark
    - Score from -1 (strong sell) to +1 (strong buy)
    """
    try:
        df = get_historical_dataframe(symbol, period="1y")
        if df is None or len(df) < MOMENTUM_MIN_PERIODS:
            return None

        closes = df["Close"].values

        # Absolute momentum: total return over available period
        total_return = (closes[-1] - closes[0]) / closes[0]

        # Rate of Change (ROC) - multiple timeframes
        roc_20 = (closes[-1] - closes[-MOMENTUM_ROC_SHORT_WINDOW]) / closes[-MOMENTUM_ROC_SHORT_WINDOW] if len(closes) >= MOMENTUM_ROC_SHORT_WINDOW else 0
        roc_60 = (closes[-1] - closes[-MOMENTUM_ROC_LONG_WINDOW]) / closes[-MOMENTUM_ROC_LONG_WINDOW] if len(closes) >= MOMENTUM_ROC_LONG_WINDOW else 0

        # Relative momentum vs SPY benchmark
        spy_df = get_historical_dataframe("SPY", period="1y")
        relative_score = 0
        if spy_df is not None and len(spy_df) >= MOMENTUM_MIN_PERIODS:
            spy_closes = spy_df["Close"].values
            spy_return = (spy_closes[-1] - spy_closes[0]) / spy_closes[0]
            relative_score = total_return - spy_return

        # Combine signals
        # Absolute: positive return = bullish
        abs_signal = np.clip(total_return * MOMENTUM_ABS_MULTIPLIER, -1, 1)

        # ROC combined (short + medium term) — weighted avg
        roc_signal = np.clip((roc_20 * MOMENTUM_ROC_SHORT_WEIGHT + roc_60 * MOMENTUM_ROC_LONG_WEIGHT) / MOMENTUM_ROC_DIVISOR, -1, 1)

        # Relative: outperforming benchmark = bullish
        rel_signal = np.clip(relative_score * MOMENTUM_REL_MULTIPLIER, -1, 1)

        # Weighted combination
        score = MOMENTUM_WEIGHT_ABS * abs_signal + MOMENTUM_WEIGHT_ROC * roc_signal + MOMENTUM_WEIGHT_REL * rel_signal
        score = float(np.clip(score, -1, 1))

        if score > SIGNAL_BUY_THRESHOLD:
            signal = "BUY"
        elif score < SIGNAL_SELL_THRESHOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Build detail string
        details = f"12m return {total_return * 100:+.1f}%"
        if spy_df is not None:
            spy_return_val = (spy_df["Close"].values[-1] - spy_df["Close"].values[0]) / spy_df["Close"].values[0]
            comparison = "above" if total_return > spy_return_val else "below"
            details += f", {comparison} SPY ({spy_return_val * 100:+.1f}%)"

        return {
            "score": round(score, 2),
            "signal": signal,
            "details": details,
        }
    except Exception:
        logger.exception("Error calculating momentum for %s", symbol)
        return None
