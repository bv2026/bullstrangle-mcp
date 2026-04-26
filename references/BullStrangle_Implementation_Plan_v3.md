# BullStrangle Implementation Plan v3

Date: 2026-04-26
Last updated: 2026-04-26
Status: ACTIVE — Phase 5a complete; Phase 3 next

## Progress

| Phase | Description | Status |
|---|---|---|
| 0 | Master Document rule extraction → `master_document_rule_inventory.md` | ✅ Done (2026-04-26) |
| 1 | Schema migration 3 + earnings calendar wiring | ✅ Done (2026-04-26) |
| 1b | Parser bug fix — 20+ split-ticker PDF artifacts in `normalize_pdf_text` | ✅ Done (2026-04-26) |
| 2 | `rule_catalog.py` — load and query `strategy_rule_catalog` | ✅ Done (2026-04-26) |
| 3 | `entry_engine.py` — Gates 1–9 evaluation | 🔲 Next |
| 4 | `exit_engine.py` — EXPIRY rules | 🔲 Pending |
| 5a | `position_book.py` — Short List backtest validator with yfinance P&L | ✅ Done (2026-04-26) |
| 5b | Active portfolio monitoring — live mark-to-market, alerts, auto-resolve | 🔲 Pending |
| 5c | `position_book.py` — full live trading layer lifecycle + book sync | 🔲 Pending |
| 6 | Tool registration (15 new MCP tools + CLI) | 🔲 Pending |
| 7 | Report updates (cycle stack, Gate 9 status) | 🔲 Pending |
| 8 | v1 score engine deprecation | 🔲 Pending |

## Overview

Architecture spec v3 and Implementation Guide v2 are written. This document defines what exists in the v1 baseline, what needs to be built, and the strict implementation order.

---

### What Exists (v1 baseline — keep unless noted)

#### Database (24 tables)

| Table | Status | Notes |
|---|---|---|
| `newsletters` | ✅ Keep | Core fact store |
| `newsletter_full_text` | ✅ Keep | |
| `watchlist_entries` | ✅ Keep | Immutable newsletter baseline |
| `short_list_entries` | ✅ Keep | |
| `watchlist_deep_analysis` | ✅ Keep | |
| `market_environment` | ✅ Keep | Feeds Gate 1 |
| `weekly_decisions` | ✅ Keep | compute_weekly_summary() output |
| `symbol_history` | ✅ Keep | |
| `strategy_reference_sections` | ✅ Keep | |
| `strategy_rules` | ✅ Keep | Decision thresholds remain tunable |
| `os_workbooks` | ✅ Keep | |
| `os_evaluation_runs` | ✅ Keep | Feeds Gate 9 |
| `os_evaluation_rows` | ✅ Keep | Live credit per symbol |
| `watchlist_deviations` | ✅ Keep | |
| `os_weekly_symbol_aggregates` | ✅ Keep | |
| `decision_batches` | ⚠️ Superseded | v1 score engine output — deprecate after Phase 6 |
| `bull_strangle_decisions` | ⚠️ Superseded | Replaced by `entry_decisions` |
| `dca_decisions` | ⚠️ Superseded | DCA is now accumulation state in `position_books` |
| `position_import_runs` | ✅ Keep | |
| `account_positions` | ✅ Keep | |
| `symbol_position_rollups` | ✅ Keep | Feeds Gate 7 |
| `generated_reports` | ✅ Keep | |
| `report_subscriptions` | ✅ Keep | |
| `earnings_calendar` | ✅ Wired (Phase 1) | Populated by `insert_earnings_calendar()` on every ingest |

#### Source modules (12)

| Module | Status |
|---|---|
| `database.py` | ✅ Migration 3 added (Phase 1) — `strategy_rule_catalog`, `position_books`, `cycle_layers`, `entry_decisions`, `exit_decisions` |
| `ingestion.py` | ✅ Earnings wiring added (Phase 1) — `insert_earnings_calendar()` + `_parse_earnings_date()` |
| `os_workbooks.py` | ✅ Keep |
| `os_ingestion.py` | ✅ Keep |
| `os_reports.py` | ✅ Keep |
| `os_weekly.py` | ✅ Keep |
| `positions.py` | ✅ Keep |
| `decisions.py` | ⚠️ Partial keep — `compute_weekly_summary()` stays; v1 score functions deprecated in Phase 6 |
| `reports.py` | ✅ Keep — update in Phase 7 |
| `tools.py` | ✅ Keep — add new tool wrappers in Phase 6 |
| `cli.py` | ✅ Keep — add new CLI commands in Phase 6 |
| `mcp_server.py` | ✅ Keep — register new tools in Phase 6 |

#### MCP tools (30)

All 30 existing tools are retained. 15 new tools are added in Phase 6.

---

### What Needs to Be Built

#### Database (5 new tables — Phase 1)

| Table | Purpose |
|---|---|
| `strategy_rule_catalog` | Every gate rule with rule_id, source section, parameters |
| `position_books` | Per-symbol/account accumulation and strangle state |
| `cycle_layers` | One row per weekly entry in the rolling 4-layer stack |
| `entry_decisions` | Gate 1–9 evaluation records per symbol per OS run |
| `exit_decisions` | Exit recommendations per layer with rule citations |

#### New modules (4)

| Module | Phase | Purpose |
|---|---|---|
| `rule_catalog.py` | 2 | Load and query `strategy_rule_catalog`; `RuleDefinition` dataclass |
| `entry_engine.py` | 3 | Gates 1–9 evaluation; `EntryDecision` + `GateResult` dataclasses |
| `exit_engine.py` | 4 | EXPIRY-001 through EXPIRY-004; exit recommendation logic |
| `position_book.py` | 5 | Layer lifecycle; book management; sync from positions CSV |

#### New MCP tools (15 — Phase 6)

**Rule catalog (2):** `list_rule_catalog`, `get_rule`

**Entry engine (4):** `evaluate_entry`, `evaluate_entry_batch`, `list_entry_decisions`, `get_entry_decision`

**Exit engine (3):** `evaluate_exit`, `list_exit_decisions`, `get_exit_decision`

**Position books (5):** `list_position_books`, `get_position_book`, `get_cycle_layers`, `open_cycle_layer`, `close_cycle_layer`

**Confirm tools (1):** `confirm_entry` (marks a decision as executed, opens the layer)

#### Wiring gaps (3)

| Gap | Phase | What |
|---|---|---|
| `earnings_calendar` population | 1 | Wire PDF parsing → earnings rows in `ingestion.py` |
| `position_books` sync | 5 | `ingest_positions` → `position_book.sync_from_positions()` |
| Report updates | 7 | Cycle stack + expiring layers + Gate 9 status in weekly plan and daily brief |

---

### Implementation Order

```
Phase 0  ← HARD BLOCKER — nothing in 1+ starts without this
Phase 1  ← schema must exist before any engine code runs
Phase 2  ← rule catalog must exist before entry engine can cite rules
Phase 3  ← entry engine before exit (exit needs layer references)
Phase 4  ← exit engine before position books (exit closes layers)
Phase 5  ← position books after all engines (orchestrates both)
Phase 6  ← tools after all modules (thin wrappers only)
Phase 7  ← reports after tools (read from new tables)
Phase 8  ← deprecation last (keep old engine running during parallel testing)
```

#### Phase 0 — Master Document Rule Inventory ✅ DONE

**Deliverable:** `references/master_document_rule_inventory.md`

Read `references/Bull Strangle Master Document - Version 8.pdf` cover to cover. For every rule, gate, threshold, and management guideline, record:

- `rule_id` — e.g. `GATE-001`, `EXPIRY-002`, `EXIT-MGT-003`
- `rule_area` — stock_selection / market_environment / entry / exit / position_sizing
- `rule_type` — hard_gate / soft_gate / guideline
- `source_section` — exact PDF section heading and page
- `description` — plain English
- `parameters_json` — numeric thresholds, comparators, units
- `data_column_mapping` — which DB column or OS field provides the value

This document becomes the seed data for `strategy_rule_catalog`. No gate in Phase 3 or 4 can be coded without a `rule_id` that traces back to a specific section of the Master Document.

Estimated output: 40–60 rows covering the 9 entry gates and 4 exit rules at minimum.

---

#### Phase 1 — Schema Migration + Earnings Wiring ✅ DONE

**Commit:** `0fe61dc` — 2026-04-26

**`src/bullstrangle_mcp/database.py`** — `_m003_v3_cycle_model` added to `_MIGRATIONS` as version 3. Creates all 5 new tables additively. No existing table altered.

**`src/bullstrangle_mcp/ingestion.py`** — `insert_earnings_calendar()` + `_parse_earnings_date()` parse watchlist `latest_earnings` dates (M/D/YYYY format) into `earnings_calendar` on every ingest. Gate 5 (no earnings during holding period) now has data to check.

**Tests added:** `test_m003_migration_is_idempotent`, `test_earnings_calendar_populated_after_ingest`, `test_parse_earnings_date_handles_formats`. Suite: **63 passed**.

---

#### Phase 2 — Rule Catalog Module ✅ DONE

**Commit:** `1fe4a3f` — 2026-04-26

**`src/bullstrangle_mcp/rule_catalog.py`** — `RuleDefinition` dataclass; `load_rule_catalog()` seeds `strategy_rule_catalog` with 47 rules using `INSERT OR IGNORE` (idempotent); `get_rule()`, `get_gate_rules()`, `list_rule_catalog()` (MCP-shaped, auto-seeds on first call).

**New MCP tools:** `list_rule_catalog` (filter by area/type), `get_rule` (fetch one rule with parsed parameters dict). **New CLI commands:** `list-rule-catalog`, `get-rule`.

**Note:** The inventory `.md` summary said 43 rules; actual section-by-section count is 47 (8+4+8+7+4+8+5+3). Tests are data-driven against `_SEED_RULES`.

**Tests added:** 18 new unit tests in `test_unit_rule_catalog.py`. Suite: **81 passed**.

---

#### Phase 1b — Parser Bug Fix ✅ DONE

**Commit:** `73f28ce` — 2026-04-26

**`src/bullstrangle_mcp/ingestion.py`** — Added 27 entries to `normalize_pdf_text()` correcting split-ticker PDF artifacts where PyPDF inserts a space inside multi-letter tickers (e.g. `C RML` → `CRML`, `TEC K` → `TECK`). Cleared the previously broken `TICKER_DESCRIPTION_CORRECTIONS` dict (it only had one entry and even that was wrong).

**Tickers corrected:** CRML, CDE, CELH, CLF, COMM, CNC, CNK, CNQ, COPX, CORZ, CPRI, CRSP, CXW, FCEL, FCX, GOLD (Barrick Mining), MCHP, NCLH, SCHW, TECK — 20 symbols across 18 newsletters.

**Impact:** All 18 newsletters re-ingested with `--force`. Zero suspicious-ticker warnings. Backtest result corrected from −5.50% (dominated by bogus Citigroup/wrong-company price lookups) to +0.58% on 25 closed trades.

**Important note:** `TEC` in the newsletters is **TECK** (Teck Resources, ~$47–59, Materials sector), NOT TECL (Direxion 3x Semiconductor ETF). Price data confirms this.

---

#### Phase 5a — Short List Backtest Validator ✅ DONE

**Commit:** `4118fd8` — 2026-04-26

**`src/bullstrangle_mcp/position_book.py`** — Paper-trade backtest engine using Darren's Short List (small portfolio) as position source and yfinance for expiration-date price resolution.

Key functions:
- `seed_from_short_list(newsletter_date, db_path, portfolio_type)` — seeds `cycle_layers` from `short_list_entries` joined to `watchlist_entries` for strikes/premiums; idempotent; checks `deployment_approved`
- `resolve_outcomes(newsletter_date, db_path)` — fetches expiration close price via yfinance; computes P&L for three outcomes: `BOTH_OTM`, `CALL_ASSIGNED`, `PUT_ASSIGNED`; updates `cycle_layers` status to `CLOSED`
- `backtest_all(db_path, portfolio_type)` — processes all approved newsletter weeks in one shot
- `generate_backtest_report(db_path, portfolio_type)` — week-by-week markdown table + summary stats

**New MCP tools:** `seed_cycle_layers`, `resolve_cycle_outcomes`, `backtest_all`, `generate_backtest_report`
**New CLI commands:** `seed-cycle-layers`, `resolve-outcomes`, `backtest-all`, `backtest-report`

**Current backtest result (small portfolio, 25 closed trades):**
- Closed: 25 trades, 13 wins (52%), Total P&L +$434, Return +0.58%
- Open: 8 positions still active (5 exp 2026-05-15, 3 exp 2026-05-22)

**`pyproject.toml`** — Added `yfinance>=1.0` dependency.

---

#### Phase 5b — Active Portfolio Monitoring

**Status:** 🔲 Pending

The paper-trade portfolio data is in SQLite but there is no ongoing monitoring layer. The following gaps must be addressed before this can be used as a live tracking tool:

| Gap | Description | Priority |
|---|---|---|
| Live mark-to-market | Open positions show `?` for current price/P&L — need yfinance live quote on demand | High |
| Auto-resolve at expiration | Currently manual — must call `resolve-outcomes` after each expiration date passes; should trigger automatically | High |
| Weekly P&L roll-up | No cumulative equity curve, no drawdown tracking, no week-over-week comparison | Medium |
| Assignment risk alerts | No flag when underlying approaches a strike (e.g. stock within 2% of call or put strike) | Medium |
| Dashboard / monitoring UI | Everything requires MCP tool calls or scripts; no persistent view of the open book | Medium |
| Multi-portfolio support | Currently only `small` portfolio backtest; `large` portfolio tracking not wired | Low |

**Suggested implementation:**
- `get_active_cycles(db_path)` tool — calls yfinance for each open position, returns live P&L, distance-to-strike, days-to-expiry
- Scheduled `resolve_cycle_outcomes` — auto-run daily after market close; close any layer whose `expiration_date <= today` and `status = ACTIVE`
- Equity curve table — append a snapshot row per week to a `portfolio_snapshots` table (weekly return, cumulative return, open positions count)
- Strike proximity warning — in `generate_backtest_report` and `generate_daily_brief`, flag any open layer where `|close_price - strike| / close_price < 0.03`

---

#### Phase 5c — Full Live Trading Layer Lifecycle

**Status:** 🔲 Pending (requires Phase 3 entry engine + real broker positions)

This is the original Phase 5 scope from the spec — live trading flow rather than paper-trade backtest:

```
sync_from_positions(import_run_id, db_path)
  → upsert position_books from symbol_position_rollups
  → set bull_strangle_ready = True when one account has ≥ 100 shares

open_cycle_layer(book_id, newsletter_id, os_run_id, strikes, premiums, db_path) → layer_id
close_cycle_layer(layer_id, actual_action, pnl, db_path)
get_book(symbol, account_id, db_path) → PositionBook
list_books(db_path, status_filter) → list[PositionBook]
get_layers(book_id, db_path) → list[CycleLayer]
```

Cannot start until Phase 3 (entry engine gates) and broker positions CSV wiring are in place.

---

#### Phase 3 — Entry Engine

**File:** `src/bullstrangle_mcp/entry_engine.py`

```
evaluate_entry(symbol, newsletter_id, os_run_id, db_path) → EntryDecision
evaluate_entry_batch(newsletter_id, os_run_id, db_path) → list[EntryDecision]
```

Gate evaluation order (fail fast — first failing gate is recorded, remaining gates skipped):

| Gate | Type | Source |
|---|---|---|
| 1 — Market deployment | Hard | `market_environment.deployment_approved` |
| 2 — IV threshold | Hard | `os_evaluation_rows.iv` vs GATE-002 threshold |
| 3 — Price range | Hard | `os_evaluation_rows.stock_price` vs GATE-003 min/max |
| 4 — Open interest | Hard | `os_evaluation_rows.open_interest` vs GATE-004 threshold |
| 5 — No earnings | Hard | `earnings_calendar` — no event in holding window |
| 6 — Watchlist membership | Hard | `watchlist_entries` for newsletter_id |
| 7 — Position book status | Hard | `position_books` — accumulation complete or new symbol |
| 8 — Weekly deviation | Soft | `os_weekly_symbol_aggregates` — credit and price deviation |
| 9 — Live credit | Soft | `os_evaluation_rows.total_credit` vs GATE-009 minimum |

Each `GateResult` carries `gate_id`, `rule_id`, `passed`, `actual_value`, `threshold_value`, `reason`.

Result persisted to `entry_decisions` with `gates_json`, `first_failing_gate`, `decision_type` (BULL_STRANGLE / ACCUMULATE / WATCH / SKIP).

**New tools:** `evaluate_entry`, `evaluate_entry_batch`, `list_entry_decisions`, `get_entry_decision`

**Test:** Unit — gate short-circuit logic with mock data. Integration — evaluate_entry_batch against real DB after PDF + OS workbook ingestion.

---

#### Phase 4 — Exit Engine

**File:** `src/bullstrangle_mcp/exit_engine.py`

```
evaluate_exit(layer_id, db_path) → ExitDecision
evaluate_exit_batch(db_path) → list[ExitDecision]  # all ACTIVE layers
```

Exit rules evaluated in order:

| Rule ID | Trigger | Action |
|---|---|---|
| EXPIRY-001 | Days to expiration ≤ 7 | Close or roll |
| EXPIRY-002 | Underlying price moved > threshold from call strike | Defensive adjustment |
| EXPIRY-003 | Credit captured ≥ target percentage | Early close |
| EXPIRY-004 | Market regime shifts to Red | Pause or close |

Each `ExitDecision` carries `layer_id`, `recommended_action`, `rule_citations_json`, `trigger_values`. Persisted to `exit_decisions`.

**New tools:** `evaluate_exit`, `list_exit_decisions`, `get_exit_decision`

**Test:** Unit — each rule triggers at correct threshold. Integration — evaluate_exit_batch returns recommendations for seeded active layers.

---

#### Phase 5 — Position Book Module

**File:** `src/bullstrangle_mcp/position_book.py`

```
sync_from_positions(import_run_id, db_path)
  → upsert position_books from symbol_position_rollups
  → set bull_strangle_ready = True when one account has ≥ 100 shares

open_cycle_layer(book_id, newsletter_id, os_run_id, strikes, premiums, db_path) → layer_id
close_cycle_layer(layer_id, actual_action, pnl, db_path)
get_book(symbol, account_id, db_path) → PositionBook
list_books(db_path, status_filter) → list[PositionBook]
get_layers(book_id, db_path) → list[CycleLayer]
```

`sync_from_positions` is called at the end of `ingest_positions_tool()` — no separate tool needed. The sync is automatic after every positions import.

**New tools:** `list_position_books`, `get_position_book`, `get_cycle_layers`, `open_cycle_layer`, `close_cycle_layer`, `confirm_entry`

**Test:** Unit — sync_from_positions creates book with correct bull_strangle_ready flag; split-account scenario correctly sets flag to False. Integration — full flow: ingest positions → sync → list_position_books.

---

#### Phase 6 — Tool Registration

No new logic. Thin wrappers only.

- `tools.py`: add 15 new tool functions following existing pattern
- `mcp_server.py`: register 15 new tools in the tool list and dispatch table
- `cli.py`: add corresponding CLI commands

**Test:** E2E — MCP server `list_tools` returns 45 tools (30 existing + 15 new).

---

#### Phase 7 — Report Updates

**File:** `src/bullstrangle_mcp/reports.py`

Update `generate_weekly_action_plan()`:
- Section: Active cycle stack — all ACTIVE layers with days-to-expiry, strikes, current credit
- Section: Expiring this week — layers where DTE ≤ 7

Update `generate_daily_brief()`:
- Gate 9 status per symbol — live credit vs threshold, pass/fail
- Layers needing attention — EXPIRY-001 or EXPIRY-002 triggered

---

#### Phase 8 — Deprecate v1 Score Engine

**File:** `src/bullstrangle_mcp/decisions.py`

Remove: `_build_strategy_context()`, `_score_bull_strangle()`, `_score_dca()`, `_select_action()`.

Keep: `compute_weekly_summary()`, `calculate_consecutive_weeks()` — these feed Gate 1 (2-week consecutive confirmation).

**Tables:** `decision_batches`, `bull_strangle_decisions`, `dca_decisions` — leave in schema for historical data, no longer written to.

**Test:** Run full test suite. Confirm 0 references to removed functions remain in active code paths.

---

### Summary Counts

| Category | Existing | To Build | Built |
|---|---|---|---|
| DB tables | 24 | 5 | 5 ✅ |
| Source modules | 12 | 4 | 2 ✅ (`rule_catalog.py`, `position_book.py` Phase 5a) |
| MCP tools | 30 | 15 | 6 ✅ (`list_rule_catalog`, `get_rule`, `seed_cycle_layers`, `resolve_cycle_outcomes`, `backtest_all`, `generate_backtest_report`) |
| Reference docs | 9 | 1 (rule inventory) | 1 ✅ |
| Parser bug fixes | — | — | 20 tickers corrected ✅ |
| **Total** | **75** | **25** | **14** |

### Monitoring Gaps Backlog (Phase 5b)

| Item | Status |
|---|---|
| Live mark-to-market for open positions | 🔲 |
| Auto-resolve cycle layers at expiration | 🔲 |
| Weekly P&L roll-up / equity curve | 🔲 |
| Assignment risk alerts (stock near strike) | 🔲 |
| Dashboard / persistent monitoring UI | 🔲 |
| Large portfolio tracking | 🔲 |

---

### Critical Path

```
Master Document PDF (Phase 0)
        ↓
schema migration + earnings wiring (Phase 1)
        ↓
rule_catalog.py — no numeric constants in engine code (Phase 2)
        ↓
entry_engine.py — Gates 1-9 (Phase 3)
        ↓
exit_engine.py — EXPIRY rules (Phase 4)
        ↓
position_book.py — layer state machine (Phase 5)
        ↓
tool wrappers + CLI (Phase 6)
        ↓
report updates (Phase 7)
        ↓
v1 score engine deprecation (Phase 8)
```

Phase 0 is the only true external dependency. Everything after Phase 0 is sequential Python work with no external blockers. Phases 3, 4, and 5 can be unit-tested in isolation with fixture data before the full integration chain exists.
