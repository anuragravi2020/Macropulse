/**
 * Macropulse - Chart.js price and volume charts.
 */

/**
 * More changes for CSV export
 * Anurag Ravi 4/16/2026 
 * 
 */
let priceChart = null;
let lastChartRender = null;
let lastChartData = null;

function renderPriceChart(canvasId, historyData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    lastChartRender = { canvasId, historyData };
    lastChartData = historyData;

    const styles = getComputedStyle(document.documentElement);
    const borderColor = styles.getPropertyValue("--border").trim();
    const textPrimary = styles.getPropertyValue("--text-primary").trim();
    const textSecondary = styles.getPropertyValue("--text-secondary").trim();
    const bgSecondary = styles.getPropertyValue("--bg-secondary").trim();
    const accentBlue = styles.getPropertyValue("--accent-blue").trim();
    const accentGreen = styles.getPropertyValue("--accent-green").trim();
    const accentRed = styles.getPropertyValue("--accent-red").trim();

    // Destroy existing chart
    if (priceChart) {
        priceChart.destroy();
        priceChart = null;
    }

    const labels = historyData.map((d) => d.date);
    const closePrices = historyData.map((d) => d.close);
    const volumes = historyData.map((d) => d.volume);

    // Determine price color (green if up overall, red if down)
    const firstPrice = closePrices[0];
    const lastPrice = closePrices[closePrices.length - 1];
    const isUp = lastPrice >= firstPrice;
    const lineColor = isUp ? accentGreen : accentRed;
    const fillColor = isUp ? "rgba(63, 185, 80, 0.08)" : "rgba(248, 81, 73, 0.08)";

    // Scale volumes to fit in bottom portion of chart
    const maxPrice = Math.max(...closePrices);
    const minPrice = Math.min(...closePrices);
    const priceRange = maxPrice - minPrice;
    const maxVolume = Math.max(...volumes);
    const scaledVolumes = volumes.map(
        (v) => minPrice - priceRange * 0.02 + (v / maxVolume) * priceRange * 0.2
    );

    priceChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Price",
                    data: closePrices,
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHitRadius: 10,
                    yAxisID: "y",
                },
                {
                    label: "Volume",
                    data: scaledVolumes,
                    type: "bar",
                    backgroundColor: hexToRgba(accentBlue, 0.15),
                    borderColor: "transparent",
                    yAxisID: "y",
                    barPercentage: 0.8,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: bgSecondary,
                    borderColor: borderColor,
                    borderWidth: 1,
                    titleColor: textPrimary,
                    bodyColor: textSecondary,
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            if (context.datasetIndex === 0) {
                                return `Price: $${context.parsed.y.toFixed(2)}`;
                            }
                            const idx = context.dataIndex;
                            return `Volume: ${(volumes[idx] / 1e6).toFixed(1)}M`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: hexToRgba(borderColor, 0.5) },
                    ticks: {
                        color: textSecondary,
                        maxTicksLimit: 8,
                        maxRotation: 0,
                    },
                    border: { color: borderColor },
                },
                y: {
                    position: "right",
                    grid: { color: hexToRgba(borderColor, 0.5) },
                    ticks: {
                        color: textSecondary,
                        callback: (val) => "$" + val.toFixed(0),
                    },
                    border: { color: borderColor },
                },
            },
        },
    });
}

function hexToRgba(color, alpha) {
    const hex = color.replace("#", "").trim();
    if (hex.length !== 6) return color;

    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

window.addEventListener("macropulsePreferencesChanged", () => {
    if (lastChartRender) {
        renderPriceChart(lastChartRender.canvasId, lastChartRender.historyData);
    }
});
/**
 * Export current chart data as CSV file
 * Anurag Ravi 4/16/2026 
 * 
 */
function exportChartDataAsCSV() {
    if (!lastChartData || lastChartData.length === 0) {
        alert("No chart data available to export");
        return;
    }

    // Build CSV header and rows
    let csvContent = "Date,Close Price,Volume\n";
    lastChartData.forEach((dataPoint) => {
        const date = dataPoint.date;
        const close = dataPoint.close.toFixed(2);
        const volume = Math.round(dataPoint.volume);
        csvContent += `${date},${close},${volume}\n`;
    });

    // Create blob and trigger download
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `chart-data-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}