# BullStrangle Implementation Plan v3

Date: 2026-04-26
Last updated: 2026-04-26
Status: ACTIVE — Phases 0–6 + 5b complete; Phase 7 next

## Progress

| Phase | Description | Status |
|---|---|---|
| 0 | Master Document rule extraction → `master_document_rule_inventory.md` | ✅ Done (2026-04-26) |
| 1 | Schema migration 3 + earnings calendar wiring | ✅ Done (2026-04-26) |
| 1b | Parser bug fix — 20+ split-ticker PDF artifacts in `normalize_pdf_text` | ✅ Done (2026-04-26) |
| M4 | Schema migration 4 — `portfolio_type` column on `cycle_layers` | ✅ Done (2026-04-26) |
| 2 | `rule_catalog.py` — load and query `strategy_rule_catalog` | ✅ Done (2026-04-26) |
| 3 | `entry_engine.py` — Gates 1–9 evaluation | ✅ Done (2026-04-26) |
| 4 | `exit_engine.py` — exit trigger rules | ✅ Done (2026-04-26) |
| 5a | `position_book.py` — Short List backtest validator with yfinance P&L | ✅ Done (2026-04-26) |
| 5b | Active portfolio monitoring — live mark-to-market, auto-resolve, equity curve, portfolio_type separation | ✅ Done (2026-04-26) |
| 5c | `position_book.py` — full live trading layer lifecycle + broker sync | 🔲 Pending |
| 6 | Tool registration (18 new MCP tools + CLI) | ✅ Done (2026-04-26) |
| 7 | Report updates (active cycle stack, Gate results in daily brief / weekly plan) | 🔲 Next |
| 8 | v1 score engine deprecation | 🔲 Pending |

---

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
| `decision_batches` | ⚠️ Superseded | v1 score engine output — deprecate after Phase 8 |
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
| `database.py` | ✅ Migrations 3 + 4 added — `strategy_rule_catalog`, `position_books`, `cycle_layers`, `entry_decisions`, `exit_decisions`, `portfolio_type` column |
| `ingestion.py` | ✅ Earnings wiring added (Phase 1) — `insert_earnings_calendar()` + `_parse_earnings_date()` |
| `os_workbooks.py` | ✅ Keep |
| `os_ingestion.py` | ✅ Keep |
| `os_reports.py` | ✅ Keep |
| `os_weekly.py` | ✅ Keep |
| `positions.py` | ✅ Keep |
| `decisions.py` | ⚠️ Partial keep — `compute_weekly_summary()` stays; v1 score functions deprecated in Phase 8 |
| `reports.py` | ✅ Keep — update in Phase 7 |
| `tools.py` | ✅ Updated — 18 new tool wrappers added (Phase 6) |
| `cli.py` | ✅ Updated — 18 new CLI commands added (Phase 6) |
| `mcp_server.py` | ✅ Updated — 18 new tools registered (Phase 6) |

#### New modules built

| Module | Phase | Status |
|---|---|---|
| `rule_catalog.py` | 2 | ✅ Done — 47 rules seeded, `get_rule` / `list_rule_catalog` |
| `entry_engine.py` | 3 | ✅ Done — Gates 1–9, `EntryDecision` + `GateResult`, persisted to `entry_decisions` |
| `exit_engine.py` | 4 | ✅ Done — 6 triggers, `ExitDecision`, urgency tiers, `generate_exit_report` |
| `position_book.py` | 5a/5b | ✅ Done — backtest engine, yfinance resolve, equity curve, auto-resolve, portfolio_type separation |

---

### Phase Detail

#### Phase 0 — Master Document Rule Inventory ✅ DONE

**Deliverable:** `references/master_document_rule_inventory.md`

Read `references/Bull Strangle Master Document - Version 8.pdf` cover to cover. For every rule, gate, threshold, and management guideline, recorded:

- `rule_id` — e.g. `GATE-001`, `EXPIRY-002`, `EXIT-MGT-003`
- `rule_area` — stock_selection / market_environment / entry / exit / position_sizing
- `rule_type` — hard_gate / soft_gate / guideline
- `source_section` — exact PDF section heading and page
- `description` — plain English
- `parameters_json` — numeric thresholds, comparators, units
- `data_column_mapping` — which DB column or OS field provides the value

---

#### Phase 1 — Schema Migration + Earnings Wiring ✅ DONE

**Commit:** `0fe61dc` — 2026-04-26

**`src/bullstrangle_mcp/database.py`** — `_m003_v3_cycle_model` added to `_MIGRATIONS` as version 3. Creates all 5 new tables additively. No existing table altered.

**`src/bullstrangle_mcp/ingestion.py`** — `insert_earnings_calendar()` + `_parse_earnings_date()` parse watchlist `latest_earnings` dates (M/D/YYYY format) into `earnings_calendar` on every ingest. Gate 5 (no earnings during holding period) now has data to check.

**Tests added:** `test_m003_migration_is_idempotent`, `test_earnings_calendar_populated_after_ingest`, `test_parse_earnings_date_handles_formats`. Suite: **63 passed**.

---

#### Phase 1b — Parser Bug Fix ✅ DONE

**Commit:** `73f28ce` — 2026-04-26

**`src/bullstrangle_mcp/ingestion.py`** — Added 27 entries to `normalize_pdf_text()` correcting split-ticker PDF artifacts where PyPDF inserts a space inside multi-letter tickers (e.g. `C RML` → `CRML`, `TEC K` → `TECK`). Cleared the previously broken `TICKER_DESCRIPTION_CORRECTIONS` dict.

**Tickers corrected:** CRML, CDE, CELH, CLF, COMM, CNC, CNK, CNQ, COPX, CORZ, CPRI, CRSP, CXW, FCEL, FCX, GOLD (Barrick Mining), MCHP, NCLH, SCHW, TECK — 20 symbols across 18 newsletters.

**Impact:** All 18 newsletters re-ingested with `--force`. Zero suspicious-ticker warnings. Backtest result corrected from −5.50% (dominated by bogus Citigroup/wrong-company price lookups) to +0.58% on 25 closed trades.

---

#### Migration M4 — portfolio_type column ✅ DONE

**Commit:** `3b52a64` — 2026-04-26

**`src/bullstrangle_mcp/database.py`** — `_m004_cycle_layers_portfolio_type` adds `portfolio_type TEXT DEFAULT 'small'` column to `cycle_layers`. Backfills existing rows to `'small'`.

All queries in `position_book.py`, `exit_engine.py`, `tools.py`, `mcp_server.py`, and `cli.py` updated to filter by `portfolio_type`. Idempotency check in `seed_from_short_list` updated to include `portfolio_type` so small and large runs each maintain independent rows.

---

#### Phase 2 — Rule Catalog Module ✅ DONE

**Commit:** `1fe4a3f` — 2026-04-26

**`src/bullstrangle_mcp/rule_catalog.py`** — `RuleDefinition` dataclass; `load_rule_catalog()` seeds `strategy_rule_catalog` with 47 rules using `INSERT OR IGNORE` (idempotent); `get_rule()`, `get_gate_rules()`, `list_rule_catalog()`.

**New MCP tools:** `list_rule_catalog`, `get_rule`. **New CLI commands:** `list-rule-catalog`, `get-rule`.

**Tests added:** 18 new unit tests in `test_unit_rule_catalog.py`. Suite: **81 passed**.

---

#### Phase 3 — Entry Engine ✅ DONE

**File:** `src/bullstrangle_mcp/entry_engine.py`

Gate evaluation (all 9 gates run — no short-circuit — for validation visibility; `first_failing_gate` tracks the production short-circuit point):

| Gate | Type | Source |
|---|---|---|
| 1 — Market deployment | Hard | `market_environment.deployment_approved` |
| 2 — IV threshold | Hard | `os_evaluation_rows.iv` vs GATE-002 threshold |
| 3 — Price range | Hard | `os_evaluation_rows.stock_price` vs GATE-003 min/max |
| 4 — Open interest | Hard | `os_evaluation_rows.open_interest` vs GATE-004 threshold |
| 5 — No earnings | Hard | `earnings_calendar` — no event in holding window |
| 6 — Watchlist membership | Hard | `watchlist_entries` for newsletter_id |
| 7 — Position book status | Hard | `position_books` — accumulation complete or new symbol |
| 8 — Weekly deviation | Soft | `os_weekly_symbol_aggregates.worst_abs_stock_price_deviation_pct` and `worst_abs_total_credit_deviation` |
| 9 — Live credit | Soft | `os_evaluation_rows.total_credit` vs GATE-009 minimum |

Key bugs fixed during wiring:
- Gate 8 column names corrected (`worst_abs_stock_price_deviation_pct`, `worst_abs_total_credit_deviation`)
- `_persist_decision` changed from ON CONFLICT upsert to SELECT-then-UPDATE-or-INSERT (SQLite NULL uniqueness prevents upsert when `os_run_id IS NULL`)

**Validation result:** 75–100% alignment between gate decisions and Darren's Short List during deployed weeks (Jan–Feb 2026). Paused weeks (Mar–Apr) correctly show 0% alignment because Gate 1 blocks all symbols.

**New MCP tools:** `evaluate_entry`, `evaluate_newsletter`, `validate_all_newsletters`, `generate_entry_validation_report`, `list_entry_decisions`

---

#### Phase 4 — Exit Engine ✅ DONE

**File:** `src/bullstrangle_mcp/exit_engine.py`

Six triggers evaluated in priority order:

| Trigger | Action |
|---|---|
| Earnings override — earnings during holding period | CLOSE_IMMEDIATELY |
| Extreme drop — stock down > 30% from entry | CLOSE_IMMEDIATELY |
| Drop below put strike | REVIEW |
| Expiration — DTE ≤ 0 | NEEDS_RESOLUTION |
| DTE alert — DTE ≤ 7 | EXIT_MONDAY |
| Strike proximity — stock within 3% of call or put strike | REVIEW |
| No triggers | HOLD |

`generate_exit_report` auto-calls `auto_resolve_expired` before evaluating triggers, so the report always reflects current state.

**New MCP tools:** `evaluate_exit`, `evaluate_exit_batch`, `generate_exit_report`, `list_exit_decisions`

---

#### Phase 5a — Short List Backtest Validator ✅ DONE

**Commit:** `4118fd8` — 2026-04-26

**`src/bullstrangle_mcp/position_book.py`** — Paper-trade backtest engine using Darren's Short List as position source and yfinance for expiration-date price resolution.

Key functions:
- `seed_from_short_list(newsletter_date, db_path, portfolio_type)` — seeds `cycle_layers` from `short_list_entries` joined to `watchlist_entries`; idempotent; checks `deployment_approved`
- `resolve_outcomes(newsletter_date, db_path)` — fetches expiration close price via yfinance; computes P&L for `BOTH_OTM`, `CALL_ASSIGNED`, `PUT_ASSIGNED`
- `backtest_all(db_path, portfolio_type)` — processes all approved newsletter weeks in one shot
- `generate_backtest_report(db_path, portfolio_type)` — week-by-week markdown + equity curve

**New MCP tools:** `seed_cycle_layers`, `resolve_cycle_outcomes`, `backtest_all`, `generate_backtest_report`

---

#### Phase 5b — Active Portfolio Monitoring ✅ DONE

**Commit:** `3b52a64` — 2026-04-26

| Item | Status |
|---|---|
| Live mark-to-market via yfinance | ✅ Done — `exit_engine._fetch_current_price()` |
| Auto-resolve expired ACTIVE layers | ✅ Done — `auto_resolve_expired()`, integrated into `generate_exit_report` |
| Weekly P&L equity curve + drawdown | ✅ Done — `get_portfolio_performance()`, appended to `generate_backtest_report` |
| `portfolio_type` column + query isolation | ✅ Done — migration M4, all queries updated |
| Small vs large portfolio comparison | ✅ Validated — small +$434/+0.76%, large -$38k/-10.75% |
| Assignment risk alerts (stock near strike) | 🔲 Deferred |
| Dashboard / persistent monitoring UI | 🔲 Deferred |

**New MCP tools:** `auto_resolve_expired`, `get_portfolio_performance`

**Drawdown calculation:** Denominator is `cumulative_invested` (total capital deployed), not `peak_pnl`, to avoid >100% artefacts when cumulative P&L swings from positive to negative.

---

#### Phase 5c — Full Live Trading Layer Lifecycle 🔲 PENDING

Requires Phase 3 entry engine + real broker positions. Cannot start until live trades exist.

```
sync_from_positions(import_run_id, db_path)
  → upsert position_books from symbol_position_rollups
  → set bull_strangle_ready = True when one account has >= 100 shares

open_cycle_layer(book_id, newsletter_id, os_run_id, strikes, premiums, db_path) -> layer_id
close_cycle_layer(layer_id, actual_action, pnl, db_path)
get_book(symbol, account_id, db_path) -> PositionBook
list_books(db_path, status_filter) -> list[PositionBook]
get_layers(book_id, db_path) -> list[CycleLayer]
```

**New tools:** `list_position_books`, `get_position_book`, `get_cycle_layers`, `open_cycle_layer`, `close_cycle_layer`, `confirm_entry`

---

#### Phase 6 — Tool Registration ✅ DONE

All new engines wired into `tools.py`, `mcp_server.py`, and `cli.py`.

**Total new MCP tools added:** 18
- Entry engine (5): `evaluate_entry`, `evaluate_newsletter`, `validate_all_newsletters`, `generate_entry_validation_report`, `list_entry_decisions`
- Exit engine (4): `evaluate_exit`, `evaluate_exit_batch`, `generate_exit_report`, `list_exit_decisions`
- Position book (4): `seed_cycle_layers`, `resolve_cycle_outcomes`, `backtest_all`, `generate_backtest_report`
- Monitoring (2): `auto_resolve_expired`, `get_portfolio_performance`
- Rule catalog (2): `list_rule_catalog`, `get_rule` (registered in Phase 2)
- Existing + new CLI commands: `evaluate-entry`, `evaluate-newsletter`, `validate-all`, `gate-report`, `list-entry-decisions`, `evaluate-exit`, `evaluate-exit-batch`, `exit-report`, `list-exit-decisions`, `auto-resolve`, `portfolio-performance`, `backtest-report` + `--portfolio-type` flag throughout

---

#### Phase 7 — Report Updates 🔲 NEXT

**File:** `src/bullstrangle_mcp/reports.py`

Update `generate_weekly_action_plan()`:
- Section: Active cycle stack — all ACTIVE layers with days-to-expiry, strikes, current credit
- Section: Expiring this week — layers where DTE ≤ 7
- Section: Gate validation summary — which symbols passed/failed and why

Update `generate_daily_brief()`:
- Gate 9 status per symbol — live credit vs threshold, pass/fail
- Layers needing attention — exit triggers fired (EXIT_MONDAY, REVIEW, CLOSE_IMMEDIATELY)
- Open position summary — count, capital at risk, nearest expiration

---

#### Phase 8 — Deprecate v1 Score Engine 🔲 PENDING

**File:** `src/bullstrangle_mcp/decisions.py`

Remove: `_build_strategy_context()`, `_score_bull_strangle()`, `_score_dca()`, `_select_action()`.

Keep: `compute_weekly_summary()`, `calculate_consecutive_weeks()` — these feed Gate 1 (2-week consecutive confirmation).

**Tables:** `decision_batches`, `bull_strangle_decisions`, `dca_decisions` — leave in schema for historical data, no longer written to.

---

### Summary Counts

| Category | Existing | To Build | Built |
|---|---|---|---|
| DB tables | 24 | 5 + 1 col | 5 tables + portfolio_type col ✅ |
| Source modules | 12 | 4 | 4 ✅ (`rule_catalog.py`, `entry_engine.py`, `exit_engine.py`, `position_book.py`) |
| MCP tools | 30 | 18 new | 18 ✅ |
| Reference docs | 9 | 1 (rule inventory) | 1 ✅ |
| Parser bug fixes | — | — | 20 tickers corrected ✅ |

### Remaining Work

| Item | Phase | Effort |
|---|---|---|
| Inject active cycle stack into weekly action plan | 7 | Medium |
| Inject gate results + exit alerts into daily brief | 7 | Medium |
| `sync_from_positions` → `position_books` book sync | 5c | Medium (needs live broker data) |
| Assignment risk alerts (stock near strike) | 5b deferred | Small |
| Remove v1 score functions from `decisions.py` | 8 | Small |
| Dashboard / monitoring UI | 5b deferred | Large |

---

### Critical Path

```
Master Document PDF (Phase 0)          ✅
        |
schema migration + earnings wiring (Phase 1)  ✅
        |
rule_catalog.py (Phase 2)              ✅
        |
entry_engine.py — Gates 1-9 (Phase 3) ✅
        |
exit_engine.py (Phase 4)              ✅
        |
position_book.py (Phase 5a/5b)        ✅
        |
tool wrappers + CLI (Phase 6)          ✅
        |
report updates (Phase 7)              <- NEXT
        |
v1 score engine deprecation (Phase 8)
        |
live trading lifecycle (Phase 5c)     <- needs live broker positions
```
