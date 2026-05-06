# Author: Kevin Ngo, 4/25/26
# Stock data pipeline with caching, API integration, and mock fallback support.

import os
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


# Kevin Ngo, 4/25/26 - in-memory cache storage for API responses
_cache = {}

# Kevin Ngo, 4/25/26 - cache expiration time (seconds)
_DEFAULT_TTL = int(os.environ.get("CACHE_TTL", 300))

# Kevin Ngo, 4/25/26 - timeout for external API requests
_REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 10))

# Kevin Ngo, 4/25/26 - tracks whether Yahoo Finance is available
_yfinance_available = None


def _cache_get(key, ttl=_DEFAULT_TTL):
    # Kevin Ngo, 4/25/26 - retrieve cached value if still valid
    if key in _cache:
        ts, data = _cache[key]

        if time.time() - ts < ttl:
            return data

        del _cache[key]

    return None


def _cache_set(key, data):
    # Kevin Ngo, 4/25/26 - store value in cache with timestamp
    _cache[key] = (time.time(), data)


def _check_yfinance():
    # Kevin Ngo, 4/25/26 - checks if Yahoo Finance API is working
    global _yfinance_available

    if _yfinance_available is not None:
        return _yfinance_available

    try:
        import yfinance as yf

        ticker = yf.Ticker("AAPL")
        hist = ticker.history(period="5d", timeout=_REQUEST_TIMEOUT)

        _yfinance_available = not hist.empty

    except Exception:
        _yfinance_available = False

    return _yfinance_available


# Kevin Ngo, 4/25/26 - fallback dataset when API is unavailable
_MOCK_STOCKS = {
    "AAPL": {"name": "Apple Inc.", "price": 189.50, "prev_close": 187.20, "volume": 54000000},
    "MSFT": {"name": "Microsoft Corp.", "price": 415.30, "prev_close": 411.80, "volume": 22000000},
    "GOOGL": {"name": "Alphabet Inc.", "price": 153.80, "prev_close": 152.10, "volume": 28000000},
}


def _generate_mock_history(mock, period="1y"):
    # Kevin Ngo, 4/25/26 - generates simulated historical stock data
    period_days = {"1mo": 22, "3mo": 63, "6mo": 126, "1y": 252}
    days = period_days.get(period, 252)

    np.random.seed(hash(mock["name"]) % 2**31)

    base_price = mock["price"]
    returns = np.random.normal(0.0003, 0.015, days)

    prices = np.zeros(days)
    prices[-1] = base_price

    for i in range(days - 2, -1, -1):
        prices[i] = prices[i + 1] / (1 + returns[i + 1])

    records = []
    start_date = datetime.now() - timedelta(days=days)

    trading_day = 0
    current = start_date

    while trading_day < days:
        if current.weekday() < 5:
            p = prices[trading_day]

            records.append({
                "date": current.strftime("%Y-%m-%d"),
                "open": round(p * 0.99, 2),
                "high": round(p * 1.01, 2),
                "low": round(p * 0.98, 2),
                "close": round(p, 2),
                "volume": int(mock["volume"] * (0.8 + np.random.random() * 0.4)),
            })

            trading_day += 1

        current += timedelta(days=1)

    return records


def search_stocks(query):
    # Kevin Ngo, 4/25/26 - search stocks using API or fallback
    results = []

    if _check_yfinance():
        try:
            import yfinance as yf

            search = yf.Search(query, max_results=5)

            if hasattr(search, "quotes"):
                for q in search.quotes:
                    results.append({
                        "symbol": q.get("symbol"),
                        "name": q.get("shortname", q.get("symbol")),
                    })

        except Exception:
            pass

    if not results:
        for sym, data in _MOCK_STOCKS.items():
            if query.upper() in sym:
                results.append({
                    "symbol": sym,
                    "name": data["name"]
                })

    return results


def get_stock_info(symbol):
    # Kevin Ngo, 4/25/26 - get current stock info
    symbol = symbol.upper()

    if _check_yfinance():
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)

            fi = ticker.fast_info

            price = fi.last_price
            prev = fi.previous_close or 0

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "change": round(price - prev, 2) if prev else 0,
                "changePercent": round(((price - prev) / prev) * 100, 2) if prev else 0,
            }

        except Exception:
            pass

    mock = _MOCK_STOCKS.get(symbol)

    if not mock:
        return None

    return {
        "symbol": symbol,
        "price": mock["price"],
        "change": mock["price"] - mock["prev_close"],
    }


def get_stock_history(symbol, period="1y"):
    # Kevin Ngo, 4/25/26 - get historical stock data
    symbol = symbol.upper()

    if _check_yfinance():
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)

            hist = ticker.history(period=period)

            if not hist.empty:
                return {
                    "symbol": symbol,
                    "history": [
                        {
                            "date": str(i.date()),
                            "open": row["Open"],
                            "close": row["Close"],
                        }
                        for i, row in hist.iterrows()
                    ]
                }

        except Exception:
            pass

    mock = _MOCK_STOCKS.get(symbol)

    if not mock:
        return None

    return {
        "symbol": symbol,
        "history": _generate_mock_history(mock, period)
    }
