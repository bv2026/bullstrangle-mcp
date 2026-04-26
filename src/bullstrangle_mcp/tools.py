from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database
from .decisions import generate_weekend_decisions, load_decision_rules
from .ingestion import ingest_directory, ingest_newsletter
from .os_ingestion import ingest_os_workbook
from .os_reports import list_os_runs, report_os_run
from .os_weekly import aggregate_os_week
from .os_workbooks import (
    calculate_newsletter_selectors,
    generate_os_workbook,
    prepare_os_workbook_record,
)
from .position_book import (
    backtest_all,
    generate_backtest_report,
    resolve_outcomes,
    seed_from_short_list,
)
from .positions import ingest_positions
from .reports import generate_daily_brief, generate_weekly_action_plan
from .entry_engine import (
    evaluate_entry,
    evaluate_newsletter,
    generate_entry_validation_report,
    validate_all_newsletters,
)
from .exit_engine import (
    evaluate_exit,
    evaluate_exit_batch,
    generate_exit_report,
)
from .rule_catalog import get_rule as _get_rule
from .rule_catalog import list_rule_catalog as _list_rule_catalog
from .rule_catalog import load_rule_catalog


def ingest_newsletter_tool(
    pdf_path: str,
    db_path: str = str(DEFAULT_DB_PATH),
    force: bool = False,
) -> dict[str, Any]:
    """MCP-shaped tool function: ingest a single newsletter PDF."""
    return ingest_newsletter(pdf_path=pdf_path, db_path=db_path, force=force)


def ingest_newsletter_directory_tool(
    directory: str = "data/newsletters",
    db_path: str = str(DEFAULT_DB_PATH),
    force: bool = False,
) -> dict[str, Any]:
    """MCP-shaped tool function: ingest all newsletter PDFs in a directory."""
    results = ingest_directory(directory=directory, db_path=db_path, force=force)
    success_count = sum(1 for row in results if row.get("status") != "error")
    error_count = sum(1 for row in results if row.get("status") == "error")
    return {
        "database_path": str(Path(db_path).resolve()),
        "directory": str(Path(directory).resolve()),
        "ingested_count": success_count,
        "error_count": error_count,
        "results": results,
    }


def list_newsletters_tool(db_path: str = str(DEFAULT_DB_PATH)) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT n.newsletter_id, n.publication_date, n.entry_date, n.target_expiration,
                   n.option_type, COUNT(w.entry_id) AS watchlist_count,
                   me.hybrid_score, me.market_status, me.deployment_approved
            FROM newsletters n
            LEFT JOIN watchlist_entries w ON w.newsletter_id = n.newsletter_id
            LEFT JOIN market_environment me ON me.newsletter_id = n.newsletter_id
            GROUP BY n.newsletter_id
            ORDER BY n.publication_date DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_newsletter_tool(newsletter_id: int, db_path: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        newsletter = conn.execute(
            "SELECT * FROM newsletters WHERE newsletter_id = ?", (newsletter_id,)
        ).fetchone()
        if not newsletter:
            raise ValueError(f"Newsletter not found: {newsletter_id}")
        env = conn.execute(
            "SELECT * FROM market_environment WHERE newsletter_id = ?", (newsletter_id,)
        ).fetchone()
        watchlist = conn.execute(
            "SELECT * FROM watchlist_entries WHERE newsletter_id = ? ORDER BY symbol",
            (newsletter_id,),
        ).fetchall()
        short_list = conn.execute(
            "SELECT * FROM short_list_entries WHERE newsletter_id = ? ORDER BY portfolio_type, rank",
            (newsletter_id,),
        ).fetchall()
        return {
            "newsletter": dict(newsletter),
            "market_environment": dict(env) if env else None,
            "watchlist": [dict(row) for row in watchlist],
            "short_list": [dict(row) for row in short_list],
        }


def get_newsletter_by_date_tool(
    newsletter_date: str, db_path: str = str(DEFAULT_DB_PATH)
) -> dict[str, Any]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT newsletter_id FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
    if not row:
        raise ValueError(f"Newsletter not found for date: {newsletter_date}")
    return get_newsletter_tool(int(row["newsletter_id"]), db_path)


def get_newsletter_by_ref_tool(
    newsletter_ref: str, db_path: str = str(DEFAULT_DB_PATH)
) -> dict[str, Any]:
    """Get a newsletter by numeric id or publication date."""
    if newsletter_ref.isdigit():
        return get_newsletter_tool(int(newsletter_ref), db_path)
    return get_newsletter_by_date_tool(newsletter_ref, db_path)


def get_symbol_history_tool(
    symbol: str,
    db_path: str = str(DEFAULT_DB_PATH),
    newsletter_date: str | None = None,
) -> dict[str, Any]:
    """Return symbol history across newsletters and whether it is new for a given date."""
    initialize_database(db_path)
    normalized_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())
    if not normalized_symbol:
        raise ValueError("Symbol must contain at least one alphanumeric character")

    with connect(db_path) as conn:
        history_rows = conn.execute(
            """
            SELECT h.symbol,
                   h.publication_date,
                   h.on_watchlist,
                   h.on_short_list,
                   n.newsletter_id,
                   n.entry_date,
                   n.target_expiration
            FROM symbol_history h
            JOIN newsletters n ON n.newsletter_id = h.newsletter_id
            WHERE h.symbol = ?
            ORDER BY h.publication_date DESC
            """,
            (normalized_symbol,),
        ).fetchall()

        if not history_rows:
            raise ValueError(f"Symbol not found in history: {normalized_symbol}")

        watchlist_rows = conn.execute(
            """
            SELECT newsletter_date,
                   expiration_date,
                   symbol,
                   description,
                   sector,
                   stock_price,
                   implied_volatility,
                   is_favorite
            FROM watchlist_entries
            WHERE symbol = ?
            ORDER BY newsletter_date DESC
            """,
            (normalized_symbol,),
        ).fetchall()

    occurrences = [dict(row) for row in history_rows]
    watchlist_entries = [dict(row) for row in watchlist_rows]
    first_seen = occurrences[-1]["publication_date"]
    latest_seen = occurrences[0]["publication_date"]
    watchlist_count = sum(1 for row in occurrences if row["on_watchlist"])
    short_list_count = sum(1 for row in occurrences if row["on_short_list"])

    result: dict[str, Any] = {
        "symbol": normalized_symbol,
        "first_seen": first_seen,
        "latest_seen": latest_seen,
        "occurrence_count": len(occurrences),
        "watchlist_count": watchlist_count,
        "short_list_count": short_list_count,
        "occurrences": occurrences,
        "watchlist_entries": watchlist_entries,
    }

    if newsletter_date:
        matched = next((row for row in occurrences if row["publication_date"] == newsletter_date), None)
        prior_count = sum(1 for row in occurrences if row["publication_date"] < newsletter_date)
        result["newsletter_date"] = newsletter_date
        result["present_on_newsletter_date"] = bool(matched)
        result["is_new_for_newsletter_date"] = bool(matched and prior_count == 0)
        result["prior_occurrence_count"] = prior_count
        result["latest_prior_publication_date"] = (
            max((row["publication_date"] for row in occurrences if row["publication_date"] < newsletter_date), default=None)
        )

    return result


def calculate_os_selectors_tool(
    newsletter_date: str, db_path: str = str(DEFAULT_DB_PATH)
) -> dict[str, Any]:
    """Calculate rounded OS selector values from one newsletter baseline."""
    return calculate_newsletter_selectors(newsletter_date, db_path).as_dict()


def prepare_os_workbook_tool(
    newsletter_date: str, db_path: str = str(DEFAULT_DB_PATH)
) -> dict[str, Any]:
    """Create or update the OS workbook metadata row for one newsletter."""
    initialize_database(db_path)
    return prepare_os_workbook_record(newsletter_date, db_path)


def generate_os_workbook_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    output_dir: str = "outputs/workbooks",
) -> dict[str, Any]:
    """Generate an Option Samurai-enabled Excel workbook from a newsletter watchlist.

    After generation the workbook is automatically copied into the os_uploads
    directory (sibling of the data directory) so it is ready for the operator
    to open in Excel, refresh Option Samurai formulas, and save.
    """
    initialize_database(db_path)
    result = generate_os_workbook(newsletter_date, db_path, output_dir)

    # Auto-copy to os_uploads so the operator can open and refresh immediately.
    generated_path = result.get("generated_path")
    if generated_path:
        uploads_dir = Path(db_path).parent / "os_uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = uploads_dir / Path(generated_path).name
        try:
            shutil.copy2(generated_path, dest)
            result["uploaded_path"] = str(dest)
            result["upload_status"] = "copied"
        except OSError as exc:
            result["uploaded_path"] = None
            result["upload_status"] = f"copy_failed: {exc}"

    return result


def ingest_os_workbook_tool(
    workbook_path: str,
    db_path: str = str(DEFAULT_DB_PATH),
    trading_date: str | None = None,
) -> dict[str, Any]:
    """Ingest a refreshed Option Samurai workbook into daily OS snapshot tables."""
    initialize_database(db_path)
    return ingest_os_workbook(workbook_path, db_path, trading_date)


def report_os_run_tool(
    run_id: int,
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
) -> dict[str, Any]:
    """Create a daily OS ingestion audit/deviation report for one run."""
    initialize_database(db_path)
    return report_os_run(run_id, db_path, output_path)


def list_os_runs_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    newsletter_date: str | None = None,
) -> list[dict[str, Any]]:
    """List OS evaluation runs with their run_id, trading date, row count, and status.

    Pass newsletter_date to filter to one week; omit it to return all runs ordered
    by newsletter_date DESC then trading_date ASC.
    """
    initialize_database(db_path)
    return list_os_runs(db_path, newsletter_date)


def aggregate_os_week_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
) -> dict[str, Any]:
    """Aggregate all daily OS runs for one newsletter week."""
    initialize_database(db_path)
    return aggregate_os_week(newsletter_date, db_path, output_path)


def generate_weekend_decisions_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    decision_date: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate weekend Bull Strangle and DCA decisions for one newsletter week."""
    initialize_database(db_path)
    return generate_weekend_decisions(newsletter_date, db_path, decision_date, output_path)


def ingest_positions_tool(
    csv_path: str,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Ingest account-level positions and symbol rollups from a CSV export."""
    initialize_database(db_path)
    return ingest_positions(csv_path, db_path)


# ── Phase B: Report generation tools ─────────────────────────────────────────


def generate_weekly_action_plan_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate the Sunday Bull Strangle weekly action plan report."""
    initialize_database(db_path)
    return generate_weekly_action_plan(newsletter_date, db_path, output_path)


def generate_daily_brief_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate the morning daily monitoring brief."""
    initialize_database(db_path)
    return generate_daily_brief(db_path, output_path)


def list_generated_reports_tool(
    report_type: str | None = None,
    limit: int = 20,
    db_path: str = str(DEFAULT_DB_PATH),
) -> list[dict[str, Any]]:
    """List previously generated reports, newest first."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        if report_type:
            rows = conn.execute(
                """
                SELECT report_id, report_type, newsletter_id, report_date,
                       output_filepath, generation_timestamp
                FROM generated_reports
                WHERE report_type = ?
                ORDER BY generation_timestamp DESC
                LIMIT ?
                """,
                (report_type, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT report_id, report_type, newsletter_id, report_date,
                       output_filepath, generation_timestamp
                FROM generated_reports
                ORDER BY generation_timestamp DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    return [dict(r) for r in rows]


def get_generated_report_tool(
    report_id: int,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Return the full content of a generated report by report_id."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM generated_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    if not row:
        raise ValueError(f"Report not found: {report_id}")
    return dict(row)


# ── Phase A: Quick-win query tools ───────────────────────────────────────────


def get_current_environment_tool(db_path: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    """Return the latest market environment row with deployment status and criteria breakdown."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        env = conn.execute(
            """
            SELECT me.*, n.publication_date, n.target_expiration, n.option_type,
                   wd.action_taken, wd.deployment_approved AS wd_deployment_approved,
                   wd.consecutive_weeks_met AS wd_consecutive_weeks,
                   wd.decision_rationale
            FROM market_environment me
            JOIN newsletters n ON n.newsletter_id = me.newsletter_id
            LEFT JOIN weekly_decisions wd ON wd.newsletter_id = me.newsletter_id
            ORDER BY me.publication_date DESC
            LIMIT 1
            """
        ).fetchone()
    if not env:
        return {"error": "No market environment data found"}
    result = dict(env)
    # Parse rationale JSON for clean embedding
    raw_rationale = result.pop("decision_rationale", None)
    try:
        result["decision_rationale"] = json.loads(raw_rationale) if raw_rationale else None
    except (ValueError, TypeError):
        result["decision_rationale"] = raw_rationale
    return result


def check_deployment_approval_tool(db_path: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    """Return full deployment approval status with per-criterion breakdown and recommended action."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        env = conn.execute(
            """
            SELECT me.*, wd.action_taken, wd.consecutive_weeks_met AS wd_consecutive_weeks,
                   wd.decision_rationale
            FROM market_environment me
            LEFT JOIN weekly_decisions wd ON wd.newsletter_id = me.newsletter_id
            ORDER BY me.publication_date DESC
            LIMIT 1
            """
        ).fetchone()
    if not env:
        return {"error": "No market environment data found"}
    e = dict(env)
    consecutive = e.get("consecutive_weeks_met") or e.get("wd_consecutive_weeks") or 0
    approved = bool(e.get("deployment_approved"))
    criteria = {
        "hybrid_bullish": {
            "passed": bool(e.get("hybrid_bullish")),
            "value": e.get("hybrid_score"),
            "threshold": ">= 0",
        },
        "sp500_above_200dma": {
            "passed": bool(e.get("sp500_above_200dma")),
            "sp500": e.get("sp500_price"),
            "dma_200": e.get("sp500_200dma"),
        },
        "vix_below_25": {
            "passed": bool(e.get("vix_below_25")),
            "value": e.get("vix"),
            "threshold": "< 25",
        },
        "breadth_above_40": {
            "passed": bool(e.get("breadth_above_40")),
            "value": e.get("breadth_pct"),
            "threshold": "> 40%",
        },
    }
    all_met = all(c["passed"] for c in criteria.values())
    return {
        "publication_date": e.get("publication_date"),
        "approved": approved,
        "all_criteria_met": all_met,
        "consecutive_weeks_met": consecutive,
        "weeks_needed": 2,
        "action_taken": e.get("action_taken"),
        "market_status": e.get("market_status"),
        "hybrid_score": e.get("hybrid_score"),
        "investment_percent": e.get("investment_percent"),
        "scaling_phase": e.get("scaling_phase"),
        "recommended_position_count": e.get("recommended_position_count"),
        "criteria": criteria,
        "reason": (
            "Two-week confirmation met — deployment approved"
            if approved
            else (
                f"Week {consecutive} of 2 — need consecutive week confirmation"
                if all_met
                else "One or more market criteria not met"
            )
        ),
    }


def get_watchlist_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Return the full watchlist for a newsletter date, with deep analysis for WL Favorites."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        nrow = conn.execute(
            "SELECT newsletter_id, publication_date, target_expiration, option_type "
            "FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
        if not nrow:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")
        watchlist = conn.execute(
            """
            SELECT we.*,
                   da.analysis_data, da.favorite_rank, da.has_proposed_trade
            FROM watchlist_entries we
            LEFT JOIN watchlist_deep_analysis da
              ON da.newsletter_id = we.newsletter_id AND da.symbol = we.symbol
            WHERE we.newsletter_id = ?
            ORDER BY we.is_favorite DESC, we.symbol
            """,
            (int(nrow["newsletter_id"]),),
        ).fetchall()
    rows = []
    for row in watchlist:
        d = dict(row)
        raw = d.pop("analysis_data", None)
        try:
            d["deep_analysis"] = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            d["deep_analysis"] = raw
        rows.append(d)
    return {
        "newsletter_date": nrow["publication_date"],
        "target_expiration": nrow["target_expiration"],
        "option_type": nrow["option_type"],
        "watchlist_count": len(rows),
        "watchlist": rows,
    }


def get_dca_candidates_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Return the short-list (DCA candidate) entries for a newsletter date."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        nrow = conn.execute(
            "SELECT newsletter_id, publication_date FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
        if not nrow:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")
        rows = conn.execute(
            """
            SELECT sl.*, we.stock_price, we.implied_volatility, we.sector,
                   we.description, we.is_favorite
            FROM short_list_entries sl
            LEFT JOIN watchlist_entries we
              ON we.newsletter_id = sl.newsletter_id AND we.symbol = sl.symbol
            WHERE sl.newsletter_id = ?
            ORDER BY sl.portfolio_type, sl.rank
            """,
            (int(nrow["newsletter_id"]),),
        ).fetchall()
    return {
        "newsletter_date": nrow["publication_date"],
        "count": len(rows),
        "candidates": [dict(r) for r in rows],
    }


def get_active_cycles_tool(db_path: str = str(DEFAULT_DB_PATH)) -> list[dict[str, Any]]:
    """Return all newsletters whose target_expiration is in the future (active position books)."""
    initialize_database(db_path)
    today = date.today().isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT n.newsletter_id, n.publication_date, n.entry_date,
                   n.target_expiration, n.option_type,
                   COUNT(we.entry_id) AS watchlist_count,
                   me.hybrid_score, me.market_status, me.deployment_approved,
                   me.scaling_phase, me.recommended_position_count,
                   julianday(n.target_expiration) - julianday(?) AS days_until_expiration
            FROM newsletters n
            LEFT JOIN watchlist_entries we ON we.newsletter_id = n.newsletter_id
            LEFT JOIN market_environment me ON me.newsletter_id = n.newsletter_id
            WHERE n.target_expiration >= ?
            GROUP BY n.newsletter_id
            ORDER BY n.target_expiration ASC
            """,
            (today, today),
        ).fetchall()
    return [dict(r) for r in rows]


def get_eligible_symbols_tool(
    newsletter_date: str,
    decision: str = "APPROVE",
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Return bull strangle decision rows filtered by final_decision (APPROVE/WATCH/SKIP)."""
    initialize_database(db_path)
    decision = decision.upper()
    if decision not in {"APPROVE", "WATCH", "SKIP"}:
        raise ValueError("decision must be one of: APPROVE, WATCH, SKIP")
    with connect(db_path) as conn:
        nrow = conn.execute(
            "SELECT newsletter_id, publication_date, target_expiration "
            "FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
        if not nrow:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")
        batch = conn.execute(
            """
            SELECT decision_batch_id, decision_date, status
            FROM decision_batches
            WHERE newsletter_id = ?
            ORDER BY decision_date DESC
            LIMIT 1
            """,
            (int(nrow["newsletter_id"]),),
        ).fetchone()
        if not batch:
            return {
                "newsletter_date": nrow["publication_date"],
                "target_expiration": nrow["target_expiration"],
                "decision_batch_id": None,
                "decision_date": None,
                "filter": decision,
                "count": 0,
                "symbols": [],
                "warning": "No decision batch found — run generate_weekend_decisions first",
            }
        rows = conn.execute(
            """
            SELECT bsd.symbol, bsd.final_decision, bsd.selected_action, bsd.priority_rank,
                   bsd.strategy_score, bsd.strategy_band, bsd.latest_total_credit,
                   bsd.latest_live_stock_price, bsd.max_price_deviation_pct,
                   bsd.selected_account, bsd.account_shares, bsd.shares_to_100,
                   bsd.reason, we.sector, we.is_favorite
            FROM bull_strangle_decisions bsd
            LEFT JOIN watchlist_entries we
              ON we.newsletter_id = bsd.newsletter_id AND we.symbol = bsd.symbol
            WHERE bsd.decision_batch_id = ? AND bsd.final_decision = ?
            ORDER BY bsd.priority_rank
            """,
            (int(batch["decision_batch_id"]), decision),
        ).fetchall()
    return {
        "newsletter_date": nrow["publication_date"],
        "target_expiration": nrow["target_expiration"],
        "decision_batch_id": batch["decision_batch_id"],
        "decision_date": batch["decision_date"],
        "filter": decision,
        "count": len(rows),
        "symbols": [dict(r) for r in rows],
    }


def get_deep_analysis_tool(
    newsletter_date: str,
    symbol: str | None = None,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Return Darren's deep-dive WL Favorites analysis for a newsletter date."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        nrow = conn.execute(
            "SELECT newsletter_id, publication_date FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
        if not nrow:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")
        if symbol:
            rows = conn.execute(
                "SELECT * FROM watchlist_deep_analysis WHERE newsletter_id = ? AND symbol = ?",
                (int(nrow["newsletter_id"]), symbol.upper()),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM watchlist_deep_analysis WHERE newsletter_id = ? "
                "ORDER BY favorite_rank",
                (int(nrow["newsletter_id"]),),
            ).fetchall()
    result = {}
    for row in rows:
        d = dict(row)
        sym = d.pop("symbol")
        raw = d.pop("analysis_data", None)
        try:
            d["analysis_data"] = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            d["analysis_data"] = raw
        result[sym] = d
    return {
        "newsletter_date": nrow["publication_date"],
        "count": len(result),
        "analysis": result,
    }


def get_market_environment_history_tool(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 12,
    db_path: str = str(DEFAULT_DB_PATH),
) -> list[dict[str, Any]]:
    """Return market environment rows in date range, newest first."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        query = "SELECT me.*, wd.action_taken, wd.consecutive_weeks_met AS wd_consecutive FROM market_environment me LEFT JOIN weekly_decisions wd ON wd.newsletter_id = me.newsletter_id WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND me.publication_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND me.publication_date <= ?"
            params.append(end_date)
        query += " ORDER BY me.publication_date DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_scaling_guidance_tool(db_path: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    """Return scaling guidance from the latest market environment."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        env = conn.execute(
            """
            SELECT me.publication_date, me.market_status, me.hybrid_score,
                   me.investment_percent, me.scaling_phase, me.recommended_position_count,
                   me.deployment_approved, me.consecutive_weeks_met,
                   wd.action_taken
            FROM market_environment me
            LEFT JOIN weekly_decisions wd ON wd.newsletter_id = me.newsletter_id
            ORDER BY me.publication_date DESC LIMIT 1
            """
        ).fetchone()
    if not env:
        return {"error": "No market environment data found"}
    e = dict(env)
    phase = e.get("scaling_phase") or "pause"
    phase_descriptions = {
        "normal": "Full deployment — all criteria met for 2+ consecutive weeks",
        "rebuild_week1": "Week 1 of recovery — 1 position only, await Week 2 confirmation",
        "rebuild_week2": "Week 2 of recovery — 1–2 positions, confirm again next week",
        "pause": "Paused — one or more market criteria not met",
    }
    return {
        "publication_date": e.get("publication_date"),
        "market_status": e.get("market_status"),
        "hybrid_score": e.get("hybrid_score"),
        "investment_percent": e.get("investment_percent"),
        "deployment_approved": bool(e.get("deployment_approved")),
        "consecutive_weeks_met": e.get("consecutive_weeks_met"),
        "scaling_phase": phase,
        "scaling_phase_description": phase_descriptions.get(phase, phase),
        "recommended_position_count": e.get("recommended_position_count"),
        "action_taken": e.get("action_taken"),
    }


def search_commentary_tool(
    query: str,
    limit: int = 10,
    db_path: str = str(DEFAULT_DB_PATH),
) -> list[dict[str, Any]]:
    """Full-text search across all ingested newsletter commentary sections."""
    initialize_database(db_path)
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ft.newsletter_id, ft.newsletter_date, ft.section_name,
                   ft.page_start, ft.page_end,
                   snippet(newsletter_search, 1, '**', '**', '...', 30) AS snippet
            FROM newsletter_search ns
            JOIN newsletter_full_text ft ON ft.text_id = ns.rowid
            WHERE newsletter_search MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Phase A: list_strategy_rules (existing) ───────────────────────────────────


def list_strategy_rules_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Return strategy rules stored in the database.

    When *category* is provided only rules with a matching rule_category are
    returned.  Omit it to return all active rules.  Decision-threshold rules
    (rule_category='decision_threshold') carry the numeric gates currently in
    use by the decision engine; editing their rule_parameters value and
    re-running weekend decisions will apply the new thresholds without any
    code change.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        if category:
            rows = conn.execute(
                """
                SELECT rule_id, rule_category, rule_name, rule_description,
                       rule_parameters, source_section, is_active, created_date
                FROM   strategy_rules
                WHERE  rule_category = ?
                ORDER  BY rule_category, rule_name
                """,
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT rule_id, rule_category, rule_name, rule_description,
                       rule_parameters, source_section, is_active, created_date
                FROM   strategy_rules
                ORDER  BY rule_category, rule_name
                """
            ).fetchall()

        loaded = load_decision_rules(conn)

    result = []
    for row in rows:
        entry = dict(row)
        # Annotate decision_threshold rows with the resolved live value
        if entry["rule_category"] == "decision_threshold":
            name: str = entry["rule_name"]
            resolved: float | None = None
            if name.startswith("bull_strangle_"):
                key = name[len("bull_strangle_"):]
                resolved = loaded["bull_strangle"].get(key)
            elif name.startswith("dca_"):
                key = name[len("dca_"):]
                resolved = loaded["dca"].get(key)
            entry["resolved_value"] = resolved
        result.append(entry)

    return result


def seed_cycle_layers_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    portfolio_type: str = "small",
) -> dict[str, Any]:
    """Seed cycle_layers from Darren's Short List for one newsletter week.

    Only seeds when deployment was approved for that week.  Safe to call twice —
    already-existing layers are left untouched.  Symbols with no watchlist entry
    (no strikes/premiums available) are skipped and listed in ``skipped``.
    """
    return seed_from_short_list(newsletter_date, db_path, portfolio_type)


def resolve_cycle_outcomes_tool(
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Fetch yfinance closing prices at expiration and compute P&L for seeded layers.

    Determines BOTH_OTM / CALL_ASSIGNED / PUT_ASSIGNED for each symbol, writes
    P&L to cycle_layers, and records the exit_decision.  Layers whose expiration
    is in the future are returned as ``pending`` and left unchanged.
    """
    return resolve_outcomes(newsletter_date, db_path)


def backtest_all_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    portfolio_type: str = "small",
) -> dict[str, Any]:
    """Seed and resolve all approved newsletters in one call.

    Equivalent to running seed_cycle_layers + resolve_cycle_outcomes for every
    approved newsletter week.  Safe to call multiple times — idempotent.
    """
    return backtest_all(db_path, portfolio_type)


def generate_backtest_report_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    portfolio_type: str = "small",
    output: str | None = None,
) -> dict[str, Any]:
    """Generate a week-by-week markdown backtest report from closed cycle layers.

    Shows entry price, strikes, expiration close, outcome, P&L per symbol,
    and summary stats (win rate, total P&L, best/worst trade).
    Optionally write the report to *output* path.
    """
    md = generate_backtest_report(db_path, portfolio_type)
    result: dict[str, Any] = {"markdown": md, "portfolio_type": portfolio_type}
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        result["output_path"] = str(out.resolve())
    return result


def list_rule_catalog_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    rule_area: str | None = None,
    rule_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return strategy rules from the v3 rule catalog.

    Auto-seeds the catalog on first call (INSERT OR IGNORE — safe to repeat).

    *rule_area* filters by area: stock_selection, earnings, strike_selection,
    capital, cycle, exit, market_environment, formula.

    *rule_type* filters by type: hard_gate, soft_gate, hard_rule, guideline,
    optional_overlay, formula.

    Omit both to return all 43 rules.  Each row includes parsed ``parameters``
    (dict) in addition to the raw ``parameters_json`` string so callers can
    read numeric thresholds directly.
    """
    return _list_rule_catalog(db_path, rule_area=rule_area, rule_type=rule_type)


# ── Phase 3: Entry Engine tools ───────────────────────────────────────────────


def evaluate_entry_tool(
    symbol: str,
    newsletter_date: str,
    db_path: str = str(DEFAULT_DB_PATH),
    entry_date: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate Gates 1–9 for one symbol against one newsletter week.

    Returns the full gate result set, decision_type (BULL_STRANGLE/WATCH/SKIP),
    first_failing_gate, and Short List membership.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT newsletter_id FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
    if not row:
        raise ValueError(f"Newsletter not found for date: {newsletter_date}")
    decision = evaluate_entry(symbol, int(row["newsletter_id"]), db_path, entry_date, persist)
    if decision is None:
        raise ValueError(f"evaluate_entry returned None for {symbol} / {newsletter_date}")
    return decision.to_dict()


def evaluate_newsletter_tool(
    newsletter_ref: str,
    db_path: str = str(DEFAULT_DB_PATH),
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate Gates 1–9 for every watchlist symbol in one newsletter week.

    newsletter_ref can be a publication date (2026-04-17) or a numeric newsletter_id.
    Returns decisions list and validation alignment summary.
    """
    initialize_database(db_path)
    return evaluate_newsletter(newsletter_ref, db_path, persist)


def validate_all_newsletters_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    persist: bool = True,
) -> dict[str, Any]:
    """Run gate evaluation across all newsletters and aggregate validation stats.

    Answers: does the entry engine consistently predict the Short List selections?
    Returns overall alignment stats and per-week summaries.
    """
    initialize_database(db_path)
    return validate_all_newsletters(db_path, persist)


def generate_entry_validation_report_tool(
    newsletter_ref: str,
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a markdown gate validation report for one newsletter week.

    Shows per-symbol gate results and how they align with the Short List selections.
    Optionally writes to output_path.  Returns ``markdown`` key with the full report.
    """
    initialize_database(db_path)
    md = generate_entry_validation_report(newsletter_ref, db_path, output_path)
    result: dict[str, Any] = {"markdown": md, "newsletter_ref": newsletter_ref}
    if output_path:
        result["output_path"] = str(Path(output_path).resolve())
    return result


# ── Phase 4: Exit Engine tools ────────────────────────────────────────────────


def evaluate_exit_tool(
    layer_id: int,
    db_path: str = str(DEFAULT_DB_PATH),
    include_live_price: bool = True,
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate exit triggers for one ACTIVE cycle_layer.

    Returns all trigger results and the recommended action
    (HOLD / REVIEW / EXIT_MONDAY / CLOSE_IMMEDIATELY / NEEDS_RESOLUTION).
    """
    initialize_database(db_path)
    decision = evaluate_exit(layer_id, db_path, include_live_price=include_live_price, persist=persist)
    if decision is None:
        raise ValueError(f"Layer {layer_id} not found or is not ACTIVE")
    return decision.to_dict()


def evaluate_exit_batch_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    include_live_price: bool = True,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate exit triggers for ALL ACTIVE cycle_layers.

    Returns a list of exit decisions sorted by expiration date then symbol.
    """
    initialize_database(db_path)
    decisions = evaluate_exit_batch(db_path, include_live_price=include_live_price, persist=persist)
    return [d.to_dict() for d in decisions]


def generate_exit_report_tool(
    db_path: str = str(DEFAULT_DB_PATH),
    output_path: str | None = None,
    include_live_price: bool = True,
) -> dict[str, Any]:
    """Generate a markdown exit monitoring report for all ACTIVE positions.

    Groups positions by urgency (IMMEDIATE / THIS_WEEK / ROUTINE) and includes
    live price, % change from entry, strike proximity, and triggered rule citations.
    """
    initialize_database(db_path)
    md = generate_exit_report(db_path, output_path, include_live_price)
    result: dict[str, Any] = {"markdown": md}
    if output_path:
        result["output_path"] = str(Path(output_path).resolve())
    return result


def list_exit_decisions_tool(
    db_path: str = str(DEFAULT_DB_PATH),
) -> list[dict[str, Any]]:
    """Return all persisted exit_decisions rows, ordered by evaluation date descending."""
    initialize_database(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ed.*, cl.symbol, cl.expiration_date, cl.account_id,
                   n.publication_date
            FROM exit_decisions ed
            JOIN cycle_layers cl ON cl.layer_id = ed.layer_id
            JOIN newsletters n ON n.newsletter_id = cl.newsletter_id
            ORDER BY ed.evaluation_date DESC, cl.symbol
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_entry_decisions_tool(
    newsletter_date: str | None = None,
    db_path: str = str(DEFAULT_DB_PATH),
    decision_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return entry_decisions rows, newest first.

    Pass newsletter_date to filter to one week.
    Pass decision_type (BULL_STRANGLE / WATCH / SKIP) to filter by decision.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        query = """
            SELECT ed.*, n.publication_date
            FROM entry_decisions ed
            JOIN newsletters n ON n.newsletter_id = ed.newsletter_id
            WHERE 1=1
        """
        params: list[Any] = []
        if newsletter_date:
            query += " AND n.publication_date = ?"
            params.append(newsletter_date)
        if decision_type:
            query += " AND ed.decision_type = ?"
            params.append(decision_type.upper())
        query += " ORDER BY n.publication_date DESC, ed.symbol"
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_rule_tool(
    rule_id: str,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, Any]:
    """Fetch a single strategy rule by its rule_id.

    Raises ``ValueError`` if the rule is not found.  Call
    ``list_rule_catalog`` to discover available rule_ids (e.g. GATE-SS-001,
    RULE-EARN-003, FORMULA-002).
    """
    try:
        rule = _get_rule(db_path, rule_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "rule_id": rule.rule_id,
        "rule_area": rule.rule_area,
        "rule_type": rule.rule_type,
        "source_section": rule.source_section,
        "description": rule.description,
        "parameters": rule.parameters,
        "parameters_json": rule.parameters_json,
        "data_column_mapping": rule.data_column_mapping,
        "is_active": rule.is_active,
    }
