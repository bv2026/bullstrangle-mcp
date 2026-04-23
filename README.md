# BullStrangle Newsletter MCP

Local ingestion tooling for Darren Carlat Bull Strangle weekly newsletter PDFs.

The first implemented tool ingests PDFs from `data/newsletters`, extracts the key newsletter sections, and stores normalized rows plus source text in SQLite.

## Quick Start

Use the bundled Codex Python runtime if your system Python does not have the project dependencies installed:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m pip install -e ".[dev,excel]"
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
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
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

Installed server command:

```powershell
C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Scripts\bullstrangle-mcp-server.exe
```

Equivalent module command:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m bullstrangle_mcp.mcp_server
```

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
- `ingest_positions`
- `report_os_run`
- `aggregate_os_week`
- `generate_weekend_decisions`

## Tests

Install test dependencies:

```powershell
$py = 'C:\Users\vsbra\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m pip install -e ".[dev,excel]"
```

Run the full suite:

```powershell
& $py -m pytest -q
```

Run by layer:

```powershell
& $py -m pytest -q -m unit
& $py -m pytest -q -m integration
& $py -m pytest -q -m e2e
```

Current test layers:

- Unit: selector rounding behavior.
- Integration: PDF ingestion, SQLite persistence, OS workbook metadata preparation, OS workbook generation, OS workbook ingestion, daily OS reporting, weekly aggregation, position ingestion, and weekend decision generation.
- E2E: launches the MCP server over stdio, lists tools, and calls `calculate_os_selectors`.
