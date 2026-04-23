from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database
from .os_weekly import aggregate_os_week
from .positions import latest_position_rollups


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


def generate_weekend_decisions(
    newsletter_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    decision_date: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_database(db_path)
    decision_date = decision_date or date.today().isoformat()
    aggregate = aggregate_os_week(newsletter_date, db_path)
    position_rollups = latest_position_rollups(db_path)
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

        batch_id = _upsert_batch(
            conn,
            newsletter=dict(newsletter),
            market=dict(market),
            aggregate=aggregate,
            decision_date=decision_date,
            source_start=source_dates["start_date"],
            source_end=source_dates["end_date"],
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
            bull_rows.append(
                _build_bull_decision(
                    batch_id,
                    dict(market),
                    row_dict,
                    position,
                    positions_available,
                )
            )
            dca_rows.append(
                _build_dca_decision(
                    batch_id,
                    dict(market),
                    row_dict,
                    position,
                    positions_available,
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
        "positions_available": positions_available,
        "bull_strangle_counts": _decision_counts(bull_rows),
        "dca_counts": _decision_counts(dca_rows),
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
        "rules": DEFAULT_RULES,
    }
    conn.execute(
        """
        INSERT INTO decision_batches
        (newsletter_id, newsletter_date, expiration_date, decision_date,
         source_run_start_date, source_run_end_date, market_environment_id,
         os_run_count, status, source_snapshot_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?)
        ON CONFLICT(newsletter_id, decision_date) DO UPDATE SET
            expiration_date = excluded.expiration_date,
            source_run_start_date = excluded.source_run_start_date,
            source_run_end_date = excluded.source_run_end_date,
            market_environment_id = excluded.market_environment_id,
            os_run_count = excluded.os_run_count,
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
            aggregate["run_count"],
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
    positions_available: bool,
) -> dict[str, Any]:
    rules = DEFAULT_RULES["bull_strangle"]
    market_approved = int(market.get("deployment_approved") or 0)
    os_valid = int(row.get("is_week_valid") or 0)
    latest_credit = row.get("latest_total_credit")
    price_deviation = row.get("worst_abs_stock_price_deviation_pct")
    credit_deviation = row.get("worst_abs_total_credit_deviation")
    position_ready = (
        not positions_available
        or (position is not None and int(position.get("bull_strangle_ready") or 0) == 1)
    )
    reasons = []
    if not market_approved:
        reasons.append("market deployment is not approved")
    if not os_valid:
        reasons.append("weekly OS data has missing core values")
    if latest_credit is None or latest_credit < rules["minimum_total_credit"]:
        reasons.append("latest total credit is missing or not positive")
    if price_deviation is not None and price_deviation > rules["max_price_deviation_pct"]:
        reasons.append("price deviation exceeds threshold")
    if credit_deviation is not None and credit_deviation > rules["max_credit_deviation"]:
        reasons.append("credit deviation exceeds threshold")
    if not position_ready:
        reasons.append("no single account has 100 shares for Bull Strangle promotion")

    if market_approved and os_valid and position_ready and not reasons:
        final = "APPROVE"
    elif os_valid and latest_credit is not None and latest_credit > 0:
        final = "WATCH"
    else:
        final = "SKIP"

    return {
        "decision_batch_id": batch_id,
        "newsletter_id": row["newsletter_id"],
        "newsletter_date": row["newsletter_date"],
        "expiration_date": row["expiration_date"],
        "watchlist_entry_id": row["entry_id"],
        "symbol": row["symbol"],
        "final_decision": final,
        "priority_rank": None,
        "market_approved": market_approved,
        "os_week_valid": os_valid,
        "latest_total_credit": latest_credit,
        "latest_live_stock_price": row.get("latest_live_stock_price"),
        "max_price_deviation_pct": price_deviation,
        "max_credit_deviation": credit_deviation,
        "selected_account": position.get("eligible_account") if position else None,
        "account_shares": position.get("max_account_quantity") if position else None,
        "consolidated_shares": position.get("total_quantity") if position else None,
        "shares_to_100": position.get("shares_to_100") if position else None,
        "rules_applied_json": json.dumps(rules, sort_keys=True),
        "criteria_json": json.dumps(
            {
                "market_approved": bool(market_approved),
                "os_week_valid": bool(os_valid),
                "latest_credit_positive": latest_credit is not None and latest_credit > 0,
                "single_account_100_shares": bool(position_ready),
            },
            sort_keys=True,
        ),
        "source_snapshot_json": _source_snapshot(row, position),
        "reason": "; ".join(reasons) if reasons else "all v1 Bull Strangle criteria passed",
    }


def _build_dca_decision(
    batch_id: int,
    market: dict[str, Any],
    row: dict[str, Any],
    position: dict[str, Any] | None,
    positions_available: bool,
) -> dict[str, Any]:
    rules = DEFAULT_RULES["dca"]
    allocation_ok = 1 if (market.get("investment_percent") or 0) > 0 else 0
    os_valid = int(row.get("is_week_valid") or 0)
    price_deviation = row.get("worst_abs_stock_price_deviation_pct")
    trend = _price_trend(row)
    candidate_score = _dca_candidate_score(row, trend)
    account_shares = position.get("max_account_quantity") if position else 0
    consolidated_shares = position.get("total_quantity") if position else 0
    target_account = position.get("dca_target_account") if position else None
    shares_to_100 = position.get("shares_to_100") if position else 100
    bull_ready = bool(position and int(position.get("bull_strangle_ready") or 0))
    reasons = []
    if not allocation_ok:
        reasons.append("market allocation is zero")
    if not os_valid:
        reasons.append("weekly OS data has missing core values")
    if candidate_score < rules["minimum_candidate_score"]:
        reasons.append("candidate score is below threshold")
    if price_deviation is not None and price_deviation > rules["max_price_deviation_pct"]:
        reasons.append("price deviation exceeds threshold")
    if positions_available and not position:
        reasons.append("no current position/account selected for DCA")
    if bull_ready:
        reasons.append("single account already has 100 shares; evaluate as Bull Strangle")

    if allocation_ok and os_valid and not reasons:
        final = "APPROVE"
    elif allocation_ok and candidate_score >= rules["minimum_candidate_score"] and not bull_ready:
        final = "WATCH"
    else:
        final = "SKIP"

    return {
        "decision_batch_id": batch_id,
        "newsletter_id": row["newsletter_id"],
        "newsletter_date": row["newsletter_date"],
        "watchlist_entry_id": row["entry_id"],
        "symbol": row["symbol"],
        "final_decision": final,
        "priority_rank": None,
        "market_allocation_ok": allocation_ok,
        "dca_candidate_score": candidate_score,
        "latest_live_price": row.get("latest_live_stock_price"),
        "weekly_price_trend": trend,
        "max_price_deviation_pct": price_deviation,
        "selected_account": target_account,
        "account_shares": account_shares,
        "consolidated_shares": consolidated_shares,
        "shares_to_100": shares_to_100,
        "rules_applied_json": json.dumps(rules, sort_keys=True),
        "criteria_json": json.dumps(
            {
                "market_allocation_ok": bool(allocation_ok),
                "os_week_valid": bool(os_valid),
                "candidate_score": candidate_score,
                "target_account": target_account,
                "shares_to_100": shares_to_100,
                "single_account_100_shares": bull_ready,
            },
            sort_keys=True,
        ),
        "source_snapshot_json": _source_snapshot(row, position),
        "reason": "; ".join(reasons) if reasons else "all v1 DCA criteria passed",
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


def _source_snapshot(row: dict[str, Any], position: dict[str, Any] | None = None) -> str:
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
    }
    return json.dumps(snapshot, sort_keys=True)


def _dca_candidate_score(row: dict[str, Any], trend: float | None) -> float:
    score = 0.0
    if row.get("is_favorite"):
        score += 2.0
    if row.get("latest_live_stock_price") is not None:
        score += 1.0
    if trend is not None and trend >= 0:
        score += 0.5
    if row.get("worst_abs_stock_price_deviation_pct") is not None:
        score -= min(float(row["worst_abs_stock_price_deviation_pct"]) * 10, 1.0)
    return round(score, 2)


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


def _counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{name} {counts.get(name, 0)}" for name in ["APPROVE", "WATCH", "SKIP"])


def _decision_table(title: str, rows: list[dict[str, Any]], limit: int = 12) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["None.", ""]
    headers = [
        "rank",
        "symbol",
        "decision",
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
