# BullStrangle MCP Implementation Guide

Date: 2026-04-22
Status: v1 implemented locally

## Overview

This project is a local Python package that ingests Bull Strangle weekly newsletter PDFs, stores normalized data in SQLite, generates Option Samurai-enabled Excel workbooks, ingests refreshed Excel snapshots, tracks deviations, aggregates weekly OS data, and generates v1 weekend decisions.

The package exposes the same workflow through:

- CLI: `bullstrangle`
- Python modules under `src/bullstrangle_mcp`
- Claude-compatible MCP server: `bullstrangle-mcp-server`

## Runtime

Python requirement:

- Python `>=3.11`

Project dependencies:

- `mcp`
- `openpyxl`
- `pypdf`

Development dependencies:

- `pytest`
- `pytest-asyncio`

Current local bundled Python path:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

Install locally:

```powershell
& $py -m pip install -e ".[dev,excel]"
```

## Source Layout

Core modules:

- `src/bullstrangle_mcp/database.py`: SQLite schema, migrations, seed strategy rules.
- `src/bullstrangle_mcp/ingestion.py`: PDF parsing and newsletter section extraction.
- `src/bullstrangle_mcp/os_workbooks.py`: OS selector calculation and workbook generation.
- `src/bullstrangle_mcp/os_ingestion.py`: refreshed Excel workbook ingestion.
- `src/bullstrangle_mcp/os_reports.py`: daily OS run Markdown report generation.
- `src/bullstrangle_mcp/os_weekly.py`: weekly aggregation across daily OS uploads.
- `src/bullstrangle_mcp/decisions.py`: v1 weekend Bull Strangle and DCA candidate decisions.
- `src/bullstrangle_mcp/tools.py`: MCP-shaped tool wrapper functions.
- `src/bullstrangle_mcp/cli.py`: command line interface.
- `src/bullstrangle_mcp/mcp_server.py`: stdio MCP server.

Tests:

- `tests/test_unit_os_workbooks.py`: selector rounding unit tests.
- `tests/test_ingestion_smoke.py`: integration workflow from PDF through weekend decisions.
- `tests/test_e2e_mcp_server.py`: MCP server stdio e2e test.

## Data Directories

Inputs:

- `data/newsletters`: weekly newsletter PDFs.
- `osamurai`: Option Samurai templates, field references, and PDFs used for formula design.

Generated local data:

- `data/bullstrangle.db`: SQLite database.
- `outputs/os_workbooks`: generated OS workbooks for Excel/Option Samurai refresh.
- `reports/YYYY-MM-DD`: generated Markdown reports.

Audit/support files:

- `data/os_formula_contract.json`
- `data/os_workbook_audit.json`
- `data/section_audit.json`
- `data/section_audit_latest.json`

## Database Layers

Newsletter baseline:

- `newsletters`
- `newsletter_full_text`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deep_analysis`
- `market_environment`
- `weekly_decisions`
- `symbol_history`

Strategy/reference:

- `strategy_reference_sections`
- `strategy_rules`

Option Samurai workflow:

- `os_workbooks`
- `os_evaluation_runs`
- `os_evaluation_rows`
- `watchlist_deviations`
- `os_weekly_symbol_aggregates`

Weekend decisions:

- `decision_batches`
- `bull_strangle_decisions`
- `dca_decisions`

Important design rule:

- `watchlist_entries` is immutable newsletter baseline data. Daily OS values never overwrite it.

## Implemented Flow

1. PDF ingestion extracts newsletter metadata, watchlist, short lists, market environment, commentary, and strategy references.
2. OS workbook generation calculates newsletter-average option selectors and writes an Excel workbook with Option Samurai formulas.
3. User opens the workbook in Excel with Option Samurai enabled, refreshes formulas, saves it, and uploads/places the file for ingestion.
4. OS ingestion reads the workbook, stores one run plus one evaluated row per symbol, and computes deviations against the newsletter baseline.
5. Daily reporting summarizes one OS run.
6. Weekly aggregation rolls up all OS runs for a newsletter date.
7. Weekend decision generation creates one decision batch and separate Bull Strangle/DCA candidate decisions.

## Option Samurai Workbook Contract

Generated workbook:

- `OS_Live`: formulas and live values.
- `Baseline`: read-only newsletter baseline copy.
- `Instructions`: brief refresh/upload instructions.
- hidden `Metadata`: workbook metadata needed for ingestion.

Current formula approach:

- Uses `_xldudf_optionsamurai_stock(...)`.
- Uses `_xldudf_optionsamurai_option(...)`.
- Uses newsletter-derived percentage selectors by default.

Selector derivation:

- sell call selector: average `(sell_call_strike - stock_price) / stock_price`
- sell put selector: average `(sell_put_strike - stock_price) / stock_price`
- buy put selector: average `(buy_put_strike - stock_price) / stock_price`
- default rounding: nearest `0.5%`

Fallback design:

- If newsletter average is not usable, delta-band fallback is documented but not currently the normal path.

## Decision Logic Status

Master Document status:

- `references/Bull Strangle Master Document - Version 8.pdf` is included as the master strategy reference.
- The full Master Document strategy has not yet been encoded into the decision engine.
- Current v1 strategy logic is scaffolding based on newsletter appendix extraction, Option Samurai integration, and workflow/account rules captured so far.
- The implementation plan for converting the Master Document into structured rules is in `references/BullStrangle_Master_Document_Implementation_Plan.md`.

Bull Strangle v1:

- `APPROVE` when market deployment is approved, weekly OS data is valid, total credit is positive, price deviation is under `8%`, and credit deviation is under `$2.50`.
- `WATCH` when OS data is usable and credit is positive but another gate is not passed.
- `SKIP` when core OS values are missing or credit is not usable.

DCA v1:

- `APPROVE` when market allocation is above zero, OS data is valid, candidate score is at least `1.0`, and price deviation is under `8%`.
- `WATCH` when allocation exists and candidate score passes but another gate is not passed.
- `SKIP` when allocation, candidate score, or OS data is not usable.

DCA caveat:

- DCA currently means candidate decision only. Holdings, available cash, target shares, and account constraints are intentionally deferred.

Account-aware DCA rule:

- Positions can be distributed across multiple accounts.
- Portfolio exposure can be viewed at consolidated symbol level.
- Execution must be account-specific: one DCA or Bull Strangle action maps to one account only.
- A DCA recommendation should target the account where the system is trying to build toward `100` shares.
- A symbol becomes Bull Strangle eligible only when one account has at least `100` shares.
- `100` shares split across multiple accounts should not be treated as Bull Strangle-ready.

## MCP Tools

Available tools:

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

MCP server module:

```powershell
& $py -m bullstrangle_mcp.mcp_server
```

Claude Desktop command:

```powershell
C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

Claude Desktop args:

```json
["-m", "bullstrangle_mcp.mcp_server"]
```

Environment:

```json
{
  "BULLSTRANGLE_DB": "C:\\work\\bullstrangle-mcp\\data\\bullstrangle.db"
}
```

## Testing

Run full suite:

```powershell
& $py -m pytest -q
```

Run by layer:

```powershell
& $py -m pytest -q -m unit
& $py -m pytest -q -m integration
& $py -m pytest -q -m e2e
```

Current expected result:

```text
7 passed
```

Compile check:

```powershell
& $py -m compileall -q src
```

## Known Deferred Work

- Multi-day live OS validation after additional market-hours uploads.
- Full Master Document strategy extraction and implementation.
- Decision threshold tuning after real multi-day OS data exists.
- DCA holdings/account-state ingestion with single-account execution selection.
- Executable DCA allocation logic.
- Report persistence tables: `report_templates`, `report_runs`, `generated_reports`.
- Richer weekend reports after decision rules stabilize.
