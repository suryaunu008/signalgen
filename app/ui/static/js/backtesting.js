/**
 * Backtesting UI Module
 * 
 * Handles all UI interactions for backtesting functionality including:
 * - Backtest configuration and submission
 * - Results display and visualization
 * - Backtest history management
 */

class BacktestingUI {
  constructor() {
    this.currentResults = null;
    this.backtestRuns = [];
  }

  /**
   * Initialize backtesting UI
   */
  async init() {
    console.log('Initializing Backtesting UI...');
    this.setupEventListeners();
    await this.loadBacktestHistory();
    await this.loadRules();
  }

  /**
   * Setup event listeners for backtesting controls
   */
  setupEventListeners() {
    // Run backtest button
    const runButton = document.getElementById('run-backtest-btn');
    if (runButton) {
      runButton.addEventListener('click', () => this.runBacktest());
    }

    // Data source change
    const dataSourceSelect = document.getElementById('backtest-data-source');
    if (dataSourceSelect) {
      dataSourceSelect.addEventListener('change', (e) => this.onDataSourceChange(e.target.value));
    }

    // Backtest mode change
    const modeSelect = document.getElementById('backtest-mode');
    if (modeSelect) {
      modeSelect.addEventListener('change', (e) => this.onModeChange(e.target.value));
    }
  }

  /**
   * Load list of trading rules
   */
  async loadRules() {
    try {
      const response = await fetch('/api/rules');
      const rules = await response.json();
      
      const ruleSelect = document.getElementById('backtest-rule-select');
      if (ruleSelect && Array.isArray(rules)) {
        ruleSelect.innerHTML = '<option value="">Select rule...</option>';
        rules.forEach(rule => {
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

  /**
   * Run backtest with current configuration
   */
  async runBacktest() {
    try {
      // Get form values
      const name = document.getElementById('backtest-name')?.value?.trim();
      const mode = document.getElementById('backtest-mode')?.value;
      const ruleId = document.getElementById('backtest-rule-select')?.value;
      const symbols = document.getElementById('backtest-symbols')?.value?.trim().split(',').map(s => s.trim());
      const timeframe = document.getElementById('backtest-timeframe')?.value;
      const startDate = document.getElementById('backtest-start-date')?.value;
      const endDate = document.getElementById('backtest-end-date')?.value;
      const dataSource = document.getElementById('backtest-data-source')?.value;

      // Validate inputs
      if (!name) {
        this.showError('Please enter a backtest name');
        return;
      }
      if (!mode) {
        this.showError('Please select backtest mode');
        return;
      }
      if (!ruleId) {
        this.showError('Please select a rule');
        return;
      }
      if (!symbols || symbols.length === 0) {
        this.showError('Please enter at least one symbol');
        return;
      }
      if (!startDate || !endDate) {
        this.showError('Please select date range');
        return;
      }

      // Show loading
      this.showLoading('Running backtest...');

      // Submit backtest
      const response = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          mode,
          rule_id: parseInt(ruleId),
          symbols,
          timeframe,
          start_date: startDate,
          end_date: endDate,
          data_source: dataSource
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Backtest failed');
      }

      const result = await response.json();
      
      this.hideLoading();
      this.showSuccess(`Backtest completed! ${result.total_signals} signals generated`);
      
      // Load and display results
      await this.loadBacktestResults(result.backtest_run_id);
      await this.loadBacktestHistory();

    } catch (error) {
      this.hideLoading();
      this.showError(`Backtest failed: ${error.message}`);
      console.error('Backtest error:', error);
    }
  }

  /**
   * Load backtest results
   */
  async loadBacktestResults(runId) {
    try {
      const response = await fetch(`/api/backtest/runs/${runId}`);
      const data = await response.json();
      
      this.currentResults = data;
      this.displayResults(data);
    } catch (error) {
      console.error('Error loading backtest results:', error);
      this.showError('Failed to load backtest results');
    }
  }

  /**
   * Display backtest results
   */
  displayResults(results) {
    const resultsContainer = document.getElementById('backtest-results-container');
    if (!resultsContainer) return;

    resultsContainer.innerHTML = `
      <div class="bg-white rounded-lg shadow-md p-6 mb-4">
        <h3 class="text-lg font-semibold mb-4">Backtest: ${results.name}</h3>
        
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-blue-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Total Signals</div>
            <div class="text-2xl font-bold text-blue-600">${results.total_signals}</div>
          </div>
          <div class="bg-green-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Symbols Tested</div>
            <div class="text-2xl font-bold text-green-600">${results.symbols.length}</div>
          </div>
          <div class="bg-purple-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Timeframe</div>
            <div class="text-2xl font-bold text-purple-600">${results.timeframe}</div>
          </div>
          <div class="bg-orange-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Mode</div>
            <div class="text-2xl font-bold text-orange-600">${results.mode}</div>
          </div>
        </div>

        <div class="mb-4">
          <h4 class="font-semibold mb-2">Date Range</h4>
          <p class="text-sm text-gray-600">${results.start_date} to ${results.end_date}</p>
        </div>

        <div class="mb-4">
          <h4 class="font-semibold mb-2">Symbols</h4>
          <div class="flex flex-wrap gap-2">
            ${results.symbols.map(s => `<span class="px-2 py-1 bg-gray-200 rounded text-sm">${s}</span>`).join('')}
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-semibold mb-4">Signals (${results.signals.length})</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              ${results.signals.map(signal => `
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-sm">${new Date(signal.timestamp).toLocaleString()}</td>
                  <td class="px-4 py-3 text-sm font-medium">${signal.symbol}</td>
                  <td class="px-4 py-3 text-sm">
                    <span class="px-2 py-1 rounded text-white ${signal.signal_type === 'BUY' ? 'bg-green-500' : 'bg-red-500'}">
                      ${signal.signal_type}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm">$${signal.price.toFixed(2)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  /**
   * Load backtest history
   */
  async loadBacktestHistory() {
    try {
      const response = await fetch('/api/backtest/runs');
      const data = await response.json();
      
      this.backtestRuns = data.runs;
      this.displayHistory(data.runs);
    } catch (error) {
      console.error('Error loading backtest history:', error);
    }
  }

  /**
   * Display backtest history
   */
  displayHistory(runs) {
    const historyContainer = document.getElementById('backtest-history-list');
    if (!historyContainer) return;

    if (runs.length === 0) {
      historyContainer.innerHTML = '<p class="text-gray-500 text-sm">No backtest runs yet</p>';
      return;
    }

    historyContainer.innerHTML = runs.map(run => `
      <div class="bg-white border border-gray-200 rounded-lg p-4 mb-3 hover:shadow-md transition-shadow">
        <div class="flex justify-between items-start">
          <div>
            <h4 class="font-semibold">${run.name}</h4>
            <p class="text-sm text-gray-600">${new Date(run.created_at).toLocaleString()}</p>
            <div class="flex gap-2 mt-2">
              <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">${run.mode}</span>
              <span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs">${run.timeframe}</span>
              <span class="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">${run.total_signals} signals</span>
            </div>
          </div>
          <div class="flex gap-2">
            <button onclick="backtestingUI.loadBacktestResults(${run.id})" 
                    class="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600">
              View
            </button>
            <button onclick="backtestingUI.deleteBacktest(${run.id})" 
                    class="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600">
              Delete
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  /**
   * Delete backtest
   */
  async deleteBacktest(runId) {
    if (!confirm('Are you sure you want to delete this backtest?')) {
      return;
    }

    try {
      const response = await fetch(`/api/backtest/runs/${runId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete backtest');
      }

      this.showSuccess('Backtest deleted successfully');
      await this.loadBacktestHistory();
      
      // Clear results if this was the current one
      if (this.currentResults && this.currentResults.id === runId) {
        document.getElementById('backtest-results-container').innerHTML = '';
        this.currentResults = null;
      }
    } catch (error) {
      this.showError(`Failed to delete backtest: ${error.message}`);
      console.error('Delete error:', error);
    }
  }

  /**
   * Handle data source change
   */
  onDataSourceChange(dataSource) {
    // Update timeframe options based on data source
    const timeframeSelect = document.getElementById('backtest-timeframe');
    if (!timeframeSelect) return;

    // Both support same timeframes for now
    console.log(`Data source changed to: ${dataSource}`);
  }

  /**
   * Handle mode change
   */
  onModeChange(mode) {
    console.log(`Backtest mode changed to: ${mode}`);
    
    // Update recommended timeframes based on mode
    const recommendedNote = document.getElementById('timeframe-recommendation');
    if (recommendedNote) {
      if (mode === 'scalping') {
        recommendedNote.textContent = 'Recommended: 1m, 5m for scalping';
      } else if (mode === 'swing') {
        recommendedNote.textContent = 'Recommended: 1h, 4h, 1d for swing trading';
      }
    }
  }

  /**
   * Show loading indicator
   */
  showLoading(message) {
    const loadingDiv = document.getElementById('backtest-loading');
    if (loadingDiv) {
      loadingDiv.innerHTML = `
        <div class="flex items-center justify-center p-4 bg-blue-50 rounded-lg">
          <i class="fas fa-spinner fa-spin mr-2"></i>
          <span>${message}</span>
        </div>
      `;
      loadingDiv.classList.remove('hidden');
    }
  }

  /**
   * Hide loading indicator
   */
  hideLoading() {
    const loadingDiv = document.getElementById('backtest-loading');
    if (loadingDiv) {
      loadingDiv.classList.add('hidden');
    }
  }

  /**
   * Show success message
   */
  showSuccess(message) {
    this.showMessage(message, 'success');
  }

  /**
   * Show error message
   */
  showError(message) {
    this.showMessage(message, 'error');
  }

  /**
   * Show message
   */
  showMessage(message, type = 'info') {
    const messageDiv = document.getElementById('backtest-message');
    if (messageDiv) {
      const bgColor = type === 'success' ? 'bg-green-50 text-green-800' : 
                      type === 'error' ? 'bg-red-50 text-red-800' : 
                      'bg-blue-50 text-blue-800';
      
      messageDiv.innerHTML = `
        <div class="${bgColor} p-4 rounded-lg mb-4">
          ${message}
        </div>
      `;
      
      // Auto-hide after 5 seconds
      setTimeout(() => {
        messageDiv.innerHTML = '';
      }, 5000);
    }
  }
}

// Create global instance
const backtestingUI = new BacktestingUI();
