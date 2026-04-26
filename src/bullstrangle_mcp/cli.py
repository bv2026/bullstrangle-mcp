from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database import DEFAULT_DB_PATH, initialize_database
from .tools import (
    aggregate_os_week_tool,
    auto_resolve_expired_tool,
    backtest_all_tool,
    calculate_os_selectors_tool,
    evaluate_entry_tool,
    evaluate_exit_batch_tool,
    evaluate_exit_tool,
    evaluate_newsletter_tool,
    generate_entry_validation_report_tool,
    generate_exit_report_tool,
    generate_os_workbook_tool,
    generate_weekend_decisions_tool,
    get_newsletter_by_ref_tool,
    get_newsletter_tool,
    generate_backtest_report_tool,
    get_rule_tool,
    get_symbol_history_tool,
    list_entry_decisions_tool,
    list_exit_decisions_tool,
    resolve_cycle_outcomes_tool,
    seed_cycle_layers_tool,
    ingest_os_workbook_tool,
    ingest_newsletter_directory_tool,
    ingest_newsletter_tool,
    ingest_positions_tool,
    list_newsletters_tool,
    list_rule_catalog_tool,
    prepare_os_workbook_tool,
    report_os_run_tool,
    validate_all_newsletters_tool,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bullstrangle")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or update the SQLite schema")

    ingest_pdf = subparsers.add_parser("ingest-pdf", help="Ingest one newsletter PDF")
    ingest_pdf.add_argument("pdf_path")
    ingest_pdf.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing newsletter for the same publication date",
    )

    ingest_dir = subparsers.add_parser("ingest-dir", help="Ingest all PDFs in a directory")
    ingest_dir.add_argument("directory", nargs="?", default="data/newsletters")
    ingest_dir.add_argument(
        "--force",
        action="store_true",
        help="Replace existing newsletters that share a publication date",
    )

    subparsers.add_parser("list-newsletters", help="List ingested newsletters")

    show = subparsers.add_parser(
        "show-newsletter", help="Show one ingested newsletter by id or date"
    )
    show.add_argument("newsletter_ref", help="Newsletter id or date, e.g. 34 or 2026-04-17")

    symbol_history = subparsers.add_parser(
        "symbol-history",
        help="Show symbol history and whether the symbol is new for a newsletter date",
    )
    symbol_history.add_argument("symbol", help="Symbol, e.g. NTAP")
    symbol_history.add_argument(
        "--newsletter-date",
        help="Optional newsletter date to determine whether the symbol is new for that week",
    )

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
        "--output-dir", default="outputs/workbooks", help="Directory for generated .xlsx files"
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

    seed_cmd = subparsers.add_parser(
        "seed-cycle-layers",
        help="Seed cycle_layers from the Short List for one newsletter week",
    )
    seed_cmd.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    seed_cmd.add_argument("--portfolio-type", default="small", choices=["small", "large"])

    resolve_cmd = subparsers.add_parser(
        "resolve-outcomes",
        help="Fetch yfinance expiration prices and compute P&L for seeded layers",
    )
    resolve_cmd.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")

    backtest_cmd = subparsers.add_parser(
        "backtest-all",
        help="Seed and resolve all approved newsletter weeks (one-shot backtest)",
    )
    backtest_cmd.add_argument("--portfolio-type", default="small", choices=["small", "large"])

    backtest_report_cmd = subparsers.add_parser(
        "backtest-report",
        help="Generate a week-by-week markdown backtest report",
    )
    backtest_report_cmd.add_argument("--portfolio-type", default="small", choices=["small", "large"])
    backtest_report_cmd.add_argument("--output", help="Optional path to write the Markdown report")

    list_rules = subparsers.add_parser(
        "list-rule-catalog",
        help="List v3 strategy rules from the Master Document catalog",
    )
    list_rules.add_argument(
        "--area",
        dest="rule_area",
        help="Filter by area: stock_selection, earnings, strike_selection, capital, "
             "cycle, exit, market_environment, formula",
    )
    list_rules.add_argument(
        "--type",
        dest="rule_type",
        help="Filter by type: hard_gate, soft_gate, hard_rule, guideline, "
             "optional_overlay, formula",
    )

    get_rule_p = subparsers.add_parser(
        "get-rule",
        help="Fetch a single strategy rule by rule_id",
    )
    get_rule_p.add_argument("rule_id", help="Rule id, e.g. GATE-SS-001 or RULE-EARN-003")

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

    eval_entry_cmd = subparsers.add_parser(
        "evaluate-entry",
        help="Evaluate Gates 1-9 for one symbol against one newsletter week",
    )
    eval_entry_cmd.add_argument("symbol", help="Ticker symbol, e.g. NTAP")
    eval_entry_cmd.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    eval_entry_cmd.add_argument("--entry-date", help="Override entry date")
    eval_entry_cmd.add_argument(
        "--no-persist", action="store_true", help="Skip writing to entry_decisions table"
    )

    eval_newsletter_cmd = subparsers.add_parser(
        "evaluate-newsletter",
        help="Evaluate Gates 1-9 for all watchlist symbols in one newsletter week",
    )
    eval_newsletter_cmd.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    eval_newsletter_cmd.add_argument(
        "--no-persist", action="store_true", help="Skip writing to entry_decisions table"
    )
    eval_newsletter_cmd.add_argument(
        "--json", action="store_true", help="Print full JSON instead of summary"
    )

    validate_all_cmd = subparsers.add_parser(
        "validate-all",
        help="Run gate evaluation across all newsletter weeks and report alignment",
    )
    validate_all_cmd.add_argument(
        "--no-persist", action="store_true", help="Skip writing to entry_decisions table"
    )

    gate_report_cmd = subparsers.add_parser(
        "gate-report",
        help="Generate a markdown gate validation report for one newsletter week",
    )
    gate_report_cmd.add_argument("newsletter_date", help="Newsletter date, e.g. 2026-04-17")
    gate_report_cmd.add_argument("--output", help="Optional path to write the Markdown report")

    list_entry_decisions_cmd = subparsers.add_parser(
        "list-entry-decisions",
        help="List persisted entry_decisions rows",
    )
    list_entry_decisions_cmd.add_argument(
        "--newsletter-date", help="Filter to one week, e.g. 2026-04-17"
    )
    list_entry_decisions_cmd.add_argument(
        "--decision-type",
        choices=["BULL_STRANGLE", "WATCH", "SKIP"],
        help="Filter by decision outcome",
    )

    eval_exit_cmd = subparsers.add_parser(
        "evaluate-exit",
        help="Evaluate exit triggers for one ACTIVE cycle_layer",
    )
    eval_exit_cmd.add_argument("layer_id", type=int, help="Layer ID from cycle_layers table")
    eval_exit_cmd.add_argument(
        "--no-price", action="store_true", help="Skip live price fetch (faster)"
    )
    eval_exit_cmd.add_argument(
        "--no-persist", action="store_true", help="Skip writing to exit_decisions table"
    )

    eval_exit_batch_cmd = subparsers.add_parser(
        "evaluate-exit-batch",
        help="Evaluate exit triggers for all ACTIVE cycle_layers",
    )
    eval_exit_batch_cmd.add_argument(
        "--no-price", action="store_true", help="Skip live price fetch (faster)"
    )
    eval_exit_batch_cmd.add_argument(
        "--no-persist", action="store_true", help="Skip writing to exit_decisions table"
    )
    eval_exit_batch_cmd.add_argument(
        "--json", action="store_true", help="Print full JSON instead of summary"
    )

    exit_report_cmd = subparsers.add_parser(
        "exit-report",
        help="Generate markdown exit monitoring report for all ACTIVE positions",
    )
    exit_report_cmd.add_argument("--output", help="Optional path to write the Markdown report")
    exit_report_cmd.add_argument(
        "--no-price", action="store_true", help="Skip live price fetch (faster)"
    )

    list_exit_decisions_cmd = subparsers.add_parser(
        "list-exit-decisions",
        help="List persisted exit_decisions rows",
    )

    subparsers.add_parser(
        "auto-resolve",
        help="Auto-resolve expired ACTIVE positions (fetch yfinance close, compute P&L)",
    )

    args = parser.parse_args(argv)

    if args.command == "init-db":
        initialize_database(args.db)
        print(json.dumps({"database_path": str(Path(args.db).resolve()), "status": "ok"}, indent=2))
        return 0
    if args.command == "ingest-pdf":
        print(json.dumps(ingest_newsletter_tool(args.pdf_path, args.db, args.force), indent=2))
        return 0
    if args.command == "ingest-dir":
        print(json.dumps(ingest_newsletter_directory_tool(args.directory, args.db, args.force), indent=2))
        return 0
    if args.command == "list-newsletters":
        print(json.dumps(list_newsletters_tool(args.db), indent=2))
        return 0
    if args.command == "show-newsletter":
        print(json.dumps(get_newsletter_by_ref_tool(args.newsletter_ref, args.db), indent=2))
        return 0
    if args.command == "symbol-history":
        print(
            json.dumps(
                get_symbol_history_tool(args.symbol, args.db, args.newsletter_date),
                indent=2,
            )
        )
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
    if args.command == "seed-cycle-layers":
        print(json.dumps(seed_cycle_layers_tool(args.newsletter_date, args.db, args.portfolio_type), indent=2))
        return 0
    if args.command == "resolve-outcomes":
        print(json.dumps(resolve_cycle_outcomes_tool(args.newsletter_date, args.db), indent=2))
        return 0
    if args.command == "backtest-all":
        print(json.dumps(backtest_all_tool(args.db, args.portfolio_type), indent=2))
        return 0
    if args.command == "backtest-report":
        report = generate_backtest_report_tool(args.db, args.portfolio_type, args.output)
        print(report["markdown"])
        return 0
    if args.command == "list-rule-catalog":
        print(
            json.dumps(
                list_rule_catalog_tool(args.db, args.rule_area, args.rule_type),
                indent=2,
            )
        )
        return 0
    if args.command == "get-rule":
        print(json.dumps(get_rule_tool(args.rule_id, args.db), indent=2))
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
    if args.command == "evaluate-entry":
        print(
            json.dumps(
                evaluate_entry_tool(
                    args.symbol,
                    args.newsletter_date,
                    args.db,
                    args.entry_date,
                    not args.no_persist,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate-newsletter":
        result = evaluate_newsletter_tool(args.newsletter_date, args.db, not args.no_persist)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            val = result["validation"]
            print(f"\nNewsletter: {result['newsletter_date']}")
            print(f"  Symbols evaluated : {val['watchlist_count']}")
            print(f"  Passed hard gates : {val['passed_all_hard_gates']}")
            print(f"  BULL_STRANGLE     : {val['bull_strangle_eligible']}")
            print(f"  Small SL alignment: {val['small_alignment']['pass']}/{val['small_short_list_count']} "
                  f"({val['small_alignment']['pct']}%)")
            print(f"  Large SL alignment: {val['large_alignment']['pass']}/{val['large_short_list_count']} "
                  f"({val['large_alignment']['pct']}%)")
            if val["gate_failure_breakdown"]:
                print("\n  Gate failure breakdown:")
                for gate_name, syms in val["gate_failure_breakdown"].items():
                    print(f"    {gate_name}: {len(syms)} ({', '.join(syms)})")
        return 0
    if args.command == "validate-all":
        print(json.dumps(validate_all_newsletters_tool(args.db, not args.no_persist), indent=2))
        return 0
    if args.command == "gate-report":
        result = generate_entry_validation_report_tool(
            args.newsletter_date, args.db, args.output
        )
        print(result["markdown"])
        return 0
    if args.command == "list-entry-decisions":
        print(
            json.dumps(
                list_entry_decisions_tool(args.newsletter_date, args.db, args.decision_type),
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate-exit":
        print(
            json.dumps(
                evaluate_exit_tool(
                    args.layer_id,
                    args.db,
                    not args.no_price,
                    not args.no_persist,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate-exit-batch":
        decisions = evaluate_exit_batch_tool(args.db, not args.no_price, not args.no_persist)
        if args.json:
            print(json.dumps(decisions, indent=2))
        else:
            print(f"\nActive positions: {len(decisions)}")
            for d in decisions:
                urgency_label = {"IMMEDIATE": "[!!!]", "THIS_WEEK": "[!]", "ROUTINE": "[OK]"}.get(
                    d["action_urgency"], "[?]"
                )
                price_str = f"${d['current_price']:.2f}" if d.get("current_price") else "N/A"
                chg_str = (
                    f"{d['pct_change_from_entry']:+.1f}%"
                    if d.get("pct_change_from_entry") is not None else "N/A"
                )
                print(
                    f"  {urgency_label} {d['symbol']:6s} exp {d['expiration_date']} "
                    f"DTE={d['days_to_expiration']:3d} "
                    f"price={price_str:7s} ({chg_str}) "
                    f"-> {d['recommended_action']}"
                )
        return 0
    if args.command == "exit-report":
        result = generate_exit_report_tool(args.db, args.output, not args.no_price)
        # Print ASCII-safe to console (emoji survive in the saved file)
        print(result["markdown"].encode("ascii", errors="replace").decode("ascii"))
        return 0
    if args.command == "list-exit-decisions":
        print(json.dumps(list_exit_decisions_tool(args.db), indent=2))
        return 0
    if args.command == "auto-resolve":
        result = auto_resolve_expired_tool(args.db)
        if not result["auto_resolved"]:
            print(result["message"])
        else:
            print(f"Resolved {result['total_resolved']} position(s) across {result['weeks_processed']} week(s):")
            for wk in result["weeks"]:
                print(f"\n  {wk['newsletter_date']}:")
                for outcome in wk["outcomes"]:
                    pnl_str = f"${outcome['pnl']:+.0f}" if outcome.get("pnl") is not None else "?"
                    print(f"    {outcome['symbol']:8s} -> {outcome['outcome']} ({pnl_str})")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
