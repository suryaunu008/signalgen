class BacktestingUI {
  constructor() {
    this.currentResults = null;
    this.plBasis = 'close';
  }

  async init() {
    this.setupEventListeners();
    this.renderTimezoneLabel();
    await this.loadRules();
    this.onModeChange(document.getElementById('backtest-mode')?.value || 'rule');
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

    const exportButton = document.getElementById('export-backtest-csv-btn');
    if (exportButton) exportButton.addEventListener('click', () => this.exportCsv());

    const modeSelect = document.getElementById('backtest-mode');
    if (modeSelect) modeSelect.addEventListener('change', (e) => this.onModeChange(e.target.value));
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

  async loadRules() {
    try {
      const response = await fetch('/api/rules');
      const rules = await response.json();
      const select = document.getElementById('backtest-rule-select');
      if (!select || !Array.isArray(rules)) return;

      select.innerHTML = '<option value="">Select rule...</option>';
      rules.forEach((rule) => {
        const option = document.createElement('option');
        option.value = rule.id;
        option.textContent = `${rule.name}${rule.is_system ? ' (System)' : ''}`;
        select.appendChild(option);
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
      entries.push({ symbol: parts[0], entry_time: this.localInputToIso(parts[1]) });
    }
    return entries;
  }

  localInputToIso(value) {
    // Accepts datetime-local shape (YYYY-MM-DDTHH:mm) and converts from device local time.
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) {
      throw new Error(`Invalid datetime value: ${value}`);
    }
    return dt.toISOString();
  }

  async runBacktesting() {
    try {
      const mode = document.getElementById('backtest-mode')?.value;
      const timeframe = document.getElementById('backtest-timeframe')?.value;
      const nSteps = parseInt(document.getElementById('backtest-n-steps')?.value || '0', 10);
      const dataSource = document.getElementById('backtest-data-source')?.value;
      const plBasis = document.getElementById('backtest-pl-basis')?.value || 'close';

      if (!mode || !timeframe || !dataSource || Number.isNaN(nSteps) || nSteps < 1) {
        this.showError('Invalid input');
        return;
      }
      this.plBasis = plBasis;

      const payload = {
        mode,
        timeframe,
        n_steps: nSteps,
        data_source: dataSource
      };

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
      result.pl_basis = this.plBasis;
      this.currentResults = result;
      this.renderResults(result);
      this.hideLoading();
      this.showSuccess(`Completed. Rows: ${result.row_count}`);
    } catch (error) {
      this.hideLoading();
      this.showError(`Backtesting failed: ${error.message}`);
      console.error(error);
    }
  }

  renderResults(result) {
    const container = document.getElementById('backtest-results-container');
    if (!container) return;

    const headers = ['Ticker', 'Entry Time', 'Entry Price'];
    for (let i = 1; i <= result.n_steps; i += 1) {
      headers.push(`T+${i}`);
    }

    const thead = `<tr>${headers.map((h, idx) => `<th class="${idx < 3 ? 'sticky z-20 bg-white' : 'bg-slate-100'} px-3 py-3 text-left text-xs font-semibold tracking-wide text-slate-700 uppercase border-b border-slate-200 ${idx === 0 ? 'left-0' : idx === 1 ? 'left-[120px]' : idx === 2 ? 'left-[320px]' : ''}">${h}</th>`).join('')}</tr>`;

    const rowsHtml = (result.rows || []).map((row) => {
      const cells = [
        `<span class="font-semibold text-slate-900">${row.symbol}</span>`,
        `<span class="text-slate-700">${new Date(row.entry_time).toLocaleString()}</span>`,
        `<span class="font-semibold text-slate-900">${Number(row.entry_price).toFixed(4)}</span>`
      ];

      const entryPriceNum = Number(row.entry_price);
      for (let i = 1; i <= result.n_steps; i += 1) {
        const step = row.steps?.[`T+${i}`] || null;
        if (!step) {
          cells.push('-');
        } else {
          const priceField = result.pl_basis || 'close';
          const basisNum = Number(step[priceField]);
          const pl = basisNum - entryPriceNum;
          const plPct = entryPriceNum === 0 ? 0 : (pl / entryPriceNum) * 100;
          const plClass = pl > 0
            ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
            : pl < 0
              ? 'text-rose-700 bg-rose-50 border-rose-200'
              : 'text-slate-700 bg-slate-100 border-slate-300';
          const sign = pl > 0 ? '+' : '';
          cells.push(
            `<div class="min-w-[220px] rounded-lg border border-slate-200 bg-white p-2">
              <div class="mb-1 text-[11px] font-semibold text-slate-500">T+${i}</div>
              <div class="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-slate-600">
                <span>O <b class="text-slate-800">${Number(step.open).toFixed(4)}</b></span>
                <span>H <b class="text-slate-800">${Number(step.high).toFixed(4)}</b></span>
                <span>L <b class="text-slate-800">${Number(step.low).toFixed(4)}</b></span>
                <span>C <b class="text-slate-800">${Number(step.close).toFixed(4)}</b></span>
              </div>
              <div class="mt-2 text-[11px] text-slate-500">Basis: <b class="text-slate-700 uppercase">${priceField}</b> (${basisNum.toFixed(4)})</div>
              <div class="mt-2 rounded-md border px-2 py-1 text-xs font-semibold ${plClass}">
                P/L ${sign}${pl.toFixed(4)} (${sign}${plPct.toFixed(2)}%)
              </div>
            </div>`
          );
        }
      }

      return `<tr class="odd:bg-white even:bg-slate-50 hover:bg-blue-50/40">${cells.map((v, idx) => `<td class="${idx < 3 ? 'sticky z-10 bg-white' : ''} px-3 py-2 align-top text-sm border-b border-slate-200 ${idx === 0 ? 'left-0 min-w-[120px]' : idx === 1 ? 'left-[120px] min-w-[200px]' : idx === 2 ? 'left-[320px] min-w-[120px]' : ''}">${v}</td>`).join('')}</tr>`;
    }).join('');

    container.innerHTML = `
      <section class="bg-gradient-to-b from-slate-50 to-white rounded-xl border border-slate-200 shadow-sm p-5">
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <h3 class="text-lg font-semibold text-slate-900">Result</h3>
          <span class="rounded-full bg-blue-100 text-blue-800 px-2.5 py-1 text-xs font-semibold">${result.row_count} rows</span>
          <span class="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 text-xs font-semibold">Mode ${result.mode}</span>
          <span class="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 text-xs font-semibold">T ${result.timeframe}</span>
          <span class="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 text-xs font-semibold">n ${result.n_steps}</span>
          <span class="rounded-full bg-amber-100 text-amber-800 px-2.5 py-1 text-xs font-semibold">P/L basis ${(result.pl_basis || 'close').toUpperCase()}</span>
        </div>
        <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table class="min-w-full bg-white">
            <thead>${thead}</thead>
            <tbody>${rowsHtml || '<tr><td class="px-3 py-4 text-sm text-gray-500" colspan="999">No rows</td></tr>'}</tbody>
          </table>
        </div>
      </section>
    `;
  }

  exportCsv() {
    if (!this.currentResults || !Array.isArray(this.currentResults.rows)) {
      this.showError('No results available to export');
      return;
    }

    const result = this.currentResults;
    const headers = ['Ticker', 'Entry Time', 'Entry Price'];
    for (let i = 1; i <= result.n_steps; i += 1) {
      headers.push(`T+${i} OHLC`, `T+${i} P/L`, `T+${i} P/L%`);
    }

    const lines = [headers.join(',')];

    for (const row of result.rows) {
      const line = [row.symbol, row.entry_time, row.entry_price];
      const entryPriceNum = Number(row.entry_price);
      for (let i = 1; i <= result.n_steps; i += 1) {
        const step = row.steps?.[`T+${i}`] || null;
        if (!step) {
          line.push('', '', '');
        } else {
          const priceField = result.pl_basis || 'close';
          const basisNum = Number(step[priceField]);
          const pl = basisNum - entryPriceNum;
          const plPct = entryPriceNum === 0 ? 0 : (pl / entryPriceNum) * 100;
          line.push(
            `"O:${step.open} H:${step.high} L:${step.low} C:${step.close} BASIS(${priceField.toUpperCase()}):${basisNum}"`,
            pl.toFixed(6),
            plPct.toFixed(4)
          );
        }
      }
      lines.push(line.join(','));
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
