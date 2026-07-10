import pytest
from pydantic import ValidationError

from app.app import BacktestScreenRequest, ManualBacktestEntry


def _manual_entry():
    return ManualBacktestEntry(
        symbol="AAPL", entry_time="2026-05-01T09:35", signal_type="BUY", entry_price=192.5
    )


def test_capital_and_sizing_defaults():
    req = BacktestScreenRequest(
        mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
        manual_entries=[_manual_entry()],
    )
    assert req.initial_capital == 10000.0
    assert req.position_sizing == "percent_equity"
    assert req.position_size == 100.0
    assert req.commission_pct == 0.0
    assert req.slippage_pct == 0.0
    assert req.exit_strategy == "holding_period"


def test_capital_fields_accept_custom_values():
    req = BacktestScreenRequest(
        mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
        initial_capital=25000, position_sizing="fixed_amount", position_size=1500,
        commission_pct=0.1, slippage_pct=0.05, manual_entries=[_manual_entry()],
    )
    assert req.initial_capital == 25000
    assert req.position_sizing == "fixed_amount"
    assert req.position_size == 1500
    assert req.commission_pct == 0.1
    assert req.slippage_pct == 0.05


def test_rejects_zero_initial_capital():
    with pytest.raises(ValidationError):
        BacktestScreenRequest(
            mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
            initial_capital=0, manual_entries=[_manual_entry()],
        )


def test_rejects_invalid_position_sizing():
    with pytest.raises(ValidationError):
        BacktestScreenRequest(
            mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
            position_sizing="martingale", manual_entries=[_manual_entry()],
        )


@pytest.mark.parametrize("strategy", ["holding_period", "target_stop", "exit_signal"])
def test_exit_strategy_accepts_valid_values(strategy):
    req = BacktestScreenRequest(
        mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
        exit_strategy=strategy, take_profit_pct=2, stop_loss_pct=3, exit_rule_id=1,
        manual_entries=[_manual_entry()],
    )
    assert req.exit_strategy == strategy


def test_rejects_invalid_exit_strategy():
    with pytest.raises(ValidationError):
        BacktestScreenRequest(
            mode="manual", timeframe="5m", n_steps=3, data_source="yahoo",
            exit_strategy="hodl", manual_entries=[_manual_entry()],
        )
