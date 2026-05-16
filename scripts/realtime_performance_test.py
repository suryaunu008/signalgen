"""
Automated real-time performance test for SignalGen.

This script drives the existing running application through its REST API and
Socket.IO events. It creates temporary watchlists, starts the real-time engine,
observes price/signal events, stops the engine, then prints a Markdown table.

Prerequisites:
- SignalGen API is running on --api-base (default http://127.0.0.1:3456).
- SignalGen Socket.IO server is running on --ws-url (default http://127.0.0.1:8765).
- IBKR TWS/IB Gateway is available if the test is expected to receive live data.
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import socketio


DEFAULT_CSV_DIR = Path("reports")


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {}
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = body
            raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot reach API at {url}: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Timed out calling {method} {url}. Make sure the app is running "
                "and the selected endpoint is responsive."
            ) from exc
        except socket.timeout as exc:
            raise RuntimeError(
                f"Timed out calling {method} {url}. Make sure the app is running "
                "and the selected endpoint is responsive."
            ) from exc


class EventCounter:
    def __init__(self, ws_url: str, transports: List[str]):
        self.ws_url = ws_url.rstrip("/")
        self.transports = transports
        self.client = socketio.Client(reconnection=True, request_timeout=10)
        self.lock = threading.Lock()
        self.connected = False
        self.reset()
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.client.event
        def connect():
            self.connected = True
            self.client.emit("join_room", {"room": "prices"})
            self.client.emit("join_room", {"room": "signals"})
            self.client.emit("join_room", {"room": "engine_status"})

        @self.client.event
        def disconnect():
            self.connected = False

        @self.client.on("price_update")
        def price_update(data):
            with self.lock:
                self.price_updates += 1
                symbol = data.get("symbol") if isinstance(data, dict) else None
                if symbol:
                    self.price_updates_by_symbol[symbol] = self.price_updates_by_symbol.get(symbol, 0) + 1

        @self.client.on("signal")
        def signal(data):
            with self.lock:
                self.signals += 1

        @self.client.on("engine_status")
        def engine_status(data):
            with self.lock:
                self.last_engine_status = data

        @self.client.on("error")
        def error(data):
            with self.lock:
                self.errors += 1
                self.error_messages.append(str(data))

    def connect(self) -> None:
        self.client.connect(self.ws_url, transports=self.transports, wait_timeout=10)

    def disconnect(self) -> None:
        if self.client.connected:
            self.client.disconnect()

    def reset(self) -> None:
        with getattr(self, "lock", threading.Lock()):
            self.price_updates = 0
            self.price_updates_by_symbol: Dict[str, int] = {}
            self.signals = 0
            self.errors = 0
            self.error_messages: List[str] = []
            self.last_engine_status: Dict[str, Any] = {}

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "price_updates": self.price_updates,
                "price_updates_by_symbol": dict(self.price_updates_by_symbol),
                "signals": self.signals,
                "errors": self.errors,
                "error_messages": list(self.error_messages),
                "last_engine_status": dict(self.last_engine_status),
            }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SignalGen real-time performance test.")
    parser.add_argument("--api-base", default="http://127.0.0.1:3456", help="SignalGen REST API base URL.")
    parser.add_argument("--ws-url", default="http://127.0.0.1:8765", help="SignalGen Socket.IO URL.")
    parser.add_argument(
        "--ws-transports",
        default="polling",
        help="Comma-separated Socket.IO transports. Default polling avoids local websocket 403 handshakes.",
    )
    parser.add_argument("--api-timeout", type=float, default=10.0, help="REST API timeout in seconds.")
    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,NVDA,AMZN,GOOGL,TSLA,META,AMD,NFLX,INTC",
        help="Comma-separated symbols.",
    )
    parser.add_argument("--scenarios", default="1,3,5,10", help="Comma-separated ticker counts to test.")
    parser.add_argument("--duration", type=int, default=300, help="Observation duration per scenario in seconds.")
    parser.add_argument("--settle-seconds", type=int, default=10, help="Seconds to wait after starting engine.")
    parser.add_argument("--rule-id", type=int, default=None, help="Rule ID. Defaults to the first available rule.")
    parser.add_argument(
        "--csv-out",
        default=None,
        help="CSV output path. Defaults to reports/realtime_performance_<timestamp>.csv.",
    )
    parser.add_argument(
        "--include-invalid-limit",
        action="store_true",
        help="Deprecated: ticker-count limit was removed, so this option is ignored.",
    )
    return parser.parse_args()


def pick_rule_id(api: ApiClient, requested_rule_id: Optional[int]) -> int:
    if requested_rule_id:
        return requested_rule_id
    rules = api.request("GET", "/api/rules")
    if not rules:
        raise RuntimeError("No rules available. Create at least one rule before running the test.")
    return int(rules[0]["id"])


def stop_engine_if_running(api: ApiClient, wait_seconds: int = 20) -> None:
    try:
        api.request("POST", "/api/engine/stop")
    except RuntimeError as exc:
        if "409" not in str(exc) and "Engine is not running" not in str(exc):
            raise

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(1)
        try:
            status = api.request("GET", "/api/engine/status")
        except RuntimeError:
            return
        if not status.get("is_running"):
            return


def get_engine_status_or_unknown(api: ApiClient) -> Dict[str, Any]:
    try:
        return api.request("GET", "/api/engine/status")
    except RuntimeError as exc:
        return {
            "is_running": None,
            "ibkr_connected": None,
            "subscribed_symbols": [],
            "status_error": str(exc),
        }


def create_watchlist(api: ApiClient, symbols: List[str], scenario_label: str) -> Dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    payload = {
        "name": f"PERF-{scenario_label}-{timestamp}",
        "symbols": symbols,
    }
    return api.request("POST", "/api/watchlists", payload)


def delete_watchlist(api: ApiClient, watchlist_id: int) -> None:
    try:
        api.request("DELETE", f"/api/watchlists/{watchlist_id}")
    except RuntimeError:
        pass


def wait_with_progress(seconds: int) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        print(f"\rObserving... {remaining:>4}s remaining", end="", flush=True)
        time.sleep(min(5, max(1, remaining)))
    print("\rObserving... done                ")


def run_scenario(
    api: ApiClient,
    events: EventCounter,
    rule_id: int,
    symbols: List[str],
    duration: int,
    settle_seconds: int,
) -> Dict[str, Any]:
    label = f"K-{len(symbols):02d}"
    watchlist_id: Optional[int] = None
    start_ok = False
    error_message = ""

    try:
        stop_engine_if_running(api)
        watchlist = create_watchlist(api, symbols, label)
        watchlist_id = int(watchlist["id"])

        events.reset()
        api.request("POST", "/api/engine/start", {"watchlist_id": watchlist_id, "rule_id": rule_id})
        start_ok = True
        time.sleep(settle_seconds)
        wait_with_progress(duration)

        status = get_engine_status_or_unknown(api)
        snapshot = events.snapshot()
        subscribed = status.get("subscribed_symbols") or []
        ticker_count = len(symbols)
        subscribed_count = len(subscribed)
        subscription_pct = (subscribed_count / ticker_count) * 100 if ticker_count else 0
        if status.get("is_running") is None:
            engine_status = "Unknown"
        else:
            engine_status = "Running" if status.get("is_running") else "Stopped"
        if status.get("ibkr_connected") is None:
            ibkr_status = "Unknown"
        else:
            ibkr_status = "Connected" if status.get("ibkr_connected") else "Disconnected"
        errors = snapshot["errors"] + (1 if status.get("status_error") else 0)
        conclusion = "Stabil" if start_ok and status.get("is_running") and subscribed_count == ticker_count and errors == 0 else "Tidak stabil"

        return {
            "Skenario": label,
            "Jumlah Ticker": ticker_count,
            "Durasi (detik)": duration,
            "Ticker Tersubscribe": subscribed_count,
            "Keberhasilan Subscription": f"{subscription_pct:.0f}%",
            "Status Engine": engine_status,
            "Status IBKR": ibkr_status,
            "Update Harga": snapshot["price_updates"],
            "Sinyal": snapshot["signals"],
            "Error": errors,
            "Kesimpulan": conclusion,
        }
    except Exception as exc:
        error_message = str(exc)
        return {
            "Skenario": label,
            "Jumlah Ticker": len(symbols),
            "Durasi (detik)": duration,
            "Ticker Tersubscribe": 0,
            "Keberhasilan Subscription": "0%",
            "Status Engine": "Error",
            "Status IBKR": "Unknown",
            "Update Harga": 0,
            "Sinyal": 0,
            "Error": 1,
            "Kesimpulan": f"Tidak stabil ({error_message})",
        }
    finally:
        stop_engine_if_running(api)
        if watchlist_id is not None:
            delete_watchlist(api, watchlist_id)


def print_markdown_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def default_csv_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(DEFAULT_CSV_DIR / f"realtime_performance_{timestamp}.csv")


def main() -> int:
    args = parse_args()
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    scenarios = [int(value.strip()) for value in args.scenarios.split(",") if value.strip()]

    if len(symbols) < max(scenarios, default=0):
        print("Jumlah symbols kurang untuk skenario yang diminta.", file=sys.stderr)
        return 2

    api = ApiClient(args.api_base, timeout=args.api_timeout)
    api.request("GET", "/")
    rule_id = pick_rule_id(api, args.rule_id)

    transports = [transport.strip() for transport in args.ws_transports.split(",") if transport.strip()]
    events = EventCounter(args.ws_url, transports=transports)
    try:
        events.connect()
    except Exception as exc:
        print(
            f"Warning: could not connect to Socket.IO at {args.ws_url} using {transports}: {exc}. "
            "Continuing with REST status metrics only.",
            file=sys.stderr,
        )

    rows: List[Dict[str, Any]] = []
    try:
        for count in scenarios:
            scenario_symbols = symbols[:count]
            print(f"\nRunning scenario with {count} ticker(s): {', '.join(scenario_symbols)}")
            rows.append(run_scenario(api, events, rule_id, scenario_symbols, args.duration, args.settle_seconds))

        if args.include_invalid_limit:
            print("Note: --include-invalid-limit ignored because the internal 5-ticker limit has been removed.")
    finally:
        events.disconnect()
        stop_engine_if_running(api)

    print("\nHasil Pengujian Kinerja Sistem\n")
    print_markdown_table(rows)

    csv_path = args.csv_out or default_csv_path()
    write_csv(csv_path, rows)
    print(f"\nCSV written to: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
