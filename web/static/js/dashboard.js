let eventSource = null;

// ==================== AUTH ====================

function getToken() {
    return localStorage.getItem('token');
}

function authHeaders() {
    const t = getToken();
    return t ? {'Authorization': 'Bearer ' + t} : {};
}

async function fetchAuth(url) {
    const res = await fetch(url, {headers: authHeaders()});
    if (res.status === 401) {
        window.location.href = '/login';
        return null;
    }
    return res;
}

async function autoLogin() {
    if (getToken()) return true;
    window.location.href = '/login';
    return false;
}

// ==================== SSE ====================
function initSSE() {
    if (eventSource) eventSource.close();
    const token = getToken();
    if (!token) return;

    document.cookie = 'token=' + encodeURIComponent(token) + '; path=/; SameSite=Strict';
    eventSource = new EventSource('/api/stream');

    eventSource.onopen = () => {
        document.getElementById('sseStatus').textContent = 'SSE ON';
        document.getElementById('sseDot').className = 'status-dot connected';
    };

    eventSource.addEventListener('alert', (e) => {
        const data = JSON.parse(e.data);
        showAlert(data.message, data.type ? data.type.toLowerCase() : 'info');
    });

    eventSource.onerror = () => {
        document.getElementById('sseStatus').textContent = 'SSE OFF';
        document.getElementById('sseDot').className = 'status-dot error';
        setTimeout(initSSE, 5000);
    };
}

function showAlert(message, type) {
    const container = document.getElementById('alertContainer');
    if (!container) return;
    const alert = document.createElement('div');
    alert.className = 'alert alert-' + (type || 'info');
    alert.textContent = message;
    container.appendChild(alert);
    setTimeout(() => alert.remove(), 8000);
}

// ==================== C2 CONTROLS ====================
document.addEventListener('DOMContentLoaded', () => {
    const c2Btn = document.getElementById('c2Btn');
    const c2Menu = document.getElementById('c2Menu');
    if (c2Btn && c2Menu) {
        c2Btn.addEventListener('click', (e) => {
            e.stopPropagation();
            c2Menu.classList.toggle('show');
        });
        document.addEventListener('click', () => c2Menu.classList.remove('show'));
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'r' || e.key === 'R') { if (!e.ctrlKey) loadDashboard(); }
        if (e.key === 'Escape') { if (c2Menu) c2Menu.classList.remove('show'); }
    });
});

async function c2Action(endpoint, label) {
    if (!confirm(label + '?')) return;
    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', ...authHeaders()}
        });
        const data = await res.json();
        if (res.ok) {
            showAlert(data.message || label + ' successful', 'success');
            loadDashboard();
        } else {
            showAlert(data.error || 'Failed', 'error');
        }
    } catch (err) {
        showAlert('Error: ' + err.message, 'error');
    }
}

function c2HaltAll() { c2Action('/api/c2/halt-all', 'Halt all new entries'); }
function c2ResumeAll() { c2Action('/api/c2/resume-all', 'Resume trading'); }
function c2CloseAll() { c2Action('/api/c2/close-all-positions', 'Close all positions'); }
function c2Retrain() { c2Action('/api/c2/retrain', 'Force ML retrain'); }

// ==================== DASHBOARD ====================
async function loadDashboard() {
    const res = await fetchAuth('/api/dashboard');
    if (!res) return;
    const data = await res.json();
    updateSummary(data.summary);
    updateAgentTable(data.agents);
    updateSignalsTable();
    updateTradesTable();
    updateModelStatus(data.model);
    updateTFTable((data.v11 || {}).timeframe_stats || {});
    updateV11Status(data.v11);
    updateC2Log((data.v11 || {}).c2_actions || []);
    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
    document.getElementById('statusIndicator').textContent = 'LIVE';
    document.getElementById('statusDot').className = 'status-dot connected';
}

async function loadMTFMatrix() {
    const res = await fetchAuth('/api/mtf-matrix');
    if (!res) return;
    updateMTFMatrix(await res.json());
}

function updateSummary(s) {
    const pnlEl = document.getElementById('totalPnl');
    pnlEl.textContent = (s.total_pnl >= 0 ? '+' : '') + '$' + s.total_pnl.toLocaleString();
    pnlEl.className = 'card-value ' + (s.total_pnl >= 0 ? 'positive' : 'negative');
    document.getElementById('totalTrades').textContent = s.total_trades;
    const wrEl = document.getElementById('winRate');
    wrEl.textContent = s.overall_win_rate + '%';
    wrEl.className = 'card-value ' + (s.overall_win_rate >= 50 ? 'positive' : 'negative');
    const barEl = document.getElementById('winRateBar');
    if (barEl) {
        const pct = Math.min(s.overall_win_rate, 100);
        const color = pct >= 50 ? 'var(--green)' : 'var(--red)';
        barEl.innerHTML = '<div class="card-bar-fill" style="width:' + pct + '%;background:' + color + '"></div>';
    }
    document.getElementById('activeAgents').textContent = s.active_agents;
    const hEl = document.getElementById('healthStatus');
    hEl.textContent = s.health_status;
    hEl.className = 'card-value ' + (s.health_status === 'HEALTHY' ? 'positive' : s.health_status === 'WARNING' ? 'negative' : 'neutral');
    const mlEl = document.getElementById('mlPredictions');
    mlEl.textContent = s.ml_rejected !== undefined ? s.ml_rejected + ' rejected' : '--';
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
            <td class="num">${i + 1}</td>
            <td><strong>${name}</strong></td>
            <td>${stats.strategy}</td>
            <td class="num">${stats.capital.toLocaleString()}</td>
            <td class="num ${stats.total_pnl >= 0 ? 'positive' : 'negative'}">${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toLocaleString()}</td>
            <td class="num ${stats.win_rate >= 50 ? 'positive' : 'negative'}">${stats.win_rate}%</td>
            <td class="num">${stats.open_positions}</td>
            <td class="num">${stats.closed_trades}</td>
        </tr>
    `).join('');
}

async function updateSignalsTable() {
    try {
        const res = await fetchAuth('/api/signals');
        if (!res) return;
        const signals = await res.json();
        const tbody = document.getElementById('signalsTableBody');
        if (signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty">No signals yet</td></tr>';
            return;
        }
        tbody.innerHTML = signals.slice(0, 15).map(s => {
            const bc = s.verdict === 'BUY' ? 'badge-long' : s.verdict === 'SELL' ? 'badge-short' : 'badge-no_trade';
            const ml = s.ml_approved ? '<span class="badge badge-long">OK</span>' : '<span class="badge badge-short">REJECT</span>';
            const mp = s.ml_prob_win !== undefined ? (s.ml_prob_win * 100).toFixed(0) + '%' : '—';
            return `<tr>
                <td class="num">${new Date(s.timestamp).toLocaleTimeString()}</td>
                <td>${s.timeframe || '—'}</td>
                <td>${s.agent}</td>
                <td>${s.symbol}</td>
                <td><span class="badge ${bc}">${s.verdict}</span></td>
                <td class="num">${mp}</td>
                <td>${ml}</td>
                <td>${s.regime || '—'}</td>
            </tr>`;
        }).join('');
    } catch (err) { console.error('Signals error:', err); }
}

async function updateTradesTable() {
    try {
        const res = await fetchAuth('/api/trades');
        if (!res) return;
        const trades = await res.json();
        const tbody = document.getElementById('tradesTableBody');
        if (trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="empty">No trades yet</td></tr>';
            return;
        }
        tbody.innerHTML = trades.slice(0, 15).map(t => {
            const sf = t.size_factors || {};
            const sz = `ml:${(sf.ml_confidence||1).toFixed(1)} reg:${(sf.regime_strength||0.5).toFixed(1)} vol:${(sf.vol_scalar||1).toFixed(1)}`;
            const pnl = t.pnl !== undefined && t.pnl !== null ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(2) : '0.00';
            const ml = t.ml_prob_win !== undefined ? (t.ml_prob_win * 100).toFixed(0) + '%' : '—';
            return `<tr>
                <td class="num">${new Date(t.timestamp).toLocaleTimeString()}</td>
                <td>${t.timeframe || '—'}</td>
                <td>${t.agent}</td>
                <td>${t.symbol}</td>
                <td class="num">${t.entry_price}</td>
                <td class="num">${t.exit_price}</td>
                <td class="num ${t.pnl >= 0 ? 'positive' : 'negative'}">${pnl}</td>
                <td>${t.regime_entry || '—'}→${t.regime_exit || '—'}</td>
                <td>${t.stop_out ? 'STOP' : (t.close_reason || '—')}</td>
                <td class="num" title="${sz}">${ml}</td>
            </tr>`;
        }).join('');
    } catch (err) { console.error('Trades error:', err); }
}

function updateModelStatus(model) {
    const el = document.getElementById('modelStatus');
    if (!el) return;
    if (model.status === 'NO_MODEL') { el.innerHTML = '<span class="empty">No trained model</span>'; return; }
    if (model.status === 'ERROR') { el.innerHTML = '<span class="empty">Error: ' + model.message + '</span>'; return; }
    const m = model.metrics || {};
    el.innerHTML = `
        <div class="detail"><span class="label">Status</span><span class="value positive">READY</span></div>
        <div class="detail"><span class="label">Accuracy</span><span class="value">${(m.accuracy * 100).toFixed(1)}%</span></div>
        <div class="detail"><span class="label">Precision</span><span class="value">${(m.precision * 100).toFixed(1)}%</span></div>
        <div class="detail"><span class="label">F1 Score</span><span class="value">${(m.f1 * 100).toFixed(1)}</span></div>
        <div class="detail"><span class="label">Samples</span><span class="value">${m.total_samples || 0}</span></div>
        <div class="detail"><span class="label">Features</span><span class="value">${(m.feature_names || []).length}</span></div>
        <div class="detail"><span class="label">Trained</span><span class="value">${m.trained_at ? new Date(m.trained_at).toLocaleString() : 'N/A'}</span></div>
    `;
}

function updateTFTable(tfStats) {
    const tbody = document.getElementById('tfTableBody');
    if (!tbody) return;
    if (!tfStats || Object.keys(tfStats).length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No trades yet</td></tr>';
        return;
    }
    const order = ['1m', '5m', '15m', '30m', '1h', '2h', '4h'];
    const sorted = Object.entries(tfStats)
        .filter(([tf]) => order.includes(tf))
        .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
    if (sorted.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No trades yet</td></tr>';
        return;
    }
    tbody.innerHTML = sorted.map(([tf, s]) => `
        <tr>
            <td><strong>${tf}</strong></td>
            <td class="num">${s.trades}</td>
            <td class="num ${s.win_rate >= 50 ? 'positive' : 'negative'}">${s.win_rate}%</td>
            <td class="num ${s.avg_pnl >= 0 ? 'positive' : 'negative'}">${s.avg_pnl >= 0 ? '+' : ''}${s.avg_pnl}%</td>
            <td class="num ${s.total_pnl >= 0 ? 'positive' : 'negative'}">${s.total_pnl >= 0 ? '+' : ''}${s.total_pnl.toFixed(2)}%</td>
        </tr>
    `).join('');
}

function updateV11Status(v11data) {
    const el = document.getElementById('v11Status');
    if (!el || !v11data) return;
    const sent = v11data.sentinel || {};
    const reg = v11data.registry || {};
    const ml = v11data.ml_predictions || {};
    const drift = v11data.drift_alerts || 0;
    el.innerHTML = `
        <div class="detail"><span class="label">Sentinel</span><span class="value ${sent.halted ? 'negative' : 'positive'}">${sent.halted ? 'HALTED' : 'CLEAR'}</span></div>
        <div class="detail"><span class="label">Triggers</span><span class="value">${sent.total_triggers || 0}</span></div>
        <div class="detail"><span class="label">Champion</span><span class="value">${reg.champion_version || 'None'}</span></div>
        <div class="detail"><span class="label">Candidates</span><span class="value">${reg.active_candidates || 0}</span></div>
        <div class="detail"><span class="label">ML Predictions</span><span class="value">${ml.total || 0} (avg: ${ml.avg_prob || 0})</span></div>
        <div class="detail"><span class="label">Approved / Rejected</span><span class="value">${ml.approved || 0} / ${ml.rejected || 0}</span></div>
        <div class="detail"><span class="label">Drift Alerts</span><span class="value ${drift > 0 ? 'negative' : 'positive'}">${drift}</span></div>
        <div class="detail"><span class="label">Governance</span><span class="value">${(v11data.governance || []).length}</span></div>
    `;
}

function updateC2Log(actions) {
    const tbody = document.getElementById('c2LogTableBody');
    if (!tbody) return;
    if (!actions || actions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty">No actions yet</td></tr>';
        return;
    }
    tbody.innerHTML = actions.slice().reverse().map(a => {
        const d = a.details ? Object.entries(a.details).map(([k, v]) => k + ': ' + v).join(', ') : '—';
        return `<tr>
            <td class="num">${new Date(a.timestamp).toLocaleString()}</td>
            <td><strong>${a.action}</strong></td>
            <td>${d}</td>
        </tr>`;
    }).join('');
}

function updateMTFMatrix(data) {
    const container = document.getElementById('mtfMatrix');
    if (!container || !data || !data.cells) return;
    const symbols = data.symbols;
    const timeframes = data.timeframes;
    const cells = data.cells;
    const cols = timeframes.length + 1;
    let html = '<div class="mtf-grid" style="grid-template-columns: repeat(' + cols + ', 1fr);">';
    html += '<div class="mtf-header">Asset</div>';
    timeframes.forEach(tf => { html += '<div class="mtf-header">' + tf + '</div>'; });
    symbols.forEach(sym => {
        html += '<div class="mtf-symbol">' + sym.replace('/USDT', '') + '</div>';
        timeframes.forEach(tf => {
            const cell = cells[sym] && cells[sym][tf] ? cells[sym][tf] : {};
            const regime = cell.regime || 'unknown';
            const pos = cell.open_positions || 0;
            const ml = cell.avg_ml_prob || 0;
            html += '<div class="mtf-cell ' + regime + '" title="' + sym + ' ' + tf + ': ' + regime + ' | ' + pos + ' open | ML: ' + ml + '">';
            if (pos > 0) html += '<div class="tf-positions">' + pos + ' open</div>';
            html += '<div class="tf-regime">' + regime.replace('_', ' ') + '</div>';
            html += '<div class="tf-ml">ML: ' + ml.toFixed(2) + '</div>';
            html += '</div>';
        });
    });
    html += '</div>';
    container.innerHTML = html;
}

async function loadSupportResistance() {
    const symbol = document.getElementById('srSymbol').value;
    const tf = document.getElementById('srTimeframe').value;
    const container = document.getElementById('srPanel');
    if (!container) return;
    try {
        const res = await fetchAuth('/api/support-resistance');
        if (!res) return;
        const data = await res.json();
        const sr = data[symbol] && data[symbol][tf] ? data[symbol][tf] : null;
        if (!sr || sr.error) {
            container.innerHTML = '<div class="sr-grid"><div class="sr-section"><span class="empty">' + (sr ? sr.error : 'No data') + '</span></div></div>';
            return;
        }
        const levelsHtml = sr.levels.map(l => {
            const d = l.distance >= 0 ? '+' + l.distance.toFixed(2) + '%' : l.distance.toFixed(2) + '%';
            return '<div class="sr-level ' + l.type + '"><span class="sr-label">' + l.label + '</span><span class="sr-value">' + l.level.toLocaleString() + '</span><span class="sr-distance ' + (l.distance >= 0 ? 'positive' : 'negative') + '">' + d + '</span></div>';
        }).join('');
        const projHtml = sr.projected.map(p => {
            const d = p.distance >= 0 ? '+' + p.distance.toFixed(2) + '%' : p.distance.toFixed(2) + '%';
            return '<div class="sr-level ' + p.type + '"><span class="sr-label">' + p.label + '</span><span class="sr-value">' + p.level.toLocaleString() + '</span><span class="sr-distance ' + (p.distance >= 0 ? 'positive' : 'negative') + '">' + d + '</span></div>';
        }).join('');
        let bounceHtml = '';
        if (sr.bounce_stats && Object.keys(sr.bounce_stats).length > 0) {
            bounceHtml = Object.entries(sr.bounce_stats).map(([label, s]) => {
                const wc = s.win_rate >= 60 ? 'positive' : s.win_rate >= 40 ? 'neutral' : 'negative';
                return '<div class="sr-level current"><span class="sr-label">' + label + '</span><span class="sr-value">' + s.tests + 'T / ' + s.bounces + 'B / ' + s.breaks + 'Br</span><span class="sr-distance ' + wc + '">' + s.win_rate + '%</span></div>';
            }).join('');
        } else {
            bounceHtml = '<div class="sr-level current"><span class="sr-label">—</span><span class="sr-value" style="color:var(--text-muted)">Accumulating data...</span><span class="sr-distance">—</span></div>';
        }
        container.innerHTML = '<div class="sr-grid">' +
            '<div class="sr-section"><div class="sr-section-title">Current Levels</div><div class="sr-levels">' + levelsHtml + '</div></div>' +
            '<div class="sr-section"><div class="sr-section-title">Projected Next Candle</div><div class="sr-levels">' + projHtml + '</div></div>' +
            '<div class="sr-section"><div class="sr-section-title">Bounce Win Rate</div><div class="sr-levels">' + bounceHtml + '</div></div>' +
            '</div>';
    } catch (err) {
        container.innerHTML = '<div class="sr-grid"><div class="sr-section"><span class="empty">Error: ' + err.message + '</span></div></div>';
    }
}

// ==================== CLOCK ====================
function updateClock() {
    const el = document.getElementById('clock');
    if (el) el.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
}

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', async () => {
    const loggedIn = await autoLogin();
    if (!loggedIn) return;

    document.getElementById('app').style.display = 'block';
    updateClock();
    setInterval(updateClock, 1000);

    loadDashboard();
    loadMTFMatrix();
    loadSupportResistance();
    initSSE();

    setInterval(loadDashboard, 10000);
    setInterval(loadMTFMatrix, 15000);
    setInterval(loadSupportResistance, 30000);
});
