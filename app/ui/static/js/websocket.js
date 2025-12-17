/**
 * WebSocket Client for SignalGen
 *
 * This module handles real-time communication with the SignalGen WebSocket server.
 * It manages connection lifecycle, event handling, and reconnection logic.
 */

class WebSocketClient {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second
    this.eventHandlers = {};

    // Bind methods to maintain context
    this.connect = this.connect.bind(this);
    this.disconnect = this.disconnect.bind(this);
    this.handleConnect = this.handleConnect.bind(this);
    this.handleDisconnect = this.handleDisconnect.bind(this);
    this.handleError = this.handleError.bind(this);
    this.handleMessage = this.handleMessage.bind(this);
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.socket && this.socket.connected) {
      console.log("WebSocket already connected");
      return;
    }

    console.log("Connecting to WebSocket server...");

    // Connect to Socket.IO server
    this.socket = io("http://127.0.0.1:8765", {
      transports: ["websocket", "polling"],
      timeout: 5000,
      forceNew: true,
    });

    // Set up event listeners
    this.socket.on("connect", this.handleConnect);
    this.socket.on("disconnect", this.handleDisconnect);
    this.socket.on("connect_error", this.handleError);

    // Set up custom event listeners
    this.socket.on("signal", (data) => this.handleEvent("signal", data));
    this.socket.on("engine_status", (data) =>
      this.handleEvent("engine_status", data)
    );
    this.socket.on("rule_update", (data) =>
      this.handleEvent("rule_update", data)
    );
    this.socket.on("watchlist_update", (data) =>
      this.handleEvent("watchlist_update", data)
    );
    this.socket.on("price_update", (data) => {
      console.log("DEBUG: Received price_update event:", data);
      console.log(
        "DEBUG: Event data structure:",
        JSON.stringify(data, null, 2)
      );
      this.handleEvent("price_update", data);
    });
    this.socket.on("room_joined", (data) => {
      console.log("DEBUG: Successfully joined room:", data.room);
    });
    this.socket.on("error", (data) => this.handleEvent("error", data));
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.isConnected = false;
  }

  /**
   * Handle successful connection
   */
  handleConnect() {
    console.log("WebSocket connected successfully");
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;

    // Trigger connect event
    this.handleEvent("connect", { connected: true });

    // Join all necessary rooms (matching backend room names)
    this.socket.emit("join_room", { room: "prices" });
    this.socket.emit("join_room", { room: "engine_status" });
    this.socket.emit("join_room", { room: "signals" });
    console.log("DEBUG: Joined prices, engine_status, and signals rooms");
  }

  /**
   * Handle disconnection
   */
  handleDisconnect(reason) {
    console.log("WebSocket disconnected:", reason);
    this.isConnected = false;

    // Trigger disconnect event
    this.handleEvent("disconnect", { reason });

    // Attempt to reconnect if not intentional
    if (reason !== "io client disconnect") {
      this.attemptReconnect();
    }
  }

  /**
   * Handle connection errors
   */
  handleError(error) {
    console.error("WebSocket connection error:", error);
    this.isConnected = false;

    // Trigger error event
    this.handleEvent("connection_error", { error: error.message });

    // Attempt to reconnect
    this.attemptReconnect();
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max reconnection attempts reached");
      this.handleEvent("reconnect_failed", {
        attempts: this.reconnectAttempts,
      });
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(
      `Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`
    );

    setTimeout(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Handle incoming messages
   */
  handleMessage(event, data) {
    console.log(`WebSocket message [${event}]:`, data);
    this.handleEvent(event, data);
  }

  /**
   * Handle custom events
   */
  handleEvent(event, data) {
    // Call registered event handlers
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for ${event}:`, error);
        }
      });
    }
  }

  /**
   * Register event handler
   * @param {string} event - Event name
   * @param {Function} handler - Event handler function
   */
  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = [];
    }
    this.eventHandlers[event].push(handler);
  }

  /**
   * Remove event handler
   * @param {string} event - Event name
   * @param {Function} handler - Event handler function to remove
   */
  off(event, handler) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event] = this.eventHandlers[event].filter(
        (h) => h !== handler
      );
    }
  }

  /**
   * Send message to server
   * @param {string} event - Event name
   * @param {Object} data - Data to send
   */
  emit(event, data) {
    if (this.socket && this.socket.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn("Cannot emit event - WebSocket not connected");
    }
  }

  /**
   * Join a room for specific updates
   * @param {string} room - Room name
   */
  joinRoom(room) {
    this.emit("join", { room });
  }

  /**
   * Leave a room
   * @param {string} room - Room name
   */
  leaveRoom(room) {
    this.emit("leave", { room });
  }

  /**
   * Get connection status
   * @returns {boolean} Connection status
   */
  isSocketConnected() {
    return this.isConnected && this.socket && this.socket.connected;
  }
}

// Create global WebSocket client instance
const WS = new WebSocketClient();
