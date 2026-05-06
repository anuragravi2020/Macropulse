# Macropulse - Quantitative Stock Signals Platform

A web application that provides quantitative analysis and trading signals for stocks using a multi-strategy ensemble approach. It combines **Momentum**, **Mean Reversion**, **Monte Carlo simulations**, and **Factor Models** to generate BUY/SELL/HOLD signals with confidence scores.

---

## How to Run

### Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)
- A modern web browser (Chrome, Firefox, Edge)

### Step 1: Set up the Backend

```bash
# Navigate to backend directory
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
# From the backend directory (with venv activated)
python app.py
```

The server starts at **http://localhost:5000**

### Step 3: Open the App

Open your browser and go to:

- **Dashboard:** http://localhost:5000/
- **Stock Page Example:** http://localhost:5000/stock.html?symbol=AAPL

That's it! No npm install, no build step needed. The frontend is pure HTML/CSS/JS served directly by Flask.

---

## Tech Stack

| Layer    | Technology                          |
| -------- | ----------------------------------- |
| Frontend | Vanilla JS, HTML5, CSS3             |
| Charts   | Chart.js 4.4.1 (CDN)               |
| Icons    | Font Awesome 6.5.1 (CDN)           |
| Backend  | Python Flask 3.1.0                  |
| Data     | Yahoo Finance (yfinance) + fallback mock data |
| Caching  | In-memory TTL cache (5 min)         |

---

## Project Structure

```
Macropulse/
├── frontend/                      # Frontend web application
│   ├── index.html                 # Dashboard / home page
│   ├── stock.html                 # Individual stock details page
│   ├── js/
│   │   ├── api.js                 # API client wrapper with error handling
│   │   ├── app.js                 # Dashboard logic (search, trending stocks)
│   │   ├── stock.js               # Stock page logic (signals, metrics)
│   │   └── charts.js              # Chart.js price & volume visualization
│   └── css/
│       └── style.css              # Full design system & styling (dark theme)
│
├── backend/                       # Flask Python backend
│   ├── app.py                     # Flask entry point & server config
│   ├── requirements.txt           # Python dependencies
│   ├── routes/
│   │   ├── search.py              # GET /api/search - stock search
│   │   ├── stock.py               # GET /api/stock/* - stock info & history
│   │   └── signals.py             # GET /api/signals/* - quant signals
│   ├── services/
│   │   └── data_fetcher.py        # Yahoo Finance integration, caching, mock data
│   └── strategies/
│       ├── signal_aggregator.py   # Weighted ensemble of all 4 strategies
│       ├── momentum.py            # Momentum strategy (30% weight)
│       ├── mean_reversion.py      # Mean reversion strategy (25% weight)
│       ├── monte_carlo.py         # Monte Carlo simulation (25% weight)
│       └── factor_model.py        # Multi-factor model (20% weight)
│
└── README.md
```

---

## API Endpoints

| Method | Endpoint                          | Description                        |
| ------ | --------------------------------- | ---------------------------------- |
| GET    | `/api/search?q=<query>`          | Search stocks by name or symbol    |
| GET    | `/api/stock/<symbol>`            | Get current stock info & metrics   |
| GET    | `/api/stock/<symbol>/history?period=<period>` | Get OHLCV price history |
| GET    | `/api/signals/<symbol>`          | Get quant signal (BUY/SELL/HOLD)   |

**Valid history periods:** `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`

### Example Responses

**Search:**
```
GET /api/search?q=apple
→ [{ "symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ" }]
```

**Stock Info:**
```
GET /api/stock/AAPL
→ { "symbol": "AAPL", "name": "Apple Inc.", "price": 189.84, "change": 2.45, "changePercent": 1.31, "volume": 54230100, "marketCap": 2950000000000, ... }
```

**Signals:**
```
GET /api/signals/AAPL
→ { "signal": "BUY", "confidence": 72, "strategies": { "momentum": {...}, "mean_reversion": {...}, "monte_carlo": {...}, "factor_model": {...} } }
```

---

## Features

### Dashboard (Home Page)
- **Real-time search** with debounced autocomplete (350ms)
- **Trending stocks grid** — AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA
- **Popular watchlist** — META, JPM, V, JNJ, WMT, DIS
- Color-coded stock cards (green = up, red = down)

### Stock Details Page
- Stock name, symbol, sector, current price with change indicator
- **Quant signal badge** (BUY/SELL/HOLD) with confidence bar
- **Strategy breakdown** — 4 cards showing each strategy's individual signal and score
- **Key metrics** — Market Cap, Volume, 52W High/Low, P/E Ratio, Forward P/E
- **Interactive price chart** with time period selector (1M, 3M, 6M, 1Y, 2Y, 5Y)
- Volume bars overlaid on the price chart

---

## Quantitative Strategies

The signal engine combines 4 independent strategies using weighted ensemble voting:

### 1. Momentum (30% weight)
- Analyzes 12-month absolute return
- Rate of Change (20-day and 60-day)
- Relative outperformance vs S&P 500 (SPY)

### 2. Mean Reversion (25% weight)
- Z-score of current price vs 20-day moving average
- Bollinger Band %B indicator
- Identifies oversold (buy) and overbought (sell) conditions

### 3. Monte Carlo Simulation (25% weight)
- 1,000 simulated price paths using Geometric Brownian Motion
- 30-day forecast horizon
- Uses historical volatility and drift from 252-day data
- Signal based on probability of price increase

### 4. Factor Model (20% weight)
- **Value factor (35%):** P/E ratio scoring
- **Quality factor (30%):** ROE and profit margins
- **Volatility factor (35%):** Lower volatility preferred

### Final Signal
| Aggregate Score | Signal |
| --------------- | ------ |
| > 0.15          | BUY    |
| < -0.15         | SELL   |
| -0.15 to 0.15   | HOLD   |

Confidence ranges from 30% to 100% based on score magnitude.

---

## Data & Caching

- **Primary source:** Yahoo Finance via `yfinance` library (live market data)
- **Fallback:** Built-in mock data for 12 stocks (works offline)
- **Cache:** In-memory with 5-minute TTL — reduces redundant API calls
- **No database required** — all data is fetched at runtime

The app automatically falls back to mock data if Yahoo Finance is unreachable, so it works without an internet connection.

---

## Supported Stocks (Mock Data Fallback)

AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, V, JNJ, WMT, DIS

With an internet connection, you can search for any stock available on Yahoo Finance.

---

## Design

- Dark theme inspired by GitHub's dark mode
- Color palette: `#0d1117` (background), `#58a6ff` (accent blue), `#3fb950` (buy/green), `#f85149` (sell/red), `#d29922` (hold/yellow)
- Fully responsive layout
- Max container width: 1200px

---

## Dependencies

### Backend (requirements.txt)
```
flask==3.1.0
flask-cors==5.0.1
yfinance==0.2.51
numpy==2.2.3
pandas==2.2.3
```

### Frontend (loaded via CDN, no install needed)
- Chart.js 4.4.1
- Font Awesome 6.5.1

---

## Data Flow

```
User Action → Frontend JS → HTTP Request → Flask Route → Data Fetcher
    → Check Cache → Hit? Return cached : Fetch from Yahoo Finance / Mock
    → Store in Cache → Return JSON → Frontend renders UI
```

---

## Notes

- The Flask server runs in **debug mode** by default (for development)
- CORS is fully enabled (any origin allowed)
- No authentication or user accounts
- No persistent storage — cache resets on server restart
- For production use, consider adding a WSGI server (gunicorn), rate limiting, and authentication
