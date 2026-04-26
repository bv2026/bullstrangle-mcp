"""Unit tests for rule_catalog.py — Phase 2.

All tests are self-contained (no PDF required).
"""
from __future__ import annotations

import json

import pytest

from bullstrangle_mcp.database import connect, initialize_database
from bullstrangle_mcp.rule_catalog import (
    RuleDefinition,
    _SEED_RULES,
    get_gate_rules,
    get_rule,
    list_rule_catalog,
    load_rule_catalog,
)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


EXPECTED_RULE_COUNT = len(_SEED_RULES)  # 47 rules across 8 areas


def test_load_rule_catalog_seeds_all_rules(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    inserted = load_rule_catalog(db)
    assert inserted == EXPECTED_RULE_COUNT

    with connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM strategy_rule_catalog").fetchone()[0]
    assert count == EXPECTED_RULE_COUNT


def test_load_rule_catalog_is_idempotent(tmp_path):
    """Second call must not raise and must return 0 inserts (INSERT OR IGNORE)."""
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    load_rule_catalog(db)
    second = load_rule_catalog(db)
    assert second == 0

    with connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM strategy_rule_catalog").fetchone()[0]
    assert count == EXPECTED_RULE_COUNT


def test_all_seed_rules_have_required_fields():
    required = {"rule_id", "rule_area", "rule_type", "description", "parameters_json"}
    for rule in _SEED_RULES:
        missing = required - rule.keys()
        assert not missing, f"{rule['rule_id']} missing fields: {missing}"


def test_all_seed_rule_ids_are_unique():
    ids = [r["rule_id"] for r in _SEED_RULES]
    assert len(ids) == len(set(ids)), "Duplicate rule_ids detected"


def test_all_seed_parameters_json_is_valid_json():
    for rule in _SEED_RULES:
        try:
            json.loads(rule["parameters_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            pytest.fail(f"{rule['rule_id']}: invalid parameters_json — {exc}")


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------


def test_get_rule_returns_correct_rule(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rule = get_rule(db, "GATE-SS-001")
    assert rule.rule_id == "GATE-SS-001"
    assert rule.rule_area == "stock_selection"
    assert rule.rule_type == "hard_gate"
    assert rule.parameters["max_iv"] == 1.0
    assert rule.parameters["comparator"] == "<"


def test_get_rule_earnings_clearance_threshold(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rule = get_rule(db, "GATE-SS-005")
    assert rule.parameters["min_earnings_clear_days"] == 45


def test_get_rule_raises_key_error_for_unknown_id(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    with pytest.raises(KeyError, match="NONEXISTENT"):
        get_rule(db, "NONEXISTENT")


def test_get_rule_raises_key_error_on_empty_catalog(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)  # schema exists but no rules seeded

    with pytest.raises(KeyError):
        get_rule(db, "GATE-SS-001")


# ---------------------------------------------------------------------------
# get_gate_rules / filtering
# ---------------------------------------------------------------------------


def test_get_gate_rules_by_area(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rules = get_gate_rules(db, rule_area="earnings")
    areas = {r.rule_area for r in rules}
    assert areas == {"earnings"}
    assert len(rules) >= 4  # GATE-SS-005 + RULE-EARN-001 through 004


def test_get_gate_rules_hard_gates_only(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rules = get_gate_rules(db, rule_type="hard_gate")
    assert all(r.rule_type == "hard_gate" for r in rules)
    expected = sum(1 for r in _SEED_RULES if r["rule_type"] == "hard_gate")
    assert len(rules) == expected


def test_get_gate_rules_area_and_type_combined(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rules = get_gate_rules(db, rule_area="stock_selection", rule_type="hard_gate")
    assert all(r.rule_area == "stock_selection" for r in rules)
    assert all(r.rule_type == "hard_gate" for r in rules)


def test_get_gate_rules_returns_all_when_no_filter(tmp_path):
    db = tmp_path / "bullstrangle.db"
    load_rule_catalog(db)

    rules = get_gate_rules(db)
    assert len(rules) == EXPECTED_RULE_COUNT


# ---------------------------------------------------------------------------
# RuleDefinition
# ---------------------------------------------------------------------------


def test_rule_definition_parses_parameters_json():
    rd = RuleDefinition(
        rule_id="TEST-001",
        rule_area="test",
        rule_type="hard_gate",
        source_section="Test",
        description="Test rule",
        parameters_json='{"max_iv": 1.0, "comparator": "<"}',
        data_column_mapping="test.column",
    )
    assert rd.parameters == {"max_iv": 1.0, "comparator": "<"}
    assert rd.get_param("max_iv") == 1.0
    assert rd.get_param("missing", default=99) == 99


def test_rule_definition_handles_invalid_json_gracefully():
    rd = RuleDefinition(
        rule_id="TEST-002",
        rule_area="test",
        rule_type="hard_gate",
        source_section="",
        description="Bad JSON",
        parameters_json="NOT JSON",
        data_column_mapping="",
    )
    assert rd.parameters == {}


# ---------------------------------------------------------------------------
# list_rule_catalog (MCP-shaped output)
# ---------------------------------------------------------------------------


def test_list_rule_catalog_auto_seeds_and_returns_dicts(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    results = list_rule_catalog(db)
    assert len(results) == EXPECTED_RULE_COUNT
    first = results[0]
    # Must have the MCP-friendly keys
    assert "rule_id" in first
    assert "parameters" in first
    assert isinstance(first["parameters"], dict)


def test_list_rule_catalog_filter_by_area(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    results = list_rule_catalog(db, rule_area="formula")
    assert all(r["rule_area"] == "formula" for r in results)
    expected_formula = sum(1 for r in _SEED_RULES if r["rule_area"] == "formula")
    assert len(results) == expected_formula


def test_list_rule_catalog_second_call_does_not_duplicate(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    list_rule_catalog(db)
    list_rule_catalog(db)

    with connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM strategy_rule_catalog").fetchone()[0]
    assert count == EXPECTED_RULE_COUNT
