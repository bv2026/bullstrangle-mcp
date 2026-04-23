"""Unit tests for the decision-chain internals.

Covers:
- load_decision_rules: DB read, fallback, inactive-row handling
- _build_bull_decision / _build_dca_decision: rules_applied_json correctness,
  no KeyError regression when full rules dict is passed
- _build_rule_diagnostics: passes/fails with tight vs loose thresholds,
  DCA action uses bull_strangle credit threshold

No PDF required.  DB tests use tmp_path + initialize_database.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from bullstrangle_mcp.database import connect, initialize_database
from bullstrangle_mcp.decisions import (
    DEFAULT_RULES,
    _build_bull_decision,
    _build_dca_decision,
    _build_rule_diagnostics,
    _build_strategy_context,
    load_decision_rules,
)


# ── shared helpers ────────────────────────────────────────────────────────────

def _approved_market() -> dict[str, Any]:
    return {
        "deployment_approved": 1,
        "investment_percent": 100,
        "hybrid_score": 2,
        "market_status": "green",
        "market_regime": "full_exposure",
    }


def _week_row(
    symbol: str = "NTAP",
    stock_price: float = 100.0,
    latest_total_credit: float | None = 2.50,
    latest_live_stock_price: float | None = 99.0,
    sell_call_strike: float | None = 104.0,
    worst_abs_stock_price_deviation_pct: float | None = 0.01,
    worst_abs_total_credit_deviation: float | None = 0.20,
    is_week_valid: int = 1,
    is_favorite: int = 0,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "stock_price": stock_price,
        "latest_total_credit": latest_total_credit,
        "latest_live_stock_price": latest_live_stock_price,
        "sell_call_strike": sell_call_strike,
        "worst_abs_stock_price_deviation_pct": worst_abs_stock_price_deviation_pct,
        "worst_abs_total_credit_deviation": worst_abs_total_credit_deviation,
        "is_week_valid": is_week_valid,
        "is_favorite": is_favorite,
        "newsletter_id": 1,
        "newsletter_date": "2026-04-17",
        "expiration_date": "2026-05-15",
        "entry_id": 1,
    }


def _ctx(
    row: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
    position: dict[str, Any] | None = None,
    short_list_symbols: set[str] | None = None,
) -> dict[str, Any]:
    """Build a strategy_context using the real function — keeps tests honest."""
    return _build_strategy_context(
        market=_approved_market(),
        row=row or _week_row(),
        position=position,
        positions_available=False,
        short_list_symbols=short_list_symbols or set(),
        rules=rules,
    )


# ── load_decision_rules ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_load_decision_rules_returns_defaults_when_threshold_rows_absent(tmp_path):
    """No decision_threshold rows → exact DEFAULT_RULES returned."""
    db = tmp_path / "test.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute("DELETE FROM strategy_rules WHERE rule_category = 'decision_threshold'")
        rules = load_decision_rules(conn)
    assert rules == DEFAULT_RULES


@pytest.mark.unit
def test_load_decision_rules_reads_custom_bs_value_from_db(tmp_path):
    """A modified bull_strangle threshold is picked up; others stay at default."""
    db = tmp_path / "test.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            "UPDATE strategy_rules SET rule_parameters = ? WHERE rule_name = ?",
            ('{"value":0.05}', "bull_strangle_max_price_deviation_pct"),
        )
        rules = load_decision_rules(conn)
    assert rules["bull_strangle"]["max_price_deviation_pct"] == pytest.approx(0.05)
    assert rules["bull_strangle"]["max_credit_deviation"] == pytest.approx(2.50)
    assert rules["bull_strangle"]["minimum_total_credit"] == pytest.approx(0.01)


@pytest.mark.unit
def test_load_decision_rules_reads_custom_dca_value_from_db(tmp_path):
    """A modified dca threshold is picked up; bull_strangle side unchanged."""
    db = tmp_path / "test.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            "UPDATE strategy_rules SET rule_parameters = ? WHERE rule_name = ?",
            ('{"value":2.5}', "dca_minimum_candidate_score"),
        )
        rules = load_decision_rules(conn)
    assert rules["dca"]["minimum_candidate_score"] == pytest.approx(2.5)
    assert rules["dca"]["max_price_deviation_pct"] == pytest.approx(0.08)


@pytest.mark.unit
def test_load_decision_rules_ignores_inactive_rows(tmp_path):
    """is_active=0 rows are excluded; the key falls back to DEFAULT_RULES value."""
    db = tmp_path / "test.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            "UPDATE strategy_rules SET rule_parameters = ?, is_active = 0 WHERE rule_name = ?",
            ('{"value":0.001}', "bull_strangle_max_price_deviation_pct"),
        )
        rules = load_decision_rules(conn)
    # Inactive row is skipped so the value must come from DEFAULT_RULES (deep-copy baseline)
    assert rules["bull_strangle"]["max_price_deviation_pct"] == pytest.approx(
        DEFAULT_RULES["bull_strangle"]["max_price_deviation_pct"]
    )


@pytest.mark.unit
def test_load_decision_rules_all_five_thresholds_present(tmp_path):
    """All five decision_threshold rules are seeded and returned."""
    db = tmp_path / "test.db"
    initialize_database(db)
    with connect(db) as conn:
        rules = load_decision_rules(conn)
    assert set(rules["bull_strangle"].keys()) == {
        "max_price_deviation_pct",
        "max_credit_deviation",
        "minimum_total_credit",
    }
    assert set(rules["dca"].keys()) == {"max_price_deviation_pct", "minimum_candidate_score"}


# ── _build_bull_decision ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_bull_decision_rules_applied_json_is_bs_subdict():
    """rules_applied_json must contain bull_strangle keys only — not the DCA sub-dict."""
    ctx = _ctx()
    result = _build_bull_decision(1, _approved_market(), _week_row(), None, ctx, rules=DEFAULT_RULES)
    applied = json.loads(result["rules_applied_json"])
    assert "max_price_deviation_pct" in applied
    assert "max_credit_deviation" in applied
    assert "minimum_total_credit" in applied
    assert "minimum_candidate_score" not in applied


@pytest.mark.unit
def test_build_bull_decision_custom_rules_stored_in_applied_json():
    """Custom threshold values appear in rules_applied_json, not the defaults."""
    custom = {
        "bull_strangle": {"max_price_deviation_pct": 0.03, "max_credit_deviation": 1.00, "minimum_total_credit": 0.05},
        "dca": DEFAULT_RULES["dca"],
    }
    ctx = _ctx(rules=custom)
    result = _build_bull_decision(1, _approved_market(), _week_row(), None, ctx, rules=custom)
    applied = json.loads(result["rules_applied_json"])
    assert applied["max_price_deviation_pct"] == pytest.approx(0.03)
    assert applied["max_credit_deviation"] == pytest.approx(1.00)


@pytest.mark.unit
def test_build_bull_decision_tight_price_threshold_appears_in_failed_rules():
    """Symbol with deviation > tight threshold ends up in rules_failed_json."""
    tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.001, "max_credit_deviation": 2.5, "minimum_total_credit": 0.01},
        "dca": DEFAULT_RULES["dca"],
    }
    row = _week_row(worst_abs_stock_price_deviation_pct=0.05)
    ctx = _ctx(row=row, rules=tight)
    result = _build_bull_decision(1, _approved_market(), row, None, ctx, rules=tight)
    failed = json.loads(result["rules_failed_json"])
    assert "price_deviation_within_threshold" in failed


# ── _build_dca_decision ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_dca_decision_rules_applied_json_is_dca_subdict():
    """rules_applied_json for DCA must contain dca keys only — not the BS sub-dict."""
    ctx = _ctx()
    result = _build_dca_decision(1, _approved_market(), _week_row(), None, ctx, rules=DEFAULT_RULES)
    applied = json.loads(result["rules_applied_json"])
    assert "minimum_candidate_score" in applied
    assert "max_price_deviation_pct" in applied
    assert "max_credit_deviation" not in applied
    assert "minimum_total_credit" not in applied


@pytest.mark.unit
def test_build_dca_decision_no_keyerror_with_full_rules_dict():
    """Regression: passing the full rules dict (not the DCA sub-dict) must not raise.

    This is the exact failure mode caught during the e2e review on 2026-04-23:
    _build_dca_decision was slicing rules to the DCA sub-dict and forwarding
    that to _build_rule_diagnostics, which needs bull_strangle.max_credit_deviation.
    """
    custom = {
        "bull_strangle": {"max_price_deviation_pct": 0.05, "max_credit_deviation": 1.00, "minimum_total_credit": 0.01},
        "dca": {"max_price_deviation_pct": 0.05, "minimum_candidate_score": 1.5},
    }
    ctx = _ctx(rules=custom)
    # Must complete without KeyError
    result = _build_dca_decision(1, _approved_market(), _week_row(), None, ctx, rules=custom)
    assert result is not None
    assert "rules_applied_json" in result
    assert "rules_passed_json" in result
    assert "rules_failed_json" in result


@pytest.mark.unit
def test_build_dca_decision_diagnostics_use_bs_credit_threshold():
    """Even for a DCA decision, credit_deviation is checked against bull_strangle rules.

    The DCA sub-dict has no max_credit_deviation key.  The diagnostic must still
    evaluate the deviation — using the bull_strangle threshold from the full dict.
    """
    tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.08, "max_credit_deviation": 0.01, "minimum_total_credit": 0.01},
        "dca": {"max_price_deviation_pct": 0.08, "minimum_candidate_score": 1.0},
    }
    row = _week_row(worst_abs_total_credit_deviation=0.50)  # 0.50 > 0.01 threshold
    ctx = _ctx(row=row, rules=tight)
    result = _build_dca_decision(1, _approved_market(), row, None, ctx, rules=tight)
    failed = json.loads(result["rules_failed_json"])
    assert "credit_deviation_within_threshold" in failed


@pytest.mark.unit
def test_build_dca_decision_custom_dca_rules_in_applied_json():
    """Custom DCA threshold values appear in rules_applied_json."""
    custom = {
        "bull_strangle": DEFAULT_RULES["bull_strangle"],
        "dca": {"max_price_deviation_pct": 0.04, "minimum_candidate_score": 2.0},
    }
    ctx = _ctx(rules=custom)
    result = _build_dca_decision(1, _approved_market(), _week_row(), None, ctx, rules=custom)
    applied = json.loads(result["rules_applied_json"])
    assert applied["max_price_deviation_pct"] == pytest.approx(0.04)
    assert applied["minimum_candidate_score"] == pytest.approx(2.0)


# ── _build_rule_diagnostics ───────────────────────────────────────────────────

@pytest.mark.unit
def test_build_rule_diagnostics_passes_all_with_loose_rules():
    """Very loose thresholds — all deviation checks land in passed."""
    loose = {
        "bull_strangle": {"max_price_deviation_pct": 0.99, "max_credit_deviation": 99.0, "minimum_total_credit": 0.01},
        "dca": DEFAULT_RULES["dca"],
    }
    ctx = _ctx(rules=loose)
    passed, failed = _build_rule_diagnostics("BULL_STRANGLE", ctx, rules=loose)
    assert "price_deviation_within_threshold" in passed
    assert "credit_deviation_within_threshold" in passed
    assert "price_deviation_within_threshold" not in failed
    assert "credit_deviation_within_threshold" not in failed


@pytest.mark.unit
def test_build_rule_diagnostics_fails_price_deviation_with_tight_threshold():
    """Symbol with price_deviation=0.05 fails when max is 0.001."""
    tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.001, "max_credit_deviation": 2.5, "minimum_total_credit": 0.01},
        "dca": DEFAULT_RULES["dca"],
    }
    row = _week_row(worst_abs_stock_price_deviation_pct=0.05)
    ctx = _ctx(row=row, rules=tight)
    passed, failed = _build_rule_diagnostics("BULL_STRANGLE", ctx, rules=tight)
    assert "price_deviation_within_threshold" in failed
    assert "price_deviation_within_threshold" not in passed


@pytest.mark.unit
def test_build_rule_diagnostics_fails_credit_deviation_with_tight_threshold():
    """Symbol with credit_deviation=1.00 fails when max is 0.01."""
    tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.08, "max_credit_deviation": 0.01, "minimum_total_credit": 0.01},
        "dca": DEFAULT_RULES["dca"],
    }
    row = _week_row(worst_abs_total_credit_deviation=1.00)
    ctx = _ctx(row=row, rules=tight)
    passed, failed = _build_rule_diagnostics("BULL_STRANGLE", ctx, rules=tight)
    assert "credit_deviation_within_threshold" in failed


@pytest.mark.unit
def test_build_rule_diagnostics_dca_action_uses_bs_credit_threshold():
    """Passing action_type='DCA' must still evaluate credit_deviation against
    bull_strangle.max_credit_deviation — the DCA sub-dict has no such key."""
    tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.08, "max_credit_deviation": 0.01, "minimum_total_credit": 0.01},
        "dca": {"max_price_deviation_pct": 0.08, "minimum_candidate_score": 1.0},
    }
    row = _week_row(worst_abs_total_credit_deviation=0.50)
    ctx = _ctx(row=row, rules=tight)
    passed, failed = _build_rule_diagnostics("DCA", ctx, rules=tight)
    assert "credit_deviation_within_threshold" in failed


@pytest.mark.unit
def test_build_rule_diagnostics_none_deviation_always_passes():
    """None deviation (no OS data yet) must always pass both thresholds."""
    very_tight = {
        "bull_strangle": {"max_price_deviation_pct": 0.0, "max_credit_deviation": 0.0, "minimum_total_credit": 0.01},
        "dca": DEFAULT_RULES["dca"],
    }
    row = _week_row(
        worst_abs_stock_price_deviation_pct=None,
        worst_abs_total_credit_deviation=None,
    )
    ctx = _ctx(row=row, rules=very_tight)
    passed, failed = _build_rule_diagnostics("BULL_STRANGLE", ctx, rules=very_tight)
    assert "price_deviation_within_threshold" in passed
    assert "credit_deviation_within_threshold" in passed
