/* Credit Card Dashboard — Frontend */
const API = '';
let mainChart = null;
let currentChartType = 'daily';
let allData = { transactions: [], daily: [], category: [], vendor: [], points: [] };

const CATEGORY_COLORS = {
    'Eligible Food/Drink': '#22c55e',
    'Eligible Streaming': '#818cf8',
    'Eligible Gas/Transit/Ride Share': '#f59e0b',
    'All Other Purchases': '#6b7280',
};

const VENDOR_COLORS = [
    '#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
    '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#a855f7',
    '#84cc16', '#e11d48', '#0ea5e9', '#d946ef', '#eab308',
];

// ── Init ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    document.getElementById('upload-form').addEventListener('submit', handleUpload);
});

async function loadAllData() {
    const params = getFilterParams();
    const [txns, daily, cat, vendor, points, stmts] = await Promise.all([
        fetchJSON(`/api/transactions${params}`),
        fetchJSON(`/api/spending/daily${params}`),
        fetchJSON(`/api/spending/category${params}`),
        fetchJSON(`/api/spending/vendor${params}`),
        fetchJSON(`/api/points${params}`),
        fetchJSON('/api/statements'),
    ]);

    allData.transactions = txns.transactions;
    allData.daily = daily.data;
    allData.category = cat.data;
    allData.vendor = vendor.data;
    allData.points = points.data;

    document.getElementById('txn-count').textContent = `${stmts.transaction_count} transactions`;
    renderTransactions(allData.transactions);
    renderStatements(stmts.statements);
    renderChart(currentChartType);
}

function getFilterParams() {
    const start = document.getElementById('filter-start').value;
    const end = document.getElementById('filter-end').value;
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const s = params.toString();
    return s ? `?${s}` : '';
}

function applyFilters() { loadAllData(); }
function clearFilters() {
    document.getElementById('filter-start').value = '';
    document.getElementById('filter-end').value = '';
    loadAllData();
}

// ── Charts ────────────────────────────────────────────────────────

function switchChart(type) {
    currentChartType = type;
    document.querySelectorAll('.chart-controls .btn-small').forEach(b => {
        b.classList.toggle('active', b.dataset.chart === type);
    });
    renderChart(type);
}

function renderChart(type) {
    if (mainChart) mainChart.destroy();

    const ctx = document.getElementById('main-chart').getContext('2d');

    switch (type) {
        case 'daily':   renderDailyChart(ctx); break;
        case 'category': renderCategoryChart(ctx); break;
        case 'vendor':  renderVendorChart(ctx); break;
        case 'points':  renderPointsChart(ctx); break;
    }
}

function renderDailyChart(ctx) {
    const data = allData.daily;
    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Daily Spending',
                data: data.map(d => d.total),
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }],
        },
        options: chartOptions('$'),
    });
}

function renderCategoryChart(ctx) {
    const byDate = {};
    const cats = new Set();
    allData.category.forEach(d => {
        if (!byDate[d.date]) byDate[d.date] = {};
        byDate[d.date][d.category] = d.total;
        cats.add(d.category);
    });

    const dates = Object.keys(byDate).sort();
    const datasets = [...cats].map(cat => ({
        label: cat,
        data: dates.map(d => byDate[d][cat] || 0),
        borderColor: CATEGORY_COLORS[cat] || '#999',
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 1,
    }));

    mainChart = new Chart(ctx, {
        type: 'line',
        data: { labels: dates, datasets },
        options: chartOptions('$'),
    });
}

function renderVendorChart(ctx) {
    const byDate = {};
    const vendors = new Set();
    allData.vendor.forEach(d => {
        if (!byDate[d.date]) byDate[d.date] = {};
        byDate[d.date][d.vendor] = d.total;
        vendors.add(d.vendor);
    });

    const dates = Object.keys(byDate).sort();
    const vendorList = [...vendors];
    const datasets = vendorList.map((v, i) => ({
        label: v.length > 30 ? v.substring(0, 30) + '…' : v,
        data: dates.map(d => byDate[d][v] || 0),
        borderColor: VENDOR_COLORS[i % VENDOR_COLORS.length],
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 1,
    }));

    mainChart = new Chart(ctx, {
        type: 'line',
        data: { labels: dates, datasets },
        options: chartOptions('$'),
    });
}

function renderPointsChart(ctx) {
    const byDate = {};
    const cats = new Set();
    allData.points.forEach(d => {
        if (!byDate[d.date]) byDate[d.date] = {};
        byDate[d.date][d.category] = (byDate[d.date][d.category] || 0) + d.points;
        cats.add(d.category);
    });

    const dates = Object.keys(byDate).sort();
    const datasets = [...cats].map(cat => ({
        label: cat,
        data: dates.map(d => byDate[d][cat] || 0),
        borderColor: CATEGORY_COLORS[cat] || '#999',
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 1,
    }));

    // Cumulative line
    let cumulative = 0;
    const cumulativeData = dates.map(d => {
        const dayTotal = Object.values(byDate[d]).reduce((s, v) => s + v, 0);
        cumulative += dayTotal;
        return cumulative;
    });
    datasets.push({
        label: 'Cumulative Points',
        data: cumulativeData,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderDash: [5, 3],
    });

    mainChart = new Chart(ctx, {
        type: 'line',
        data: { labels: dates, datasets },
        options: chartOptions('pts'),
    });
}

function chartOptions(unit) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                display: true,
                position: 'bottom',
                labels: { color: '#9ca3af', boxWidth: 12, padding: 15, font: { size: 11 } },
            },
            tooltip: {
                callbacks: {
                    label: ctx => `${ctx.dataset.label}: ${unit === '$' ? '$' : ''}${ctx.parsed.y.toLocaleString()}${unit === 'pts' ? ' pts' : ''}`,
                },
            },
            zoom: {
                pan: { enabled: true, mode: 'x' },
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    drag: { enabled: true, backgroundColor: 'rgba(99,102,241,0.1)', borderColor: '#6366f1' },
                    mode: 'x',
                },
            },
        },
        scales: {
            x: {
                type: 'time',
                time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#6b7280', maxTicksLimit: 20 },
            },
            y: {
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: {
                    color: '#6b7280',
                    callback: v => unit === '$' ? `$${v.toLocaleString()}` : v.toLocaleString(),
                },
            },
        },
    };
}

function resetZoom() {
    if (mainChart) mainChart.resetZoom();
}

// ── Transactions Table ────────────────────────────────────────────

function renderTransactions(txns) {
    const tbody = document.getElementById('txn-body');
    document.getElementById('table-count').textContent = `(${txns.length})`;

    tbody.innerHTML = txns.map(t => {
        const amtClass = t.amount < 0 ? 'amount-neg' : 'amount-pos';
        const catClass = `cat-${t.points_rate}x`;
        return `<tr>
            <td>${t.transaction_date}</td>
            <td>${escHtml(t.description)}</td>
            <td>${escHtml(t.cardholder)}</td>
            <td class="num ${amtClass}">$${t.amount.toFixed(2)}</td>
            <td class="num"><span class="points-badge">${t.points}</span></td>
            <td><span class="cat-badge ${catClass}">${t.points_rate}x ${escHtml(t.points_category)}</span></td>
            <td>${escHtml(t.card)}</td>
        </tr>`;
    }).join('');
}

// ── Statements ────────────────────────────────────────────────────

function renderStatements(stmts) {
    const div = document.getElementById('statements-list');
    if (!stmts.length) {
        div.innerHTML = '<p style="color:var(--text-dim)">No statements uploaded yet.</p>';
        return;
    }

    div.innerHTML = stmts.map(s => `
        <div class="statement-row">
            <div class="statement-info">
                <strong>${escHtml(s.statement_date)}</strong>
                <span class="dim">· ${s.total_transactions || '—'} txns · $${(s.total_spend || 0).toFixed(2)} · ${(s.total_points || 0).toLocaleString()} pts</span>
                <span class="dim">· ${escHtml(s.filename || '')}</span>
            </div>
            <div class="statement-actions">
                <button class="btn btn-small btn-secondary" onclick="viewPdf('${escHtml(s.filename)}')">View PDF</button>
                <button class="btn btn-small btn-danger" onclick="deleteStmt(${s.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

// ── Upload ────────────────────────────────────────────────────────

function showUpload() { document.getElementById('upload-modal').classList.remove('hidden'); }
function hideUpload() {
    document.getElementById('upload-modal').classList.add('hidden');
    document.getElementById('upload-status').classList.add('hidden');
}

async function handleUpload(e) {
    e.preventDefault();
    const form = e.target;
    const files = form.querySelector('input[type=file]').files;
    if (!files.length) return;

    const status = document.getElementById('upload-status');
    status.className = 'status';
    status.textContent = `Uploading ${files.length} file(s)...`;
    status.classList.remove('hidden');

    const fd = new FormData();
    for (const file of files) {
        fd.append('files', file);
    }

    try {
        const res = await fetch(`${API}/api/upload`, { method: 'POST', body: fd });
        const data = await res.json();

        if (!res.ok) {
            status.className = 'status error';
            status.textContent = `Error: ${data.detail || 'Upload failed'}`;
            return;
        }

        const parts = [];
        if (data.ingested > 0) {
            const txns = data.results.reduce((s, r) => s + r.transactions, 0);
            const spend = data.results.reduce((s, r) => s + r.total_spend, 0);
            const pts = data.results.reduce((s, r) => s + r.total_points, 0);
            parts.push(`✓ ${data.ingested} statement(s): ${txns} transactions, $${spend.toFixed(2)} spend, ${pts.toLocaleString()} pts`);
        }
        if (data.errors.length > 0) {
            parts.push(`${data.errors.length} failed: ${data.errors.map(e => e.filename).join(', ')}`);
        }

        status.className = data.errors.length ? 'status error' : 'status ok';
        status.textContent = parts.join(' · ') || 'No new statements to ingest';
        form.reset();

        setTimeout(() => { hideUpload(); loadAllData(); }, 2000);
    } catch (err) {
        status.className = 'status error';
        status.textContent = `Error: ${err.message}`;
    }
}

// ── PDF Viewer ────────────────────────────────────────────────────

function viewPdf(filename) {
    document.getElementById('pdf-title').textContent = filename;
    document.getElementById('pdf-viewer').src = `${API}/api/pdf/${filename}`;
    document.getElementById('pdf-modal').classList.remove('hidden');
}

function hidePdf() {
    document.getElementById('pdf-modal').classList.add('hidden');
    document.getElementById('pdf-viewer').src = '';
}

// ── Delete ────────────────────────────────────────────────────────

async function deleteStmt(id) {
    if (!confirm('Delete this statement and all its transactions?')) return;
    await fetch(`${API}/api/statements/${id}`, { method: 'DELETE' });
    loadAllData();
}

// ── Utils ─────────────────────────────────────────────────────────

async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

function escHtml(s) {
    const div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
}