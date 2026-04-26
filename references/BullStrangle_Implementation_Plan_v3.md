# BullStrangle Implementation Plan v3

Date: 2026-04-26
Status: ACTIVE

## Overview

Architecture spec v3 and Implementation Guide v2 are written. No v3 code exists yet. This document defines what exists in the v1 baseline, what needs to be built, and the strict implementation order.

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
| `earnings_calendar` | ⚠️ Exists/empty | Never populated — wire in Phase 1 |

#### Source modules (12)

| Module | Status |
|---|---|
| `database.py` | ✅ Keep — add migration 3 in Phase 1 |
| `ingestion.py` | ✅ Keep — add earnings wiring in Phase 1 |
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

#### Phase 0 — Master Document Rule Inventory ⛔ BLOCKER

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

#### Phase 1 — Schema Migration + Earnings Wiring

**File:** `src/bullstrangle_mcp/database.py`

Add `_m003_v3_cycle_model` to `_MIGRATIONS`. Creates all 5 new tables. The migration must be additive — no existing table is altered.

**File:** `src/bullstrangle_mcp/ingestion.py`

Wire earnings date parsing from PDF → `INSERT OR IGNORE INTO earnings_calendar`. Gate 5 (no earnings during holding period) cannot function without this data.

**Test:** One new unit test — migration idempotency. One integration test — earnings rows appear after PDF ingestion.

---

#### Phase 2 — Rule Catalog Module

**File:** `src/bullstrangle_mcp/rule_catalog.py`

```
load_rule_catalog(db_path) → seeds strategy_rule_catalog from master_document_rule_inventory.md
get_gate_rules(db_path, rule_area) → list[RuleDefinition]
get_rule(db_path, rule_id) → RuleDefinition
```

Every `RuleDefinition` carries `rule_id`, `rule_type`, `parameters_json`, `source_section`. No gate in Phase 3 may hard-code a numeric threshold — it must call `get_rule()`.

**New tools:** `list_rule_catalog`, `get_rule`

**Test:** Unit — `load_rule_catalog` seeds rows; `get_rule("GATE-001")` returns expected parameters.

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

| Category | Existing | To Build |
|---|---|---|
| DB tables | 24 | 5 |
| Source modules | 12 | 4 |
| MCP tools | 30 | 15 |
| Reference docs | 9 | 1 (rule inventory) |
| **Total** | **75** | **25** |

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
