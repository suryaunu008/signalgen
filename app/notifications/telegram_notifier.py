"""
Telegram Notifier Module

This module provides Telegram notification capabilities for trading signals.
It integrates with the Telegram Bot API to send real-time signal alerts
to subscribed users.

Key Features:
- Async message delivery via Telegram Bot API
- Rich formatted messages with signal details
- Configurable via application settings
- Error handling and retry logic
- Support for multiple chat IDs
- Signal formatting with emojis and markdown

Configuration:
- telegram_bot_token: Bot token from BotFather
- telegram_chat_ids: Comma-separated list of chat IDs

Typical Usage:
    notifier = TelegramNotifier(repository)
    await notifier.initialize()
    await notifier.send_signal(signal_data)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp


class TelegramNotifier:
    """
    Telegram notification service for trading signals.
    
    This class handles sending formatted trading signals to Telegram
    chat IDs configured in the system settings.
    """
    
    def __init__(self, repository):
        """
        Initialize Telegram notifier.
        
        Args:
            repository: SQLite repository instance for settings
        """
        self.logger = logging.getLogger(__name__)
        self.repository = repository
        self.bot_token: Optional[str] = None
        self.chat_ids: List[str] = []
        self.enabled = False
        self.api_base_url = "https://api.telegram.org/bot{token}"
        
    async def initialize(self) -> bool:
        """
        Initialize notifier by loading settings from repository.
        
        Returns:
            bool: True if successfully initialized and enabled
        """
        try:
            # Load bot token from settings
            self.bot_token = self.repository.get_setting('telegram_bot_token')
            
            # Load chat IDs from settings
            chat_ids_str = self.repository.get_setting('telegram_chat_ids', '')
            if chat_ids_str:
                self.chat_ids = [
                    chat_id.strip() 
                    for chat_id in str(chat_ids_str).split(',') 
                    if chat_id.strip()
                ]
            
            # Check if enabled
            self.enabled = self.repository.get_setting('telegram_enabled', False)
            
            if self.enabled and self.bot_token and self.chat_ids:
                self.logger.info(
                    f"Telegram notifier initialized successfully. "
                    f"Enabled: {self.enabled}, Chat IDs: {len(self.chat_ids)}"
                )
                return True
            else:
                if not self.bot_token:
                    self.logger.warning("Telegram bot token not configured")
                if not self.chat_ids:
                    self.logger.warning("No Telegram chat IDs configured")
                if not self.enabled:
                    self.logger.info("Telegram notifications disabled in settings")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram notifier: {e}")
            self.enabled = False
            return False
    
    async def send_signal(self, signal_data: Dict[str, Any]) -> bool:
        """
        Send trading signal notification to Telegram.
        
        Args:
            signal_data: Signal data dictionary containing signal details
            
        Returns:
            bool: True if sent successfully to at least one chat
        """
        if not self.enabled:
            self.logger.debug("Telegram notifier is disabled, skipping notification")
            return False
        
        if not self.bot_token or not self.chat_ids:
            self.logger.warning("Telegram not properly configured, skipping notification")
            return False
        
        try:
            # Format message
            message = self._format_signal_message(signal_data)
            
            # Send to all configured chat IDs
            tasks = [
                self._send_message(chat_id, message) 
                for chat_id in self.chat_ids
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check if at least one succeeded
            success_count = sum(1 for r in results if r is True)
            
            if success_count > 0:
                self.logger.info(
                    f"Telegram notification sent successfully to {success_count}/{len(self.chat_ids)} chats"
                )
                return True
            else:
                self.logger.error("Failed to send Telegram notification to any chat")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def _format_signal_message(self, signal_data: Dict[str, Any]) -> str:
        """
        Format signal data into a readable Telegram message.
        
        Args:
            signal_data: Signal data dictionary
            
        Returns:
            str: Formatted message with markdown
        """
        try:
            symbol = signal_data.get('symbol', 'UNKNOWN')
            signal_type = signal_data.get('type', 'UNKNOWN')
            timestamp = signal_data.get('timestamp', datetime.now().isoformat())
            rule_name = signal_data.get('rule_name', 'N/A')
            
            # Get indicator values if available
            indicators = signal_data.get('indicator_values', {})
            price = signal_data.get('price', indicators.get('close', 'N/A'))
            
            # Signal emoji
            emoji = "🚀" if signal_type.upper() == "BUY" else "🔻" if signal_type.upper() == "SELL" else "⚠️"
            
            # Build message
            message_lines = [
                f"{emoji} *SIGNAL TRADING ALERT*",
                "",
                f"*Symbol:* `{symbol}`",
                f"*Type:* *{signal_type.upper()}*",
                f"*Price:* {self._format_price(price)}",
                f"*Time:* {self._format_timestamp(timestamp)}",
                f"*Rule:* {rule_name}",
            ]
            
            # Add key indicators if available
            if indicators:
                message_lines.append("")
                message_lines.append("*📊 Indicators:*")
                
                # Common indicators to show
                key_indicators = ['rsi', 'macd', 'signal', 'bb_upper', 'bb_lower', 'adx']
                for key in key_indicators:
                    if key in indicators and indicators[key] is not None:
                        value = indicators[key]
                        formatted_value = f"{float(value):.2f}" if isinstance(value, (int, float)) else str(value)
                        display_name = key.replace('_', ' ').upper()
                        message_lines.append(f"  • {display_name}: `{formatted_value}`")
            
            # Add footer
            message_lines.append("")
            message_lines.append("_SignalGen Trading System_")
            
            return "\n".join(message_lines)
            
        except Exception as e:
            self.logger.error(f"Error formatting signal message: {e}")
            return f"⚠️ Signal Alert: {signal_data.get('symbol', 'UNKNOWN')} - {signal_data.get('type', 'UNKNOWN')}"
    
    def _format_price(self, price: Any) -> str:
        """Format price value."""
        try:
            if isinstance(price, (int, float)):
                return f"${float(price):.2f}"
            return str(price)
        except:
            return "N/A"
    
    def _format_timestamp(self, timestamp: Any) -> str:
        """Format timestamp for display."""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                return str(timestamp)
            
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(timestamp)
    
    async def _send_message(self, chat_id: str, message: str) -> bool:
        """
        Send message to specific Telegram chat.
        
        Args:
            chat_id: Telegram chat ID
            message: Message text to send
            
        Returns:
            bool: True if sent successfully
        """
        if not self.bot_token:
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        self.logger.debug(f"Message sent successfully to chat {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(
                            f"Failed to send message to chat {chat_id}: "
                            f"Status {response.status}, Response: {error_text}"
                        )
                        return False
                        
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout sending message to chat {chat_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message to chat {chat_id}: {e}")
            return False
    
    async def send_test_message(self, chat_id: Optional[str] = None) -> bool:
        """
        Send a test message to verify configuration.
        
        Args:
            chat_id: Specific chat ID to test, or None for all configured chats
            
        Returns:
            bool: True if test message sent successfully
        """
        if not self.bot_token:
            self.logger.error("Bot token not configured")
            return False
        
        test_message = (
            "✅ *Telegram Notifier Test*\n\n"
            "Your SignalGen bot is configured correctly!\n"
            "You will receive trading signal notifications here.\n\n"
            f"_Test sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        )
        
        if chat_id:
            return await self._send_message(chat_id, test_message)
        else:
            if not self.chat_ids:
                self.logger.error("No chat IDs configured")
                return False
            
            tasks = [self._send_message(cid, test_message) for cid in self.chat_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return any(r is True for r in results)
    
    async def send_engine_status(self, status: str, message: str = "") -> bool:
        """
        Send engine status notification.
        
        Args:
            status: Status type (started, stopped, error)
            message: Additional status message
            
        Returns:
            bool: True if sent successfully
        """
        if not self.enabled or not self.bot_token or not self.chat_ids:
            return False
        
        emoji_map = {
            'started': '▶️',
            'stopped': '⏹️',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        emoji = emoji_map.get(status.lower(), '📢')
        
        notification = (
            f"{emoji} *Engine Status Update*\n\n"
            f"*Status:* {status.upper()}\n"
        )
        
        if message:
            notification += f"*Message:* {message}\n"
        
        notification += f"\n_Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        
        try:
            tasks = [self._send_message(chat_id, notification) for chat_id in self.chat_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return any(r is True for r in results)
        except Exception as e:
            self.logger.error(f"Error sending engine status: {e}")
            return False
