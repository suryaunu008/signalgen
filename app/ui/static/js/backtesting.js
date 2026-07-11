class BacktestingUI {
  constructor() {
    this.currentResults = null;
    this.entryPriceBasis = 'close';
    this.exitPriceBasis = 'close';
    this.focusLabel = 'REALIZED';
    this.currentPage = 1;
    this.pageSize = 25;
    this.initialized = false;
    this.backtestingInProgress = false;
  }

  async init() {
    if (!this.initialized) {
      this.setupEventListeners();
      this.initialized = true;
    }
    this.renderTimezoneLabel();
    await this.loadRules();
    this.onModeChange(document.getElementById('backtest-mode')?.value || 'rule');
    this.onExitStrategyChange(document.getElementById('backtest-exit-strategy')?.value || 'holding_period');
    this.onPositionSizingChange(document.getElementById('backtest-position-sizing')?.value || 'percent_equity');
  }

  // ---------------------------------------------------------------------
  // History (persisted runs: config + headline summary; not the full table)
  // Shown in a modal to keep the main view uncluttered.
  // ---------------------------------------------------------------------
  openHistoryModal() {
    const modal = document.getElementById('backtest-history-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
    this.loadHistory();
  }

  closeHistoryModal() {
    const modal = document.getElementById('backtest-history-modal');
    if (modal) modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }

  async loadHistory() {
    const el = document.getElementById('backtest-history-list');
    if (!el) return;
    try {
      const res = await fetch('/api/backtest/screen/runs?limit=50');
      if (!res.ok) throw new Error('Failed to load history');
      const runs = await res.json();
      this.renderHistory(Array.isArray(runs) ? runs : []);
    } catch (err) {
      el.innerHTML = `<p class="text-rose-600">Failed to load history: ${this.escapeHtml(err.message)}</p>`;
    }
  }

  renderHistory(runs) {
    const el = document.getElementById('backtest-history-list');
    if (!el) return;
    if (runs.length === 0) {
      el.innerHTML =
        '<p class="text-slate-500">No saved runs yet. Run a backtest to see it here.</p>';
      return;
    }
    el.innerHTML = runs.map((run) => this.buildHistoryRowHtml(run)).join('');
  }

  // Pick the headline metric block consistent with the results view:
  // realized exits unless the run used a plain holding period.
  historyHeadline(run) {
    const summary = run.summary || {};
    const cfg = run.config || {};
    const useRealized = cfg.exit_strategy && cfg.exit_strategy !== 'holding_period';
    return (
      (useRealized ? summary.realized : summary.final) ||
      summary.final ||
      summary.realized ||
      null
    );
  }

  buildHistoryRowHtml(run) {
    const cfg = run.config || {};
    const summary = run.summary || {};
    const m = this.historyHeadline(run) || {};
    const fmtPct = (v) =>
      v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${Number(v).toFixed(2)}%`;
    const ret = Number(m.total_return_pct);
    const retClass = ret > 0 ? 'text-emerald-700' : ret < 0 ? 'text-rose-700' : 'text-slate-600';
    const entries = summary.total_entries;
    const exitLabel =
      { holding_period: 'Holding', target_stop: 'TP/SL', exit_signal: 'Exit Signal' }[
        cfg.exit_strategy
      ] || cfg.exit_strategy || '-';
    const badge = (text, cls = 'bg-slate-100 text-slate-700') =>
      `<span class="rounded-full ${cls} px-2 py-0.5 text-[11px] font-semibold">${this.escapeHtml(text)}</span>`;
    return `
      <div class="rounded-lg border border-slate-200 mb-2">
        <div class="flex items-center gap-3 p-3">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-1.5">
              ${badge(cfg.mode || run.mode || 'run', 'bg-slate-800 text-white')}
              ${badge('T ' + (cfg.timeframe || run.timeframe || '-'))}
              ${badge('T+' + (cfg.n_steps != null ? cfg.n_steps : '?'))}
              ${badge(exitLabel, 'bg-purple-100 text-purple-800')}
            </div>
            <div class="mt-1 text-xs text-slate-500">${this.fmtHistoryDate(run.created_at)}</div>
          </div>
          <div class="text-right whitespace-nowrap">
            <div class="text-sm font-bold ${retClass}">${fmtPct(m.total_return_pct)}</div>
            <div class="text-[11px] text-slate-500">${run.row_count != null ? run.row_count : 0} trades${
              entries != null ? ` · ${entries} entries` : ''
            }</div>
          </div>
          <div class="flex items-center gap-1">
            <button type="button" onclick="backtestingUI.toggleHistoryDetail(${run.id})" class="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50" title="View details"><i class="fas fa-eye"></i></button>
            <button type="button" onclick="backtestingUI.deleteHistoryRun(${run.id})" class="rounded-md border border-rose-200 px-2 py-1 text-xs font-semibold text-rose-600 hover:bg-rose-50" title="Delete"><i class="fas fa-trash"></i></button>
          </div>
        </div>
        <div id="backtest-history-detail-${run.id}" class="hidden border-t border-slate-100 p-3 bg-slate-50">
          ${this.buildHistoryDetailHtml(run)}
        </div>
      </div>`;
  }

  buildHistoryDetailHtml(run) {
    const cfg = run.config || {};
    const m = this.historyHeadline(run) || {};
    const fmtPct = (v) =>
      v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${Number(v).toFixed(2)}%`;
    const fmtCash = (v) =>
      v === null || v === undefined || Number.isNaN(Number(v))
        ? '-'
        : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    const fmtNum = (v, d = 2) =>
      v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(d);

    const range =
      cfg.start_at || cfg.end_at
        ? `${this.fmtHistoryDate(cfg.start_at)} → ${this.fmtHistoryDate(cfg.end_at)}`
        : '-';
    const tpsl = [];
    if (cfg.take_profit_pct != null) tpsl.push(`TP ${cfg.take_profit_pct}%`);
    if (cfg.stop_loss_pct != null) tpsl.push(`SL ${cfg.stop_loss_pct}%`);

    let exitDetail = tpsl.length ? tpsl.join(' · ') : cfg.exit_strategy || '-';
    if (cfg.exit_strategy === 'exit_signal' && cfg.exit_rule_id != null) {
      exitDetail = `Exit Signal · ${this.ruleName(cfg.exit_rule_id)}`;
    }

    const cfgRows = [
      ['Rule', cfg.rule_id != null ? this.ruleName(cfg.rule_id) : '—'],
      ['Data source', cfg.data_source || '-'],
      ['Range', range],
      ['Entry / Exit basis', `${cfg.entry_price_basis || '-'} / ${cfg.exit_price_basis || '-'}`],
      ['Exit strategy', exitDetail],
      ['Symbols', Array.isArray(cfg.symbols) && cfg.symbols.length ? cfg.symbols.join(', ') : '-'],
    ];

    const metricCards = [
      ['Total Return', fmtPct(m.total_return_pct)],
      ['Net P/L', fmtCash(m.net_pl_cash)],
      ['Win Rate', fmtPct(m.win_rate)],
      ['Trades', m.evaluated != null ? String(m.evaluated) : '-'],
      ['Max Drawdown', fmtPct(m.max_drawdown_pct)],
      ['Profit Factor', fmtNum(m.profit_factor, 2)],
    ];

    return `
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs mb-3">
        ${cfgRows
          .map(
            ([k, v]) => `
          <div class="flex justify-between gap-3 border-b border-slate-100 py-1">
            <span class="text-slate-500">${k}</span>
            <span class="font-medium text-slate-800 text-right truncate">${this.escapeHtml(v)}</span>
          </div>`
          )
          .join('')}
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
        ${metricCards
          .map(
            ([label, value]) => `
          <div class="rounded-md border border-slate-200 bg-white p-2">
            <div class="text-[10px] font-semibold uppercase text-slate-500">${label}</div>
            <div class="mt-0.5 text-sm font-bold text-slate-800">${value}</div>
          </div>`
          )
          .join('')}
      </div>`;
  }

  toggleHistoryDetail(runId) {
    const el = document.getElementById(`backtest-history-detail-${runId}`);
    if (el) el.classList.toggle('hidden');
  }

  async deleteHistoryRun(runId) {
    if (!window.confirm('Delete this saved backtest run?')) return;
    try {
      const res = await fetch(`/api/backtest/screen/runs/${runId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Delete failed');
      }
      this.showSuccess('Run deleted');
      this.loadHistory();
    } catch (err) {
      this.showError(`Delete failed: ${err.message}`);
    }
  }

  ruleName(ruleId) {
    const name = this.rulesById && this.rulesById[ruleId];
    return name || `Rule #${ruleId}`;
  }

  fmtHistoryDate(value) {
    if (!value) return '-';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  renderTimezoneLabel() {
    const el = document.getElementById('backtest-timezone-label');
    if (!el) return;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';
    el.textContent = `Timezone: ${tz} (device local)`;
  }

  setupEventListeners() {
    const runButton = document.getElementById('run-backtest-btn');
    if (runButton) runButton.addEventListener('click', () => this.runBacktesting());

    const modeSelect = document.getElementById('backtest-mode');
    if (modeSelect) modeSelect.addEventListener('change', (e) => this.onModeChange(e.target.value));

    const exitStrategy = document.getElementById('backtest-exit-strategy');
    if (exitStrategy) exitStrategy.addEventListener('change', (e) => this.onExitStrategyChange(e.target.value));

    const sizing = document.getElementById('backtest-position-sizing');
    if (sizing) sizing.addEventListener('change', (e) => this.onPositionSizingChange(e.target.value));
  }

  onModeChange(mode) {
    const ruleFields = document.getElementById('backtest-rule-mode-fields');
    const manualFields = document.getElementById('backtest-manual-mode-fields');
    if (!ruleFields || !manualFields) return;

    if (mode === 'manual') {
      ruleFields.classList.add('hidden');
      manualFields.classList.remove('hidden');
      return;
    }

    manualFields.classList.add('hidden');
    ruleFields.classList.remove('hidden');
  }

  onExitStrategyChange(strategy) {
    const tp = document.getElementById('backtest-tp-field');
    const sl = document.getElementById('backtest-sl-field');
    const rule = document.getElementById('backtest-exit-rule-field');
    const hint = document.getElementById('backtest-exit-strategy-hint');
    const show = (el, on) => el && el.classList.toggle('hidden', !on);

    show(tp, strategy === 'target_stop');
    show(sl, strategy === 'target_stop');
    show(rule, strategy === 'exit_signal');

    if (hint) {
      if (strategy === 'target_stop') {
        hint.textContent = 'Take Profit / Stop Loss: each position is closed at the first candle that touches your TP or SL level (SL checked first if both hit). Falls back to a time exit at Max Holding.';
      } else if (strategy === 'exit_signal') {
        hint.textContent = 'Exit Signal: each position is closed at the first candle after entry where the chosen exit rule fires, capped at Max Holding candles.';
      } else {
        hint.textContent = 'Holding Period: every entry is exited after N candles; the result table compares all T+1..T+N horizons.';
      }
    }
  }

  onPositionSizingChange(sizing) {
    const label = document.getElementById('backtest-position-size-label');
    const input = document.getElementById('backtest-position-size');
    if (!label || !input) return;
    if (sizing === 'fixed_amount') {
      label.textContent = 'Size (amount/trade)';
      input.value = input.value === '100' ? '1000' : input.value;
    } else {
      label.textContent = 'Size (% equity)';
      input.value = input.value === '1000' ? '100' : input.value;
    }
  }

  async loadRules() {
    try {
      const response = await fetch('/api/rules');
      const rules = await response.json();
      const select = document.getElementById('backtest-rule-select');
      const exitSelect = document.getElementById('backtest-exit-rule-select');
      if (!Array.isArray(rules)) return;

      // Cache id -> name so history (which only stores rule_id) can show names.
      this.rulesById = {};
      rules.forEach((rule) => { this.rulesById[rule.id] = rule.name; });

      if (select) select.innerHTML = '<option value="">Select rule...</option>';
      if (exitSelect) exitSelect.innerHTML = '<option value="">Select exit rule...</option>';
      rules.forEach((rule) => {
        const label = `${rule.name}${rule.is_system ? ' (System)' : ''}`;
        if (select) {
          const option = document.createElement('option');
          option.value = rule.id;
          option.textContent = label;
          select.appendChild(option);
        }
        if (exitSelect) {
          const opt = document.createElement('option');
          opt.value = rule.id;
          opt.textContent = label;
          exitSelect.appendChild(opt);
        }
      });
    } catch (error) {
      this.showError('Failed to load rules');
      console.error(error);
    }
  }

  parseManualEntries(input) {
    const lines = input.split('\n').map((v) => v.trim()).filter(Boolean);
    const entries = [];
    for (const line of lines) {
      const parts = line.split(',').map((v) => v.trim());
      if (parts.length < 2) {
        throw new Error(`Invalid manual entry line: ${line}`);
      }
      const signalType = (parts[2] || 'BUY').toUpperCase();
      if (!['BUY', 'SELL'].includes(signalType)) {
        throw new Error(`Invalid signal type in line: ${line}`);
      }
      const entry = { symbol: parts[0], entry_time: this.localInputToIso(parts[1]), signal_type: signalType };
      if (parts[3] !== undefined && parts[3] !== '') {
        const entryPrice = Number(parts[3]);
        if (!Number.isFinite(entryPrice) || entryPrice <= 0) {
          throw new Error(`Invalid entry price in line: ${line}`);
        }
        entry.entry_price = entryPrice;
      }
      entries.push(entry);
    }
    return entries;
  }

  localInputToIso(value) {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) {
      throw new Error(`Invalid datetime value: ${value}`);
    }
    return value;
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

  async runBacktesting() {
    if (this.backtestingInProgress) {
      return;
    }

    try {
      this.backtestingInProgress = true;
      const mode = document.getElementById('backtest-mode')?.value;
      const timeframe = document.getElementById('backtest-timeframe')?.value;
      const nSteps = parseInt(document.getElementById('backtest-n-steps')?.value || '0', 10);
      const dataSource = document.getElementById('backtest-data-source')?.value;
      const entryPriceBasis = document.getElementById('backtest-entry-price-basis')?.value || 'close';
      const exitPriceBasis = document.getElementById('backtest-exit-price-basis')?.value || 'close';

      if (!mode || !timeframe || !dataSource || Number.isNaN(nSteps) || nSteps < 1) {
        this.showError('Invalid input');
        return;
      }
      this.entryPriceBasis = entryPriceBasis;
      this.exitPriceBasis = exitPriceBasis;

      const payload = {
        mode,
        timeframe,
        n_steps: nSteps,
        data_source: dataSource,
        entry_price_basis: entryPriceBasis,
        exit_price_basis: exitPriceBasis,
        initial_capital: Number(document.getElementById('backtest-initial-capital')?.value || 10000),
        position_sizing: document.getElementById('backtest-position-sizing')?.value || 'percent_equity',
        position_size: Number(document.getElementById('backtest-position-size')?.value || 100),
        commission_pct: Number(document.getElementById('backtest-commission-pct')?.value || 0),
        slippage_pct: Number(document.getElementById('backtest-slippage-pct')?.value || 0)
      };

      if (!(payload.initial_capital > 0) || !(payload.position_size > 0)) {
        this.showError('Initial capital and position size must be greater than 0');
        return;
      }

      // Exit strategy
      const exitStrategy = document.getElementById('backtest-exit-strategy')?.value || 'holding_period';
      payload.exit_strategy = exitStrategy;
      if (exitStrategy === 'target_stop') {
        const tp = document.getElementById('backtest-take-profit')?.value;
        const sl = document.getElementById('backtest-stop-loss')?.value;
        if ((!tp || tp === '') && (!sl || sl === '')) {
          this.showError('Take Profit / Stop Loss requires at least one of TP% or SL%');
          return;
        }
        if (tp) payload.take_profit_pct = Number(tp);
        if (sl) payload.stop_loss_pct = Number(sl);
      } else if (exitStrategy === 'exit_signal') {
        const exitRuleId = document.getElementById('backtest-exit-rule-select')?.value;
        if (!exitRuleId) {
          this.showError('Exit Signal strategy requires an exit rule');
          return;
        }
        payload.exit_rule_id = parseInt(exitRuleId, 10);
      }

      if (mode === 'rule') {
        const ruleId = document.getElementById('backtest-rule-select')?.value;
        const startAt = document.getElementById('backtest-start-at')?.value;
        const endAt = document.getElementById('backtest-end-at')?.value;
        const symbolsRaw = document.getElementById('backtest-symbols')?.value?.trim() || '';
        if (!ruleId || !startAt || !endAt) {
          this.showError('Rule mode requires: rule, start, end');
          return;
        }

        payload.rule_id = parseInt(ruleId, 10);
        payload.start_at = this.localInputToIso(startAt);
        payload.end_at = this.localInputToIso(endAt);

        if (symbolsRaw) {
          payload.symbols = symbolsRaw.split(',').map((s) => s.trim()).filter(Boolean);
        }
      } else {
        const manualRaw = document.getElementById('backtest-manual-entries')?.value || '';
        payload.manual_entries = this.parseManualEntries(manualRaw);
        if (payload.manual_entries.length === 0) {
          this.showError('Manual mode requires at least 1 entry');
          return;
        }
      }

      this.showLoading('Running backtesting...');
      const response = await fetch('/api/backtest/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Backtesting failed');
      }

      const result = await response.json();
      result.entry_price_basis = result.entry_price_basis || this.entryPriceBasis;
      result.exit_price_basis = result.exit_price_basis || result.pl_basis || this.exitPriceBasis;
      this.currentResults = result;
      // Default focus: realized exit unless plain holding-period (then final horizon)
      this.focusLabel = (result.exit_strategy && result.exit_strategy !== 'holding_period')
        ? 'REALIZED'
        : `T+${result.n_steps}`;
      this.renderResults(result);
      this.hideLoading();
      this.showSuccess(`Completed. Trades: ${result.row_count}`);
    } catch (error) {
      this.hideLoading();
      this.showError(`Backtesting failed: ${error.message}`);
      console.error(error);
    } finally {
      this.backtestingInProgress = false;
    }
  }

  getFocusMetrics() {
    const m = this.currentResults?.metrics;
    if (!m) return null;
    if (this.focusLabel === 'REALIZED') return m.realized || m.final;
    const step = parseInt(String(this.focusLabel).replace('T+', ''), 10);
    return (m.per_step || [])[step - 1] || m.final;
  }

  getFocusExit(row) {
    return row?.steps?.[this.focusLabel] || null;
  }

  renderResults(result) {
    const container = document.getElementById('backtest-results-container');
    if (!container) return;

    this.currentPage = 1;
    const strategyLabel = {
      holding_period: 'Holding Period',
      target_stop: 'TP / SL',
      exit_signal: 'Exit Signal'
    }[result.exit_strategy] || 'Holding Period';

    container.innerHTML = `
      <section class="bg-gradient-to-b from-slate-50 to-white rounded-xl border border-slate-200 shadow-sm p-5">
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <h3 class="text-lg font-semibold text-slate-900">Result</h3>
          <span class="rounded-full bg-blue-100 text-blue-800 px-2.5 py-1 text-xs font-semibold">${result.row_count} trades</span>
          <span class="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 text-xs font-semibold">Mode ${result.mode}</span>
          <span class="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 text-xs font-semibold">T ${result.timeframe}</span>
          <span class="rounded-full bg-purple-100 text-purple-800 px-2.5 py-1 text-xs font-semibold">Exit: ${strategyLabel}</span>
          <span class="rounded-full bg-blue-100 text-blue-800 px-2.5 py-1 text-xs font-semibold">Entry ${(result.entry_price_basis || 'close').toUpperCase()}</span>
          <span class="rounded-full bg-amber-100 text-amber-800 px-2.5 py-1 text-xs font-semibold">Exit ${(result.exit_price_basis || 'close').toUpperCase()}</span>
        </div>
        ${this.buildFocusControlHtml(result)}
        <div id="backtest-headline"></div>
        <div id="backtest-equity"></div>
        ${result.exit_strategy === 'holding_period' ? this.buildHoldingPeriodTableHtml(result.metrics) : ''}
        ${this.buildBySymbolTableHtml(result.metrics)}
        <div class="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table class="min-w-full bg-white">
            <thead id="backtest-results-head"></thead>
            <tbody id="backtest-results-body"></tbody>
          </table>
        </div>
        <div id="backtest-pagination-bar" class="mt-4 flex items-center justify-between"></div>
      </section>
    `;

    const focusSelect = document.getElementById('backtest-focus-select');
    if (focusSelect) {
      focusSelect.addEventListener('change', (e) => {
        this.focusLabel = e.target.value;
        this.renderFocusViews();
      });
    }

    this.renderFocusViews();
  }

  buildFocusControlHtml(result) {
    if (result.exit_strategy !== 'holding_period') {
      return `
        <div class="mb-3 flex items-center gap-2 text-sm text-slate-600">
          <i class="fas fa-flag-checkered text-slate-400"></i>
          Showing <b class="text-slate-800">realized exits</b> (first exit that satisfied the strategy).
        </div>`;
    }
    const options = [];
    for (let i = 1; i <= result.n_steps; i += 1) {
      options.push(`<option value="T+${i}" ${this.focusLabel === `T+${i}` ? 'selected' : ''}>T+${i}</option>`);
    }
    return `
      <div class="mb-3 flex items-center gap-2">
        <label class="text-sm font-medium text-slate-700">Holding Period</label>
        <select id="backtest-focus-select" class="px-2 py-1 rounded border border-slate-300 text-sm">${options.join('')}</select>
        <span class="text-xs text-slate-500">Trade list &amp; headline reflect the selected exit horizon.</span>
      </div>`;
  }

  renderFocusViews() {
    const m = this.getFocusMetrics();
    const headline = document.getElementById('backtest-headline');
    if (headline) headline.innerHTML = this.buildHeadlineHtml(m);
    const equity = document.getElementById('backtest-equity');
    if (equity) equity.innerHTML = this.buildEquityCurveHtml(m);
    this.renderTableHead();
    this.currentPage = 1;
    this.renderBacktestTable();
  }

  buildHeadlineHtml(m) {
    if (!m) return '';
    const fmtCash = (v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    const fmtPct = (v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${Number(v).toFixed(2)}%`;
    const fmtNum = (v, d = 2) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(d);
    const retClass = Number(m.total_return_pct) > 0 ? 'text-emerald-700' : Number(m.total_return_pct) < 0 ? 'text-rose-700' : 'text-slate-700';
    const plClass = Number(m.net_pl_cash) > 0 ? 'text-emerald-700' : Number(m.net_pl_cash) < 0 ? 'text-rose-700' : 'text-slate-700';

    const cards = [
      ['Final Equity', fmtCash(m.final_equity), 'text-slate-900'],
      ['Net P/L', `${Number(m.net_pl_cash) > 0 ? '+' : ''}${fmtCash(m.net_pl_cash)}`, plClass],
      ['Total Return', `${Number(m.total_return_pct) > 0 ? '+' : ''}${fmtPct(m.total_return_pct)}`, retClass],
      ['Max Drawdown', fmtPct(m.max_drawdown_pct), 'text-rose-700'],
      ['Win Rate', fmtPct(m.win_rate), 'text-emerald-700'],
      ['Trades', `${m.evaluated || 0}`, 'text-slate-900'],
      ['Profit Factor', m.profit_factor === null || m.profit_factor === undefined ? '-' : fmtNum(m.profit_factor, 2), 'text-blue-700'],
      ['Expectancy', fmtCash(m.expectancy_cash), plClass],
      ['Avg Win / Loss', `${fmtCash(m.avg_win_cash)} / ${fmtCash(m.avg_loss_cash)}`, 'text-slate-700'],
      ['Risk / Reward', m.risk_reward === null || m.risk_reward === undefined ? '-' : fmtNum(m.risk_reward, 2), 'text-slate-700'],
      ['Sharpe (per-trade)', m.sharpe === null || m.sharpe === undefined ? '-' : fmtNum(m.sharpe, 2), 'text-slate-700'],
      ['Commission', fmtCash(m.total_commission), 'text-slate-500']
    ];

    return `
      <div class="mb-4 grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        ${cards.map(([label, value, cls]) => `
          <div class="rounded-lg border border-slate-200 bg-white p-3">
            <div class="text-[11px] font-semibold uppercase text-slate-500">${label}</div>
            <div class="mt-1 text-lg font-bold ${cls}">${value}</div>
          </div>
        `).join('')}
      </div>`;
  }

  buildEquityCurveHtml(m) {
    const pts = (m && m.equity_curve) || [];
    if (pts.length < 2) {
      return '<div class="mb-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">Not enough trades for an equity curve.</div>';
    }
    const eqs = pts.map((p) => Number(p.equity));
    const base = Number(m.initial_capital) || eqs[0];
    const min = Math.min(...eqs, base);
    const max = Math.max(...eqs, base);
    const W = 600;
    const H = 160;
    const pad = 10;
    const range = (max - min) || 1;
    const x = (i) => pad + (i / (pts.length - 1)) * (W - 2 * pad);
    const y = (v) => H - pad - ((v - min) / range) * (H - 2 * pad);
    const linePts = pts.map((p, i) => `${x(i).toFixed(1)},${y(Number(p.equity)).toFixed(1)}`).join(' ');
    const areaPts = `${pad.toFixed(1)},${(H - pad).toFixed(1)} ${linePts} ${(W - pad).toFixed(1)},${(H - pad).toFixed(1)}`;
    const baseY = y(base).toFixed(1);
    const up = Number(m.final_equity) >= base;
    const stroke = up ? '#059669' : '#e11d48';
    const fill = up ? 'rgba(5,150,105,0.12)' : 'rgba(225,29,72,0.12)';

    return `
      <div class="mb-4 rounded-lg border border-slate-200 bg-white p-4">
        <div class="mb-2 flex items-center justify-between">
          <div class="text-sm font-semibold text-slate-700">Equity Curve <span class="text-xs font-normal text-slate-400">(${this.focusLabel === 'REALIZED' ? 'realized exits' : this.focusLabel})</span></div>
          <div class="text-xs text-slate-500">Peak ${max.toLocaleString(undefined, { maximumFractionDigits: 0 })} &middot; Trough ${min.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
        </div>
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:160px;">
          <line x1="${pad}" y1="${baseY}" x2="${W - pad}" y2="${baseY}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 4" />
          <polygon points="${areaPts}" fill="${fill}" stroke="none" />
          <polyline points="${linePts}" fill="none" stroke="${stroke}" stroke-width="2" />
        </svg>
        <div class="mt-1 flex justify-between text-[11px] text-slate-400">
          <span>Start ${base.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          <span>End ${Number(m.final_equity).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        </div>
      </div>`;
  }

  buildHoldingPeriodTableHtml(metrics) {
    if (!metrics || !Array.isArray(metrics.per_step)) return '';
    const fmtCash = (v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    const fmtPct = (v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${Number(v).toFixed(2)}%`;
    const fmtNum = (v, d = 2) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(d);
    const rows = metrics.per_step.map((step) => {
      const retClass = Number(step.total_return_pct) > 0 ? 'text-emerald-700' : Number(step.total_return_pct) < 0 ? 'text-rose-700' : 'text-slate-700';
      const active = this.focusLabel === step.label ? 'bg-blue-50' : 'odd:bg-white even:bg-slate-50';
      return `
        <tr class="${active} cursor-pointer hover:bg-blue-50/60" data-focus="${step.label}">
          <td class="px-3 py-2 text-sm font-semibold text-slate-900">${step.label}</td>
          <td class="px-3 py-2 text-sm text-slate-700">${step.evaluated}</td>
          <td class="px-3 py-2 text-sm text-slate-700">${fmtPct(step.win_rate)}</td>
          <td class="px-3 py-2 text-sm font-semibold ${retClass}">${fmtPct(step.total_return_pct)}</td>
          <td class="px-3 py-2 text-sm ${retClass}">${fmtCash(step.net_pl_cash)}</td>
          <td class="px-3 py-2 text-sm text-rose-700">${fmtPct(step.max_drawdown_pct)}</td>
          <td class="px-3 py-2 text-sm text-blue-700">${step.profit_factor === null || step.profit_factor === undefined ? '-' : fmtNum(step.profit_factor, 2)}</td>
          <td class="px-3 py-2 text-sm text-slate-700">${fmtCash(step.expectancy_cash)}</td>
        </tr>`;
    }).join('');

    setTimeout(() => {
      document.querySelectorAll('#backtest-holding-table tr[data-focus]').forEach((tr) => {
        tr.addEventListener('click', () => {
          const label = tr.getAttribute('data-focus');
          this.focusLabel = label;
          const sel = document.getElementById('backtest-focus-select');
          if (sel) sel.value = label;
          this.renderResults(this.currentResults);
        });
      });
    }, 0);

    return `
      <div class="mb-4">
        <div class="mb-2 text-sm font-semibold text-slate-700">Holding Period Analysis <span class="text-xs font-normal text-slate-400">(click a row to focus)</span></div>
        <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table id="backtest-holding-table" class="min-w-full">
            <thead>
              <tr class="bg-slate-100">
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Horizon</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Trades</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Win Rate</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Return %</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Net P/L</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Max DD</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Profit Factor</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Expectancy</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="8" class="px-3 py-3 text-sm text-slate-500">No metric rows</td></tr>'}</tbody>
          </table>
        </div>
      </div>`;
  }

  buildBySymbolTableHtml(metrics) {
    const list = (metrics && metrics.by_symbol) || [];
    if (!list.length) return '';
    const fmtPct = (v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${Number(v).toFixed(2)}%`;
    const fmtNum = (v, d = 4) => v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(d);
    const rows = list.slice(0, 10).map((row) => {
      const totalClass = Number(row.total_pl) > 0 ? 'text-emerald-700' : Number(row.total_pl) < 0 ? 'text-rose-700' : 'text-slate-700';
      return `
        <tr class="odd:bg-white even:bg-slate-50">
          <td class="px-3 py-2 text-sm font-semibold text-slate-900">${row.symbol}</td>
          <td class="px-3 py-2 text-sm text-slate-700">${row.evaluated}/${row.trades}</td>
          <td class="px-3 py-2 text-sm text-slate-700">${fmtPct(row.win_rate)}</td>
          <td class="px-3 py-2 text-sm font-semibold ${totalClass}">${fmtNum(row.total_pl, 4)}</td>
          <td class="px-3 py-2 text-sm ${totalClass}">${fmtPct(row.avg_pl_pct)}</td>
        </tr>`;
    }).join('');
    return `
      <div class="mb-4">
        <div class="mb-2 text-sm font-semibold text-slate-700">By Symbol <span class="text-xs font-normal text-slate-400">(final horizon, price P/L)</span></div>
        <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table class="min-w-full">
            <thead>
              <tr class="bg-slate-100">
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Ticker</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Eval/Trade</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Win Rate</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Final P/L</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-700">Avg P/L%</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  renderTableHead() {
    const head = document.getElementById('backtest-results-head');
    if (!head) return;
    const showReason = this.currentResults?.exit_strategy && this.currentResults.exit_strategy !== 'holding_period';
    const headers = ['Ticker', 'Signal', 'Entry Time', 'Entry Price', 'Exit Time', 'Exit Price'];
    if (showReason) headers.push('Exit Reason');
    headers.push('P/L', 'P/L %');
    head.innerHTML = `<tr>${headers.map((h) => `<th class="bg-slate-100 px-3 py-3 text-left text-xs font-semibold tracking-wide text-slate-700 uppercase border-b border-slate-200">${h}</th>`).join('')}</tr>`;
  }

  buildTradeRowHtml(row) {
    const signalType = (row.signal_type || 'BUY').toUpperCase();
    const signalClass = signalType === 'SELL' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700';
    const showReason = this.currentResults?.exit_strategy && this.currentResults.exit_strategy !== 'holding_period';
    const step = this.getFocusExit(row);

    const cells = [
      `<span class="font-semibold text-slate-900">${row.symbol}</span>`,
      `<span class="rounded-full px-2 py-1 text-xs font-semibold ${signalClass}">${signalType}</span>`,
      `<span class="text-slate-700">${this.formatDateTime(row.entry_time)}</span>`,
      `<span class="font-semibold text-slate-900">${Number(row.entry_price).toFixed(4)}</span>`
    ];

    if (!step) {
      cells.push('<span class="text-slate-400">-</span>', '<span class="text-slate-400">-</span>');
      if (showReason) cells.push('<span class="text-slate-400">-</span>');
      cells.push('<span class="text-slate-400">-</span>', '<span class="text-slate-400">-</span>');
    } else {
      const pl = Number(step.pl);
      const plPct = Number(step.pl_pct);
      const plClass = pl > 0 ? 'text-emerald-700' : pl < 0 ? 'text-rose-700' : 'text-slate-700';
      const sign = pl > 0 ? '+' : '';
      cells.push(
        `<span class="text-slate-700">${this.formatDateTime(step.time)}</span>`,
        `<span class="font-semibold text-slate-900">${Number(step.exit_price).toFixed(4)}</span>`
      );
      if (showReason) {
        const reason = step.exit_reason || 'time_exit';
        const reasonClass = {
          take_profit: 'bg-emerald-100 text-emerald-700',
          stop_loss: 'bg-rose-100 text-rose-700',
          exit_signal: 'bg-blue-100 text-blue-700',
          time_exit: 'bg-slate-100 text-slate-600'
        }[reason] || 'bg-slate-100 text-slate-600';
        cells.push(`<span class="rounded-full px-2 py-1 text-xs font-semibold ${reasonClass}">${reason.replace('_', ' ')}</span>`);
      }
      cells.push(
        `<span class="font-semibold ${plClass}">${sign}${pl.toFixed(4)}</span>`,
        `<span class="${plClass}">${sign}${plPct.toFixed(2)}%</span>`
      );
    }

    return `<tr class="odd:bg-white even:bg-slate-50 hover:bg-blue-50/40">${cells.map((v) => `<td class="px-3 py-2 align-top text-sm border-b border-slate-200">${v}</td>`).join('')}</tr>`;
  }

  renderBacktestTable() {
    if (!this.currentResults || !Array.isArray(this.currentResults.rows)) return;
    const tbody = document.getElementById('backtest-results-body');
    if (!tbody) return;

    const rows = this.currentResults.rows;
    const totalItems = rows.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / this.pageSize));
    if (this.currentPage > totalPages) this.currentPage = totalPages;
    const start = (this.currentPage - 1) * this.pageSize;
    const end = Math.min(start + this.pageSize, totalItems);
    const pageRows = rows.slice(start, end);

    tbody.innerHTML = pageRows.length > 0
      ? pageRows.map((row) => this.buildTradeRowHtml(row)).join('')
      : '<tr><td class="px-3 py-4 text-sm text-gray-500" colspan="999">No rows</td></tr>';

    this.renderBacktestPagination(totalItems, totalPages, totalItems === 0 ? 0 : start + 1, end);
  }

  renderBacktestPagination(totalItems, totalPages, from, to) {
    const bar = document.getElementById('backtest-pagination-bar');
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
        this.renderBacktestTable();
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
        this.renderBacktestTable();
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
        this.renderBacktestTable();
      }
    });

    right.appendChild(sizeWrap);
    right.appendChild(prev);
    right.appendChild(page);
    right.appendChild(next);
    bar.appendChild(left);
    bar.appendChild(right);
  }

  csvEscape(value) {
    const s = value === null || value === undefined ? '' : String(value);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  downloadCsv(filename, csvText) {
    // Route through the backend so the WebView2/PyWebView runtime saves via its
    // native download manager (blob + `download` attribute is unreliable there).
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/backtest/export-csv';
    form.style.display = 'none';
    const addField = (name, val) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      input.value = val;
      form.appendChild(input);
    };
    addField('filename', filename);
    addField('csv', csvText);
    document.body.appendChild(form);
    form.submit();
    setTimeout(() => { if (form.parentNode) document.body.removeChild(form); }, 1000);
  }

  exportCsv() {
    if (!this.currentResults || !Array.isArray(this.currentResults.rows)) {
      this.showError('No results available to export');
      return;
    }

    const result = this.currentResults;
    const showReason = result.exit_strategy && result.exit_strategy !== 'holding_period';
    const headers = ['Ticker', 'Signal', 'Entry Time', 'Entry Price', 'Exit Time', 'Exit Price'];
    if (showReason) headers.push('Exit Reason');
    headers.push('P/L', 'P/L %', 'Focus');

    const esc = (v) => this.csvEscape(v);
    const lines = [headers.map(esc).join(',')];
    for (const row of result.rows) {
      const step = this.getFocusExit(row);
      const line = [
        row.symbol,
        row.signal_type || 'BUY',
        this.formatDateTime(row.entry_time),
        row.entry_price,
        step ? this.formatDateTime(step.time) : '',
        step ? step.exit_price : ''
      ];
      if (showReason) line.push(step ? (step.exit_reason || 'time_exit') : '');
      line.push(
        step ? Number(step.pl).toFixed(6) : '',
        step ? Number(step.pl_pct).toFixed(4) : '',
        this.focusLabel
      );
      lines.push(line.map(esc).join(','));
    }

    this.downloadCsv(`backtest_${Date.now()}.csv`, lines.join('\n'));
  }

  showLoading(message) {
    const loadingDiv = document.getElementById('backtest-loading');
    if (!loadingDiv) return;
    loadingDiv.innerHTML = `<div class="flex items-center justify-center p-4 bg-blue-50 rounded-lg"><i class="fas fa-spinner fa-spin mr-2"></i><span>${message}</span></div>`;
    loadingDiv.classList.remove('hidden');
  }

  hideLoading() {
    const loadingDiv = document.getElementById('backtest-loading');
    if (loadingDiv) loadingDiv.classList.add('hidden');
  }

  showSuccess(message) { this.showMessage(message, 'success'); }
  showError(message) { this.showMessage(message, 'error'); }

  showMessage(message, type = 'info') {
    const messageDiv = document.getElementById('backtest-message');
    if (!messageDiv) return;
    const bgColor = type === 'success' ? 'bg-green-50 text-green-800' : type === 'error' ? 'bg-red-50 text-red-800' : 'bg-blue-50 text-blue-800';
    messageDiv.innerHTML = `<div class="${bgColor} p-4 rounded-lg mb-4">${message}</div>`;
    setTimeout(() => { messageDiv.innerHTML = ''; }, 5000);
  }
}

const backtestingUI = new BacktestingUI();
