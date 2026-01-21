/**
 * Telegram Settings Management
 *
 * This module handles Telegram notification configuration in the UI.
 */

class TelegramSettings {
  constructor() {
    this.settings = {
      bot_token: "",
      chat_ids: "",
      enabled: false,
    };

    this.init();
  }

  async init() {
    await this.loadSettings();
    this.setupEventListeners();
  }

  async loadSettings() {
    try {
      const response = await fetch("/api/telegram/settings");
      if (response.ok) {
        this.settings = await response.json();
        this.updateUI();
      }
    } catch (error) {
      console.error("Failed to load Telegram settings:", error);
      this.showNotification("Failed to load settings", "error");
    }
  }

  updateUI() {
    const tokenInput = document.getElementById("telegram-bot-token");
    const chatIdsInput = document.getElementById("telegram-chat-ids");
    const enabledCheckbox = document.getElementById("telegram-enabled");

    if (tokenInput) tokenInput.value = this.settings.bot_token || "";
    if (chatIdsInput) chatIdsInput.value = this.settings.chat_ids || "";
    if (enabledCheckbox)
      enabledCheckbox.checked = this.settings.enabled || false;

    this.updateStatus();
  }

  updateStatus() {
    const statusElement = document.getElementById("telegram-status");
    if (!statusElement) return;

    const hasToken =
      this.settings.bot_token && !this.settings.bot_token.startsWith("...");
    const hasChatIds =
      this.settings.chat_ids && this.settings.chat_ids.length > 0;
    const isEnabled = this.settings.enabled;

    let status = "";
    let className = "";

    if (!hasToken) {
      status = "⚠️ Bot token not configured";
      className = "status-warning";
    } else if (!hasChatIds) {
      status = "⚠️ Chat IDs not configured";
      className = "status-warning";
    } else if (!isEnabled) {
      status = "⏸️ Disabled";
      className = "status-disabled";
    } else {
      status = "✅ Active";
      className = "status-active";
    }

    statusElement.textContent = status;
    statusElement.className = `telegram-status ${className}`;
  }

  setupEventListeners() {
    // Save button
    const saveBtn = document.getElementById("telegram-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => this.saveSettings());
    }

    // Test button
    const testBtn = document.getElementById("telegram-test-btn");
    if (testBtn) {
      testBtn.addEventListener("click", () => this.sendTestMessage());
    }

    // Enable checkbox
    const enabledCheckbox = document.getElementById("telegram-enabled");
    if (enabledCheckbox) {
      enabledCheckbox.addEventListener("change", () => {
        this.settings.enabled = enabledCheckbox.checked;
        this.updateStatus();
      });
    }
  }

  async saveSettings() {
    const tokenInput = document.getElementById("telegram-bot-token");
    const chatIdsInput = document.getElementById("telegram-chat-ids");
    const enabledCheckbox = document.getElementById("telegram-enabled");

    const newSettings = {};

    // Only update if value changed and not masked
    const newToken = tokenInput?.value.trim();
    if (newToken && !newToken.startsWith("...")) {
      newSettings.bot_token = newToken;
    }

    if (chatIdsInput) {
      newSettings.chat_ids = chatIdsInput.value.trim();
    }

    if (enabledCheckbox) {
      newSettings.enabled = enabledCheckbox.checked;
    }

    try {
      const response = await fetch("/api/telegram/settings", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newSettings),
      });

      if (response.ok) {
        const result = await response.json();
        this.showNotification("Settings saved successfully", "success");
        await this.loadSettings(); // Reload to get masked token
      } else {
        const error = await response.json();
        this.showNotification(`Failed to save: ${error.detail}`, "error");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      this.showNotification("Failed to save settings", "error");
    }
  }

  async sendTestMessage() {
    const testBtn = document.getElementById("telegram-test-btn");
    if (!testBtn) return;

    // Disable button during test
    testBtn.disabled = true;
    testBtn.textContent = "Sending...";

    try {
      const response = await fetch("/api/telegram/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        this.showNotification(
          "✅ Test message sent! Check your Telegram.",
          "success",
        );
      } else {
        const error = await response.json();
        this.showNotification(`❌ Test failed: ${error.detail}`, "error");
      }
    } catch (error) {
      console.error("Error sending test message:", error);
      this.showNotification("Failed to send test message", "error");
    } finally {
      testBtn.disabled = false;
      testBtn.textContent = "Send Test Message";
    }
  }

  showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // Add to document
    const container =
      document.getElementById("notification-container") || document.body;
    container.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      notification.remove();
    }, 5000);
  }
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    window.telegramSettings = new TelegramSettings();
  });
} else {
  window.telegramSettings = new TelegramSettings();
}
