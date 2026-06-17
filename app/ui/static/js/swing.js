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
    this.currentFilter = 'signals';
    this.currentPage = 1;
    this.pageSize = 25;
    this.sortKey = 'symbol';
    this.sortDirection = 'asc';
    this.eventsBound = false;
    this.cacheBackfillInProgress = false;
    this.chartState = null;
    this.chart = null;
    this.chartSeries = [];
    this.panelCharts = [];
    this.chartRulerClickHandler = null;
    this.chartRulerMoveHandler = null;
    this.chartRulerRangeHandler = null;
    this.syncingChartRange = false;
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

    const fillYahooCacheButton = document.getElementById('fill-yahoo-cache-btn');
    if (fillYahooCacheButton) {
      fillYahooCacheButton.addEventListener('click', () => this.fillYahooCache());
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
        const chartButton = event.target.closest('button[data-chart-index]');
        if (chartButton) {
          const index = parseInt(chartButton.dataset.chartIndex, 10);
          const row = this.currentResults?.results?.[index];
          if (row) this.openChart(row);
          return;
        }

        const target = event.target.closest('button[data-filter]');
        if (!target) return;
        this.filterResults(target.dataset.filter || 'all');
      });
    }

    const closeChartButton = document.getElementById('close-swing-chart-modal');
    if (closeChartButton) closeChartButton.addEventListener('click', () => this.closeChartModal());

    const chartModal = document.getElementById('swing-chart-modal');
    if (chartModal) {
      chartModal.addEventListener('click', (event) => {
        if (event.target.id === 'swing-chart-modal') this.closeChartModal();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (!this.chartState || !['Delete', 'Backspace', 'Escape'].includes(event.key)) return;
      const target = event.target;
      if (target?.matches?.('input, textarea, select, [contenteditable="true"]')) return;
      if (event.key === 'Escape' && this.chartState.rulerStart) {
        this.chartState.rulerStart = null;
        this.chartState.rulerPreview = null;
        this.renderChartRulers();
        return;
      }
      if (!['Delete', 'Backspace'].includes(event.key) || !this.chartState.rulerSelectedId) return;
      this.deleteChartRuler(this.chartState.rulerSelectedId);
    });

    const rangeMinus = document.getElementById('swing-chart-range-minus');
    if (rangeMinus) rangeMinus.addEventListener('click', () => this.adjustChartRange(-20));

    const rangePlus = document.getElementById('swing-chart-range-plus');
    if (rangePlus) rangePlus.addEventListener('click', () => this.adjustChartRange(20));

    const ruleToggle = document.getElementById('swing-chart-rule-toggle');
    if (ruleToggle) ruleToggle.addEventListener('click', () => this.toggleChartRulePanel());

    const rulerToggle = document.getElementById('swing-chart-ruler-toggle');
    if (rulerToggle) rulerToggle.addEventListener('click', () => this.toggleChartRuler());
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

  getHistoricalDateRange() {
    const startValue = document.getElementById('swing-start-date')?.value || '';
    const endValue = document.getElementById('swing-end-date')?.value || '';

    if (!startValue && !endValue) {
      return null;
    }

    if (!startValue || !endValue) {
      throw new Error('Please fill both screening start and end dates, or leave both empty');
    }

    const start = new Date(`${startValue}T00:00:00`);
    const endInclusive = new Date(`${endValue}T00:00:00`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(endInclusive.getTime())) {
      throw new Error('Invalid screening date');
    }
    if (endInclusive < start) {
      throw new Error('Screening end date must be the same as or later than start date');
    }

    const endExclusive = new Date(endInclusive);
    endExclusive.setDate(endExclusive.getDate() + 1);

    return {
      start_date: this.toLocalIsoDateTime(start),
      end_date: this.toLocalIsoDateTime(endExclusive),
      display_start: startValue,
      display_end: endValue
    };
  }

  toLocalIsoDateTime(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    const ss = String(date.getSeconds()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}T${hh}:${min}:${ss}`;
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

  getSelectedCacheTimeframes() {
    return Array.from(document.querySelectorAll('.yahoo-cache-timeframe:checked'))
      .map((input) => input.value)
      .filter(Boolean);
  }

  setCacheBackfillState(inProgress) {
    this.cacheBackfillInProgress = inProgress;
    const button = document.getElementById('fill-yahoo-cache-btn');
    const inputs = document.querySelectorAll('.yahoo-cache-timeframe');
    inputs.forEach((input) => {
      input.disabled = inProgress;
    });

    if (!button) return;
    button.disabled = inProgress;
    button.innerHTML = inProgress
      ? '<i class="fas fa-spinner fa-spin mr-2"></i>Filling...'
      : '<i class="fas fa-download mr-2"></i>Fill Data';
  }

  showCacheStatus(message, type = 'info') {
    const statusEl = document.getElementById('yahoo-cache-status');
    if (!statusEl) return;

    statusEl.className = 'min-h-[42px] rounded-md border px-3 py-2 text-sm';
    if (type === 'success') {
      statusEl.classList.add('border-green-200', 'bg-green-50', 'text-green-800');
    } else if (type === 'error') {
      statusEl.classList.add('border-red-200', 'bg-red-50', 'text-red-800');
    } else {
      statusEl.classList.add('border-blue-200', 'bg-blue-50', 'text-blue-800');
    }
    statusEl.textContent = message;
  }

  async fillYahooCache() {
    if (this.cacheBackfillInProgress) return;

    const universeId = document.getElementById('swing-universe-select')?.value;
    const timeframes = this.getSelectedCacheTimeframes();
    if (!universeId) {
      this.showError('Please select a ticker universe');
      this.showCacheStatus('Select a ticker universe before filling Yahoo cache.', 'error');
      return;
    }
    if (timeframes.length === 0) {
      this.showError('Please select at least one timeframe');
      this.showCacheStatus('Select at least one timeframe before filling Yahoo cache.', 'error');
      return;
    }

    const universe = this.universes.find((item) => String(item.id) === String(universeId));
    const tickerCount = Array.isArray(universe?.tickers) ? universe.tickers.length : 0;
    const universeName = universe?.name || 'selected universe';

    try {
      this.setCacheBackfillState(true);
      this.showCacheStatus(`Filling Yahoo cache for ${universeName}: ${tickerCount} tickers, ${timeframes.join(', ')}.`, 'info');
      this.showLoading('Filling Yahoo cache...');

      const response = await fetch('/api/swing/backfill-yahoo-cache', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker_universe_id: parseInt(universeId, 10),
          timeframes
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Yahoo cache fill failed');
      }

      const result = await response.json();
      const errors = Array.isArray(result.errors) ? result.errors.length : 0;
      const items = Array.isArray(result.items) ? result.items.length : 0;
      const message = `Yahoo cache filled: ${result.total_candles || 0} candles across ${items} symbol/timeframe jobs${errors ? `, ${errors} errors` : ''}.`;
      this.showCacheStatus(message, errors ? 'error' : 'success');
      this.showMessage(message, errors ? 'error' : 'success');
    } catch (error) {
      const message = `Yahoo cache fill failed: ${error.message}`;
      this.showCacheStatus(message, 'error');
      this.showError(message);
      console.error('Yahoo cache fill error:', error);
    } finally {
      this.hideLoading();
      this.setCacheBackfillState(false);
    }
  }

  formatDate(value) {
    const date = this.parseLocalDate(value);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleDateString(undefined, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  }

  formatDateTime(value) {
    const date = this.parseLocalDate(value);
    if (Number.isNaN(date.getTime())) return '-';
    return `${this.formatDate(date)} ${date.toLocaleTimeString()}`;
  }

  parseLocalDate(value) {
    if (!value) return new Date(NaN);
    if (value instanceof Date) return value;
    if (typeof value === 'number') return new Date(value > 1e12 ? value : value * 1000);
    if (typeof value === 'string') {
      if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        return new Date(`${value}T00:00:00`);
      }
      const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
      return new Date(hasTimezone ? value : value.replace(' ', 'T'));
    }
    return new Date(NaN);
  }

  formatPrice(value, decimals = 2) {
    const price = Number(value);
    if (!Number.isFinite(price)) return '-';
    return price.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
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
      const historicalRange = this.getHistoricalDateRange();
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

      const payload = {
        rule_id: parseInt(ruleId, 10),
        ticker_universe_id: parseInt(universeId, 10),
        timeframe,
        lookback_days: lookbackDays
      };
      if (historicalRange) {
        payload.start_date = historicalRange.start_date;
        payload.end_date = historicalRange.end_date;
        payload.display_start = historicalRange.display_start;
        payload.display_end = historicalRange.display_end;
      }

      const response = await fetch('/api/swing/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: this.activeScreeningController.signal,
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Screening failed');
      }

      const result = await response.json();
      result.request_payload = payload;
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
    results.forEach((row, index) => {
      row._screenIndex = index;
    });
    const summary = result.summary || {};
    this.currentFilter = 'signals';
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
    const period = document.createElement('p');
    period.className = 'text-sm text-gray-600 mb-2';
    if (summary.screening_start && summary.screening_end) {
      const endDate = new Date(summary.screening_end);
      endDate.setDate(endDate.getDate() - 1);
      period.textContent = `Historical period: ${this.formatDate(summary.screening_start)} - ${this.formatDate(endDate)}`;
    } else {
      period.textContent = `Lookback period: ${summary.lookback_days || '-'} days`;
    }
    summaryCard.appendChild(period);
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
      { label: 'Status', key: 'status' },
      { label: 'Chart', key: null }
    ];
    columns.forEach(({ label, key }) => {
      const th = document.createElement('th');
      th.className = `px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase select-none ${key ? 'cursor-pointer' : ''}`;
      if (key) th.dataset.sortKey = key;
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
      price.textContent = Number.isFinite(r.price) ? this.formatPrice(r.price) : '-';

      const timestamp = document.createElement('td');
      timestamp.className = 'px-4 py-3 text-sm';
      timestamp.textContent = r.timestamp ? this.formatDateTime(r.timestamp) : '-';

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

      const chart = document.createElement('td');
      chart.className = 'px-4 py-3 text-sm';
      const chartBtn = document.createElement('button');
      chartBtn.className = 'w-9 h-9 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed';
      chartBtn.title = r.signal ? 'Open chart' : 'Chart is available for signal rows';
      chartBtn.dataset.chartIndex = String(r._screenIndex ?? 0);
      chartBtn.disabled = !r.signal || !r.timestamp;
      chartBtn.innerHTML = '<i class="fas fa-chart-line"></i>';
      chart.appendChild(chartBtn);

      tr.appendChild(symbol);
      tr.appendChild(signalTd);
      tr.appendChild(price);
      tr.appendChild(timestamp);
      tr.appendChild(status);
      tr.appendChild(chart);
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

  async openChart(row) {
    const requestPayload = this.currentResults?.request_payload || {};
    const ruleId = requestPayload.rule_id || parseInt(document.getElementById('swing-rule-select')?.value, 10);
    const timeframe = requestPayload.timeframe || document.getElementById('swing-timeframe')?.value || '1d';
    if (!ruleId || !row?.symbol || !row?.timestamp) {
      this.showError('Chart requires symbol, timestamp, and rule');
      return;
    }

    this.chartState = {
      row,
      ruleId,
      timeframe,
      before: 80,
      after: 40,
      enabled: new Set(),
      showRule: false,
      showRuler: false,
      rulerStart: null,
      rulerPreview: null,
      rulerSelectedId: null,
      rulerNextId: 1,
      rulers: []
    };

    const modal = document.getElementById('swing-chart-modal');
    if (modal) modal.classList.remove('hidden');
    await this.loadChartData();
  }

  closeChartModal() {
    const modal = document.getElementById('swing-chart-modal');
    if (modal) modal.classList.add('hidden');
    this.clearCharts();
    this.chartState = null;
  }

  async adjustChartRange(delta) {
    if (!this.chartState) return;
    this.chartState.before = Math.min(250, Math.max(10, this.chartState.before + delta));
    this.chartState.after = Math.min(120, Math.max(0, this.chartState.after + Math.round(delta / 2)));
    await this.loadChartData();
  }

  async loadChartData() {
    if (!this.chartState) return;
    const { row, ruleId, timeframe, before, after } = this.chartState;
    const errorEl = document.getElementById('swing-chart-error');
    if (errorEl) errorEl.classList.add('hidden');

    try {
      const params = new URLSearchParams({
        symbol: row.symbol,
        timeframe,
        timestamp: row.timestamp,
        rule_id: String(ruleId),
        before: String(before),
        after: String(after)
      });
      const response = await fetch(`/api/swing/chart?${params.toString()}`);
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to load chart');
      }
      const data = await response.json();
      this.chartState.data = data;
      if (this.chartState.enabled.size === 0) {
        (data.indicators || []).forEach((item) => this.chartState.enabled.add(item.id));
      }
      this.renderChartModal(data);
    } catch (error) {
      if (errorEl) {
        errorEl.textContent = error.message;
        errorEl.classList.remove('hidden');
      }
      console.error('Chart error:', error);
    }
  }

  renderChartModal(data) {
    const title = document.getElementById('swing-chart-title');
    const subtitle = document.getElementById('swing-chart-subtitle');
    const rangeLabel = document.getElementById('swing-chart-range-label');
    if (title) title.textContent = `${data.symbol} ${data.signal ? data.signal : ''}`.trim();
    if (subtitle) {
      subtitle.textContent = `${data.timeframe} • ${data.rule_name || 'Rule'} • ${this.formatDateTime(data.signal_timestamp)}`;
    }
    if (rangeLabel) rangeLabel.textContent = `${data.before} / ${data.after} candles`;

    this.assignIndicatorColors(data.indicators || []);
    this.renderIndicatorToggles(data.indicators || []);
    this.renderChartRulePanel(data.rule || null);
    this.renderChartRulerToggle();
    this.renderCharts(data);
  }

  toggleChartRulePanel() {
    if (!this.chartState) return;
    this.chartState.showRule = !this.chartState.showRule;
    this.renderChartRulePanel(this.chartState.data?.rule || null);
  }

  renderChartRulePanel(rule) {
    const panel = document.getElementById('swing-chart-rule-panel');
    const toggle = document.getElementById('swing-chart-rule-toggle');
    if (!panel) return;

    const visible = !!this.chartState?.showRule;
    panel.classList.toggle('hidden', !visible);
    if (toggle) {
      toggle.classList.toggle('bg-blue-50', visible);
      toggle.classList.toggle('border-blue-300', visible);
      toggle.classList.toggle('text-blue-700', visible);
    }
    if (!visible) return;

    panel.innerHTML = '';
    if (!rule) {
      const empty = document.createElement('p');
      empty.className = 'text-sm text-gray-500';
      empty.textContent = 'Rule details are not available for this chart.';
      panel.appendChild(empty);
      return;
    }

    const header = document.createElement('div');
    header.className = 'flex flex-wrap items-center justify-between gap-2 mb-3';

    const titleWrap = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'font-semibold text-gray-900';
    title.textContent = rule.name || 'Rule';
    const meta = document.createElement('div');
    meta.className = 'text-xs text-gray-500';
    const bits = [
      rule.signal_type ? `Signal: ${rule.signal_type}` : null,
      rule.logic ? `Logic: ${rule.logic}` : null,
      Number.isFinite(Number(rule.cooldown_sec)) ? `Cooldown: ${rule.cooldown_sec}s` : null,
      rule.is_system ? 'System' : 'Custom',
    ].filter(Boolean);
    meta.textContent = bits.join(' • ');
    titleWrap.appendChild(title);
    titleWrap.appendChild(meta);

    header.appendChild(titleWrap);
    panel.appendChild(header);

    const conditions = Array.isArray(rule.conditions) ? rule.conditions : [];
    if (!conditions.length) {
      const empty = document.createElement('p');
      empty.className = 'text-sm text-gray-500';
      empty.textContent = 'No conditions.';
      panel.appendChild(empty);
      return;
    }

    const list = document.createElement('div');
    list.className = 'space-y-2';
    conditions.forEach((condition, index) => {
      const item = document.createElement('div');
      item.className = 'rounded-md border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-gray-800';
      const prefix = index === 0 ? 'WHEN' : (rule.logic || 'AND');
      item.textContent = `${prefix} ${this.formatCondition(condition)}`;
      list.appendChild(item);
    });
    panel.appendChild(list);
  }

  formatConditionOperand(operand, multiplier = 1) {
    const text = this.formatOperand(operand);
    const numericMultiplier = Number(multiplier ?? 1);
    if (!Number.isFinite(numericMultiplier) || numericMultiplier <= 0 || numericMultiplier === 1) {
      return text;
    }
    return `${numericMultiplier} * ${text}`;
  }

  formatCondition(condition) {
    return `${this.formatConditionOperand(condition.left, condition.left_multiplier)} ${condition.op || '?'} ${this.formatConditionOperand(condition.right, condition.right_multiplier)}`;
  }

  toggleChartRuler() {
    if (!this.chartState) return;
    this.chartState.showRuler = !this.chartState.showRuler;
    if (!this.chartState.showRuler) {
      this.chartState.rulerStart = null;
      this.chartState.rulerPreview = null;
    }
    this.renderChartRulerToggle();
    if (!this.chartState.data) return;
    this.renderChartRulers();
  }

  renderChartRulerToggle() {
    const toggle = document.getElementById('swing-chart-ruler-toggle');
    if (!toggle) return;

    const visible = !!this.chartState?.showRuler;
    toggle.classList.toggle('bg-blue-50', visible);
    toggle.classList.toggle('border-blue-300', visible);
    toggle.classList.toggle('text-blue-700', visible);
    toggle.classList.toggle('hover:bg-blue-100', visible);
    toggle.classList.toggle('bg-white', !visible);
    toggle.classList.toggle('border-gray-300', !visible);
    toggle.classList.toggle('text-gray-700', !visible);
    toggle.classList.toggle('hover:bg-gray-50', !visible);
  }

  formatOperand(value) {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(6)));
    return String(value);
  }

  assignIndicatorColors(indicators) {
    if (!this.chartState) return;
    if (!this.chartState.indicatorColors) this.chartState.indicatorColors = new Map();
    indicators.forEach((indicator, index) => {
      if (!this.chartState.indicatorColors.has(indicator.id)) {
        this.chartState.indicatorColors.set(indicator.id, this.seriesColor(index));
      }
    });
  }

  getIndicatorColor(indicator) {
    return this.chartState?.indicatorColors?.get(indicator.id) || this.seriesColor(0);
  }

  getIndicatorSwatchStyle(indicator) {
    if (indicator.type === 'marker') {
      if (indicator.direction === 'bearish') return 'background: #dc2626;';
      if (indicator.direction === 'bullish') return 'background: #16a34a;';
      return 'background: #7c3aed;';
    }
    if (indicator.type === 'histogram') {
      return 'background: linear-gradient(90deg, #16a34a 0 50%, #dc2626 50% 100%);';
    }
    return `background: ${this.getIndicatorColor(indicator)};`;
  }

  renderIndicatorToggles(indicators) {
    const container = document.getElementById('swing-chart-toggles');
    if (!container) return;
    container.innerHTML = '';

    if (indicators.length === 0) {
      const empty = document.createElement('span');
      empty.className = 'text-sm text-gray-500';
      empty.textContent = 'No rule indicators to plot';
      container.appendChild(empty);
      return;
    }

    indicators.forEach((indicator) => {
      const label = document.createElement('label');
      label.className = 'inline-flex items-center gap-2 px-2.5 py-1 rounded-md border border-gray-300 text-sm bg-white';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = this.chartState.enabled.has(indicator.id);
      input.addEventListener('change', () => {
        if (input.checked) {
          this.chartState.enabled.add(indicator.id);
        } else {
          this.chartState.enabled.delete(indicator.id);
        }
        this.renderCharts(this.chartState.data);
      });
      const swatch = document.createElement('span');
      swatch.className = 'inline-block w-3 h-3 rounded-sm border border-gray-300';
      swatch.style.cssText = this.getIndicatorSwatchStyle(indicator);
      const text = document.createElement('span');
      text.textContent = indicator.label;
      label.appendChild(input);
      label.appendChild(swatch);
      label.appendChild(text);
      container.appendChild(label);
    });
  }

  renderCharts(data) {
    this.clearCharts();
    const LW = window.LightweightCharts;
    const mainEl = document.getElementById('swing-chart-main');
    const panelsEl = document.getElementById('swing-chart-panels');
    if (!mainEl || !panelsEl) return;
    panelsEl.innerHTML = '';

    if (!LW || typeof LW.createChart !== 'function') {
      mainEl.innerHTML = '<div class="p-4 text-sm text-red-700">Chart library failed to load.</div>';
      return;
    }

    const candles = (data.candles || []).map((candle) => ({
      time: candle.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close
    }));

    this.chart = LW.createChart(mainEl, this.getChartOptions(mainEl, 430));
    const candleSeries = this.addChartSeries(this.chart, 'candlestick', {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderVisible: false,
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626'
    });
    candleSeries.setData(candles);
    this.addChartMarkers(candleSeries, data);
    this.chartSeries.push(candleSeries);
    this.attachChartRulerTool(this.chart, mainEl, candleSeries);

    const overlay = (data.indicators || []).filter((item) => item.type !== 'marker' && item.panel === 'overlay' && this.chartState.enabled.has(item.id));
    overlay.forEach((item) => {
      const series = this.addChartSeries(this.chart, item.type || 'line', {
        color: this.getIndicatorColor(item),
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false
      });
      series.setData(item.points || []);
      this.chartSeries.push(series);
    });
    this.chart.timeScale().fitContent();

    const grouped = {};
    (data.indicators || [])
      .filter((item) => item.type !== 'marker' && item.panel !== 'overlay' && this.chartState.enabled.has(item.id))
      .forEach((item) => {
        if (!grouped[item.panel]) grouped[item.panel] = [];
        grouped[item.panel].push(item);
      });

    Object.entries(grouped).forEach(([panelName, items]) => {
      const panelWrap = document.createElement('div');
      panelWrap.className = 'border border-gray-200 rounded-md overflow-hidden';
      const panelTitle = document.createElement('div');
      panelTitle.className = 'px-3 py-2 text-xs font-semibold uppercase text-gray-500 bg-gray-50 border-b border-gray-200';
      panelTitle.textContent = panelName;
      const panelEl = document.createElement('div');
      panelEl.className = 'h-[180px]';
      panelWrap.appendChild(panelTitle);
      panelWrap.appendChild(panelEl);
      panelsEl.appendChild(panelWrap);

      const panelChart = LW.createChart(panelEl, this.getChartOptions(panelEl, 180));
      this.panelCharts.push(panelChart);
      items.forEach((item) => {
        const series = this.addChartSeries(panelChart, item.type || 'line', {
          color: this.getIndicatorColor(item),
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false
        });
        const points = (item.points || []).map((point) => (
          item.type === 'histogram'
            ? { ...point, color: point.value >= 0 ? '#16a34a' : '#dc2626' }
            : point
        ));
        series.setData(points);
        this.chartSeries.push(series);
      });
      panelChart.timeScale().fitContent();
    });

    this.syncChartTimeScales();
  }

  attachChartRulerTool(chart, container, series) {
    if (!chart || !container || !series) return;

    container.classList.add('relative', 'overflow-hidden');

    const overlay = document.createElement('div');
    overlay.id = 'swing-chart-ruler-overlay';
    overlay.className = 'pointer-events-none absolute inset-0 z-20';
    container.appendChild(overlay);

    if (typeof chart.subscribeClick === 'function') {
      this.chartRulerClickHandler = (param) => {
        if (!this.chartState?.showRuler) return;
        const point = this.getRulerPoint(param, container, series);
        if (!point) return;

        if (!this.chartState.rulerStart) {
          this.chartState.rulerStart = point;
          this.chartState.rulerPreview = null;
          this.renderChartRulers();
          return;
        }

        this.chartState.rulers.push({
          id: this.chartState.rulerNextId++,
          start: this.chartState.rulerStart,
          end: point
        });
        this.chartState.rulerStart = null;
        this.chartState.rulerPreview = null;
        this.renderChartRulers();
      };
      chart.subscribeClick(this.chartRulerClickHandler);
    }

    if (typeof chart.subscribeCrosshairMove === 'function') {
      this.chartRulerMoveHandler = (param) => {
        if (!this.chartState?.showRuler || !this.chartState.rulerStart) return;
        this.chartState.rulerPreview = this.getRulerPoint(param, container, series);
        this.renderChartRulers();
      };
      chart.subscribeCrosshairMove(this.chartRulerMoveHandler);
    }

    const timeScale = chart.timeScale();
    if (timeScale && typeof timeScale.subscribeVisibleLogicalRangeChange === 'function') {
      this.chartRulerRangeHandler = () => this.renderChartRulers();
      timeScale.subscribeVisibleLogicalRangeChange(this.chartRulerRangeHandler);
    }

    this.renderChartRulers();
  }

  getRulerPoint(param, container, series) {
    const point = param?.point;
    if (!point || !param.time || typeof series.coordinateToPrice !== 'function') return null;

    const bounds = container.getBoundingClientRect();
    if (point.x < 0 || point.y < 0 || point.x > bounds.width || point.y > bounds.height) return null;

    const price = Number(series.coordinateToPrice(point.y));
    if (!Number.isFinite(price)) return null;

    return {
      time: param.time,
      price
    };
  }

  renderChartRulers() {
    const overlay = document.getElementById('swing-chart-ruler-overlay');
    if (!overlay || !this.chart || !this.chartSeries.length) return;

    overlay.innerHTML = '';
    const width = overlay.clientWidth || overlay.parentElement?.clientWidth || 0;
    const height = overlay.clientHeight || overlay.parentElement?.clientHeight || 0;
    if (width <= 0 || height <= 0) return;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'absolute inset-0 h-full w-full overflow-visible');
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.style.pointerEvents = 'none';
    overlay.appendChild(svg);

    const rulers = this.chartState?.rulers || [];
    rulers.forEach((ruler) => this.drawChartRuler(svg, overlay, ruler, false));

    if (this.chartState?.rulerStart && this.chartState?.rulerPreview) {
      this.drawChartRuler(svg, overlay, {
        id: 'preview',
        start: this.chartState.rulerStart,
        end: this.chartState.rulerPreview
      }, true);
    }
  }

  drawChartRuler(svg, overlay, ruler, isPreview) {
    const start = this.resolveRulerPoint(ruler.start);
    const end = this.resolveRulerPoint(ruler.end);
    if (!start || !end) return;

    const isUp = end.price >= start.price;
    const color = isPreview ? '#64748b' : (isUp ? '#2563eb' : '#f43f5e');
    const fill = isPreview ? 'rgba(100, 116, 139, 0.18)' : (isUp ? 'rgba(37, 99, 235, 0.22)' : 'rgba(244, 63, 94, 0.22)');
    const selected = this.chartState?.rulerSelectedId === ruler.id;
    const strokeWidth = selected ? '3' : '2';
    const left = Math.min(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const rectWidth = Math.abs(end.x - start.x);
    const rectHeight = Math.abs(end.y - start.y);

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', String(left));
    rect.setAttribute('y', String(top));
    rect.setAttribute('width', String(Math.max(1, rectWidth)));
    rect.setAttribute('height', String(Math.max(1, rectHeight)));
    rect.setAttribute('fill', fill);
    rect.setAttribute('stroke', color);
    rect.setAttribute('stroke-width', selected ? '1.5' : '1');
    rect.setAttribute('pointer-events', 'none');
    svg.appendChild(rect);

    const baseLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    baseLine.setAttribute('x1', String(left));
    baseLine.setAttribute('y1', String(start.y));
    baseLine.setAttribute('x2', String(Math.max(start.x, end.x)));
    baseLine.setAttribute('y2', String(start.y));
    baseLine.setAttribute('stroke', color);
    baseLine.setAttribute('stroke-width', '1');
    baseLine.setAttribute('stroke-dasharray', '4 3');
    baseLine.setAttribute('pointer-events', 'none');
    svg.appendChild(baseLine);

    const arrowLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    arrowLine.setAttribute('x1', String(end.x));
    arrowLine.setAttribute('y1', String(start.y));
    arrowLine.setAttribute('x2', String(end.x));
    arrowLine.setAttribute('y2', String(end.y));
    arrowLine.setAttribute('stroke', color);
    arrowLine.setAttribute('stroke-width', strokeWidth);
    arrowLine.setAttribute('stroke-dasharray', isPreview ? '6 4' : '0');
    arrowLine.setAttribute('pointer-events', 'none');
    svg.appendChild(arrowLine);

    [
      { y: start.y, direction: start.y <= end.y ? -1 : 1 },
      { y: end.y, direction: end.y >= start.y ? 1 : -1 }
    ].forEach((arrow) => {
      const arrowHead = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      arrowHead.setAttribute('d', `M ${end.x - 5} ${arrow.y - (arrow.direction * 6)} L ${end.x} ${arrow.y} L ${end.x + 5} ${arrow.y - (arrow.direction * 6)}`);
      arrowHead.setAttribute('fill', 'none');
      arrowHead.setAttribute('stroke', color);
      arrowHead.setAttribute('stroke-width', strokeWidth);
      arrowHead.setAttribute('stroke-linecap', 'round');
      arrowHead.setAttribute('stroke-linejoin', 'round');
      arrowHead.setAttribute('pointer-events', 'none');
      svg.appendChild(arrowHead);
    });

    [start, end].forEach((point) => {
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', String(point.x));
      dot.setAttribute('cy', String(point.y));
      dot.setAttribute('r', selected ? '5' : '4');
      dot.setAttribute('fill', '#ffffff');
      dot.setAttribute('stroke', color);
      dot.setAttribute('stroke-width', '2');
      svg.appendChild(dot);
    });

    const label = document.createElement('div');
    label.className = [
      'pointer-events-auto absolute -translate-x-1/2 rounded px-2.5 py-1.5 text-xs font-semibold leading-5 text-white shadow-lg text-center min-w-[104px]',
      isPreview ? 'bg-slate-600' : (isUp ? 'bg-blue-600' : 'bg-rose-500')
    ].join(' ');
    label.style.left = `${Math.min(Math.max(end.x, 58), Math.max(58, overlay.clientWidth - 58))}px`;
    const labelTop = isUp ? top - 80 : top + rectHeight + 10;
    label.style.top = `${Math.min(Math.max(labelTop, 6), Math.max(6, overlay.clientHeight - 78))}px`;
    label.title = isPreview ? 'Ruler preview' : 'Click to select. Use x or Delete to remove.';

    const summary = this.getRulerSummary(ruler);
    const lines = [summary.price, summary.time, summary.volume];
    lines.forEach((lineText) => {
      const line = document.createElement('div');
      line.textContent = lineText;
      label.appendChild(line);
    });

    if (!isPreview) {
      label.addEventListener('click', (event) => {
        event.stopPropagation();
        this.chartState.rulerSelectedId = ruler.id;
        this.renderChartRulers();
      });

      const deleteButton = document.createElement('button');
      deleteButton.type = 'button';
      deleteButton.className = 'absolute -right-2 -top-2 h-5 w-5 rounded-full bg-black/35 leading-none hover:bg-black/50';
      deleteButton.title = 'Delete ruler';
      deleteButton.textContent = 'x';
      deleteButton.addEventListener('click', (event) => {
        event.stopPropagation();
        this.deleteChartRuler(ruler.id);
      });
      label.appendChild(deleteButton);
    }
    overlay.appendChild(label);
  }

  resolveRulerPoint(point) {
    if (!point || !this.chart || !this.chartSeries.length) return null;
    const series = this.chartSeries[0];
    const timeScale = this.chart.timeScale();
    if (!timeScale || typeof timeScale.timeToCoordinate !== 'function' || typeof series.priceToCoordinate !== 'function') return null;

    const x = timeScale.timeToCoordinate(point.time);
    const y = series.priceToCoordinate(point.price);
    if (!Number.isFinite(Number(x)) || !Number.isFinite(Number(y))) return null;
    return { ...point, x: Number(x), y: Number(y) };
  }

  getRulerSummary(ruler) {
    const startPrice = Number(ruler.start?.price);
    const endPrice = Number(ruler.end?.price);
    const priceDiff = Number.isFinite(startPrice) && Number.isFinite(endPrice)
      ? endPrice - startPrice
      : 0;
    const percent = Number.isFinite(startPrice) && startPrice !== 0 && Number.isFinite(endPrice)
      ? ((endPrice - startPrice) / startPrice) * 100
      : 0;
    const priceSign = priceDiff > 0 ? '+' : '';
    const percentSign = percent > 0 ? '+' : '';
    const days = this.formatRulerDays(ruler.start?.time, ruler.end?.time);
    const stats = this.getRulerCandleStats(ruler.start?.time, ruler.end?.time);

    return {
      price: `${priceSign}${this.formatRulerValue(priceDiff)} (${percentSign}${this.formatRulerValue(percent)}%) ${stats.bars}`,
      time: `${stats.bars} bar, ${days}d`,
      volume: `Vol ${this.formatRulerVolume(stats.volume)}`
    };
  }

  formatRulerValue(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '-';
    const abs = Math.abs(number);
    const decimals = abs >= 100 ? 0 : 2;
    return number.toLocaleString('id-ID', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  formatRulerDays(startTime, endTime) {
    const start = this.parseLocalDate(startTime);
    const end = this.parseLocalDate(endTime);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '-';
    const days = Math.abs(end.getTime() - start.getTime()) / 86400000;
    if (days < 1 && days > 0) return this.formatRulerValue(days);
    return Math.round(days).toLocaleString('id-ID');
  }

  getRulerCandleStats(startTime, endTime) {
    const startMs = this.rulerTimeToMs(startTime);
    const endMs = this.rulerTimeToMs(endTime);
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) {
      return { bars: 0, volume: 0 };
    }

    const from = Math.min(startMs, endMs);
    const to = Math.max(startMs, endMs);
    const candles = this.chartState?.data?.candles || [];
    let bars = 0;
    let volume = 0;

    candles.forEach((candle) => {
      const candleMs = this.rulerTimeToMs(candle.time);
      if (!Number.isFinite(candleMs) || candleMs < from || candleMs > to) return;
      bars += 1;
      volume += Number(candle.volume || 0);
    });

    return { bars, volume };
  }

  rulerTimeToMs(value) {
    const date = this.parseLocalDate(value);
    const ms = date.getTime();
    return Number.isNaN(ms) ? NaN : ms;
  }

  formatRulerVolume(value) {
    const volume = Number(value);
    if (!Number.isFinite(volume) || volume === 0) return '-';

    const units = [
      { suffix: 'T', value: 1e12 },
      { suffix: 'B', value: 1e9 },
      { suffix: 'M', value: 1e6 },
      { suffix: 'K', value: 1e3 }
    ];
    const unit = units.find((item) => Math.abs(volume) >= item.value);
    if (!unit) return this.formatRulerValue(volume);
    return `${this.formatRulerValue(volume / unit.value)} ${unit.suffix}`;
  }

  deleteChartRuler(id) {
    if (!this.chartState) return;
    this.chartState.rulers = (this.chartState.rulers || []).filter((ruler) => ruler.id !== id);
    if (this.chartState.rulerSelectedId === id) this.chartState.rulerSelectedId = null;
    this.renderChartRulers();
  }

  syncChartTimeScales() {
    const charts = [this.chart, ...this.panelCharts].filter(Boolean);
    if (charts.length < 2) return;

    charts.forEach((sourceChart) => {
      const sourceScale = sourceChart.timeScale();
      if (!sourceScale || typeof sourceScale.subscribeVisibleLogicalRangeChange !== 'function') return;

      sourceScale.subscribeVisibleLogicalRangeChange((range) => {
        if (this.syncingChartRange || !range) return;
        this.syncingChartRange = true;
        charts.forEach((targetChart) => {
          if (targetChart === sourceChart) return;
          const targetScale = targetChart.timeScale();
          if (targetScale && typeof targetScale.setVisibleLogicalRange === 'function') {
            targetScale.setVisibleLogicalRange(range);
          }
        });
        this.syncingChartRange = false;
      });
    });
  }

  getChartOptions(container, height) {
    return {
      width: Math.max(320, container.clientWidth || 900),
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#334155'
      },
      grid: {
        vertLines: { color: '#e5e7eb' },
        horzLines: { color: '#e5e7eb' }
      },
      rightPriceScale: { borderColor: '#e5e7eb' },
      timeScale: { borderColor: '#e5e7eb', timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 }
    };
  }

  addChartSeries(chart, type, options) {
    const LW = window.LightweightCharts;
    if (type === 'candlestick') {
      if (typeof chart.addCandlestickSeries === 'function') return chart.addCandlestickSeries(options);
      return chart.addSeries(LW.CandlestickSeries, options);
    }
    if (type === 'histogram') {
      if (typeof chart.addHistogramSeries === 'function') return chart.addHistogramSeries(options);
      return chart.addSeries(LW.HistogramSeries, options);
    }
    if (typeof chart.addLineSeries === 'function') return chart.addLineSeries(options);
    return chart.addSeries(LW.LineSeries, options);
  }

  addChartMarkers(series, data) {
    const markers = [];
    if (data?.signal_time) {
      markers.push({
        time: data.signal_time,
        position: 'aboveBar',
        color: '#2563eb',
        shape: 'arrowDown',
        text: 'Signal'
      });
    }

    (data?.indicators || []).forEach((indicator) => {
      if (indicator.type !== 'marker' || !this.chartState.enabled.has(indicator.id)) return;
      (indicator.markers || []).forEach((marker) => markers.push(marker));
    });

    markers.sort((a, b) => Number(a.time || 0) - Number(b.time || 0));
    if (typeof series.setMarkers === 'function') {
      series.setMarkers(markers);
      return;
    }
    if (window.LightweightCharts?.createSeriesMarkers) {
      window.LightweightCharts.createSeriesMarkers(series, markers);
    }
  }

  addSignalMarker(series, signalTime) {
    const marker = {
      time: signalTime,
      position: 'aboveBar',
      color: '#2563eb',
      shape: 'arrowDown',
      text: 'Signal'
    };
    if (typeof series.setMarkers === 'function') {
      series.setMarkers([marker]);
      return;
    }
    if (window.LightweightCharts?.createSeriesMarkers) {
      window.LightweightCharts.createSeriesMarkers(series, [marker]);
    }
  }

  clearCharts() {
    if (this.chart) {
      if (this.chartRulerClickHandler && typeof this.chart.unsubscribeClick === 'function') {
        this.chart.unsubscribeClick(this.chartRulerClickHandler);
      }
      if (this.chartRulerMoveHandler && typeof this.chart.unsubscribeCrosshairMove === 'function') {
        this.chart.unsubscribeCrosshairMove(this.chartRulerMoveHandler);
      }
      if (this.chartRulerRangeHandler) {
        const timeScale = this.chart.timeScale();
        if (timeScale && typeof timeScale.unsubscribeVisibleLogicalRangeChange === 'function') {
          timeScale.unsubscribeVisibleLogicalRangeChange(this.chartRulerRangeHandler);
        }
      }
      this.chart.remove();
      this.chart = null;
    }
    this.chartRulerClickHandler = null;
    this.chartRulerMoveHandler = null;
    this.chartRulerRangeHandler = null;
    this.panelCharts.forEach((chart) => chart.remove());
    this.panelCharts = [];
    this.chartSeries = [];
    this.syncingChartRange = false;
    const mainEl = document.getElementById('swing-chart-main');
    const panelsEl = document.getElementById('swing-chart-panels');
    if (mainEl) mainEl.innerHTML = '';
    if (panelsEl) panelsEl.innerHTML = '';
  }

  seriesColor(index) {
    const colors = ['#2563eb', '#f59e0b', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#9333ea'];
    return colors[index % colors.length];
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
