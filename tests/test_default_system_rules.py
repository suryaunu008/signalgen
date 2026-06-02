from app.core.rule_engine import RuleEngine
from app.storage.init_db import initialize_database
from app.storage.sqlite_repo import SQLiteRepository


def test_default_system_rules_are_loose_and_do_not_use_relative_volume(tmp_path):
    db_path = tmp_path / "signalgen.db"
    initialize_database(str(db_path))

    repo = SQLiteRepository(str(db_path))
    rules = repo.get_system_rules()
    rule_engine = RuleEngine()

    names = {rule["name"] for rule in rules}
    assert {
        "Default Scalping",
        "EMA Momentum Scalping",
        "BB Pullback Scalping",
        "Trend Continuation Scalping",
    }.issubset(names)

    for rule in rules:
        definition = rule["definition"]
        rule_engine.validate_rule(definition)
        operands = [
            condition[side]
            for condition in definition.get("conditions", [])
            for side in ("left", "right")
            if isinstance(condition.get(side), str)
        ]
        assert not any(operand.startswith("REL_VOLUME") for operand in operands)

