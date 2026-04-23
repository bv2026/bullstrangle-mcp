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
    ingest_os_workbook_tool,
    ingest_newsletter_directory_tool,
    ingest_newsletter_tool,
    ingest_positions_tool,
    list_newsletters_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
)


SERVER_NAME = "bullstrangle-newsletter"


def default_db_path() -> str:
    return os.environ.get("BULLSTRANGLE_DB", str(DEFAULT_DB_PATH))


mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "BullStrangle newsletter MCP server. Use these tools to ingest weekly "
        "newsletter PDFs, inspect normalized newsletter data, and prepare "
        "Option Samurai workbook metadata."
    ),
)


@mcp.tool()
def ingest_newsletter(pdf_path: str, db_path: str | None = None) -> dict[str, Any]:
    """Ingest one Bull Strangle weekly newsletter PDF into SQLite."""
    return ingest_newsletter_tool(pdf_path, db_path or default_db_path())


@mcp.tool()
def ingest_newsletter_directory(
    directory: str = "data/newsletters", db_path: str | None = None
) -> dict[str, Any]:
    """Ingest all newsletter PDFs in a directory."""
    return ingest_newsletter_directory_tool(directory, db_path or default_db_path())


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
    output_dir: str = "outputs/os_workbooks",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Generate an Option Samurai-enabled Excel workbook from the newsletter watchlist."""
    return generate_os_workbook_tool(newsletter_date, db_path or default_db_path(), output_dir)


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
def report_os_run(
    run_id: int,
    output_path: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Create a daily OS ingestion/deviation report for one run."""
    return report_os_run_tool(run_id, db_path or default_db_path(), output_path)


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
    """Return the configured local database path."""
    path = Path(default_db_path())
    return {
        "database_path": str(path.resolve()),
        "exists": path.exists(),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
