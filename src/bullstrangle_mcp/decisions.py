from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database
from .os_weekly import aggregate_os_week
from .positions import latest_position_state


STRATEGY_LOGIC_VERSION = "score_branch_v1"


# ── Weekly summary (moved from ingestion.py) ──────────────────────────────────
# These functions compute deployment decisions from market environment facts
# stored during ingestion.  They live here — not in ingestion.py — because
# they apply business rules to stored data rather than parsing PDF content.

def _bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def calculate_consecutive_weeks(
    conn: sqlite3.Connection,
    publication_date: date,
    current_met: bool,
) -> int:
    """Count how many consecutive weeks criteria have been met up to and including this week."""
    if not current_met:
        return 0
    rows = conn.execute(
        """
        SELECT publication_date, all_criteria_met
        FROM market_environment
        WHERE publication_date < ?
        ORDER BY publication_date DESC
        """,
        (publication_date.isoformat(),),
    ).fetchall()
    count = 1
    for row in rows:
        if row["all_criteria_met"]:
            count += 1
        else:
            break
    return count


def compute_weekly_summary(
    conn: sqlite3.Connection,
    newsletter_id: int,
    publication_date: date,
) -> None:
    """Compute and persist weekly deployment decision and symbol history.

    Called once per newsletter after all PDF sections have been inserted.
    Reads the market_environment row written by ingestion, applies the
    two-week confirmation rule, and writes to weekly_decisions and
    symbol_history.

    This is deliberately separate from the ingestion pipeline: ingestion
    stores facts; this function applies rules.  To re-evaluate decisions
    without re-ingesting the PDF, call this directly.
    """
    env = conn.execute(
        "SELECT * FROM market_environment WHERE newsletter_id = ?",
        (newsletter_id,),
    ).fetchone()

    all_criteria_met = bool(env["all_criteria_met"]) if env else False
    consecutive = calculate_consecutive_weeks(conn, publication_date, all_criteria_met)
    deployment_approved = all_criteria_met and consecutive >= 2
    action = (
        "deploy" if deployment_approved
        else ("monitor_only" if all_criteria_met else "pause")
    )
    scaling_phase = (
        "normal" if deployment_approved
        else ("rebuild_week1" if all_criteria_met else "pause")
    )
    recommended_position_count = 3 if deployment_approved else (1 if all_criteria_met else 0)

    if env:
        conn.execute(
            """
            UPDATE market_environment
            SET consecutive_weeks_met = ?, deployment_approved = ?,
                recommended_position_count = ?, scaling_phase = ?
            WHERE newsletter_id = ?
            """,
            (
                consecutive,
                _bool_int(deployment_approved),
                recommended_position_count,
                scaling_phase,
                newsletter_id,
            ),
        )

    rationale = {
        "decision": action,
        "reason": (
            "Two-week confirmation met" if deployment_approved
            else ("Week 1 of confirmation" if all_criteria_met
                  else "One or more market criteria failed")
        ),
        "criteria_status": {
            "all_criteria_met": all_criteria_met,
            "consecutive_weeks": {
                "value": consecutive,
                "threshold": 2,
                "passed": consecutive >= 2,
            },
        },
    }
    conn.execute(
        """
        INSERT INTO weekly_decisions
        (newsletter_id, publication_date, all_criteria_met, consecutive_weeks_met,
         deployment_approved, action_taken, positions_deployed, symbols_deployed,
         decision_rationale)
        VALUES (?, ?, ?, ?, ?, ?, 0, '[]', ?)
        ON CONFLICT(newsletter_id) DO UPDATE SET
            publication_date = excluded.publication_date,
            all_criteria_met = excluded.all_criteria_met,
            consecutive_weeks_met = excluded.consecutive_weeks_met,
            deployment_approved = excluded.deployment_approved,
            action_taken = excluded.action_taken,
            positions_deployed = excluded.positions_deployed,
            symbols_deployed = excluded.symbols_deployed,
            decision_rationale = excluded.decision_rationale,
            decision_timestamp = CURRENT_TIMESTAMP
        """,
        (
            newsletter_id,
            publication_date.isoformat(),
            _bool_int(all_criteria_met),
            consecutive,
            _bool_int(deployment_approved),
            action,
            json.dumps(rationale, sort_keys=True),
        ),
    )

    short_rows = conn.execute(
        """
        SELECT symbol, group_concat(portfolio_type) AS portfolios
        FROM short_list_entries
        WHERE newsletter_id = ?
        GROUP BY symbol
        """,
        (newsletter_id,),
    ).fetchall()
    short_map = {row["symbol"]: row["portfolios"] for row in short_rows}

    entries = conn.execute(
        "SELECT * FROM watchlist_entries WHERE newsletter_id = ? ORDER BY symbol",
        (newsletter_id,),
    ).fetchall()
    conn.execute("DELETE FROM symbol_history WHERE newsletter_id = ?", (newsletter_id,))
    for entry in entries:
        on_short = entry["symbol"] in short_map
        conn.execute(
            """
            INSERT INTO symbol_history
            (symbol, newsletter_id, publication_date, on_watchlist, on_short_list, metadata)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (
                entry["symbol"],
                newsletter_id,
                publication_date.isoformat(),
                _bool_int(on_short),
                json.dumps({"source": "newsletter_ingestion"}, sort_keys=True),
            ),
        )


DEFAULT_RULES = {
    "bull_strangle": {
        "max_price_deviation_pct": 0.08,
        "max_credit_deviation": 2.50,
        "minimum_total_credit": 0.01,
    },
    "dca": {
        "max_price_deviation_pct": 0.08,
        "minimum_candidate_score": 1.0,
    },
}


def load_decision_rules(conn: sqlite3.Connection) -> dict[str, Any]:
    """Load numeric decision thresholds from the strategy_rules table.

    Returns a dict with the same shape as DEFAULT_RULES.  If the
    decision_threshold rows are absent (fresh DB before first init) the
    function falls back to DEFAULT_RULES so callers never break.

    Threshold rule_name convention: ``<category>_<key>``, e.g.
    ``bull_strangle_max_price_deviation_pct``.  The numeric value is stored
    as ``{"value": <float>}`` in the rule_parameters JSON column.
    """
    rows = conn.execute(
        """
        SELECT rule_name, rule_parameters
        FROM   strategy_rules
        WHERE  rule_category = 'decision_threshold'
          AND  is_active      = 1
        """
    ).fetchall()

    if not rows:
        return DEFAULT_RULES

    import copy

    rules: dict[str, Any] = copy.deepcopy(DEFAULT_RULES)
    for row in rows:
        name: str = row["rule_name"]
        try:
            params = json.loads(row["rule_parameters"] or "{}")
            value = params.get("value")
            if value is None:
                continue
        except (ValueError, TypeError):
            continue

        if name.startswith("bull_strangle_"):
            key = name[len("bull_strangle_"):]
            if key in rules["bull_strangle"]:
                rules["bull_strangle"][key] = float(value)
        elif name.startswith("dca_"):
            key = name[len("dca_"):]
            if key in rules["dca"]:
                rules["dca"][key] = float(value)

    return rules


def generate_weekend_decisions(
    newsletter_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    decision_date: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_database(db_path)
    decision_date = decision_date or date.today().isoformat()
    aggregate = aggregate_os_week(newsletter_date, db_path)
    position_run_id, position_rollups = latest_position_state(db_path)
    positions_available = bool(position_rollups)

    with connect(db_path) as conn:
        newsletter = conn.execute(
            """
            SELECT newsletter_id, publication_date, target_expiration
            FROM newsletters
            WHERE publication_date = ?
            """,
            (newsletter_date,),
        ).fetchone()
        if not newsletter:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")

        market = conn.execute(
            """
            SELECT *
            FROM market_environment
            WHERE newsletter_id = ?
            """,
            (newsletter["newsletter_id"],),
        ).fetchone()
        if not market:
            raise ValueError(f"Market environment not found for date: {newsletter_date}")

        source_dates = conn.execute(
            """
            SELECT MIN(trading_date) AS start_date, MAX(trading_date) AS end_date
            FROM os_evaluation_runs
            WHERE newsletter_id = ?
            """,
            (newsletter["newsletter_id"],),
        ).fetchone()
        short_list_symbols = {
            row["symbol"]
            for row in conn.execute(
                """
                SELECT DISTINCT symbol
                FROM short_list_entries
                WHERE newsletter_id = ?
                """,
                (newsletter["newsletter_id"],),
            ).fetchall()
        }

        loaded_rules = load_decision_rules(conn)
        batch_id = _upsert_batch(
            conn,
            newsletter=dict(newsletter),
            market=dict(market),
            aggregate=aggregate,
            decision_date=decision_date,
            source_start=source_dates["start_date"],
            source_end=source_dates["end_date"],
            position_run_id=position_run_id,
            rules=loaded_rules,
        )
        conn.execute("DELETE FROM bull_strangle_decisions WHERE decision_batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM dca_decisions WHERE decision_batch_id = ?", (batch_id,))

        rows = conn.execute(
            """
            SELECT w.*, a.*
            FROM watchlist_entries w
            LEFT JOIN os_weekly_symbol_aggregates a
              ON a.newsletter_id = w.newsletter_id AND a.symbol = w.symbol
            WHERE w.newsletter_id = ?
            ORDER BY w.symbol
            """,
            (newsletter["newsletter_id"],),
        ).fetchall()

        bull_rows = []
        dca_rows = []
        for row in rows:
            row_dict = dict(row)
            position = position_rollups.get(row_dict["symbol"])
            strategy_context = _build_strategy_context(
                dict(market),
                row_dict,
                position,
                positions_available,
                short_list_symbols,
                rules=loaded_rules,
            )
            bull_rows.append(
                _build_bull_decision(
                    batch_id,
                    dict(market),
                    row_dict,
                    position,
                    strategy_context,
                    rules=loaded_rules,
                )
            )
            dca_rows.append(
                _build_dca_decision(
                    batch_id,
                    dict(market),
                    row_dict,
                    position,
                    strategy_context,
                    rules=loaded_rules,
                )
            )

        bull_rows = _rank_decisions(bull_rows)
        dca_rows = _rank_decisions(dca_rows)
        _insert_bull_decisions(conn, bull_rows)
        _insert_dca_decisions(conn, dca_rows)
        conn.commit()

    result = {
        "decision_batch_id": batch_id,
        "newsletter_id": int(newsletter["newsletter_id"]),
        "newsletter_date": newsletter["publication_date"],
        "expiration_date": newsletter["target_expiration"],
        "decision_date": decision_date,
        "market_status": market["market_status"],
        "deployment_approved": int(market["deployment_approved"] or 0),
        "os_run_count": aggregate["run_count"],
        "position_run_id": position_run_id,
        "positions_available": positions_available,
        "bull_strangle_counts": _decision_counts(bull_rows),
        "dca_counts": _decision_counts(dca_rows),
        "selected_action_counts": _selected_action_counts(bull_rows),
        "bull_strangle_decisions": bull_rows,
        "dca_decisions": dca_rows,
    }
    result["markdown"] = render_weekend_decisions_markdown(result)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result["markdown"], encoding="utf-8")
        result["output_path"] = str(out.resolve())
    return result


def render_weekend_decisions_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Weekend Decisions {result['newsletter_date']}",
        "",
        "## Summary",
        "",
        f"- Decision batch: {result['decision_batch_id']}",
        f"- Newsletter date: {result['newsletter_date']}",
        f"- Expiration date: {result['expiration_date']}",
        f"- Decision date: {result['decision_date']}",
        f"- Market status: {result['market_status']}",
        f"- Deployment approved: {bool(result['deployment_approved'])}",
        f"- OS run count: {result['os_run_count']}",
        f"- Position run id: {result['position_run_id'] or 'none'}",
        f"- Preferred actions: {_counts_text(result['selected_action_counts'], ['BULL_STRANGLE', 'DCA', 'WATCH', 'SKIP'])}",
        f"- Bull Strangle: {_counts_text(result['bull_strangle_counts'])}",
        f"- DCA: {_counts_text(result['dca_counts'])}",
        "",
    ]
    lines.extend(_decision_table("Bull Strangle Decisions", result["bull_strangle_decisions"]))
    lines.extend(_decision_table("DCA Decisions", result["dca_decisions"]))
    return "\n".join(lines).rstrip() + "\n"


def _upsert_batch(
    conn,
    newsletter: dict[str, Any],
    market: dict[str, Any],
    aggregate: dict[str, Any],
    decision_date: str,
    source_start: str | None,
    source_end: str | None,
    position_run_id: int | None,
    rules: dict[str, Any],
) -> int:
    snapshot = {
        "market_environment": {
            "hybrid_score": market.get("hybrid_score"),
            "market_status": market.get("market_status"),
            "deployment_approved": market.get("deployment_approved"),
            "investment_percent": market.get("investment_percent"),
        },
        "weekly_aggregate": {
            "run_count": aggregate["run_count"],
            "symbol_count": aggregate["symbol_count"],
            "valid_symbol_count": aggregate["valid_symbol_count"],
            "invalid_symbol_count": aggregate["invalid_symbol_count"],
            "run_ids": aggregate["run_ids"],
        },
        "rules": rules,
        "strategy_logic_version": STRATEGY_LOGIC_VERSION,
        "position_run_id": position_run_id,
    }
    conn.execute(
        """
        INSERT INTO decision_batches
        (newsletter_id, newsletter_date, expiration_date, decision_date,
         source_run_start_date, source_run_end_date, market_environment_id,
         position_run_id, os_run_count, strategy_logic_version, status, source_snapshot_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?)
        ON CONFLICT(newsletter_id, decision_date) DO UPDATE SET
            expiration_date = excluded.expiration_date,
            source_run_start_date = excluded.source_run_start_date,
            source_run_end_date = excluded.source_run_end_date,
            market_environment_id = excluded.market_environment_id,
            position_run_id = excluded.position_run_id,
            os_run_count = excluded.os_run_count,
            strategy_logic_version = excluded.strategy_logic_version,
            status = excluded.status,
            source_snapshot_json = excluded.source_snapshot_json
        """,
        (
            newsletter["newsletter_id"],
            newsletter["publication_date"],
            newsletter["target_expiration"],
            decision_date,
            source_start,
            source_end,
            market["env_id"],
            position_run_id,
            aggregate["run_count"],
            STRATEGY_LOGIC_VERSION,
            json.dumps(snapshot, sort_keys=True),
        ),
    )
    row = conn.execute(
        """
        SELECT decision_batch_id
        FROM decision_batches
        WHERE newsletter_id = ? AND decision_date = ?
        """,
        (newsletter["newsletter_id"], decision_date),
    ).fetchone()
    return int(row["decision_batch_id"])


def _build_bull_decision(
    batch_id: int,
    market: dict[str, Any],
    row: dict[str, Any],
    position: dict[str, Any] | None,
    strategy_context: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    full_rules = rules or DEFAULT_RULES
    rules_applied = full_rules["bull_strangle"]
    final, reasons = _decision_outcome_for_action("BULL_STRANGLE", strategy_context)
    passed_rules, failed_rules = _build_rule_diagnostics("BULL_STRANGLE", strategy_context, rules=full_rules)

    return {
        "decision_batch_id": batch_id,
        "newsletter_id": row["newsletter_id"],
        "newsletter_date": row["newsletter_date"],
        "expiration_date": row["expiration_date"],
        "watchlist_entry_id": row["entry_id"],
        "symbol": row["symbol"],
        "final_decision": final,
        "priority_rank": None,
        "selected_action": strategy_context["selected_action"],
        "strategy_score": strategy_context["strategy_score"],
        "strategy_band": strategy_context["strategy_band"],
        "market_approved": strategy_context["market_approved"],
        "os_week_valid": strategy_context["os_valid"],
        "latest_total_credit": strategy_context["latest_credit"],
        "latest_live_stock_price": row.get("latest_live_stock_price"),
        "max_price_deviation_pct": strategy_context["price_deviation"],
        "max_credit_deviation": strategy_context["credit_deviation"],
        "selected_account": strategy_context["selected_account"],
        "account_shares": position.get("max_account_quantity") if position else None,
        "consolidated_shares": position.get("total_quantity") if position else None,
        "shares_to_100": position.get("shares_to_100") if position else None,
        "rules_applied_json": json.dumps(rules_applied, sort_keys=True),
        "rules_passed_json": json.dumps(passed_rules, sort_keys=True),
        "rules_failed_json": json.dumps(failed_rules, sort_keys=True),
        "criteria_json": json.dumps(strategy_context, sort_keys=True),
        "source_snapshot_json": _source_snapshot(row, position, strategy_context),
        "reason": "; ".join(reasons) if reasons else "Bull Strangle chosen as preferred strategy action",
    }


def _build_dca_decision(
    batch_id: int,
    market: dict[str, Any],
    row: dict[str, Any],
    position: dict[str, Any] | None,
    strategy_context: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    full_rules = rules or DEFAULT_RULES
    rules_applied = full_rules["dca"]
    final, reasons = _decision_outcome_for_action("DCA", strategy_context)
    passed_rules, failed_rules = _build_rule_diagnostics("DCA", strategy_context, rules=full_rules)
    account_shares = position.get("max_account_quantity") if position else 0
    consolidated_shares = position.get("total_quantity") if position else 0
    target_account = strategy_context["selected_account"]
    shares_to_100 = position.get("shares_to_100") if position else 100

    return {
        "decision_batch_id": batch_id,
        "newsletter_id": row["newsletter_id"],
        "newsletter_date": row["newsletter_date"],
        "watchlist_entry_id": row["entry_id"],
        "symbol": row["symbol"],
        "final_decision": final,
        "priority_rank": None,
        "selected_action": strategy_context["selected_action"],
        "strategy_score": strategy_context["strategy_score"],
        "strategy_band": strategy_context["strategy_band"],
        "market_allocation_ok": strategy_context["market_approved"],
        "dca_candidate_score": strategy_context["strategy_score"],
        "latest_live_price": row.get("latest_live_stock_price"),
        "weekly_price_trend": strategy_context["trend"],
        "max_price_deviation_pct": strategy_context["price_deviation"],
        "selected_account": target_account,
        "account_shares": account_shares,
        "consolidated_shares": consolidated_shares,
        "shares_to_100": shares_to_100,
        "rules_applied_json": json.dumps(rules_applied, sort_keys=True),
        "rules_passed_json": json.dumps(passed_rules, sort_keys=True),
        "rules_failed_json": json.dumps(failed_rules, sort_keys=True),
        "criteria_json": json.dumps(strategy_context, sort_keys=True),
        "source_snapshot_json": _source_snapshot(row, position, strategy_context),
        "reason": "; ".join(reasons) if reasons else "DCA chosen as preferred strategy action",
    }


def _rank_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
        decision_weight = {"APPROVE": 0, "WATCH": 1, "SKIP": 2}[row["final_decision"]]
        score = row.get("latest_total_credit")
        if score is None:
            score = row.get("dca_candidate_score") or 0
        return (decision_weight, -float(score or 0), row["symbol"])

    ranked = sorted(rows, key=sort_key)
    for index, row in enumerate(ranked, start=1):
        row["priority_rank"] = index
    return ranked


def _insert_bull_decisions(conn, rows: list[dict[str, Any]]) -> None:
    columns = [
        "decision_batch_id",
        "newsletter_id",
        "newsletter_date",
        "expiration_date",
        "watchlist_entry_id",
        "symbol",
        "final_decision",
        "priority_rank",
        "selected_action",
        "strategy_score",
        "strategy_band",
        "market_approved",
        "os_week_valid",
        "latest_total_credit",
        "latest_live_stock_price",
        "max_price_deviation_pct",
        "max_credit_deviation",
        "selected_account",
        "account_shares",
        "consolidated_shares",
        "shares_to_100",
        "rules_applied_json",
        "rules_passed_json",
        "rules_failed_json",
        "criteria_json",
        "source_snapshot_json",
        "reason",
    ]
    _insert_rows(conn, "bull_strangle_decisions", columns, rows)


def _insert_dca_decisions(conn, rows: list[dict[str, Any]]) -> None:
    columns = [
        "decision_batch_id",
        "newsletter_id",
        "newsletter_date",
        "watchlist_entry_id",
        "symbol",
        "final_decision",
        "priority_rank",
        "selected_action",
        "strategy_score",
        "strategy_band",
        "market_allocation_ok",
        "dca_candidate_score",
        "latest_live_price",
        "weekly_price_trend",
        "max_price_deviation_pct",
        "selected_account",
        "account_shares",
        "consolidated_shares",
        "shares_to_100",
        "rules_applied_json",
        "rules_passed_json",
        "rules_failed_json",
        "criteria_json",
        "source_snapshot_json",
        "reason",
    ]
    _insert_rows(conn, "dca_decisions", columns, rows)


def _insert_rows(conn, table_name: str, columns: list[str], rows: list[dict[str, Any]]) -> None:
    placeholders = ", ".join(["?"] * len(columns))
    conn.executemany(
        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )


def _source_snapshot(
    row: dict[str, Any],
    position: dict[str, Any] | None = None,
    strategy_context: dict[str, Any] | None = None,
) -> str:
    snapshot = {
        "newsletter_baseline": {
            "stock_price": row.get("stock_price"),
            "sell_call_strike": row.get("sell_call_strike"),
            "sell_put_strike": row.get("sell_put_strike"),
            "buy_put_strike": row.get("buy_put_strike"),
            "is_favorite": row.get("is_favorite"),
        },
        "weekly_aggregate": {
            "run_count": row.get("run_count"),
            "latest_run_id": row.get("latest_run_id"),
            "latest_live_stock_price": row.get("latest_live_stock_price"),
            "latest_total_credit": row.get("latest_total_credit"),
            "missing_core_value_days": row.get("missing_core_value_days"),
        },
        "position_context": {
            "selected_account": (
                position.get("eligible_account") or position.get("dca_target_account")
                if position
                else None
            ),
            "account_shares": position.get("max_account_quantity") if position else None,
            "consolidated_shares": position.get("total_quantity") if position else None,
            "shares_to_100": position.get("shares_to_100") if position else None,
        },
        "strategy_context": {
            "selected_action": strategy_context.get("selected_action") if strategy_context else None,
            "strategy_score": strategy_context.get("strategy_score") if strategy_context else None,
            "strategy_band": strategy_context.get("strategy_band") if strategy_context else None,
            "accumulation_preferred": (
                strategy_context.get("accumulation_preferred") if strategy_context else None
            ),
        },
    }
    return json.dumps(snapshot, sort_keys=True)


def _build_strategy_context(
    market: dict[str, Any],
    row: dict[str, Any],
    position: dict[str, Any] | None,
    positions_available: bool,
    short_list_symbols: set[str],
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bs_rules = (rules or DEFAULT_RULES)["bull_strangle"]
    market_approved = int(market.get("deployment_approved") or 0)
    os_valid = int(row.get("is_week_valid") or 0)
    latest_credit = row.get("latest_total_credit")
    latest_live_price = row.get("latest_live_stock_price")
    baseline_price = row.get("stock_price")
    call_strike = row.get("sell_call_strike")
    price_deviation = row.get("worst_abs_stock_price_deviation_pct")
    credit_deviation = row.get("worst_abs_total_credit_deviation")
    trend = _price_trend(row)
    account_shares = float(position.get("max_account_quantity") or 0) if position else 0.0
    consolidated_shares = float(position.get("total_quantity") or 0) if position else 0.0
    bull_stock_backed_ready = bool(position and int(position.get("bull_strangle_ready") or 0))
    price_attractive_for_dca = bool(
        latest_live_price is not None
        and baseline_price is not None
        and float(latest_live_price) <= float(baseline_price) * 0.97
        and (call_strike is None or float(latest_live_price) < float(call_strike))
    )
    accumulation_preferred = bool(
        (0 < account_shares < 100)
        or (positions_available and position is not None and account_shares < 100 and price_attractive_for_dca)
        or (not positions_available and price_attractive_for_dca)
    )
    selected_account = (
        position.get("dca_target_account")
        if position
        else None
    )
    strategy_score = 0.0
    if market_approved:
        strategy_score += 2.0
    if os_valid:
        strategy_score += 2.0
    if latest_credit is not None and float(latest_credit) > 0:
        strategy_score += 1.0
    if price_deviation is None or float(price_deviation) <= bs_rules["max_price_deviation_pct"]:
        strategy_score += 1.0
    if credit_deviation is None or float(credit_deviation) <= bs_rules["max_credit_deviation"]:
        strategy_score += 1.0
    if row.get("is_favorite"):
        strategy_score += 1.0
    if row.get("symbol") in short_list_symbols:
        strategy_score += 1.0
    if latest_live_price is not None and call_strike is not None and float(latest_live_price) < float(call_strike):
        strategy_score += 1.0
    strategy_score = round(strategy_score, 2)
    if strategy_score >= 8:
        strategy_band = "strong"
    elif strategy_score >= 6:
        strategy_band = "moderate"
    elif strategy_score >= 4:
        strategy_band = "watch"
    else:
        strategy_band = "weak"

    direct_bull_viable = bool(
        market_approved
        and os_valid
        and latest_credit is not None
        and float(latest_credit) >= bs_rules["minimum_total_credit"]
        and (price_deviation is None or float(price_deviation) <= bs_rules["max_price_deviation_pct"])
        and (credit_deviation is None or float(credit_deviation) <= bs_rules["max_credit_deviation"])
        and strategy_band in {"strong", "moderate"}
    )
    dca_viable = bool(
        market_approved
        and os_valid
        and strategy_band in {"strong", "moderate"}
        and accumulation_preferred
    )

    if direct_bull_viable and not accumulation_preferred:
        selected_action = "BULL_STRANGLE"
    elif dca_viable:
        selected_action = "DCA"
    elif strategy_band in {"strong", "moderate", "watch"}:
        selected_action = "WATCH"
    else:
        selected_action = "SKIP"

    return {
        "market_approved": market_approved,
        "os_valid": os_valid,
        "latest_credit": latest_credit,
        "latest_live_price": latest_live_price,
        "baseline_price": baseline_price,
        "call_strike": call_strike,
        "price_deviation": price_deviation,
        "credit_deviation": credit_deviation,
        "trend": trend,
        "strategy_score": strategy_score,
        "strategy_band": strategy_band,
        "selected_action": selected_action,
        "selected_account": selected_account,
        "positions_available": positions_available,
        "account_shares": account_shares,
        "consolidated_shares": consolidated_shares,
        "bull_stock_backed_ready": bull_stock_backed_ready,
        "accumulation_preferred": accumulation_preferred,
        "price_attractive_for_dca": price_attractive_for_dca,
        "is_short_listed": row.get("symbol") in short_list_symbols,
        "is_favorite": bool(row.get("is_favorite")),
    }


def _build_rule_diagnostics(
    action_type: str,
    strategy_context: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # rules is the full rules dict (same shape as DEFAULT_RULES), or None.
    # Deviation diagnostics always use bull_strangle thresholds regardless of action_type.
    bs_rules = (rules or DEFAULT_RULES)["bull_strangle"]
    passed: dict[str, Any] = {
        "market_approved": bool(strategy_context["market_approved"]),
        "os_valid": bool(strategy_context["os_valid"]),
        "strategy_band": strategy_context["strategy_band"],
        "selected_action": strategy_context["selected_action"],
    }
    failed: dict[str, Any] = {}

    credit_ok = strategy_context["latest_credit"] is not None and float(strategy_context["latest_credit"]) > 0
    price_ok = strategy_context["price_deviation"] is None or float(strategy_context["price_deviation"]) <= bs_rules["max_price_deviation_pct"]
    credit_dev_ok = strategy_context["credit_deviation"] is None or float(strategy_context["credit_deviation"]) <= bs_rules["max_credit_deviation"]

    if credit_ok:
        passed["latest_credit_positive"] = True
    else:
        failed["latest_credit_positive"] = strategy_context["latest_credit"]

    if price_ok:
        passed["price_deviation_within_threshold"] = strategy_context["price_deviation"]
    else:
        failed["price_deviation_within_threshold"] = strategy_context["price_deviation"]

    if credit_dev_ok:
        passed["credit_deviation_within_threshold"] = strategy_context["credit_deviation"]
    else:
        failed["credit_deviation_within_threshold"] = strategy_context["credit_deviation"]

    if strategy_context["is_favorite"]:
        passed["favorite_symbol"] = True
    if strategy_context["is_short_listed"]:
        passed["short_listed"] = True
    if strategy_context["price_attractive_for_dca"]:
        passed["price_attractive_for_dca"] = True

    if action_type == "BULL_STRANGLE":
        if strategy_context["selected_action"] == "BULL_STRANGLE":
            passed["preferred_action_match"] = True
        else:
            failed["preferred_action_match"] = strategy_context["selected_action"]
        if strategy_context["bull_stock_backed_ready"]:
            passed["stock_backed_ready"] = True
    else:
        if strategy_context["selected_action"] == "DCA":
            passed["preferred_action_match"] = True
        else:
            failed["preferred_action_match"] = strategy_context["selected_action"]
        if strategy_context["selected_account"]:
            passed["selected_account"] = strategy_context["selected_account"]
        if strategy_context["accumulation_preferred"]:
            passed["accumulation_preferred"] = True
        else:
            failed["accumulation_preferred"] = False

    if not strategy_context["market_approved"]:
        failed["market_approved"] = False
    if not strategy_context["os_valid"]:
        failed["os_valid"] = False
    if strategy_context["strategy_band"] == "weak":
        failed["strategy_band"] = "weak"

    return passed, failed


def _decision_outcome_for_action(
    action_type: str,
    strategy_context: dict[str, Any],
) -> tuple[str, list[str]]:
    selected_action = strategy_context["selected_action"]
    reasons: list[str] = []
    if action_type == "BULL_STRANGLE":
        if selected_action == "BULL_STRANGLE":
            return "APPROVE", reasons
        if selected_action == "DCA":
            reasons.append("DCA chosen as preferred strategy action")
            return "SKIP", reasons
        if selected_action == "WATCH":
            reasons.extend(_watch_reasons(strategy_context))
            return "WATCH", reasons
        reasons.extend(_skip_reasons(strategy_context))
        return "SKIP", reasons
    if selected_action == "DCA":
        return "APPROVE", reasons
    if selected_action == "BULL_STRANGLE":
        reasons.append("Bull Strangle chosen as preferred strategy action")
        return "SKIP", reasons
    if selected_action == "WATCH":
        reasons.extend(_watch_reasons(strategy_context))
        return "WATCH", reasons
    reasons.extend(_skip_reasons(strategy_context))
    return "SKIP", reasons


def _watch_reasons(strategy_context: dict[str, Any]) -> list[str]:
    reasons = []
    if not strategy_context["market_approved"]:
        reasons.append("market deployment is not approved")
    if not strategy_context["os_valid"]:
        reasons.append("weekly OS data has missing core values")
    if strategy_context["selected_action"] == "WATCH" and strategy_context["strategy_band"] in {"strong", "moderate"}:
        reasons.append("setup scores well but is not the preferred executable action yet")
    return reasons or ["setup remains on watch"]


def _skip_reasons(strategy_context: dict[str, Any]) -> list[str]:
    reasons = []
    if not strategy_context["os_valid"]:
        reasons.append("weekly OS data has missing core values")
    if strategy_context["latest_credit"] is None or float(strategy_context["latest_credit"] or 0) <= 0:
        reasons.append("latest total credit is missing or not positive")
    if strategy_context["strategy_band"] == "weak":
        reasons.append("strategy score is too weak")
    return reasons or ["setup is not actionable"]


def _price_trend(row: dict[str, Any]) -> float | None:
    first = row.get("first_live_stock_price")
    latest = row.get("latest_live_stock_price")
    if first in (None, 0) or latest is None:
        return None
    return (float(latest) - float(first)) / float(first)


def _decision_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"APPROVE": 0, "WATCH": 0, "SKIP": 0}
    for row in rows:
        counts[row["final_decision"]] += 1
    return counts


def _selected_action_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"BULL_STRANGLE": 0, "DCA": 0, "WATCH": 0, "SKIP": 0}
    seen = set()
    for row in rows:
        symbol = row["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)
        counts[row["selected_action"]] += 1
    return counts


def _counts_text(counts: dict[str, int], order: list[str] | None = None) -> str:
    order = order or ["APPROVE", "WATCH", "SKIP"]
    return ", ".join(f"{name} {counts.get(name, 0)}" for name in order)


def _decision_table(title: str, rows: list[dict[str, Any]], limit: int = 12) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["None.", ""]
    headers = [
        "rank",
        "symbol",
        "decision",
        "action",
        "score",
        "account",
        "acct_shares",
        "to_100",
        "credit_or_score",
        "max_price_dev",
        "reason",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows[:limit]:
        credit_or_score = row.get("latest_total_credit")
        if credit_or_score is None:
            credit_or_score = row.get("dca_candidate_score")
        max_price_dev = row.get("max_price_deviation_pct")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["priority_rank"]),
                    row["symbol"],
                    row["final_decision"],
                    row.get("selected_action") or "",
                    _format_number(row.get("strategy_score")),
                    str(row.get("selected_account") or ""),
                    _format_number(row.get("account_shares")),
                    _format_number(row.get("shares_to_100")),
                    _format_number(credit_or_score),
                    _format_percent(max_price_dev),
                    row["reason"].replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _format_number(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}"


def _format_percent(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value) * 100:.2f}%"
