const API_BASE = 'https://windguard-backend.onrender.com';
let currentLiveData = null;
let activeDisplayData = null;
let latestForecastData = null;
let aggregateSlots = []; // For 6-hour slices

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
        
        const timeRangeSelect = document.getElementById('time-range-select');
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', (e) => {
                const val = e.target.value;
                if (val === 'current') {
                    if (currentLiveData) updateUI(currentLiveData);
                } else if (val.startsWith('agg_')) {
                    const idx = parseInt(val.split('_')[1]);
                    if (aggregateSlots[idx]) updateUI(aggregateSlots[idx]);
                } else {
                    // Detailed 3-hour slot — cast string to integer for array indexing
                    const idx = parseInt(val, 10);
                    if (!isNaN(idx) && latestForecastData && latestForecastData[idx]) {
                        updateUI(latestForecastData[idx]);
                    }
                }
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
        currentLiveData = data;
        
        // Reset Time Range back to current visually
        const timeSelect = document.getElementById('time-range-select');
        if (timeSelect) timeSelect.value = 'current';
        
        updateUI(data);

        const forecastRes = await fetch(`${API_BASE}/api/forecast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (forecastRes.ok) {
            latestForecastData = await forecastRes.json();
            
            if (!latestForecastData || latestForecastData.length === 0) {
                showToast("Data not available. Try after some time.");
            }
            
            // Populate Time Range dropdown natively
            const timeSelect = document.getElementById('time-range-select');
            if (timeSelect) {
                timeSelect.innerHTML = '<option value="current">Current (Live Data)</option>';
                
                // 1. Add Predefined 6-hour Aggregate Slots (Boss Request)
                aggregateSlots = [];
                for(let i=0; i < latestForecastData.length - 1; i += 2) {
                    const d1 = latestForecastData[i];
                    const d2 = latestForecastData[i+1];
                    
                    const dt1 = new Date(d1.timestamp.replace(' ', 'T'));
                    const hStart = dt1.getHours().toString().padStart(2, '0');
                    const dtEnd = new Date(new Date(d2.timestamp.replace(' ', 'T')).getTime() + 3*60*60*1000);
                    const hEnd = dtEnd.getHours().toString().padStart(2, '0');

                    // Simple Average for Aggregation
                    const agg = JSON.parse(JSON.stringify(d1));
                    agg.timestamp = `${d1.timestamp.split(' ')[0]} ${hStart}:00-${hEnd}:00`;
                    agg.kpis.forEach((k, idx) => {
                        const val2 = d2.kpis.find(k2 => k2.label === k.label)?.value || 0;
                        k.value = (k.value + val2) / 2;
                    });
                    aggregateSlots.push(agg);
                    
                    const opt = document.createElement('option');
                    opt.value = `agg_${aggregateSlots.length - 1}`;
                    opt.textContent = `★ ${agg.timestamp}`;
                    timeSelect.appendChild(opt);
                }

                // Divider
                const divider = document.createElement('option');
                divider.disabled = true;
                divider.textContent = "-------------------------";
                timeSelect.appendChild(divider);

                // 2. Add Detailed 3-hour Individual Slots
                latestForecastData.forEach((item, index) => {
                    const dt = new Date(item.timestamp.replace(' ', 'T'));
                    const h1 = dt.getHours().toString().padStart(2, '0');
                    const nextDt = new Date(dt.getTime() + 3*60*60*1000);
                    const h2 = nextDt.getHours().toString().padStart(2, '0');
                    
                    const opt = document.createElement('option');
                    opt.value = index;
                    opt.textContent = `${item.timestamp.split(' ')[0]} | ${h1}:00 - ${h2}:00`;
                    timeSelect.appendChild(opt);
                });
            }
        }

    } catch (err) {
        console.error(err);
        showToast("Backend connection error. Please try again later.");
    } finally {
        btn.textContent = 'Sync Data';
        btn.disabled = false;
    }
}

function updateUI(data) {
    activeDisplayData = data;
    
    // Show which time window is active
    let timeLabel = document.getElementById('active-time-label');
    if (!timeLabel) {
        timeLabel = document.createElement('div');
        timeLabel.id = 'active-time-label';
        timeLabel.style.cssText = 'font-size:0.8rem;color:#a78bfa;margin-bottom:0.5rem;font-weight:600;letter-spacing:0.05rem;';
        const kpiSection = document.getElementById('kpi-containers');
        if (kpiSection && kpiSection.parentNode) {
            kpiSection.parentNode.insertBefore(timeLabel, kpiSection);
        }
    }
    if (data.timestamp) {
        // Format timestamp nicely
        const ts = data.timestamp.replace(' ', 'T');
        const dt = new Date(ts);
        const nextDt = new Date(dt.getTime() + 3*60*60*1000);
        const fmt = (d) => `${d.getHours().toString().padStart(2,'0')}:00`;
        const dateStr = dt.toLocaleDateString('en-IN', {day:'numeric', month:'short'});
        // If timestamp contains a dash it's an aggregate slot
        if (data.timestamp.includes('-') && data.timestamp.includes(':00-')) {
            timeLabel.textContent = `⏱ VIEWING FORECAST WINDOW: ${data.timestamp}`;
        } else {
            timeLabel.textContent = `⏱ VIEWING FORECAST WINDOW: ${dateStr} | ${fmt(dt)} – ${fmt(nextDt)}`;
        }
        timeLabel.style.display = 'block';
    } else {
        timeLabel.style.display = 'none';
    }
    
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

    // 2. Update Recommendations (only exists on dashboard page)
    const recsList = document.getElementById('recs-list');
    if (recsList) {
        recsList.innerHTML = '';
        data.recommendations.forEach(rec => {
            const item = document.createElement('div');
            item.className = `rec-item priority-${rec.priority}`;
            item.innerHTML = `<strong>[${rec.category}]</strong> ${rec.message}`;
            recsList.appendChild(item);
        });
    }

    // 3. Update Risk Profile (only exists on dashboard page)
    const riskLabel = document.getElementById('risk-label');
    const riskMeter = document.getElementById('risk-meter');
    if (riskLabel) riskLabel.textContent = `${data.risk_level} Risk (${Math.round(data.risk_score * 100)}%)`;
    if (riskMeter) {
        let color = '#10b981';
        if (data.risk_level === 'MEDIUM') color = '#f59e0b';
        if (data.risk_level === 'HIGH') color = '#ef4444';
        riskMeter.style.background = `conic-gradient(${color} 0% ${data.risk_score * 100}%, rgba(255,255,255,0.1) ${data.risk_score * 100}% 100%)`;
    }
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

    // Labels: extract HH:MM from timestamp (works for both 'YYYY-MM-DD HH:MM' and ISO strings)
    const labels = forecastData.map(d => {
        const ts = (d.timestamp || '').replace(' ', 'T');
        const dt = new Date(ts);
        if (isNaN(dt.getTime())) return d.timestamp || '';
        const h1 = dt.getHours().toString().padStart(2, '0');
        const nextDt = new Date(dt.getTime() + 3*60*60*1000);
        const h2 = nextDt.getHours().toString().padStart(2, '0');
        return `${h1}:00–${h2}:00`;
    });
    // Loss data: support both old ForecastOut and new DashboardData schemas
    const lossData = forecastData.map(d => {
        if (typeof d.loss_mw === 'number') return d.loss_mw;
        if (d.kpis) {
            const kpi = d.kpis.find(k => k.label === 'Energy Loss');
            return kpi ? kpi.value : 0;
        }
        return 0;
    });

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
            context: activeDisplayData ? {
                wind_speed: activeDisplayData.weather?.wind_speed,
                temperature: activeDisplayData.weather?.temp,
                generation_mw: activeDisplayData.generation_forecast_mw,
                demand_mw: activeDisplayData.demand_forecast_mw,
                price_inr: activeDisplayData.kpis.find(k => k.label === "Electricity Price")?.value,
                risk_level: activeDisplayData.risk_level,
                loss_mw: activeDisplayData.kpis.find(k => k.label === "Energy Loss")?.value
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

function showToast(message) {
    let toast = document.querySelector('.toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 5000);
}

