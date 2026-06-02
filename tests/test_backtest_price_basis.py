import pytest
from pydantic import ValidationError

from app.app import BacktestScreenRequest, ManualBacktestEntry


def test_backtest_screen_request_accepts_entry_and_exit_price_basis():
    request = BacktestScreenRequest(
        mode="manual",
        timeframe="5m",
        n_steps=3,
        data_source="yahoo",
        entry_price_basis="open",
        exit_price_basis="close",
        manual_entries=[
            ManualBacktestEntry(
                symbol="AAPL",
                entry_time="2026-05-01T09:35",
                signal_type="BUY",
                entry_price=192.5,
            )
        ],
    )

    assert request.entry_price_basis == "open"
    assert request.exit_price_basis == "close"
    assert request.manual_entries[0].entry_price == 192.5


def test_backtest_screen_request_rejects_invalid_price_basis():
    with pytest.raises(ValidationError):
        BacktestScreenRequest(
            mode="manual",
            timeframe="5m",
            n_steps=3,
            data_source="yahoo",
            entry_price_basis="last",
            exit_price_basis="close",
            manual_entries=[
                {"symbol": "AAPL", "entry_time": "2026-05-01T09:35", "signal_type": "BUY"}
            ],
        )

