const API_BASE = 'https://windguard-backend.onrender.com';
let latestDashboardData = null;
let latestForecastData = null;

document.addEventListener('DOMContentLoaded', () => {
    updateTime();
    setInterval(updateTime, 1000);
    checkAPIStatus();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        
        // Populate Indian Districts Datalist
        const datalist = document.getElementById('city-list');
        if (datalist && typeof INDIAN_DISTRICTS !== 'undefined') {
            INDIAN_DISTRICTS.forEach(city => {
                const opt = document.createElement('option');
                opt.value = city;
                datalist.appendChild(opt);
            });
        }
        
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

        const forecastRes = await fetch(`${API_BASE}/api/forecast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (forecastRes.ok) {
            latestForecastData = await forecastRes.json();
        }

    } catch (err) {
        console.error(err);
        alert('Failed to connect to backend. Please ensure the FastAPI server is running.');
    } finally {
        btn.textContent = 'Sync Data';
        btn.disabled = false;
    }
}

function updateUI(data) {
    latestDashboardData = data;
    
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

// Chart Instances
let historyChart = null;
let forecastChart = null;

async function fetchHistoryData() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        if (!response.ok) throw new Error('Failed to fetch history');
        const data = await response.json();

        renderChart(data);

        // Fetch Forecast
        const payload = {
            plant_location: "Coimbatore, IN",
            installed_capacity_mw: 50,
            transformer_capacity_mw: 45,
            electricity_price: null
        };
        const forecastRes = await fetch(`${API_BASE}/api/forecast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (forecastRes.ok) {
            const forecastData = await forecastRes.json();
            renderForecastChart(forecastData);
        }

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

function renderForecastChart(forecastData) {
    const ctx = document.getElementById('forecast-chart');
    if (!ctx) return;

    const labels = forecastData.map(d => d.timestamp.replace(' ', 'T').substring(11, 16));
    const lossData = forecastData.map(d => d.loss_mw);

    if (forecastChart) forecastChart.destroy();

    forecastChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Energy Loss (MW)',
                data: lossData,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#f8fafc' } }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Loss (MW)', color: '#94a3b8' },
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            }
        }
    });
}

// Chatbot Logic
document.addEventListener('DOMContentLoaded', () => {
    const chatToggle = document.getElementById('chatbot-toggle');
    const chatWindow = document.getElementById('chatbot-window');
    const chatClose = document.getElementById('chatbot-close');
    const chatInput = document.getElementById('chatbot-input');
    const chatSend = document.getElementById('chatbot-send');
    const chatMessages = document.getElementById('chatbot-messages');

    if (chatToggle && chatWindow) {
        chatToggle.addEventListener('click', () => {
            chatWindow.classList.toggle('hidden');
        });

        // Closing the chat hides it, but does NOT delete history.
        chatClose.addEventListener('click', () => {
            chatWindow.classList.add('hidden');
        });

        chatSend.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        
        // Inject a tiny clear button for resetting the session manually
        const chatHeader = chatWindow.querySelector('.chatbot-header');
        if (chatHeader && !document.getElementById('chatbot-clear')) {
            const clearBtn = document.createElement('button');
            clearBtn.id = 'chatbot-clear';
            clearBtn.textContent = 'Clear';
            clearBtn.style.background = 'transparent';
            clearBtn.style.border = '1px solid rgba(255,255,255,0.2)';
            clearBtn.style.color = '#fff';
            clearBtn.style.borderRadius = '4px';
            clearBtn.style.padding = '2px 8px';
            clearBtn.style.fontSize = '0.8rem';
            clearBtn.style.cursor = 'pointer';
            clearBtn.style.marginRight = '8px';
            
            chatHeader.insertBefore(clearBtn, chatClose);
            
            clearBtn.addEventListener('click', () => {
                sessionStorage.removeItem('windguard_chat');
                chatMessages.innerHTML = '';
            });
        }
        
        // Load persistent memory
        loadChatHistory();
    }

    function loadChatHistory() {
        const saved = sessionStorage.getItem('windguard_chat');
        if (saved && chatMessages) {
            const logs = JSON.parse(saved);
            chatMessages.innerHTML = '';
            logs.forEach(msg => {
                const el = document.createElement('div');
                el.className = `message ${msg.role}`;
                el.textContent = msg.text;
                chatMessages.appendChild(el);
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function saveMessage(role, text) {
        const saved = sessionStorage.getItem('windguard_chat');
        const logs = saved ? JSON.parse(saved) : [];
        logs.push({ role, text });
        sessionStorage.setItem('windguard_chat', JSON.stringify(logs));
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // Append user message
        const userMsg = document.createElement('div');
        userMsg.className = 'message user';
        userMsg.textContent = text;
        chatMessages.appendChild(userMsg);
        chatInput.value = '';
        saveMessage('user', text);
        
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Add loading state
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'message ai';
        loadingMsg.textContent = 'Thinking...';
        chatMessages.appendChild(loadingMsg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        const payload = {
            message: text,
            context: latestDashboardData ? {
                wind_speed: latestDashboardData.weather?.wind_speed,
                temperature: latestDashboardData.weather?.temp,
                generation_mw: latestDashboardData.generation_forecast_mw,
                demand_mw: latestDashboardData.demand_forecast_mw,
                price_inr: latestDashboardData.kpis.find(k => k.label === "Electricity Price")?.value,
                risk_level: latestDashboardData.risk_level,
                loss_mw: latestDashboardData.kpis.find(k => k.label === "Energy Loss")?.value
            } : null,
            forecast_context: latestForecastData
        };

        try {
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Chat failed');

            const data = await response.json();
            loadingMsg.textContent = data.reply;
            saveMessage('ai', data.reply);
        } catch (err) {
            loadingMsg.textContent = 'Error: Cannot reach the assistant right now.';
            console.error(err);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
