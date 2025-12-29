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
  }

  /**
   * Initialize swing trading UI
   */
  async init() {
    console.log('Initializing Swing Trading UI...');
    this.setupEventListeners();
    await this.loadTickerUniverses();
    await this.loadRules();
  }

  /**
   * Setup event listeners
   */
  setupEventListeners() {
    // Run screening button
    const screenButton = document.getElementById('run-screening-btn');
    if (screenButton) {
      screenButton.addEventListener('click', () => this.runScreening());
    }

    // Create universe button
    const createUniverseBtn = document.getElementById('create-universe-btn');
    if (createUniverseBtn) {
      createUniverseBtn.addEventListener('click', () => this.showCreateUniverseForm());
    }

    // Save universe button
    const saveUniverseBtn = document.getElementById('save-universe-btn');
    if (saveUniverseBtn) {
      saveUniverseBtn.addEventListener('click', () => this.saveUniverse());
    }

    // Cancel universe button
    const cancelUniverseBtn = document.getElementById('cancel-universe-btn');
    if (cancelUniverseBtn) {
      cancelUniverseBtn.addEventListener('click', () => this.hideUniverseForm());
    }
  }

  /**
   * Load trading rules
   */
  async loadRules() {
    try {
      const response = await fetch('/api/rules');
      const rules = await response.json();
      
      const ruleSelect = document.getElementById('swing-rule-select');
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
   * Load ticker universes
   */
  async loadTickerUniverses() {
    try {
      const response = await fetch('/api/swing/universes');
      const data = await response.json();
      
      this.universes = data.universes;
      this.displayUniverseSelector(data.universes);
      this.displayUniverseList(data.universes);
    } catch (error) {
      console.error('Error loading ticker universes:', error);
      this.showError('Failed to load ticker universes');
    }
  }

  /**
   * Display universe selector
   */
  displayUniverseSelector(universes) {
    const universeSelect = document.getElementById('swing-universe-select');
    if (!universeSelect) return;

    universeSelect.innerHTML = '<option value="">Select ticker universe...</option>';
    universes.forEach(universe => {
      const option = document.createElement('option');
      option.value = universe.id;
      option.textContent = `${universe.name} (${universe.tickers.length} tickers)`;
      universeSelect.appendChild(option);
    });
  }

  /**
   * Display universe list for management
   */
  displayUniverseList(universes) {
    const universeList = document.getElementById('universe-list');
    if (!universeList) return;

    if (universes.length === 0) {
      universeList.innerHTML = '<p class="text-gray-500 text-sm">No ticker universes yet</p>';
      return;
    }

    universeList.innerHTML = universes.map(universe => `
      <div class="bg-white border border-gray-200 rounded-lg p-4 mb-3 hover:shadow-md transition-shadow">
        <div class="flex justify-between items-start">
          <div class="flex-1">
            <h4 class="font-semibold">${universe.name}</h4>
            <p class="text-sm text-gray-600">${universe.description || 'No description'}</p>
            <div class="mt-2">
              <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                ${universe.tickers.length} tickers
              </span>
            </div>
            <div class="mt-2 text-sm text-gray-600 max-h-20 overflow-y-auto">
              ${universe.tickers.length > 0 ? universe.tickers.join(', ') : 'No tickers'}
            </div>
          </div>
          <div class="flex gap-2 ml-4">
            <button onclick="swingTradingUI.editUniverse(${universe.id})" 
                    class="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600">
              Edit
            </button>
            <button onclick="swingTradingUI.deleteUniverse(${universe.id})" 
                    class="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                    ${universe.name === 'Custom' ? 'disabled' : ''}>
              Delete
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  /**
   * Run swing screening
   */
  async runScreening() {
    try {
      const ruleId = document.getElementById('swing-rule-select')?.value;
      const universeId = document.getElementById('swing-universe-select')?.value;
      const timeframe = document.getElementById('swing-timeframe')?.value || '1d';
      const lookbackDays = parseInt(document.getElementById('swing-lookback')?.value) || 30;

      // Validate
      if (!ruleId) {
        this.showError('Please select a rule');
        return;
      }
      if (!universeId) {
        this.showError('Please select a ticker universe');
        return;
      }

      // Show loading
      this.showLoading('Running swing screening...');

      // Run screening
      const response = await fetch('/api/swing/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_id: parseInt(ruleId),
          ticker_universe_id: parseInt(universeId),
          timeframe,
          lookback_days: lookbackDays
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Screening failed');
      }

      const result = await response.json();
      
      this.hideLoading();
      this.showSuccess(`Screening completed! ${result.summary.signals_found} signals found`);
      
      this.currentResults = result;
      this.displayResults(result);

    } catch (error) {
      this.hideLoading();
      this.showError(`Screening failed: ${error.message}`);
      console.error('Screening error:', error);
    }
  }

  /**
   * Display screening results
   */
  displayResults(result) {
    const resultsContainer = document.getElementById('swing-results-container');
    if (!resultsContainer) return;

    const { results, summary } = result;

    resultsContainer.innerHTML = `
      <div class="bg-white rounded-lg shadow-md p-6 mb-4">
        <h3 class="text-lg font-semibold mb-4">Screening Results</h3>
        
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-blue-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Total Tickers</div>
            <div class="text-2xl font-bold text-blue-600">${summary.total_tickers}</div>
          </div>
          <div class="bg-green-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Signals Found</div>
            <div class="text-2xl font-bold text-green-600">${summary.signals_found}</div>
          </div>
          <div class="bg-purple-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Successful</div>
            <div class="text-2xl font-bold text-purple-600">${summary.successful}</div>
          </div>
          <div class="bg-red-50 rounded-lg p-4">
            <div class="text-sm text-gray-600">Errors</div>
            <div class="text-2xl font-bold text-red-600">${summary.errors}</div>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-md p-6">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold">Ticker Results</h3>
          <div class="flex gap-2">
            <button onclick="swingTradingUI.filterResults('all')" 
                    class="px-3 py-1 bg-gray-200 rounded text-sm hover:bg-gray-300">
              All
            </button>
            <button onclick="swingTradingUI.filterResults('signals')" 
                    class="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600">
              Signals Only
            </button>
            <button onclick="swingTradingUI.filterResults('errors')" 
                    class="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600">
              Errors Only
            </button>
          </div>
        </div>
        
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200" id="swing-results-table">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Signal</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              ${results.map(r => `
                <tr class="hover:bg-gray-50 ${r.status === 'error' ? 'result-error' : ''} ${r.signal ? 'result-signal' : ''}">
                  <td class="px-4 py-3 text-sm font-medium">${r.symbol}</td>
                  <td class="px-4 py-3 text-sm">
                    ${r.signal ? `
                      <span class="px-2 py-1 rounded text-white ${r.signal === 'BUY' ? 'bg-green-500' : 'bg-red-500'}">
                        ${r.signal}
                      </span>
                    ` : '<span class="text-gray-400">-</span>'}
                  </td>
                  <td class="px-4 py-3 text-sm">
                    ${r.price ? `$${r.price.toFixed(2)}` : '-'}
                  </td>
                  <td class="px-4 py-3 text-sm">
                    ${r.timestamp ? new Date(r.timestamp).toLocaleString() : '-'}
                  </td>
                  <td class="px-4 py-3 text-sm">
                    ${r.status === 'success' ? 
                      '<span class="text-green-600">✓</span>' : 
                      `<span class="text-red-600" title="${r.error_message}">✗</span>`}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  /**
   * Filter results display
   */
  filterResults(filter) {
    const rows = document.querySelectorAll('#swing-results-table tbody tr');
    rows.forEach(row => {
      if (filter === 'all') {
        row.style.display = '';
      } else if (filter === 'signals') {
        row.style.display = row.classList.contains('result-signal') ? '' : 'none';
      } else if (filter === 'errors') {
        row.style.display = row.classList.contains('result-error') ? '' : 'none';
      }
    });
  }

  /**
   * Show create universe form
   */
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

  /**
   * Edit universe
   */
  async editUniverse(universeId) {
    const universe = this.universes.find(u => u.id === universeId);
    if (!universe) return;

    const formContainer = document.getElementById('universe-form-container');
    if (formContainer) {
      document.getElementById('universe-form-title').textContent = 'Edit Ticker Universe';
      document.getElementById('universe-id').value = universe.id;
      document.getElementById('universe-name').value = universe.name;
      document.getElementById('universe-tickers').value = universe.tickers.join(', ');
      document.getElementById('universe-description').value = universe.description || '';
      formContainer.classList.remove('hidden');
    }
  }

  /**
   * Save universe (create or update)
   */
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

      const tickers = tickersStr ? tickersStr.split(',').map(t => t.trim()).filter(t => t) : [];

      const payload = { name, tickers, description };

      let response;
      if (id) {
        // Update
        response = await fetch(`/api/swing/universes/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        // Create
        response = await fetch('/api/swing/universes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (!response.ok) {
        const error = await response.json();
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

  /**
   * Delete universe
   */
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

  /**
   * Hide universe form
   */
  hideUniverseForm() {
    const formContainer = document.getElementById('universe-form-container');
    if (formContainer) {
      formContainer.classList.add('hidden');
    }
  }

  /**
   * Show loading indicator
   */
  showLoading(message) {
    const loadingDiv = document.getElementById('swing-loading');
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
    const loadingDiv = document.getElementById('swing-loading');
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
    const messageDiv = document.getElementById('swing-message');
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
const swingTradingUI = new SwingTradingUI();
