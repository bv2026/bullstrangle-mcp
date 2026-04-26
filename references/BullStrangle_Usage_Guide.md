# BullStrangle MCP Usage Guide

Date: 2026-04-26
Audience: local operator workflow

---

## Setup

Open PowerShell in the repo:

```powershell
cd C:\work\bullstrangle-mcp
```

Install package and dependencies:

```powershell
pip install -e ".[dev,excel]"
```

All CLI examples below use the `bullstrangle` entry point.
Substitute `python -m bullstrangle_mcp.cli` if the entry point is unavailable.

Default database path:

```text
data\bullstrangle.db
```

---

## Canonical Working Locations

| What | Where |
|------|-------|
| Newsletter PDFs | `data\newsletters` |
| SQLite DB | `data\bullstrangle.db` |
| Positions CSV | `data\positions\positions.csv` |
| Generated OS workbook templates | `outputs\workbooks` |
| Refreshed OS workbooks for ingest | `data\os_uploads` |
| Generated reports | `outputs\reports\YYYY-MM-DD` |

Operator rules:
- `outputs\workbooks` is template output only — never edit or save over these files.
- `data\os_uploads` is auto-populated on workbook generation; open the file there, refresh, and save in place before ingest.
- `data\positions\positions.csv` is the canonical positions input file.

---

## Weekly Monitoring Workflow (May Cycle)

This is the primary workflow for the May 2026 validation period.
Run these commands each week to track open positions and strategy alignment.

### Monday Morning — Auto-Resolve + Exit Check

Auto-close any positions that expired over the weekend:

```powershell
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type small
```

Then review the exit monitoring report for all still-open positions:

```powershell
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --output outputs\reports\exit_report_small.md
```

Print to console (no file save):

```powershell
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small
```

Skip live price fetch (faster, offline):

```powershell
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --no-price
```

### After Newsletter Arrives — Ingest + Gate Validation

Ingest the new PDF:

```powershell
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\newsletter.pdf
```

Check whether the market is deployed this week:

```powershell
bullstrangle --db data\bullstrangle.db check-deployment 2026-04-24
```

Evaluate all watchlist symbols against Gates 1–9:

```powershell
bullstrangle --db data\bullstrangle.db evaluate-newsletter 2026-04-24
```

Generate and save the full gate validation report:

```powershell
bullstrangle --db data\bullstrangle.db gate-report 2026-04-24 --output outputs\reports\gate_report_2026-04-24.md
```

### After OS Workbook Refresh — Ingest + Aggregate

Ingest the refreshed workbook (use actual trading date):

```powershell
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28
```

Aggregate for the week:

```powershell
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --output outputs\reports\os_week_2026-04-24.md
```

### Weekend — Portfolio Performance

Check equity curve and performance for both portfolios:

```powershell
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type small
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type large
```

Full backtest report with equity curve (saved to file):

```powershell
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type small --output outputs\reports\backtest_small.md
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type large --output outputs\reports\backtest_large.md
```

---

## CLI Fallback Reference

**Use this section if Claude Desktop is unavailable due to usage limits.**
All monitoring tasks can be performed from PowerShell alone.

### Database & Newsletter

```powershell
# Initialize or migrate DB
bullstrangle --db data\bullstrangle.db init-db

# Ingest one PDF
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\newsletter.pdf

# Force re-ingest (replace existing)
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\newsletter.pdf --force

# Ingest whole folder
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters

# List ingested newsletters
bullstrangle --db data\bullstrangle.db list-newsletters

# Show one newsletter
bullstrangle --db data\bullstrangle.db show-newsletter 2026-04-24

# Symbol history across newsletters
bullstrangle --db data\bullstrangle.db symbol-history NTAP --newsletter-date 2026-04-24
```

### OS Workbook & Daily Ingestion

```powershell
# Check selector values
bullstrangle --db data\bullstrangle.db os-selectors 2026-04-24

# Generate Excel workbook template
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-24 --output-dir outputs\workbooks

# Ingest refreshed workbook
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28

# List OS runs for a newsletter
bullstrangle --db data\bullstrangle.db list-os-runs --newsletter-date 2026-04-24

# Daily OS run report
bullstrangle --db data\bullstrangle.db report-os-run 3 --output outputs\reports\os_run_3.md

# Weekly aggregation
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --output outputs\reports\os_week_2026-04-24.md
```

### Positions

```powershell
# Ingest positions CSV
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
```

### Rule Catalog

```powershell
# List all 47 strategy rules
bullstrangle --db data\bullstrangle.db list-rule-catalog

# Filter by area (stock_selection, earnings, exit, market_environment, capital, cycle, strike_selection, formula)
bullstrangle --db data\bullstrangle.db list-rule-catalog --area exit

# Filter by type (hard_gate, hard_rule, soft_gate, guideline, optional_overlay, formula)
bullstrangle --db data\bullstrangle.db list-rule-catalog --type hard_gate

# Fetch one rule by ID
bullstrangle --db data\bullstrangle.db get-rule GATE-SS-001
bullstrangle --db data\bullstrangle.db get-rule GATE-ME-001
bullstrangle --db data\bullstrangle.db get-rule EXIT-001
```

### Gate Validation (Entry Engine)

```powershell
# Evaluate all 9 gates for one symbol (latest newsletter)
bullstrangle --db data\bullstrangle.db evaluate-entry NTAP --newsletter-date 2026-04-24

# Evaluate all symbols for one newsletter week
bullstrangle --db data\bullstrangle.db evaluate-newsletter 2026-04-24

# Validate all newsletters (full history)
bullstrangle --db data\bullstrangle.db validate-all

# Generate gate validation report (saved to file)
bullstrangle --db data\bullstrangle.db gate-report 2026-04-24 --output outputs\reports\gate_report_2026-04-24.md

# List persisted entry decisions
bullstrangle --db data\bullstrangle.db list-entry-decisions
bullstrangle --db data\bullstrangle.db list-entry-decisions --newsletter-date 2026-04-24
```

### Exit Monitoring (Exit Engine)

```powershell
# Evaluate exit triggers for one layer (layer_id from cycle_layers table)
bullstrangle --db data\bullstrangle.db evaluate-exit --layer-id 42

# Evaluate all active positions (with live prices)
bullstrangle --db data\bullstrangle.db evaluate-exit-batch

# Evaluate without live price fetch (faster)
bullstrangle --db data\bullstrangle.db evaluate-exit-batch --no-persist

# Full exit monitoring report (small portfolio, live prices)
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small

# Full exit monitoring report (large portfolio, saved to file)
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type large --output outputs\reports\exit_report_large.md

# Exit report without live prices (offline mode)
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --no-price

# List persisted exit decisions
bullstrangle --db data\bullstrangle.db list-exit-decisions
```

### Position Book & Backtest

```powershell
# Seed paper-trade positions for one newsletter (small portfolio)
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type small

# Seed large portfolio
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type large

# Resolve outcomes for one week (fetches yfinance close at expiration)
bullstrangle --db data\bullstrangle.db resolve-outcomes 2026-04-24

# Auto-resolve all expired active positions
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type small
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type large

# Run full backtest (seed + resolve all approved newsletters)
bullstrangle --db data\bullstrangle.db backtest-all --portfolio-type small
bullstrangle --db data\bullstrangle.db backtest-all --portfolio-type large

# Equity curve + performance summary (printed)
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type small
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type large

# Full backtest report with equity curve (saved to file)
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type small --output outputs\reports\backtest_small.md
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type large --output outputs\reports\backtest_large.md
```

### Weekend Decisions (v1 engine — legacy)

```powershell
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-27 --output outputs\reports\weekend_decisions_2026-04-24.md
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-27 --json
```

---

## One-Time Or Reset Setup

Initialize or migrate the DB:

```powershell
bullstrangle --db data\bullstrangle.db init-db
```

Ingest all newsletter PDFs:

```powershell
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
```

Force replace one existing newsletter:

```powershell
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\some.pdf --force
```

Force replace matching dates during directory ingest:

```powershell
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters --force
```

---

## OS Workbook Workflow (Market Hours)

1. Open `data\os_uploads\BullStrangle_OS_Live_YYYY-MM-DD.xlsx` in Excel.
2. Make sure the Option Samurai add-in is enabled.
3. Refresh / recalculate the workbook.
4. Save the workbook.
5. Ingest from `data\os_uploads`:

```powershell
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28
```

The command returns `run_id`, `row_count`, `populated_live_value_count`, `status`.
If Excel did not save cached formula values, open the workbook, refresh, save again, and re-ingest.

---

## Positions Ingestion

After updating `data\positions\positions.csv`:

```powershell
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
```

Stores one import run in `position_import_runs`, one row per account/symbol in `account_positions`, and one symbol-level awareness row in `symbol_position_rollups`.

Bull Strangle readiness requires 100 shares in one account. Shares split across accounts do not qualify.

---

## Quick DB Inspection

Check row counts across key tables:

```powershell
python -c "
import sqlite3, sys
conn = sqlite3.connect('data/bullstrangle.db')
tables = [
    'newsletters', 'watchlist_entries', 'short_list_entries',
    'earnings_calendar', 'os_evaluation_runs', 'os_evaluation_rows',
    'os_weekly_symbol_aggregates', 'strategy_rule_catalog',
    'entry_decisions', 'exit_decisions',
    'cycle_layers', 'position_books',
]
for t in tables:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:<35} {n}')
"
```

Check cycle layer status:

```powershell
python -c "
import sqlite3
conn = sqlite3.connect('data/bullstrangle.db')
rows = conn.execute(
    'SELECT portfolio_type, status, COUNT(*) as n FROM cycle_layers '
    'WHERE account_id = ? GROUP BY portfolio_type, status ORDER BY portfolio_type, status',
    ('paper_trade',)
).fetchall()
for r in rows:
    print(r[0], r[1], r[2])
"
```

---

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

`BULLSTRANGLE_DATA_DIR` sets the base data folder. The server derives:
- DB path: `{DATA_DIR}/bullstrangle.db`
- Newsletter PDF dir: `{DATA_DIR}/newsletters`
- Generated workbook output: `{DATA_DIR}/../outputs/workbooks`

`BULLSTRANGLE_DB` may still override the DB path explicitly. When both are set, `BULLSTRANGLE_DB` wins for the database path only.

---

## Test Commands

Run all tests:

```powershell
pytest -q
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

Current expected result: **81 passed**

---

## References

- `references/BullStrangle_Dry_Run_Runbook.md` — step-by-step operator runbook
- `references/Claude_Prompts_BullStrangle.md` — ready-to-use Claude Desktop prompts
- `references/BullStrangle_Implementation_Plan_v3.md` — phase tracker
- `references/master_document_rule_inventory.md` — all 47 strategy rules
