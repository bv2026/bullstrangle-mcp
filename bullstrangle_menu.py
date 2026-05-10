"""
BullStrangle Interactive Menu CLI
Use this when Claude Desktop is unavailable (e.g., usage limits exhausted).
Replicates the core MCP workflow via the existing bullstrangle CLI.

Usage:
    python bullstrangle_menu.py
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

DB = r"data\bullstrangle.db"
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "data" / "reports"


def report_path(nl_date: str, name: str) -> Path:
    d = REPORTS_DIR / "weekly" / nl_date
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}.md"


def daily_report_path(trading_date: str, name: str) -> Path:
    d = REPORTS_DIR / "daily" / trading_date
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}.md"


def run_cmd(args: list[str], show_output: bool = True) -> str:
    cmd = ["bullstrangle", "--db", DB] + args
    print(f"\n  > {' '.join(cmd)}\n")
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


def save_path(date_key: str, name: str, daily: bool = False) -> str:
    p = daily_report_path(date_key, name) if daily else report_path(date_key, name)
    print(f"  Saving to: {p}")
    return str(p)


def get_friday() -> str:
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    friday = today - timedelta(days=days_since_friday)
    return friday.isoformat()


def get_today() -> str:
    return date.today().isoformat()


def latest_run_id(nl_date: str) -> str | None:
    import sqlite3
    db_path = BASE_DIR / DB
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT id FROM os_evaluation_runs WHERE newsletter_date = ? ORDER BY trading_date DESC, id DESC LIMIT 1",
        (nl_date,),
    ).fetchone()
    conn.close()
    return str(row[0]) if row else None


def newsletter_exists(nl_date: str) -> bool:
    import sqlite3
    db_path = BASE_DIR / DB
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT 1 FROM newsletters WHERE publication_date = ?", (nl_date,)
    ).fetchone()
    conn.close()
    return row is not None


def find_newsletter_pdf(nl_date: str) -> Path | None:
    nl_dir = BASE_DIR / "data" / "newsletters"
    if not nl_dir.exists():
        return None
    from datetime import datetime
    try:
        d = datetime.strptime(nl_date, "%Y-%m-%d")
    except ValueError:
        return None
    month_name = d.strftime("%B")
    day = d.day
    for p in sorted(nl_dir.glob("*.pdf"), reverse=True):
        name_lower = p.name.lower()
        if month_name.lower() in name_lower and str(day) in name_lower:
            return p
    return None


# ─── MENU HANDLERS ───────────────────────────────────────────────────────────


def menu_weekly():
    friday = get_friday()
    while True:
        print("\n╔══ WEEKLY WORKFLOW ══╗")
        print("  Sunday: 1 → 2 → 3 → 5  |  Friday: 4")
        choice = prompt_choice([
            "Ingest Newsletter + Generate Workbook",
            "Market Brief",
            "Weekly Action Plan",
            "OS Weekly Aggregation (end of week)",
            "Weekend Decisions (BS + DCA)",
        ])
        if choice == 0:
            return
        nl_date = prompt_date("Newsletter date", friday)
        if choice == 1:
            already_ingested = newsletter_exists(nl_date)
            if already_ingested:
                print(f"  Newsletter {nl_date} already ingested — skipping PDF.")
                args = ["weekend-setup", nl_date]
            else:
                pdf = find_newsletter_pdf(nl_date)
                if pdf:
                    print(f"  Found PDF: {pdf}")
                    args = ["weekend-setup", nl_date, "--pdf", str(pdf)]
                else:
                    print(f"  No PDF found in data\\newsletters for {nl_date}.")
                    print(f"  Drop the PDF there and retry.")
                    continue
            run_cmd(args)
        elif choice == 2:
            out = save_path(nl_date, "market_brief")
            args = ["daily-brief", "--output", out]
            run_cmd(args)
        elif choice == 3:
            out = save_path(nl_date, "action_plan")
            args = ["weekly-action-plan", nl_date, "--output", out]
            run_cmd(args)
        elif choice == 4:
            out = save_path(nl_date, "os_weekly")
            args = ["aggregate-os-week", nl_date, "--output", out]
            run_cmd(args)
        elif choice == 5:
            out = save_path(nl_date, "weekend_decisions")
            args = ["generate-weekend-decisions", nl_date, "--output", out]
            run_cmd(args)


def menu_daily():
    friday = get_friday()
    today = get_today()
    while True:
        print("\n╔══ DAILY WORKFLOW ══╗")
        print("  Market hours: 1 → 2 → 3  |  Ad-hoc: 4-7")
        choice = prompt_choice([
            "Ingest Refreshed Workbook",
            "Evaluate Newsletter + Gate Report",
            "Daily Brief (exit alerts, positions, status)",
            "Evaluate Single Symbol (gate check)",
            "OS Run Report",
            "Exit Report (detailed)",
            "Auto-Resolve Expired",
        ])
        if choice == 0:
            return
        if choice == 1:
            nl_date = prompt_date("Newsletter date", friday)
            workbook = BASE_DIR / "data" / "os_uploads" / f"BullStrangle_OS_Live_{nl_date}.xlsx"
            if not workbook.exists():
                print(f"  Workbook not found: {workbook}")
                print(f"  Run Weekly Setup first, then refresh in Excel and save.")
                continue
            print(f"  Workbook: {workbook}")
            td = prompt_date("Trading date", today)
            run_cmd(["daily-ingest", nl_date, "--trading-date", td])
        elif choice == 2:
            nl_date = prompt_date("Newsletter date", friday)
            print("\n  Evaluating all symbols...")
            run_cmd(["evaluate-newsletter", nl_date], show_output=False)
            print("  Generating gate report...")
            out = save_path(today, "gate_report", daily=True)
            args = ["gate-report", nl_date, "--output", out]
            run_cmd(args)
        elif choice == 3:
            out = save_path(today, "daily_brief", daily=True)
            args = ["daily-brief", "--output", out]
            run_cmd(args)
        elif choice == 4:
            sym = input("  Symbol: ").strip().upper()
            if sym:
                nl_date = prompt_date("Newsletter date", friday)
                run_cmd(["evaluate-entry", sym, nl_date])
        elif choice == 5:
            nl_date = prompt_date("Newsletter date", friday)
            rid = latest_run_id(nl_date)
            if not rid:
                print(f"  No OS runs found for {nl_date}.")
                continue
            print(f"  Latest run ID: {rid}")
            out = save_path(today, f"os_run_{rid}", daily=True)
            run_cmd(["report-os-run", rid, "--output", out])
        elif choice == 6:
            ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
            out = save_path(today, f"exit_{ptype}", daily=True)
            args = ["exit-report", "--portfolio-type", ptype, "--output", out]
            run_cmd(args)
        elif choice == 7:
            ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
            run_cmd(["auto-resolve", "--portfolio-type", ptype])


def menu_portfolio():
    while True:
        print("\n╔══ PORTFOLIO & BACKTEST ══╗")
        choice = prompt_choice([
            "Portfolio Performance",
            "Backtest Report",
            "Backtest All (seed + resolve all)",
            "Seed Cycle Layers (single week)",
            "Resolve Outcomes (single week)",
        ])
        if choice == 0:
            return
        ptype = input("  Portfolio [small/large] (small): ").strip() or "small"
        if choice == 1:
            run_cmd(["portfolio-performance", "--portfolio-type", ptype])
        elif choice == 2:
            out = save_path(get_friday(), f"backtest_{ptype}")
            args = ["backtest-report", "--portfolio-type", ptype, "--output", out]
            run_cmd(args)
        elif choice == 3:
            run_cmd(["backtest-all", "--portfolio-type", ptype])
        elif choice == 4:
            nl_date = prompt_date("Newsletter date", get_friday())
            run_cmd(["seed-cycle-layers", nl_date, "--portfolio-type", ptype])
        elif choice == 5:
            nl_date = prompt_date("Newsletter date", get_friday())
            run_cmd(["resolve-outcomes", nl_date])


def menu_maintenance():
    while True:
        print("\n╔══ MAINTENANCE & LOOKUP ══╗")
        choice = prompt_choice([
            "List Newsletters",
            "Show Newsletter Details",
            "Symbol History",
            "Strategy Rules (list all)",
            "Strategy Rules (by area)",
            "Get Single Rule",
            "List Entry Decisions",
            "List Exit Decisions",
            "Validate All Newsletters (gate alignment)",
            "Ingest Positions CSV",
            "Bulk Re-Ingest All PDFs",
            "DB Status (row counts)",
        ])
        if choice == 0:
            return
        if choice == 1:
            run_cmd(["list-newsletters"])
        elif choice == 2:
            ref = input("  Newsletter id or date: ").strip()
            if ref:
                run_cmd(["show-newsletter", ref])
        elif choice == 3:
            sym = input("  Symbol: ").strip().upper()
            if sym:
                run_cmd(["symbol-history", sym])
        elif choice == 4:
            run_cmd(["list-rule-catalog"])
        elif choice == 5:
            area = input("  Area (stock_selection/earnings/exit/market_environment/capital/cycle/strike_selection/formula): ").strip()
            if area:
                run_cmd(["list-rule-catalog", "--area", area])
        elif choice == 6:
            rule_id = input("  Rule ID (e.g. GATE-SS-001): ").strip()
            if rule_id:
                run_cmd(["get-rule", rule_id])
        elif choice == 7:
            nl_date = prompt_date("Newsletter date (blank=all)", get_friday())
            args = ["list-entry-decisions"]
            if nl_date:
                args += ["--newsletter-date", nl_date]
            run_cmd(args)
        elif choice == 8:
            run_cmd(["list-exit-decisions"])
        elif choice == 9:
            run_cmd(["validate-all"])
        elif choice == 10:
            run_cmd(["ingest-positions", "data\\positions\\positions.csv"])
        elif choice == 11:
            run_cmd(["ingest-dir", "data\\newsletters"])
        elif choice == 12:
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


def main():
    print("""
+---------------------------------------------------------+
|       BullStrangle CLI -- Offline Operator Menu          |
|  Use when Claude Desktop is unavailable                  |
+---------------------------------------------------------+
""")

    while True:
        print("\n=== MAIN MENU ===")
        choice = prompt_choice([
            "Weekly Workflow     (ingest, market brief, action plan)",
            "Daily Workflow      (ingest workbook, evaluate, daily brief)",
            "Portfolio & Backtest",
            "Maintenance & Lookup",
        ])
        if choice == 0:
            print("\n  Goodbye.\n")
            break
        elif choice == 1:
            menu_weekly()
        elif choice == 2:
            menu_daily()
        elif choice == 3:
            menu_portfolio()
        elif choice == 4:
            menu_maintenance()


if __name__ == "__main__":
    main()
