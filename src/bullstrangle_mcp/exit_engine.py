"""
Phase 4 — Exit Engine: RULE-EXIT-* evaluation for active Bull Strangle cycle layers.

For each ACTIVE cycle_layer, evaluates all exit triggers in priority order and
recommends an action.  Live price is fetched from yfinance when available; the
engine degrades gracefully when quotes cannot be retrieved.

Trigger priority (highest first):
  1. RULE-EARN-003  — earnings override → CLOSE_IMMEDIATELY (hard rule)
  2. RULE-EXIT-006  — drop ≥ 25% from entry price → EXIT_MONDAY (optional overlay)
  3. RULE-EXIT-007  — drop ≥ 15% below put strike → EXIT_MONDAY (optional overlay)
  4. Expiration past → NEEDS_RESOLUTION (call resolve_cycle_outcomes)
  5. RULE-EXIT-001  — DTE ≤ 7 → REVIEW (advisory alert)
  6. (default)       → HOLD

RULE-EXIT-001 through RULE-EXIT-004 describe what happens AT expiration;
the resolution logic lives in position_book.resolve_outcomes().  This engine
focuses on INTRA-CYCLE management decisions.
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
class ExitTrigger:
    rule_id: str
    name: str
    triggered: bool
    skipped: bool = False
    actual_value: Any = None
    threshold: Any = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "actual_value": self.actual_value,
            "threshold": self.threshold,
            "reason": self.reason,
        }


# Recommended action codes
ACTION_HOLD = "HOLD"
ACTION_REVIEW = "REVIEW"               # advisory — look at this week
ACTION_EXIT_MONDAY = "EXIT_MONDAY"     # optional overlay — exit at Monday open
ACTION_CLOSE_IMMEDIATELY = "CLOSE_IMMEDIATELY"  # mandatory earnings override
ACTION_NEEDS_RESOLUTION = "NEEDS_RESOLUTION"    # expiration date passed — run resolve


@dataclass
class ExitDecision:
    layer_id: int
    symbol: str
    account_id: str
    newsletter_date: str
    expiration_date: str
    evaluation_date: str
    days_to_expiration: int

    # Layer position data
    stock_price_at_entry: float
    call_strike: float
    put_strike: float
    total_credit_collected: float
    invested_capital: float

    # Live price (None when yfinance unavailable)
    current_price: float | None = None
    price_source: str = "unavailable"

    # Trigger results
    triggers: list[ExitTrigger] = field(default_factory=list)

    # Recommendation
    recommended_action: str = ACTION_HOLD
    action_urgency: str = "ROUTINE"   # IMMEDIATE | THIS_WEEK | ROUTINE
    rule_citations: list[str] = field(default_factory=list)
    action_reason: str = ""

    # Derived metrics (populated when current_price is available)
    pct_change_from_entry: float | None = None
    pct_above_call_strike: float | None = None  # positive = above call (bad for covered call)
    pct_below_put_strike: float | None = None   # positive = below put (assignment risk)
    unrealized_premium_pct: float | None = None  # credit / invested_capital

    def to_dict(self) -> dict:
        return {
            "layer_id": self.layer_id,
            "symbol": self.symbol,
            "account_id": self.account_id,
            "newsletter_date": self.newsletter_date,
            "expiration_date": self.expiration_date,
            "evaluation_date": self.evaluation_date,
            "days_to_expiration": self.days_to_expiration,
            "current_price": self.current_price,
            "price_source": self.price_source,
            "stock_price_at_entry": self.stock_price_at_entry,
            "call_strike": self.call_strike,
            "put_strike": self.put_strike,
            "total_credit_collected": round(self.total_credit_collected, 2),
            "invested_capital": round(self.invested_capital, 2),
            "pct_change_from_entry": (
                round(self.pct_change_from_entry, 2) if self.pct_change_from_entry is not None else None
            ),
            "pct_above_call_strike": (
                round(self.pct_above_call_strike, 2) if self.pct_above_call_strike is not None else None
            ),
            "pct_below_put_strike": (
                round(self.pct_below_put_strike, 2) if self.pct_below_put_strike is not None else None
            ),
            "unrealized_premium_pct": (
                round(self.unrealized_premium_pct, 2) if self.unrealized_premium_pct is not None else None
            ),
            "recommended_action": self.recommended_action,
            "action_urgency": self.action_urgency,
            "rule_citations": self.rule_citations,
            "action_reason": self.action_reason,
            "triggers": [t.to_dict() for t in self.triggers],
        }


# ---------------------------------------------------------------------------
# Live price fetching
# ---------------------------------------------------------------------------

def _fetch_current_price(symbol: str) -> tuple[float | None, str]:
    """Fetch latest close price via yfinance. Returns (price, source_description)."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
        if price and price > 0:
            return float(price), "yfinance_live"
        # Fallback: last 2-day history
        hist = ticker.history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1]), "yfinance_history"
        return None, "unavailable"
    except Exception:
        return None, "unavailable"


# ---------------------------------------------------------------------------
# Individual trigger evaluators
# ---------------------------------------------------------------------------

def _trigger_earnings_override(conn, layer: dict, today: date) -> ExitTrigger:
    """RULE-EARN-003: earnings announced into active cycle → CLOSE_IMMEDIATELY."""
    expiry_str = layer["expiration_date"]
    symbol = layer["symbol"]

    # Look for any earnings between tomorrow and expiration (inclusive)
    tomorrow = (today + timedelta(days=1)).isoformat()
    row = conn.execute(
        "SELECT earnings_date FROM earnings_calendar "
        "WHERE symbol = ? AND earnings_date >= ? AND earnings_date <= ? "
        "ORDER BY earnings_date LIMIT 1",
        (symbol, tomorrow, expiry_str),
    ).fetchone()

    if not row:
        return ExitTrigger(
            "RULE-EARN-003", "Earnings Override",
            triggered=False,
            reason="No earnings detected before expiration",
        )

    earn_str = row["earnings_date"]
    earn_dt = date.fromisoformat(earn_str)
    days_until = (earn_dt - today).days
    return ExitTrigger(
        "RULE-EARN-003", "Earnings Override",
        triggered=True,
        actual_value=earn_str,
        threshold=f"before expiration {expiry_str}",
        reason=f"Earnings on {earn_str} ({days_until}d away) — MANDATORY close before earnings",
    )


def _trigger_extreme_drop_from_entry(layer: dict, current_price: float | None) -> ExitTrigger:
    """RULE-EXIT-006 (optional overlay): drop ≥ 25% from entry price → EXIT_MONDAY."""
    if current_price is None:
        return ExitTrigger(
            "RULE-EXIT-006", "Extreme Drop from Entry (25%)",
            triggered=False, skipped=True,
            reason="No live price available — trigger skipped",
        )
    entry = layer["stock_price_at_entry"] or 0
    if entry <= 0:
        return ExitTrigger(
            "RULE-EXIT-006", "Extreme Drop from Entry (25%)",
            triggered=False, skipped=True,
            reason="Entry price is zero or null — trigger skipped",
        )
    pct = (current_price - entry) / entry * 100
    triggered = pct <= -25.0
    return ExitTrigger(
        "RULE-EXIT-006", "Extreme Drop from Entry (25%)",
        triggered=triggered,
        actual_value=f"{pct:+.1f}%",
        threshold="≤ −25%",
        reason=(
            f"Stock dropped {pct:.1f}% from entry ${entry:.2f} — exit optional at Monday open"
            if triggered else
            f"OK — {pct:+.1f}% from entry (threshold: −25%)"
        ),
    )


def _trigger_drop_below_put_strike(layer: dict, current_price: float | None) -> ExitTrigger:
    """RULE-EXIT-007 (optional overlay): drop ≥ 15% below put strike → EXIT_MONDAY."""
    if current_price is None:
        return ExitTrigger(
            "RULE-EXIT-007", "Drop Below Put Strike (15%)",
            triggered=False, skipped=True,
            reason="No live price available — trigger skipped",
        )
    put_strike = layer["put_strike"] or 0
    if put_strike <= 0:
        return ExitTrigger(
            "RULE-EXIT-007", "Drop Below Put Strike (15%)",
            triggered=False, skipped=True,
            reason="Put strike is zero or null — trigger skipped",
        )
    pct_below = (put_strike - current_price) / put_strike * 100
    triggered = pct_below >= 15.0
    return ExitTrigger(
        "RULE-EXIT-007", "Drop Below Put Strike (15%)",
        triggered=triggered,
        actual_value=f"{pct_below:+.1f}% below put",
        threshold="≥ 15% below put strike",
        reason=(
            f"Stock is {pct_below:.1f}% below put strike ${put_strike:.2f} — exit optional at Monday open"
            if triggered else
            f"OK — {pct_below:+.1f}% from put strike ${put_strike:.2f} (threshold: 15%)"
        ),
    )


def _trigger_expiration_check(layer: dict, today: date) -> ExitTrigger:
    """Expiration passed — layer needs resolution (run resolve_cycle_outcomes)."""
    expiry_dt = date.fromisoformat(layer["expiration_date"])
    triggered = today >= expiry_dt
    return ExitTrigger(
        "RULE-EXIT-001", "Expiration Status",
        triggered=triggered,
        actual_value=layer["expiration_date"],
        threshold=f"today={today.isoformat()}",
        reason=(
            f"Expiration date {layer['expiration_date']} has passed — call resolve_cycle_outcomes"
            if triggered else
            f"Not yet expired (expires {layer['expiration_date']})"
        ),
    )


def _trigger_dte_alert(layer: dict, today: date) -> ExitTrigger:
    """DTE ≤ 7 advisory alert — week of expiration, watch closely."""
    expiry_dt = date.fromisoformat(layer["expiration_date"])
    dte = (expiry_dt - today).days
    triggered = 0 < dte <= 7
    return ExitTrigger(
        "RULE-EXIT-001", "DTE Alert (≤ 7 days)",
        triggered=triggered,
        actual_value=f"{dte}d",
        threshold="≤ 7 days",
        reason=(
            f"Expiration in {dte} days — monitor closely this week"
            if triggered else
            f"{dte} days to expiration (threshold: 7)"
        ),
    )


def _trigger_strike_proximity(layer: dict, current_price: float | None) -> ExitTrigger:
    """Advisory: stock within 2% of call or put strike — assignment risk."""
    if current_price is None:
        return ExitTrigger(
            "RULE-EXIT-001", "Strike Proximity",
            triggered=False, skipped=True,
            reason="No live price — trigger skipped",
        )
    call_strike = layer["call_strike"] or 0
    put_strike = layer["put_strike"] or 0
    near_call = call_strike > 0 and abs(current_price - call_strike) / call_strike <= 0.02
    near_put = put_strike > 0 and abs(current_price - put_strike) / put_strike <= 0.02
    triggered = near_call or near_put
    sides = []
    if near_call:
        sides.append(f"call ${call_strike:.2f}")
    if near_put:
        sides.append(f"put ${put_strike:.2f}")
    return ExitTrigger(
        "RULE-EXIT-001", "Strike Proximity (2%)",
        triggered=triggered,
        actual_value=f"${current_price:.2f}",
        threshold="within 2% of either strike",
        reason=(
            f"Stock near {', '.join(sides)} — assignment risk elevated"
            if triggered else
            f"OK — price ${current_price:.2f} not near strikes (call ${call_strike:.2f}, put ${put_strike:.2f})"
        ),
    )


# ---------------------------------------------------------------------------
# Action determination
# ---------------------------------------------------------------------------

def _determine_action(triggers: list[ExitTrigger]) -> tuple[str, str, list[str], str]:
    """Return (recommended_action, urgency, rule_citations, reason) from trigger list."""
    # Priority order
    by_id = {t.rule_id + "|" + t.name: t for t in triggers}

    # 1. Earnings override — mandatory close
    earn = next((t for t in triggers if t.name == "Earnings Override" and t.triggered), None)
    if earn:
        return (
            ACTION_CLOSE_IMMEDIATELY, "IMMEDIATE",
            ["RULE-EARN-003"],
            earn.reason,
        )

    # 2. Expiration passed — needs resolution
    exp = next((t for t in triggers if t.name == "Expiration Status" and t.triggered), None)
    if exp:
        return (
            ACTION_NEEDS_RESOLUTION, "IMMEDIATE",
            ["RULE-EXIT-001", "RULE-EXIT-002", "RULE-EXIT-003", "RULE-EXIT-004"],
            exp.reason,
        )

    # 3. Extreme drop overlays (both are optional, but flag them)
    drop_entry = next((t for t in triggers if t.name == "Extreme Drop from Entry (25%)" and t.triggered), None)
    drop_put = next((t for t in triggers if t.name == "Drop Below Put Strike (15%)" and t.triggered), None)
    if drop_entry or drop_put:
        triggered_overlays = [t for t in [drop_entry, drop_put] if t]
        reasons = " | ".join(t.reason for t in triggered_overlays)
        citations = [t.rule_id for t in triggered_overlays]
        return (
            ACTION_EXIT_MONDAY, "THIS_WEEK",
            citations,
            f"OPTIONAL OVERLAY: {reasons}",
        )

    # 4. DTE ≤ 7 — advisory review
    dte = next((t for t in triggers if t.name == "DTE Alert (≤ 7 days)" and t.triggered), None)
    prox = next((t for t in triggers if t.name == "Strike Proximity (2%)" and t.triggered), None)
    if dte or prox:
        alerts = [t for t in [dte, prox] if t]
        reasons = " | ".join(t.reason for t in alerts)
        return (
            ACTION_REVIEW, "THIS_WEEK",
            ["RULE-EXIT-001"],
            reasons,
        )

    return ACTION_HOLD, "ROUTINE", [], "No exit triggers — hold to expiration"


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def _compute_metrics(layer: dict, current_price: float | None, decision: ExitDecision) -> None:
    """Fill derived price metrics on an ExitDecision in-place."""
    if current_price is None:
        return
    entry = layer["stock_price_at_entry"] or 0
    call = layer["call_strike"] or 0
    put = layer["put_strike"] or 0
    cap = layer["invested_capital"] or 0
    credit = layer["total_credit_collected"] or 0

    if entry > 0:
        decision.pct_change_from_entry = (current_price - entry) / entry * 100
    if call > 0 and current_price > call:
        decision.pct_above_call_strike = (current_price - call) / call * 100
    if put > 0 and current_price < put:
        decision.pct_below_put_strike = (put - current_price) / put * 100
    if cap > 0:
        decision.unrealized_premium_pct = credit / cap * 100


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_exit(
    layer_id: int,
    db_path: str,
    include_live_price: bool = True,
    persist: bool = True,
) -> ExitDecision | None:
    """
    Evaluate all exit triggers for one ACTIVE cycle_layer.

    Returns None if the layer does not exist or is not ACTIVE.
    When include_live_price=True, fetches from yfinance (may be slow — use
    evaluate_exit_batch with parallel=False for batch runs to control pacing).
    """
    with connect(db_path) as conn:
        layer = conn.execute(
            "SELECT cl.*, n.publication_date "
            "FROM cycle_layers cl "
            "JOIN newsletters n ON n.newsletter_id = cl.newsletter_id "
            "WHERE cl.layer_id = ? AND cl.status = 'ACTIVE'",
            (layer_id,),
        ).fetchone()
        if not layer:
            return None
        layer = dict(layer)

        today = date.today()
        expiry_dt = date.fromisoformat(layer["expiration_date"])
        dte = (expiry_dt - today).days

        # Live price
        current_price: float | None = None
        price_source = "unavailable"
        if include_live_price:
            current_price, price_source = _fetch_current_price(layer["symbol"])

        # Build triggers
        triggers = [
            _trigger_earnings_override(conn, layer, today),
            _trigger_extreme_drop_from_entry(layer, current_price),
            _trigger_drop_below_put_strike(layer, current_price),
            _trigger_expiration_check(layer, today),
            _trigger_dte_alert(layer, today),
            _trigger_strike_proximity(layer, current_price),
        ]

        action, urgency, citations, reason = _determine_action(triggers)

        decision = ExitDecision(
            layer_id=layer_id,
            symbol=layer["symbol"],
            account_id=layer["account_id"],
            newsletter_date=layer["publication_date"],
            expiration_date=layer["expiration_date"],
            evaluation_date=today.isoformat(),
            days_to_expiration=dte,
            stock_price_at_entry=layer["stock_price_at_entry"] or 0.0,
            call_strike=layer["call_strike"] or 0.0,
            put_strike=layer["put_strike"] or 0.0,
            total_credit_collected=layer["total_credit_collected"] or 0.0,
            invested_capital=layer["invested_capital"] or 0.0,
            current_price=current_price,
            price_source=price_source,
            triggers=triggers,
            recommended_action=action,
            action_urgency=urgency,
            rule_citations=citations,
            action_reason=reason,
        )

        _compute_metrics(layer, current_price, decision)

        if persist:
            _persist_exit_decision(conn, decision)

        return decision


def _persist_exit_decision(conn, decision: ExitDecision) -> None:
    """Insert or update an ExitDecision in exit_decisions table."""
    rule_json = json.dumps(decision.rule_citations)
    triggers_json = json.dumps([t.to_dict() for t in decision.triggers], sort_keys=True)
    values_json = json.dumps({
        "current_price": decision.current_price,
        "pct_change_from_entry": decision.pct_change_from_entry,
        "pct_above_call_strike": decision.pct_above_call_strike,
        "pct_below_put_strike": decision.pct_below_put_strike,
        "days_to_expiration": decision.days_to_expiration,
    })

    existing = conn.execute(
        "SELECT exit_decision_id FROM exit_decisions WHERE layer_id = ?",
        (decision.layer_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE exit_decisions SET
              evaluation_date     = ?,
              recommended_action  = ?,
              rule_citations_json = ?,
              trigger_values_json = ?,
              notes               = ?
            WHERE exit_decision_id = ?
            """,
            (
                decision.evaluation_date,
                decision.recommended_action,
                rule_json,
                values_json,
                triggers_json,
                existing["exit_decision_id"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO exit_decisions
            (layer_id, evaluation_date, recommended_action,
             rule_citations_json, trigger_values_json, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision.layer_id,
                decision.evaluation_date,
                decision.recommended_action,
                rule_json,
                values_json,
                triggers_json,
            ),
        )


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def evaluate_exit_batch(
    db_path: str,
    include_live_price: bool = True,
    persist: bool = True,
) -> list[ExitDecision]:
    """Evaluate exit triggers for all ACTIVE cycle_layers."""
    with connect(db_path) as conn:
        layer_ids = [
            r["layer_id"]
            for r in conn.execute(
                "SELECT layer_id FROM cycle_layers WHERE status = 'ACTIVE' "
                "ORDER BY newsletter_id, symbol"
            ).fetchall()
        ]

    results = []
    for lid in layer_ids:
        d = evaluate_exit(lid, db_path, include_live_price=include_live_price, persist=persist)
        if d:
            results.append(d)
    return results


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

_URGENCY_ICON = {
    "IMMEDIATE": "🔴",
    "THIS_WEEK": "🟡",
    "ROUTINE": "🟢",
}

_ACTION_LABEL = {
    ACTION_HOLD: "HOLD",
    ACTION_REVIEW: "REVIEW",
    ACTION_EXIT_MONDAY: "EXIT MONDAY",
    ACTION_CLOSE_IMMEDIATELY: "CLOSE NOW",
    ACTION_NEEDS_RESOLUTION: "NEEDS RESOLUTION",
}


def generate_exit_report(
    db_path: str,
    output_path: str | None = None,
    include_live_price: bool = True,
) -> str:
    """
    Generate a markdown exit monitoring report for all ACTIVE positions.

    Fetches live prices (unless include_live_price=False), evaluates all
    triggers, and returns a report grouped by urgency tier.
    """
    decisions = evaluate_exit_batch(db_path, include_live_price=include_live_price)

    today = date.today().isoformat()
    lines: list[str] = []
    lines.append("# Bull Strangle Exit Monitoring Report")
    lines.append("")
    lines.append(f"**Date:** {today}  **Active positions:** {len(decisions)}")
    lines.append("")

    if not decisions:
        lines.append("_No active positions._")
        report = "\n".join(lines)
        if output_path:
            import os
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        return report

    # Group by urgency
    by_urgency: dict[str, list[ExitDecision]] = {
        "IMMEDIATE": [],
        "THIS_WEEK": [],
        "ROUTINE": [],
    }
    for d in decisions:
        by_urgency.setdefault(d.action_urgency, []).append(d)

    # Summary table
    lines.append("## Position Summary")
    lines.append("")
    header = "| Symbol | Expiry | DTE | Entry | Current | Chg% | Call | Put | Action |"
    sep =    "|--------|--------|-----|-------|---------|------|------|-----|--------|"
    lines.append(header)
    lines.append(sep)

    for d in sorted(decisions, key=lambda x: (x.expiration_date, x.symbol)):
        icon = _URGENCY_ICON.get(d.action_urgency, "")
        price_str = f"${d.current_price:.2f}" if d.current_price else "N/A"
        chg_str = (
            f"{d.pct_change_from_entry:+.1f}%"
            if d.pct_change_from_entry is not None else "N/A"
        )
        action_str = f"{icon} {_ACTION_LABEL.get(d.recommended_action, d.recommended_action)}"
        lines.append(
            f"| {d.symbol:6s} "
            f"| {d.expiration_date} "
            f"| {d.days_to_expiration:3d} "
            f"| ${d.stock_price_at_entry:.2f} "
            f"| {price_str:7s} "
            f"| {chg_str:6s} "
            f"| ${d.call_strike:.2f} "
            f"| ${d.put_strike:.2f} "
            f"| {action_str} |"
        )
    lines.append("")

    # Detailed alerts by urgency
    for urgency in ["IMMEDIATE", "THIS_WEEK"]:
        group = by_urgency.get(urgency, [])
        if not group:
            continue
        icon = _URGENCY_ICON.get(urgency, "")
        lines.append(f"## {icon} {urgency} Actions")
        lines.append("")
        for d in group:
            lines.append(f"### {d.symbol} — {_ACTION_LABEL.get(d.recommended_action, d.recommended_action)}")
            lines.append("")
            lines.append(f"**Rule citations:** {', '.join(d.rule_citations)}")
            lines.append(f"**Reason:** {d.action_reason}")
            if d.current_price:
                lines.append(f"**Current price:** ${d.current_price:.2f}")
            lines.append(f"**Strikes:** call ${d.call_strike:.2f} / put ${d.put_strike:.2f}")
            lines.append(f"**Expiration:** {d.expiration_date} ({d.days_to_expiration}d)")
            lines.append("")

            # Triggered details
            triggered = [t for t in d.triggers if t.triggered and not t.skipped]
            if triggered:
                lines.append("**Triggered conditions:**")
                for t in triggered:
                    lines.append(f"- **{t.name}** ({t.rule_id}): {t.reason}")
                lines.append("")

    # Routine positions — compact
    routine = by_urgency.get("ROUTINE", [])
    if routine:
        lines.append("## 🟢 ROUTINE — Hold to Expiration")
        lines.append("")
        for d in routine:
            credit_pct = (
                f"{d.unrealized_premium_pct:.1f}%"
                if d.unrealized_premium_pct is not None else "N/A"
            )
            price_str = f"${d.current_price:.2f}" if d.current_price else "N/A"
            lines.append(
                f"- **{d.symbol}** exp {d.expiration_date} ({d.days_to_expiration}d) "
                f"| current: {price_str} "
                f"| credit: ${d.total_credit_collected:.0f} ({credit_pct} of capital)"
            )
        lines.append("")

    report = "\n".join(lines)

    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

    return report
