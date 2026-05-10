"""
BullStrangle Interactive Menu CLI
Use this when Claude Desktop is unavailable (e.g., usage limits exhausted).
Replicates the core MCP workflow via the existing bullstrangle CLI.

Usage:
    python bullstrangle_menu.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

DB = r"data\bullstrangle.db"
BASE_DIR = Path(__file__).parent


def run_cmd(args: list[str], show_output: bool = True) -> str:
    cmd = ["bullstrangle", "--db", DB] + args
    print(f"\n  → {' '.join(cmd)}\n")
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(BASE_DIR),
    )
    output = result.stdout + result.stderr
    if show_output:
        print(output[:5000])
        if len(output) > 5000:
            print(f"\n  ... ({len(output)} chars total, truncated)")
    if result.returncode != 0:
        print(f"  [Exit code: {result.returncode}]")
    return output


def prompt_date(label: str, default: str | None = None) -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"  {label}{hint}: ").strip()
    return val or default or ""


def prompt_choice(options: list[str]) -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. Back")
    while True:
        try:
            choice = int(input("\n  Select: "))
            if 0 <= choice <= len(options):
                return choice
        except (ValueError, EOFError):
            pass
        print("  Invalid choice, try again.")


def get_friday() -> str:
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    friday = today - timedelta(days=days_since_friday)
    return friday.isoformat()


def get_today() -> str:
    return date.today().isoformat()


# ─── MENU HANDLERS ───────────────────────────────────────────────────────────


def menu_daily_workflow():
    friday = get_friday()
    today = get_today()
    while True:
        print("\n╔══ DAILY WORKFLOW ══╗")
        choice = prompt_choice([
            "Daily Brief (morning monitoring)",
            "Daily Ingest (after Excel refresh)",
            "Exit Report (active positions)",
            "Auto-Resolve Expired",
        ])
        if choice == 0:
            return
        if choice == 1:
            run_cmd(["daily-brief"])
        elif choice == 2:
            nl_date = prompt_date("Newsletter date", friday)
            td = prompt_date("Trading date", today)
            run_cmd(["daily-ingest", nl_date, "--trading-date", td])
        elif choice == 3:
            ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
            run_cmd(["exit-report", "--portfolio-type", ptype])
        elif choice == 4:
            ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
            run_cmd(["auto-resolve", "--portfolio-type", ptype])


def menu_weekend_workflow():
    friday = get_friday()
    while True:
        print("\n╔══ WEEKEND WORKFLOW ══╗")
        choice = prompt_choice([
            "Weekend Setup (ingest PDF + generate workbook)",
            "Weekly Action Plan",
            "Gate Report (entry validation)",
            "Evaluate Newsletter (all symbols)",
            "OS Weekly Aggregation",
        ])
        if choice == 0:
            return
        if choice == 1:
            nl_date = prompt_date("Newsletter date", friday)
            pdf = input("  PDF path (Enter to skip if already ingested): ").strip()
            args = ["weekend-setup", nl_date]
            if pdf:
                args += ["--pdf", pdf]
            run_cmd(args)
        elif choice == 2:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["weekly-action-plan", nl_date])
        elif choice == 3:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["gate-report", nl_date])
        elif choice == 4:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["evaluate-newsletter", nl_date])
        elif choice == 5:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["aggregate-os-week", nl_date])


def menu_portfolio():
    while True:
        print("\n╔══ PORTFOLIO & BACKTEST ══╗")
        choice = prompt_choice([
            "Portfolio Performance",
            "Backtest Report",
            "Seed Cycle Layers",
            "Resolve Outcomes",
            "Backtest All (seed + resolve all)",
        ])
        if choice == 0:
            return
        ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
        if choice == 1:
            run_cmd(["portfolio-performance", "--portfolio-type", ptype])
        elif choice == 2:
            run_cmd(["backtest-report", "--portfolio-type", ptype])
        elif choice == 3:
            nl_date = prompt_date("Newsletter date", get_friday())
            run_cmd(["seed-cycle-layers", nl_date, "--portfolio-type", ptype])
        elif choice == 4:
            nl_date = prompt_date("Newsletter date", get_friday())
            run_cmd(["resolve-outcomes", nl_date])
        elif choice == 5:
            run_cmd(["backtest-all", "--portfolio-type", ptype])


def menu_data():
    while True:
        print("\n╔══ DATA & INGESTION ══╗")
        choice = prompt_choice([
            "List Newsletters",
            "Ingest Newsletter PDF",
            "Ingest All PDFs in Directory",
            "Ingest Positions CSV",
            "Symbol History",
            "Show Newsletter Details",
            "DB Status (row counts)",
        ])
        if choice == 0:
            return
        if choice == 1:
            run_cmd(["list-newsletters"])
        elif choice == 2:
            pdf = input("  PDF path: ").strip()
            if pdf:
                run_cmd(["ingest-pdf", pdf])
        elif choice == 3:
            d = input("  Directory [data\\newsletters]: ").strip() or "data\\newsletters"
            run_cmd(["ingest-dir", d])
        elif choice == 4:
            csv = input("  CSV path [data\\positions\\positions.csv]: ").strip() or "data\\positions\\positions.csv"
            run_cmd(["ingest-positions", csv])
        elif choice == 5:
            sym = input("  Symbol: ").strip().upper()
            if sym:
                run_cmd(["symbol-history", sym])
        elif choice == 6:
            ref = input("  Newsletter id or date: ").strip()
            if ref:
                run_cmd(["show-newsletter", ref])
        elif choice == 7:
            print()
            subprocess.run(
                [sys.executable, "-c", """
import sqlite3
conn = sqlite3.connect('data/bullstrangle.db')
tables = [
    'newsletters', 'watchlist_entries', 'short_list_entries',
    'earnings_calendar', 'os_evaluation_runs', 'os_evaluation_rows',
    'os_weekly_symbol_aggregates', 'strategy_rule_catalog',
    'entry_decisions', 'exit_decisions', 'cycle_layers', 'position_books',
]
for t in tables:
    try:
        n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t:<35} {n}')
    except Exception:
        print(f'  {t:<35} (not found)')
"""],
                cwd=str(BASE_DIR),
            )


def menu_rules():
    while True:
        print("\n╔══ STRATEGY RULES ══╗")
        choice = prompt_choice([
            "List All Rules",
            "List by Area (stock_selection, exit, etc.)",
            "Get Single Rule",
        ])
        if choice == 0:
            return
        if choice == 1:
            run_cmd(["list-rule-catalog"])
        elif choice == 2:
            area = input("  Area (stock_selection/earnings/exit/market_environment/capital/cycle/strike_selection/formula): ").strip()
            if area:
                run_cmd(["list-rule-catalog", "--area", area])
        elif choice == 3:
            rule_id = input("  Rule ID (e.g. GATE-SS-001): ").strip()
            if rule_id:
                run_cmd(["get-rule", rule_id])


def menu_os_workbook():
    friday = get_friday()
    while True:
        print("\n╔══ OS WORKBOOK ══╗")
        choice = prompt_choice([
            "Generate OS Workbook",
            "Ingest Refreshed Workbook",
            "OS Selectors (calculated values)",
            "Report OS Run",
            "List OS Runs",
        ])
        if choice == 0:
            return
        if choice == 1:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["generate-os-workbook", nl_date])
        elif choice == 2:
            path = input("  Workbook path: ").strip()
            td = prompt_date("Trading date", get_today())
            if path:
                run_cmd(["ingest-os-workbook", path, "--trading-date", td, "--regenerate-if-stale"])
        elif choice == 3:
            nl_date = prompt_date("Newsletter date", friday)
            run_cmd(["os-selectors", nl_date])
        elif choice == 4:
            run_id = input("  Run ID: ").strip()
            if run_id:
                run_cmd(["report-os-run", run_id])
        elif choice == 5:
            run_cmd(["list-newsletters"])  # Shows context for choosing
            # Actually list OS runs - need newsletter date or use list-newsletters
            nl_date = prompt_date("Newsletter date (or Enter for all)", "")
            # The CLI doesn't have list-os-runs as command yet; use daily-brief or aggregate
            if nl_date:
                run_cmd(["aggregate-os-week", nl_date, "--json"])


def main():
    print("""
╔═══════════════════════════════════════════════════════╗
║       BullStrangle CLI — Offline Operator Menu       ║
║  Use when Claude Desktop is unavailable              ║
╚═══════════════════════════════════════════════════════╝
""")

    while True:
        print("\n═══ MAIN MENU ═══")
        choice = prompt_choice([
            "Daily Workflow      (brief, ingest, exit monitor)",
            "Weekend Workflow    (setup, action plan, gates)",
            "Portfolio & Backtest",
            "Data & Ingestion    (newsletters, positions, DB)",
            "OS Workbook         (generate, ingest, report)",
            "Strategy Rules      (catalog lookup)",
        ])
        if choice == 0:
            print("\n  Goodbye.\n")
            break
        elif choice == 1:
            menu_daily_workflow()
        elif choice == 2:
            menu_weekend_workflow()
        elif choice == 3:
            menu_portfolio()
        elif choice == 4:
            menu_data()
        elif choice == 5:
            menu_os_workbook()
        elif choice == 6:
            menu_rules()


if __name__ == "__main__":
    main()
