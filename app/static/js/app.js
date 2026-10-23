/* Credit Card Dashboard — Frontend */
const API = '';
let mainChart = null, categoryChart = null, vendorChart = null, pointsChart = null;
let currentView = 'monthly';
let currentTableView = 'all';
let sortColumn = 'transaction_date';
let sortDirection = 'desc';
let selectedMonth = '';
let allData = { transactions: [], daily: [], monthly: [], categories: [], vendor: [], points: [] };
let vendorRules = [];
let categoryList = [];
// Column filters (multi-select; OR within a column, AND across columns)
let filters = { vendors: new Set(), categories: new Set(), pointsCategories: new Set() };
let filterOptions = { vendors: [], categories: [], pointsCategories: [] };
let activeFilterCol = null;
const FILTER_COLS = {
    vendors: { label: 'Vendor', optionsKey: 'vendors', param: 'vendors' },
    categories: { label: 'Category', optionsKey: 'categories', param: 'categories' },
    pointsCategories: { label: 'Points Cat', optionsKey: 'pointsCategories', param: 'points_categories' },
};

const CATEGORY_COLORS = {
    'Grocery': '#22c55e', 'Dining & Drinks': '#f97316', 'Gas & Transit': '#f59e0b',
    'Subscriptions': '#818cf8', 'Shopping': '#6366f1', 'Health': '#ec4899',
    'Telecom': '#06b6d4', 'Home & Services': '#14b8a6', 'Donations': '#a855f7',
    'Travel': '#e11d48', 'Kids & Education': '#84cc16', 'Auto': '#78716c',
    'Gifts': '#d946ef', 'Other': '#6b7280',
};
const VENDOR_COLORS = [
    '#6366f1','#22c55e','#f59e0b','#ef4444','#8b5cf6',
    '#06b6d4','#ec4899','#14b8a6','#f97316','#a855f7',
    '#84cc16','#e11d48','#0ea5e9','#d946ef','#eab308',
];

// ── Init ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    loadVendorRules();
    loadCategoryList();
    document.getElementById('upload-form').addEventListener('submit', handleUpload);

    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (sortColumn === col) { sortDirection = sortDirection === 'asc' ? 'desc' : 'asc'; }
            else { sortColumn = col; sortDirection = col === 'transaction_date' ? 'desc' : 'asc'; }
            document.querySelectorAll('.sortable').forEach(h => h.classList.remove('asc', 'desc'));
            th.classList.add(sortDirection);
            renderTransactions();
        });
    });
});

async function loadAllData() {
    const params = getFilterParams();
    const dateStr = getDateParams().toString();
    const [txns, daily, monthly, cats, vendor, points, stmts, fopts] = await Promise.all([
        fetchJSON(`/api/transactions${params}`), fetchJSON(`/api/spending/daily${params}`),
        fetchJSON(`/api/spending/monthly${params}`), fetchJSON(`/api/spending/categories${params}`),
        fetchJSON(`/api/spending/vendor${params}`), fetchJSON(`/api/points${params}`),
        fetchJSON('/api/statements'),
        fetchJSON(`/api/filters${dateStr ? '?' + dateStr : ''}`),
    ]);
    allData.transactions = txns.transactions;
    allData.daily = daily.data; allData.monthly = monthly.data;
    allData.categories = cats.data; allData.vendor = vendor.data;
    allData.points = points.data;
    filterOptions = {
        vendors: fopts.vendors || [],
        categories: fopts.categories || [],
        pointsCategories: fopts.points_categories || [],
    };
    document.getElementById('txn-count').textContent = `${stmts.transaction_count} transactions`;
    buildMonthSelect(); renderTransactions(); renderStatements(stmts.statements);
    renderMainChart(); renderPieCharts();
    renderFilterIndicators();
    if (activeFilterCol) renderFilterMenu(document.getElementById('filter-search').value);
}

function getDateParams() {
    const start = document.getElementById('filter-start').value;
    const end = document.getElementById('filter-end').value;
    const p = new URLSearchParams();
    if (start) p.set('start', start); if (end) p.set('end', end);
    return p;
}

function getFilterParams() {
    const p = getDateParams();
    for (const [col, cfg] of Object.entries(FILTER_COLS)) {
        filters[col].forEach(v => p.append(cfg.param, v));
    }
    const s = p.toString(); return s ? `?${s}` : '';
}

function applyFilters() { loadAllData(); }
function clearFilters() {
    document.getElementById('filter-start').value = '';
    document.getElementById('filter-end').value = '';
    selectedMonth = '';
    currentView = 'monthly';
    currentTableView = 'all';
    Object.values(filters).forEach(s => s.clear());
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === 'monthly'));
    document.querySelectorAll('[data-tview]').forEach(b => b.classList.toggle('active', b.dataset.tview === 'all'));
    document.getElementById('month-select').classList.toggle('hidden', true);
    loadAllData();
}

// ── Month Select ──────────────────────────────────────────────────

function buildMonthSelect() {
    const months = new Set();
    allData.transactions.forEach(t => months.add(t.transaction_date.substring(0, 7)));
    const sorted = [...months].sort().reverse();
    const sel = document.getElementById('month-select');
    sel.innerHTML = '<option value="">All Months</option>' +
        sorted.map(m => `<option value="${m}"${m === selectedMonth ? ' selected' : ''}>${formatMonth(m)}</option>`).join('');
}

function formatMonth(ym) {
    const [y, m] = ym.split('-');
    const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${names[parseInt(m)-1]} ${y}`;
}

function switchTableView(view) {
    currentTableView = view;
    document.querySelectorAll('[data-tview]').forEach(b => b.classList.toggle('active', b.dataset.tview === view));
    document.getElementById('month-select').classList.toggle('hidden', view !== 'monthly');
    if (view === 'monthly' && !selectedMonth) {
        const first = document.getElementById('month-select').querySelector('option:not([value=""])');
        if (first) { selectedMonth = first.value; document.getElementById('month-select').value = selectedMonth; }
    }
    renderTransactions();
}

function filterByMonth(month) { selectedMonth = month; renderTransactions(); }

function filterByChartMonth(month) {
    // Set date range to the selected month
    const [y, m] = month.split('-');
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    document.getElementById('filter-start').value = `${month}-01`;
    document.getElementById('filter-end').value = `${month}-${String(lastDay).padStart(2, '0')}`;

    // Switch spending chart to daily view for this month
    currentView = 'daily';
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === 'daily'));

    // Also filter the table
    selectedMonth = month;
    currentTableView = 'monthly';
    document.querySelectorAll('[data-tview]').forEach(b => b.classList.toggle('active', b.dataset.tview === 'monthly'));
    document.getElementById('month-select').classList.toggle('hidden', false);
    document.getElementById('month-select').value = month;

    loadAllData();
}

// ── Raw Description Toggle ────────────────────────────────────────

function toggleRawDesc() {
    const show = document.getElementById('show-raw-desc').checked;
    document.querySelectorAll('.raw-col').forEach(el => el.classList.toggle('hidden', !show));
}

// ── Categories ────────────────────────────────────────────────────

async function loadCategoryList() {
    const data = await fetchJSON('/api/categories');
    categoryList = data.categories;
    populateCatDropdowns();
}

function populateCatDropdowns() {
    const sel = document.getElementById('rule-category');
    if (sel) sel.innerHTML = catDropdownOptions('');
    const vm = document.getElementById('vm-category');
    if (vm) vm.innerHTML = catDropdownOptions('');
}

function catDropdownOptions(selected) {
    return '<option value="">None (use auto-categorizer)</option>' +
        categoryList.map(c => `<option value="${escHtml(c)}"${c === selected ? ' selected' : ''}>${escHtml(c)}</option>`).join('');
}

function catCssClass(cat) { return `cat-${(cat||'other').toLowerCase().replace(/[^a-z]/g,'')}`; }

function toggleCategories() {
    const panel = document.getElementById('cats-panel');
    const btn = document.getElementById('cats-toggle');
    panel.classList.toggle('hidden');
    btn.textContent = panel.classList.contains('hidden') ? 'Show' : 'Hide';
    if (!panel.classList.contains('hidden')) renderCategories();
}

function renderCategories() {
    const div = document.getElementById('cats-list');
    div.innerHTML = categoryList.map((c, i) => `
        <div class="cat-row">
            <span class="cat-row-name"><span class="cat-badge ${catCssClass(c)}">${escHtml(c)}</span></span>
            <div class="rule-actions">
                <button class="btn btn-small btn-secondary" onclick="editCategoryName(${i})">Edit</button>
                <button class="btn btn-small btn-danger" onclick="deleteCategory(${i})">Delete</button>
            </div>
        </div>
    `).join('');
}

async function addCategory() {
    const input = document.getElementById('new-cat-name');
    const name = input.value.trim();
    if (!name || categoryList.includes(name)) return;
    categoryList.push(name);
    await fetchJSON_withMethod('PUT', '/api/categories', { categories: categoryList });
    input.value = '';
    populateCatDropdowns(); renderCategories();
}

async function editCategoryName(index) {
    const old = categoryList[index];
    const newName = prompt('Category name:', old);
    if (newName === null || !newName.trim() || newName.trim() === old) return;
    categoryList[index] = newName.trim();
    await fetchJSON_withMethod('PUT', '/api/categories', { categories: categoryList });
    populateCatDropdowns(); renderCategories(); loadAllData();
}

async function deleteCategory(index) {
    const name = categoryList[index];
    if (!confirm(`Delete category "${name}"?`)) return;
    categoryList.splice(index, 1);
    await fetchJSON_withMethod('PUT', '/api/categories', { categories: categoryList });
    populateCatDropdowns(); renderCategories();
}

// ── Vendor Rules ──────────────────────────────────────────────────

async function loadVendorRules() {
    const data = await fetchJSON('/api/vendor-rules');
    vendorRules = data.rules;
    renderRules();
}

function toggleRules() {
    const panel = document.getElementById('rules-panel');
    const btn = document.getElementById('rules-toggle');
    panel.classList.toggle('hidden');
    btn.textContent = panel.classList.contains('hidden') ? 'Show' : 'Hide';
}

function renderRules() {
    const div = document.getElementById('rules-list');
    if (!vendorRules.length) {
        div.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem">No rules yet. Click a vendor cell in the table to create one.</p>';
        return;
    }
    div.innerHTML = vendorRules.map((r, i) => `
        <div class="rule-row">
            <span class="rule-pattern">${escHtml(r.pattern)}</span>
            <span class="rule-vendor">${escHtml(r.vendor)}</span>
            <span class="rule-cat">${r.category ? `<span class="cat-badge ${catCssClass(r.category)}">${escHtml(r.category)}</span>` : '<span class="dim">-</span>'}</span>
            <div class="rule-actions">
                <button class="btn btn-small btn-secondary" onclick="editRule(${i})">Edit</button>
                <button class="btn btn-small btn-danger" onclick="deleteRule('${escAttr(r.pattern)}')">Delete</button>
            </div>
        </div>
    `).join('');
}

async function addRule() {
    const pattern = document.getElementById('rule-pattern').value.trim();
    const vendor = document.getElementById('rule-vendor').value.trim();
    const category = document.getElementById('rule-category').value;
    if (!pattern || !vendor) return;
    await fetchJSON_withMethod('POST', '/api/vendor-rules', { pattern, vendor, category });
    document.getElementById('rule-pattern').value = '';
    document.getElementById('rule-vendor').value = '';
    document.getElementById('rule-category').value = '';
    await loadVendorRules(); await loadAllData();
}

async function deleteRule(pattern) {
    if (!confirm(`Delete rule "${pattern}"?`)) return;
    await fetch(`${API}/api/vendor-rules/${encodeURIComponent(pattern)}`, { method: 'DELETE' });
    await loadVendorRules(); await loadAllData();
}

// ── Vendor Rule Modal ─────────────────────────────────────────────

function showVendorModal(title, pattern, vendor, category, oldPattern) {
    document.getElementById('vendor-modal-title').textContent = title;
    document.getElementById('vm-pattern').value = pattern || '';
    document.getElementById('vm-vendor').value = vendor || '';
    document.getElementById('vm-old-pattern').value = oldPattern || '';
    populateCatDropdowns();
    document.getElementById('vm-category').value = category || '';
    document.getElementById('vendor-modal').classList.remove('hidden');
    document.getElementById('vm-pattern').focus();
}

function hideVendorModal() { document.getElementById('vendor-modal').classList.add('hidden'); }

async function submitVendorModal(e) {
    e.preventDefault();
    const pattern = document.getElementById('vm-pattern').value.trim();
    const vendor = document.getElementById('vm-vendor').value.trim();
    const category = document.getElementById('vm-category').value;
    const oldPattern = document.getElementById('vm-old-pattern').value;
    if (!pattern || !vendor) return;
    if (oldPattern) {
        await fetchJSON_withMethod('PUT', '/api/vendor-rules', { old_pattern: oldPattern, pattern, vendor, category });
    } else {
        await fetchJSON_withMethod('POST', '/api/vendor-rules', { pattern, vendor, category });
    }
    hideVendorModal();
    await loadVendorRules(); await loadAllData();
}

function editRule(index) {
    const rule = vendorRules[index];
    showVendorModal('Edit Vendor Rule', rule.pattern, rule.vendor, rule.category || '', rule.pattern);
}

function saveVendorFromCell(txnId, rawDesc) {
    showVendorModal('Create Vendor Rule', rawDesc.trim(), '', '', '');
}

// ── Per-Transaction Category Override ─────────────────────────────

function editCategory(txnId, currentCat) {
    const td = event.target.closest('td');
    const existing = td.querySelector('select');
    if (existing) return;
    const select = document.createElement('select');
    select.innerHTML = catDropdownOptions(currentCat);
    select.value = currentCat;
    select.className = 'inline-cat-select';
    select.onchange = async () => {
        await fetchJSON_withMethod('PUT', `/api/transactions/${txnId}/category`, { category: select.value });
        await loadAllData();
    };
    select.onblur = () => { setTimeout(() => renderTransactions(), 200); };
    td.innerHTML = '';
    td.appendChild(select);
    select.focus();
}

function editNotes(txnId, currentNotes) {
    const td = event.target.closest('td');
    const existing = td.querySelector('input');
    if (existing) return;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentNotes;
    input.className = 'inline-notes-input';
    input.placeholder = 'Add note...';
    const save = async () => {
        await fetchJSON_withMethod('PUT', `/api/transactions/${txnId}/notes`, { notes: input.value });
        await loadAllData();
    };
    input.onkeydown = (e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') renderTransactions(); };
    input.onblur = save;
    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
}

// ── Charts ────────────────────────────────────────────────────────

function switchView(view) {
    currentView = view;
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    renderMainChart();
}

function renderMainChart() {
    if (mainChart) mainChart.destroy();
    const ctx = document.getElementById('main-chart').getContext('2d');
    if (currentView === 'monthly') {
        const data = allData.monthly;
        mainChart = new Chart(ctx, {
            type: 'bar',
            data: { labels: data.map(d => formatMonth(d.month)), datasets: [{ label: 'Monthly Spending', data: data.map(d => d.total),
                backgroundColor: '#6366f180', borderColor: '#6366f1', borderWidth: 1, borderRadius: 4 }] },
            options: {
                ...spendingOpts('$'),
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const month = allData.monthly[idx].month;
                        filterByChartMonth(month);
                    }
                },
                onHover: (evt, elements) => {
                    evt.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } else {
        const data = allData.daily;
        mainChart = new Chart(ctx, {
            type: 'bar',
            data: { labels: data.map(d => d.date), datasets: [{ label: 'Daily Spending', data: data.map(d => d.total),
                backgroundColor: '#6366f180', borderColor: '#6366f1', borderWidth: 1, borderRadius: 2 }] },
            options: spendingOpts('$')
        });
    }
}

function renderPieCharts() {
    // Category pie
    if (categoryChart) categoryChart.destroy();
    const catData = allData.categories;
    const catLabels = catData.map(d => d.category);
    const catColors = catLabels.map(c => CATEGORY_COLORS[c] || '#999');
    categoryChart = new Chart(document.getElementById('category-chart').getContext('2d'), {
        type: 'doughnut',
        data: { labels: catLabels, datasets: [{ data: catData.map(d => d.total), backgroundColor: catColors.map(c => c + 'cc'), borderColor: catColors, borderWidth: 1 }] },
        options: pieOpts('$')
    });

    // Vendor pie
    if (vendorChart) vendorChart.destroy();
    const vendData = allData.vendor;
    const vendTotals = {};
    vendData.forEach(x => { vendTotals[x.vendor_name] = (vendTotals[x.vendor_name] || 0) + x.total; });
    const vendSorted = Object.entries(vendTotals).sort((a, b) => b[1] - a[1]);
    const vendLabels = vendSorted.map(([v]) => v.length > 18 ? v.substring(0, 18) + '…' : v);
    const vendColors = vendLabels.map((_, i) => VENDOR_COLORS[i % VENDOR_COLORS.length]);
    vendorChart = new Chart(document.getElementById('vendor-chart').getContext('2d'), {
        type: 'doughnut',
        data: { labels: vendLabels, datasets: [{ data: vendSorted.map(([, t]) => t), backgroundColor: vendColors.map(c => c + 'cc'), borderColor: vendColors, borderWidth: 1 }] },
        options: pieOpts('$')
    });

    // Points pie
    if (pointsChart) pointsChart.destroy();
    const ptsData = allData.points;
    const ptsTotals = {}, ptsColors = {};
    ptsData.forEach(d => { ptsTotals[d.category] = (ptsTotals[d.category] || 0) + d.points; ptsColors[d.category] = CATEGORY_COLORS[d.category] || '#999'; });
    const ptsCats = Object.keys(ptsTotals).sort((a, b) => ptsTotals[b] - ptsTotals[a]);
    pointsChart = new Chart(document.getElementById('points-chart').getContext('2d'), {
        type: 'doughnut',
        data: { labels: ptsCats, datasets: [{ data: ptsCats.map(c => ptsTotals[c]), backgroundColor: ptsCats.map(c => (ptsColors[c]||'#999')+'cc'), borderColor: ptsCats.map(c => ptsColors[c]||'#999'), borderWidth: 1 }] },
        options: pieOpts('pts')
    });
}

function spendingOpts(u) {
    return {responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${u==='$'?'$':''}${c.parsed.y.toLocaleString()}${u==='pts'?' pts':''}`}}},
        scales:{x:{grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#6b7280',maxTicksLimit:20}},
            y:{grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#6b7280',callback:v=>u==='$'?`$${v.toLocaleString()}`:v.toLocaleString()}}}};
}
function pieOpts(u) {
    return {responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:true,position:'right',labels:{color:'#9ca3af',boxWidth:10,padding:8,font:{size:10}}},
            tooltip:{callbacks:{label:c=>`${c.label}: ${u==='$'?'$':''}${c.parsed.toLocaleString()}${u==='pts'?' pts':''} (${((c.parsed/c.dataset.data.reduce((a,b)=>a+b,0))*100).toFixed(1)}%)`}}}};
}

// ── Column Filter Dropdowns (Sheets-style) ────────────────────────

function openFilterMenu(col, btn, ev) {
    if (ev) ev.stopPropagation();
    const menu = document.getElementById('filter-menu');
    if (activeFilterCol === col && !menu.classList.contains('hidden')) { closeFilterMenu(); return; }
    activeFilterCol = col;
    document.getElementById('filter-menu-title').textContent = FILTER_COLS[col].label;
    const rect = btn.getBoundingClientRect();
    menu.style.left = `${window.scrollX + rect.left}px`;
    menu.style.top = `${window.scrollY + rect.bottom + 4}px`;
    menu.classList.remove('hidden');
    const search = document.getElementById('filter-search');
    search.value = '';
    renderFilterMenu('');
    search.focus();
    setTimeout(() => document.addEventListener('click', closeFilterMenuOnOutside), 0);
}

function closeFilterMenu() {
    document.getElementById('filter-menu').classList.add('hidden');
    activeFilterCol = null;
    document.removeEventListener('click', closeFilterMenuOnOutside);
}

function closeFilterMenuOnOutside(e) {
    const menu = document.getElementById('filter-menu');
    if (!menu.contains(e.target)) closeFilterMenu();
}

function filterOptionsFor(col) {
    // Selected values stay listed even if they fall outside the current date range
    const set = new Set(filterOptions[FILTER_COLS[col].optionsKey] || []);
    filters[col].forEach(v => set.add(v));
    return [...set].sort((a, b) => a.localeCompare(b));
}

function renderFilterMenu(searchText) {
    const col = activeFilterCol;
    if (!col) return;
    const sel = filters[col];
    const all = filterOptionsFor(col);
    window._filterMenuAll = all;
    const q = (searchText || '').toLowerCase();
    const shown = all.map((v, i) => [v, i]).filter(([v]) => v.toLowerCase().includes(q));
    const list = document.getElementById('filter-list');
    list.innerHTML = shown.map(([v, i]) =>
        `<label class="filter-option"><input type="checkbox" ${sel.has(v) ? 'checked' : ''} onchange="toggleFilterOption(${i})"><span>${escHtml(v)}</span></label>`
    ).join('') || '<div class="filter-empty">No matches</div>';
}

function toggleFilterOption(idx) {
    const col = activeFilterCol;
    const v = window._filterMenuAll[idx];
    if (!col || v === undefined) return;
    filters[col].has(v) ? filters[col].delete(v) : filters[col].add(v);
    loadAllData();  // selections apply immediately
}

function filterMenuAll(selectAll) {
    const col = activeFilterCol;
    if (!col) return;
    if (selectAll) (window._filterMenuAll || []).forEach(v => filters[col].add(v));
    else filters[col].clear();
    loadAllData();
}

function renderFilterIndicators() {
    document.querySelectorAll('.filter-btn[data-fcol]').forEach(btn => {
        const n = filters[btn.dataset.fcol].size;
        btn.classList.toggle('active', n > 0);
        const chip = btn.parentElement.querySelector('.filter-chip');
        if (chip) { chip.textContent = n > 0 ? `(${n})` : ''; chip.classList.toggle('hidden', n === 0); }
    });
}

// ── Transactions Table ────────────────────────────────────────────

function renderTransactions() {
    let txns = [...allData.transactions];
    if (currentTableView === 'monthly' && selectedMonth) txns = txns.filter(t => t.transaction_date.startsWith(selectedMonth));
    txns.sort((a, b) => {
        let va=a[sortColumn],vb=b[sortColumn];
        if(sortColumn==='amount'||sortColumn==='points'){va=parseFloat(va)||0;vb=parseFloat(vb)||0;}
        else{va=(va||'').toLowerCase();vb=(vb||'').toLowerCase();}
        if(va<vb)return sortDirection==='asc'?-1:1;if(va>vb)return sortDirection==='asc'?1:-1;return 0;
    });
    const tbody = document.getElementById('txn-body');
    document.getElementById('table-count').textContent = `(${txns.length})`;
    const showRaw = document.getElementById('show-raw-desc')?.checked;
    tbody.innerHTML = txns.map(t => {
        const amt = t.amount<0?'amount-neg':'amount-pos';
        const cc = catCssClass(t.category), pc = `pts-${t.points_rate}x`;
        const vd = t.vendor||t.description;
        return `<tr>
            <td>${t.transaction_date}</td>
            <td class="vendor-cell" onclick="saveVendorFromCell(${t.id},'${escAttr(t.description)}')" title="Click to create vendor rule">${escHtml(vd)}</td>
            <td class="raw-col${showRaw?'':' hidden'}">${escHtml(t.description)}</td>
            <td class="num ${amt}">$${t.amount.toFixed(2)}</td>
            <td class="num"><span class="points-badge">${t.points}</span></td>
            <td class="cat-cell" onclick="editCategory(${t.id},'${escAttr(t.category)}')" title="Click to change"><span class="cat-badge ${cc}">${escHtml(t.category||'Other')}</span></td>
            <td><span class="cat-badge ${pc}">${t.points_rate}x ${escHtml(t.points_category)}</span></td>
            <td>${escHtml(t.card)}</td>
            <td class="notes-cell" onclick="editNotes(${t.id}, '${escAttr(t.notes||'')}')"><span class="notes-text">${escHtml(t.notes||'')}</span></td>
        </tr>`;
    }).join('');
}

// ── Statements ────────────────────────────────────────────────────

function renderStatements(stmts) {
    const div = document.getElementById('statements-list');
    if(!stmts.length){div.innerHTML='<p style="color:var(--text-dim)">No statements uploaded yet.</p>';return;}
    div.innerHTML = stmts.map(s=>`<div class="statement-row"><div class="statement-info"><strong>${escHtml(s.statement_date)}</strong><span class="dim"> · $${(s.total_spend||0).toFixed(2)} · ${(s.total_points||0).toLocaleString()} pts · ${escHtml(s.filename||'')}</span></div><div class="statement-actions"><button class="btn btn-small btn-secondary" onclick="viewPdf('${escAttr(s.filename)}')">View PDF</button><button class="btn btn-small btn-danger" onclick="deleteStmt(${s.id})">Delete</button></div></div>`).join('');
}

// ── Upload ────────────────────────────────────────────────────────

function showUpload(){document.getElementById('upload-modal').classList.remove('hidden');}
function hideUpload(){document.getElementById('upload-modal').classList.add('hidden');document.getElementById('upload-status').classList.add('hidden');}

async function handleUpload(e){
    e.preventDefault();const form=e.target;const files=form.querySelector('input[type=file]').files;
    if(!files.length)return;const status=document.getElementById('upload-status');
    status.className='status';status.textContent=`Uploading ${files.length} file(s)...`;status.classList.remove('hidden');
    const fd=new FormData();for(const f of files)fd.append('files',f);
    try{const res=await fetch(`${API}/api/upload`,{method:'POST',body:fd});const data=await res.json();
    if(!res.ok){status.className='status error';status.textContent=`Error: ${data.detail||'Upload failed'}`;return;}
    const parts=[];if(data.ingested>0){const tx=data.results.reduce((s,r)=>s+r.transactions,0);const sp=data.results.reduce((s,r)=>s+r.total_spend,0);const pt=data.results.reduce((s,r)=>s+r.total_points,0);parts.push(`✓ ${data.ingested} statement(s): ${tx} txns, $${sp.toFixed(2)}, ${pt.toLocaleString()} pts`);}
    if(data.errors.length)parts.push(`${data.errors.length} failed`);
    status.className=data.errors.length?'status error':'status ok';status.textContent=parts.join(' · ')||'No new statements';
    form.reset();setTimeout(()=>{hideUpload();loadAllData();},2000);
    }catch(err){status.className='status error';status.textContent=`Error: ${err.message}`;}
}

function viewPdf(fn){document.getElementById('pdf-title').textContent=fn;document.getElementById('pdf-viewer').src=`${API}/api/pdf/${fn}`;document.getElementById('pdf-modal').classList.remove('hidden');}
function hidePdf(){document.getElementById('pdf-modal').classList.add('hidden');document.getElementById('pdf-viewer').src='';}
async function deleteStmt(id){if(!confirm('Delete this statement and all its transactions?'))return;await fetch(`${API}/api/statements/${id}`,{method:'DELETE'});loadAllData();}

async function fetchJSON(u){return(await fetch(u)).json();}
async function fetchJSON_withMethod(m,u,b){return(await fetch(u,{method:m,headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();}
function escHtml(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
function escAttr(s){return(s||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");}