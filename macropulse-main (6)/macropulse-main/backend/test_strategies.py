"""Cumulative strategy test suite for Macropulse.

Tests all four quantitative strategies individually, then runs integration
tests through the signal aggregator. Uses synthetic price data and mocked
data fetchers — no internet connection required.

Usage:
    cd backend
    python test_strategies.py
"""

import sys
import os
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

# Ensure backend/ is on the path when run from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic price series helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(prices):
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    arr = np.array(prices, dtype=float)
    dates = pd.date_range("2024-01-01", periods=len(arr), freq="B")
    return pd.DataFrame({
        "Open":   arr * 0.995,
        "High":   arr * 1.010,
        "Low":    arr * 0.990,
        "Close":  arr,
        "Volume": np.full(len(arr), 1_000_000),
    }, index=dates)


def _uptrend(n=252):
    """Strong uptrend: +0.3 %/day (~+107 % over a year)."""
    return [round(100.0 * (1.003 ** i), 4) for i in range(n)]


def _downtrend(n=252):
    """Strong downtrend: -0.3 %/day (~-53 % over a year)."""
    return [round(200.0 * (0.997 ** i), 4) for i in range(n)]


def _flat(n=252, price=150.0):
    """Perfectly flat prices — zero variance."""
    return [price] * n


def _overbought(n=252):
    """Stable base price, then sharp spike in last 20 days → overbought."""
    np.random.seed(0)
    prices = np.full(n, 100.0) + np.random.normal(0, 0.4, n)
    prices[-20:] = 140.0 + np.random.normal(0, 0.4, 20)
    return [round(float(p), 4) for p in prices]


def _oversold(n=252):
    """Stable base price, then sharp drop in last 20 days → oversold."""
    np.random.seed(1)
    prices = np.full(n, 100.0) + np.random.normal(0, 0.4, n)
    prices[-20:] = 60.0 + np.random.normal(0, 0.4, 20)
    return [round(float(p), 4) for p in prices]


def _make_mock_info(pe=20.0, fwd_pe=18.0, roe=0.25, margin=0.30,
                    market_cap=1e12):
    return {
        "symbol": "TEST",
        "shortName": "Test Corp",
        "trailingPE": pe,
        "forwardPE": fwd_pe,
        "returnOnEquity": roe,
        "profitMargins": margin,
        "marketCap": market_cap,
        "sector": "Technology",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Momentum
# ─────────────────────────────────────────────────────────────────────────────

class TestMomentumStrategy(unittest.TestCase):

    def _run(self, prices, spy_prices=None):
        from strategies.momentum import calculate_momentum
        df = _make_df(prices)
        spy_df = _make_df(spy_prices if spy_prices is not None
                          else _flat(len(prices), 500.0))

        def mock_hist(sym, period="1y"):
            return spy_df if sym.upper() == "SPY" else df

        with patch("strategies.momentum.get_historical_dataframe",
                   side_effect=mock_hist):
            return calculate_momentum("TEST")

    def test_bullish_returns_buy(self):
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "BUY")
        self.assertGreater(r["score"], 0.2)

    def test_bearish_returns_sell(self):
        r = self._run(_downtrend(), spy_prices=_flat(252, 500.0))
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "SELL")
        self.assertLess(r["score"], -0.2)

    def test_insufficient_data_returns_none(self):
        self.assertIsNone(self._run(_uptrend(n=30)))

    def test_score_always_in_bounds(self):
        for prices in [_uptrend(), _downtrend()]:
            r = self._run(prices)
            if r:
                self.assertGreaterEqual(r["score"], -1.0)
                self.assertLessEqual(r["score"],    1.0)

    def test_has_required_keys(self):
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        for key in ("score", "signal", "details"):
            self.assertIn(key, r)

    def test_outperforming_spy_scores_higher(self):
        """Stock outperforming SPY should score higher than SPY-tracking stock."""
        spy = _flat(252, 500.0)
        r_strong = self._run(_uptrend(),          spy_prices=spy)
        r_flat   = self._run(_flat(252, 100.0),   spy_prices=spy)
        self.assertGreater(r_strong["score"],
                           r_flat["score"] if r_flat else -2)

    def test_roc_divisor_fix(self):
        """
        Regression: ROC signal was divided by 2 instead of 5 (sum of weights
        3 + 2). After the fix all scores must stay within [-1, 1].
        """
        prices_short = (_flat(232, 100.0)
                        + [round(100.0 * (1.015 ** i), 4) for i in range(20)])
        for prices in [prices_short, _uptrend()]:
            r = self._run(prices)
            if r:
                self.assertLessEqual(abs(r["score"]), 1.0,
                                     "ROC divisor bug would push score past ±1")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mean Reversion
# ─────────────────────────────────────────────────────────────────────────────

class TestMeanReversionStrategy(unittest.TestCase):

    def _run(self, prices):
        from strategies.mean_reversion import calculate_mean_reversion
        with patch("strategies.mean_reversion.get_historical_dataframe",
                   return_value=_make_df(prices)):
            return calculate_mean_reversion("TEST")

    def test_oversold_returns_buy(self):
        r = self._run(_oversold())
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "BUY")

    def test_overbought_returns_sell(self):
        r = self._run(_overbought())
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "SELL")

    def test_insufficient_data_returns_none(self):
        self.assertIsNone(self._run(_flat(n=10)))

    def test_zero_std_returns_hold(self):
        """
        Improvement: flat prices used to return None (error path).
        After the fix, zero rolling_std returns HOLD instead.
        """
        r = self._run(_flat(n=252))
        self.assertIsNotNone(r, "Flat prices should return HOLD, not None")
        self.assertEqual(r["signal"], "HOLD")

    def test_score_in_bounds(self):
        for prices in [_oversold(), _overbought()]:
            r = self._run(prices)
            if r:
                self.assertGreaterEqual(r["score"], -1.0)
                self.assertLessEqual(r["score"],    1.0)

    def test_has_required_keys(self):
        r = self._run(_oversold())
        if r:
            for key in ("score", "signal", "details"):
                self.assertIn(key, r)

    def test_details_contains_zscore(self):
        r = self._run(_oversold())
        if r:
            self.assertIn("Z-score", r["details"])

    def test_50day_lookback_detects_reversion(self):
        """
        50-day mean (improvement) detects a crash even when the last 20 days
        are uniformly low — the old 20-day-only window would miss this because
        the current price equals the 20-day mean (z-score ≈ 0 → HOLD).
        With the 50-day mean, the drop is clearly visible → BUY.
        """
        np.random.seed(42)
        prices = ([100.0 + float(np.random.normal(0, 0.3)) for _ in range(232)]
                  + [60.0  + float(np.random.normal(0, 0.5)) for _ in range(20)])
        r = self._run(prices)
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "BUY")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────

class TestMonteCarloStrategy(unittest.TestCase):

    def _run(self, prices):
        from strategies.monte_carlo import calculate_monte_carlo
        with patch("strategies.monte_carlo.get_historical_dataframe",
                   return_value=_make_df(prices)):
            return calculate_monte_carlo("TEST")

    def test_has_required_keys(self):
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        for key in ("score", "signal", "details"):
            self.assertIn(key, r)

    def test_insufficient_data_returns_none(self):
        self.assertIsNone(self._run(_uptrend(n=30)))

    def test_score_in_bounds(self):
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["score"], -1.0)
        self.assertLessEqual(r["score"],    1.0)

    def test_uptrend_positive_score(self):
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        self.assertGreater(r["score"], 0)

    def test_downtrend_negative_score(self):
        r = self._run(_downtrend())
        self.assertIsNotNone(r)
        self.assertLess(r["score"], 0)

    def test_reproducibility(self):
        """seed=42 guarantees identical output across repeated calls."""
        r1 = self._run(_uptrend())
        r2 = self._run(_uptrend())
        self.assertEqual(r1["score"], r2["score"])

    def test_details_contains_var_and_cvar(self):
        """Improvement: CVaR should now appear alongside VaR in the details."""
        r = self._run(_uptrend())
        self.assertIsNotNone(r)
        self.assertIn("VaR",  r["details"])
        self.assertIn("CVaR", r["details"])

    def test_cvar_penalizes_high_volatility(self):
        """
        Two series with identical drift but different volatility, built from
        deterministic alternating log-returns so mu and sigma are exact.
        High-vol (sigma=5%): large CVaR → heavy risk penalty → lower score.
        Low-vol  (sigma=0.5%): tiny CVaR → no penalty → higher score.
        """
        # mu must exceed 0.5*sigma^2 for the GBM drift to stay positive after
        # the Itô correction (drift = mu - 0.5*sigma^2).
        # sigma_high=0.05 → need mu > 0.00125; use mu=0.003 for clear margin.
        mu = 0.003
        n  = 252

        def _from_log_rets(rets):
            prices = [100.0]
            for r in rets:
                prices.append(prices[-1] * float(np.exp(r)))
            return prices[1:]

        high_vol = _from_log_rets(
            [mu + 0.05  * (1 if i % 2 == 0 else -1) for i in range(n)])
        low_vol  = _from_log_rets(
            [mu + 0.005 * (1 if i % 2 == 0 else -1) for i in range(n)])

        r_high = self._run(high_vol)
        r_low  = self._run(low_vol)
        if r_high and r_low:
            self.assertLessEqual(r_high["score"], r_low["score"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Factor Model
# ─────────────────────────────────────────────────────────────────────────────

_MISSING = object()  # sentinel so _run(info=None) actually passes None through


class TestFactorModelStrategy(unittest.TestCase):

    def _run(self, info=_MISSING, prices=None):
        from strategies.factor_model import calculate_factor_model
        info   = _make_mock_info() if info is _MISSING else info
        prices = prices if prices is not None else _uptrend()
        with patch("strategies.factor_model.get_ticker_info_raw",
                   return_value=info), \
             patch("strategies.factor_model.get_historical_dataframe",
                   return_value=_make_df(prices)):
            return calculate_factor_model("TEST")

    def test_has_required_keys(self):
        r = self._run()
        self.assertIsNotNone(r)
        for key in ("score", "signal", "details"):
            self.assertIn(key, r)

    def test_no_info_returns_none(self):
        self.assertIsNone(self._run(info=None))

    def test_score_in_bounds(self):
        r = self._run()
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["score"], -1.0)
        self.assertLessEqual(r["score"],    1.0)

    def test_high_quality_scores_positive(self):
        info = _make_mock_info(pe=12.0, fwd_pe=10.0, roe=0.45, margin=0.40,
                               market_cap=2e12)
        r = self._run(info=info)
        self.assertIsNotNone(r)
        self.assertGreater(r["score"], 0)

    def test_low_quality_scores_negative(self):
        info = _make_mock_info(pe=250.0, fwd_pe=220.0, roe=0.01, margin=0.001,
                               market_cap=1e8)
        r = self._run(info=info)
        self.assertIsNotNone(r)
        self.assertLess(r["score"], 0)

    def test_missing_pe_still_returns_result(self):
        """Quality + volatility + size factors keep the model running."""
        info = _make_mock_info()
        info.pop("trailingPE", None)
        info.pop("forwardPE",  None)
        self.assertIsNotNone(self._run(info=info))

    def test_empty_info_returns_none(self):
        from strategies.factor_model import calculate_factor_model
        with patch("strategies.factor_model.get_ticker_info_raw",
                   return_value={}), \
             patch("strategies.factor_model.get_historical_dataframe",
                   return_value=None):
            self.assertIsNone(calculate_factor_model("TEST"))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Signal Aggregator
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalAggregator(unittest.TestCase):

    @staticmethod
    def _sig(score):
        sig = "BUY" if score > 0.2 else ("SELL" if score < -0.2 else "HOLD")
        return {"score": score, "signal": sig, "details": "mock"}

    def _run(self, m=None, mr=None, mc=None, fm=None):
        from strategies.signal_aggregator import get_aggregated_signal
        with patch("strategies.signal_aggregator.calculate_momentum",
                   return_value=m),  \
             patch("strategies.signal_aggregator.calculate_mean_reversion",
                   return_value=mr), \
             patch("strategies.signal_aggregator.calculate_monte_carlo",
                   return_value=mc), \
             patch("strategies.signal_aggregator.calculate_factor_model",
                   return_value=fm):
            return get_aggregated_signal("TEST")

    def test_all_active_returns_result(self):
        r = self._run(self._sig(0.5), self._sig(0.4),
                      self._sig(0.3), self._sig(0.6))
        self.assertIsNotNone(r)
        for key in ("symbol", "signal", "confidence", "breakdown"):
            self.assertIn(key, r)

    def test_all_none_returns_none(self):
        self.assertIsNone(self._run(None, None, None, None))

    def test_weight_redistribution_partial_none(self):
        """2 active strategies → weights redistribute; result is still valid."""
        r = self._run(self._sig(0.5), None, self._sig(0.4), None)
        self.assertIsNotNone(r)
        self.assertEqual(r["signal"], "BUY")

    def test_buy_threshold(self):
        r = self._run(self._sig(0.8), self._sig(0.7),
                      self._sig(0.6), self._sig(0.9))
        self.assertEqual(r["signal"], "BUY")

    def test_sell_threshold(self):
        r = self._run(self._sig(-0.8), self._sig(-0.7),
                      self._sig(-0.6), self._sig(-0.9))
        self.assertEqual(r["signal"], "SELL")

    def test_hold_range(self):
        r = self._run(self._sig(0.05), self._sig(-0.05),
                      self._sig(0.0),  self._sig(0.02))
        self.assertEqual(r["signal"], "HOLD")

    def test_confidence_always_in_bounds(self):
        for scores in [(0.9, 0.8, 0.9, 0.7),
                       (-0.9, -0.8, -0.9, -0.7),
                       (0, 0, 0, 0)]:
            r = self._run(*[self._sig(s) for s in scores])
            if r:
                self.assertGreaterEqual(r["confidence"], 30)
                self.assertLessEqual(r["confidence"],   100)

    def test_agreement_boosts_confidence(self):
        """All strategies agreeing → higher confidence than mixed signals."""
        agreed = self._run(self._sig(0.5), self._sig(0.4),
                           self._sig(0.6), self._sig(0.3))
        mixed  = self._run(self._sig(0.5), self._sig(-0.4),
                           self._sig(0.6), self._sig(-0.3))
        self.assertGreater(agreed["confidence"], mixed["confidence"])

    def test_coverage_penalty_lowers_confidence(self):
        """4 active strategies → higher confidence than 1 active strategy."""
        four = self._run(self._sig(0.5), self._sig(0.4),
                         self._sig(0.6), self._sig(0.3))
        one  = self._run(self._sig(0.5), None, None, None)
        self.assertGreater(four["confidence"], one["confidence"])

    def test_breakdown_has_all_four_keys(self):
        r = self._run(self._sig(0.5), self._sig(0.3),
                      self._sig(0.4), self._sig(0.2))
        for k in ("momentum", "mean_reversion", "monte_carlo", "factor_model"):
            self.assertIn(k, r["breakdown"])

    def test_magnitude_weighted_agreement(self):
        """
        Improvement: agreement is now magnitude-weighted.
        Four strategies all agreeing with high scores should yield equal or
        higher confidence than the same count agreeing with low scores.
        """
        high_agree = self._run(self._sig(0.8), self._sig(0.7),
                               self._sig(0.8), self._sig(0.7))
        low_agree  = self._run(self._sig(0.8), self._sig(0.05),
                               self._sig(0.8), self._sig(0.05))
        self.assertGreaterEqual(high_agree["confidence"],
                                low_agree["confidence"])


# ─────────────────────────────────────────────────────────────────────────────
# 6. Cumulative Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestCumulativeIntegration(unittest.TestCase):
    """
    Run all four strategies sequentially then pipe their outputs through the
    signal aggregator — mirrors exactly what the /api/signals endpoint does.
    All data fetching is mocked; no internet connection required.
    """

    def _full_run(self, prices, info=None):
        from strategies.momentum        import calculate_momentum
        from strategies.mean_reversion  import calculate_mean_reversion
        from strategies.monte_carlo     import calculate_monte_carlo
        from strategies.factor_model    import calculate_factor_model
        from strategies.signal_aggregator import get_aggregated_signal

        info   = info if info is not None else _make_mock_info()
        df     = _make_df(prices)
        spy_df = _make_df(_flat(len(prices), 500.0))

        def mock_hist(sym, period="1y"):
            return spy_df if sym.upper() == "SPY" else df

        with patch("strategies.momentum.get_historical_dataframe",
                   side_effect=mock_hist), \
             patch("strategies.mean_reversion.get_historical_dataframe",
                   return_value=df), \
             patch("strategies.monte_carlo.get_historical_dataframe",
                   return_value=df), \
             patch("strategies.factor_model.get_historical_dataframe",
                   return_value=df), \
             patch("strategies.factor_model.get_ticker_info_raw",
                   return_value=info):
            mom      = calculate_momentum("TEST")
            mean_rev = calculate_mean_reversion("TEST")
            monte    = calculate_monte_carlo("TEST")
            factor   = calculate_factor_model("TEST")
            agg      = get_aggregated_signal("TEST")

        return mom, mean_rev, monte, factor, agg

    def test_bullish_scenario_all_strategies_active(self):
        info = _make_mock_info(pe=14.0, fwd_pe=11.0, roe=0.38, margin=0.42,
                               market_cap=2e12)
        mom, mr, mc, fm, agg = self._full_run(_uptrend(), info=info)

        self.assertIsNotNone(mom, "Momentum should produce a result")
        self.assertIsNotNone(mc,  "Monte Carlo should produce a result")
        self.assertIsNotNone(fm,  "Factor model should produce a result")
        self.assertIsNotNone(agg, "Aggregator should produce a result")

        self.assertGreater(mom["score"], 0, "Momentum positive in uptrend")
        self.assertGreater(mc["score"],  0, "Monte Carlo positive in uptrend")
        self.assertIn(agg["signal"], ("BUY", "SELL", "HOLD"))
        self.assertGreaterEqual(agg["confidence"], 30)
        self.assertLessEqual(agg["confidence"],   100)

    def test_bearish_scenario_aggregate_is_valid(self):
        info = _make_mock_info(pe=350.0, fwd_pe=300.0, roe=0.01, margin=0.002,
                               market_cap=5e7)
        _, _, _, _, agg = self._full_run(_downtrend(), info=info)
        self.assertIsNotNone(agg)
        self.assertIn(agg["signal"], ("BUY", "SELL", "HOLD"))

    def test_weighted_score_matches_expected_signal(self):
        """Verify the aggregator produces the signal implied by weighted avg."""
        from strategies.signal_aggregator import get_aggregated_signal, WEIGHTS

        scores = {"momentum": 0.60, "mean_reversion": 0.40,
                  "monte_carlo": 0.50, "factor_model": 0.30}

        def make(s):
            sig = "BUY" if s > 0.2 else ("SELL" if s < -0.2 else "HOLD")
            return {"score": s, "signal": sig, "details": "test"}

        with patch("strategies.signal_aggregator.calculate_momentum",
                   return_value=make(scores["momentum"])),       \
             patch("strategies.signal_aggregator.calculate_mean_reversion",
                   return_value=make(scores["mean_reversion"])), \
             patch("strategies.signal_aggregator.calculate_monte_carlo",
                   return_value=make(scores["monte_carlo"])),    \
             patch("strategies.signal_aggregator.calculate_factor_model",
                   return_value=make(scores["factor_model"])):
            result = get_aggregated_signal("TEST")

        expected = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
        expected_signal = ("BUY"  if expected >  0.15 else
                           "SELL" if expected < -0.15 else "HOLD")
        self.assertEqual(result["signal"], expected_signal)

    def test_all_mock_symbols_produce_valid_results(self):
        """
        Run the full aggregator pipeline against all 12 built-in mock stocks.
        Forces mock data fallback so no internet is required.
        """
        import services.data_fetcher as df_mod
        from strategies.signal_aggregator import get_aggregated_signal

        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA",
                   "META", "JPM", "V", "JNJ", "WMT", "DIS"]
        valid_signals = {"BUY", "SELL", "HOLD"}
        failures = []

        original = df_mod._yfinance_available
        df_mod._yfinance_available = False          # bypass network check
        try:
            for sym in symbols:
                try:
                    r = get_aggregated_signal(sym)
                    if r is None:
                        failures.append(f"{sym}: returned None")
                    elif r["signal"] not in valid_signals:
                        failures.append(f"{sym}: invalid signal '{r['signal']}'")
                except Exception as exc:
                    failures.append(f"{sym}: exception — {exc}")
        finally:
            df_mod._yfinance_available = original   # restore

        self.assertEqual(failures, [],
                         "Failed symbols:\n" + "\n".join(failures))

    def test_unanimous_direction_matches_aggregate(self):
        """When all 4 strategies strongly agree the aggregate must match."""
        from strategies.signal_aggregator import get_aggregated_signal

        for direction, score in [("BUY", 0.8), ("SELL", -0.8)]:
            sig = {"score": score, "signal": direction, "details": "mock"}
            with patch("strategies.signal_aggregator.calculate_momentum",
                       return_value=sig), \
                 patch("strategies.signal_aggregator.calculate_mean_reversion",
                       return_value=sig), \
                 patch("strategies.signal_aggregator.calculate_monte_carlo",
                       return_value=sig), \
                 patch("strategies.signal_aggregator.calculate_factor_model",
                       return_value=sig):
                r = get_aggregated_signal("TEST")
            self.assertEqual(r["signal"], direction,
                             f"Expected {direction} when all strategies agree")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
