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
- Generated reports: `outputs/reports/YYYY-MM-DD`

Recommended operator rule:

- never overwrite the generated template in `outputs/workbooks`
- the workbook is auto-copied to `data/os_uploads` on generation — open it there, refresh, and save in place

## End-to-End Operator Flow

Two inputs feed the system in parallel — the weekly newsletter PDF and the broker positions export. Both land in the DB and are consumed together by the weekend decision engine.

```
WEEKLY (Sunday night / Monday)
──────────────────────────────────────────────────────────────

data/newsletters/newsletter.pdf
        │
        │  weekend-setup YYYY-MM-DD --pdf <path>
        │  (or: ingest-pdf → generate-os-workbook separately)
        ▼
  bullstrangle.db
  (watchlist, market env, short list, deep analysis)
        │
        │  auto-generates workbook + copies to os_uploads
        ▼
data/os_uploads/BullStrangle_OS_Live_YYYY-MM-DD.xlsx     ← operator working copy

        │  gate-report + weekly-action-plan
        ▼
outputs/reports/action_plan_YYYY-MM-DD.md                ← gate summary, positions, DCA list


DAILY (market hours, Mon–Fri)
──────────────────────────────────────────────────────────────

data/os_uploads/BullStrangle_OS_Live_YYYY-MM-DD.xlsx
        │
        │  open in Excel → enable Option Samurai add-in
        │  → refresh formulas → save
        │
        │  daily-ingest YYYY-MM-DD --trading-date YYYY-MM-DD
        │  (auto-stale-recovery if DB was rebuilt)
        ▼
  bullstrangle.db                             outputs/reports/os_run_N_YYYY-MM-DD.md
  (os_evaluation_runs, os_evaluation_rows)

        │  daily-brief (morning)
        ▼
  exit alerts + open positions + gate status  ← printed to console or saved


ONCE PER WEEK (before weekend decisions)
──────────────────────────────────────────────────────────────

data/positions/positions.csv          ← export from broker
        │
        │  ingest-positions
        ▼
  bullstrangle.db
  (account_positions, symbol_position_rollups)
  Answers: shares per account, which symbols have ≥100 shares
           in one account (bull strangle ready), DCA target account


WEEKEND (Saturday / Sunday)
──────────────────────────────────────────────────────────────

  bullstrangle.db
  (all of the above combined)
        │
        │  aggregate-os-week          ← roll up daily OS runs
        │  generate-weekend-decisions ← score + action per symbol
        ▼
outputs/reports/YYYY-MM-DD/
  os_week_YYYY-MM-DD.md              ← deviations summary
  weekend_decisions_YYYY-MM-DD.md    ← BULL_STRANGLE / DCA / WATCH / SKIP
```

**How positions feeds decisions:**

| Position fact | Decision impact |
|---|---|
| One account has ≥ 100 shares | Symbol eligible for stock-backed `BULL_STRANGLE` |
| Shares split across accounts | Not bull-strangle ready — routes to `DCA` instead |
| Shares in target account | DCA output: which account to buy in, how many shares to 100 |

## Documentation

### Current (v3)

- [**Architecture Spec v3**](references/BullStrangle_Architecture_Spec_v3.md) — rolling cycle model, gate-based decisions, OS as execution data source
- [**Implementation Guide v2**](references/BullStrangle_Implementation_Guide_v2.md) — what changes, phase plan, new modules, testing
- [**Implementation Plan v3**](references/BullStrangle_Implementation_Plan_v3.md) — what exists vs what to build, 8-phase order, critical path
- [**Master Document Rule Inventory**](references/master_document_rule_inventory.md) — 43 rules extracted from Master Document v8; seed data for `strategy_rule_catalog`

### Operator Guides

- [Usage Guide](references/BullStrangle_Usage_Guide.md)
- [Dry Run Runbook](references/BullStrangle_Dry_Run_Runbook.md)
- [Claude Prompts](references/Claude_Prompts_BullStrangle.md) — 63 ready-to-use prompts for Claude Desktop

### Historical / Reference

- [Architecture Spec v1.1](references/BullStrangle_Newsletter_MCP_Architecture_Spec_v1.1_JSONB.md) — superseded by v3
- [System Architecture v2](references/BullStrangle_SystemArchitecture_v2.md) — superseded by v3
- [Workflow Architecture](references/BullStrangle_MCP_Workflow_Architecture.md)
- [Implementation Guide v1](references/BullStrangle_Implementation_Guide.md) — superseded by v2
- [Decision Logic Design](references/BullStrangle_Decision_Logic_Design.md) — superseded by v3 gate engine
- [Master Document Implementation Plan](references/BullStrangle_Master_Document_Implementation_Plan.md)
- [Gap Analysis (2026-04-26)](references/gap_analysis_spec_vs_impl_2026-04-26.md)

## Implemented Extraction

- `Watch List with Option Price`: symbol, description, price, IV, sector, strikes, option bid/ask prices, return percentages.
- `The Short List(s)`: large and small portfolio symbol membership, linked back to watchlist rows when available.
- `Stock Market Weekly Recap`: full source section text.
- `Market Environment Awareness`: SPX, VIX, breadth, 200-DMA, component scores, hybrid score, regime, position/cash factors.
- `Strategy Overview Core Elements` and `Trade Management Suggestions`: stored as versioned reference sections and seeded strategy rules.

## CLI

Full CLI reference is in [`references/BullStrangle_Dry_Run_Runbook.md`](references/BullStrangle_Dry_Run_Runbook.md).
Quick reference:

```powershell
# Setup
bullstrangle --db data\bullstrangle.db init-db
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
bullstrangle --db data\bullstrangle.db list-newsletters

# OS workbook
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-24 --output-dir outputs\workbooks
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24

# Rule catalog
bullstrangle --db data\bullstrangle.db list-rule-catalog --area exit
bullstrangle --db data\bullstrangle.db get-rule GATE-SS-001

# Gate validation (entry engine)
bullstrangle --db data\bullstrangle.db evaluate-newsletter 2026-04-24
bullstrangle --db data\bullstrangle.db gate-report 2026-04-24 --output outputs\reports\gate_report_2026-04-24.md
bullstrangle --db data\bullstrangle.db list-entry-decisions --newsletter-date 2026-04-24

# Exit monitoring
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type small
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --output outputs\reports\exit_report_small.md

# Backtest & performance
bullstrangle --db data\bullstrangle.db backtest-all --portfolio-type small
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type small
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type small --output outputs\reports\backtest_small.md

# Workflow commands (preferred)
bullstrangle --db data\bullstrangle.db weekend-setup 2026-04-24 --pdf data\newsletters\newsletter.pdf
bullstrangle --db data\bullstrangle.db daily-ingest 2026-04-24 --trading-date 2026-04-28

# Reports
bullstrangle --db data\bullstrangle.db weekly-action-plan 2026-04-24 --output outputs\reports\action_plan_2026-04-24.md
bullstrangle --db data\bullstrangle.db daily-brief

# Positions & decisions
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-27
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

### Report generation tools *(added 2026-04-26; updated Phase 7)*

- `generate_weekly_action_plan` — 10-section Sunday action plan: market status, criteria table, DCA list, strangle eligibility, watchlist, WL Favorites deep dives, **gate validation summary (pass/watch/skip + Short List alignment %)**, **active position table (DTE, strikes, credit, capital)**, action items, reminders, workflow, appendix
- `generate_daily_brief` — morning monitoring brief: market env, **active positions with DTE + capital at risk**, **exit alerts (🚨/⚠️/👀 grouped by urgency)**, **gate status for latest newsletter**
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

- `generate_weekend_decisions` — produce weekend Bull Strangle and DCA decision outputs (v1 legacy engine)
- `list_strategy_rules` — inspect strategy/rule rows, including tunable decision thresholds
- `list_rule_catalog` — list all 47 v3 Master Document rules; filter by area (stock_selection, earnings, exit…) or type (hard_gate, hard_rule, optional_overlay…)
- `get_rule` — fetch a single rule by rule_id with parsed parameters dict (e.g. `GATE-SS-005` → `min_earnings_clear_days: 45`)

### Gate validation tools — entry engine v3 *(added 2026-04-26)*

- `evaluate_entry` — evaluate all 9 gates for one symbol against one newsletter
- `evaluate_newsletter` — evaluate all 9 gates for every watchlist symbol in a newsletter week
- `validate_all_newsletters` — evaluate gates across all ingested newsletters (full history validation)
- `generate_entry_validation_report` — generate gate pass/fail report with Short List alignment stats
- `list_entry_decisions` — list persisted gate decisions; filterable by newsletter date

### Exit monitoring tools — exit engine v3 *(added 2026-04-26)*

- `evaluate_exit` — evaluate all exit triggers for one active cycle layer by layer_id
- `evaluate_exit_batch` — evaluate exit triggers for all ACTIVE cycle layers with live prices
- `generate_exit_report` — markdown exit monitoring report grouped by urgency (IMMEDIATE / THIS_WEEK / ROUTINE); auto-resolves expired positions first
- `list_exit_decisions` — list persisted exit decisions

### Position book & backtest tools *(added 2026-04-26)*

- `seed_cycle_layers` — seed paper-trade cycle_layers from Short List for one newsletter week
- `resolve_cycle_outcomes` — fetch yfinance closing prices at expiration and compute P&L
- `auto_resolve_expired` — find and resolve all ACTIVE layers whose expiration date has passed
- `backtest_all` — seed + resolve all approved newsletter weeks in one call
- `get_portfolio_performance` — week-by-week equity curve with cumulative P&L, return %, and drawdown
- `generate_backtest_report` — full markdown backtest report with per-symbol tables and equity curve

### Workflow tools *(added Phase W)*

- `weekend_setup` — Sunday in one call: ingest PDF (optional) → generate OS workbook → auto-copy to `data/os_uploads`
- `daily_ingest` — daily in one call: find workbook in `data/os_uploads` → ingest (with stale-workbook auto-recovery) → generate OS run report to `outputs/reports`

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
                  Phase W commands: weekend-setup, daily-ingest
                  Phase 7 commands: weekly-action-plan, daily-brief
tools.py          Anti-corruption layer — parameter coercion and db_path defaults
                  Phase W: weekend_setup_tool, daily_ingest_tool
ingestion.py      PDF parsing and fact storage (stores data, no business rules)
                  insert_earnings_calendar() populates earnings_calendar on every ingest
decisions.py      Business rule evaluation — weekly summary, scoring, weekend decisions
                  compute_weekly_summary() and calculate_consecutive_weeks() live here
reports.py        Report generation — weekly action plan, daily brief, report history
                  Phase 7: gate validation summary + active positions + exit alerts wired in
os_workbooks.py   Option Samurai Excel workbook generation
os_ingestion.py   Refreshed workbook ingestion and deviation recording
os_reports.py     Daily OS run reports (read-only)
os_weekly.py      Weekly symbol aggregation across daily OS runs
positions.py      Position CSV ingestion and account rollups
database.py       Schema (authoritative SCHEMA_SQL), versioned migrations, connect()
                  Migrations: m001 decision/position cols, m002 reports+earnings,
                              m003 v3 cycle model (5 new tables), m004 portfolio_type col
rule_catalog.py   Rule catalog loader — seeds strategy_rule_catalog with 47 rules
                  get_rule(), get_gate_rules(), list_rule_catalog()
entry_engine.py   Gate evaluator — all 9 gates per symbol per newsletter week
                  EntryDecision + GateResult dataclasses; persists to entry_decisions
                  evaluate_entry(), evaluate_newsletter(), validate_all_newsletters()
exit_engine.py    Exit trigger evaluator — 6 triggers in priority order
                  ExitDecision dataclass; urgency tiers; auto-resolve integration
                  evaluate_exit(), evaluate_exit_batch(), generate_exit_report()
position_book.py  Paper-trade backtest engine + equity curve tracking
                  seed_from_short_list(), resolve_outcomes(), backtest_all()
                  auto_resolve_expired(), get_portfolio_performance()
                  generate_backtest_report()
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

- Unit: selector rounding, ingestion safety (force flag), DB WAL/index checks, position ingestion, parser fixtures (`parse_watchlist_option_prices`, `parse_market_environment`), strategy-context builder (`_build_strategy_context`), migration idempotency (`_m003_v3_cycle_model`), earnings calendar wiring (`insert_earnings_calendar`), earnings date parsing (`_parse_earnings_date`), rule catalog seeding/idempotency/filtering (`rule_catalog.py`). No PDF required.
- Integration: PDF ingestion, SQLite persistence, OS workbook metadata preparation, OS workbook generation, OS workbook ingestion, daily OS reporting, weekly aggregation, position ingestion, and weekend decision generation. *(requires newsletter PDF in `data/newsletters/`)*
- E2E: launches the MCP server over stdio, lists tools, and calls `calculate_os_selectors`. *(requires newsletter PDF)*

Current expected result:

```text
81 passed
```

## Changelog

### 2026-04-26 — Phase W + Phase 7: workflow commands, stale workbook detection, Phase 7 report updates

**Phase W — Workflow commands:**
`weekend-setup` and `daily-ingest` replace the previous multi-step Sunday/daily sequences with single commands. Stale workbook detection added to `ingest_os_workbook`: when the workbook's embedded `newsletter_id` doesn't match the DB (e.g. after a DB rebuild), the error message names the correct date and the re-generate command; `--regenerate-if-stale` flag silently regenerates and retries. **New tools:** `weekend_setup`, `daily_ingest`. **New CLI commands:** `weekend-setup`, `daily-ingest`, `ingest-os-workbook --regenerate-if-stale`.

**Phase 7 — Report updates:**
`generate_daily_brief` now shows: active positions with DTE + capital at risk, exit alerts (🚨 CLOSE_IMMEDIATELY / ⚠️ EXIT_MONDAY / 👀 REVIEW) grouped by urgency, gate status for the latest newsletter. `generate_weekly_action_plan` now includes: Section 4 gate validation summary (pass/watch/skip, Short List alignment %, gate failure breakdown), Section 5 active position table (DTE, strikes, credit, capital). Dead `decision_batches` / `bull_strangle_decisions` table queries replaced with live `entry_decisions` and `exit_decisions` engine tables. Windows UTF-8 fix in CLI (`sys.stdout.reconfigure`). **New CLI commands:** `weekly-action-plan`, `daily-brief`.

---

### 2026-04-26 — Phases 3–6 + 5b + M4: entry engine, exit engine, backtest, portfolio_type

Full v3 gate-based decision layer built and wired. All engines registered as MCP tools and CLI commands.

**Phase 3 — `entry_engine.py`:** All 9 entry gates implemented (`EntryDecision` + `GateResult` dataclasses). All gates run on every symbol (no short-circuit) for validation visibility; `first_failing_gate` records the production short-circuit point. Persists to `entry_decisions`. Validated: 75–100% alignment with Darren's Short List on deployed weeks. **New tools:** `evaluate_entry`, `evaluate_newsletter`, `validate_all_newsletters`, `generate_entry_validation_report`, `list_entry_decisions`.

**Phase 4 — `exit_engine.py`:** Six exit triggers evaluated in priority order (earnings override, extreme drop, below put strike, expiration, DTE ≤ 7, strike proximity). `generate_exit_report` auto-resolves expired positions before building the report. **New tools:** `evaluate_exit`, `evaluate_exit_batch`, `generate_exit_report`, `list_exit_decisions`.

**Phase 5a — `position_book.py`:** Paper-trade backtest engine. Seeds `cycle_layers` from Short List, resolves outcomes via yfinance at expiration, generates equity curve. Small portfolio result: +$434 / +0.76% (25 trades, 52% win rate). **New tools:** `seed_cycle_layers`, `resolve_cycle_outcomes`, `backtest_all`, `generate_backtest_report`.

**Phase 5b — active monitoring:** `auto_resolve_expired` auto-closes past-expiration ACTIVE layers. `get_portfolio_performance` builds week-by-week equity curve with drawdown (denominator = cumulative invested, not peak P&L). **New tools:** `auto_resolve_expired`, `get_portfolio_performance`.

**Migration M4 — `portfolio_type`:** Added `portfolio_type TEXT DEFAULT 'small'` column to `cycle_layers`. All queries updated. Small (+$434/+0.76%) and large (-$38k/-10.75%) portfolios now tracked independently.

**Phase 6 — tool registration:** 18 new MCP tools + CLI commands wired. Total MCP tools: **50**.

---

### 2026-04-26 — Phase 2: rule_catalog.py

New module `rule_catalog.py` seeds `strategy_rule_catalog` with all 47 rules extracted from the Master Document (8 areas, 6 types). Auto-seeds on first MCP/CLI call using `INSERT OR IGNORE` — idempotent.

**New MCP tools:** `list_rule_catalog` (filter by area/type), `get_rule` (fetch one rule with parsed parameters dict). **New CLI commands:** `list-rule-catalog`, `get-rule`.

Total MCP tools: **32** (was 30). Tests: **81 passed** (was 63, +18 rule catalog unit tests).

---

### 2026-04-26 — Phase 1: v3 cycle model schema migration

Added 5 new DB tables (migration 3) that form the backbone of the gate-based v3 cycle model, plus automatic earnings calendar population on every newsletter ingest.

**New DB tables (migration 3):** `strategy_rule_catalog`, `position_books`, `cycle_layers`, `entry_decisions`, `exit_decisions`.

**New ingestion wiring:** `insert_earnings_calendar()` parses `latest_earnings` dates from watchlist rows (M/D/YYYY format) and inserts them into `earnings_calendar` on every `ingest-pdf` / `ingest-dir` run.

**3 new unit tests:** migration idempotency, earnings calendar population after ingest, earnings date format parsing. Total: **63 passed**.

Implementation plan: [BullStrangle Implementation Plan v3](references/BullStrangle_Implementation_Plan_v3.md)

---

### 2026-04-26 — Phase 0: Master Document rule extraction

Extracted all 43 rules, gates, and thresholds from the 187-page Bull Strangle Master Document v8 into a structured inventory. This is the authoritative seed data for `strategy_rule_catalog`.

**Rule inventory:** [Master Document Rule Inventory](references/master_document_rule_inventory.md) — 43 rules across 8 areas (stock_selection, earnings, strike_selection, capital, cycle, exit, market_environment, formula).

---

### 2026-04-26 — Phase A/B gap-fill

Added 14 MCP tools and a new `reports.py` module to close the largest gaps identified in the spec vs. implementation gap analysis (`references/gap_analysis_spec_vs_impl_2026-04-26.md`).

**New tools:** `get_current_environment`, `check_deployment_approval`, `get_watchlist`, `get_dca_candidates`, `get_active_cycles`, `get_eligible_symbols`, `get_deep_analysis`, `get_market_environment_history`, `get_scaling_guidance`, `search_commentary`, `generate_weekly_action_plan`, `generate_daily_brief`, `list_generated_reports`, `get_generated_report`.

**New DB tables (migration 2):** `generated_reports`, `report_subscriptions`, `earnings_calendar`.

Total MCP tools: **30** (was 16). Spec target: 34.

Full gap analysis: [references/gap_analysis_spec_vs_impl_2026-04-26.md](references/gap_analysis_spec_vs_impl_2026-04-26.md)
