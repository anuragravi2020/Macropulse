/**
 * Macropulse - Stock Page Logic
 * Loads stock info, signals, and chart for the given symbol.
 */

let currentSymbol = null;

document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    currentSymbol = params.get("symbol");

    if (!currentSymbol) {
        showError("No stock symbol provided.");
        return;
    }
/* Yash Patel, 04/17/2026
call new function with save button*/

    document.title = `${currentSymbol.toUpperCase()} - Macropulse`;
    initSaveButton();
    loadStockPage(currentSymbol);
    initChartControls();
});

async function loadStockPage(symbol) {
    try {
        // Load stock info first
        const stockData = await getStock(symbol);
        renderStockHero(stockData);

        // Show content, hide loading
        document.getElementById("page-loading").style.display = "none";
        document.getElementById("stock-content").style.display = "block";

        // Load signals and chart in parallel
        loadSignals(symbol);
        loadChart(symbol, "1y");
    } catch (err) {
        showError(err.message || `Could not find stock "${symbol}".`);
    }
}

/* Anurag Ravi, 04/23/2026
Skeleton loader functions for the metrics and strategy sections */
function showMetricsSkeleton() {
    const grid = document.getElementById("metrics-grid");
    if (!grid) return;
    grid.innerHTML = Array(6).fill(`
        <div class="metric-item">
            <div class="skeleton skeleton-label"></div>
            <div class="skeleton skeleton-value"></div>
        </div>
    `).join("");
}

function showStrategySkeleton() {
    const grid = document.getElementById("strategies-grid");
    if (!grid) return;
    grid.innerHTML = Array(4).fill(`
        <div class="strategy-card">
            <div class="skeleton skeleton-strategy-header"></div>
            <div class="skeleton skeleton-strategy-score"></div>
            <div class="skeleton skeleton-strategy-detail"></div>
        </div>
    `).join("");
}

function renderStockHero(data) {
    document.getElementById("stock-name").textContent = data.name;
    document.getElementById("stock-symbol").textContent = data.symbol;
    document.getElementById("stock-sector").textContent =
        data.sector && data.sector !== "N/A"
            ? `${data.sector} · ${data.industry || ""}`
            : "";
    document.getElementById("stock-price").textContent = `$${data.price.toFixed(2)}`;

    const changeEl = document.getElementById("stock-change");
    const isPositive = data.change >= 0;
    const sign = isPositive ? "+" : "";
    changeEl.textContent = `${sign}${data.change.toFixed(2)} (${sign}${data.changePercent.toFixed(2)}%)`;
    changeEl.className = `price-change ${isPositive ? "positive" : "negative"}`;
    changeEl.style.color = isPositive ? "var(--accent-green)" : "var(--accent-red)";

/* Yash Patel, 04/27/2026
Updates save button using current stock symbol*/

    // Key metrics
    renderMetrics(data);
    updateSaveButton(data.symbol);
}

function renderMetrics(data) {
    const grid = document.getElementById("metrics-grid");
    const metrics = [
        { label: "Market Cap", value: data.marketCap || "N/A" },
        { label: "Volume", value: data.volume ? formatNumber(data.volume) : "N/A" },
        { label: "52W High", value: data.high52w ? `$${data.high52w.toFixed(2)}` : "N/A" },
        { label: "52W Low", value: data.low52w ? `$${data.low52w.toFixed(2)}` : "N/A" },
        { label: "P/E Ratio", value: data.pe_ratio ? data.pe_ratio.toFixed(2) : "N/A" },
        { label: "Forward P/E", value: data.forward_pe ? data.forward_pe.toFixed(2) : "N/A" },
    ];

    grid.innerHTML = metrics
        .map(
            (m) => `
        <div class="metric-item">
            <div class="metric-label">${m.label}</div>
            <div class="metric-value">${m.value}</div>
        </div>
    `
        )
        .join("");
}

// ===== Signal Display =====

async function loadSignals(symbol) {
    const loadingEl = document.getElementById("signal-loading");
    const contentEl = document.getElementById("signal-content");

    try {
        const data = await getSignals(symbol);

        loadingEl.style.display = "none";
        contentEl.style.display = "block";

        // Main signal badge
        const badge = document.getElementById("signal-badge");
        const signalLower = data.signal.toLowerCase();
        badge.textContent = data.signal;
        badge.className = `signal-badge-lg ${signalLower}`;

        // Confidence bar
        const fill = document.getElementById("confidence-fill");
        fill.style.width = `${data.confidence}%`;
        fill.className = `confidence-fill ${signalLower}`;
        document.getElementById("confidence-value").textContent = `${data.confidence}%`;

        // Strategy breakdown
        renderStrategies(data.breakdown);
    } catch (err) {
        loadingEl.innerHTML = `<span style="color: var(--accent-red)">Could not load signals: ${err.message}</span>`;
    }
}

function renderStrategies(breakdown) {
    const grid = document.getElementById("strategies-grid");
    const strategyNames = {
        momentum: { label: "Momentum", icon: "fa-rocket" },
        mean_reversion: { label: "Mean Reversion", icon: "fa-arrows-left-right" },
        monte_carlo: { label: "Monte Carlo", icon: "fa-dice" },
        factor_model: { label: "Factor Model", icon: "fa-scale-balanced" },
    };

    let html = "";
    for (const [key, result] of Object.entries(breakdown)) {
        const meta = strategyNames[key] || { label: key, icon: "fa-chart-simple" };
        const signalLower = (result.signal || "hold").toLowerCase();
        const scoreDisplay = result.signal === "N/A" ? "N/A" : result.score.toFixed(2);

        html += `
            <div class="strategy-card">
                <div class="strategy-header">
                    <span class="strategy-name">
                        <i class="fa-solid ${meta.icon}" style="margin-right:6px; color:var(--accent-blue)"></i>
                        ${meta.label}
                    </span>
                    <span class="signal-badge-sm ${signalLower}">${result.signal}</span>
                </div>
                <div class="strategy-score">${scoreDisplay}</div>
                <div class="strategy-details">${result.details}</div>
            </div>
        `;
    }

    grid.innerHTML = html;
}

// ===== Chart =====

async function loadChart(symbol, period) {
    /* Anurag Ravi, 04/23/2026
    Show loading overlay while chart data is being fetched */
    showChartLoading("price-chart");
    try {
        const data = await getStockHistory(symbol, period);
        if (data && data.history && data.history.length > 0) {
            renderPriceChart("price-chart", data.history);
        } else {
            hideChartLoading("price-chart");
        }
    } catch (err) {
        hideChartLoading("price-chart");
        console.error("Chart load failed:", err);
    }
}

function initChartControls() {
    const buttons = document.querySelectorAll(".chart-btn");
    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            buttons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const period = btn.getAttribute("data-period");
            if (currentSymbol) loadChart(currentSymbol, period);
        });
    });
}

/* Yash Patel, 04/17/2026
Initializes save button, stores unique stocks, and updates button state based on saved list*/
function initSaveButton() {
    const saveButton = document.getElementById("save-stock-btn");
    if (!saveButton) return;

    saveButton.addEventListener("click", () => {
        if (!currentSymbol) return;

        const normalizedSymbol = currentSymbol.toUpperCase();
        const savedStocks = getStoredSavedStocks();

        if (!savedStocks.includes(normalizedSymbol)) {
            savedStocks.push(normalizedSymbol);
            localStorage.setItem("macropulseSavedStocks", JSON.stringify(savedStocks));
        }

        updateSaveButton(normalizedSymbol);
    });
}

function getStoredSavedStocks() {
    try {
        const saved = JSON.parse(localStorage.getItem("macropulseSavedStocks") || "[]");
        if (!Array.isArray(saved)) return [];

        return saved
            .map((symbol) => String(symbol || "").trim().toUpperCase())
            .filter((symbol, index, arr) => symbol && arr.indexOf(symbol) === index);
    } catch {
        return [];
    }
}

function updateSaveButton(symbol) {
    const saveButton = document.getElementById("save-stock-btn");
    if (!saveButton) return;

    const isSaved = getStoredSavedStocks().includes(String(symbol || "").toUpperCase());
    saveButton.textContent = isSaved ? "Saved" : "Save";
    saveButton.disabled = isSaved;
    saveButton.classList.toggle("saved", isSaved);
}

// ===== Helpers =====

function showError(message) {
    document.getElementById("page-loading").style.display = "none";
    document.getElementById("page-error").style.display = "block";
    document.getElementById("error-message").textContent = message;
}

function formatNumber(num) {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + "B";
    if (num >= 1e6) return (num / 1e6).toFixed(2) + "M";
    if (num >= 1e3) return (num / 1e3).toFixed(1) + "K";
    return num.toString();
}
