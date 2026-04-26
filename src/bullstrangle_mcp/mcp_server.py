from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .database import DEFAULT_DB_PATH
from .tools import (
    aggregate_os_week_tool,
    auto_resolve_expired_tool,
    backtest_all_tool,
    calculate_os_selectors_tool,
    check_deployment_approval_tool,
    evaluate_entry_tool,
    evaluate_exit_batch_tool,
    evaluate_exit_tool,
    evaluate_newsletter_tool,
    generate_backtest_report_tool,
    generate_daily_brief_tool,
    generate_entry_validation_report_tool,
    generate_exit_report_tool,
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
    list_entry_decisions_tool,
    list_exit_decisions_tool,
    list_generated_reports_tool,
    list_newsletters_tool,
    list_os_runs_tool,
    list_rule_catalog_tool,
    list_strategy_rules_tool,
    resolve_cycle_outcomes_tool,
    seed_cycle_layers_tool,
    get_rule_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
    search_commentary_tool,
    validate_all_newsletters_tool,
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


@mcp.tool()
def auto_resolve_expired(db_path: str | None = None) -> dict[str, Any]:
    """Scan for ACTIVE cycle_layers whose expiration has passed and close them.

    Automatically calls resolve_outcomes for every expired newsletter week —
    fetches the yfinance closing price at expiration, computes P&L, and marks
    the layer CLOSED with the correct outcome (BOTH_OTM / CALL_ASSIGNED /
    PUT_ASSIGNED).  Safe to run daily; already-closed layers are untouched.

    Run this every Monday morning (or schedule it) so the book is always
    current before you review the weekly action plan.
    """
    return auto_resolve_expired_tool(db_path or default_db_path())


@mcp.tool()
def seed_cycle_layers(
    newsletter_date: str,
    portfolio_type: str = "small",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Seed cycle_layers from the newsletter Short List for one week.

    Only seeds when the week was deployment-approved. Safe to call multiple times.
    portfolio_type: 'small' (default) or 'large'.
    """
    return seed_cycle_layers_tool(newsletter_date, db_path or default_db_path(), portfolio_type)


@mcp.tool()
def resolve_cycle_outcomes(
    newsletter_date: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Fetch yfinance closing prices at expiration and record P&L for seeded layers.

    Determines BOTH_OTM / CALL_ASSIGNED / PUT_ASSIGNED per symbol.
    Layers whose expiration is in the future are returned as pending.
    """
    return resolve_cycle_outcomes_tool(newsletter_date, db_path or default_db_path())


@mcp.tool()
def backtest_all(
    portfolio_type: str = "small",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Seed and resolve all approved newsletter weeks in one call.

    Runs seed_cycle_layers + resolve_cycle_outcomes for every week where
    deployment was approved. Idempotent — safe to run multiple times.
    """
    return backtest_all_tool(db_path or default_db_path(), portfolio_type)


@mcp.tool()
def generate_backtest_report(
    portfolio_type: str = "small",
    output: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate a week-by-week markdown backtest report from closed cycle layers.

    Shows entry price, strikes, close at expiration, outcome (BOTH_OTM /
    CALL_ASSIGNED / PUT_ASSIGNED), P&L per symbol, and summary stats.
    Optionally write to an output file path.
    """
    return generate_backtest_report_tool(db_path or default_db_path(), portfolio_type, output)


@mcp.tool()
def list_rule_catalog(
    rule_area: str | None = None,
    rule_type: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return strategy rules from the v3 Master Document rule catalog.

    Auto-seeds all 43 canonical rules on first call (idempotent).

    *rule_area* filters by area: stock_selection, earnings, strike_selection,
    capital, cycle, exit, market_environment, formula.

    *rule_type* filters by type: hard_gate, soft_gate, hard_rule, guideline,
    optional_overlay, formula.

    Omit both to return all 43 rules. Each row includes a parsed ``parameters``
    dict so callers can read numeric thresholds directly without parsing JSON.
    """
    return list_rule_catalog_tool(
        db_path or default_db_path(),
        rule_area=rule_area,
        rule_type=rule_type,
    )


@mcp.tool()
def get_rule(rule_id: str, db_path: str | None = None) -> dict[str, Any]:
    """Fetch a single strategy rule by rule_id.

    Returns rule_id, rule_area, rule_type, source_section, description,
    parameters (parsed dict), parameters_json (raw), data_column_mapping,
    is_active.

    Use list_rule_catalog to discover available rule_ids (e.g. GATE-SS-001,
    RULE-EARN-003, RULE-ENV-002, FORMULA-002).
    """
    return get_rule_tool(rule_id, db_path or default_db_path())


@mcp.tool()
def evaluate_exit(
    layer_id: int,
    include_live_price: bool = True,
    persist: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Evaluate exit triggers for one ACTIVE cycle_layer.

    Checks: earnings override (RULE-EARN-003), extreme drop overlays
    (RULE-EXIT-006/007), expiration status, DTE alert, and strike proximity.

    Returns recommended_action: HOLD | REVIEW | EXIT_MONDAY |
    CLOSE_IMMEDIATELY | NEEDS_RESOLUTION — with urgency, rule citations,
    and live price metrics (when include_live_price=True).
    """
    return evaluate_exit_tool(layer_id, db_path or default_db_path(), include_live_price, persist)


@mcp.tool()
def evaluate_exit_batch(
    include_live_price: bool = True,
    persist: bool = True,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Evaluate exit triggers for ALL ACTIVE cycle_layers.

    Fetches live prices for each position (one yfinance call per symbol) and
    returns a sorted list of exit decisions.  Set include_live_price=False to
    skip price fetches and run purely from DB data.
    """
    return evaluate_exit_batch_tool(db_path or default_db_path(), include_live_price, persist)


@mcp.tool()
def generate_exit_report(
    output_path: str | None = None,
    include_live_price: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate a markdown exit monitoring report for all ACTIVE positions.

    Groups positions by urgency tier (IMMEDIATE / THIS_WEEK / ROUTINE),
    shows live price, % change from entry, strike proximity, and triggered
    rule citations.  Optionally writes to output_path.
    Returns ``markdown`` key with the full report.
    """
    return generate_exit_report_tool(
        db_path or default_db_path(),
        output_path,
        include_live_price,
    )


@mcp.tool()
def list_exit_decisions(db_path: str | None = None) -> list[dict[str, Any]]:
    """Return all persisted exit_decisions rows, newest evaluation first."""
    return list_exit_decisions_tool(db_path or default_db_path())


@mcp.tool()
def evaluate_entry(
    symbol: str,
    newsletter_date: str,
    entry_date: str | None = None,
    persist: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Evaluate Gates 1–9 for one symbol against one newsletter week.

    Returns gate_results list, decision_type (BULL_STRANGLE / WATCH / SKIP),
    first_failing_gate, Short List membership, and pricing data.

    Gates 7 (MA alignment) and 8 (weekly deviation) are skipped when no
    Option Samurai data has been ingested — they will not cause a failure.
    """
    return evaluate_entry_tool(
        symbol,
        newsletter_date,
        db_path or default_db_path(),
        entry_date,
        persist,
    )


@mcp.tool()
def evaluate_newsletter(
    newsletter_ref: str,
    persist: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Evaluate Gates 1–9 for every watchlist symbol in one newsletter week.

    newsletter_ref is a publication date (e.g. 2026-04-17) or a numeric
    newsletter_id. Returns decisions list and a validation alignment summary
    comparing gate outcomes to Darren's Short List selections.
    """
    return evaluate_newsletter_tool(newsletter_ref, db_path or default_db_path(), persist)


@mcp.tool()
def validate_all_newsletters(
    persist: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Run gate evaluation across ALL newsletter weeks and aggregate validation stats.

    Answers: does the entry engine consistently explain the Short List selections?
    Returns overall alignment percentages and a per-week breakdown.  Use
    generate_entry_validation_report for a per-week markdown view.
    """
    return validate_all_newsletters_tool(db_path or default_db_path(), persist)


@mcp.tool()
def generate_entry_validation_report(
    newsletter_ref: str,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate a markdown gate validation report for one newsletter week.

    Shows every watchlist symbol with pass/fail/skip per gate, the final
    decision (BULL_STRANGLE / WATCH / SKIP), and Short List membership.
    Includes an alignment summary and gate-failure breakdown table.
    Optionally writes to output_path.  Returns ``markdown`` key.
    """
    return generate_entry_validation_report_tool(
        newsletter_ref,
        db_path or default_db_path(),
        output_path,
    )


@mcp.tool()
def list_entry_decisions(
    newsletter_date: str | None = None,
    decision_type: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return persisted entry_decisions rows.

    Pass newsletter_date (e.g. 2026-04-17) to filter to one week.
    Pass decision_type (BULL_STRANGLE / WATCH / SKIP) to filter by outcome.
    Omit both to return all rows, newest week first.
    """
    return list_entry_decisions_tool(
        newsletter_date,
        db_path or default_db_path(),
        decision_type,
    )


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
