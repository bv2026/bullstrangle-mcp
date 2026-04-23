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

## Documentation

- [Workflow Architecture](references/BullStrangle_MCP_Workflow_Architecture.md)
- [Implementation Guide](references/BullStrangle_Implementation_Guide.md)
- [Decision Logic Design](references/BullStrangle_Decision_Logic_Design.md)
- [Master Document Implementation Plan](references/BullStrangle_Master_Document_Implementation_Plan.md)
- [Dry Run Runbook](references/BullStrangle_Dry_Run_Runbook.md)
- [Claude Prompts](references/Claude_Prompts_BullStrangle.md)
- [Usage Guide](references/BullStrangle_Usage_Guide.md)

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
bullstrangle --db data\bullstrangle.db os-selectors 2026-04-17
bullstrangle --db data\bullstrangle.db prepare-os-workbook 2026-04-17
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-17 --output-dir outputs\os_workbooks
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
- `ingest_positions`
- `list_strategy_rules`
- `report_os_run`
- `aggregate_os_week`
- `generate_weekend_decisions`

Ingestion safety:

- Newsletter re-ingestion is now protected by default.
- If a publication date already exists, `ingest-pdf` and `ingest-dir` will fail that item unless `--force` is supplied.
- `ingest-dir` now continues past bad PDFs and reports per-file errors instead of aborting the whole batch.

## Module Architecture

```
mcp_server.py     MCP stdio server — thin wrappers only, no logic
cli.py            PowerShell-friendly CLI — same tool functions as MCP
tools.py          Anti-corruption layer — parameter coercion and db_path defaults
ingestion.py      PDF parsing and fact storage (stores data, no business rules)
decisions.py      Business rule evaluation — weekly summary, scoring, weekend decisions
                  compute_weekly_summary() and calculate_consecutive_weeks() live here
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
