"""
Phase 3 — Entry Engine: Gates 1-9 evaluation for Bull Strangle strategy.

Each gate maps to one or more rules in strategy_rule_catalog.  Gates 1-6 and 9
run purely from newsletter data (always available).  Gates 7 and 8 require OS
evaluation data; they are skipped (not failed) when that data is absent.

Key design decision for validation mode:
  All gates are evaluated on every symbol even after a hard-gate failure so
  the full picture is visible.  ``first_failing_gate`` records which gate would
  have short-circuited a live evaluation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .database import connect


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    gate_num: int
    rule_id: str
    name: str
    gate_type: str          # "hard" | "soft"
    passed: bool
    skipped: bool = False   # True when required data is unavailable
    actual_value: Any = None
    threshold: Any = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "gate": self.gate_num,
            "rule_id": self.rule_id,
            "name": self.name,
            "type": self.gate_type,
            "passed": self.passed,
            "skipped": self.skipped,
            "actual": self.actual_value,
            "threshold": self.threshold,
            "reason": self.reason,
        }


@dataclass
class EntryDecision:
    symbol: str
    newsletter_id: int
    newsletter_date: str
    expiration_date: str | None
    entry_date: str | None

    gate_results: list[GateResult] = field(default_factory=list)
    passed_all_hard_gates: bool = False
    first_failing_gate: int | None = None
    first_failing_gate_name: str | None = None
    decision_type: str = "SKIP"    # BULL_STRANGLE | WATCH | SKIP

    deployment_approved: bool = False
    stock_price: float = 0.0
    implied_volatility: float = 0.0
    call_premium: float = 0.0
    put_premium: float = 0.0
    total_credit: float = 0.0
    expected_return_pct: float = 0.0

    # Short-list membership (filled during evaluation for validation)
    in_short_list_small: bool = False
    in_short_list_large: bool = False
    short_list_rank_small: int | None = None
    short_list_rank_large: int | None = None

    def passes_gate(self, gate_num: int) -> bool | None:
        """Return True/False/None(skipped) for a specific gate number."""
        for r in self.gate_results:
            if r.gate_num == gate_num:
                if r.skipped:
                    return None
                return r.passed
        return None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "newsletter_date": self.newsletter_date,
            "expiration_date": self.expiration_date,
            "entry_date": self.entry_date,
            "decision_type": self.decision_type,
            "passed_all_hard_gates": self.passed_all_hard_gates,
            "first_failing_gate": self.first_failing_gate,
            "first_failing_gate_name": self.first_failing_gate_name,
            "deployment_approved": self.deployment_approved,
            "stock_price": self.stock_price,
            "implied_volatility": round(self.implied_volatility, 4),
            "total_credit": round(self.total_credit, 2),
            "expected_return_pct": round(self.expected_return_pct, 2),
            "in_short_list_small": self.in_short_list_small,
            "in_short_list_large": self.in_short_list_large,
            "short_list_rank_small": self.short_list_rank_small,
            "short_list_rank_large": self.short_list_rank_large,
            "gates": [r.to_dict() for r in self.gate_results],
        }


# ---------------------------------------------------------------------------
# Individual gate evaluators
# ---------------------------------------------------------------------------

def _gate_1_market_deployment(conn, newsletter_id: int) -> GateResult:
    """Gate 1 — RULE-ENV-002: two consecutive weeks of criteria met required."""
    row = conn.execute(
        "SELECT deployment_approved, consecutive_weeks_met FROM weekly_decisions "
        "WHERE newsletter_id = ?",
        (newsletter_id,),
    ).fetchone()
    if not row:
        return GateResult(
            1, "RULE-ENV-002", "Market Deployment", "hard",
            passed=False, reason="No weekly_decisions row found for this newsletter",
        )
    passed = bool(row["deployment_approved"])
    consec = row["consecutive_weeks_met"]
    return GateResult(
        1, "RULE-ENV-002", "Market Deployment", "hard",
        passed=passed,
        actual_value=consec,
        threshold=2,
        reason="OK" if passed else f"deployment_approved=False (consecutive_weeks={consec})",
    )


def _gate_2_iv_ceiling(we) -> GateResult:
    """Gate 2 — GATE-SS-001: IV must be strictly below 100%."""
    if we is None:
        return GateResult(2, "GATE-SS-001", "IV Ceiling", "hard",
                          passed=False, reason="Symbol not on watchlist")
    iv = we["implied_volatility"] or 0.0
    passed = iv < 1.0
    return GateResult(
        2, "GATE-SS-001", "IV Ceiling", "hard",
        passed=passed,
        actual_value=f"{iv:.0%}",
        threshold="< 100%",
        reason="OK" if passed else f"IV={iv:.0%} — at or above 100% ceiling",
    )


def _gate_3_premium_yield(we) -> GateResult:
    """Gate 3 — GATE-SS-004 (soft): combined premium must yield ≥ 2% of stock price."""
    if we is None:
        return GateResult(3, "GATE-SS-004", "Minimum Premium Yield", "soft",
                          passed=False, reason="Symbol not on watchlist")
    call_p = we["sell_call_premium"] or 0.0
    put_p = we["sell_put_premium"] or 0.0
    price = we["stock_price"] or 0.0
    if price <= 0:
        return GateResult(3, "GATE-SS-004", "Minimum Premium Yield", "soft",
                          passed=False, reason="stock_price is zero or null")
    credit = call_p + put_p
    yield_pct = credit / price * 100
    passed = yield_pct >= 2.0
    return GateResult(
        3, "GATE-SS-004", "Minimum Premium Yield", "soft",
        passed=passed,
        actual_value=f"{yield_pct:.2f}%",
        threshold="≥ 2.0%",
        reason="OK" if passed else f"Yield={yield_pct:.2f}% below 2% floor",
    )


def _gate_4_option_liquidity(we) -> GateResult:
    """Gate 4 — GATE-SS-003: both call and put must have non-zero premiums."""
    if we is None:
        return GateResult(4, "GATE-SS-003", "Option Liquidity", "hard",
                          passed=False, reason="Symbol not on watchlist")
    call_ok = (we["sell_call_premium"] or 0) > 0
    put_ok = (we["sell_put_premium"] or 0) > 0
    passed = call_ok and put_ok
    if passed:
        reason = "OK"
    elif not call_ok and not put_ok:
        reason = "Zero premium on both call and put"
    elif not call_ok:
        reason = "Zero call premium"
    else:
        reason = "Zero put premium"
    return GateResult(
        4, "GATE-SS-003", "Option Liquidity", "hard",
        passed=passed,
        actual_value=f"call={we['sell_call_premium']}, put={we['sell_put_premium']}",
        threshold="both > 0",
        reason=reason,
    )


def _gate_5_earnings_clearance(conn, symbol: str, entry_date_str: str | None,
                                expiration_date_str: str | None) -> GateResult:
    """Gate 5 — GATE-SS-005 + RULE-EARN-001: no earnings within 45 days OR before expiration."""
    if not entry_date_str or not expiration_date_str:
        return GateResult(
            5, "GATE-SS-005", "Earnings Clearance", "hard",
            passed=True, skipped=True,
            reason="Entry or expiration date unavailable — skipped",
        )
    entry_dt = date.fromisoformat(entry_date_str)
    expiry_dt = date.fromisoformat(expiration_date_str)

    row = conn.execute(
        "SELECT earnings_date FROM earnings_calendar "
        "WHERE symbol = ? AND earnings_date >= ? ORDER BY earnings_date LIMIT 1",
        (symbol, entry_date_str),
    ).fetchone()

    if not row:
        return GateResult(
            5, "GATE-SS-005", "Earnings Clearance", "hard",
            passed=True, actual_value="N/A",
            reason="No upcoming earnings found in calendar",
        )

    earn_str = row["earnings_date"]
    earn_dt = date.fromisoformat(earn_str)

    # RULE-EARN-001: earnings must not fall before or on the expiration date
    if earn_dt <= expiry_dt:
        return GateResult(
            5, "GATE-SS-005", "Earnings Clearance", "hard",
            passed=False,
            actual_value=earn_str,
            threshold=f"> {expiry_dt.isoformat()} (expiry)",
            reason=f"Earnings {earn_str} falls on or before expiration {expiry_dt.isoformat()}",
        )

    days_clear = (earn_dt - entry_dt).days
    # GATE-SS-005: must be > 45 days from entry
    if days_clear < 45:
        return GateResult(
            5, "GATE-SS-005", "Earnings Clearance", "hard",
            passed=False,
            actual_value=f"{earn_str} ({days_clear}d away)",
            threshold="≥ 45 days from entry",
            reason=f"Earnings in {days_clear}d — inside 45-day clearance buffer",
        )

    return GateResult(
        5, "GATE-SS-005", "Earnings Clearance", "hard",
        passed=True,
        actual_value=f"{earn_str} ({days_clear}d away)",
        threshold="≥ 45 days from entry",
        reason="OK",
    )


def _gate_6_watchlist_membership(we) -> GateResult:
    """Gate 6 — GATE-SS-008: symbol must appear on the current watchlist."""
    passed = we is not None
    return GateResult(
        6, "GATE-SS-008", "Watchlist Membership", "hard",
        passed=passed,
        reason="On watchlist" if passed else "Not on watchlist for this newsletter",
    )


def _gate_7_ma_alignment(conn, newsletter_id: int, symbol: str) -> GateResult:
    """Gate 7 — GATE-SS-002/006: stock above ≥ 2 of 4 MAs. Skipped when no OS data."""
    os_row = conn.execute(
        "SELECT sma_50d, sma_200d, live_stock_price FROM os_evaluation_rows "
        "WHERE newsletter_id = ? AND symbol = ? ORDER BY evaluation_row_id DESC LIMIT 1",
        (newsletter_id, symbol),
    ).fetchone()
    if not os_row:
        return GateResult(
            7, "GATE-SS-002", "MA Alignment", "hard",
            passed=True, skipped=True,
            reason="No OS evaluation data — gate skipped",
        )
    price = os_row["live_stock_price"] or 0
    mas = {"50d": os_row["sma_50d"], "200d": os_row["sma_200d"]}
    above = [k for k, v in mas.items() if v and price > v]
    below = [k for k, v in mas.items() if v and price <= v]
    # With only 2 MAs available from OS, require at least 1
    passed = len(above) >= 1
    return GateResult(
        7, "GATE-SS-002", "MA Alignment", "hard",
        passed=passed,
        actual_value=f"above {len(above)}/2 ({', '.join(above) or 'none'})",
        threshold="≥ 1 of 2 available MAs",
        reason="OK" if passed else f"Below all available MAs ({', '.join(below)})",
    )


def _gate_8_weekly_deviation(conn, newsletter_id: int, symbol: str) -> GateResult:
    """Gate 8 — weekly stock-price deviation (soft). Skipped when no OS aggregate data.

    Uses ``worst_abs_stock_price_deviation_pct`` from the weekly aggregate, which
    measures the worst intra-week stock price drift from the newsletter baseline.
    A deviation > 20% suggests the option premiums in the newsletter are stale.
    """
    agg = conn.execute(
        "SELECT worst_abs_stock_price_deviation_pct, worst_abs_total_credit_deviation, "
        "       latest_total_credit, is_week_valid "
        "FROM os_weekly_symbol_aggregates WHERE newsletter_id = ? AND symbol = ?",
        (newsletter_id, symbol),
    ).fetchone()
    if not agg:
        return GateResult(
            8, "RULE-DEV-001", "Weekly Deviation", "soft",
            passed=True, skipped=True,
            reason="No OS weekly aggregate data — gate skipped",
        )
    price_dev = abs(agg["worst_abs_stock_price_deviation_pct"] or 0)
    passed = price_dev <= 20.0
    return GateResult(
        8, "RULE-DEV-001", "Weekly Deviation", "soft",
        passed=passed,
        actual_value=f"{price_dev:.1f}%",
        threshold="≤ 20%",
        reason="OK" if passed else f"Price deviation {price_dev:.1f}% exceeds 20% threshold",
    )


def _gate_9_expected_return(we) -> GateResult:
    """Gate 9 — GATE-SS-004 proxy (soft): newsletter bull-strangle return must be ≥ 4%."""
    if we is None:
        return GateResult(9, "GATE-SS-004", "Expected Return", "soft",
                          passed=False, reason="Symbol not on watchlist")
    ret_pct = we["bull_strangle_return_pct"] or 0.0
    passed = ret_pct >= 4.0
    return GateResult(
        9, "GATE-SS-004", "Expected Return", "soft",
        passed=passed,
        actual_value=f"{ret_pct:.1f}%",
        threshold="≥ 4.0%",
        reason="OK" if passed else f"Return {ret_pct:.1f}% below 4% minimum",
    )


# ---------------------------------------------------------------------------
# Core evaluation functions
# ---------------------------------------------------------------------------

def evaluate_entry(
    symbol: str,
    newsletter_id: int,
    db_path: str,
    entry_date: str | None = None,
    persist: bool = True,
) -> EntryDecision | None:
    """
    Evaluate Gates 1–9 for one symbol against one newsletter week.

    All gates are always run (no early termination) so the full picture is
    available for validation.  ``first_failing_gate`` records the gate that
    would have caused a short-circuit in live production mode.

    Returns None if the newsletter_id does not exist.
    """
    with connect(db_path) as conn:
        nl = conn.execute(
            "SELECT newsletter_id, publication_date, entry_date, target_expiration "
            "FROM newsletters WHERE newsletter_id = ?",
            (newsletter_id,),
        ).fetchone()
        if not nl:
            return None

        effective_entry = entry_date or nl["entry_date"] or nl["publication_date"]
        expiration = nl["target_expiration"]

        # Watchlist entry (may be None if symbol not on this week's list)
        we = conn.execute(
            "SELECT * FROM watchlist_entries WHERE newsletter_id = ? AND symbol = ?",
            (newsletter_id, symbol),
        ).fetchone()

        # Short-list membership for both portfolios
        sl_rows = conn.execute(
            "SELECT portfolio_type, rank FROM short_list_entries "
            "WHERE newsletter_id = ? AND symbol = ?",
            (newsletter_id, symbol),
        ).fetchall()
        sl_small = next((r["rank"] for r in sl_rows if r["portfolio_type"] == "small"), None)
        sl_large = next((r["rank"] for r in sl_rows if r["portfolio_type"] == "large"), None)

        # Deployment status
        wd = conn.execute(
            "SELECT deployment_approved FROM weekly_decisions WHERE newsletter_id = ?",
            (newsletter_id,),
        ).fetchone()

        decision = EntryDecision(
            symbol=symbol,
            newsletter_id=newsletter_id,
            newsletter_date=nl["publication_date"],
            expiration_date=expiration,
            entry_date=effective_entry,
            deployment_approved=bool(wd["deployment_approved"]) if wd else False,
            in_short_list_small=sl_small is not None,
            in_short_list_large=sl_large is not None,
            short_list_rank_small=sl_small,
            short_list_rank_large=sl_large,
        )

        if we:
            decision.stock_price = we["stock_price"] or 0.0
            decision.implied_volatility = we["implied_volatility"] or 0.0
            decision.call_premium = we["sell_call_premium"] or 0.0
            decision.put_premium = we["sell_put_premium"] or 0.0
            decision.total_credit = decision.call_premium + decision.put_premium
            decision.expected_return_pct = we["bull_strangle_return_pct"] or 0.0

        # Run all gates — collect all results regardless of failure
        results = [
            _gate_1_market_deployment(conn, newsletter_id),
            _gate_2_iv_ceiling(we),
            _gate_3_premium_yield(we),
            _gate_4_option_liquidity(we),
            _gate_5_earnings_clearance(conn, symbol, effective_entry, expiration),
            _gate_6_watchlist_membership(we),
            _gate_7_ma_alignment(conn, newsletter_id, symbol),
            _gate_8_weekly_deviation(conn, newsletter_id, symbol),
            _gate_9_expected_return(we),
        ]
        decision.gate_results = results

        # Identify first hard gate failure (production short-circuit point)
        for r in results:
            if not r.passed and not r.skipped and r.gate_type == "hard":
                if decision.first_failing_gate is None:
                    decision.first_failing_gate = r.gate_num
                    decision.first_failing_gate_name = r.name
                break  # stop at first hard failure for short-circuit tracking

        decision.passed_all_hard_gates = decision.first_failing_gate is None

        # Decision type
        if not decision.passed_all_hard_gates:
            decision.decision_type = "SKIP"
        else:
            soft_failures = [r for r in results if not r.passed and not r.skipped and r.gate_type == "soft"]
            if soft_failures:
                decision.decision_type = "WATCH"
            else:
                decision.decision_type = "BULL_STRANGLE"

        if persist:
            _persist_decision(conn, decision)

        return decision


def _persist_decision(conn, decision: EntryDecision) -> None:
    """Insert or update an EntryDecision in entry_decisions.

    Newsletter-level evaluations (no OS run) use os_run_id = NULL.
    SQLite treats NULLs as distinct in UNIQUE constraints, so we cannot
    use ON CONFLICT for the upsert; instead we do an explicit SELECT →
    UPDATE or INSERT.
    """
    gates_json = json.dumps([r.to_dict() for r in decision.gate_results], sort_keys=True)
    existing = conn.execute(
        "SELECT decision_id FROM entry_decisions "
        "WHERE newsletter_id = ? AND os_run_id IS NULL AND symbol = ?",
        (decision.newsletter_id, decision.symbol),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE entry_decisions SET
              evaluation_date    = ?,
              decision_type      = ?,
              first_failing_gate = ?,
              gates_json         = ?,
              live_stock_price   = ?,
              live_iv            = ?,
              live_total_credit  = ?
            WHERE decision_id = ?
            """,
            (
                decision.newsletter_date,
                decision.decision_type,
                str(decision.first_failing_gate) if decision.first_failing_gate else None,
                gates_json,
                decision.stock_price,
                decision.implied_volatility,
                decision.total_credit,
                existing["decision_id"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO entry_decisions
            (newsletter_id, os_run_id, symbol, evaluation_date, decision_type,
             first_failing_gate, gates_json,
             live_stock_price, live_iv, live_total_credit,
             live_call_strike, live_put_strike)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                decision.newsletter_id,
                decision.symbol,
                decision.newsletter_date,
                decision.decision_type,
                str(decision.first_failing_gate) if decision.first_failing_gate else None,
                gates_json,
                decision.stock_price,
                decision.implied_volatility,
                decision.total_credit,
            ),
        )


def evaluate_newsletter(
    newsletter_ref: str | int,
    db_path: str,
    persist: bool = True,
) -> dict:
    """
    Evaluate Gates 1–9 for every watchlist symbol in one newsletter week.

    Returns a dict with:
      - newsletter_date, expiration_date
      - decisions: list of EntryDecision.to_dict()
      - validation: alignment stats vs Short List
    """
    with connect(db_path) as conn:
        # Resolve newsletter
        if isinstance(newsletter_ref, int):
            nl = conn.execute(
                "SELECT newsletter_id, publication_date FROM newsletters WHERE newsletter_id = ?",
                (newsletter_ref,),
            ).fetchone()
        else:
            nl = conn.execute(
                "SELECT newsletter_id, publication_date FROM newsletters WHERE publication_date = ?",
                (newsletter_ref,),
            ).fetchone()
        if not nl:
            raise ValueError(f"Newsletter not found: {newsletter_ref!r}")
        newsletter_id = nl["newsletter_id"]
        pub_date = nl["publication_date"]

        # All watchlist symbols for this week
        symbols = [
            r["symbol"]
            for r in conn.execute(
                "SELECT symbol FROM watchlist_entries WHERE newsletter_id = ? ORDER BY symbol",
                (newsletter_id,),
            )
        ]

    decisions = [
        evaluate_entry(sym, newsletter_id, db_path, persist=persist)
        for sym in symbols
        if evaluate_entry  # always true; just to keep the list comp readable
    ]
    # Filter out None returns (shouldn't happen but be safe)
    decisions = [d for d in decisions if d is not None]

    return {
        "newsletter_date": pub_date,
        "decisions": [d.to_dict() for d in decisions],
        "validation": _build_validation_summary(decisions),
    }


def _build_validation_summary(decisions: list[EntryDecision]) -> dict:
    """Compare gate decisions to Short List membership for strategy validation."""
    total = len(decisions)
    passed_hard = [d for d in decisions if d.passed_all_hard_gates]
    passed_all = [d for d in decisions if d.decision_type == "BULL_STRANGLE"]

    in_small = [d for d in decisions if d.in_short_list_small]
    in_large = [d for d in decisions if d.in_short_list_large]

    # Short list symbols that pass all hard gates
    small_pass = [d for d in in_small if d.passed_all_hard_gates]
    large_pass = [d for d in in_large if d.passed_all_hard_gates]

    # Short list symbols that fail a hard gate (Darren overrode rules?)
    small_fail = [d for d in in_small if not d.passed_all_hard_gates]
    large_fail = [d for d in in_large if not d.passed_all_hard_gates]

    # Symbols that pass all gates but aren't in short list (missed opportunities?)
    gate_approved_not_selected = [
        d for d in passed_hard
        if not d.in_short_list_small and not d.in_short_list_large
    ]

    # Gate failure breakdown
    gate_failures: dict[str, list[str]] = {}
    for d in decisions:
        if d.first_failing_gate is not None:
            key = f"Gate {d.first_failing_gate} — {d.first_failing_gate_name}"
            gate_failures.setdefault(key, []).append(d.symbol)

    return {
        "watchlist_count": total,
        "passed_all_hard_gates": len(passed_hard),
        "bull_strangle_eligible": len(passed_all),
        "small_short_list_count": len(in_small),
        "large_short_list_count": len(in_large),
        "small_alignment": {
            "pass": len(small_pass),
            "fail": len(small_fail),
            "fail_symbols": [
                {"symbol": d.symbol, "failing_gate": d.first_failing_gate_name}
                for d in small_fail
            ],
            "pct": round(len(small_pass) / len(in_small) * 100, 1) if in_small else None,
        },
        "large_alignment": {
            "pass": len(large_pass),
            "fail": len(large_fail),
            "fail_symbols": [
                {"symbol": d.symbol, "failing_gate": d.first_failing_gate_name}
                for d in large_fail
            ],
            "pct": round(len(large_pass) / len(in_large) * 100, 1) if in_large else None,
        },
        "gate_approved_not_in_short_list": [d.symbol for d in gate_approved_not_selected],
        "gate_failure_breakdown": {k: v for k, v in sorted(gate_failures.items())},
    }


# ---------------------------------------------------------------------------
# Backtest validation — all approved newsletters
# ---------------------------------------------------------------------------

def validate_all_newsletters(db_path: str, persist: bool = True) -> dict:
    """
    Run gate evaluation across all newsletters and aggregate validation stats.
    Answers: does the decision layer consistently explain the Short List selections?
    """
    with connect(db_path) as conn:
        newsletters = conn.execute(
            "SELECT newsletter_id, publication_date FROM newsletters ORDER BY publication_date"
        ).fetchall()

    all_decisions: list[EntryDecision] = []
    weekly_results = []

    for nl in newsletters:
        result = evaluate_newsletter(nl["newsletter_id"], db_path, persist=persist)
        decisions = [
            _dict_to_entry_decision(d) for d in result["decisions"]
        ]
        all_decisions.extend(decisions)
        weekly_results.append({
            "newsletter_date": nl["publication_date"],
            "summary": result["validation"],
        })

    overall = _build_validation_summary(all_decisions)

    return {
        "weeks_evaluated": len(newsletters),
        "overall": overall,
        "by_week": weekly_results,
    }


def _dict_to_entry_decision(d: dict) -> EntryDecision:
    """Reconstruct a lightweight EntryDecision from to_dict() output for aggregation."""
    dec = EntryDecision(
        symbol=d["symbol"],
        newsletter_id=0,
        newsletter_date=d["newsletter_date"],
        expiration_date=d.get("expiration_date"),
        entry_date=d.get("entry_date"),
        passed_all_hard_gates=d["passed_all_hard_gates"],
        first_failing_gate=d.get("first_failing_gate"),
        first_failing_gate_name=d.get("first_failing_gate_name"),
        decision_type=d["decision_type"],
        deployment_approved=d.get("deployment_approved", False),
        in_short_list_small=d.get("in_short_list_small", False),
        in_short_list_large=d.get("in_short_list_large", False),
        short_list_rank_small=d.get("short_list_rank_small"),
        short_list_rank_large=d.get("short_list_rank_large"),
    )
    return dec


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

_PASS = "pass"
_FAIL = "FAIL"
_SKIP = "skip"


def _fmt_gate(result: GateResult) -> str:
    if result.skipped:
        return _SKIP
    return _PASS if result.passed else _FAIL


def generate_entry_validation_report(
    newsletter_ref: str | int,
    db_path: str,
    output_path: str | None = None,
) -> str:
    """
    Generate a markdown report showing gate results for every watchlist symbol
    and how they align with the Short List selections.
    """
    result = evaluate_newsletter(newsletter_ref, db_path, persist=True)
    decisions = [_dict_to_entry_decision(d) for d in result["decisions"]]
    # Re-fetch full gate data from original dicts
    dicts = result["decisions"]
    val = result["validation"]
    pub_date = result["newsletter_date"]

    # Fetch market environment details for header
    with connect(db_path) as conn:
        nl = conn.execute(
            "SELECT n.newsletter_id, n.target_expiration, wd.deployment_approved, "
            "wd.consecutive_weeks_met, me.hybrid_score, me.market_status "
            "FROM newsletters n "
            "LEFT JOIN weekly_decisions wd ON wd.newsletter_id = n.newsletter_id "
            "LEFT JOIN market_environment me ON me.newsletter_id = n.newsletter_id "
            "WHERE n.publication_date = ?",
            (pub_date,),
        ).fetchone()

    lines: list[str] = []
    lines.append(f"# Bull Strangle Gate Validation Report")
    lines.append(f"")
    lines.append(f"**Newsletter:** {pub_date}  "
                 f"**Expiration:** {nl['target_expiration'] if nl else '?'}")

    if nl:
        status_icon = "DEPLOYED" if nl["deployment_approved"] else "PAUSED"
        lines.append(f"**Market:** {status_icon} | "
                     f"Hybrid score: {nl['hybrid_score']} | "
                     f"Consecutive weeks: {nl['consecutive_weeks_met']} | "
                     f"Status: {nl['market_status']}")
    lines.append("")

    # Per-symbol gate table
    # Columns: Symbol | G1 | G2 IV | G3 Yield | G4 Liq | G5 Earn | G6 WL | G9 Ret | Decision | Short List
    lines.append("## Gate Results by Symbol")
    lines.append("")
    header = (
        "| Symbol | G1 Mkt | G2 IV | G3 Yld | G4 Liq | G5 Earn | G6 WL | G9 Ret | Decision | Short List |"
    )
    sep = "|--------|--------|-------|--------|--------|---------|-------|--------|----------|------------|"
    lines.append(header)
    lines.append(sep)

    for d in dicts:
        gates = {r["gate"]: r for r in d["gates"]}

        def gf(num: int) -> str:
            r = gates.get(num)
            if not r:
                return "-"
            if r["skipped"]:
                return "skip"
            return "pass" if r["passed"] else f"**FAIL**"

        sl_parts = []
        if d["in_short_list_small"]:
            sl_parts.append(f"S#{d['short_list_rank_small']}")
        if d["in_short_list_large"]:
            sl_parts.append(f"L#{d['short_list_rank_large']}")
        sl_str = ", ".join(sl_parts) if sl_parts else "—"

        dt = d["decision_type"]
        if dt == "BULL_STRANGLE":
            dt_fmt = "**BULL_STRANGLE**"
        elif dt == "WATCH":
            dt_fmt = "WATCH"
        else:
            dt_fmt = "skip"

        lines.append(
            f"| {d['symbol']:6s} "
            f"| {gf(1):6s} "
            f"| {gf(2):5s} "
            f"| {gf(3):6s} "
            f"| {gf(4):6s} "
            f"| {gf(5):7s} "
            f"| {gf(6):5s} "
            f"| {gf(9):6s} "
            f"| {dt_fmt:16s} "
            f"| {sl_str:10s} |"
        )

    lines.append("")

    # Validation summary
    lines.append("## Validation Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Watchlist symbols evaluated | {val['watchlist_count']} |")
    lines.append(f"| Passed all hard gates | {val['passed_all_hard_gates']} |")
    lines.append(f"| BULL_STRANGLE eligible (all gates) | {val['bull_strangle_eligible']} |")
    lines.append(f"| Small Short List symbols | {val['small_short_list_count']} |")
    lines.append(f"| Small Short List — gate alignment | "
                 f"{val['small_alignment']['pass']}/{val['small_short_list_count']} "
                 f"({val['small_alignment']['pct']}%) |")
    lines.append(f"| Large Short List symbols | {val['large_short_list_count']} |")
    lines.append(f"| Large Short List — gate alignment | "
                 f"{val['large_alignment']['pass']}/{val['large_short_list_count']} "
                 f"({val['large_alignment']['pct']}%) |")
    lines.append("")

    # Short list symbols that failed gates
    if val["small_alignment"]["fail_symbols"]:
        lines.append("### Short List symbols that FAILED hard gates (strategy override?)")
        lines.append("")
        for item in val["small_alignment"]["fail_symbols"]:
            lines.append(f"- **{item['symbol']}** — failed {item['failing_gate']}")
        lines.append("")

    # Gate-approved symbols not in short list
    if val["gate_approved_not_in_short_list"]:
        lines.append("### Gate-approved symbols NOT selected by Darren")
        lines.append("")
        lines.append(", ".join(val["gate_approved_not_in_short_list"]))
        lines.append("")

    # Gate failure breakdown
    if val["gate_failure_breakdown"]:
        lines.append("### Gate failure breakdown")
        lines.append("")
        lines.append("| Gate | Failures | Symbols |")
        lines.append("|------|----------|---------|")
        for gate_name, syms in val["gate_failure_breakdown"].items():
            lines.append(f"| {gate_name} | {len(syms)} | {', '.join(syms)} |")
        lines.append("")

    report = "\n".join(lines)

    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

    return report
