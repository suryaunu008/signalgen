"""
Notifications Module

This module provides notification capabilities for the SignalGen system.
It supports multiple notification channels including Telegram.

Components:
- TelegramNotifier: Send trading signals via Telegram Bot
"""

from .telegram_notifier import TelegramNotifier

__all__ = ['TelegramNotifier']
