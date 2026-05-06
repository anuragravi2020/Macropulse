/**
 * Macropulse API Client
 * Fetch wrapper for all backend calls with error handling and loading states.
 */

const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || `${window.location.origin}/api`;

async function apiRequest(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
    }
    return response.json();
}

/**
 * Search stocks by query string.
 * GET /api/search?q=<query>
 */
async function searchStocks(query) {
    if (!query || query.trim().length === 0) return { results: [] };
    return apiRequest(`/search?q=${encodeURIComponent(query.trim())}`);
}

/**
 * Get current stock info.
 * GET /api/stock/<symbol>
 */
async function getStock(symbol) {
    return apiRequest(`/stock/${encodeURIComponent(symbol)}`);
}

/**
 * Get historical OHLCV data.
 * GET /api/stock/<symbol>/history?period=1y
 */
async function getStockHistory(symbol, period = "1y") {
    return apiRequest(`/stock/${encodeURIComponent(symbol)}/history?period=${period}`);
}

/**
 *
 * GET /api/signals/<symbol>
 */
async function getSignals(symbol) {
    return apiRequest(`/signals/${encodeURIComponent(symbol)}`);
}
