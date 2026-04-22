from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database


CORE_VALUE_COLUMNS = [
    "live_stock_price",
    "sell_call_bid",
    "sell_put_bid",
    "buy_put_ask",
    "total_credit",
]


def aggregate_os_week(
    newsletter_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_database(db_path)
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

        runs = conn.execute(
            """
            SELECT *
            FROM os_evaluation_runs
            WHERE newsletter_id = ?
            ORDER BY trading_date, run_id
            """,
            (newsletter["newsletter_id"],),
        ).fetchall()
        if not runs:
            raise ValueError(f"No OS evaluation runs found for newsletter date: {newsletter_date}")

        symbols = conn.execute(
            """
            SELECT DISTINCT symbol
            FROM os_evaluation_rows
            WHERE newsletter_id = ?
            ORDER BY symbol
            """,
            (newsletter["newsletter_id"],),
        ).fetchall()

        aggregates = []
        for symbol_row in symbols:
            aggregate = _aggregate_symbol(conn, int(newsletter["newsletter_id"]), symbol_row["symbol"])
            _upsert_aggregate(conn, aggregate)
            aggregates.append(aggregate)
        conn.commit()

    valid_count = sum(1 for aggregate in aggregates if aggregate["is_week_valid"])
    invalid_count = len(aggregates) - valid_count
    result = {
        "newsletter_id": int(newsletter["newsletter_id"]),
        "newsletter_date": newsletter["publication_date"],
        "expiration_date": newsletter["target_expiration"],
        "run_count": len(runs),
        "symbol_count": len(aggregates),
        "valid_symbol_count": valid_count,
        "invalid_symbol_count": invalid_count,
        "run_ids": [int(run["run_id"]) for run in runs],
        "top_price_deviations": _top_abs(aggregates, "worst_abs_stock_price_deviation_pct"),
        "top_credit_deviations": _top_abs(aggregates, "worst_abs_total_credit_deviation"),
        "invalid_symbols": [
            {
                "symbol": aggregate["symbol"],
                "missing_core_value_days": aggregate["missing_core_value_days"],
            }
            for aggregate in aggregates
            if not aggregate["is_week_valid"]
        ],
        "aggregates": aggregates,
    }
    result["markdown"] = render_os_week_aggregate_markdown(result)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result["markdown"], encoding="utf-8")
        result["output_path"] = str(out.resolve())
    return result


def render_os_week_aggregate_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Weekly OS Aggregation {result['newsletter_date']}",
        "",
        "## Summary",
        "",
        f"- Newsletter date: {result['newsletter_date']}",
        f"- Expiration date: {result['expiration_date']}",
        f"- OS run count: {result['run_count']}",
        f"- Run ids: {', '.join(str(run_id) for run_id in result['run_ids'])}",
        f"- Symbols: {result['symbol_count']}",
        f"- Valid symbols: {result['valid_symbol_count']}",
        f"- Invalid symbols: {result['invalid_symbol_count']}",
        "",
    ]
    lines.extend(_markdown_table(
        "Invalid Symbols",
        result["invalid_symbols"],
        headers=["symbol", "missing_core_value_days"],
    ))
    lines.extend(_markdown_table(
        "Top Price Deviations",
        result["top_price_deviations"],
        headers=[
            "symbol",
            "worst_abs_stock_price_deviation_pct",
            "latest_total_credit",
            "missing_core_value_days",
        ],
        percent_columns={"worst_abs_stock_price_deviation_pct"},
        currency_columns={"latest_total_credit"},
    ))
    lines.extend(_markdown_table(
        "Top Credit Deviations",
        result["top_credit_deviations"],
        headers=[
            "symbol",
            "worst_abs_total_credit_deviation",
            "latest_total_credit",
            "missing_core_value_days",
        ],
        currency_columns={"worst_abs_total_credit_deviation", "latest_total_credit"},
    ))
    return "\n".join(lines).rstrip() + "\n"


def _aggregate_symbol(conn, newsletter_id: int, symbol: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT r.trading_date, r.run_id, e.*
        FROM os_evaluation_rows e
        JOIN os_evaluation_runs r ON r.run_id = e.run_id
        WHERE e.newsletter_id = ? AND e.symbol = ?
        ORDER BY r.trading_date, r.run_id
        """,
        (newsletter_id, symbol),
    ).fetchall()
    deviations = conn.execute(
        """
        SELECT d.*
        FROM watchlist_deviations d
        WHERE d.newsletter_id = ? AND d.symbol = ?
        """,
        (newsletter_id, symbol),
    ).fetchall()
    first = rows[0]
    latest = rows[-1]
    live_prices = _nonnull([row["live_stock_price"] for row in rows])
    total_credits = _nonnull([row["total_credit"] for row in rows])
    missing_days = sum(
        1 for row in rows if any(row[column] is None for column in CORE_VALUE_COLUMNS)
    )
    worst_price = max(
        [abs(row["stock_price_deviation_pct"]) for row in deviations if row["stock_price_deviation_pct"] is not None],
        default=None,
    )
    worst_credit = max(
        [abs(row["total_credit_deviation"]) for row in deviations if row["total_credit_deviation"] is not None],
        default=None,
    )
    aggregate_json = {
        "run_ids": [int(row["run_id"]) for row in rows],
        "trading_dates": [row["trading_date"] for row in rows],
        "latest_raw_row": json.loads(latest["raw_row_json"]) if latest["raw_row_json"] else {},
    }
    return {
        "newsletter_id": newsletter_id,
        "newsletter_date": latest["newsletter_date"],
        "expiration_date": latest["expiration_date"],
        "symbol": symbol,
        "watchlist_entry_id": latest["watchlist_entry_id"],
        "run_count": len(rows),
        "first_run_id": first["run_id"],
        "latest_run_id": latest["run_id"],
        "first_trading_date": first["trading_date"],
        "latest_trading_date": latest["trading_date"],
        "first_live_stock_price": first["live_stock_price"],
        "latest_live_stock_price": latest["live_stock_price"],
        "min_live_stock_price": min(live_prices) if live_prices else None,
        "max_live_stock_price": max(live_prices) if live_prices else None,
        "latest_live_stock_iv": latest["live_stock_iv"],
        "latest_sell_call_strike": latest["sell_call_strike"],
        "latest_sell_call_bid": latest["sell_call_bid"],
        "latest_sell_put_strike": latest["sell_put_strike"],
        "latest_sell_put_bid": latest["sell_put_bid"],
        "latest_buy_put_strike": latest["buy_put_strike"],
        "latest_buy_put_ask": latest["buy_put_ask"],
        "latest_total_credit": latest["total_credit"],
        "min_total_credit": min(total_credits) if total_credits else None,
        "max_total_credit": max(total_credits) if total_credits else None,
        "worst_abs_stock_price_deviation_pct": worst_price,
        "worst_abs_total_credit_deviation": worst_credit,
        "missing_core_value_days": missing_days,
        "is_week_valid": 1 if missing_days == 0 else 0,
        "aggregate_json": json.dumps(aggregate_json, default=str, sort_keys=True),
    }


def _upsert_aggregate(conn, aggregate: dict[str, Any]) -> None:
    columns = list(aggregate.keys())
    placeholders = ", ".join(["?"] * len(columns))
    update_clause = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column not in {"newsletter_id", "symbol"}
    )
    conn.execute(
        f"""
        INSERT INTO os_weekly_symbol_aggregates
        ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(newsletter_id, symbol) DO UPDATE SET
        {update_clause},
        updated_at = CURRENT_TIMESTAMP
        """,
        tuple(aggregate[column] for column in columns),
    )


def _nonnull(values: list[Any]) -> list[float]:
    return [float(value) for value in values if value is not None]


def _top_abs(
    aggregates: list[dict[str, Any]],
    field_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = [
        {
            "symbol": aggregate["symbol"],
            field_name: aggregate[field_name],
            "latest_total_credit": aggregate["latest_total_credit"],
            "missing_core_value_days": aggregate["missing_core_value_days"],
        }
        for aggregate in aggregates
        if aggregate[field_name] is not None
    ]
    return sorted(rows, key=lambda row: abs(row[field_name]), reverse=True)[:limit]


def _markdown_table(
    title: str,
    rows: list[dict[str, Any]],
    headers: list[str],
    percent_columns: set[str] | None = None,
    currency_columns: set[str] | None = None,
) -> list[str]:
    percent_columns = percent_columns or set()
    currency_columns = currency_columns or set()
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["None.", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _format_markdown_value(row.get(header), header, percent_columns, currency_columns)
                for header in headers
            )
            + " |"
        )
    lines.append("")
    return lines


def _format_markdown_value(
    value: Any,
    header: str,
    percent_columns: set[str],
    currency_columns: set[str],
) -> str:
    if value is None:
        return ""
    if header in percent_columns:
        return f"{float(value) * 100:.2f}%"
    if header in currency_columns:
        numeric = float(value)
        return f"-${abs(numeric):.2f}" if numeric < 0 else f"${numeric:.2f}"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")
