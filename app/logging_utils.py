"""
In-memory log buffering and real-time broadcasting.

Keeps a rolling buffer of formatted log lines since process start (used to
serve the initial state of the "Application Logs" modal) and pushes each new
line to connected WebSocket clients in real time via the Socket.IO
broadcaster, once one is attached.
"""

import logging
from collections import deque
from typing import Optional


class InMemoryLogHandler(logging.Handler):
    """Logging handler that buffers formatted lines and broadcasts them live."""

    def __init__(self, capacity: int = 5000):
        super().__init__()
        self.buffer = deque(maxlen=capacity)
        self.broadcaster = None

    def get_buffer_text(self, lines: Optional[int] = None) -> str:
        entries = list(self.buffer)
        if lines is not None:
            entries = entries[-lines:]
        return ("\n".join(entries) + "\n") if entries else ""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return

        self.buffer.append(line)

        broadcaster = self.broadcaster
        if broadcaster is not None:
            try:
                broadcaster.broadcast_log_entry_sync(line)
            except Exception:
                pass


# Module-level singleton shared between main.py (attaches it to the root
# logger and later sets .broadcaster) and app.py (reads the buffer for the
# /api/logs endpoint).
log_handler = InMemoryLogHandler()
