from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database


DEFAULT_PRICE_DEVIATION_ALERT_PCT = 0.03
DEFAULT_CREDIT_DEVIATION_ALERT = 0.50


def report_os_run(
    run_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        run = conn.execute(
            "SELECT * FROM os_evaluation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not run:
            raise ValueError(f"OS evaluation run not found: {run_id}")

        row_count = conn.execute(
            "SELECT COUNT(*) AS count FROM os_evaluation_rows WHERE run_id = ?",
            (run_id,),
        ).fetchone()["count"]
        deviation_count = conn.execute(
            "SELECT COUNT(*) AS count FROM watchlist_deviations WHERE run_id = ?",
            (run_id,),
        ).fetchone()["count"]
        missing_rows = _fetch_missing_rows(conn, run_id)
        largest_price_deviations = _fetch_largest_price_deviations(conn, run_id)
        largest_credit_deviations = _fetch_largest_credit_deviations(conn, run_id)
        strike_changes = _fetch_strike_changes(conn, run_id)
        quality_flags = _build_quality_flags(
            run=dict(run),
            missing_rows=missing_rows,
            largest_price_deviations=largest_price_deviations,
            largest_credit_deviations=largest_credit_deviations,
        )

    report = {
        "run": _json_row(run),
        "counts": {
            "evaluation_rows": row_count,
            "deviation_rows": deviation_count,
            "missing_or_error_rows": len(missing_rows),
        },
        "quality_flags": quality_flags,
        "missing_or_error_rows": missing_rows,
        "largest_price_deviations": largest_price_deviations,
        "largest_credit_deviations": largest_credit_deviations,
        "strike_changes": strike_changes,
    }
    report["markdown"] = render_os_run_report_markdown(report)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report["markdown"], encoding="utf-8")
        report["output_path"] = str(out.resolve())

    return report


def list_os_runs(
    db_path: str | Path = DEFAULT_DB_PATH,
    newsletter_date: str | None = None,
) -> list[dict[str, Any]]:
    """Return OS evaluation runs, optionally filtered to one newsletter date.

    Each entry includes the run_id needed for report_os_run.  Ordered by
    newsletter_date DESC then trading_date ASC so the most recent newsletter
    appears first and its daily runs are in chronological order.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        if newsletter_date:
            rows = conn.execute(
                """
                SELECT run_id, newsletter_date, expiration_date, trading_date,
                       row_count, populated_live_value_count, formula_cell_count,
                       status, uploaded_at
                FROM   os_evaluation_runs
                WHERE  newsletter_date = ?
                ORDER  BY trading_date ASC, run_id ASC
                """,
                (newsletter_date,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT run_id, newsletter_date, expiration_date, trading_date,
                       row_count, populated_live_value_count, formula_cell_count,
                       status, uploaded_at
                FROM   os_evaluation_runs
                ORDER  BY newsletter_date DESC, trading_date ASC, run_id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]


def render_os_run_report_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    lines = [
        f"# OS Run Report {run['run_id']}",
        "",
        "## Summary",
        "",
        f"- Newsletter date: {run['newsletter_date']}",
        f"- Trading date: {run['trading_date']}",
        f"- Expiration date: {run['expiration_date']}",
        f"- Status: {run['status']}",
        f"- Evaluation rows: {report['counts']['evaluation_rows']}",
        f"- Deviation rows: {report['counts']['deviation_rows']}",
        f"- Populated live values: {run['populated_live_value_count']}",
        f"- Formula cells: {run['formula_cell_count']}",
        f"- Missing/error rows: {report['counts']['missing_or_error_rows']}",
        "",
    ]
    lines.extend(_markdown_section("Quality Flags", report["quality_flags"]))
    lines.extend(_markdown_table("Missing Or Error Rows", report["missing_or_error_rows"]))
    lines.extend(_markdown_table("Largest Price Deviations", report["largest_price_deviations"]))
    lines.extend(_markdown_table("Largest Credit Deviations", report["largest_credit_deviations"]))
    lines.extend(_markdown_table("Strike Changes", report["strike_changes"]))
    return "\n".join(lines).rstrip() + "\n"


def _fetch_missing_rows(conn, run_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol, live_stock_price, live_stock_iv, sell_call_bid, sell_put_bid,
               buy_put_ask, total_credit, bull_strangle_return_pct
        FROM os_evaluation_rows
        WHERE run_id = ?
          AND (
            live_stock_price IS NULL
            OR live_stock_iv IS NULL
            OR sell_call_bid IS NULL
            OR sell_put_bid IS NULL
            OR buy_put_ask IS NULL
            OR total_credit IS NULL
            OR bull_strangle_return_pct IS NULL
          )
        ORDER BY symbol
        """,
        (run_id,),
    ).fetchall()
    return [_json_row(row) for row in rows]


def _fetch_largest_price_deviations(conn, run_id: int, limit: int = 10) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol,
               ROUND(stock_price_deviation, 2) AS stock_price_deviation,
               ROUND(stock_price_deviation_pct * 100, 2) AS stock_price_deviation_pct,
               ROUND(iv_deviation, 4) AS iv_deviation,
               ROUND(total_credit_deviation, 2) AS total_credit_deviation
        FROM watchlist_deviations
        WHERE run_id = ?
          AND stock_price_deviation_pct IS NOT NULL
        ORDER BY ABS(stock_price_deviation_pct) DESC
        LIMIT ?
        """,
        (run_id, limit),
    ).fetchall()
    return [_json_row(row) for row in rows]


def _fetch_largest_credit_deviations(conn, run_id: int, limit: int = 10) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol,
               ROUND(total_credit_deviation, 2) AS total_credit_deviation,
               ROUND(stock_price_deviation_pct * 100, 2) AS stock_price_deviation_pct,
               sell_call_strike_deviation,
               sell_put_strike_deviation,
               buy_put_strike_deviation
        FROM watchlist_deviations
        WHERE run_id = ?
          AND total_credit_deviation IS NOT NULL
        ORDER BY ABS(total_credit_deviation) DESC
        LIMIT ?
        """,
        (run_id, limit),
    ).fetchall()
    return [_json_row(row) for row in rows]


def _fetch_strike_changes(conn, run_id: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol,
               sell_call_strike_deviation,
               sell_put_strike_deviation,
               buy_put_strike_deviation
        FROM watchlist_deviations
        WHERE run_id = ?
          AND (
            COALESCE(sell_call_strike_deviation, 0) != 0
            OR COALESCE(sell_put_strike_deviation, 0) != 0
            OR COALESCE(buy_put_strike_deviation, 0) != 0
          )
        ORDER BY symbol
        LIMIT ?
        """,
        (run_id, limit),
    ).fetchall()
    return [_json_row(row) for row in rows]


def _build_quality_flags(
    run: dict[str, Any],
    missing_rows: list[dict[str, Any]],
    largest_price_deviations: list[dict[str, Any]],
    largest_credit_deviations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    flags = []
    if missing_rows:
        flags.append(
            {
                "severity": "warning",
                "flag": "missing_or_error_values",
                "detail": f"{len(missing_rows)} symbols have missing/error-derived core OS values.",
            }
        )
    if not run.get("populated_live_value_count"):
        flags.append(
            {
                "severity": "error",
                "flag": "no_cached_live_values",
                "detail": "Workbook formulas appear not to have saved cached live values.",
            }
        )
    price_alerts = [
        row for row in largest_price_deviations
        if abs(float(row["stock_price_deviation_pct"] or 0)) >= DEFAULT_PRICE_DEVIATION_ALERT_PCT * 100
    ]
    if price_alerts:
        flags.append(
            {
                "severity": "info",
                "flag": "large_price_deviations",
                "detail": f"{len(price_alerts)} symbols moved at least {DEFAULT_PRICE_DEVIATION_ALERT_PCT:.0%} from newsletter baseline.",
            }
        )
    credit_alerts = [
        row for row in largest_credit_deviations
        if abs(float(row["total_credit_deviation"] or 0)) >= DEFAULT_CREDIT_DEVIATION_ALERT
    ]
    if credit_alerts:
        flags.append(
            {
                "severity": "info",
                "flag": "large_credit_deviations",
                "detail": f"{len(credit_alerts)} symbols changed total credit by at least ${DEFAULT_CREDIT_DEVIATION_ALERT:.2f}.",
            }
        )
    if not flags:
        flags.append(
            {
                "severity": "ok",
                "flag": "no_quality_flags",
                "detail": "No missing core values or threshold deviations found.",
            }
        )
    return flags


def _markdown_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    for row in rows:
        lines.append(f"- {row}")
    lines.append("")
    return lines


def _markdown_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["None.", ""]
    headers = list(rows[0].keys())
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_format_markdown_value(row.get(header)) for header in headers) + " |")
    lines.append("")
    return lines


def _format_markdown_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def _json_row(row) -> dict[str, Any]:
    result = dict(row)
    if "validation_json" in result and isinstance(result["validation_json"], str):
        try:
            result["validation_json"] = json.loads(result["validation_json"])
        except json.JSONDecodeError:
            pass
    return result
