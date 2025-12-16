/**
 * API Client for SignalGen
 *
 * This module provides a clean interface for communicating with the SignalGen REST API.
 * It handles all HTTP requests, error handling, and response formatting.
 */

class ApiClient {
  constructor() {
    this.baseURL = "http://127.0.0.1:3456";
    this.defaultHeaders = {
      "Content-Type": "application/json",
    };
  }

  /**
   * Make a generic HTTP request
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Request options
   * @returns {Promise} Response data
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: { ...this.defaultHeaders, ...options.headers },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }

  /**
   * GET request
   * @param {string} endpoint - API endpoint
   * @param {Object} params - Query parameters
   * @returns {Promise} Response data
   */
  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url, { method: "GET" });
  }

  /**
   * POST request
   * @param {string} endpoint - API endpoint
   * @param {Object} data - Request body data
   * @returns {Promise} Response data
   */
  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * PUT request
   * @param {string} endpoint - API endpoint
   * @param {Object} data - Request body data
   * @returns {Promise} Response data
   */
  async put(endpoint, data = {}) {
    return this.request(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  /**
   * DELETE request
   * @param {string} endpoint - API endpoint
   * @returns {Promise} Response data
   */
  async delete(endpoint) {
    return this.request(endpoint, { method: "DELETE" });
  }

  // Health and Status
  async getHealth() {
    return this.get("/api/health");
  }

  async getSystemStatus() {
    return this.get("/api/status");
  }

  // Rules API
  async getAllRules() {
    return this.get("/api/rules");
  }

  async getRule(ruleId) {
    return this.get(`/api/rules/${ruleId}`);
  }

  async createRule(ruleData) {
    return this.post("/api/rules", ruleData);
  }

  async updateRule(ruleId, ruleData) {
    return this.put(`/api/rules/${ruleId}`, ruleData);
  }

  async deleteRule(ruleId) {
    return this.delete(`/api/rules/${ruleId}`);
  }

  async activateRule(ruleId) {
    return this.put(`/api/rules/${ruleId}/activate`);
  }

  // Watchlists API
  async getAllWatchlists() {
    return this.get("/api/watchlists");
  }

  async getWatchlist(watchlistId) {
    return this.get(`/api/watchlists/${watchlistId}`);
  }

  async createWatchlist(watchlistData) {
    return this.post("/api/watchlists", watchlistData);
  }

  async updateWatchlist(watchlistId, watchlistData) {
    return this.put(`/api/watchlists/${watchlistId}`, watchlistData);
  }

  async deleteWatchlist(watchlistId) {
    return this.delete(`/api/watchlists/${watchlistId}`);
  }

  async activateWatchlist(watchlistId) {
    return this.put(`/api/watchlists/${watchlistId}/activate`);
  }

  // Engine API
  async getEngineStatus() {
    return this.get("/api/engine/status");
  }

  async startEngine(engineConfig) {
    return this.post("/api/engine/start", engineConfig);
  }

  async stopEngine() {
    return this.post("/api/engine/stop");
  }

  // Signals API
  async getSignals(limit = 100, symbol = null) {
    const params = { limit };
    if (symbol) params.symbol = symbol;
    return this.get("/api/signals", params);
  }

  // Settings API
  async getSetting(key) {
    return this.get(`/api/settings/${key}`);
  }

  async getAllSettings() {
    return this.get("/api/settings");
  }

  async setSetting(key, value) {
    return this.put(`/api/settings/${key}`, { value });
  }
}

// Create global API client instance
const API = new ApiClient();
