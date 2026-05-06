import logging
import numpy as np
from services.data_fetcher import get_ticker_info_raw, get_historical_dataframe
from strategies.config import (
    FACTOR_MIN_PERIODS,
    FACTOR_ROE_CENTER,
    FACTOR_ROE_SCALE,
    FACTOR_MARGIN_CENTER,
    FACTOR_MARGIN_SCALE,
    FACTOR_VOL_NORMALIZATION,
    FACTOR_SIZE_CENTER,
    FACTOR_SIZE_SCALE,
    FACTOR_WEIGHT_VALUE,
    FACTOR_WEIGHT_GROWTH,
    FACTOR_WEIGHT_QUALITY,
    FACTOR_WEIGHT_VOLATILITY,
    FACTOR_WEIGHT_SIZE,
    SIGNAL_BUY_THRESHOLD,
    SIGNAL_SELL_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _score_pe_ratio(pe):
    """Continuous P/E scoring using sigmoid-like curve centered at market median ~20."""
    if pe <= 0:
        return 0.0
    # Inverse relationship: lower P/E = higher score
    # Centered at 20, with smooth transitions
    score = 1.0 - (2.0 / (1.0 + np.exp(-0.15 * (pe - 20))))
    return float(np.clip(score, -1, 1))


def _score_earnings_growth(info):
    """Score based on earnings growth rate (forward vs trailing P/E gap)."""
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")

    if trailing_pe and forward_pe and trailing_pe > 0 and forward_pe > 0:
        # If forward P/E < trailing P/E, earnings are expected to grow
        growth_ratio = (trailing_pe - forward_pe) / trailing_pe
        return float(np.clip(growth_ratio * 3, -1, 1))
    return None


def calculate_factor_model(symbol):
    """
    Multi-Factor Model with 5 scoring dimensions:
    - Value factor (25%): P/E ratio scoring with continuous sigmoid curve
    - Growth factor (15%): Earnings growth from trailing vs forward P/E
    - Quality factor (25%): ROE and profit margins combined
    - Volatility factor (20%): Low-vol premium with downside risk adjustment
    - Size factor (15%): Market cap stability premium
    - Combined multi-factor score from -1 to +1
    """
    try:
        info = get_ticker_info_raw(symbol)
        if info is None:
            return None

        scores = []
        details_parts = []

        # --- Value Factor: P/E Ratio (continuous scoring) ---
        pe_ratio = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        pe = forward_pe or pe_ratio

        if pe is not None and pe > 0:
            value_score = _score_pe_ratio(pe)
            scores.append(("value", value_score, FACTOR_WEIGHT_VALUE))
            details_parts.append(f"P/E {pe:.1f}")
        else:
            details_parts.append("P/E N/A")

        # --- Growth Factor: Earnings Growth ---
        growth_score = _score_earnings_growth(info)
        if growth_score is not None:
            scores.append(("growth", growth_score, FACTOR_WEIGHT_GROWTH))
            details_parts.append(f"growth {growth_score:+.2f}")
        else:
            details_parts.append("growth N/A")

        # --- Quality Factor: ROE + Profit Margins ---
        roe = info.get("returnOnEquity")
        profit_margin = info.get("profitMargins")

        quality_scores = []
        if roe is not None:
            # ROE > 20% is excellent, < 5% is poor
            roe_score = float(np.clip((roe - FACTOR_ROE_CENTER) * FACTOR_ROE_SCALE, -1, 1))
            quality_scores.append(roe_score)
            details_parts.append(f"ROE {roe * 100:.1f}%")

        if profit_margin is not None:
            # Profit margin > 20% is strong, < 0% is poor
            margin_score = float(np.clip((profit_margin - FACTOR_MARGIN_CENTER) * FACTOR_MARGIN_SCALE, -1, 1))
            quality_scores.append(margin_score)

        if quality_scores:
            quality_score = np.mean(quality_scores)
            scores.append(("quality", float(quality_score), FACTOR_WEIGHT_QUALITY))
        else:
            details_parts.append("quality N/A")

        # --- Volatility Factor: Low-Vol Premium with Downside Risk ---
        df = get_historical_dataframe(symbol, period="1y")
        if df is not None and len(df) >= FACTOR_MIN_PERIODS:
            daily_returns = df["Close"].pct_change().dropna().values
            annual_vol = np.std(daily_returns, ddof=1) * np.sqrt(252)

            # Downside deviation (only negative returns)
            negative_returns = daily_returns[daily_returns < 0]
            downside_vol = np.std(negative_returns, ddof=1) * np.sqrt(252) if len(negative_returns) > 5 else annual_vol

            # Sortino-style adjustment: penalize downside risk more
            adjusted_vol = 0.6 * annual_vol + 0.4 * downside_vol

            # Lower volatility = better (low-vol premium)
            vol_score = float(np.clip(1.0 - (adjusted_vol / FACTOR_VOL_NORMALIZATION), -1, 1))

            scores.append(("volatility", vol_score, FACTOR_WEIGHT_VOLATILITY))
            details_parts.append(f"vol {annual_vol * 100:.1f}%")
        else:
            details_parts.append("vol N/A")

        # --- Size Factor: Market Cap Stability ---
        market_cap = info.get("marketCap")
        if market_cap is not None and market_cap > 0:
            # Large cap > $50B = stable, small cap < $2B = risky but higher upside
            log_cap = np.log10(market_cap)
            # Score: mega cap (12+) = 0.6, large (10-12) = 0.3, mid (9-10) = 0, small (<9) = -0.3
            size_score = float(np.clip((log_cap - FACTOR_SIZE_CENTER) * FACTOR_SIZE_SCALE, -0.5, 0.7))
            scores.append(("size", size_score, FACTOR_WEIGHT_SIZE))
        else:
            details_parts.append("mcap N/A")

        if not scores:
            return None

        # Weighted combination
        total_weight = sum(w for _, _, w in scores)
        combined = sum(s * w for _, s, w in scores) / total_weight if total_weight > 0 else 0
        combined = float(np.clip(combined, -1, 1))

        if combined > SIGNAL_BUY_THRESHOLD:
            signal = "BUY"
        elif combined < SIGNAL_SELL_THRESHOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        return {
            "score": round(combined, 2),
            "signal": signal,
            "details": ", ".join(details_parts),
        }
    except Exception:
        logger.exception("Error calculating factor model for %s", symbol)
        return None
