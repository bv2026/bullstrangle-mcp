# BullStrangle Newsletter MCP

Local ingestion tooling for Darren Carlat Bull Strangle weekly newsletter PDFs.

The first implemented tool ingests PDFs from `data/newsletters`, extracts the key newsletter sections, and stores normalized rows plus source text in SQLite.

## Quick Start

```powershell
pip install -e ".[dev,excel]"
bullstrangle --db data\bullstrangle.db init-db
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
bullstrangle --db data\bullstrangle.db list-newsletters
```

By default the database is written to `data/bullstrangle.db`.

## Canonical Paths

These are the finalized working locations:

- Newsletter PDFs: `data/newsletters`
- SQLite DB: `data/bullstrangle.db`
- Positions CSV: `data/positions/positions.csv`
- Generated OS workbook templates: `outputs/workbooks`
- Refreshed OS workbooks for ingestion: `data/os_uploads`
- Generated reports: `reports/YYYY-MM-DD`

Recommended operator rule:

- never overwrite the generated template in `outputs/workbooks`
- always refresh and save the live Excel copy in `data/os_uploads`

## Documentation

- [Architecture Spec v1.1](references/BullStrangle_Newsletter_MCP_Architecture_Spec_v1.1_JSONB.md) — canonical spec (32 tables, 34 tools)
- [Workflow Architecture](references/BullStrangle_MCP_Workflow_Architecture.md)
- [Implementation Guide](references/BullStrangle_Implementation_Guide.md)
- [Decision Logic Design](references/BullStrangle_Decision_Logic_Design.md)
- [Master Document Implementation Plan](references/BullStrangle_Master_Document_Implementation_Plan.md)
- [Dry Run Runbook](references/BullStrangle_Dry_Run_Runbook.md)
- [Usage Guide](references/BullStrangle_Usage_Guide.md)
- [Claude Prompts](references/Claude_Prompts_BullStrangle.md) — 34 ready-to-use prompts for Claude Desktop
- [Gap Analysis (2026-04-26)](references/gap_analysis_spec_vs_impl_2026-04-26.md) — spec vs. implementation status, remaining TODO

## Implemented Extraction

- `Watch List with Option Price`: symbol, description, price, IV, sector, strikes, option bid/ask prices, return percentages.
- `The Short List(s)`: large and small portfolio symbol membership, linked back to watchlist rows when available.
- `Stock Market Weekly Recap`: full source section text.
- `Market Environment Awareness`: SPX, VIX, breadth, 200-DMA, component scores, hybrid score, regime, position/cash factors.
- `Strategy Overview Core Elements` and `Trade Management Suggestions`: stored as versioned reference sections and seeded strategy rules.

## CLI

```powershell
bullstrangle --db data\bullstrangle.db init-db
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\some.pdf
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\some.pdf --force
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters --force
bullstrangle --db data\bullstrangle.db list-newsletters
bullstrangle --db data\bullstrangle.db show-newsletter 2026-04-17
bullstrangle --db data\bullstrangle.db show-newsletter 34
bullstrangle --db data\bullstrangle.db symbol-history NTAP --newsletter-date 2026-04-17
bullstrangle --db data\bullstrangle.db os-selectors 2026-04-17
bullstrangle --db data\bullstrangle.db prepare-os-workbook 2026-04-17
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-17 --output-dir outputs\workbooks
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-17.xlsx --trading-date 2026-04-22
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
bullstrangle --db data\bullstrangle.db report-os-run 1 --output reports\2026-04-22\os_run_1.md
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-17 --output reports\2026-04-22\os_week_2026-04-17.md
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-17 --json
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-25 --output reports\2026-04-22\weekend_decisions_2026-04-17.md
```

## Claude Desktop MCP

This project includes a stdio MCP server for Claude Desktop.

Installed server command (available after `pip install -e .`):

```powershell
bullstrangle-mcp-server
```

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

## Tool Inventory

### Ingestion tools

- `ingest_newsletter` — ingest one newsletter PDF
- `ingest_newsletter_directory` — ingest a directory of PDFs with per-file status
- `list_newsletters` — list ingested newsletters
- `get_newsletter` — fetch one newsletter by id
- `get_newsletter_by_date` — fetch one newsletter by publication date (YYYY-MM-DD)
- `get_symbol_history` — symbol appearance history across newsletters; new-flag for a given date

### Market intelligence tools *(added 2026-04-26)*

- `get_current_environment` — latest market environment row: hybrid score, VIX, breadth, S&P vs 200-DMA, deployment status
- `check_deployment_approval` — per-criterion pass/fail breakdown, consecutive-week count, recommended action
- `get_market_environment_history` — time-range query over market environment rows
- `get_scaling_guidance` — scaling phase, recommended position count, plain-English guidance

### Watchlist & symbol tools *(added 2026-04-26)*

- `get_watchlist` — full watchlist for a newsletter date with WL Favorites deep analysis embedded
- `get_dca_candidates` — short-list DCA candidates for a newsletter date
- `get_active_cycles` — all open position books (target expiration ≥ today), sorted soonest first
- `get_eligible_symbols` — bull strangle decision rows filtered by APPROVE / WATCH / SKIP
- `get_deep_analysis` — WL Favorites deep-dive JSONB artifacts (technical assessment, proposed trade)

### Search

- `search_commentary` — full-text search (FTS5) over all ingested newsletter commentary sections

### Report generation tools *(added 2026-04-26)*

- `generate_weekly_action_plan` — 10-section Sunday action plan: market status, criteria table, DCA list, strangle eligibility, watchlist, WL Favorites deep dives, action items, reminders, workflow, appendix
- `generate_daily_brief` — morning monitoring brief: market env, active cycles with days-to-expiry, automated alerts
- `list_generated_reports` — list previously generated reports (newest first)
- `get_generated_report` — retrieve full Markdown content of a generated report by id

### OS workbook tools

- `calculate_os_selectors` — calculate newsletter-derived OS selector values
- `prepare_os_workbook` — create/update workbook metadata row
- `generate_os_workbook` — generate the Excel workbook template
- `ingest_os_workbook` — ingest a refreshed live workbook
- `list_os_runs` — list OS runs so run IDs are discoverable
- `report_os_run` — render a daily OS deviation report
- `aggregate_os_week` — aggregate all runs for one newsletter week

### Decision and rules tools

- `generate_weekend_decisions` — produce weekend Bull Strangle and DCA decision outputs
- `list_strategy_rules` — inspect strategy/rule rows, including tunable decision thresholds

### Portfolio tools

- `ingest_positions` — ingest account positions from `data/positions/positions.csv`

### Ingestion safety

- Newsletter re-ingestion is protected by default.
- If a publication date already exists, `ingest-pdf` and `ingest-dir` will fail that item unless `--force` is supplied.
- `ingest-dir` continues past bad PDFs and reports per-file errors instead of aborting the whole batch.

## Module Architecture

```
mcp_server.py     MCP stdio server — thin wrappers only, no logic
cli.py            PowerShell-friendly CLI — same tool functions as MCP
tools.py          Anti-corruption layer — parameter coercion and db_path defaults
ingestion.py      PDF parsing and fact storage (stores data, no business rules)
decisions.py      Business rule evaluation — weekly summary, scoring, weekend decisions
                  compute_weekly_summary() and calculate_consecutive_weeks() live here
reports.py        Report generation — weekly action plan, daily brief, report history
os_workbooks.py   Option Samurai Excel workbook generation
os_ingestion.py   Refreshed workbook ingestion and deviation recording
os_reports.py     Daily OS run reports (read-only)
os_weekly.py      Weekly symbol aggregation across daily OS runs
positions.py      Position CSV ingestion and account rollups
database.py       Schema (authoritative SCHEMA_SQL), versioned migrations, connect()
```

**Key design rules:**
- `ingestion.py` stores facts extracted from PDFs. It does not apply business rules.
- `decisions.py` applies rules to stored facts. Call `compute_weekly_summary()` to re-evaluate decisions without re-ingesting a PDF.
- `database.py` is the single source of truth for schema. Add new columns to `SCHEMA_SQL` and append a numbered migration to `_MIGRATIONS` — never use ad-hoc `ALTER TABLE` elsewhere.
- The database uses WAL mode and a 5-second busy timeout for safe concurrent access.
- Decision thresholds (max deviations, minimum credits) live in the `strategy_rules` table under `rule_category = 'decision_threshold'`. Edit them in the DB and re-run `generate_weekend_decisions` — no code change required. Use `list_strategy_rules` (MCP) or query SQLite directly to inspect current values.
- Set `BULLSTRANGLE_DATA_DIR` to the absolute path of your `data/` folder. All path defaults (`db_path`, `directory`, `output_dir`) resolve from it so the tools work from any working directory. `BULLSTRANGLE_DB` still overrides the DB path explicitly; when it is set without `BULLSTRANGLE_DATA_DIR`, file defaults derive from the DB file's parent directory.

## Tests

Run the full suite:

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

Current test layers:

- Unit: selector rounding, ingestion safety (force flag), DB WAL/index checks, position ingestion, parser fixtures (`parse_watchlist_option_prices`, `parse_market_environment`), strategy-context builder (`_build_strategy_context`). No PDF required.
- Integration: PDF ingestion, SQLite persistence, OS workbook metadata preparation, OS workbook generation, OS workbook ingestion, daily OS reporting, weekly aggregation, position ingestion, and weekend decision generation. *(requires newsletter PDF in `data/newsletters/`)*
- E2E: launches the MCP server over stdio, lists tools, and calls `calculate_os_selectors`. *(requires newsletter PDF)*

Current expected result:

```text
60 passed
```

## Changelog

### 2026-04-26 — Phase A/B gap-fill

Added 14 MCP tools and a new `reports.py` module to close the largest gaps identified in the spec vs. implementation gap analysis (`reports/gap_analysis_spec_vs_impl_2026-04-26.md`).

**New tools:** `get_current_environment`, `check_deployment_approval`, `get_watchlist`, `get_dca_candidates`, `get_active_cycles`, `get_eligible_symbols`, `get_deep_analysis`, `get_market_environment_history`, `get_scaling_guidance`, `search_commentary`, `generate_weekly_action_plan`, `generate_daily_brief`, `list_generated_reports`, `get_generated_report`.

**New DB tables (migration 2):** `generated_reports`, `report_subscriptions`, `earnings_calendar`.

Total MCP tools: **30** (was 16). Spec target: 34.

Full gap analysis: [references/gap_analysis_spec_vs_impl_2026-04-26.md](references/gap_analysis_spec_vs_impl_2026-04-26.md)
