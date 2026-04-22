# BullStrangle MCP Usage Guide

Date: 2026-04-22
Audience: local operator workflow

## Setup

Open PowerShell in the repo:

```powershell
cd C:\work\bullstrangle-mcp
```

Set the Python variable:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

Install package and dependencies:

```powershell
& $py -m pip install -e ".[dev,excel]"
```

The database path used in examples is:

```powershell
data\bullstrangle.db
```

## One-Time Or Reset Setup

Initialize or migrate the DB:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db init-db
```

Ingest all newsletter PDFs:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-dir data\newsletters
```

List ingested newsletters:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db list-newsletters
```

Show one newsletter by date:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db show-newsletter 2026-04-17
```

## Generate The OS Workbook

Check calculated selectors:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db os-selectors 2026-04-17
```

Generate the Excel workbook:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-os-workbook 2026-04-17 --output-dir outputs\os_workbooks
```

Current generated file:

```text
outputs\os_workbooks\BullStrangle_OS_Live_2026-04-17.xlsx
```

Inbound refreshed workbook folder:

```text
data\os_uploads
```

Keep generated templates and refreshed uploads separate:

- `outputs\os_workbooks`: MCP-generated workbook templates.
- `data\os_uploads`: Excel-refreshed workbooks ready for ingestion.

## Market-Hours Daily Workflow

Use this after market opens and Option Samurai can return live data.

1. Copy the generated workbook from `outputs\os_workbooks` into `data\os_uploads`.
2. Open the copy in `data\os_uploads` in Excel.
3. Make sure the Option Samurai add-in is enabled.
4. Refresh/recalculate the workbook.
5. Save the workbook.
6. Ingest the saved workbook from `data\os_uploads`.

Ingest command:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-17.xlsx --trading-date 2026-04-23
```

Use the actual trading date for `--trading-date`.

The command returns:

- `run_id`
- `workbook_id`
- `newsletter_date`
- `expiration_date`
- `row_count`
- `populated_live_value_count`
- `formula_cell_count`
- `status`

If Excel did not save cached formula values, the ingest may report blanks or formula-only values. In that case, open the workbook, refresh formulas, save again, and re-ingest.

## Daily OS Report

Use the `run_id` returned by `ingest-os-workbook`.

Example:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db report-os-run 2 --output reports\2026-04-23\os_run_2.md
```

To print full JSON:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db report-os-run 2 --json
```

## Weekly Aggregation

Run this after one or more daily OS uploads. It can be run any time; it recomputes the weekly aggregate table for the newsletter date.

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db aggregate-os-week 2026-04-17 --output reports\2026-04-23\os_week_2026-04-17.md
```

To print full JSON:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db aggregate-os-week 2026-04-17 --json
```

The weekly report shows:

- OS run count
- valid/invalid symbols
- missing core values
- top price deviations
- top credit deviations

## Weekend Decision Generation

Run after the weekly OS uploads are complete.

Example:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-25 --output reports\2026-04-25\weekend_decisions_2026-04-17.md
```

To print full JSON:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-25 --json
```

Current v1 output includes:

- one `decision_batches` row
- one `bull_strangle_decisions` row per watchlist symbol
- one `dca_decisions` row per watchlist symbol
- Markdown summary with APPROVE/WATCH/SKIP counts

DCA note:

- DCA output is candidate-only until holdings/account-state ingestion is added.
- Positions may be spread across accounts, but a future DCA or Bull Strangle recommendation must be assigned to one account only.
- DCA goal is to build the selected account position to `100` shares.
- A symbol should be promoted to Bull Strangle only after one account reaches `100` shares.
- Total shares split across multiple accounts are useful for exposure awareness, but not enough for Bull Strangle promotion.

## Query Useful DB Counts

Use Python against SQLite:

```powershell
@'
import sqlite3
conn = sqlite3.connect("data/bullstrangle.db")
for table in [
    "newsletters",
    "watchlist_entries",
    "os_evaluation_runs",
    "os_evaluation_rows",
    "watchlist_deviations",
    "os_weekly_symbol_aggregates",
    "decision_batches",
    "bull_strangle_decisions",
    "dca_decisions",
]:
    print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
'@ | & $py -
```

## Claude Desktop MCP

Claude Desktop config example:

```json
{
  "mcpServers": {
    "bullstrangle": {
      "command": "C:\\Users\\vsbra\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe",
      "args": [
        "-m",
        "bullstrangle_mcp.mcp_server"
      ],
      "env": {
        "BULLSTRANGLE_DB": "C:\\work\\bullstrangle-mcp\\data\\bullstrangle.db"
      }
    }
  }
}
```

Available MCP tools:

- `ingest_newsletter`
- `ingest_newsletter_directory`
- `list_newsletters`
- `get_newsletter`
- `get_newsletter_by_date`
- `calculate_os_selectors`
- `prepare_os_workbook`
- `generate_os_workbook`
- `ingest_os_workbook`
- `report_os_run`
- `aggregate_os_week`
- `generate_weekend_decisions`

## Test Commands

Run all tests:

```powershell
& $py -m pytest -q
```

Run by layer:

```powershell
& $py -m pytest -q -m unit
& $py -m pytest -q -m integration
& $py -m pytest -q -m e2e
```

Compile check:

```powershell
& $py -m compileall -q src
```

## Current Known Good Artifacts

Generated workbook:

```text
outputs\os_workbooks\BullStrangle_OS_Live_2026-04-17.xlsx
```

Inbound OS upload folder:

```text
data\os_uploads
```

Generated reports:

```text
reports\2026-04-22\os_run_1.md
reports\2026-04-22\os_week_2026-04-17.md
reports\2026-04-22\weekend_decisions_2026-04-17.md
```

Current local April 17 status:

- OS runs: `1`
- OS rows: `24`
- weekly aggregate symbols: `24`
- Bull Strangle decisions: `24`
- DCA candidate decisions: `24`

## Tomorrow Checklist

When the market opens:

1. Copy `outputs\os_workbooks\BullStrangle_OS_Live_2026-04-17.xlsx` to `data\os_uploads`.
2. Open the copy in `data\os_uploads`.
3. Refresh Option Samurai formulas in Excel.
4. Save the workbook.
5. Run `ingest-os-workbook` against the file in `data\os_uploads` with tomorrow's trading date.
6. Run `report-os-run` for the new `run_id`.
7. Run `aggregate-os-week`.
8. Review missing values and largest deviations.

Weekend decisions can wait until the week is complete.
