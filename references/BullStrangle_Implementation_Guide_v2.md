# BullStrangle MCP — Implementation Guide v2

**Date:** 2026-04-26
**Status:** Active — supersedes BullStrangle_Implementation_Guide.md
**See also:** BullStrangle_Architecture_Spec_v3.md

---

## What Changed and Why

The v1 implementation built a solid facts pipeline (PDF → DB → OS workbook → reports) but the decision engine was a placeholder: an invented point-scoring system with no grounding in the Master Document. The rolling weekly cycle — the core of how the strategy actually operates — was not modelled at all.

v2 keeps everything that works and rebuilds the decision layer correctly.

**What works and is kept unchanged:**
- PDF ingestion and newsletter fact storage
- Option Samurai workbook generation and ingestion
- Deviation tracking against newsletter baseline
- Market environment tracking and 2-week rule
- Report generation (weekly action plan, daily brief)
- MCP server infrastructure

**What is replaced:**
- Score-based decision engine → gate-based engine derived from Master Document
- Weekend batch decisions → intraday entry decisions triggered by live OS data
- No position tracking → position books and cycle layers

**What is new:**
- `strategy_rule_catalog` — Master Document rules in DB, referenced by gates
- `position_books` — ongoing per-symbol/account position state
- `cycle_layers` — one row per weekly entry, tracks the rolling stack
- `entry_decisions` — gate-evaluated entry decisions, re-evaluated on each OS refresh
- `exit_decisions` — expiration outcome decisions driven by Master Document exit rules
- `entry_engine.py` — the gate engine
- `exit_engine.py` — expiration logic
- `position_book.py` — book and layer management

---

## Current State (v1 baseline)

**What is implemented and tested (60 tests passing):**
- PDF ingestion, all newsletter sections
- `os_workbooks.py` — workbook generation with auto-copy to os_uploads
- `os_ingestion.py` — refreshed workbook ingestion, deviation storage
- `os_weekly.py` — weekly rollup
- `os_reports.py` — daily deviation report
- `reports.py` — weekly action plan, daily brief
- `decisions.py` — score-based weekend decisions (to be superseded)
- `positions.py` — broker CSV ingestion
- 30 MCP tools active

**What is in the DB but unused by the decision engine:**
- `watchlist_entries.implied_volatility` — stored, not gated on
- `watchlist_entries.total_open_interest` — stored, not gated on
- `watchlist_entries.latest_earnings` / `has_earnings` — stored, not gated on
- `watchlist_entries.sector` — stored, diversification not enforced
- `earnings_calendar` table — exists, never populated

**What is missing entirely:**
- `strategy_rule_catalog` — rules not in DB
- `position_books` — no position book model
- `cycle_layers` — no cycle layer tracking
- `entry_decisions` — no gate-based entry decisions
- `exit_decisions` — no exit decision model
- Gate engine — entry and exit logic not implemented

---

## Phase 0 — Pre-Build (Before Any Code)

**Output:** `references/master_document_rule_inventory.md`

Read `references/Bull Strangle Master Document - Version 8.pdf` and produce a structured rule inventory. This is the foundation for `strategy_rule_catalog` and the gate engine. Do not write code until this exists.

Format for each rule:

```
Rule ID: ENTRY-STOCK-001
Area: stock_selection
Type: hard_gate
Description: Implied volatility must exceed 35%
Source: Master Document v8 — Strategy Overview Core Elements, Pick Quality Stocks
Parameters: {"min_iv": 0.35}
Data: watchlist_entries.implied_volatility, os_evaluation_rows.live_iv
Fail action: SKIP
```

Rule areas to extract:

| Area | Rule IDs | Description |
|---|---|---|
| `market_gate` | ENTRY-MARKET-xxx | Deployment approval, regime, investment % |
| `stock_selection` | ENTRY-STOCK-xxx | IV, price range, OI, technical quality |
| `earnings` | ENTRY-EARNINGS-xxx | No earnings during holding period |
| `position_book` | ENTRY-POSITION-xxx | Max concurrent layers, account rules |
| `account` | ENTRY-ACCOUNT-xxx | Single-account execution, 100-share threshold |
| `credit` | ENTRY-CREDIT-xxx | Minimum credit, deviation thresholds |
| `exit` | EXPIRY-xxx | Called away, assigned, expire worthless, roll |
| `sizing` | SIZE-xxx | 100-share increments, position count per regime |

Acceptance criteria for Phase 0:
- Every gate in the spec (Gates 1–9) maps to at least one rule in the inventory
- Every exit outcome (EXPIRY-001–004) maps to at least one rule
- Each rule has a source reference (page or section in the PDF)
- Inventory reviewed against the newsletter appendix extraction in `strategy_reference_sections`

---

## Phase 1 — Schema Migration

**Output:** New tables in `database.py`, migration 3

Add migration `_m003_v3_cycle_model` to `database.py`.

Tables to add (full DDL in Architecture Spec v3 Section 4.3):
- `strategy_rule_catalog`
- `position_books`
- `cycle_layers`
- `entry_decisions`
- `exit_decisions`

Indexes to add:
- `cycle_layers(book_id)`, `cycle_layers(expiration_date)`, `cycle_layers(status)`
- `entry_decisions(newsletter_id)`, `entry_decisions(symbol)`, `entry_decisions(status)`
- `exit_decisions(layer_id)`, `exit_decisions(expiration_date)`

Seed `strategy_rule_catalog` in the migration from the rule inventory produced in Phase 0.

Also add to newsletter ingestion (in `ingestion.py`):
- Populate `earnings_calendar` from `watchlist_entries.latest_earnings` on ingest
  (symbol, earnings_date, source='newsletter', confirmed=0)

Acceptance criteria:
- `& $py -m compileall -q src` passes
- `& $py -m pytest -q` passes (all 52 passing tests still pass)
- `init-db` runs migration 3 cleanly on fresh DB
- `strategy_rule_catalog` seeded with all rules from Phase 0 inventory
- `earnings_calendar` populated when newsletter is ingested

---

## Phase 2 — Rule Catalog Module

**Output:** `src/bullstrangle_mcp/rule_catalog.py`

New module that loads rule definitions from `strategy_rule_catalog` and exposes them to the gate engine.

```python
def load_rule_catalog(db_path) -> dict[str, RuleDefinition]:
    """Load all active rules from strategy_rule_catalog.
    Returns dict keyed by rule_id."""

def get_gate_rules(area: str, db_path) -> list[RuleDefinition]:
    """Load rules for a specific area (e.g. 'stock_selection')."""

def get_rule(rule_id: str, db_path) -> RuleDefinition:
    """Load one rule by ID."""
```

`RuleDefinition` is a simple dataclass:
```python
@dataclass
class RuleDefinition:
    rule_id: str
    rule_area: str
    rule_type: str          # 'hard_gate' | 'filter' | 'guideline'
    rule_description: str
    source_document: str
    source_section: str
    parameters: dict        # parsed from parameters_json
    is_active: bool
```

Add MCP tool: `list_rule_catalog(area=None)` and `get_rule(rule_id)`.

Acceptance criteria:
- All rules loaded correctly from DB
- `list_rule_catalog` tool returns all rules with source references
- Parameters parsed correctly for numeric thresholds

---

## Phase 3 — Entry Gate Engine

**Output:** `src/bullstrangle_mcp/entry_engine.py`

The core of the v3 redesign. Implements gates 1–9 from the spec.

### Module interface

```python
def evaluate_entry_gates(
    symbol: str,
    newsletter_id: int,
    os_run_id: int | None,
    account_id: str | None,
    db_path: str,
) -> EntryDecision:
    """Run all entry gates for a symbol.
    Returns EntryDecision with full gate results."""

def evaluate_all_candidates(
    newsletter_id: int,
    os_run_id: int | None,
    db_path: str,
) -> list[EntryDecision]:
    """Run entry gates for every symbol on the watchlist.
    Called Sunday (gates 1-8) and on each OS refresh (gate 9)."""
```

### Gate implementation pattern

Each gate is a function:
```python
def _gate_implied_volatility(
    symbol: str,
    newsletter_id: int,
    os_run_id: int | None,
    rule: RuleDefinition,
    conn: sqlite3.Connection,
) -> GateResult:
    min_iv = rule.parameters["min_iv"]
    # prefer live IV from OS if available
    live_iv = _get_live_iv(symbol, os_run_id, conn) if os_run_id else None
    nl_iv = _get_nl_iv(symbol, newsletter_id, conn)
    iv = live_iv or nl_iv
    passed = iv is not None and iv > min_iv
    return GateResult(
        gate_id="GATE-3",
        rule_id=rule.rule_id,
        passed=passed,
        value=iv,
        threshold=min_iv,
        unit="implied_volatility",
        source="os_evaluation_rows" if live_iv else "watchlist_entries",
        reason=f"IV {iv:.0%} {'≥' if passed else '<'} minimum {min_iv:.0%}" if iv else "IV not available",
    )
```

### EntryDecision dataclass

```python
@dataclass
class EntryDecision:
    symbol: str
    newsletter_id: int
    os_run_id: int | None
    account_id: str | None
    decision_type: str          # BULL_STRANGLE | ACCUMULATE | WATCH | SKIP
    gates: list[GateResult]
    first_failing_gate: str | None
    live_stock_price: float | None
    live_total_credit: float | None
    live_iv: float | None
    nl_call_strike: float | None
    nl_put_strike: float | None
    nl_total_credit: float | None
    account_shares: int | None
    shares_to_100: int | None
```

### Persistence

`evaluate_entry_gates` writes to `entry_decisions` after each evaluation. If a pending decision already exists for the same `(newsletter_id, symbol, account_id)`, it is updated in place (Gate 9 re-evaluations update the same row).

### Key design rules

- Gate 9 (live credit) is the only soft gate. All others are hard gates.
- Gates are evaluated in order. First hard gate failure → SKIP immediately.
- Gate 9 failure → WATCH (not SKIP). Will be re-evaluated on next OS refresh.
- Account selection (Gate 8) uses `position_books` to determine target account. If no book exists, create one with 0 shares.
- `os_run_id = None` means evaluate offline gates only (Gates 1–8). Used on Sunday when market is closed.

Acceptance criteria:
- Unit tests for each gate in isolation (no PDF or OS required)
- Integration test: full gate run against a real newsletter + OS snapshot
- Gate 9 WATCH → EXECUTE flow tested end to end
- Every decision written to `entry_decisions` with complete `gates_json`

---

## Phase 4 — Exit Gate Engine

**Output:** `src/bullstrangle_mcp/exit_engine.py`

Implements exit outcome logic for expiring cycle layers.

### Module interface

```python
def evaluate_exit_gates(
    layer_id: int,
    db_path: str,
) -> ExitDecision:
    """Determine recommended exit action for an expiring layer.
    Applies Master Document exit rules."""

def list_expiring_layers(
    expiration_date: str,
    db_path: str,
) -> list[dict]:
    """Return all cycle_layers expiring on or before the given date."""
```

### Exit rule evaluation

```python
def _evaluate_outcome(layer: dict, conn) -> tuple[str, list[str]]:
    """
    Determine the exit outcome based on what the market did.
    The operator inputs the actual outcome; this function
    maps it to the Master Document rule and recommended next action.
    """
    # EXPIRY-001: both expired worthless
    # EXPIRY-002: call assigned (stock called away)
    # EXPIRY-003: put assigned (stock assigned to account)
    # EXPIRY-004: early close
```

### Outcome confirmation flow

```
1. evaluate_exit_gates() → ExitDecision (recommended_action, rule_citations)
2. Display to operator in daily brief / exit report
3. Operator confirms actual outcome via confirm_exit_outcome()
4. update cycle_layers.status
5. update position_books.total_shares if shares changed
6. if EXPIRE_WORTHLESS_CONTINUE → flag symbol for next week's entry evaluation
```

Acceptance criteria:
- Each EXPIRY outcome maps to correct Master Document rule citation
- Position book shares updated correctly after assignment
- CALLED_AWAY reduces position book shares to 0 for that account
- EXPIRE_WORTHLESS does not change share count

---

## Phase 5 — Position Book Module

**Output:** `src/bullstrangle_mcp/position_book.py`

Manages the position book and cycle layer lifecycle.

```python
def get_or_create_book(symbol: str, account_id: str, db_path: str) -> dict:
    """Get existing position book or create one with 0 shares."""

def update_book_shares(book_id: int, shares_delta: int, db_path: str) -> dict:
    """Update total_shares and recalculate bull_strangle_ready flag."""

def create_cycle_layer(
    book_id: int,
    newsletter_id: int,
    os_run_id: int,
    entry_data: dict,
    db_path: str,
) -> dict:
    """Create a new open cycle layer after operator confirms fill."""

def update_layer_status(
    layer_id: int,
    status: str,
    exit_notes: str | None,
    db_path: str,
) -> dict:
    """Update cycle layer status after expiration outcome is confirmed."""

def get_active_layers(symbol: str | None, account_id: str | None, db_path: str) -> list[dict]:
    """Return all open cycle layers, optionally filtered."""

def get_expiring_layers(expiration_date: str, db_path: str) -> list[dict]:
    """Return layers expiring on or before the given date."""
```

### Sync from positions CSV

When `ingest-positions` runs, sync `position_books` from `symbol_position_rollups`:
- For each row in `symbol_position_rollups`, upsert `position_books`
- `bull_strangle_ready` = 1 when max_account_quantity >= 100
- Do not overwrite `cycle_layers` or `status` — those are managed separately

Acceptance criteria:
- Creating a layer with 100 shares sets `bull_strangle_ready = 1`
- CALLED_AWAY exit sets shares to 0 and `bull_strangle_ready = 0`
- ASSIGNED exit adds shares from the assignment (puts exercised)
- `get_active_layers` returns correctly filtered results

---

## Phase 6 — New MCP Tools and CLI Commands

**Output:** updates to `tools.py`, `mcp_server.py`, `cli.py`

### New tool functions in `tools.py`

```python
def evaluate_entry_gates_tool(symbol, newsletter_date, trading_date=None, account_id=None, db_path=...) -> dict
def evaluate_all_candidates_tool(newsletter_date, trading_date=None, db_path=...) -> dict
def list_entry_decisions_tool(newsletter_date, status=None, db_path=...) -> dict
def get_entry_decision_tool(decision_id, db_path=...) -> dict
def confirm_entry_execution_tool(decision_id, call_strike, call_premium, put_strike, put_premium, stock_price, account_id, db_path=...) -> dict

def evaluate_exit_gates_tool(layer_id, db_path=...) -> dict
def list_expiring_layers_tool(expiration_date, db_path=...) -> dict
def list_exit_decisions_tool(expiration_date, db_path=...) -> dict
def confirm_exit_outcome_tool(exit_decision_id, actual_action, outcome_notes, db_path=...) -> dict

def get_position_book_tool(symbol, account_id, db_path=...) -> dict
def list_position_books_tool(status=None, db_path=...) -> dict
def list_active_cycle_layers_tool(symbol=None, account_id=None, db_path=...) -> dict
def get_cycle_layer_tool(layer_id, db_path=...) -> dict

def list_rule_catalog_tool(area=None, db_path=...) -> dict
def get_rule_tool(rule_id, db_path=...) -> dict
```

### New CLI commands

```powershell
# Entry decisions
bullstrangle --db data\bullstrangle.db evaluate-candidates 2026-04-28
bullstrangle --db data\bullstrangle.db evaluate-candidates 2026-04-28 --trading-date 2026-04-28
bullstrangle --db data\bullstrangle.db list-entry-decisions 2026-04-28
bullstrangle --db data\bullstrangle.db list-entry-decisions 2026-04-28 --status pending

# Exit decisions
bullstrangle --db data\bullstrangle.db list-expiring-layers --expiration-date 2026-05-02
bullstrangle --db data\bullstrangle.db evaluate-exits --expiration-date 2026-05-02

# Position books
bullstrangle --db data\bullstrangle.db list-books
bullstrangle --db data\bullstrangle.db list-books --status active
bullstrangle --db data\bullstrangle.db show-book NTAP schwab-ira
bullstrangle --db data\bullstrangle.db list-layers
bullstrangle --db data\bullstrangle.db list-layers --status open

# Rule catalog
bullstrangle --db data\bullstrangle.db list-rules
bullstrangle --db data\bullstrangle.db list-rules --area stock_selection
```

Acceptance criteria:
- All new tools registered in `mcp_server.py`
- All new CLI commands parse and call correct tool functions
- E2E test: MCP server starts, lists all tools including new ones

---

## Phase 7 — Report Updates

**Output:** updates to `reports.py`

### Weekly action plan additions

The weekly action plan report (`generate_weekly_action_plan`) should add:

```
Section: Active Cycle Stack
  For each symbol with open layers:
  - Layer count, next expiration, days to expiry
  - Total credit income across all open layers
  - Alert if any layer expires within 5 days

Section: Expiring This Week
  Layers expiring before next newsletter:
  - Symbol, account, expiration date, strikes, premium received
  - Exit decision recommendation (pre-evaluated)

Section: Entry Candidates This Week
  Symbols that passed gates 1–8 (offline):
  - Symbol, decision type, first failing gate (if any)
  - Pending Gate 9 — will resolve during market hours Mon–Fri

Section: Accumulation Pipeline
  Position books with status=accumulating:
  - Symbol, account, current shares, shares to 100, avg cost basis
```

### Daily brief additions

The daily brief (`generate_daily_brief`) should add:

```
Section: Gate 9 Status (after OS ingestion)
  For each pending entry_decision:
  - Symbol, live credit vs newsletter credit, deviation
  - WATCH (not yet executable) or EXECUTE (credit acceptable)

Section: Expiring Soon
  Layers expiring within 7 days:
  - Days to expiry, strikes, exit decision recommendation
```

---

## Phase 8 — Deprecation

Once the v3 gate engine is operational and producing `entry_decisions`:

1. Mark `generate_weekend_decisions` as deprecated in the MCP server docstring
2. Retain `bull_strangle_decisions` and `dca_decisions` tables (historical record)
3. Remove `_build_strategy_context`, `_build_bull_decision`, `_build_dca_decision` from `decisions.py`
4. Keep `compute_weekly_summary` — it is still correct (2-week rule, deployment_approved)
5. Update README and all docs to remove references to weekend batch decisions

---

## Testing Requirements

### Unit Tests (no PDF, no OS required)

- `test_unit_entry_gates.py` — each gate function in isolation
  - Gate 1: market approved / not approved
  - Gate 3: IV above / below threshold
  - Gate 4: price in range / out of range
  - Gate 6: earnings inside / outside holding period
  - Gate 8: shares < 100 / >= 100
  - Gate 9: credit positive / negative / deviation exceeded
- `test_unit_exit_engine.py` — each EXPIRY outcome
  - EXPIRE_WORTHLESS does not change shares
  - CALLED_AWAY sets shares to 0
  - ASSIGNED adds shares
- `test_unit_position_book.py` — book and layer lifecycle

### Integration Tests (requires newsletter PDF)

- `test_integration_entry_cycle.py`
  - Ingest newsletter → evaluate candidates → all gates 1–8 run
  - Ingest OS workbook → Gate 9 re-evaluated → WATCH or EXECUTE
  - Confirm execution → cycle layer created
- `test_integration_exit_cycle.py`
  - Create test layer → evaluate exits → confirm outcome → book updated

### E2E Tests

- `test_e2e_mcp_server.py` — extend to call new tools via stdio MCP

---

## Canonical File Locations

```
data/
  newsletters/          ← inbound PDFs
  os_uploads/           ← auto-populated on workbook generation
  positions/            ← positions CSV (export from broker)
  bullstrangle.db       ← SQLite DB

outputs/
  workbooks/            ← generated OS workbook templates
  reports/YYYY-MM-DD/   ← generated Markdown reports

references/
  Bull Strangle Master Document - Version 8.pdf   ← strategy authority
  master_document_rule_inventory.md               ← Phase 0 output (to be created)
  BullStrangle_Architecture_Spec_v3.md            ← this system's spec
  BullStrangle_Implementation_Guide_v2.md         ← this document
  BullStrangle_Usage_Guide.md                     ← operator how-to
  BullStrangle_Dry_Run_Runbook.md                 ← step-by-step runbook
  Claude_Prompts_BullStrangle.md                  ← ready-to-use Claude prompts
```

---

## Known Deferred Work

The following items are tracked but not in scope for v2 implementation:

- Automated broker order placement
- Live broker position reconciliation (currently CSV-based)
- Intraday price alerts and Gate 9 auto-recheck
- Multi-account optimization for DCA target selection
- Tax-lot tracking for accumulated positions
- Sector diversification enforcement (max N positions per sector)
- Performance analytics (win rate, P&L by symbol/sector/regime)
- Cloud deployment (Phase C from v2.0 design doc)

---

*Document version 2.0 — 2026-04-26*
*Supersedes: BullStrangle_Implementation_Guide.md*
*See also: BullStrangle_Architecture_Spec_v3.md*
