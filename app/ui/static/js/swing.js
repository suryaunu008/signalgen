/**
 * Swing Trading UI Module
 *
 * Handles all UI interactions for swing trading functionality including:
 * - Ticker universe management
 * - Swing screening configuration and execution
 * - Results display and filtering
 */

class SwingTradingUI {
  constructor() {
    this.currentResults = null;
    this.universes = [];
    this.screeningInProgress = false;
    this.activeScreeningController = null;
    this.messageTimer = null;
    this.currentFilter = 'all';
    this.currentPage = 1;
    this.pageSize = 25;
    this.sortKey = 'symbol';
    this.sortDirection = 'asc';
    this.eventsBound = false;
  }

  escapeCsvValue(value) {
    const str = value === null || value === undefined ? '' : String(value);
    if (/[",\n]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  }

  async init() {
    console.log('Initializing Swing Trading UI...');
    this.setupEventListeners();
    await this.loadTickerUniverses();
    await this.loadRules();
  }

  setupEventListeners() {
    if (this.eventsBound) return;
    this.eventsBound = true;

    const screenButton = document.getElementById('run-screening-btn');
    if (screenButton) {
      screenButton.addEventListener('click', () => {
        if (this.screeningInProgress) {
          this.cancelScreening();
          return;
        }
        this.runScreening();
      });
    }

    const createUniverseBtn = document.getElementById('create-universe-btn');
    if (createUniverseBtn) {
      createUniverseBtn.addEventListener('click', () => this.showCreateUniverseForm());
    }

    const saveUniverseBtn = document.getElementById('save-universe-btn');
    if (saveUniverseBtn) {
      saveUniverseBtn.addEventListener('click', () => this.saveUniverse());
    }

    const cancelUniverseBtn = document.getElementById('cancel-universe-btn');
    if (cancelUniverseBtn) {
      cancelUniverseBtn.addEventListener('click', () => this.hideUniverseForm());
    }

    const universeList = document.getElementById('universe-list');
    if (universeList) {
      universeList.addEventListener('click', (event) => {
        const target = event.target.closest('button[data-action]');
        if (!target) return;
        const universeId = parseInt(target.dataset.universeId, 10);
        if (!Number.isInteger(universeId) || universeId <= 0) return;

        if (target.dataset.action === 'edit') {
          this.editUniverse(universeId);
        } else if (target.dataset.action === 'delete') {
          this.deleteUniverse(universeId);
        }
      });
    }

    const resultsContainer = document.getElementById('swing-results-container');
    if (resultsContainer) {
      resultsContainer.addEventListener('click', (event) => {
        const target = event.target.closest('button[data-filter]');
        if (!target) return;
        this.filterResults(target.dataset.filter || 'all');
      });
    }
  }

  async loadRules() {
    try {
      const response = await fetch('/api/rules');
      const rules = await response.json();

      const ruleSelect = document.getElementById('swing-rule-select');
      if (ruleSelect && Array.isArray(rules)) {
        ruleSelect.innerHTML = '<option value="">Select rule...</option>';
        rules.forEach((rule) => {
          const option = document.createElement('option');
          option.value = rule.id;
          option.textContent = `${rule.name}${rule.is_system ? ' (System)' : ''}`;
          ruleSelect.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error loading rules:', error);
      this.showError('Failed to load rules');
    }
  }

  async loadTickerUniverses() {
    try {
      const response = await fetch('/api/swing/universes');
      const data = await response.json();

      this.universes = Array.isArray(data.universes) ? data.universes : [];
      this.displayUniverseSelector(this.universes);
      this.displayUniverseList(this.universes);
    } catch (error) {
      console.error('Error loading ticker universes:', error);
      this.showError('Failed to load ticker universes');
    }
  }

  displayUniverseSelector(universes) {
    const universeSelect = document.getElementById('swing-universe-select');
    if (!universeSelect) return;

    universeSelect.innerHTML = '<option value="">Select ticker universe...</option>';
    universes.forEach((universe) => {
      const option = document.createElement('option');
      option.value = universe.id;
      option.textContent = `${universe.name} (${Array.isArray(universe.tickers) ? universe.tickers.length : 0} tickers)`;
      universeSelect.appendChild(option);
    });
  }

  displayUniverseList(universes) {
    const universeList = document.getElementById('universe-list');
    if (!universeList) return;

    universeList.innerHTML = '';

    if (!universes.length) {
      const empty = document.createElement('p');
      empty.className = 'text-gray-500 text-sm';
      empty.textContent = 'No ticker universes yet';
      universeList.appendChild(empty);
      return;
    }

    const fragment = document.createDocumentFragment();

    universes.forEach((universe) => {
      const tickers = Array.isArray(universe.tickers) ? universe.tickers : [];
      const card = document.createElement('div');
      card.className = 'bg-white border border-gray-200 rounded-lg p-4 mb-3 hover:shadow-md transition-shadow';

      const row = document.createElement('div');
      row.className = 'flex justify-between items-start';

      const left = document.createElement('div');
      left.className = 'flex-1';

      const title = document.createElement('h4');
      title.className = 'font-semibold';
      title.textContent = universe.name || 'Unnamed Universe';

      const desc = document.createElement('p');
      desc.className = 'text-sm text-gray-600';
      desc.textContent = universe.description || 'No description';

      const badgeWrap = document.createElement('div');
      badgeWrap.className = 'mt-2';
      const badge = document.createElement('span');
      badge.className = 'px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs';
      badge.textContent = `${tickers.length} tickers`;
      badgeWrap.appendChild(badge);

      const tickerList = document.createElement('div');
      tickerList.className = 'mt-2 text-sm text-gray-600 max-h-20 overflow-y-auto';
      tickerList.textContent = tickers.length > 0 ? tickers.join(', ') : 'No tickers';

      left.appendChild(title);
      left.appendChild(desc);
      left.appendChild(badgeWrap);
      left.appendChild(tickerList);

      const actions = document.createElement('div');
      actions.className = 'flex gap-2 ml-4';

      const editBtn = document.createElement('button');
      editBtn.className = 'px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600';
      editBtn.dataset.action = 'edit';
      editBtn.dataset.universeId = String(universe.id);
      editBtn.textContent = 'Edit';

      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600 disabled:opacity-60 disabled:cursor-not-allowed';
      deleteBtn.dataset.action = 'delete';
      deleteBtn.dataset.universeId = String(universe.id);
      deleteBtn.textContent = 'Delete';
      if (universe.name === 'Custom') {
        deleteBtn.disabled = true;
      }

      actions.appendChild(editBtn);
      actions.appendChild(deleteBtn);

      row.appendChild(left);
      row.appendChild(actions);
      card.appendChild(row);
      fragment.appendChild(card);
    });

    universeList.appendChild(fragment);
  }

  getSafeLookbackDays() {
    const raw = document.getElementById('swing-lookback')?.value;
    const parsed = parseInt(raw, 10);
    if (!Number.isFinite(parsed)) return 30;
    return Math.min(365, Math.max(1, parsed));
  }

  setScreeningState(inProgress) {
    this.screeningInProgress = inProgress;
    const button = document.getElementById('run-screening-btn');
    if (!button) return;

    if (inProgress) {
      button.classList.remove('bg-green-600', 'hover:bg-green-700');
      button.classList.add('bg-red-600', 'hover:bg-red-700');
      button.innerHTML = '<i class="fas fa-stop mr-2"></i>Cancel Screening';
    } else {
      button.classList.remove('bg-red-600', 'hover:bg-red-700');
      button.classList.add('bg-green-600', 'hover:bg-green-700');
      button.innerHTML = '<i class="fas fa-search mr-2"></i>Run Screening';
    }
  }

  cancelScreening() {
    if (this.activeScreeningController) {
      this.activeScreeningController.abort();
      this.activeScreeningController = null;
    }
  }

  async runScreening() {
    try {
      const ruleId = document.getElementById('swing-rule-select')?.value;
      const universeId = document.getElementById('swing-universe-select')?.value;
      const timeframe = document.getElementById('swing-timeframe')?.value || '1d';
      const lookbackDays = this.getSafeLookbackDays();
      const lookbackInput = document.getElementById('swing-lookback');
      if (lookbackInput) lookbackInput.value = String(lookbackDays);

      if (!ruleId) {
        this.showError('Please select a rule');
        return;
      }
      if (!universeId) {
        this.showError('Please select a ticker universe');
        return;
      }

      this.setScreeningState(true);
      this.showLoading('Running swing screening...');

      this.activeScreeningController = new AbortController();

      const response = await fetch('/api/swing/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: this.activeScreeningController.signal,
        body: JSON.stringify({
          rule_id: parseInt(ruleId, 10),
          ticker_universe_id: parseInt(universeId, 10),
          timeframe,
          lookback_days: lookbackDays
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Screening failed');
      }

      const result = await response.json();
      this.currentResults = result;
      this.displayResults(result);

      const summary = result.summary || {};
      this.showSuccess(`Screening completed. ${summary.signals_found || 0} signals found.`);
    } catch (error) {
      if (error.name === 'AbortError') {
        this.showMessage('Screening cancelled', 'info');
      } else {
        this.showError(`Screening failed: ${error.message}`);
        console.error('Screening error:', error);
      }
    } finally {
      this.hideLoading();
      this.setScreeningState(false);
      this.activeScreeningController = null;
    }
  }

  buildStatCard(label, value, className) {
    const card = document.createElement('div');
    card.className = `rounded-lg p-4 ${className}`;

    const labelEl = document.createElement('div');
    labelEl.className = 'text-sm text-gray-600';
    labelEl.textContent = label;

    const valueEl = document.createElement('div');
    valueEl.className = 'text-2xl font-bold';
    valueEl.textContent = String(value);

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    return card;
  }

  displayResults(result) {
    const resultsContainer = document.getElementById('swing-results-container');
    if (!resultsContainer) return;

    const results = Array.isArray(result.results) ? result.results : [];
    const summary = result.summary || {};
    this.currentFilter = 'all';
    this.currentPage = 1;
    this.sortKey = 'symbol';
    this.sortDirection = 'asc';

    resultsContainer.innerHTML = '';

    const summaryCard = document.createElement('div');
    summaryCard.className = 'bg-white rounded-lg shadow-md p-6 mb-4';

    const summaryTitle = document.createElement('h3');
    summaryTitle.className = 'text-lg font-semibold mb-4';
    summaryTitle.textContent = 'Screening Results';

    const summaryGrid = document.createElement('div');
    summaryGrid.className = 'grid grid-cols-2 md:grid-cols-3 gap-4 mb-6';
    summaryGrid.appendChild(this.buildStatCard('Total Tickers', summary.total_tickers || 0, 'bg-blue-50 text-blue-600'));
    summaryGrid.appendChild(this.buildStatCard('Signals Found', summary.signals_found || 0, 'bg-green-50 text-green-600'));
    summaryGrid.appendChild(this.buildStatCard('Successful', summary.successful || 0, 'bg-indigo-50 text-indigo-600'));
    summaryGrid.appendChild(this.buildStatCard('Errors', summary.errors || 0, 'bg-red-50 text-red-600'));
    summaryGrid.appendChild(this.buildStatCard('No Data', summary.no_data || 0, 'bg-amber-50 text-amber-600'));
    summaryGrid.appendChild(this.buildStatCard('Duration (ms)', summary.duration_ms || 0, 'bg-slate-50 text-slate-600'));

    summaryCard.appendChild(summaryTitle);
    summaryCard.appendChild(summaryGrid);
    if (result.request_id) {
      const requestId = document.createElement('p');
      requestId.className = 'text-xs text-gray-500';
      requestId.textContent = `Request ID: ${result.request_id}`;
      summaryCard.appendChild(requestId);
    }

    const tableCard = document.createElement('div');
    tableCard.className = 'bg-white rounded-lg shadow-md p-6';

    const tableHeader = document.createElement('div');
    tableHeader.className = 'flex justify-between items-center mb-4';

    const tableTitle = document.createElement('h3');
    tableTitle.className = 'text-lg font-semibold';
    tableTitle.textContent = 'Ticker Results';

    const filterBar = document.createElement('div');
    filterBar.className = 'flex gap-2';
    [
      { key: 'all', label: 'All', cls: 'bg-gray-200 hover:bg-gray-300' },
      { key: 'signals', label: 'Signals Only', cls: 'bg-green-500 text-white hover:bg-green-600' },
      { key: 'errors', label: 'Errors Only', cls: 'bg-red-500 text-white hover:bg-red-600' }
    ].forEach((item) => {
      const button = document.createElement('button');
      button.className = `px-3 py-1 rounded text-sm ${item.cls}`;
      button.dataset.filter = item.key;
      button.textContent = item.label;
      filterBar.appendChild(button);
    });

    tableHeader.appendChild(tableTitle);
    tableHeader.appendChild(filterBar);
    tableCard.appendChild(tableHeader);

    const exportWrap = document.createElement('div');
    exportWrap.className = 'mb-4';
    const exportBtn = document.createElement('button');
    exportBtn.className = 'px-3 py-1 bg-sky-600 text-white rounded text-sm hover:bg-sky-700';
    exportBtn.textContent = 'Export CSV';
    exportBtn.addEventListener('click', () => this.exportResultsCsv());
    exportWrap.appendChild(exportBtn);
    tableCard.appendChild(exportWrap);

    const overflow = document.createElement('div');
    overflow.className = 'overflow-x-auto';

    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';
    table.id = 'swing-results-table';

    const thead = document.createElement('thead');
    thead.className = 'bg-gray-50';
    const headerRow = document.createElement('tr');
    const columns = [
      { label: 'Symbol', key: 'symbol' },
      { label: 'Signal', key: 'signal' },
      { label: 'Price', key: 'price' },
      { label: 'Timestamp', key: 'timestamp' },
      { label: 'Status', key: 'status' }
    ];
    columns.forEach(({ label, key }) => {
      const th = document.createElement('th');
      th.className = 'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none';
      th.dataset.sortKey = key;
      th.textContent = label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';

    table.appendChild(thead);
    table.appendChild(tbody);
    overflow.appendChild(table);
    tableCard.appendChild(overflow);

    const paginationBar = document.createElement('div');
    paginationBar.className = 'mt-4 flex items-center justify-between';
    paginationBar.id = 'swing-pagination-bar';
    tableCard.appendChild(paginationBar);

    resultsContainer.appendChild(summaryCard);
    resultsContainer.appendChild(tableCard);
    this.renderResultsTable();
  }

  exportResultsCsv() {
    if (!this.currentResults || !Array.isArray(this.currentResults.results) || this.currentResults.results.length === 0) {
      this.showError('No screening results to export');
      return;
    }

    const rows = this.currentResults.results;
    const headers = ['symbol', 'signal', 'price', 'timestamp', 'status', 'error_message'];
    const lines = [headers.join(',')];

    rows.forEach((row) => {
      const values = headers.map((key) => this.escapeCsvValue(row[key]));
      lines.push(values.join(','));
    });

    const csv = lines.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const now = new Date().toISOString().replace(/[:.]/g, '-');

    link.href = url;
    link.download = `swing-screening-${now}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  filterResults(filter) {
    this.currentFilter = filter;
    this.currentPage = 1;
    this.renderResultsTable();
  }

  toggleSort(sortKey) {
    if (this.sortKey === sortKey) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortKey = sortKey;
      this.sortDirection = 'asc';
    }
    this.currentPage = 1;
    this.renderResultsTable();
  }

  getComparableValue(row, key) {
    if (key === 'price') return Number.isFinite(row.price) ? row.price : Number.NEGATIVE_INFINITY;
    if (key === 'timestamp') return row.timestamp ? new Date(row.timestamp).getTime() : 0;
    if (key === 'signal') return row.signal || '';
    if (key === 'status') return row.status || '';
    return (row[key] || '').toString().toUpperCase();
  }

  getProcessedResults() {
    const base = Array.isArray(this.currentResults?.results) ? [...this.currentResults.results] : [];
    let filtered = base;
    if (this.currentFilter === 'signals') {
      filtered = base.filter((row) => !!row.signal);
    } else if (this.currentFilter === 'errors') {
      filtered = base.filter((row) => row.status === 'error');
    }

    filtered.sort((a, b) => {
      const av = this.getComparableValue(a, this.sortKey);
      const bv = this.getComparableValue(b, this.sortKey);
      if (av < bv) return this.sortDirection === 'asc' ? -1 : 1;
      if (av > bv) return this.sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    return filtered;
  }

  renderResultsTable() {
    const table = document.getElementById('swing-results-table');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const processed = this.getProcessedResults();
    const totalItems = processed.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / this.pageSize));
    if (this.currentPage > totalPages) this.currentPage = totalPages;
    const start = (this.currentPage - 1) * this.pageSize;
    const end = Math.min(start + this.pageSize, totalItems);
    const pageItems = processed.slice(start, end);

    tbody.innerHTML = '';
    pageItems.forEach((r) => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50';
      if (r.status === 'error') tr.classList.add('result-error');
      if (r.signal) tr.classList.add('result-signal');

      const symbol = document.createElement('td');
      symbol.className = 'px-4 py-3 text-sm font-medium';
      symbol.textContent = r.symbol || '-';

      const signalTd = document.createElement('td');
      signalTd.className = 'px-4 py-3 text-sm';
      if (r.signal) {
        const badge = document.createElement('span');
        badge.className = `px-2 py-1 rounded text-white ${r.signal === 'BUY' ? 'bg-green-500' : 'bg-red-500'}`;
        badge.textContent = r.signal;
        signalTd.appendChild(badge);
      } else {
        const dash = document.createElement('span');
        dash.className = 'text-gray-400';
        dash.textContent = '-';
        signalTd.appendChild(dash);
      }

      const price = document.createElement('td');
      price.className = 'px-4 py-3 text-sm';
      price.textContent = Number.isFinite(r.price) ? `$${r.price.toFixed(2)}` : '-';

      const timestamp = document.createElement('td');
      timestamp.className = 'px-4 py-3 text-sm';
      timestamp.textContent = r.timestamp ? new Date(r.timestamp).toLocaleString() : '-';

      const status = document.createElement('td');
      status.className = 'px-4 py-3 text-sm';
      const statusIcon = document.createElement('span');
      if (r.status === 'success') {
        statusIcon.className = 'text-green-600';
        statusIcon.textContent = '✓';
      } else {
        statusIcon.className = 'text-red-600';
        statusIcon.textContent = '✗';
        statusIcon.title = r.error_message || 'Unknown error';
      }
      status.appendChild(statusIcon);

      tr.appendChild(symbol);
      tr.appendChild(signalTd);
      tr.appendChild(price);
      tr.appendChild(timestamp);
      tr.appendChild(status);
      tbody.appendChild(tr);
    });

    this.renderSortHeaderState(table);
    this.renderPagination(totalItems, totalPages, totalItems === 0 ? 0 : start + 1, end);
  }

  renderSortHeaderState(table) {
    const headers = table.querySelectorAll('th[data-sort-key]');
    headers.forEach((th) => {
      const key = th.dataset.sortKey;
      const baseLabel = th.textContent.replace(/\s[↑↓]$/, '');
      th.textContent = baseLabel;
      if (key === this.sortKey) {
        th.textContent = `${baseLabel} ${this.sortDirection === 'asc' ? '↑' : '↓'}`;
      }
      th.onclick = () => this.toggleSort(key);
    });
  }

  renderPagination(totalItems, totalPages, from, to) {
    const bar = document.getElementById('swing-pagination-bar');
    if (!bar) return;
    bar.innerHTML = '';

    const left = document.createElement('div');
    left.className = 'text-sm text-gray-600';
    left.textContent = totalItems === 0 ? 'No rows' : `Showing ${from}-${to} of ${totalItems}`;

    const right = document.createElement('div');
    right.className = 'flex items-center gap-2';
    const sizeWrap = document.createElement('label');
    sizeWrap.className = 'text-sm text-gray-600 flex items-center gap-1';
    sizeWrap.textContent = 'Rows';

    const sizeSelect = document.createElement('select');
    sizeSelect.className = 'px-2 py-1 rounded border border-gray-300 text-sm';
    [10, 25, 50, 100].forEach((size) => {
      const opt = document.createElement('option');
      opt.value = String(size);
      opt.textContent = String(size);
      if (this.pageSize === size) opt.selected = true;
      sizeSelect.appendChild(opt);
    });
    sizeSelect.addEventListener('change', (event) => {
      const next = parseInt(event.target.value, 10);
      if (!Number.isNaN(next) && next > 0) {
        this.pageSize = next;
        this.currentPage = 1;
        this.renderResultsTable();
      }
    });
    sizeWrap.appendChild(sizeSelect);

    const prev = document.createElement('button');
    prev.className = 'px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50';
    prev.textContent = 'Prev';
    prev.disabled = this.currentPage <= 1;
    prev.addEventListener('click', () => {
      if (this.currentPage > 1) {
        this.currentPage -= 1;
        this.renderResultsTable();
      }
    });

    const page = document.createElement('span');
    page.className = 'text-sm text-gray-700';
    page.textContent = `Page ${this.currentPage}/${totalPages}`;

    const next = document.createElement('button');
    next.className = 'px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50';
    next.textContent = 'Next';
    next.disabled = this.currentPage >= totalPages;
    next.addEventListener('click', () => {
      if (this.currentPage < totalPages) {
        this.currentPage += 1;
        this.renderResultsTable();
      }
    });

    right.appendChild(sizeWrap);
    right.appendChild(prev);
    right.appendChild(page);
    right.appendChild(next);
    bar.appendChild(left);
    bar.appendChild(right);
  }

  showCreateUniverseForm() {
    const formContainer = document.getElementById('universe-form-container');
    if (formContainer) {
      document.getElementById('universe-form-title').textContent = 'Create Ticker Universe';
      document.getElementById('universe-id').value = '';
      document.getElementById('universe-name').value = '';
      document.getElementById('universe-tickers').value = '';
      document.getElementById('universe-description').value = '';
      formContainer.classList.remove('hidden');
    }
  }

  async editUniverse(universeId) {
    const universe = this.universes.find((u) => u.id === universeId);
    if (!universe) return;

    const formContainer = document.getElementById('universe-form-container');
    if (formContainer) {
      document.getElementById('universe-form-title').textContent = 'Edit Ticker Universe';
      document.getElementById('universe-id').value = universe.id;
      document.getElementById('universe-name').value = universe.name;
      document.getElementById('universe-tickers').value = (universe.tickers || []).join(', ');
      document.getElementById('universe-description').value = universe.description || '';
      formContainer.classList.remove('hidden');
    }
  }

  async saveUniverse() {
    try {
      const id = document.getElementById('universe-id')?.value;
      const name = document.getElementById('universe-name')?.value?.trim();
      const tickersStr = document.getElementById('universe-tickers')?.value?.trim();
      const description = document.getElementById('universe-description')?.value?.trim();

      if (!name) {
        this.showError('Please enter a universe name');
        return;
      }

      const tickers = tickersStr
        ? tickersStr.split(',').map((ticker) => ticker.trim().toUpperCase()).filter((ticker) => ticker)
        : [];

      const payload = { name, tickers, description };

      let response;
      if (id) {
        response = await fetch(`/api/swing/universes/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        response = await fetch('/api/swing/universes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to save universe');
      }

      this.showSuccess(`Universe ${id ? 'updated' : 'created'} successfully`);
      this.hideUniverseForm();
      await this.loadTickerUniverses();
    } catch (error) {
      this.showError(`Failed to save universe: ${error.message}`);
      console.error('Save universe error:', error);
    }
  }

  async deleteUniverse(universeId) {
    if (!confirm('Are you sure you want to delete this ticker universe?')) {
      return;
    }

    try {
      const response = await fetch(`/api/swing/universes/${universeId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete universe');
      }

      this.showSuccess('Universe deleted successfully');
      await this.loadTickerUniverses();
    } catch (error) {
      this.showError(`Failed to delete universe: ${error.message}`);
      console.error('Delete universe error:', error);
    }
  }

  hideUniverseForm() {
    const formContainer = document.getElementById('universe-form-container');
    if (formContainer) {
      formContainer.classList.add('hidden');
    }
  }

  showLoading(message) {
    const loadingDiv = document.getElementById('swing-loading');
    if (loadingDiv) {
      loadingDiv.innerHTML = '';
      const wrapper = document.createElement('div');
      wrapper.className = 'flex items-center justify-center p-4 bg-blue-50 rounded-lg';

      const icon = document.createElement('i');
      icon.className = 'fas fa-spinner fa-spin mr-2';

      const text = document.createElement('span');
      text.textContent = message;

      wrapper.appendChild(icon);
      wrapper.appendChild(text);
      loadingDiv.appendChild(wrapper);
      loadingDiv.classList.remove('hidden');
    }
  }

  hideLoading() {
    const loadingDiv = document.getElementById('swing-loading');
    if (loadingDiv) {
      loadingDiv.classList.add('hidden');
    }
  }

  showSuccess(message) {
    this.showMessage(message, 'success');
  }

  showError(message) {
    this.showMessage(message, 'error');
  }

  showMessage(message, type = 'info') {
    const messageDiv = document.getElementById('swing-message');
    if (!messageDiv) return;

    if (this.messageTimer) {
      clearTimeout(this.messageTimer);
      this.messageTimer = null;
    }

    const bgColor = type === 'success'
      ? 'bg-green-50 text-green-800'
      : type === 'error'
        ? 'bg-red-50 text-red-800'
        : 'bg-blue-50 text-blue-800';

    messageDiv.innerHTML = '';

    const card = document.createElement('div');
    card.className = `${bgColor} p-4 rounded-lg mb-4`;
    card.textContent = message;

    messageDiv.appendChild(card);

    this.messageTimer = setTimeout(() => {
      messageDiv.innerHTML = '';
      this.messageTimer = null;
    }, 5000);
  }
}

const swingTradingUI = new SwingTradingUI();
