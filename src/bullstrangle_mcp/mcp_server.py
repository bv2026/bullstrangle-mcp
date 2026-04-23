from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .database import DEFAULT_DB_PATH
from .tools import (
    aggregate_os_week_tool,
    calculate_os_selectors_tool,
    generate_os_workbook_tool,
    generate_weekend_decisions_tool,
    get_newsletter_by_date_tool,
    get_newsletter_tool,
    get_symbol_history_tool,
    ingest_os_workbook_tool,
    ingest_newsletter_directory_tool,
    ingest_newsletter_tool,
    ingest_positions_tool,
    list_newsletters_tool,
    list_os_runs_tool,
    list_strategy_rules_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
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
#   <data>/../outputs/os_workbooks/ — generated workbook templates


def _data_dir() -> Path | None:
    """Return the configured data directory, or None if not set."""
    d = os.environ.get("BULLSTRANGLE_DATA_DIR")
    return Path(d) if d else None


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
    """Default generated workbook output dir: DATA_DIR/../outputs/os_workbooks."""
    d = _data_dir()
    return str(d.parent / "outputs" / "os_workbooks") if d else "outputs/os_workbooks"


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

    output_dir defaults to DATA_DIR/../outputs/os_workbooks when BULLSTRANGLE_DATA_DIR
    is set, otherwise outputs/os_workbooks relative to the working directory.
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
