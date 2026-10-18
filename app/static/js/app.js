/* Credit Card Dashboard — Frontend */
const API = '';
let mainChart = null;
let currentChart = 'spending';
let currentView = 'daily';
let allData = { transactions: [], daily: [], monthly: [], category: [], vendor: [], points: [] };

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
    const [txns, daily, monthly, cat, vendor, points, stmts] = await Promise.all([
        fetchJSON(`/api/transactions${params}`),
        fetchJSON(`/api/spending/daily${params}`),
        fetchJSON(`/api/spending/monthly${params}`),
        fetchJSON(`/api/spending/category${params}`),
        fetchJSON(`/api/spending/vendor${params}`),
        fetchJSON(`/api/points${params}`),
        fetchJSON('/api/statements'),
    ]);

    allData.transactions = txns.transactions;
    allData.daily = daily.data;
    allData.monthly = monthly.data;
    allData.category = cat.data;
    allData.vendor = vendor.data;
    allData.points = points.data;

    document.getElementById('txn-count').textContent = `${stmts.transaction_count} transactions`;
    renderTransactions(allData.transactions);
    renderStatements(stmts.statements);
    renderChart();
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

// ── Chart Controls ────────────────────────────────────────────────

function switchView(view) {
    currentView = view;
    document.querySelectorAll('[data-view]').forEach(b => {
        b.classList.toggle('active', b.dataset.view === view);
    });
    renderChart();
}

function switchChart(chart) {
    currentChart = chart;
    document.querySelectorAll('[data-chart]').forEach(b => {
        b.classList.toggle('active', b.dataset.chart === chart);
    });
    // Show/hide daily/monthly toggle based on chart type
    const toggleGroup = document.querySelector('.toggle-group');
    if (toggleGroup) {
        toggleGroup.style.display = chart === 'spending' ? '' : 'none';
    }
    renderChart();
}

// ── Charts ────────────────────────────────────────────────────────

function renderChart() {
    if (mainChart) mainChart.destroy();

    const ctx = document.getElementById('main-chart').getContext('2d');

    switch (currentChart) {
        case 'spending': currentView === 'daily' ? renderDailyChart(ctx) : renderMonthlyChart(ctx); break;
        case 'category': renderCategoryChart(ctx); break;
        case 'vendor':   renderVendorChart(ctx); break;
        case 'points':   renderPointsChart(ctx); break;
    }
}

function renderDailyChart(ctx) {
    const data = allData.daily;
    mainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Daily Spending',
                data: data.map(d => d.total),
                backgroundColor: '#6366f180',
                borderColor: '#6366f1',
                borderWidth: 1,
                borderRadius: 2,
            }],
        },
        options: spendingChartOptions('$'),
    });
}

function renderMonthlyChart(ctx) {
    const data = allData.monthly;
    mainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.month),
            datasets: [{
                label: 'Monthly Spending',
                data: data.map(d => d.total),
                backgroundColor: '#6366f180',
                borderColor: '#6366f1',
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: spendingChartOptions('$'),
    });
}

function renderCategoryChart(ctx) {
    // Aggregate by category across all dates
    const catTotals = {};
    allData.category.forEach(d => {
        catTotals[d.category] = (catTotals[d.category] || 0) + d.total;
    });

    const cats = Object.keys(catTotals).sort((a, b) => catTotals[b] - catTotals[a]);
    const colors = cats.map(c => CATEGORY_COLORS[c] || '#999');

    mainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: cats,
            datasets: [{
                label: 'Total Spend',
                data: cats.map(c => catTotals[c]),
                backgroundColor: colors.map(c => c + '80'),
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: spendingChartOptions('$'),
    });
}

function renderVendorChart(ctx) {
    // Aggregate by vendor
    const vendorTotals = {};
    allData.vendor.forEach(d => {
        vendorTotals[d.vendor] = (vendorTotals[d.vendor] || 0) + d.total;
    });

    const vendors = Object.keys(vendorTotals).sort((a, b) => vendorTotals[b] - vendorTotals[a]);
    const colors = vendors.map((_, i) => VENDOR_COLORS[i % VENDOR_COLORS.length]);

    mainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: vendors.map(v => v.length > 25 ? v.substring(0, 25) + '…' : v),
            datasets: [{
                label: 'Total Spend',
                data: vendors.map(v => vendorTotals[v]),
                backgroundColor: colors.map(c => c + '80'),
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            ...spendingChartOptions('$'),
            indexAxis: 'y',
            plugins: {
                ...spendingChartOptions('$').plugins,
                legend: { display: false },
            },
        },
    });
}

function renderPointsChart(ctx) {
    const catTotals = {};
    const catColors = {};
    allData.points.forEach(d => {
        catTotals[d.category] = (catTotals[d.category] || 0) + d.points;
        catColors[d.category] = CATEGORY_COLORS[d.category] || '#999';
    });

    const cats = Object.keys(catTotals).sort((a, b) => catTotals[b] - catTotals[a]);

    mainChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: cats,
            datasets: [{
                label: 'Points Earned',
                data: cats.map(c => catTotals[c]),
                backgroundColor: cats.map(c => (catColors[c] || '#999') + '80'),
                borderColor: cats.map(c => catColors[c] || '#999'),
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: spendingChartOptions('pts'),
    });
}

function spendingChartOptions(unit) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                display: false,
            },
            tooltip: {
                callbacks: {
                    label: ctx => `${unit === '$' ? '$' : ''}${ctx.parsed.y.toLocaleString()}${unit === 'pts' ? ' pts' : ''}`,
                },
            },
        },
        scales: {
            x: {
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