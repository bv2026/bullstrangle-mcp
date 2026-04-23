from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database
from .decisions import generate_weekend_decisions
from .ingestion import ingest_directory, ingest_newsletter
from .os_ingestion import ingest_os_workbook
from .os_reports import report_os_run
from .os_weekly import aggregate_os_week
from .os_workbooks import (
    calculate_newsletter_selectors,
    generate_os_workbook,
    prepare_os_workbook_record,
)
from .positions import ingest_positions


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
    output_dir: str = "outputs/os_workbooks",
) -> dict[str, Any]:
    """Generate an Option Samurai-enabled Excel workbook from a newsletter watchlist."""
    initialize_database(db_path)
    return generate_os_workbook(newsletter_date, db_path, output_dir)


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
