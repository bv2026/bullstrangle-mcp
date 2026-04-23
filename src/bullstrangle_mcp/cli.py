from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database import DEFAULT_DB_PATH, initialize_database
from .tools import (
    aggregate_os_week_tool,
    calculate_os_selectors_tool,
    generate_os_workbook_tool,
    generate_weekend_decisions_tool,
    get_newsletter_by_ref_tool,
    get_newsletter_tool,
    ingest_os_workbook_tool,
    ingest_newsletter_directory_tool,
    ingest_newsletter_tool,
    ingest_positions_tool,
    list_newsletters_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bullstrangle")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or update the SQLite schema")

    ingest_pdf = subparsers.add_parser("ingest-pdf", help="Ingest one newsletter PDF")
    ingest_pdf.add_argument("pdf_path")

    ingest_dir = subparsers.add_parser("ingest-dir", help="Ingest all PDFs in a directory")
    ingest_dir.add_argument("directory", nargs="?", default="data/newsletters")

    subparsers.add_parser("list-newsletters", help="List ingested newsletters")

    show = subparsers.add_parser(
        "show-newsletter", help="Show one ingested newsletter by id or date"
    )
    show.add_argument("newsletter_ref", help="Newsletter id or date, e.g. 34 or 2026-04-17")

    selectors = subparsers.add_parser(
        "os-selectors", help="Calculate rounded Option Samurai selectors for a newsletter"
    )
    selectors.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")

    prepare_os = subparsers.add_parser(
        "prepare-os-workbook",
        help="Create or update the OS workbook metadata row for a newsletter",
    )
    prepare_os.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")

    generate_os = subparsers.add_parser(
        "generate-os-workbook",
        help="Generate the Option Samurai Excel workbook for a newsletter",
    )
    generate_os.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    generate_os.add_argument(
        "--output-dir", default="outputs/os_workbooks", help="Directory for generated .xlsx files"
    )

    ingest_os = subparsers.add_parser(
        "ingest-os-workbook",
        help="Ingest a refreshed Option Samurai Excel workbook",
    )
    ingest_os.add_argument("workbook_path")
    ingest_os.add_argument("--trading-date", help="Trading date for the OS snapshot, e.g. 2026-04-22")

    ingest_positions = subparsers.add_parser(
        "ingest-positions",
        help="Ingest account-level positions from a CSV export",
    )
    ingest_positions.add_argument("csv_path", help="Positions CSV path, e.g. data/positions/positions.csv")

    report_os = subparsers.add_parser(
        "report-os-run",
        help="Show a daily OS ingestion/deviation report for one run",
    )
    report_os.add_argument("run_id", type=int)
    report_os.add_argument("--output", help="Optional path to write a Markdown report")
    report_os.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON instead of the Markdown report",
    )

    aggregate_os = subparsers.add_parser(
        "aggregate-os-week",
        help="Aggregate all daily OS runs for one newsletter date",
    )
    aggregate_os.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    aggregate_os.add_argument("--output", help="Optional path to write a Markdown report")
    aggregate_os.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON instead of the Markdown report",
    )

    weekend_decisions = subparsers.add_parser(
        "generate-weekend-decisions",
        help="Generate weekend Bull Strangle and DCA decisions for a newsletter date",
    )
    weekend_decisions.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    weekend_decisions.add_argument("--decision-date", help="Decision date, defaults to today")
    weekend_decisions.add_argument("--output", help="Optional path to write a Markdown report")
    weekend_decisions.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON instead of the Markdown report",
    )

    args = parser.parse_args(argv)

    if args.command == "init-db":
        initialize_database(args.db)
        print(json.dumps({"database_path": str(Path(args.db).resolve()), "status": "ok"}, indent=2))
        return 0
    if args.command == "ingest-pdf":
        print(json.dumps(ingest_newsletter_tool(args.pdf_path, args.db), indent=2))
        return 0
    if args.command == "ingest-dir":
        print(json.dumps(ingest_newsletter_directory_tool(args.directory, args.db), indent=2))
        return 0
    if args.command == "list-newsletters":
        print(json.dumps(list_newsletters_tool(args.db), indent=2))
        return 0
    if args.command == "show-newsletter":
        print(json.dumps(get_newsletter_by_ref_tool(args.newsletter_ref, args.db), indent=2))
        return 0
    if args.command == "os-selectors":
        print(json.dumps(calculate_os_selectors_tool(args.newsletter_date, args.db), indent=2))
        return 0
    if args.command == "prepare-os-workbook":
        print(json.dumps(prepare_os_workbook_tool(args.newsletter_date, args.db), indent=2))
        return 0
    if args.command == "generate-os-workbook":
        print(
            json.dumps(
                generate_os_workbook_tool(args.newsletter_date, args.db, args.output_dir),
                indent=2,
            )
        )
        return 0
    if args.command == "ingest-os-workbook":
        print(
            json.dumps(
                ingest_os_workbook_tool(args.workbook_path, args.db, args.trading_date),
                indent=2,
            )
        )
        return 0
    if args.command == "ingest-positions":
        print(json.dumps(ingest_positions_tool(args.csv_path, args.db), indent=2))
        return 0
    if args.command == "report-os-run":
        report = report_os_run_tool(args.run_id, args.db, args.output)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(report["markdown"])
        return 0
    if args.command == "aggregate-os-week":
        aggregate = aggregate_os_week_tool(args.newsletter_date, args.db, args.output)
        if args.json:
            print(json.dumps(aggregate, indent=2))
        else:
            print(aggregate["markdown"])
        return 0
    if args.command == "generate-weekend-decisions":
        decisions = generate_weekend_decisions_tool(
            args.newsletter_date,
            args.db,
            args.decision_date,
            args.output,
        )
        if args.json:
            print(json.dumps(decisions, indent=2))
        else:
            print(decisions["markdown"])
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
