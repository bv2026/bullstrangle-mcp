# BullStrangle MCP Usage Guide

Date: 2026-04-23
Audience: local operator workflow

## Setup

Open PowerShell in the repo:

```powershell
cd C:\work\bullstrangle-mcp
```

Install package and dependencies:

```powershell
pip install -e ".[dev,excel]"
```

The database path used in examples is:

```powershell
data\bullstrangle.db
```

## Canonical Working Locations

Use these as the standard locations going forward:

- Newsletter PDFs: `data\newsletters`
- SQLite DB: `data\bullstrangle.db`
- Positions CSV: `data\positions\positions.csv`
- Generated OS workbook templates: `outputs\workbooks`
- Refreshed OS workbook uploads: `data\os_uploads`
- Generated reports: `reports\YYYY-MM-DD`

Operator rule:

- `outputs\workbooks` is template output only
- `data\os_uploads` is the only place to save Excel-refreshed live workbooks before ingest
- `data\positions\positions.csv` is the canonical positions input file

## One-Time Or Reset Setup

Initialize or migrate the DB:

```powershell
bullstrangle --db data\bullstrangle.db init-db
```

Ingest all newsletter PDFs:

```powershell
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
```

Safety note:

- Newsletter ingestion is non-destructive by default.
- If a newsletter with the same publication date already exists, ingestion will raise an error for that PDF unless you use `--force`.
- `ingest-dir` continues to the next PDF if one file fails and reports the error in its JSON output.

Force replace one existing newsletter:

```powershell
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\some.pdf --force
```

Force replace matching dates during directory ingest:

```powershell
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters --force
```

List ingested newsletters:

```powershell
bullstrangle --db data\bullstrangle.db list-newsletters
```

Show one newsletter by date:

```powershell
bullstrangle --db data\bullstrangle.db show-newsletter 2026-04-24
```

Show symbol history and whether it is new this week:

```powershell
bullstrangle --db data\bullstrangle.db symbol-history NTAP --newsletter-date 2026-04-24
```

## Generate The OS Workbook

Check calculated selectors:

```powershell
bullstrangle --db data\bullstrangle.db os-selectors 2026-04-24
```

Generate the Excel workbook:

```powershell
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-24 --output-dir outputs\workbooks
```

Current generated file:

```text
outputs\workbooks\BullStrangle_OS_Live_2026-04-24.xlsx
```

Inbound refreshed workbook folder:

```text
data\os_uploads
```

Keep generated templates and refreshed uploads separate:

- `outputs\workbooks`: MCP-generated workbook templates.
- `data\os_uploads`: Excel-refreshed workbooks ready for ingestion.

## Market-Hours Daily Workflow

Use this after market opens and Option Samurai can return live data.

1. Copy the generated workbook from `outputs\workbooks` into `data\os_uploads`.
2. Open the copy in `data\os_uploads` in Excel.
3. Make sure the Option Samurai add-in is enabled.
4. Refresh/recalculate the workbook.
5. Save the workbook.
6. Ingest the saved workbook from `data\os_uploads`.

Ingest command:

```powershell
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-23
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
bullstrangle --db data\bullstrangle.db report-os-run 2 --output reports\2026-04-23\os_run_2.md
```

To print full JSON:

```powershell
bullstrangle --db data\bullstrangle.db report-os-run 2 --json
```

## Weekly Aggregation

Run this after one or more daily OS uploads. It can be run any time; it recomputes the weekly aggregate table for the newsletter date.

```powershell
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --output reports\2026-04-23\os_week_2026-04-24.md
```

To print full JSON:

```powershell
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --json
```

The weekly report shows:

- OS run count
- valid/invalid symbols
- missing core values
- top price deviations
- top credit deviations

## Positions Ingestion

Use this after updating `data\positions\positions.csv`.

```powershell
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
```

The command stores:

- one import run in `position_import_runs`
- one row per account/symbol in `account_positions`
- one symbol-level awareness row in `symbol_position_rollups`

Important:

- Consolidated symbol quantity is used for portfolio awareness.
- Bull Strangle readiness requires `100` shares in one account.
- `100` shares split across accounts does not qualify.
- DCA uses the selected/target account and shares needed to reach `100`.

## Weekend Decision Generation

Run after the weekly OS uploads are complete.

Example:

```powershell
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-25 --output reports\2026-04-25\weekend_decisions_2026-04-24.md
```

To print full JSON:

```powershell
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-25 --json
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
'@ | python -
```

## Claude Desktop MCP

`claude_desktop_config.json` entry:

```json
{
  "mcpServers": {
    "bullstrangle-mcp": {
      "command": "bullstrangle-mcp-server",
      "args": [],
      "env": {
        "BULLSTRANGLE_DATA_DIR": "C:\\work\\bullstrangle-mcp\\data"
      }
    }
  }
}
```

`BULLSTRANGLE_DATA_DIR` sets the base data folder.  The server derives:

- DB path: `{DATA_DIR}/bullstrangle.db`
- Newsletter PDF dir: `{DATA_DIR}/newsletters`
- Generated workbook output: `{DATA_DIR}/../outputs/workbooks`

`BULLSTRANGLE_DB` may still be set to override the DB path explicitly.  When
both are set, `BULLSTRANGLE_DB` wins for the database path only.

Available MCP tools:

- `ingest_newsletter`
- `ingest_newsletter_directory`
- `list_newsletters`
- `get_newsletter`
- `get_newsletter_by_date`
- `get_symbol_history`
- `calculate_os_selectors`
- `prepare_os_workbook`
- `generate_os_workbook`
- `ingest_os_workbook`
- `ingest_positions`
- `list_strategy_rules`
- `list_os_runs`
- `report_os_run`
- `aggregate_os_week`
- `generate_weekend_decisions`

## Tool Reference

Newsletter/query tools:

- `list_newsletters`
- `get_newsletter`
- `get_newsletter_by_date`
- `get_symbol_history`

OS workflow tools:

- `calculate_os_selectors`
- `prepare_os_workbook`
- `generate_os_workbook`
- `ingest_os_workbook`
- `list_os_runs`
- `report_os_run`
- `aggregate_os_week`

Decision/rules tools:

- `list_strategy_rules`
- `generate_weekend_decisions`

Portfolio tools:

- `ingest_positions`

Example symbol-history prompt:

```text
Use the BullStrangle MCP tools to get symbol history for NTAP for newsletter date 2026-04-24. Tell me whether it is new, when it first appeared, and which prior newsletters included it.
```

Use `list_strategy_rules` with `category="decision_threshold"` to inspect the
numeric gates (max deviations, minimum credits) currently in use by the
decision engine.  To change a threshold without a code deploy, update the
`rule_parameters` JSON value in SQLite and re-run `generate_weekend_decisions`.

MCP ingest safety:

- `ingest_newsletter` and `ingest_newsletter_directory` also support `force`.
- Leave `force` unset for normal use.
- Use `force=true` only when you intentionally want to replace an already-ingested newsletter date.

## Test Commands

Run all tests:

```powershell
pytest -q
```

Current expected result:

```text
50 passed
```

Run by layer:

```powershell
pytest -q -m unit
pytest -q -m integration
pytest -q -m e2e
```

Compile check:

```powershell
python -m compileall -q src
```

## Current Known Good Artifacts

Generated workbook:

```text
outputs\workbooks\BullStrangle_OS_Live_2026-04-24.xlsx
```

Inbound OS upload folder:

```text
data\os_uploads
```

Generated reports:

```text
reports\2026-04-22\os_run_1.md
reports\2026-04-22\os_week_2026-04-24.md
reports\2026-04-22\weekend_decisions_2026-04-24.md
```

Canonical current files:

```text
data\positions\positions.csv
outputs\workbooks\BullStrangle_OS_Live_2026-04-24.xlsx
data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx
```

Current local April 17 status:

- OS runs: `2`
- OS rows: `24`
- weekly aggregate symbols: `24`
- Preferred actions: `BULL_STRANGLE 17`, `DCA 3`, `WATCH 4`, `SKIP 0`
- Bull Strangle decisions: `APPROVE 17`, `WATCH 4`, `SKIP 3`
- DCA decisions: `APPROVE 3`, `WATCH 4`, `SKIP 17`

## Tomorrow Checklist

When the market opens:

1. Copy `outputs\workbooks\BullStrangle_OS_Live_2026-04-24.xlsx` to `data\os_uploads`.
2. Open the copy in `data\os_uploads`.
3. Refresh Option Samurai formulas in Excel.
4. Save the workbook.
5. Run `ingest-os-workbook` against the file in `data\os_uploads` with tomorrow's trading date.
6. Run `report-os-run` for the new `run_id`.
7. Run `aggregate-os-week`.
8. Review missing values and largest deviations.

Weekend decisions can wait until the week is complete.

## Dry Run References

For a simple operator dry run:

- `references/BullStrangle_Dry_Run_Runbook.md`

For Claude Desktop prompts:

- `references/Claude_Prompts_BullStrangle.md`
