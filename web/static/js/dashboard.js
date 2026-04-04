let winRateChart = null;
let trainingChart = null;

async function loadDashboard() {
    try {
        const response = await fetch('/api/dashboard');
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        updateSummary(data.summary);
        updateAgentTable(data.agents);
        updateSignalsTable(data.v11);
        updateTradesTable(data.v11);
        updateModelStatus(data.model);
        updateWinRateChart(data.agents);
        updateTrainingChart(data.training);
        updateV11Status(data.v11);
        updateABTable((data.v11 || {}).ab_testing || {});
        updateTFTable((data.v11 || {}).timeframe_stats || {});
        document.getElementById('lastUpdate').textContent = `Last update: ${new Date().toLocaleTimeString()}`;
        document.getElementById('statusIndicator').textContent = 'CONNECTED';
        document.getElementById('statusIndicator').className = 'status-indicator connected';
    } catch (err) {
        document.getElementById('statusIndicator').textContent = 'ERROR';
        document.getElementById('statusIndicator').className = 'status-indicator error';
        console.error('Dashboard load error:', err);
    }
}

function updateSummary(summary) {
    const pnlEl = document.getElementById('totalPnl');
    pnlEl.textContent = `$${summary.total_pnl.toLocaleString()}`;
    pnlEl.className = `card-value ${summary.total_pnl >= 0 ? 'positive' : 'negative'}`;
    document.getElementById('totalTrades').textContent = summary.total_trades;
    const wrEl = document.getElementById('winRate');
    wrEl.textContent = `${summary.overall_win_rate}%`;
    wrEl.className = `card-value ${summary.overall_win_rate >= 50 ? 'positive' : 'negative'}`;
    document.getElementById('activeAgents').textContent = summary.active_agents;
    const healthEl = document.getElementById('healthStatus');
    healthEl.textContent = summary.health_status;
    healthEl.className = `card-value ${summary.health_status === 'HEALTHY' ? 'positive' : summary.health_status === 'WARNING' ? 'negative' : 'neutral'}`;
    const trainingEl = document.getElementById('trainingRows');
    trainingEl.textContent = `${summary.enriched_training_rows || 0} enriched / ${trainingEl.dataset.totalRows || 0} total`;
}

function updateAgentTable(agents) {
    const tbody = document.getElementById('agentTableBody');
    const sorted = Object.entries(agents).sort((a, b) => b[1].total_pnl - a[1].total_pnl);
    if (sorted.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty">No agents found</td></tr>';
        return;
    }
    tbody.innerHTML = sorted.map(([name, stats], i) => `
        <tr>
            <td>${i + 1}</td>
            <td><strong>${name}</strong></td>
            <td>${stats.strategy}</td>
            <td>${stats.capital.toLocaleString()}</td>
            <td class="${stats.total_pnl >= 0 ? 'positive' : 'negative'}">${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toLocaleString()}</td>
            <td class="${stats.win_rate >= 50 ? 'positive' : 'negative'}">${stats.win_rate}%</td>
            <td>${stats.open_positions}</td>
            <td>${stats.closed_trades}</td>
        </tr>
    `).join('');
}

async function updateSignalsTable(v11data) {
    try {
        const response = await fetch('/api/signals');
        const signals = await response.json();
        const tbody = document.getElementById('signalsTableBody');
        if (signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty">No signals yet</td></tr>';
            return;
        }
        tbody.innerHTML = signals.slice(0, 10).map(s => {
            const badgeClass = s.verdict === 'BUY' ? 'badge-long' : s.verdict === 'SELL' ? 'badge-short' : 'badge-no_trade';
            const mlBadge = s.ml_approved ? '<span class="badge badge-long">ML OK</span>' : '<span class="badge badge-short">ML REJECT</span>';
            return `
            <tr>
                <td>${new Date(s.timestamp).toLocaleString()}</td>
                <td>${s.agent}</td>
                <td>${s.symbol}</td>
                <td><span class="badge ${badgeClass}">${s.verdict}</span></td>
                <td>${s.ml_prob_win}</td>
                <td>${mlBadge}</td>
                <td>${s.regime || '—'}</td>
            </tr>
        `}).join('');
    } catch (err) {
        console.error('Signals load error:', err);
    }
}

async function updateTradesTable(v11data) {
    try {
        const response = await fetch('/api/trades');
        const trades = await response.json();
        const tbody = document.getElementById('tradesTableBody');
        if (trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty">No trades yet</td></tr>';
            return;
        }
        tbody.innerHTML = trades.slice(0, 10).map(t => {
            const sf = t.size_factors || {};
            const sizingInfo = `ml:${(sf.ml_confidence||1).toFixed(1)}×reg:${(sf.regime_strength||0.5).toFixed(1)}×vol:${(sf.vol_scalar||1).toFixed(1)}`;
            return `
            <tr>
                <td>${new Date(t.timestamp).toLocaleString()}</td>
                <td>${t.agent}</td>
                <td>${t.symbol}</td>
                <td>${t.entry_price}</td>
                <td>${t.exit_price}</td>
                <td class="${t.pnl >= 0 ? 'positive' : 'negative'}">${t.pnl >= 0 ? '+' : ''}${t.pnl ? t.pnl.toFixed(2) : '0'}</td>
                <td>${t.regime_entry}→${t.regime_exit}</td>
                <td>${t.stop_out ? 'STOP' : t.close_reason}</td>
                <td title="${sizingInfo}">${t.ml_prob_win}</td>
            </tr>
        `}).join('');
    } catch (err) {
        console.error('Trades load error:', err);
    }
}

function updateModelStatus(model) {
    const el = document.getElementById('modelStatus');
    if (model.status === 'NO_MODEL') {
        el.innerHTML = '<span class="empty">No trained model found</span>';
        return;
    }
    if (model.status === 'ERROR') {
        el.innerHTML = `<span class="empty">Error: ${model.message}</span>`;
        return;
    }
    const m = model.metrics || {};
    el.innerHTML = `
        <div class="detail"><span class="label">Status</span><span class="value positive">READY</span></div>
        <div class="detail"><span class="label">Accuracy</span><span class="value">${(m.accuracy * 100).toFixed(1)}%</span></div>
        <div class="detail"><span class="label">Precision</span><span class="value">${(m.precision * 100).toFixed(1)}%</span></div>
        <div class="detail"><span class="label">F1 Score</span><span class="value">${(m.f1 * 100).toFixed(1)}</span></div>
        <div class="detail"><span class="label">Training Samples</span><span class="value">${m.total_samples || 0}</span></div>
        <div class="detail"><span class="label">Last Trained</span><span class="value">${m.trained_at ? new Date(m.trained_at).toLocaleString() : 'N/A'}</span></div>
    `;
}

function updateWinRateChart(agents) {
    const ctx = document.getElementById('winRateChart').getContext('2d');
    if (winRateChart) winRateChart.destroy();
    const labels = Object.keys(agents);
    const data = Object.values(agents).map(a => a.win_rate);
    const colors = data.map(v => v >= 50 ? '#34d399' : '#f87171');
    winRateChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Win Rate %',
                data,
                backgroundColor: colors,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, max: 100, grid: { color: '#1f2937' }, ticks: { color: '#6b7280' } },
                x: { grid: { display: false }, ticks: { color: '#6b7280' } }
            }
        }
    });
}

function updateTrainingChart(training) {
    const ctx = document.getElementById('trainingChart').getContext('2d');
    if (trainingChart) trainingChart.destroy();
    const wins = training.win_rate;
    const losses = 100 - wins;
    trainingChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Wins', 'Losses'],
            datasets: [{
                data: [wins, losses],
                backgroundColor: ['#34d399', '#f87171'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#6b7280', padding: 20 } }
            }
        }
    });
    document.getElementById('trainingRows').dataset.rows = training.rows;
    document.getElementById('trainingRows').textContent = `${training.rows} rows`;
}

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    loadV11Status();
    setInterval(loadDashboard, 30000);
    setInterval(loadV11Status, 60000);
});

async function loadV11Status() {
    try {
        const response = await fetch('/api/v11');
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        updateV11Status(data);
        updateABTable(data.ab_testing);
    } catch (err) {
        console.error('V11 load error:', err);
    }
}

function updateV11Status(v11data) {
    const el = document.getElementById('v11Status');
    if (!el || !v11data) return;
    const sentinel = v11data.sentinel || {};
    const registry = v11data.registry || {};
    const champion = registry.champion_version || 'None';
    const candidates = registry.active_candidates || 0;
    const ml = v11data.ml_predictions || {};
    const drift = v11data.drift_alerts || 0;
    const tfStats = v11data.timeframe_stats || {};
    const tfList = Object.keys(tfStats).length > 0 ? Object.keys(tfStats).join(', ') : '7 timeframes configured';

    el.innerHTML = `
        <div class="detail"><span class="label">Sentinel</span><span class="value ${sentinel.halted ? 'negative' : 'positive'}">${sentinel.halted ? 'HALTED' : 'CLEAR'}</span></div>
        <div class="detail"><span class="label">Sentinel Triggers</span><span class="value">${sentinel.total_triggers || 0}</span></div>
        <div class="detail"><span class="label">Champion Model</span><span class="value">${champion}</span></div>
        <div class="detail"><span class="label">Active Candidates</span><span class="value">${candidates}</span></div>
        <div class="detail"><span class="label">ML Predictions</span><span class="value">${ml.total || 0} (avg prob: ${ml.avg_prob || 0})</span></div>
        <div class="detail"><span class="label">ML Approved / Rejected</span><span class="value">${ml.approved || 0} / ${ml.rejected || 0}</span></div>
        <div class="detail"><span class="label">Drift Alerts</span><span class="value ${drift > 0 ? 'negative' : 'positive'}">${drift}</span></div>
        <div class="detail"><span class="label">Active Timeframes</span><span class="value">${tfList}</span></div>
        <div class="detail"><span class="label">Governance Decisions</span><span class="value">${(v11data.governance || []).length}</span></div>
    `;
}

function updateABTable(partitions) {
    const tbody = document.getElementById('abTableBody');
    if (!tbody) return;
    if (!partitions || Object.keys(partitions).length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No active partitions</td></tr>';
        return;
    }
    tbody.innerHTML = Object.entries(partitions).map(([name, p]) => `
        <tr>
            <td><strong>${name}</strong></td>
            <td>${p.model}</td>
            <td>${(p.allocation * 100).toFixed(0)}%</td>
            <td>${p.trades}</td>
            <td class="${p.total_return >= 0 ? 'positive' : 'negative'}">${p.total_return >= 0 ? '+' : ''}${p.total_return.toFixed(2)}%</td>
        </tr>
    `).join('');
}

function updateTFTable(tfStats) {
    const tbody = document.getElementById('tfTableBody');
    if (!tbody) return;
    if (!tfStats || Object.keys(tfStats).length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No trades yet — waiting for positions to close</td></tr>';
        return;
    }
    const tfOrder = ['1m', '5m', '15m', '30m', '1h', '2h', '4h'];
    const sorted = Object.entries(tfStats).sort((a, b) => {
        const ia = tfOrder.indexOf(a[0]);
        const ib = tfOrder.indexOf(b[0]);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
    tbody.innerHTML = sorted.map(([tf, s]) => `
        <tr>
            <td><strong>${tf}</strong></td>
            <td>${s.trades}</td>
            <td class="${s.win_rate >= 50 ? 'positive' : 'negative'}">${s.win_rate}%</td>
            <td class="${s.avg_pnl >= 0 ? 'positive' : 'negative'}">${s.avg_pnl >= 0 ? '+' : ''}${s.avg_pnl}%</td>
            <td class="${s.total_pnl >= 0 ? 'positive' : 'negative'}">${s.total_pnl >= 0 ? '+' : ''}${s.total_pnl.toFixed(2)}%</td>
        </tr>
    `).join('');
}
