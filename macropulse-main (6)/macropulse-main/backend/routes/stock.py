# Author: Kevin Ngo, 4/11/26

from datetime import datetime, timezone
from flask import Blueprint, jsonify, make_response, request
from services.data_fetcher import get_stock_history, get_stock_info
import re

# Kevin Ngo, 4/11/26 - Stock API routes for Macropulse backend
# Handles stock info + historical price data with validation and safe responses

stock_bp = Blueprint("stock", __name__)

# Kevin Ngo, 4/11/26 - Allowed time ranges for historical stock data
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}

# Kevin Ngo, 4/11/26 - Short user-friendly aliases mapped to valid API periods
PERIOD_ALIASES = {
    "1m": "1mo",
    "3m": "3mo",
    "6m": "6mo",
    "12m": "1y",
}

# Kevin Ngo, 4/11/26 - Regex pattern to validate stock symbols
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-^=]{1,15}$")


def _normalize_symbol(symbol):
    # Kevin Ngo, 4/11/26 - Clean and standardize stock symbol input
    normalized = (symbol or "").strip().upper().replace(" ", "")

    # Kevin Ngo, 4/11/26 - Convert dot notation to hyphen format if needed
    if "." in normalized and "-" not in normalized:
        normalized = normalized.replace(".", "-")

    return normalized


def _normalize_period(raw_period):
    # Kevin Ngo, 4/11/26 - Normalize user input for time period
    period = (raw_period or "1y").strip().lower()

    # Kevin Ngo, 4/11/26 - Convert aliases into valid API values
    period = PERIOD_ALIASES.get(period, period)

    return period


def _response(payload, status=200, cache_seconds=None):
    # Kevin Ngo, 4/11/26 - Standard API response wrapper with security headers
    response = make_response(jsonify(payload), status)

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["Cache-Control"] = (
        f"public, max-age={cache_seconds}"
        if cache_seconds is not None
        else "no-store"
    )

    return response


def _error(message, status=400, **extra):
    # Kevin Ngo, 4/11/26 - Standard error response format
    payload = {"error": message, **extra}
    return _response(payload, status=status, cache_seconds=0)


def _request_meta(symbol, period=None):
    # Kevin Ngo, 4/11/26 - Adds request metadata for debugging/tracking
    meta = {
        "symbol": symbol,
        "requestedAt": datetime.now(timezone.utc).isoformat(),
    }

    if period is not None:
        meta["period"] = period

    return meta


@stock_bp.route("/stock/<symbol>")
def stock_info(symbol):
    # Kevin Ngo, 4/11/26 - Fetch and return stock info for a symbol
    normalized_symbol = _normalize_symbol(symbol)

    if not normalized_symbol:
        return _error("Stock symbol is required.")

    if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
        return _error(
            f"Invalid stock symbol '{symbol}'. Use letters, numbers, '.', '-', '^', or '='.",
            status=400,
        )

    try:
        data = get_stock_info(normalized_symbol)
    except Exception:
        return _error(
            f"Unable to load stock data for '{normalized_symbol}'. Please try again.",
            status=502,
            meta=_request_meta(normalized_symbol),
        )

    if data is None:
        return _error(
            f"Stock '{normalized_symbol}' not found",
            status=404,
            meta=_request_meta(normalized_symbol),
        )

    payload = dict(data)
    payload["meta"] = _request_meta(normalized_symbol)

    return _response(payload, status=200, cache_seconds=60)


@stock_bp.route("/stock/<symbol>/history")
def stock_history(symbol):
    # Kevin Ngo, 4/11/26 - Fetch historical stock price data
    normalized_symbol = _normalize_symbol(symbol)

    if not normalized_symbol:
        return _error("Stock symbol is required.")

    if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
        return _error(
            f"Invalid stock symbol '{symbol}'. Use letters, numbers, '.', '-', '^', or '='.",
            status=400,
        )

    period = _normalize_period(request.args.get("period", "1y"))

    if period not in VALID_PERIODS:
        return _error(
            f"Invalid period '{period}'. Use one of: {sorted(VALID_PERIODS)}",
            status=400,
            meta=_request_meta(normalized_symbol, period=period),
        )

    try:
        data = get_stock_history(normalized_symbol, period=period)
    except Exception:
        return _error(
            f"Unable to load price history for '{normalized_symbol}'. Please try again.",
            status=502,
            meta=_request_meta(normalized_symbol, period=period),
        )

    if data is None:
        return _error(
            f"No history found for '{normalized_symbol}'",
            status=404,
            meta=_request_meta(normalized_symbol, period=period),
        )

    history = data.get("history", [])

    payload = {
        "symbol": data.get("symbol", normalized_symbol),
        "history": history,
        "period": period,
        "points": len(history),
        "meta": _request_meta(normalized_symbol, period=period),
    }

    return _response(payload, status=200, cache_seconds=300)
