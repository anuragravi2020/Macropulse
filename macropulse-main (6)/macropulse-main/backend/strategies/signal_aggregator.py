import logging
import time
from strategies.momentum import calculate_momentum
from strategies.mean_reversion import calculate_mean_reversion
from strategies.monte_carlo import calculate_monte_carlo
from strategies.factor_model import calculate_factor_model
from strategies.config import (
    STRATEGY_WEIGHTS,
    AGG_BUY_THRESHOLD,
    AGG_SELL_THRESHOLD,
    AGG_BASE_CONFIDENCE_OFFSET,
    AGG_AGREEMENT_BONUS_MAX,
    AGG_COVERAGE_PENALTY_MAX,
    AGG_CONFIDENCE_MAX,
    AGG_CONFIDENCE_MIN,
)

logger = logging.getLogger(__name__)

# Mubashir - US13: In-memory TTL cache so repeated requests within 5 minutes
# return cached results instead of re-running all four strategies.
_signal_cache = {}
CACHE_TTL = 300  # seconds (5 minutes)


def get_aggregated_signal(symbol):
    """
    Weighted ensemble combining all strategies into BUY/SELL/HOLD with confidence %.

    - Runs all 4 strategies independently (cached for 5 minutes per symbol)
    - Combines scores using predefined weights from config
    - Redistributes weight if a strategy returns None (missing data)
    - Confidence: 30-100% based on score magnitude and strategy agreement

    Returns:
        {
            "symbol": "AAPL",
            "signal": "BUY" | "SELL" | "HOLD",
            "confidence": 0-100,
            "breakdown": { ... }
        }
    """
    symbol = symbol.upper()

    # US13: Return cached result if still within TTL
    cached = _signal_cache.get(symbol)
    if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
        logger.info("Cache hit for %s (age: %.0fs)", symbol, time.time() - cached["timestamp"])
        return cached["data"]

    # Run all strategies and track execution
    strategy_runners = {
        "momentum": calculate_momentum,
        "mean_reversion": calculate_mean_reversion,
        "monte_carlo": calculate_monte_carlo,
        "factor_model": calculate_factor_model,
    }

    results = {}
    for name, runner in strategy_runners.items():
        try:
            results[name] = runner(symbol)
            logger.info("Strategy %s completed for %s", name, symbol)
        except Exception as e:
            logger.warning("Strategy %s failed for %s: %s", name, symbol, e)
            results[name] = None

    # Calculate weighted score from available strategies
    weighted_sum = 0
    total_weight = 0
    breakdown = {}
    active_strategies = 0

    for strategy_name, result in results.items():
        if result is not None:
            weight = STRATEGY_WEIGHTS[strategy_name]
            weighted_sum += result["score"] * weight
            total_weight += weight
            breakdown[strategy_name] = result
            active_strategies += 1
        else:
            breakdown[strategy_name] = {
                "score": 0,
                "signal": "N/A",
                "details": "Insufficient data",
            }

    if total_weight == 0:
        return None

    # Normalize score (redistributes weight from missing strategies)
    final_score = weighted_sum / total_weight

    # Determine signal
    if final_score > AGG_BUY_THRESHOLD:
        signal = "BUY"
    elif final_score < AGG_SELL_THRESHOLD:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Confidence calculation:
    # Base confidence from score magnitude
    base_confidence = abs(final_score) * 100 + AGG_BASE_CONFIDENCE_OFFSET

    # Agreement bonus: magnitude-weighted — a strategy with score 0.9 agreeing
    # carries more weight than one with score 0.05 agreeing.
    if active_strategies >= 2:
        total_magnitude = sum(
            abs(r["score"]) for r in results.values() if r is not None
        )
        if total_magnitude > 0:
            aligned_magnitude = sum(
                abs(r["score"]) for r in results.values()
                if r is not None and (
                    (r["score"] > 0 and final_score > 0) or
                    (r["score"] < 0 and final_score < 0)
                )
            )
            agreement_ratio = aligned_magnitude / total_magnitude
        else:
            agreement_ratio = 0
        agreement_bonus = agreement_ratio * AGG_AGREEMENT_BONUS_MAX
    else:
        agreement_bonus = 0

    # Coverage penalty: fewer strategies = less confidence
    coverage_ratio = active_strategies / len(STRATEGY_WEIGHTS)
    coverage_penalty = (1 - coverage_ratio) * AGG_COVERAGE_PENALTY_MAX

    confidence = min(int(base_confidence + agreement_bonus - coverage_penalty), AGG_CONFIDENCE_MAX)
    confidence = max(confidence, AGG_CONFIDENCE_MIN)

    result_data = {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "breakdown": breakdown,
    }

    # US13: Store result in cache with current timestamp
    _signal_cache[symbol] = {"data": result_data, "timestamp": time.time()}

    return result_data
