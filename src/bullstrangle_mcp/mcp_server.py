from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .database import DEFAULT_DB_PATH
from .tools import (
    aggregate_os_week_tool,
    calculate_os_selectors_tool,
    check_deployment_approval_tool,
    generate_daily_brief_tool,
    generate_os_workbook_tool,
    generate_weekly_action_plan_tool,
    generate_weekend_decisions_tool,
    get_active_cycles_tool,
    get_current_environment_tool,
    get_dca_candidates_tool,
    get_deep_analysis_tool,
    get_eligible_symbols_tool,
    get_generated_report_tool,
    get_market_environment_history_tool,
    get_newsletter_by_date_tool,
    get_newsletter_tool,
    get_scaling_guidance_tool,
    get_symbol_history_tool,
    get_watchlist_tool,
    ingest_os_workbook_tool,
    ingest_newsletter_directory_tool,
    ingest_newsletter_tool,
    ingest_positions_tool,
    list_generated_reports_tool,
    list_newsletters_tool,
    list_os_runs_tool,
    list_strategy_rules_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
    search_commentary_tool,
)


SERVER_NAME = "bullstrangle-mcp"


# ── Path resolution ───────────────────────────────────────────────────────────
# BULLSTRANGLE_DATA_DIR sets the base data directory so every path default
# resolves correctly regardless of working directory.
# BULLSTRANGLE_DB (existing) overrides the DB path explicitly and takes
# precedence over the DATA_DIR-derived path.
#
# Typical claude_desktop_config.json env block:
#   "BULLSTRANGLE_DATA_DIR": "C:\\work\\bullstrangle-mcp\\data"
#
# Layout assumed when BULLSTRANGLE_DATA_DIR = <data>:
#   <data>/bullstrangle.db          — SQLite database
#   <data>/newsletters/             — inbound newsletter PDFs
#   <data>/os_uploads/              — refreshed Option Samurai workbooks
#   <data>/../outputs/workbooks/    — generated workbook templates


def _data_dir() -> Path | None:
    """Return the configured or DB-derived data directory, or None if not set."""
    d = os.environ.get("BULLSTRANGLE_DATA_DIR")
    if d:
        return Path(d)
    db = os.environ.get("BULLSTRANGLE_DB")
    return Path(db).parent if db else None


def default_db_path() -> str:
    """DB path: BULLSTRANGLE_DB → DATA_DIR/bullstrangle.db → package default."""
    if "BULLSTRANGLE_DB" in os.environ:
        return os.environ["BULLSTRANGLE_DB"]
    d = _data_dir()
    return str(d / "bullstrangle.db") if d else str(DEFAULT_DB_PATH)


def default_newsletters_dir() -> str:
    """Default newsletter PDF directory: DATA_DIR/newsletters → data/newsletters."""
    d = _data_dir()
    return str(d / "newsletters") if d else "data/newsletters"


def default_os_workbooks_dir() -> str:
    """Default generated workbook output dir: DATA_DIR/../outputs/workbooks."""
    d = _data_dir()
    return str(d.parent / "outputs" / "workbooks") if d else "outputs/workbooks"


mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "BullStrangle newsletter MCP server. Use these tools to ingest weekly "
        "newsletter PDFs, inspect normalized newsletter data, and prepare "
        "Option Samurai workbook metadata."
    ),
)


@mcp.tool()
def ingest_newsletter(
    pdf_path: str,
    db_path: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Ingest one Bull Strangle weekly newsletter PDF into SQLite."""
    return ingest_newsletter_tool(pdf_path, db_path or default_db_path(), force)


@mcp.tool()
def ingest_newsletter_directory(
    directory: str | None = None,
    db_path: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Ingest all newsletter PDFs in a directory.

    directory defaults to DATA_DIR/newsletters when BULLSTRANGLE_DATA_DIR is set,
    otherwise data/newsletters relative to the working directory.
    """
    return ingest_newsletter_directory_tool(
        directory or default_newsletters_dir(),
        db_path or default_db_path(),
        force,
    )


@mcp.tool()
def list_newsletters(db_path: str | None = None) -> list[dict[str, Any]]:
    """List ingested newsletters and their watchlist/market status summary."""
    return list_newsletters_tool(db_path or default_db_path())


@mcp.tool()
def get_newsletter(newsletter_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Return one newsletter with market environment, watchlist, and short lists."""
    return get_newsletter_tool(newsletter_id, db_path or default_db_path())


@mcp.tool()
def get_newsletter_by_date(newsletter_date: str, db_path: str | None = None) -> dict[str, Any]:
    """Return one newsletter by publication date, for example 2026-04-17."""
    return get_newsletter_by_date_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def get_symbol_history(
    symbol: str,
    newsletter_date: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return symbol history and whether the symbol is new for a given newsletter date."""
    return get_symbol_history_tool(symbol, db_path or default_db_path(), newsletter_date)


@mcp.tool()
def calculate_os_selectors(
    newsletter_date: str, db_path: str | None = None
) -> dict[str, Any]:
    """Calculate rounded Option Samurai selectors from one newsletter baseline."""
    return calculate_os_selectors_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def prepare_os_workbook(
    newsletter_date: str, db_path: str | None = None
) -> dict[str, Any]:
    """Create or update OS workbook metadata and formula contract for a newsletter."""
    return prepare_os_workbook_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def generate_os_workbook(
    newsletter_date: str,
    output_dir: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate an Option Samurai-enabled Excel workbook from the newsletter watchlist.

    The workbook is written to output_dir (defaults to DATA_DIR/../outputs/workbooks)
    and automatically copied to DATA_DIR/os_uploads so it is ready for the operator
    to open in Excel, refresh Option Samurai formulas, and save.
    Returns generated_path, uploaded_path, and upload_status.
    """
    return generate_os_workbook_tool(
        newsletter_date,
        db_path or default_db_path(),
        output_dir or default_os_workbooks_dir(),
    )


@mcp.tool()
def ingest_os_workbook(
    workbook_path: str,
    trading_date: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Ingest a refreshed Option Samurai workbook into daily OS snapshot tables."""
    return ingest_os_workbook_tool(workbook_path, db_path or default_db_path(), trading_date)


@mcp.tool()
def ingest_positions(csv_path: str, db_path: str | None = None) -> dict[str, Any]:
    """Ingest account-level positions and symbol rollups from a CSV export."""
    return ingest_positions_tool(csv_path, db_path or default_db_path())


@mcp.tool()
def list_strategy_rules(
    category: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """List strategy rules stored in the database.

    Pass category='decision_threshold' to see only the numeric decision gates
    (max deviations, minimum credits) that the engine uses when evaluating
    Bull Strangle and DCA candidates.  Omit category to return all rules.
    """
    return list_strategy_rules_tool(db_path or default_db_path(), category)


@mcp.tool()
def report_os_run(
    run_id: int,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Create a daily OS ingestion/deviation report for one run."""
    return report_os_run_tool(run_id, db_path or default_db_path(), output_path)


@mcp.tool()
def list_os_runs(
    newsletter_date: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """List OS evaluation runs with run_id, trading date, row count, and status.

    Pass newsletter_date (e.g. 2026-04-17) to filter to one week.
    Omit it to return all runs ordered by newsletter_date DESC then trading_date ASC.
    Use run_id from this list as input to report_os_run.
    """
    return list_os_runs_tool(db_path or default_db_path(), newsletter_date)


@mcp.tool()
def aggregate_os_week(
    newsletter_date: str,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Aggregate all daily OS runs for one newsletter week."""
    return aggregate_os_week_tool(newsletter_date, db_path or default_db_path(), output_path)


@mcp.tool()
def generate_weekend_decisions(
    newsletter_date: str,
    decision_date: str | None = None,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate weekend Bull Strangle and DCA decisions for one newsletter week."""
    return generate_weekend_decisions_tool(
        newsletter_date,
        db_path or default_db_path(),
        decision_date,
        output_path,
    )


@mcp.tool()
def generate_weekly_action_plan(
    newsletter_date: str,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate the Sunday Bull Strangle weekly action plan report.

    Produces a full Markdown report covering market environment, DCA candidates,
    strangle eligibility, WL Favorites deep analysis, action items, and reminders.
    Optionally writes to output_path and logs to generated_reports table.
    """
    return generate_weekly_action_plan_tool(
        newsletter_date,
        db_path or default_db_path(),
        output_path,
    )


@mcp.tool()
def generate_daily_brief(
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate the morning daily monitoring brief.

    Covers: market environment check, active cycles with days-to-expiration,
    and automated alerts (upcoming expirations, deployment status, approved symbols).
    """
    return generate_daily_brief_tool(db_path or default_db_path(), output_path)


@mcp.tool()
def list_generated_reports(
    report_type: str | None = None,
    limit: int = 20,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """List previously generated reports, newest first.

    Pass report_type ('weekly_action_plan' or 'daily_brief') to filter.
    Use the returned report_id with get_generated_report to retrieve full content.
    """
    return list_generated_reports_tool(report_type, limit, db_path or default_db_path())


@mcp.tool()
def get_generated_report(
    report_id: int,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return the full Markdown content of a previously generated report by report_id."""
    return get_generated_report_tool(report_id, db_path or default_db_path())


@mcp.tool()
def get_current_environment(db_path: str | None = None) -> dict[str, Any]:
    """Return the latest market environment with deployment status and all raw metrics."""
    return get_current_environment_tool(db_path or default_db_path())


@mcp.tool()
def check_deployment_approval(db_path: str | None = None) -> dict[str, Any]:
    """Return deployment approval status with per-criterion breakdown and recommended action."""
    return check_deployment_approval_tool(db_path or default_db_path())


@mcp.tool()
def get_watchlist(
    newsletter_date: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return the full watchlist for a newsletter date, including WL Favorites deep analysis."""
    return get_watchlist_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def get_dca_candidates(
    newsletter_date: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return the short-list DCA candidates for a newsletter date."""
    return get_dca_candidates_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def get_active_cycles(db_path: str | None = None) -> list[dict[str, Any]]:
    """Return all newsletters with target_expiration >= today (active position books), soonest first."""
    return get_active_cycles_tool(db_path or default_db_path())


@mcp.tool()
def get_eligible_symbols(
    newsletter_date: str,
    decision: str = "APPROVE",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return bull strangle decision rows filtered by final_decision (APPROVE / WATCH / SKIP)."""
    return get_eligible_symbols_tool(newsletter_date, decision, db_path or default_db_path())


@mcp.tool()
def get_deep_analysis(
    newsletter_date: str,
    symbol: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return Darren's deep-dive WL Favorites analysis. Omit symbol to return all favorites."""
    return get_deep_analysis_tool(newsletter_date, symbol, db_path or default_db_path())


@mcp.tool()
def get_market_environment_history(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 12,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return market environment history rows in descending date order.

    Pass start_date / end_date (YYYY-MM-DD) to filter the range.
    limit controls maximum rows returned (default 12).
    """
    return get_market_environment_history_tool(start_date, end_date, limit, db_path or default_db_path())


@mcp.tool()
def get_scaling_guidance(db_path: str | None = None) -> dict[str, Any]:
    """Return scaling phase, recommended position count, and deployment guidance from latest environment."""
    return get_scaling_guidance_tool(db_path or default_db_path())


@mcp.tool()
def search_commentary(
    query: str,
    limit: int = 10,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Full-text search across all ingested newsletter commentary sections.

    Uses SQLite FTS5. Supports phrase queries ("market uptrend") and
    prefix queries (uptrend*). Returns matching section snippets with
    newsletter date and section name.
    """
    return search_commentary_tool(query, limit, db_path or default_db_path())


@mcp.resource("bullstrangle://database")
def database_info() -> dict[str, Any]:
    """Return the configured paths derived from environment variables."""
    d = _data_dir()
    return {
        "database_path": str(Path(default_db_path()).resolve()),
        "database_exists": Path(default_db_path()).exists(),
        "data_dir": str(d.resolve()) if d else None,
        "newsletters_dir": default_newsletters_dir(),
        "os_workbooks_dir": default_os_workbooks_dir(),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
