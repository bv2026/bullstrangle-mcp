# BullStrangle MCP — Claude Context

## What This Is
**Legacy/superseded** — early ingestion tooling for Darren Carlat Bull Strangle weekly newsletter PDFs using SQLite. This project has been replaced by `C:\work\bullstrangle-platform` which uses PostgreSQL and a full MCP server.

**Do not add new features here.** Use `bullstrangle-platform` for all active development.

## What It Did
- Ingested PDFs from `data/newsletters` into SQLite (`data/bullstrangle.db`)
- Generated option spread workbook templates in `outputs/workbooks`
- CLI entry point: `bullstrangle --db data\bullstrangle.db <command>`

## Canonical Paths (historical)
- Newsletter PDFs: `data/newsletters`
- SQLite DB: `data/bullstrangle.db`
- Positions CSV: `data/positions/positions.csv`
- Generated workbooks: `outputs/workbooks`
- Reports: `outputs/reports/YYYY-MM-DD`

## Active Platform
Use `C:\work\bullstrangle-platform` instead — PostgreSQL, full MCP tools, live Tradier integration, weekly scan, portfolio tracking.
