# BullStrangle MCP / Schwab MCP Handoff

Date: 2026-05-02

Scope: architecture, workflow, dependency review, current project state, and next-session TODOs for `bullstrangle-mcp` with `schwab-mcp-file` as the adjacent broker/market-data MCP.

## Executive Summary

BullStrangle MCP and Schwab MCP are separate local MCP projects. There is no direct Python import dependency, shared package dependency, or shared database between them today.

The dependency is architectural/workflow-level:

- BullStrangle MCP owns the Bull Strangle newsletter workflow, Option Samurai workbook workflow, rule/gate/exit engines, reports, and its own SQLite database.
- Schwab MCP owns read-only Schwab market/account access for the SmartSpreads futures workflow: REST quotes/account endpoints, streaming quotes, TOS CSV parsing, and its own SQLite mark/trade-log database.
- Claude Desktop can orchestrate both MCPs because both are configured as local MCP servers.
- BullStrangle's live trading Phase 5c can use Schwab MCP as a future broker/account data source, but today's BullStrangle broker bridge is still CSV-based through `ingest-positions`.

The practical conclusion: keep the systems decoupled. For Phase 5c, either continue using broker CSV as the BullStrangle canonical input or introduce a narrow read-only adapter that converts Schwab account/position output into BullStrangle's existing `account_positions`, `symbol_position_rollups`, `position_books`, and `cycle_layers` model.

## Verified Repo State

### BullStrangle MCP

- Path: `C:\work\bullstrangle-mcp`
- Branch: `main`
- Local state: clean, tracking `origin/main`
- HEAD: `05d8fb7`
- Last known test result this session: `81 passed`
- Last known compile check this session: `python -m compileall -q src` passed
- Key current docs:
  - `README.md`
  - `references/BullStrangle_Implementation_Plan_v3.md`
  - `references/BullStrangle_Usage_Guide.md`
  - `references/BullStrangle_Architecture_Spec_v3.md`

### Schwab MCP File

- Path: `C:\work\schwab-mcp-file`
- Branch: `main`
- HEAD: `aa49e24`
- Local state: clean tracked files, with two untracked local files:
  - `config/tos-screenshot.png`
  - `scripts/refresh_token.bat`
- Last known test result this session: `93 passed, 1 warning`
- Warning: `websockets.legacy` deprecation warning in tests; not a functional failure.

## Active Runtime Configuration

The current Claude Desktop configuration registers both MCPs.

BullStrangle MCP:

- Uses installed entry point: `bullstrangle-mcp-server.exe`
- Uses `BULLSTRANGLE_DB=C:\work\bullstrangle-mcp\data\bullstrangle.db`
- The code now supports deriving default data paths from `BULLSTRANGLE_DB.parent` when `BULLSTRANGLE_DATA_DIR` is absent.

Schwab MCP:

- Runs `python -m schwab_mcp.server`
- Uses `PYTHONPATH=C:\work\schwab-mcp-file\src`
- Uses Schwab OAuth credentials from environment variables. Do not put secrets in docs.
- Uses `SCHWAB_WATCHLIST_CONFIG=C:\work\SmartSpreads\published\watchlist.yaml`
- Uses `SCHWAB_DB_PATH=C:\work\schwab-mcp-file\config\smartspreads.db`
- Uses `SCHWAB_TOS_STATEMENT_PATH=C:\work\schwab-mcp-file\config\tos-statement.csv`
- Uses `SCHWAB_TOKEN_PATH=C:\Users\vsbra\.schwab\token.json`
- Uses dashboard port `8766`

## BullStrangle MCP Architecture

Primary role: local decision intelligence and workflow automation for the Bull Strangle newsletter process.

Core dependencies:

- Python 3.11+
- `mcp`
- `openpyxl`
- `pypdf`
- `yfinance`
- SQLite database at `data\bullstrangle.db`

Main workflow:

1. Newsletter PDF lands in `data\newsletters`.
2. `weekend-setup <newsletter_date> --pdf <path>` ingests the PDF, stores facts, creates watchlist entries, and generates the Option Samurai workbook.
3. Operator refreshes the workbook in Excel with the Option Samurai add-in and saves it under `data\os_uploads`.
4. `daily-ingest <newsletter_date> --trading-date <date>` ingests refreshed workbook rows, detects stale workbook/DB mismatches, and writes the OS run report.
5. `weekly-action-plan` and `daily-brief` produce operational reports from live engine tables.
6. `ingest-positions` imports broker positions from CSV into BullStrangle tables.
7. Entry, exit, and position-book engines evaluate gates, exits, paper/live cycle state, and reports.

Important modules:

- `database.py`: schema and migrations. Treat as the source of truth.
- `ingestion.py`: PDF parsing, newsletter facts, earnings calendar, parser quality reports.
- `os_workbooks.py`: Option Samurai workbook generation.
- `os_ingestion.py`: refreshed workbook ingestion, stale workbook handling, row validation.
- `positions.py`: broker CSV position import and symbol rollups.
- `entry_engine.py`: v3 nine-gate entry logic.
- `exit_engine.py`: exit-trigger evaluation and auto-resolve for expired active layers.
- `position_book.py`: paper/backtest/active cycle-layer state and performance.
- `rule_catalog.py`: seeded v3 rule catalog from the Master Document.
- `reports.py`: weekly action plan, daily brief, generated report history.
- `tools.py`: MCP anti-corruption boundary and tool implementations.
- `mcp_server.py`: thin MCP registration layer.
- `cli.py`: PowerShell-friendly CLI, same core tool functions as MCP.
- `decisions.py`: legacy/v1 weekly summary support. Partially deprecated; keep only what feeds Gate 1.

Current architecture status:

- Phase W complete: single-command `weekend-setup` and `daily-ingest`.
- Phase 7 complete: reports are wired to live gate/exit/cycle tables.
- Phase 5b complete: active portfolio monitoring, mark-to-market, auto-resolve, performance, `portfolio_type`.
- Phase 8 partial: v1 DB writes stopped; deprecated functions still present for June cleanup.
- Phase 5c pending: live broker-sync lifecycle, blocked until actual Bull Strangle live trades exist.

## Schwab MCP Architecture

Primary role: read-only broker/market-data layer for the SmartSpreads futures workflow.

Core dependencies:

- Python 3.11+
- `schwab-py`
- `mcp`
- `keyring`
- `pyyaml`
- `pydantic`
- `structlog`
- `python-dotenv`
- `aiosqlite`

Data sources:

- Schwab REST API for quotes, balances, equity positions, and transactions.
- Schwab WebSocket streaming for live futures marks.
- TOS CSV export for futures positions and P&L because Schwab REST does not return futures positions.
- Published SmartSpreads watchlist contract at `C:\work\SmartSpreads\published\watchlist.yaml`.
- Local SQLite database at `config\smartspreads.db` for mark snapshots and trade logs.

Important modules:

- `auth.py`: OAuth/token lifecycle.
- `client.py`: Schwab REST wrapper.
- `streaming.py`: WebSocket `StreamManager`.
- `cache.py`: in-memory quote/bar caches.
- `config.py`: positions/watchlist loaders and published contract validation.
- `tos_parser.py`: TOS CSV parser.
- `db.py`: SQLite snapshots and trade log.
- `dashboard.py`: local dashboard generator.
- `tools\quotes.py`: quote and market-hours tools.
- `tools\spreads.py`: spread/butterfly analytics.
- `tools\positions.py`: futures position and trade-history tools.
- `tools\streaming_tools.py`: live quote/watchlist/bar/status tools.
- `tools\account.py`: balances, account positions, transactions.
- `server.py`: MCP stdio server and dashboard startup.

Current Schwab status:

- SmartSpreads published watchlist loading is live.
- `intermarket` entries are preserved and priced as 2-leg spreads.
- Startup logs watchlist validation state, including stale/fallback warnings.
- `get_watchlist_quotes` returns `watchlist_validation`.
- Remaining design question: whether stale/fallback watchlists should be warnings only or hard failures.

## Dependency / Integration Review

| Area | BullStrangle MCP | Schwab MCP | Current dependency |
|---|---|---|---|
| Code | `src\bullstrangle_mcp` | `src\schwab_mcp` | None |
| Database | `data\bullstrangle.db` | `config\smartspreads.db` | None |
| Primary domain | Bull Strangle equity/options workflow | SmartSpreads futures workflow | None |
| Runtime orchestrator | Claude Desktop MCP | Claude Desktop MCP | Shared operator surface |
| Market data | OS workbook, yfinance, broker CSV | Schwab REST/streaming/TOS CSV | Potential future source |
| Broker positions | CSV import into BullStrangle | Schwab account tools plus TOS futures CSV | Potential Phase 5c adapter |
| Watchlist | BullStrangle newsletter/OS watchlist | SmartSpreads published YAML | Separate workflows |

Design implication:

- Do not make BullStrangle import Schwab code directly.
- Do not make BullStrangle depend on Schwab's SmartSpreads DB.
- If integration is needed, add a small contract boundary: Schwab account output -> BullStrangle position import model.
- Keep BullStrangle reports and rule engines independent from Schwab connection health.
- Treat Schwab as a read-only data source, not a trading/execution system.

## Current BullStrangle TODO

### P1 - Run the next live workflow

When the next Bull Strangle newsletter arrives:

```powershell
bullstrangle --db data\bullstrangle.db weekend-setup YYYY-MM-DD --pdf data\newsletters\newsletter.pdf
```

Then refresh the generated OS workbook in Excel and run:

```powershell
bullstrangle --db data\bullstrangle.db daily-ingest YYYY-MM-DD --trading-date YYYY-MM-DD
bullstrangle --db data\bullstrangle.db weekly-action-plan YYYY-MM-DD
bullstrangle --db data\bullstrangle.db daily-brief YYYY-MM-DD --trading-date YYYY-MM-DD
```

Review:

- Parser quality report.
- OS run report.
- Gate validation status.
- Active positions and exit alerts.
- Any stale workbook warning.

### P1 - Phase 5c live trading lifecycle

Build after real Bull Strangle trades exist in broker.

Add to `position_book.py`:

- `sync_from_positions(import_run_id, db_path)`: upsert `position_books` from `symbol_position_rollups`; mark `bull_strangle_ready` when one account has at least 100 shares.
- `open_cycle_layer(...)`: record a live strangle entry with real account, strikes, premiums, and OS context.
- `close_cycle_layer(...)`: close live layers using broker-confirmed results instead of yfinance auto-resolve.

Add CLI/MCP wrappers as needed.

Preferred first implementation path:

1. Keep `ingest-positions` CSV as the canonical Phase 5c input.
2. Build `sync_from_positions` against existing BullStrangle tables.
3. Only after that is stable, consider a Schwab read-only adapter that produces the same import shape.

### P2 - Phase 8 final cleanup

Remove deprecated v1 scoring remnants from `decisions.py` when safe.

Delete/deprecate:

- `_build_strategy_context()`
- `_score_bull_strangle()`
- `_score_dca()`
- `_select_action()`
- `_upsert_batch()`
- `_insert_bull_decisions()`
- `_insert_dca_decisions()`

Keep:

- `compute_weekly_summary()`
- `calculate_consecutive_weeks()`

Reason: those still feed Gate 1 consecutive-week confirmation.

### P2 - BullStrangle / Schwab bridge decision

Decide whether BullStrangle live broker sync should remain CSV-first or use Schwab MCP account tools.

Recommended: CSV-first for first live cycle, because it is simpler, auditable, and already modeled in BullStrangle. Use Schwab later as an optional data source that generates the same canonical import rows.

### P3 - Schwab workflow TODOs

From Schwab README current status:

- Decide whether stale/fallback watchlists should remain warnings or become hard failures.
- Run the new SmartSpreads weekly pipeline on the live current issue and review validation output.
- Continue Daily review improvements once SmartSpreads adds its first persistence layer.

## Next Session Startup Checklist

Run these first:

```powershell
cd C:\work\bullstrangle-mcp
git status --short --branch
git log -3 --oneline --decorate
pytest -q
```

Then:

```powershell
cd C:\work\schwab-mcp-file
git status --short --branch
git log -3 --oneline --decorate
pytest -q
```

If working on Phase 5c:

```powershell
cd C:\work\bullstrangle-mcp
Select-String -Path references\BullStrangle_Implementation_Plan_v3.md -Pattern "Phase 5c" -Context 2,80
Select-String -Path src\bullstrangle_mcp\position_book.py,src\bullstrangle_mcp\positions.py,src\bullstrangle_mcp\database.py -Pattern "position_books|cycle_layers|symbol_position_rollups|account_positions" -Context 2,3
```

If checking Schwab integration:

```powershell
cd C:\work\schwab-mcp-file
Select-String -Path README.md,src\schwab_mcp\tools\account.py,src\schwab_mcp\tools\positions.py -Pattern "positions|transactions|watchlist_validation|stale|fallback" -Context 2,3
```

## Open Questions

1. For BullStrangle live trades, is broker CSV acceptable as the source of truth for the first production cycle, or should Schwab account data be pulled directly?
2. Do Schwab account tools currently return enough normalized equity/options detail for BullStrangle, or only enough for equities plus futures/TOS CSV workflows?
3. Should BullStrangle reports show Schwab-derived freshness/source metadata if Schwab becomes a data source?
4. Should the Schwab SmartSpreads watchlist stale/fallback state be warning-only or hard fail?

## Risk Notes

- Schwab MCP is read-only by design. Keep it that way.
- Schwab futures positions are TOS CSV-based, not REST-based.
- BullStrangle is equity/options focused; do not assume Schwab's futures-oriented SmartSpreads data contracts fit BullStrangle live cycle layers without an adapter.
- Do not share databases between the projects.
- Do not commit local DBs, tokens, TOS exports, screenshots, or secrets.
- The two untracked Schwab files are local/user files and should be left alone unless explicitly requested.

