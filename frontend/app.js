const API_BASE = 'https://windguard-backend.onrender.com';

document.addEventListener('DOMContentLoaded', () => {
    updateTime();
    setInterval(updateTime, 1000);
    checkAPIStatus();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchData);
        // Initial fetch for dashboard
        fetchData();
    }

    const historyChartEl = document.getElementById('history-chart');
    if (historyChartEl) {
        // Initial fetch for history page
        fetchHistoryData();
    }
});

function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent = now.toLocaleString();
}

async function checkAPIStatus() {
    try {
        const resp = await fetch(`${API_BASE}/health`);
        const statusEl = document.getElementById('api-status');
        if (resp.ok) {
            statusEl.textContent = 'Operational';
            statusEl.style.color = '#10b981';
        } else {
            statusEl.textContent = 'Error';
            statusEl.style.color = '#ef4444';
        }
    } catch (e) {
        document.getElementById('api-status').textContent = 'Offline';
    }
}

async function fetchData() {
    const payload = {
        plant_location: document.getElementById('location-input').value,
        installed_capacity_mw: parseFloat(document.getElementById('capacity-input').value),
        transformer_capacity_mw: parseFloat(document.getElementById('transformer-input').value),
        electricity_price: parseFloat(document.getElementById('price-input').value) || null
    };

    const btn = document.getElementById('refresh-btn');
    btn.textContent = 'Syncing...';
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Prediction failed');

        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.error(err);
        alert('Failed to connect to backend. Please ensure the FastAPI server is running.');
    } finally {
        btn.textContent = 'Sync Data';
        btn.disabled = false;
    }
}

function updateUI(data) {
    // 1. Update KPI Cards
    const kpiContainer = document.getElementById('kpi-containers');
    kpiContainer.innerHTML = '';

    data.kpis.forEach(kpi => {
        const card = document.createElement('div');
        card.className = 'kpi-card';
        card.innerHTML = `
            <div class="kpi-label">${kpi.label}</div>
            <div class="kpi-value">${kpi.value.toLocaleString()}<span class="kpi-unit">${kpi.unit}</span></div>
        `;
        kpiContainer.appendChild(card);
    });

    // 2. Update Recommendations
    const recsList = document.getElementById('recs-list');
    recsList.innerHTML = '';

    data.recommendations.forEach(rec => {
        const item = document.createElement('div');
        item.className = `rec-item priority-${rec.priority}`;
        item.innerHTML = `
            <strong>[${rec.category}]</strong> ${rec.message}
        `;
        recsList.appendChild(item);
    });

    // 3. Update Risk Profile
    const riskLabel = document.getElementById('risk-label');
    const riskMeter = document.getElementById('risk-meter');

    riskLabel.textContent = `${data.risk_level} Risk (${Math.round(data.risk_score * 100)}%)`;

    // Simple visual for risk meter
    let color = '#10b981';
    if (data.risk_level === 'MEDIUM') color = '#f59e0b';
    if (data.risk_level === 'HIGH') color = '#ef4444';

    riskMeter.style.background = `conic-gradient(${color} 0% ${data.risk_score * 100}%, rgba(255,255,255,0.1) ${data.risk_score * 100}% 100%)`;
}

// Chart Instance
let historyChart = null;

async function fetchHistoryData() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        if (!response.ok) throw new Error('Failed to fetch history');
        const data = await response.json();

        renderChart(data);
    } catch (err) {
        console.error("History fetch error:", err);
    }
}

function renderChart(historyData) {
    const ctx = document.getElementById('history-chart').getContext('2d');

    // Sort chronologically just in case
    historyData.sort((a, b) => new Date(a.timestamp.replace(' ', 'T')) - new Date(b.timestamp.replace(' ', 'T')));

    const labels = historyData.map(d => {
        const dt = new Date(d.timestamp.replace(' ', 'T'));
        return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours()}:00`;
    });

    const priceData = historyData.map(d => d.price);
    const demandData = historyData.map(d => d.demand);

    if (historyChart) {
        historyChart.destroy();
    }

    historyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Electricity Price (INR/MWh)',
                    data: priceData,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'National Demand (MW)',
                    data: demandData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: '#f8fafc' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8', maxTicksLimit: 12 },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'Price (INR)', color: '#94a3b8' },
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'Demand (MW)', color: '#94a3b8' },
                    ticks: { color: '#94a3b8' },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}
