/**
 * SignalGen Main Application
 *
 * This module initializes and coordinates all UI components, handles user interactions,
 * and manages the application state. It serves as the main controller for the frontend.
 */

class SignalGenApp {
  constructor() {
    this.engineRunning = false;
    this.currentWatchlist = null;
    this.currentRule = null;
    this.watchlistSymbols = [];
    this.signals = [];
    this.maxSignals = 50; // Keep only last 50 signals in UI
    this.statusPollInterval = null; // For polling engine status
    this.priceData = {}; // Store current price data for all symbols

    // Bind methods to maintain context
    this.init = this.init.bind(this);
    this.loadInitialData = this.loadInitialData.bind(this);
    this.setupEventListeners = this.setupEventListeners.bind(this);
    this.setupWebSocketListeners = this.setupWebSocketListeners.bind(this);
    this.pollEngineStatus = this.pollEngineStatus.bind(this);

    // Component methods
    this.updateEngineStatus = this.updateEngineStatus.bind(this);
    this.updateRulesList = this.updateRulesList.bind(this);
    this.updateWatchlists = this.updateWatchlists.bind(this);
    this.addSignal = this.addSignal.bind(this);
    this.deleteSignal = this.deleteSignal.bind(this);
    this.showSignalDetail = this.showSignalDetail.bind(this);
    this.closeSignalModal = this.closeSignalModal.bind(this);
    this.showToast = this.showToast.bind(this);
    this.showLoading = this.showLoading.bind(this);
    this.hideLoading = this.hideLoading.bind(this);

    // Price table methods
    this.initializePriceTable = this.initializePriceTable.bind(this);
    this.updatePriceTable = this.updatePriceTable.bind(this);
  }

  /**
   * Initialize the application
   */
  async init() {
    try {
      console.log("Initializing SignalGen application...");

      // Show loading state
      this.showLoading();

      // Setup event listeners
      this.setupEventListeners();

      // Setup WebSocket listeners
      this.setupWebSocketListeners();

      // Initialize price table
      this.initializePriceTable();

      // Connect to WebSocket
      WS.connect();

      // Load initial data
      await this.loadInitialData();

      // Hide loading state
      this.hideLoading();

      // Attach event listeners to the initial condition row
      // This is necessary because the initial condition row in the HTML template
      // doesn't get its event listeners attached during application initialization
      const initialConditionRow = document.querySelector(".condition-row");
      if (initialConditionRow) {
        this.attachConditionRowListeners(initialConditionRow);
      }

      console.log("SignalGen application initialized successfully");
      this.showToast("Application loaded successfully", "success");
    } catch (error) {
      console.error("Failed to initialize application:", error);
      this.hideLoading();
      this.showToast("Failed to initialize application", "error");
    }
  }

  /**
   * Load initial data from API
   */
  async loadInitialData() {
    try {
      // Load system status
      const status = await API.getSystemStatus();
      this.updateEngineStatus(status.engine);

      // Load rules
      const rules = await API.getAllRules();
      this.updateRulesList(rules);
      this.populateRuleSelect(rules);

      // Load watchlists
      const watchlists = await API.getAllWatchlists();
      this.updateWatchlists(watchlists);
      this.populateWatchlistSelect(watchlists);

      // Load recent signals (sorted from newest to oldest)
      const signals = await API.getSignals(20);
      // Reverse to show newest first, and load silently without toast
      signals.reverse().forEach((signal) => this.addSignal(signal, true));

      // Load settings
      const settings = await API.getAllSettings();
      this.populateSettingsForm(settings);
      
      // Load and set current timeframe
      await this.loadTimeframe();
    } catch (error) {
      console.error("Failed to load initial data:", error);
      throw error;
    }
  }

  /**
   * Setup DOM event listeners
   */
  setupEventListeners() {
    // Engine controls
    document
      .getElementById("start-engine")
      .addEventListener("click", () => this.startEngine());
    document
      .getElementById("stop-engine")
      .addEventListener("click", () => this.stopEngine());

    // Timeframe selector
    document
      .getElementById("timeframe-select")
      .addEventListener("change", (e) => this.handleTimeframeChange(e));

    // Rule builder
    document
      .getElementById("rule-builder-form")
      .addEventListener("submit", (e) => this.handleRuleSubmit(e));
    document
      .getElementById("clear-rule-form")
      .addEventListener("click", () => this.clearRuleForm());
    document
      .getElementById("add-condition")
      .addEventListener("click", () => this.addConditionRow());

    // Watchlist manager
    document
      .getElementById("watchlist-form")
      .addEventListener("submit", (e) => this.handleWatchlistSubmit(e));
    document
      .getElementById("add-symbol")
      .addEventListener("click", () => this.addSymbolToWatchlist());

    // Settings
    document
      .getElementById("save-settings")
      .addEventListener("click", () => this.saveSettings());

    // Delegate event listeners for dynamic content
    document.addEventListener("click", (e) => {
      if (e.target.closest(".remove-condition")) {
        this.removeConditionRow(e.target.closest(".condition-row"));
      }
      if (e.target.closest(".view-rule-details")) {
        const ruleId = parseInt(
          e.target.closest(".view-rule-details").dataset.ruleId
        );
        this.viewRuleDetails(ruleId);
      }
      if (e.target.closest(".delete-rule")) {
        const ruleId = parseInt(
          e.target.closest(".delete-rule").dataset.ruleId
        );
        this.deleteRule(ruleId);
      }
      if (e.target.closest(".delete-watchlist")) {
        const watchlistId = parseInt(
          e.target.closest(".delete-watchlist").dataset.watchlistId
        );
        this.deleteWatchlist(watchlistId);
      }
      if (e.target.closest(".remove-symbol")) {
        const symbol = e.target.closest(".remove-symbol").dataset.symbol;
        this.removeSymbolFromWatchlist(symbol);
      }
    });

    // Modal close button event listener
    document
      .getElementById("close-rule-modal")
      .addEventListener("click", () => {
        this.closeRuleModal();
      });

    // Close rule modal when clicking outside
    document
      .getElementById("rule-detail-modal")
      .addEventListener("click", (e) => {
        if (e.target.id === "rule-detail-modal") {
          this.closeRuleModal();
        }
      });

    // Signal modal close button event listener
    document
      .getElementById("close-signal-modal")
      .addEventListener("click", () => {
        this.closeSignalModal();
      });

    // Close signal modal when clicking outside
    document
      .getElementById("signal-detail-modal")
      .addEventListener("click", (e) => {
        if (e.target.id === "signal-detail-modal") {
          this.closeSignalModal();
        }
      });
  }

  /**
   * Setup WebSocket event listeners
   */
  setupWebSocketListeners() {
    WS.on("connect", () => {
      console.log("Connected to WebSocket server");
      this.updateConnectionStatus(true);

      // Request current engine status when connected
      this.pollEngineStatus();
    });

    WS.on("disconnect", () => {
      console.log("Disconnected from WebSocket server");
      this.updateConnectionStatus(false);
    });

    WS.on("signal", (signal) => {
      this.addSignal(signal);
    });

    WS.on("engine_status", (statusData) => {
      console.log("Received engine_status via WebSocket:", statusData);
      // Extract status from wrapper if present
      const status = statusData.data || statusData;
      this.updateEngineStatus(status);
    });

    WS.on("rule_update", (rule) => {
      this.updateRuleInList(rule);
    });

    WS.on("watchlist_update", (watchlist) => {
      this.updateWatchlistInList(watchlist);
    });

    WS.on("price_update", (priceData) => {
      console.log("DEBUG: App.js received price_update:", priceData);
      console.log("DEBUG: Price data type:", typeof priceData);
      console.log("DEBUG: Price data keys:", Object.keys(priceData || {}));
      this.updatePriceTable(priceData);
    });

    WS.on("error", (error) => {
      this.showToast(error.message || "An error occurred", "error");
    });
  }

  /**
   * Start polling engine status
   */
  startStatusPolling() {
    // Clear any existing interval
    if (this.statusPollInterval) {
      clearInterval(this.statusPollInterval);
    }

    // Poll every 2 seconds
    this.statusPollInterval = setInterval(() => {
      this.pollEngineStatus();
    }, 2000);

    console.log("Started engine status polling");
  }

  /**
   * Stop polling engine status
   */
  stopStatusPolling() {
    if (this.statusPollInterval) {
      clearInterval(this.statusPollInterval);
      this.statusPollInterval = null;
      console.log("Stopped engine status polling");
    }
  }

  /**
   * Poll engine status from API
   */
  async pollEngineStatus() {
    try {
      const status = await API.getEngineStatus();
      console.log("Polled engine status:", status); // Debug log
      this.updateEngineStatus(status);
    } catch (error) {
      console.error("Error polling engine status:", error); // Debug log
      // Silently fail - don't spam console/UI on polling errors
    }
  }

  /**
   * Update connection status indicators
   */
  updateConnectionStatus(connected) {
    const wsStatus = document.getElementById("ws-status");
    if (wsStatus) {
      const indicator = wsStatus.querySelector(".status-indicator");
      const text = wsStatus.querySelector(".status-text");

      if (connected) {
        indicator.className =
          "status-indicator w-3 h-3 bg-green-500 rounded-full animate-pulse";
        text.textContent = "Connected";
      } else {
        indicator.className =
          "status-indicator w-3 h-3 bg-red-500 rounded-full";
        text.textContent = "Disconnected";
      }
    }
  }

  /**
   * Update engine status display
   */
  updateEngineStatus(status) {
    console.log("DEBUG: updateEngineStatus called with:", status);

    const wasRunning = this.engineRunning;
    this.engineRunning = status.is_running;

    // Update engine status indicator
    const engineStatus = document.getElementById("engine-status");
    const indicator = engineStatus.querySelector("div:first-child");
    const text = engineStatus.querySelector("span");

    if (status.is_running) {
      indicator.className = "w-3 h-3 bg-green-500 rounded-full animate-pulse";
      text.textContent = "Engine: Running";
    } else {
      indicator.className = "w-3 h-3 bg-red-500 rounded-full";
      text.textContent = "Engine: Stopped";
    }

    // Update IBKR status - check both ibkr_connected and is_connected
    const ibkrStatus = document.getElementById("ibkr-status");
    const ibkrIndicator = ibkrStatus.querySelector("div:first-child");
    const ibkrText = ibkrStatus.querySelector("span");

    const ibkrConnected =
      status.ibkr_connected !== undefined
        ? status.ibkr_connected
        : status.is_connected;

    console.log("DEBUG: IBKR connected status:", ibkrConnected);

    if (ibkrConnected) {
      ibkrIndicator.className =
        "w-3 h-3 bg-green-500 rounded-full animate-pulse";
      ibkrText.textContent = "IBKR: Connected";
    } else {
      ibkrIndicator.className = "w-3 h-3 bg-red-500 rounded-full ";
      ibkrText.textContent = "IBKR: Disconnected";
    }

    // Update client ID display if connected
    const clientIdField = document.getElementById("ib-client-id");
    if (
      clientIdField &&
      status.connection_details &&
      status.connection_details.client_id
    ) {
      clientIdField.value = `Client ID: ${status.connection_details.client_id}`;
    } else if (clientIdField) {
      clientIdField.value = "Auto (random)";
    }

    // Update control buttons
    const startBtn = document.getElementById("start-engine");
    const stopBtn = document.getElementById("stop-engine");
    const timeframeSelect = document.getElementById("timeframe-select");
    const watchlistSelect = document.getElementById("watchlist-select");
    const ruleSelect = document.getElementById("rule-select");

    startBtn.disabled = status.is_running;
    stopBtn.disabled = !status.is_running;
    
    // Disable timeframe, watchlist, and rule selectors when engine is running
    if (timeframeSelect) {
      timeframeSelect.disabled = status.is_running;
      if (status.is_running) {
        timeframeSelect.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        timeframeSelect.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    }
    
    if (watchlistSelect) {
      watchlistSelect.disabled = status.is_running;
      if (status.is_running) {
        watchlistSelect.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        watchlistSelect.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    }
    
    if (ruleSelect) {
      ruleSelect.disabled = status.is_running;
      if (status.is_running) {
        ruleSelect.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        ruleSelect.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    }

    // If engine just transitioned from running to stopped, clear price table (frontend only)
    if (wasRunning && !status.is_running) {
      this.clearPriceTable();
    }

    // Update current selections
    if (status.active_rule) {
      this.currentRule = status.active_rule;
      document.getElementById("rule-select").value = status.active_rule.id;
    }

    if (status.active_watchlist && status.active_watchlist.length > 0) {
      // Find the watchlist with these symbols
      const watchlists = document.querySelectorAll(
        "#watchlists-container .watchlist-item"
      );
      watchlists.forEach((item) => {
        const symbols = JSON.parse(item.dataset.symbols || "[]");
        if (
          JSON.stringify(symbols.sort()) ===
          JSON.stringify(status.active_watchlist.sort())
        ) {
          const watchlistId = parseInt(item.dataset.watchlistId);
          document.getElementById("watchlist-select").value = watchlistId;
          this.currentWatchlist = { id: watchlistId, symbols };
        }
      });
    }
  }

  /**
   * Update rules list display
   */
  updateRulesList(rules) {
    const container = document.getElementById("rules-list");

    if (rules.length === 0) {
      container.innerHTML =
        '<div class="text-gray-500 text-center py-4">No rules found</div>';
      return;
    }

    container.innerHTML = rules
      .map(
        (rule) => `
            <div class="rule-item p-3 border rounded-lg ${
              rule.is_system ? "bg-gray-50" : "bg-white"
            }" data-rule-id="${rule.id}">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <h4 class="font-medium ${
                          rule.is_system ? "text-gray-600" : "text-gray-900"
                        }">${rule.name}</h4>
                        <p class="text-sm text-gray-600 mt-1">
                            ${rule.definition.logic} - ${
          rule.definition.conditions.length
        } conditions
                        </p>
                        <p class="text-xs text-gray-500 mt-1">
                            Cooldown: ${rule.definition.cooldown_sec}s
                            ${rule.is_system ? " • System Rule" : ""}
                        </p>
                    </div>
                    <div class="flex space-x-1">
                        <button class="view-rule-details px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600" data-rule-id="${
                          rule.id
                        }">
                            View Details
                        </button>
                        ${
                          !rule.is_system
                            ? `
                            <button class="delete-rule px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600" data-rule-id="${rule.id}">
                                Delete
                            </button>
                        `
                            : ""
                        }
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  /**
   * Update watchlists display
   */
  updateWatchlists(watchlists) {
    const container = document.getElementById("watchlists-container");

    if (watchlists.length === 0) {
      container.innerHTML =
        '<div class="text-gray-500 text-center py-4">No watchlists found</div>';
      return;
    }

    container.innerHTML = watchlists
      .map(
        (watchlist) => `
            <div class="watchlist-item p-3 border rounded-lg bg-white" data-watchlist-id="${
              watchlist.id
            }" data-symbols='${JSON.stringify(watchlist.symbols)}'>
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <h4 class="font-medium text-gray-900">${
                          watchlist.name
                        }</h4>
                        <p class="text-sm text-gray-600 mt-1">
                            ${watchlist.symbols.join(", ")}
                        </p>
                        <p class="text-xs text-gray-500 mt-1">
                            ${watchlist.symbols.length}/5 symbols
                            ${watchlist.is_active ? " • Active" : ""}
                        </p>
                    </div>
                    <div class="flex space-x-1">
                        <button class="delete-watchlist px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600" data-watchlist-id="${
                          watchlist.id
                        }">
                            Delete
                        </button>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  /**
   * Add signal to the signals display
   * @param {Object} signal - Signal data
   * @param {boolean} silent - If true, don't show toast notification (for initial load)
   */
  addSignal(signal, silent = false) {
    this.signals.unshift(signal);

    // Keep only the most recent signals
    if (this.signals.length > this.maxSignals) {
      this.signals = this.signals.slice(0, this.maxSignals);
    }

    const container = document.getElementById("signals-container");

    // Clear "no signals" message if this is the first signal
    if (this.signals.length === 1) {
      container.innerHTML = "";
    }

    // Create signal element
    const signalElement = document.createElement("div");
    signalElement.className =
      "signal-item p-3 border rounded-lg bg-green-50 border-green-200 hover:shadow-md transition-shadow";
    signalElement.dataset.signalId = signal.id || Date.now(); // Use signal ID for deletion

    // Handle both 'time' (from DB) and 'timestamp' (from WebSocket) fields
    const signalTime = signal.time || signal.timestamp;
    const signalDate = signalTime ? new Date(signalTime) : null;
    const dateDisplay = signalDate
      ? signalDate.toLocaleDateString()
      : "Unknown date";
    const timeDisplay = signalDate
      ? signalDate.toLocaleTimeString()
      : "Unknown time";

    signalElement.innerHTML = `
            <div class="flex justify-between items-start gap-3">
                <div class="flex-1">
                    <h4 class="font-medium text-green-800">${signal.symbol}</h4>
                    <p class="text-sm text-green-600">Price: $${signal.price}</p>
                    <p class="text-xs text-green-500">${dateDisplay} • ${timeDisplay}</p>
                </div>
                <div class="flex items-center gap-1">
                    <button class="view-signal-detail px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors" title="View Details">
                        <i class="fas fa-info-circle"></i>
                    </button>
                    <button class="delete-signal px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 transition-colors" title="Delete Signal">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;

    // Add click handler for detail button
    const detailBtn = signalElement.querySelector(".view-signal-detail");
    detailBtn.addEventListener("click", () => this.showSignalDetail(signal));

    // Add click handler for delete button
    const deleteBtn = signalElement.querySelector(".delete-signal");
    deleteBtn.addEventListener("click", () =>
      this.deleteSignal(signal, signalElement)
    );

    // Add to container (at the beginning)
    container.insertBefore(signalElement, container.firstChild);

    // Remove old signals if we have too many
    while (container.children.length > this.maxSignals) {
      container.removeChild(container.lastChild);
    }

    // Show toast notification only if not in silent mode
    if (!silent) {
      this.showToast(
        `New signal: ${signal.symbol} at $${signal.price}`,
        "success"
      );
    }
  }

  /**
   * Delete signal from UI and database
   * @param {Object} signal - Signal data
   * @param {HTMLElement} signalElement - Signal DOM element
   */
  async deleteSignal(signal, signalElement) {
    if (!confirm(`Delete signal for ${signal.symbol} at $${signal.price}?`)) {
      return;
    }

    try {
      // If signal has ID, delete from database
      if (signal.id) {
        await API.deleteSignal(signal.id);
      }

      // Remove from UI
      signalElement.remove();

      // Remove from signals array
      const index = this.signals.findIndex((s) => s.id === signal.id);
      if (index > -1) {
        this.signals.splice(index, 1);
      }

      // If no signals left, show placeholder
      const container = document.getElementById("signals-container");
      if (container.children.length === 0) {
        container.innerHTML = `
          <div class="text-gray-500 text-center py-8">
            No signals received yet
          </div>
        `;
      }

      this.showToast("Signal deleted successfully", "success");
    } catch (error) {
      console.error("Failed to delete signal:", error);
      this.showToast(`Failed to delete signal: ${error.message}`, "error");
    }
  }

  /**
   * Populate rule select dropdown
   */
  populateRuleSelect(rules) {
    const select = document.getElementById("rule-select");
    select.innerHTML =
      '<option value="">Select rule...</option>' +
      rules
        .map((rule) => `<option value="${rule.id}">${rule.name}</option>`)
        .join("");
  }

  /**
   * Populate watchlist select dropdown
   */
  populateWatchlistSelect(watchlists) {
    const select = document.getElementById("watchlist-select");
    select.innerHTML =
      '<option value="">Select watchlist...</option>' +
      watchlists
        .map(
          (watchlist) =>
            `<option value="${watchlist.id}">${watchlist.name}</option>`
        )
        .join("");
  }

  /**
   * Populate settings form
   */
  populateSettingsForm(settings) {
    if (settings.ib_host)
      document.getElementById("ib-host").value = settings.ib_host;
    if (settings.ib_port)
      document.getElementById("ib-port").value = settings.ib_port;
    // Client ID is auto-generated, don't populate from settings
  }

  /**
   * Start the engine
   */
  async startEngine() {
    try {
      const watchlistId = parseInt(
        document.getElementById("watchlist-select").value
      );
      const ruleId = parseInt(document.getElementById("rule-select").value);

      if (!watchlistId || !ruleId) {
        this.showToast("Please select both a watchlist and a rule", "error");
        return;
      }

      this.showLoading();

      await API.startEngine({ watchlist_id: watchlistId, rule_id: ruleId });

      this.showToast("Engine started successfully", "success");
    } catch (error) {
      console.error("Failed to start engine:", error);
      this.showToast(`Failed to start engine: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Stop the engine
   */
  async stopEngine() {
    try {
      this.showLoading();

      await API.stopEngine();

      // Clear real-time prices on frontend when engine stops
      this.clearPriceTable();

      this.showToast("Engine stopped successfully", "success");
    } catch (error) {
      console.error("Failed to stop engine:", error);
      this.showToast(`Failed to stop engine: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Load current timeframe setting
   */
  async loadTimeframe() {
    try {
      const response = await API.getAvailableTimeframes();
      const currentTimeframe = response.current || '1m';
      
      // Set the dropdown to current value
      const timeframeSelect = document.getElementById("timeframe-select");
      if (timeframeSelect) {
        timeframeSelect.value = currentTimeframe;
      }
      
      console.log(`Current timeframe: ${currentTimeframe}`);
    } catch (error) {
      console.error("Failed to load timeframe:", error);
    }
  }

  /**
   * Handle timeframe change
   */
  async handleTimeframeChange(event) {
    const newTimeframe = event.target.value;
    
    try {
      // Check if engine is running
      if (this.engineRunning) {
        this.showToast(
          "Cannot change timeframe while engine is running. Stop the engine first.",
          "warning"
        );
        // Revert to current value
        await this.loadTimeframe();
        return;
      }

      this.showLoading();

      await API.changeTimeframe(newTimeframe);

      this.showToast(
        `Timeframe changed to ${newTimeframe}. Historical data will be re-aggregated when engine starts.`,
        "success"
      );
    } catch (error) {
      console.error("Failed to change timeframe:", error);
      this.showToast(`Failed to change timeframe: ${error.message}`, "error");
      
      // Revert to previous value
      await this.loadTimeframe();
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Handle rule form submission
   */
  async handleRuleSubmit(event) {
    event.preventDefault();

    try {
      const name = document.getElementById("rule-name").value.trim();
      const logic = document.getElementById("rule-logic").value;
      const cooldown = parseInt(document.getElementById("rule-cooldown").value);

      if (!name) {
        this.showToast("Please enter a rule name", "error");
        return;
      }

      // Collect and validate conditions
      const conditions = [];
      const conditionRows = document.querySelectorAll(".condition-row");
      let validationErrors = [];

      conditionRows.forEach((row, index) => {
        let left = row.querySelector(".condition-left").value;
        const op = row.querySelector(".condition-op").value;
        let right = row.querySelector(".condition-right").value;

        // Handle custom numeric input for left side
        if (left === "_CUSTOM_") {
          const customInput = row.querySelector(".condition-left-custom");
          console.log(`DEBUG: Left custom input found: ${!!customInput}`);

          if (customInput) {
            console.log(
              `DEBUG: Left custom input value: "${customInput.value}"`
            );

            // Validate the custom input
            if (!this.validateCustomInput(customInput)) {
              validationErrors.push(
                `Condition ${index + 1} left side: Invalid number`
              );
              return;
            }

            left = parseFloat(customInput.value);
            console.log(`DEBUG: Parsed left value: ${left}`);
          } else {
            console.error(
              `DEBUG: ERROR - Left custom input not found in form submission!`
            );
            validationErrors.push(
              `Condition ${index + 1} left side: Custom input missing`
            );
            return;
          }
        }

        // Handle custom numeric input for right side
        if (right === "_CUSTOM_") {
          const customInput = row.querySelector(".condition-right-custom");
          console.log(`DEBUG: Right custom input found: ${!!customInput}`);

          if (customInput) {
            console.log(
              `DEBUG: Right custom input value: "${customInput.value}"`
            );

            // Validate the custom input
            if (!this.validateCustomInput(customInput)) {
              validationErrors.push(
                `Condition ${index + 1} right side: Invalid number`
              );
              return;
            }

            right = parseFloat(customInput.value);
            console.log(`DEBUG: Parsed right value: ${right}`);
          } else {
            console.error(
              `DEBUG: ERROR - Right custom input not found in form submission!`
            );
            validationErrors.push(
              `Condition ${index + 1} right side: Custom input missing`
            );
            return;
          }
        }

        // Additional validation for numeric values
        if (typeof left === "number" && (isNaN(left) || !isFinite(left))) {
          validationErrors.push(
            `Condition ${index + 1} left side: Invalid numeric value`
          );
          return;
        }

        if (typeof right === "number" && (isNaN(right) || !isFinite(right))) {
          validationErrors.push(
            `Condition ${index + 1} right side: Invalid numeric value`
          );
          return;
        }

        conditions.push({ left, op, right });
      });

      // Check for validation errors
      if (validationErrors.length > 0) {
        this.showToast(
          `Validation errors: ${validationErrors.join(", ")}`,
          "error"
        );
        return;
      }

      if (conditions.length === 0) {
        this.showToast("Please add at least one valid condition", "error");
        return;
      }

      const ruleData = {
        name,
        definition: {
          logic,
          conditions,
          cooldown_sec: cooldown,
        },
      };

      console.log("DEBUG: Submitting rule data:", ruleData);
      this.showLoading();

      await API.createRule(ruleData);

      // Reload rules
      const rules = await API.getAllRules();
      this.updateRulesList(rules);
      this.populateRuleSelect(rules);

      // Clear form
      this.clearRuleForm();

      this.showToast("Rule created successfully", "success");
    } catch (error) {
      console.error("Failed to create rule:", error);
      this.showToast(`Failed to create rule: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Clear rule form
   */
  clearRuleForm() {
    document.getElementById("rule-name").value = "";
    document.getElementById("rule-logic").value = "AND";
    document.getElementById("rule-cooldown").value = "60";

    // Clean up all existing condition rows before clearing
    const existingRows = document.querySelectorAll(".condition-row");
    existingRows.forEach((row) => this.cleanupConditionRow(row));

    // Reset conditions to single empty row
    const container = document.getElementById("conditions-container");
    container.innerHTML = this.getConditionRowHTML();

    // Use setTimeout to ensure DOM is fully updated before attaching listeners
    setTimeout(() => {
      const newRow = container.querySelector(".condition-row");
      if (newRow) {
        this.attachConditionRowListeners(newRow);
      }
    }, 0);
  }

  /**
   * Get HTML for a condition row with all operands
   */
  getConditionRowHTML() {
    return `
      <div class="condition-row flex space-x-2">
        <select class="condition-left flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          <optgroup label="Price & Candle">
            <option value="PRICE">PRICE</option>
            <option value="PREV_CLOSE">PREV_CLOSE</option>
            <option value="PREV_OPEN">PREV_OPEN</option>
          </optgroup>
          <optgroup label="Simple Moving Averages">
            <option value="MA20">MA20</option>
            <option value="MA50">MA50</option>
            <option value="MA100">MA100</option>
            <option value="MA200">MA200</option>
          </optgroup>
          <optgroup label="Exponential Moving Averages">
            <option value="EMA6">EMA6</option>
            <option value="EMA9">EMA9</option>
            <option value="EMA10">EMA10</option>
            <option value="EMA13">EMA13</option>
            <option value="EMA20">EMA20</option>
            <option value="EMA21">EMA21</option>
            <option value="EMA34">EMA34</option>
            <option value="EMA50">EMA50</option>
          </optgroup>
          <optgroup label="MACD">
            <option value="MACD">MACD</option>
            <option value="MACD_SIGNAL">MACD_SIGNAL</option>
            <option value="MACD_HIST">MACD_HIST</option>
            <option value="MACD_HIST_PREV">MACD_HIST_PREV</option>
          </optgroup>
          <optgroup label="RSI">
            <option value="RSI14">RSI14</option>
            <option value="RSI14_PREV">RSI14_PREV</option>
          </optgroup>
          <optgroup label="ADX">
            <option value="ADX5">ADX5</option>
            <option value="ADX5_PREV">ADX5_PREV</option>
          </optgroup>
          <optgroup label="Bollinger Bands">
            <option value="BB_UPPER">BB_UPPER</option>
            <option value="BB_MIDDLE">BB_MIDDLE</option>
            <option value="BB_LOWER">BB_LOWER</option>
            <option value="BB_WIDTH">BB_WIDTH</option>
          </optgroup>
          <optgroup label="Calculated Metrics">
            <option value="PRICE_EMA20_DIFF_PCT">PRICE_EMA20_DIFF_PCT</option>
          </optgroup>
          <optgroup label="Numeric Value">
            <option value="_CUSTOM_">Custom Number...</option>
          </optgroup>
        </select>
        <select class="condition-op px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value=">">></option>
          <option value="<"><</option>
          <option value=">=">>=</option>
          <option value="<="><=</option>
          <option value="CROSS_UP">CROSS_UP</option>
          <option value="CROSS_DOWN">CROSS_DOWN</option>
        </select>
        <select class="condition-right flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          <optgroup label="Price & Candle">
            <option value="PRICE">PRICE</option>
            <option value="PREV_CLOSE">PREV_CLOSE</option>
            <option value="PREV_OPEN">PREV_OPEN</option>
          </optgroup>
          <optgroup label="Simple Moving Averages">
            <option value="MA20">MA20</option>
            <option value="MA50">MA50</option>
            <option value="MA100">MA100</option>
            <option value="MA200">MA200</option>
          </optgroup>
          <optgroup label="Exponential Moving Averages">
            <option value="EMA6">EMA6</option>
            <option value="EMA9">EMA9</option>
            <option value="EMA10">EMA10</option>
            <option value="EMA13">EMA13</option>
            <option value="EMA20">EMA20</option>
            <option value="EMA21">EMA21</option>
            <option value="EMA34">EMA34</option>
            <option value="EMA50">EMA50</option>
          </optgroup>
          <optgroup label="MACD">
            <option value="MACD">MACD</option>
            <option value="MACD_SIGNAL">MACD_SIGNAL</option>
            <option value="MACD_HIST">MACD_HIST</option>
            <option value="MACD_HIST_PREV">MACD_HIST_PREV</option>
          </optgroup>
          <optgroup label="RSI">
            <option value="RSI14">RSI14</option>
            <option value="RSI14_PREV">RSI14_PREV</option>
          </optgroup>
          <optgroup label="ADX">
            <option value="ADX5">ADX5</option>
            <option value="ADX5_PREV">ADX5_PREV</option>
          </optgroup>
          <optgroup label="Bollinger Bands">
            <option value="BB_UPPER">BB_UPPER</option>
            <option value="BB_MIDDLE">BB_MIDDLE</option>
            <option value="BB_LOWER">BB_LOWER</option>
            <option value="BB_WIDTH">BB_WIDTH</option>
          </optgroup>
          <optgroup label="Calculated Metrics">
            <option value="PRICE_EMA20_DIFF_PCT">PRICE_EMA20_DIFF_PCT</option>
          </optgroup>
          <optgroup label="Numeric Value">
            <option value="_CUSTOM_">Custom Number...</option>
          </optgroup>
        </select>
        <button type="button" class="remove-condition px-3 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    `;
  }

  /**
   * Attach event listeners to condition row
   */
  attachConditionRowListeners(row) {
    console.log("DEBUG: attachConditionRowListeners called for row:", row);
    const leftSelect = row.querySelector(".condition-left");
    const rightSelect = row.querySelector(".condition-right");

    console.log("DEBUG: leftSelect found:", !!leftSelect);
    console.log("DEBUG: rightSelect found:", !!rightSelect);

    if (!leftSelect || !rightSelect) {
      console.error("DEBUG: Could not find select elements in condition row");
      return;
    }

    leftSelect.addEventListener("change", (e) => {
      console.log(
        "DEBUG: Left select change event triggered, value:",
        e.target.value
      );
      if (e.target.value === "_CUSTOM_") {
        console.log("DEBUG: Calling showCustomInput for left side");
        this.showCustomInput(row, "left");
      } else {
        console.log("DEBUG: Calling hideCustomInput for left side");
        this.hideCustomInput(row, "left");
      }
    });

    rightSelect.addEventListener("change", (e) => {
      console.log(
        "DEBUG: Right select change event triggered, value:",
        e.target.value
      );
      if (e.target.value === "_CUSTOM_") {
        console.log("DEBUG: Calling showCustomInput for right side");
        this.showCustomInput(row, "right");
      } else {
        console.log("DEBUG: Calling hideCustomInput for right side");
        this.hideCustomInput(row, "right");
      }
    });

    console.log("DEBUG: Event listeners attached successfully");
  }

  /**
   * Show custom numeric input
   */
  showCustomInput(row, side) {
    console.log(`DEBUG: showCustomInput called for side: ${side}`);
    console.log(`DEBUG: Row element:`, row);

    // Validate inputs
    if (!row || !side) {
      console.error(`DEBUG: Invalid inputs - row: ${!!row}, side: ${side}`);
      return;
    }

    const select = row.querySelector(`.condition-${side}`);
    const existingInput = row.querySelector(`.condition-${side}-custom`);

    console.log(`DEBUG: Select element found: ${!!select}`);
    console.log(`DEBUG: Existing input found: ${!!existingInput}`);

    if (!select) {
      console.error(`DEBUG: Select element not found for side: ${side}`);
      return;
    }

    if (existingInput) {
      console.log(
        `DEBUG: Custom input already exists for ${side}, focusing it`
      );
      existingInput.focus();
      existingInput.select();
      return;
    }

    // Create input with validation attributes
    const input = document.createElement("input");
    input.type = "number";
    input.step = "any";
    input.min = "-999999999";
    input.max = "999999999";
    input.className = `condition-${side}-custom flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`;
    input.placeholder = "Enter number";
    input.value = "0";
    input.setAttribute("data-side", side); // Add data attribute for tracking

    // Create a button to switch back to dropdown
    const switchButton = document.createElement("button");
    switchButton.type = "button";
    switchButton.className = `condition-${side}-switch px-2 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors text-xs`;
    switchButton.innerHTML = '<i class="fas fa-list"></i>';
    switchButton.title = "Switch to dropdown";
    switchButton.setAttribute("data-side", side);

    console.log(`DEBUG: Created input element:`, input);
    console.log(`DEBUG: Select parent node:`, select.parentNode);

    try {
      // Hide the select dropdown
      select.style.display = "none";

      // Insert the input and button before the select
      select.parentNode.insertBefore(input, select);
      select.parentNode.insertBefore(switchButton, select);

      console.log(`DEBUG: Successfully inserted custom input for ${side}`);

      // Verify the input was added and is properly positioned
      const addedInput = row.querySelector(`.condition-${side}-custom`);
      console.log(
        `DEBUG: Verification - Custom input found after insertion: ${!!addedInput}`
      );

      if (!addedInput) {
        console.error(
          `DEBUG: ERROR - Custom input not found after insertion for ${side}`
        );
        return;
      }

      // Add validation event listener
      addedInput.addEventListener("input", (e) => {
        this.validateCustomInput(e.target);
      });

      // Add click listener to switch button
      switchButton.addEventListener("click", () => {
        console.log(`DEBUG: Switch button clicked for ${side}`);
        this.switchToDropdown(row, side);
      });

      // Focus the input for better UX
      setTimeout(() => {
        addedInput.focus();
        addedInput.select();
      }, 0);
    } catch (error) {
      console.error(`DEBUG: Error inserting custom input for ${side}:`, error);
      // Restore select visibility on error
      if (select) {
        select.style.display = "";
      }
    }
  }

  /**
   * Hide custom numeric input
   */
  hideCustomInput(row, side) {
    console.log(`DEBUG: hideCustomInput called for side: ${side}`);

    // Validate inputs
    if (!row || !side) {
      console.error(`DEBUG: Invalid inputs - row: ${!!row}, side: ${side}`);
      return;
    }

    const input = row.querySelector(`.condition-${side}-custom`);
    const switchButton = row.querySelector(`.condition-${side}-switch`);
    const select = row.querySelector(`.condition-${side}`);

    console.log(`DEBUG: Input element found: ${!!input}`);
    console.log(`DEBUG: Switch button found: ${!!switchButton}`);
    console.log(`DEBUG: Select element found: ${!!select}`);

    if (input) {
      try {
        // Remove the input element (event listeners are automatically removed)
        input.remove();
        console.log(`DEBUG: Removed custom input for ${side}`);
      } catch (error) {
        console.error(`DEBUG: Error removing custom input for ${side}:`, error);
      }
    } else {
      console.log(`DEBUG: No custom input to remove for ${side}`);
    }

    if (switchButton) {
      try {
        // Remove the switch button
        switchButton.remove();
        console.log(`DEBUG: Removed switch button for ${side}`);
      } catch (error) {
        console.error(
          `DEBUG: Error removing switch button for ${side}:`,
          error
        );
      }
    }

    if (select) {
      try {
        // Restore select visibility
        select.style.display = "";
        console.log(`DEBUG: Restored select display for ${side}`);

        // If select is still on _CUSTOM_ after hiding input, reset to first valid option
        if (select.value === "_CUSTOM_") {
          // Find first non-custom option
          const firstOption = Array.from(select.options).find(
            (opt) => opt.value !== "_CUSTOM_"
          );
          if (firstOption) {
            select.value = firstOption.value;
            console.log(
              `DEBUG: Reset select from _CUSTOM_ to ${firstOption.value}`
            );
          }
        }
      } catch (error) {
        console.error(`DEBUG: Error restoring select for ${side}:`, error);
      }
    } else {
      console.log(`DEBUG: No select element to restore for ${side}`);
    }
  }

  /**
   * Switch from custom input back to dropdown
   */
  switchToDropdown(row, side) {
    console.log(`DEBUG: switchToDropdown called for side: ${side}`);

    if (!row || !side) {
      console.error(`DEBUG: Invalid inputs - row: ${!!row}, side: ${side}`);
      return;
    }

    const select = row.querySelector(`.condition-${side}`);
    const input = row.querySelector(`.condition-${side}-custom`);
    const switchButton = row.querySelector(`.condition-${side}-switch`);

    if (input) {
      input.remove();
      console.log(`DEBUG: Removed custom input for ${side}`);
    }

    if (switchButton) {
      switchButton.remove();
      console.log(`DEBUG: Removed switch button for ${side}`);
    }

    if (select) {
      // Reset to first valid option
      const firstOption = Array.from(select.options).find(
        (opt) => opt.value !== "_CUSTOM_"
      );
      if (firstOption) {
        select.value = firstOption.value;
      }
      select.style.display = "";
      console.log(`DEBUG: Restored dropdown for ${side}`);
    }
  }

  /**
   * Validate custom numeric input
   * @param {HTMLInputElement} input - The input element to validate
   */
  validateCustomInput(input) {
    if (!input) return;

    const value = parseFloat(input.value);
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);

    // Check if value is a valid number
    if (isNaN(value)) {
      input.setCustomValidity("Please enter a valid number");
      input.classList.add("border-red-500");
      return false;
    }

    // Check min/max constraints
    if (!isNaN(min) && value < min) {
      input.setCustomValidity(`Value must be at least ${min}`);
      input.classList.add("border-red-500");
      return false;
    }

    if (!isNaN(max) && value > max) {
      input.setCustomValidity(`Value must be at most ${max}`);
      input.classList.add("border-red-500");
      return false;
    }

    // Clear validation errors
    input.setCustomValidity("");
    input.classList.remove("border-red-500");
    return true;
  }

  /**
   * Add condition row to rule builder
   */
  addConditionRow() {
    console.log("DEBUG: addConditionRow called");
    const container = document.getElementById("conditions-container");
    console.log("DEBUG: Conditions container found:", !!container);

    // Create a temporary div to hold the HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = this.getConditionRowHTML();
    const actualRow = tempDiv.firstElementChild;

    console.log("DEBUG: Created new condition row:", actualRow);
    console.log("DEBUG: Row HTML:", tempDiv.innerHTML);

    // Append the row to the container
    container.appendChild(actualRow);
    console.log("DEBUG: Row appended to container");

    // Use setTimeout to ensure DOM is fully updated before attaching listeners
    setTimeout(() => {
      this.attachConditionRowListeners(actualRow);
      console.log("DEBUG: Event listeners attached to new row");
    }, 0);
  }

  /**
   * Remove condition row from rule builder
   */
  removeConditionRow(row) {
    const container = document.getElementById("conditions-container");
    if (container.children.length > 1) {
      // Clean up custom inputs before removing the row
      this.cleanupConditionRow(row);
      row.remove();
    } else {
      this.showToast("At least one condition is required", "error");
    }
  }

  /**
   * Clean up custom inputs in a condition row
   * @param {HTMLElement} row - The condition row to clean up
   */
  cleanupConditionRow(row) {
    if (!row) return;

    // Remove any custom inputs and restore select visibility
    const leftCustomInput = row.querySelector(".condition-left-custom");
    const rightCustomInput = row.querySelector(".condition-right-custom");
    const leftSwitchButton = row.querySelector(".condition-left-switch");
    const rightSwitchButton = row.querySelector(".condition-right-switch");
    const leftSelect = row.querySelector(".condition-left");
    const rightSelect = row.querySelector(".condition-right");

    if (leftCustomInput) {
      leftCustomInput.remove();
    }
    if (rightCustomInput) {
      rightCustomInput.remove();
    }
    if (leftSwitchButton) {
      leftSwitchButton.remove();
    }
    if (rightSwitchButton) {
      rightSwitchButton.remove();
    }
    if (leftSelect) {
      leftSelect.style.display = "";
      leftSelect.value = "PRICE";
    }
    if (rightSelect) {
      rightSelect.style.display = "";
      rightSelect.value = "PRICE";
    }
  }

  /**
   * Synchronize select dropdown state with custom input visibility
   * @param {HTMLElement} row - The condition row to synchronize
   */
  synchronizeConditionRowState(row) {
    if (!row) return;

    const leftSelect = row.querySelector(".condition-left");
    const rightSelect = row.querySelector(".condition-right");
    const leftCustomInput = row.querySelector(".condition-left-custom");
    const rightCustomInput = row.querySelector(".condition-right-custom");

    // Synchronize left side
    if (leftSelect && leftCustomInput) {
      leftSelect.value = "_CUSTOM_";
      leftSelect.style.display = "none";
    } else if (leftSelect && !leftCustomInput) {
      leftSelect.style.display = "";
      if (leftSelect.value === "_CUSTOM_") {
        leftSelect.value = "PRICE";
      }
    }

    // Synchronize right side
    if (rightSelect && rightCustomInput) {
      rightSelect.value = "_CUSTOM_";
      rightSelect.style.display = "none";
    } else if (rightSelect && !rightCustomInput) {
      rightSelect.style.display = "";
      if (rightSelect.value === "_CUSTOM_") {
        rightSelect.value = "PRICE";
      }
    }
  }

  /**
   * Handle watchlist form submission
   */
  async handleWatchlistSubmit(event) {
    event.preventDefault();

    try {
      const name = document.getElementById("watchlist-name").value.trim();

      if (!name) {
        this.showToast("Please enter a watchlist name", "error");
        return;
      }

      if (this.watchlistSymbols.length === 0) {
        this.showToast("Please add at least one symbol", "error");
        return;
      }

      if (this.watchlistSymbols.length > 5) {
        this.showToast("Maximum 5 symbols allowed", "error");
        return;
      }

      const watchlistData = {
        name,
        symbols: this.watchlistSymbols,
      };

      this.showLoading();

      await API.createWatchlist(watchlistData);

      // Reload watchlists
      const watchlists = await API.getAllWatchlists();
      this.updateWatchlists(watchlists);
      this.populateWatchlistSelect(watchlists);

      // Clear form
      document.getElementById("watchlist-name").value = "";
      this.watchlistSymbols = [];
      this.updateSymbolsList();

      this.showToast("Watchlist created successfully", "success");
    } catch (error) {
      console.error("Failed to create watchlist:", error);
      this.showToast(`Failed to create watchlist: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Add symbol to watchlist
   */
  addSymbolToWatchlist() {
    const input = document.getElementById("watchlist-symbol");
    const symbol = input.value.trim().toUpperCase();

    if (!symbol) {
      this.showToast("Please enter a symbol", "error");
      return;
    }

    if (this.watchlistSymbols.includes(symbol)) {
      this.showToast("Symbol already added", "error");
      return;
    }

    if (this.watchlistSymbols.length >= 5) {
      this.showToast("Maximum 5 symbols allowed", "error");
      return;
    }

    this.watchlistSymbols.push(symbol);
    input.value = "";
    this.updateSymbolsList();
  }

  /**
   * Remove symbol from watchlist
   */
  removeSymbolFromWatchlist(symbol) {
    this.watchlistSymbols = this.watchlistSymbols.filter((s) => s !== symbol);
    this.updateSymbolsList();
  }

  /**
   * Update symbols list display
   */
  updateSymbolsList() {
    const container = document.getElementById("symbols-list");

    if (this.watchlistSymbols.length === 0) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = this.watchlistSymbols
      .map(
        (symbol) => `
            <span class="inline-flex items-center px-2 py-1 bg-teal-100 text-teal-800 text-sm rounded">
                ${symbol}
                <button class="remove-symbol ml-1 text-teal-600 hover:text-teal-800" data-symbol="${symbol}">
                    <i class="fas fa-times"></i>
                </button>
            </span>
        `
      )
      .join("");
  }

  /**
   * Delete rule
   */
  async deleteRule(ruleId) {
    if (!confirm("Are you sure you want to delete this rule?")) {
      return;
    }

    try {
      this.showLoading();

      await API.deleteRule(ruleId);

      // Reload rules
      const rules = await API.getAllRules();
      this.updateRulesList(rules);
      this.populateRuleSelect(rules);

      this.showToast("Rule deleted successfully", "success");
    } catch (error) {
      console.error("Failed to delete rule:", error);
      this.showToast(`Failed to delete rule: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Delete watchlist
   */
  async deleteWatchlist(watchlistId) {
    if (!confirm("Are you sure you want to delete this watchlist?")) {
      return;
    }

    try {
      this.showLoading();

      await API.deleteWatchlist(watchlistId);

      // Reload watchlists
      const watchlists = await API.getAllWatchlists();
      this.updateWatchlists(watchlists);
      this.populateWatchlistSelect(watchlists);

      this.showToast("Watchlist deleted successfully", "success");
    } catch (error) {
      console.error("Failed to delete watchlist:", error);
      this.showToast(`Failed to delete watchlist: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Save settings
   */
  async saveSettings() {
    try {
      const settings = {
        ib_host: document.getElementById("ib-host").value,
        ib_port: parseInt(document.getElementById("ib-port").value),
        // Client ID is auto-generated on each connection, not configurable
      };

      this.showLoading();

      // Save each setting
      for (const [key, value] of Object.entries(settings)) {
        await API.setSetting(key, value);
      }

      this.showToast("Settings saved successfully", "success");
    } catch (error) {
      console.error("Failed to save settings:", error);
      this.showToast(`Failed to save settings: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Update rule in list (WebSocket update)
   */
  updateRuleInList(rule) {
    const ruleElement = document.querySelector(`[data-rule-id="${rule.id}"]`);
    if (ruleElement) {
      // Reload rules to get updated list
      API.getAllRules().then((rules) => {
        this.updateRulesList(rules);
        this.populateRuleSelect(rules);
      });
    }
  }

  /**
   * Update watchlist in list (WebSocket update)
   */
  updateWatchlistInList(watchlist) {
    const watchlistElement = document.querySelector(
      `[data-watchlist-id="${watchlist.id}"]`
    );
    if (watchlistElement) {
      // Reload watchlists to get updated list
      API.getAllWatchlists().then((watchlists) => {
        this.updateWatchlists(watchlists);
        this.populateWatchlistSelect(watchlists);
      });
    }
  }

  /**
   * Show toast notification
   */
  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");

    const toast = document.createElement("div");
    toast.className = `p-4 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full ${
      type === "success"
        ? "bg-green-500 text-white"
        : type === "error"
        ? "bg-red-500 text-white"
        : type === "warning"
        ? "bg-yellow-500 text-white"
        : "bg-blue-500 text-white"
    }`;

    toast.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${
                  type === "success"
                    ? "fa-check-circle"
                    : type === "error"
                    ? "fa-exclamation-circle"
                    : type === "warning"
                    ? "fa-exclamation-triangle"
                    : "fa-info-circle"
                } mr-2"></i>
                <span>${message}</span>
            </div>
        `;

    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
      toast.classList.remove("translate-x-full");
      toast.classList.add("translate-x-0");
    }, 10);

    // Remove after 3 seconds
    setTimeout(() => {
      toast.classList.add("translate-x-full");
      setTimeout(() => {
        container.removeChild(toast);
      }, 300);
    }, 3000);
  }

  /**
   * Show loading overlay
   */
  showLoading() {
    document.getElementById("loading-overlay").classList.remove("hidden");
  }

  /**
   * Hide loading overlay
   */
  hideLoading() {
    document.getElementById("loading-overlay").classList.add("hidden");
  }

  /**
   * Initialize the price table structure
   */
  initializePriceTable() {
    // Get the price table container
    const priceTableContainer = document.getElementById(
      "price-table-container"
    );
    if (!priceTableContainer) {
      console.error("Price table container not found");
      return;
    }

    // Initialize with empty table
    priceTableContainer.innerHTML = `
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Change</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Update</th>
            </tr>
          </thead>
          <tbody id="price-table-body" class="bg-white divide-y divide-gray-200">
            <tr>
              <td colspan="4" class="px-6 py-4 text-center text-gray-500">No price data available</td>
            </tr>
          </tbody>
        </table>
      </div>
    `;
  }

  /**
   * Update the price table with new price data
   * @param {Object} priceData - Price update data containing symbol, price, and timestamp
   */
  updatePriceTable(priceData) {
    console.log("DEBUG: updatePriceTable called with:", priceData);

    // Check if priceData has the expected structure
    if (!priceData) {
      console.error("DEBUG: priceData is null or undefined");
      return;
    }

    const { symbol, price, timestamp } = priceData;

    if (!symbol || !price) {
      console.error("DEBUG: Missing symbol or price in priceData:", priceData);
      return;
    }

    console.log(
      "DEBUG: Extracted symbol:",
      symbol,
      "price:",
      price,
      "timestamp:",
      timestamp
    );

    // Store previous price for change calculation
    const previousPrice = this.priceData[symbol]
      ? this.priceData[symbol].price
      : null;

    // Update price data
    this.priceData[symbol] = {
      price: price,
      timestamp: timestamp || new Date().toISOString(),
      previousPrice: previousPrice,
    };

    // Get or create table body
    const tableBody = document.getElementById("price-table-body");
    if (!tableBody) return;

    // Check if row already exists for this symbol
    let existingRow = document.getElementById(`price-row-${symbol}`);

    if (existingRow) {
      // Update existing row
      this.updatePriceRow(existingRow, symbol, price, previousPrice, timestamp);
    } else {
      // Create new row
      this.createPriceRow(symbol, price, previousPrice, timestamp);
    }

    // Sort table by symbol
    this.sortPriceTable();
  }

  /**
   * Create a new price row in the table
   * @param {string} symbol - Stock symbol
   * @param {number} price - Current price
   * @param {number} previousPrice - Previous price for change calculation
   * @param {string} timestamp - Update timestamp
   */
  createPriceRow(symbol, price, previousPrice, timestamp) {
    const tableBody = document.getElementById("price-table-body");
    if (!tableBody) return;

    // Remove "no data" message if this is the first row
    if (
      tableBody.children.length === 1 &&
      tableBody.children[0].children.length === 1
    ) {
      tableBody.innerHTML = "";
    }

    const row = document.createElement("tr");
    row.id = `price-row-${symbol}`;

    const change = previousPrice ? price - previousPrice : 0;
    const changePercent = previousPrice
      ? ((change / previousPrice) * 100).toFixed(2)
      : 0;
    const changeClass =
      change > 0
        ? "text-green-600"
        : change < 0
        ? "text-red-600"
        : "text-gray-600";
    const changeSymbol = change > 0 ? "▲" : change < 0 ? "▼" : "•";

    row.innerHTML = `
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${symbol}</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${price.toFixed(
        2
      )}</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm ${changeClass}">
        <span class="change-symbol">${changeSymbol}</span>
        <span class="change-amount">${Math.abs(change).toFixed(2)}</span>
        <span class="change-percent">(${changePercent}%)</span>
      </td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(
        timestamp
      ).toLocaleTimeString()}</td>
    `;

    tableBody.appendChild(row);
  }

  /**
   * Update an existing price row
   * @param {HTMLElement} row - The table row element
   * @param {string} symbol - Stock symbol
   * @param {number} price - Current price
   * @param {number} previousPrice - Previous price for change calculation
   * @param {string} timestamp - Update timestamp
   */
  updatePriceRow(row, symbol, price, previousPrice, timestamp) {
    const change = previousPrice ? price - previousPrice : 0;
    const changePercent = previousPrice
      ? ((change / previousPrice) * 100).toFixed(2)
      : 0;
    const changeClass =
      change > 0
        ? "text-green-600"
        : change < 0
        ? "text-red-600"
        : "text-gray-600";
    const changeSymbol = change > 0 ? "▲" : change < 0 ? "▼" : "•";

    // Update price cell
    const priceCell = row.children[1];
    priceCell.textContent = `$${price.toFixed(2)}`;

    // Update change cell with animation
    const changeCell = row.children[2];
    changeCell.className = `px-6 py-4 whitespace-nowrap text-sm ${changeClass}`;
    changeCell.innerHTML = `
      <span class="change-symbol">${changeSymbol}</span>
      <span class="change-amount">${Math.abs(change).toFixed(2)}</span>
      <span class="change-percent">(${changePercent}%)</span>
    `;

    // Add flash animation for price changes
    if (previousPrice && price !== previousPrice) {
      row.classList.add("price-flash");
      setTimeout(() => {
        row.classList.remove("price-flash");
      }, 1000);
    }

    // Update timestamp
    const timestampCell = row.children[3];
    timestampCell.textContent = new Date(timestamp).toLocaleTimeString();
  }

  /**
   * Sort the price table by symbol
   */
  sortPriceTable() {
    const tableBody = document.getElementById("price-table-body");
    if (!tableBody) return;

    const rows = Array.from(tableBody.children);
    rows.sort((a, b) => {
      const symbolA = a.id.replace("price-row-", "");
      const symbolB = b.id.replace("price-row-", "");
      return symbolA.localeCompare(symbolB);
    });

    // Re-append sorted rows
    rows.forEach((row) => tableBody.appendChild(row));
  }

  /**
   * Clear all real-time prices from the UI (frontend only)
   */
  clearPriceTable() {
    // Reset in-memory price cache
    this.priceData = {};

    // Reset table body to empty state
    const tableBody = document.getElementById("price-table-body");
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="4" class="px-6 py-4 text-center text-gray-500">No price data available</td>
        </tr>
      `;
    }
  }

  /**
   * View rule details in modal
   * @param {number} ruleId - ID of the rule to view
   */
  async viewRuleDetails(ruleId) {
    try {
      this.showLoading();

      // Fetch rule details
      const rule = await API.getRule(ruleId);

      // Populate modal with rule details
      document.getElementById("modal-rule-name").textContent = rule.name;
      document.getElementById("modal-rule-type").textContent = rule.is_system
        ? "System"
        : "Custom";
      document.getElementById("modal-rule-logic").textContent =
        rule.definition.logic;
      document.getElementById(
        "modal-rule-cooldown"
      ).textContent = `${rule.definition.cooldown_sec} seconds`;

      // Format dates
      const createdDate = new Date(rule.created_at).toLocaleString();
      const updatedDate = new Date(rule.updated_at).toLocaleString();
      document.getElementById("modal-rule-created").textContent = createdDate;
      document.getElementById("modal-rule-updated").textContent = updatedDate;

      // Populate conditions
      const conditionsContainer = document.getElementById(
        "modal-rule-conditions"
      );
      conditionsContainer.innerHTML = rule.definition.conditions
        .map((condition, index) => {
          let leftOperand = condition.left;
          let rightOperand = condition.right;

          // Handle custom numeric values
          if (typeof leftOperand === "number") {
            leftOperand = leftOperand.toString();
          }
          if (typeof rightOperand === "number") {
            rightOperand = rightOperand.toString();
          }

          return `
          <div class="p-3 bg-gray-50 rounded border border-gray-200">
            <div class="flex items-center space-x-2">
              <span class="text-sm font-medium text-gray-700">Condition ${
                index + 1
              }:</span>
              <span class="text-sm text-gray-900">${leftOperand}</span>
              <span class="text-sm font-medium text-blue-600">${
                condition.op
              }</span>
              <span class="text-sm text-gray-900">${rightOperand}</span>
            </div>
          </div>
        `;
        })
        .join("");

      // Show modal
      document.getElementById("rule-detail-modal").classList.remove("hidden");
    } catch (error) {
      console.error("Failed to load rule details:", error);
      this.showToast(`Failed to load rule details: ${error.message}`, "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Close the rule detail modal
   */
  closeRuleModal() {
    document.getElementById("rule-detail-modal").classList.add("hidden");
  }

  /**
   * Show signal detail modal
   */
  async showSignalDetail(signal) {
    try {
      this.showLoading();

      // Populate signal information
      const signalTime = signal.time || signal.timestamp;
      const signalDate = signalTime ? new Date(signalTime) : null;

      document.getElementById("signal-modal-symbol").textContent =
        signal.symbol;
      document.getElementById(
        "signal-modal-price"
      ).textContent = `$${signal.price}`;
      document.getElementById("signal-modal-date").textContent = signalDate
        ? signalDate.toLocaleDateString()
        : "Unknown";
      document.getElementById("signal-modal-time").textContent = signalDate
        ? signalDate.toLocaleTimeString()
        : "Unknown";

      // Fetch rule information
      let rule = null;
      if (signal.rule_id) {
        try {
          rule = await API.getRule(signal.rule_id);
        } catch (error) {
          console.warn("Failed to fetch rule details:", error);
        }
      }

      if (rule) {
        // Populate rule information
        document.getElementById("signal-modal-rule-name").textContent =
          rule.name || "Unknown";
        document.getElementById("signal-modal-rule-logic").textContent =
          rule.definition?.logic || rule.logic || "Unknown";
        document.getElementById("signal-modal-rule-cooldown").textContent = `${
          rule.definition?.cooldown_sec || rule.cooldown_sec || 60
        } seconds`;

        // Populate conditions
        const conditionsContainer = document.getElementById(
          "signal-modal-rule-conditions"
        );
        const conditions = rule.definition?.conditions || rule.conditions || [];

        if (conditions.length > 0) {
          conditionsContainer.innerHTML = conditions
            .map(
              (cond, idx) => `
              <div class="flex items-center space-x-2 text-xs bg-white border border-blue-200 rounded p-2">
                <span class="font-mono text-blue-700">${idx + 1}.</span>
                <span class="font-medium text-gray-700">${cond.left}</span>
                <span class="px-2 py-0.5 bg-blue-100 text-blue-800 rounded font-semibold">${
                  cond.op
                }</span>
                <span class="font-medium text-gray-700">${cond.right}</span>
              </div>
            `
            )
            .join("");
        } else {
          conditionsContainer.innerHTML =
            '<p class="text-xs text-gray-500">No conditions</p>';
        }
      } else {
        // Rule not found or unavailable
        document.getElementById("signal-modal-rule-name").textContent =
          "Rule not available";
        document.getElementById("signal-modal-rule-logic").textContent = "-";
        document.getElementById("signal-modal-rule-cooldown").textContent = "-";
        document.getElementById("signal-modal-rule-conditions").innerHTML =
          '<p class="text-xs text-gray-500">Rule information not available</p>';
      }

      // Show modal
      document.getElementById("signal-detail-modal").classList.remove("hidden");
    } catch (error) {
      console.error("Failed to show signal detail:", error);
      this.showToast("Failed to load signal details", "error");
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Close the signal detail modal
   */
  closeSignalModal() {
    document.getElementById("signal-detail-modal").classList.add("hidden");
  }
}

// Create global app instance
const App = new SignalGenApp();
