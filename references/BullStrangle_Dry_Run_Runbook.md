# BullStrangle Dry Run Runbook

Date: 2026-04-23
Audience: operator dry run

## Purpose

Use this runbook to exercise the full workflow without treating the output as final production trading logic.

This dry run is intended to validate:

- newsletter ingestion
- OS workbook generation
- refreshed OS workbook ingestion
- positions ingestion
- weekly aggregation
- weekend decision generation
- report output and diagnostics

## Current Dry Run Status

The system is ready for a workflow dry run.

Current local capabilities:

- CLI implemented
- MCP server implemented
- newsletter ingestion implemented
- OS workbook generation implemented
- refreshed workbook ingestion implemented
- positions ingestion implemented
- weekly aggregation implemented
- weekend decision generation implemented
- decision diagnostics implemented
- tests passing

What is still provisional:

- strategy score weights
- final thresholds from the Master Document
- executable DCA sizing
- cash/buying-power-aware account deployment

## Inputs

Expected local inputs:

- newsletter PDFs under `data/newsletters`
- generated workbook templates under `outputs/os_workbooks`
- refreshed OS workbooks under `data/os_uploads`
- positions CSV under `data/positions/positions.csv`

## Environment

Open PowerShell in:

```powershell
cd C:\work\bullstrangle-mcp
```

Set Python:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## Dry Run Checklist

### 1. Initialize And Confirm DB

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db init-db
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db list-newsletters
```

### 2. Ingest Newsletter PDFs

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-dir data\newsletters
```

Confirm one target newsletter:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db show-newsletter 2026-04-17
```

### 3. Generate OS Workbook

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-os-workbook 2026-04-17 --output-dir outputs\os_workbooks
```

Expected workbook:

```text
outputs\os_workbooks\BullStrangle_OS_Live_2026-04-17.xlsx
```

### 4. Refresh Workbook In Excel

1. Copy the workbook into `data\os_uploads`
2. Open the copied file in Excel
3. Refresh Option Samurai formulas
4. Save the workbook

Expected refreshed file:

```text
data\os_uploads\BullStrangle_OS_Live_2026-04-17.xlsx
```

### 5. Ingest Refreshed OS Workbook

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-17.xlsx --trading-date 2026-04-23
```

Capture the returned `run_id`.

### 6. Generate Daily OS Report

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db report-os-run 2 --output reports\2026-04-23\os_run_2.md
```

Review:

- missing/error rows
- largest price deviations
- largest credit deviations
- strike changes

### 7. Ingest Positions

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-positions data\positions\positions.csv
```

Review:

- account count
- symbol count
- bull-strangle-ready symbols

### 8. Aggregate Weekly OS Data

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db aggregate-os-week 2026-04-17 --output reports\2026-04-23\os_week_2026-04-17.md
```

Review:

- run count
- invalid symbols
- top price deviations
- top credit deviations

### 9. Generate Weekend Decisions

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-23 --output reports\2026-04-23\weekend_decisions_2026-04-17.md
```

Review:

- preferred action counts
- Bull Strangle counts
- DCA counts
- symbol-level reasons

### 10. Inspect Diagnostics

Use `--json` if you want the full payload:

```powershell
& $py -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-23 --json
```

Look for:

- `selected_action`
- `strategy_score`
- `strategy_band`
- `rules_passed_json`
- `rules_failed_json`
- `source_snapshot_json`

## Dry Run Success Criteria

The dry run is successful if:

- newsletter date resolves correctly
- workbook generates correctly
- refreshed workbook ingests without schema errors
- daily report renders
- positions import succeeds
- weekly aggregation renders
- weekend decisions render
- diagnostics are populated on decision rows

## Current Known-Good Example

April 17 local example currently produces:

- Preferred actions: `BULL_STRANGLE 17`, `DCA 3`, `WATCH 4`, `SKIP 0`
- Bull Strangle: `APPROVE 17`, `WATCH 4`, `SKIP 3`
- DCA: `APPROVE 3`, `WATCH 4`, `SKIP 17`

## Dry Run Caveat

Treat this as a workflow validation run, not final production trade approval.

The score/action framework is implemented, but final strategy calibration still depends on:

- Master Document rule extraction
- more multi-day OS uploads
- threshold tuning
- DCA sizing rules
