# Bull Strangle MCP — Architecture Specification v3

**Version:** 3.0
**Date:** 2026-04-26
**Status:** Active — supersedes v1.1 (JSONB) and v2.0 (pre-build design)
**Authors:** Balaji + Claude

---

## Why a v3

v1.1 (April 2026) was written as an implementation target before the strategy was fully understood.
v2.0 (April 2026) was the original design document, marked superseded at build time.

Both documents share the same fundamental flaw: they modelled the system as a **weekly batch decision tool** — one newsletter → one decision run → score every symbol → pick actions. That is the wrong mental model for this strategy.

The actual strategy is a **rolling weekly cycle machine**:
- A new position layer is opened every week
- Up to four overlapping layers are active simultaneously
- Each layer has its own expiration (~28 days out)
- Entry decisions happen during market hours when live option prices are known
- Exit decisions happen at expiration based on what the market did

This document specifies the correct architecture built around that model. Decisions are gate-based, derived directly from the Master Document and newsletter content. No invented scoring weights.

---

## Table of Contents

1. [Strategy Model](#1-strategy-model)
2. [System Principles](#2-system-principles)
3. [Data Sources and Their Roles](#3-data-sources-and-their-roles)
4. [Data Model](#4-data-model)
5. [Decision Engine — Gate Model](#5-decision-engine--gate-model)
6. [The Rolling Cycle Model](#6-the-rolling-cycle-model)
7. [Weekly Operational Rhythm](#7-weekly-operational-rhythm)
8. [MCP Tool Inventory](#8-mcp-tool-inventory)
9. [Module Architecture](#9-module-architecture)
10. [Migration From v1 Implementation](#10-migration-from-v1-implementation)

---

## 1. Strategy Model

### 1.1 What the Strategy Actually Is

The Bull Strangle is a **covered options income strategy** operated as a rolling weekly machine.

Three legs per position:
```
Buy 100 shares of stock           ← capital base
Sell OTM call ~4 weeks out        ← income + upside cap
Sell OTM put ~4 weeks out         ← income + assignment risk
```

New layers are opened every week. At any given time up to four layers are active simultaneously, each with its own expiration date, each generating its own weekly option income.

### 1.2 Stock Selection Criteria

From the Master Document — all criteria must be met at entry:

| Criterion | Rule |
|---|---|
| Technical quality | Technically strong — passes Darren's watchlist curation |
| Implied volatility | IV > 35% |
| Price range | $10 ≤ last price ≤ $120 |
| Liquidity | Open interest > 25,000 contracts |
| Earnings safety | No earnings announced during the holding period |
| Watchlist presence | Symbol on Darren's current weekly watchlist |

### 1.3 Market Environment Gates

From the Master Document — market regime determines whether new layers are opened:

| Regime | Criteria | Investment % | Action |
|---|---|---|---|
| Green | All 4 criteria met for 2 consecutive weeks | 75% | Open new layers |
| Yellow | All 4 criteria met, week 1 only | 50% | Limited new layers |
| Red | Any criterion failing | 0–25% | No new layers |

The 4 criteria:
1. Hybrid score ≥ 0 (weekly SMA composite, Friday close)
2. S&P 500 above its 200-day moving average
3. VIX < 25
4. Breadth > 40% (% of S&P stocks above 50-DMA)

### 1.4 DCA — Accumulation Phase

DCA is not a separate strategy decision type. It is the **accumulation phase** within a position book for a symbol where the account does not yet hold 100 shares.

```
Account < 100 shares → ACCUMULATE (buy shares, no options yet)
Account ≥ 100 shares → BULL STRANGLE eligible (sell call + sell put)
```

DCA targets one specific account. Shares split across multiple accounts do not qualify as strangle-ready.

### 1.5 Exit Rules

From the Master Document — at expiration:

| Outcome | Action |
|---|---|
| Both options expire worthless, stock held | Continue: sell new call and put for next cycle |
| Stock called away (call assigned) | Close naked puts for small debit, or wait for put expiration |
| Stock assigned (put exercised) | Sell all shares; close naked calls for small debit, or wait |
| Early close needed | Close position for net debit if strategy fundamentals change |

---

## 2. System Principles

1. **Decisions follow the document, not invented weights.** Every gate and rule cites a source: Master Document section, newsletter section, or operator-defined threshold with explicit rationale. No `score += 2.0` magic numbers.

2. **Two decision types only: ENTRY and EXIT.** Entry decisions answer "should we open a new layer this week?" Exit decisions answer "what do we do with the layer expiring this Friday?" These are separate workflows with separate timing.

3. **Entry decisions are intraday, not weekend-batch.** The newsletter identifies candidates. Live OS data confirms whether the credit is executable *right now*. Entry triggers during market hours, not Sunday evening.

4. **The newsletter provides the trade thesis. OS provides the execution check.** Darren's strikes, credit estimates, and watchlist curation are the input. Live Option Samurai data validates whether those strikes still carry sufficient premium when you go to execute.

5. **Position books are the core entity.** The system tracks ongoing relationships with symbols across multiple layers and cycles. It is not a stateless weekly batch.

6. **Facts layer is immutable.** Newsletter data, once ingested, is never overwritten. It is the permanent baseline. All OS snapshots are appended, never edited.

7. **Gate failures are auditable.** Every entry and exit decision records which gates passed, which failed, the value at evaluation time, and the rule source. A human operator can read any decision and understand exactly why it landed where it did.

8. **No auto-execution.** The system recommends. The operator executes. Fills are confirmed back into the position book manually.

---

## 3. Data Sources and Their Roles

### Newsletter PDF (weekly, Sunday)

**Role: Trade thesis and universe definition**

- Defines which symbols are in the watchlist this week
- Provides baseline strikes (call, put) at newsletter publication time
- Provides baseline credit estimate at newsletter publication time
- Provides market environment assessment (regime, criteria status)
- Identifies short list (priority candidates) and WL Favorites (highest conviction)
- Earnings dates for all watchlist symbols
- Darren's market narrative and any methodology notes

The newsletter defines *what to trade and why*. It does not define *when to execute* — that is OS's job.

### OS Workbook (daily, market hours)

**Role: Real-time execution data**

- Live stock price at the newsletter strikes
- Live option premium at the newsletter strikes (call bid, put bid, total credit)
- Live IV at time of refresh
- Live open interest
- Deviation from newsletter baseline (price moved? credit compressed?)

The OS workbook answers: *"Is the trade Darren described still executable right now at acceptable credit?"*

It is refreshed 1–2 times per day during market hours. Each refresh is ingested as a timestamped snapshot. Entry decisions reference the most recent OS snapshot, not the newsletter baseline.

### Positions CSV (weekly, from broker)

**Role: Account state for position book management**

- How many shares per symbol per account
- Which accounts are accumulating vs strangle-ready
- Which symbols have ≥ 100 shares in one account (strangle eligible)
- DCA target account selection (account closest to 100 shares)

### Master Document Rules

**Role: Hard gates and exit logic**

- Stock selection criteria (IV, price, OI, earnings)
- Market regime gates
- Exit rules (called away, assigned, expire worthless)
- Account rules (single-account execution)
- Position sizing (100-share increments)

These rules are stored in `strategy_rule_catalog` with source references, and are applied directly by the gate engine — not approximated by invented scoring weights.

---

## 4. Data Model

### 4.1 Design Rules

- One authoritative `SCHEMA_SQL` in `database.py`. All changes via numbered migrations in `_MIGRATIONS`.
- Every fact table is append-only. No row is ever deleted or updated to erase history.
- Only status/outcome columns are updated in place (cycle layer status, position book shares).
- All JSON stored as TEXT, queried with `json_extract()`.
- WAL mode + 5-second busy timeout on all connections.

### 4.2 Retained Tables (unchanged from v1)

```
newsletters                  — one row per newsletter (publication date, target expiration)
newsletter_full_text         — FTS5 virtual table for full-text search
watchlist_entries            — immutable newsletter baseline (symbol, strikes, IV, credit, earnings)
short_list_entries           — short list membership per newsletter
watchlist_deep_analysis      — WL Favorites JSONB artifacts
market_environment           — hybrid score, criteria, regime, deployment approval per newsletter
weekly_decisions             — 2-week confirmation, deployment_approved flag
symbol_history               — which symbols appeared in which newsletters
strategy_reference_sections  — extracted strategy appendix text
strategy_rules               — tunable thresholds (decision_threshold category)
os_workbooks                 — generated workbook metadata
os_evaluation_runs           — one row per OS workbook ingestion (trading date, run stats)
os_evaluation_rows           — one row per symbol per OS run (live price, credit, IV)
watchlist_deviations         — per-symbol deviation from newsletter baseline
os_weekly_symbol_aggregates  — weekly rollup across daily OS runs
position_import_runs         — broker positions import metadata
account_positions            — raw account-level positions rows
symbol_position_rollups      — consolidated symbol-level awareness
generated_reports            — report content log (weekly action plan, daily brief, etc.)
report_subscriptions         — deferred
earnings_calendar            — symbol → earnings_date (populated from OS rows and newsletter)
```

### 4.3 New Tables (v3 additions)

#### `strategy_rule_catalog`

Master Document-backed rule inventory. Every gate in the decision engine references a row here.

```sql
CREATE TABLE strategy_rule_catalog (
    rule_id          TEXT PRIMARY KEY,           -- e.g. ENTRY-STOCK-002
    rule_area        TEXT NOT NULL,              -- market_gate | stock_selection | entry | exit | account
    rule_type        TEXT NOT NULL,              -- hard_gate | filter | guideline
    rule_description TEXT NOT NULL,
    source_document  TEXT NOT NULL,              -- 'master_document_v8' | 'operator'
    source_section   TEXT,                       -- section or page reference
    parameters_json  TEXT,                       -- {"min": 0.35} etc.
    is_active        INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Seeded at `init-db` with all rules extracted from the Master Document.

#### `position_books`

One row per symbol per account. Tracks the ongoing accumulation / strangle relationship.

```sql
CREATE TABLE position_books (
    book_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol               TEXT NOT NULL,
    account_id           TEXT NOT NULL,              -- broker account identifier
    status               TEXT NOT NULL DEFAULT 'accumulating',
                                                     -- accumulating | active | paused | closed
    total_shares         INTEGER NOT NULL DEFAULT 0,
    avg_cost_basis       REAL,
    bull_strangle_ready  INTEGER NOT NULL DEFAULT 0, -- 1 when total_shares >= 100
    first_entry_date     TEXT,
    last_action_date     TEXT,
    notes                TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(symbol, account_id)
);
```

#### `cycle_layers`

One row per weekly entry. Each newsletter week that results in an actual entry creates one layer per symbol per account.

```sql
CREATE TABLE cycle_layers (
    layer_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id              INTEGER NOT NULL REFERENCES position_books(book_id),
    newsletter_id        INTEGER NOT NULL REFERENCES newsletters(newsletter_id),
    os_run_id            INTEGER REFERENCES os_evaluation_runs(run_id),
                                                     -- OS snapshot used at entry decision
    account_id           TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    open_date            TEXT NOT NULL,              -- actual entry date (market day)
    expiration_date      TEXT NOT NULL,              -- option expiration date
    shares_qty           INTEGER NOT NULL DEFAULT 100,
    -- Strikes from newsletter (Darren's recommended structure)
    nl_call_strike       REAL,
    nl_put_strike        REAL,
    nl_total_credit      REAL,                       -- newsletter baseline credit
    -- Actual executed values (filled by operator after execution)
    call_strike          REAL,
    call_premium         REAL,
    put_strike           REAL,
    put_premium          REAL,
    total_credit         REAL,
    stock_entry_price    REAL,
    -- Live OS values at time of entry decision
    live_stock_price     REAL,
    live_total_credit    REAL,
    live_iv              REAL,
    -- Status
    status               TEXT NOT NULL DEFAULT 'pending',
                                                     -- pending | open | expired_worthless
                                                     -- called_away | assigned | rolled | closed_early
    exit_date            TEXT,
    exit_notes           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_cycle_layers_book ON cycle_layers(book_id);
CREATE INDEX idx_cycle_layers_expiration ON cycle_layers(expiration_date);
CREATE INDEX idx_cycle_layers_newsletter ON cycle_layers(newsletter_id);
CREATE INDEX idx_cycle_layers_status ON cycle_layers(status);
```

#### `entry_decisions`

Replaces `bull_strangle_decisions` and `dca_decisions`. One row per symbol per evaluation. Stores the complete gate evaluation result.

```sql
CREATE TABLE entry_decisions (
    decision_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id        INTEGER NOT NULL REFERENCES newsletters(newsletter_id),
    os_run_id            INTEGER REFERENCES os_evaluation_runs(run_id),
                                                     -- OS snapshot evaluated against
    symbol               TEXT NOT NULL,
    account_id           TEXT,                       -- target account when known
    evaluated_at         TEXT NOT NULL,              -- timestamp of evaluation
    decision_type        TEXT NOT NULL,              -- BULL_STRANGLE | ACCUMULATE | WATCH | SKIP
    -- Gate results — one JSON object per gate
    gates_json           TEXT NOT NULL,              -- [{gate_id, rule_id, passed, value, threshold, reason}]
    first_failing_gate   TEXT,                       -- rule_id of first hard gate failure
    -- Live values at evaluation time
    live_stock_price     REAL,
    live_total_credit    REAL,
    live_iv              REAL,
    nl_call_strike       REAL,
    nl_put_strike        REAL,
    nl_total_credit      REAL,
    -- Position context
    account_shares       INTEGER,
    shares_to_100        INTEGER,
    -- Execution window
    valid_until          TEXT,                       -- OS data freshness cutoff
    -- Outcome
    status               TEXT NOT NULL DEFAULT 'pending',
                                                     -- pending | executed | expired | cancelled
    layer_id             INTEGER REFERENCES cycle_layers(layer_id),
                                                     -- linked when executed
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_entry_decisions_newsletter ON entry_decisions(newsletter_id);
CREATE INDEX idx_entry_decisions_symbol ON entry_decisions(symbol);
CREATE INDEX idx_entry_decisions_status ON entry_decisions(status);
```

#### `exit_decisions`

One row per cycle layer at expiration. Records what the recommended exit action is and what was actually done.

```sql
CREATE TABLE exit_decisions (
    exit_decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    layer_id             INTEGER NOT NULL REFERENCES cycle_layers(layer_id),
    expiration_date      TEXT NOT NULL,
    evaluated_at         TEXT NOT NULL,
    -- Recommended action and the rules that drove it
    recommended_action   TEXT NOT NULL,
                                                     -- EXPIRE_WORTHLESS_CONTINUE
                                                     -- CALLED_AWAY_CLOSE_PUTS
                                                     -- ASSIGNED_SELL_SHARES
                                                     -- ROLL_FORWARD
                                                     -- CLOSE_EARLY
    rule_citations_json  TEXT NOT NULL,              -- [{rule_id, description}]
    -- Outcome (filled after operator confirms)
    actual_action        TEXT,
    outcome_notes        TEXT,
    pnl_credit_income    REAL,                       -- total premium received this layer
    pnl_stock_gain_loss  REAL,                       -- stock P&L if shares sold
    status               TEXT NOT NULL DEFAULT 'pending',
                                                     -- pending | completed
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_exit_decisions_layer ON exit_decisions(layer_id);
CREATE INDEX idx_exit_decisions_expiration ON exit_decisions(expiration_date);
```

### 4.4 Table Group Summary

```
FACTS (immutable, append-only)
  newsletters, newsletter_full_text, watchlist_entries, short_list_entries,
  watchlist_deep_analysis, market_environment, weekly_decisions, symbol_history,
  strategy_reference_sections, os_evaluation_runs, os_evaluation_rows,
  watchlist_deviations, os_weekly_symbol_aggregates, position_import_runs,
  account_positions, earnings_calendar

RULES (seeded, operator-editable)
  strategy_rules, strategy_rule_catalog

POSITION BOOK (mutable state)
  position_books, cycle_layers, symbol_position_rollups

DECISIONS (append-only, outcome filled in place)
  entry_decisions, exit_decisions

REPORTS
  generated_reports, report_subscriptions

OS WORKBOOKS
  os_workbooks
```

---

## 5. Decision Engine — Gate Model

### 5.1 Core Principle

The engine evaluates gates in order. Each gate has a rule source reference. The first failing hard gate stops evaluation and the symbol is SKIP. No gates are combined into a composite score. Pass/fail is explicit and auditable.

### 5.2 Entry Gate Sequence

```
GATE 1 — Market Deployment Approval
  Rule: ENTRY-MARKET-001
  Source: Master Document — Market Environment section
  Check: market_environment.deployment_approved = 1
         (all 4 criteria met for 2 consecutive weeks)
  Type: Hard gate
  Fail action: SKIP — market not ready, no new entries regardless of symbol quality

GATE 2 — Symbol on Current Watchlist
  Rule: ENTRY-WATCHLIST-001
  Source: Newsletter watchlist section
  Check: symbol present in watchlist_entries for this newsletter_id
  Type: Hard gate
  Fail action: SKIP — Darren did not include this symbol this week

GATE 3 — Implied Volatility
  Rule: ENTRY-STOCK-001
  Source: Master Document — "Pick Quality Stocks" / IV > 35%
  Check: watchlist_entries.implied_volatility > 0.35
         OR os_evaluation_rows.live_iv > 0.35 (live IV from latest OS run)
  Type: Hard gate
  Fail action: SKIP — IV too low, option premium insufficient

GATE 4 — Price Range
  Rule: ENTRY-STOCK-002
  Source: Master Document — "Pick Quality Stocks" / $10–$120
  Check: 10 <= live_stock_price <= 120
  Type: Hard gate
  Fail action: SKIP — price outside acceptable range

GATE 5 — Open Interest
  Rule: ENTRY-STOCK-003
  Source: Master Document — "Pick Quality Stocks" / OI > 25,000
  Check: watchlist_entries.total_open_interest > 25000
         OR os_evaluation_rows live OI field when available
  Type: Hard gate
  Fail action: SKIP — liquidity insufficient

GATE 6 — Earnings Safety
  Rule: ENTRY-EARNINGS-001
  Source: Master Document — "Earnings not announced during the holding period"
  Check: no row in earnings_calendar where symbol matches AND
         earnings_date BETWEEN open_date AND expiration_date
  Type: Hard gate
  Fail action: SKIP — earnings risk during holding period

GATE 7 — Position Book Check
  Rule: ENTRY-POSITION-001
  Source: Operator / account management
  Check: account does not already have an open cycle_layer for this symbol
         that would exceed the maximum concurrent layers per symbol
  Type: Hard gate
  Fail action: SKIP — already fully deployed in this symbol this week

GATE 8 — Accumulate vs Full Entry
  Rule: ENTRY-ACCOUNT-001
  Source: Master Document — "Buy stock in 100 share increments"
  Check: position_books.total_shares >= 100 for the target account
  If shares < 100: decision_type = ACCUMULATE (buy shares, no options)
  If shares >= 100: continue to Gate 9

GATE 9 — Live Credit Viability (OS workbook)
  Rule: ENTRY-CREDIT-001
  Source: Master Document — option premium quality
  Check: latest os_evaluation_rows.total_credit > 0
         AND price_deviation within threshold (strategy_rules.bull_strangle_max_price_deviation_pct)
         AND credit_deviation within threshold (strategy_rules.bull_strangle_max_credit_deviation)
  Type: Soft gate — failure → WATCH (not SKIP), retry on next OS refresh
  Fail action: WATCH — credit not yet executable, re-evaluate at next OS refresh
```

### 5.3 Gate Result Record

Every gate evaluation stores:

```json
{
  "gate_id": "GATE-3",
  "rule_id": "ENTRY-STOCK-001",
  "passed": false,
  "value": 0.31,
  "threshold": 0.35,
  "unit": "implied_volatility",
  "source": "watchlist_entries",
  "reason": "IV 31% is below minimum 35%"
}
```

This is stored in `entry_decisions.gates_json`. Any operator or report can reconstruct exactly why a symbol was skipped.

### 5.4 Decision Outcomes

| All gates pass (shares ≥ 100) | → BULL_STRANGLE |
|---|---|
| Gates 1–7 pass, shares < 100 | → ACCUMULATE |
| Gates 1–8 pass, Gate 9 (credit) fails | → WATCH (retry next OS refresh) |
| Any gate 1–7 fails | → SKIP (with first failing gate recorded) |

### 5.5 Exit Gate Logic

Exit decisions are triggered by expiration approaching (typically Thursday evening or Friday close):

```
EXPIRY-001 — Both options expire worthless, shares held
  Action: EXPIRE_WORTHLESS_CONTINUE
  Next: sell new call and put for the following week's expiration
  Rule: "When both options expire and stock is kept, usually continue holding
         and sell calls and puts for the next cycle unless better watchlist
         candidates exist." (Master Document)

EXPIRY-002 — Call assigned (stock called away)
  Action: CALLED_AWAY_CLOSE_PUTS
  Rule: "If stock is called away prior to expiration, look to close naked
         puts for a small debit; otherwise wait for put expiration."
  Next: close naked puts OR let puts expire; evaluate fresh entry next cycle

EXPIRY-003 — Put assigned (stock assigned to account)
  Action: ASSIGNED_SELL_SHARES
  Rule: "If stock is assigned prior to expiration, sell all shares and look
         to close naked calls for a small debit; otherwise wait for call expiration."
  Next: sell shares; close calls OR let calls expire; re-evaluate

EXPIRY-004 — Early close needed
  Action: CLOSE_EARLY
  Trigger: strategy fundamentals changed (symbol dropped from watchlist,
            earnings date inside holding period discovered, market went Red)
```

---

## 6. The Rolling Cycle Model

### 6.1 The Four-Layer Stack

At any point during a normal trading week, up to four layers per symbol per account are active simultaneously:

```
Week  Open Date  Expiration   Status
────  ─────────  ──────────   ──────
 N-3  Mon Apr 7  Fri May 2    open  ← expiring this Friday
 N-2  Mon Apr 14 Fri May 9    open
 N-1  Mon Apr 21 Fri May 16   open
  N   Mon Apr 28 Fri May 23   pending → evaluate this week
```

Each layer is independently tracked in `cycle_layers`. Each has its own strikes, premiums, and expiration outcome.

### 6.2 Weekly Cycle State Machine

```
newsletter arrives (Sunday)
        │
        ▼
   CANDIDATE EVALUATION
   Run gates 1–8 for all watchlist symbols
   (Gate 9 deferred — market closed)
        │
        ├── SKIP: gates 1–7 failed
        ├── ACCUMULATE: shares < 100
        └── CANDIDATE: all gates 1–8 pass → status = pending
                │
                ▼ (Monday–Friday, market hours)
          OS WORKBOOK REFRESH
          Run Gate 9 for all pending candidates
                │
                ├── WATCH: credit not yet executable
                └── EXECUTE: Gate 9 passes → entry_decision status = executed
                            create cycle_layer (status = open)
                            operator confirms fill
                                │
                                ▼ (expiration Friday)
                          EXIT EVALUATION
                          Run EXPIRY-001 through EXPIRY-004
                                │
                                └── update cycle_layer status
                                    create exit_decision
                                    update position_book
```

### 6.3 Position Book Lifecycle

```
ACCUMULATING
  Symbol has < 100 shares in the target account.
  Weekly ACCUMULATE decisions recommend buying shares.
  No options sold yet.
  Position book tracks share count and avg cost basis.

ACTIVE
  Symbol has ≥ 100 shares in one account.
  Weekly BULL_STRANGLE decisions open new layers.
  Call and put sold each week (when market is Green/Yellow).
  Layer stack builds up — up to 4 open simultaneously.

PAUSED
  Market turned Red. No new layers opened.
  Existing layers continue to expiration normally.
  Position book remains intact.

CLOSED
  Symbol dropped from watchlist and all layers expired.
  Or operator closes the book.
  Historical record preserved.
```

---

## 7. Weekly Operational Rhythm

### Sunday — Newsletter Day

```
1. Ingest newsletter PDF → facts stored (watchlist, market env, short list)
2. Run gates 1–8 for all watchlist symbols (offline gates — no OS needed)
   → produces entry_decisions with status 'pending' or 'skip'
3. Generate weekly action plan report
   → market environment, deployment status, candidate list, active cycles,
      expiring layers this week, accumulation pipeline
4. Generate OS workbook from newsletter strikes → outputs/workbooks/
   → auto-copied to data/os_uploads/ (ready for Monday refresh)
```

### Monday–Friday — Market Hours

```
1. Open data/os_uploads/BullStrangle_OS_Live_YYYY-MM-DD.xlsx in Excel
2. Enable Option Samurai add-in, refresh formulas, save
3. Run ingest-os-workbook → stores OS snapshot
4. System re-evaluates Gate 9 for all pending entry_decisions
   → WATCH: credit still insufficient, try again later
   → EXECUTE: credit acceptable → entry_decision status = executed
              → operator enters trade
              → operator confirms fill (strike, premium, account, shares)
              → system creates cycle_layer (status = open)
5. Generate daily brief → active cycles, expiring soon, any Gate 9 changes
```

### Thursday/Friday — Expiration

```
1. Identify cycle_layers WHERE expiration_date = this Friday
2. Run exit gate logic for each expiring layer
3. Generate exit decision recommendations
4. Operator reviews outcomes after market close
5. Operator confirms actual outcome for each layer
6. System updates cycle_layer status and position_book share count
7. If EXPIRE_WORTHLESS_CONTINUE → next Sunday will open new layer
8. If CALLED_AWAY or ASSIGNED → position_book shares updated accordingly
```

### Weekend (Saturday)

```
No Excel required. System queries DB only:
- Cycle P&L summary for closing week
- Accumulation pipeline status
- Market environment trend (last 4 weeks)
- Watch list streak analysis
- Prep: what to watch for in Sunday newsletter
```

---

## 8. MCP Tool Inventory

### Newsletter and Facts Tools (retained from v1)

- `ingest_newsletter` — ingest one newsletter PDF
- `ingest_newsletter_directory` — batch ingest with per-file error handling
- `list_newsletters` — list ingested newsletters
- `get_newsletter` — fetch newsletter by id
- `get_newsletter_by_date` — fetch newsletter by date
- `get_symbol_history` — appearance history across newsletters

### Market Intelligence Tools (retained from v1)

- `get_current_environment` — latest market environment snapshot
- `check_deployment_approval` — per-criterion pass/fail, consecutive weeks
- `get_market_environment_history` — time-range query
- `get_scaling_guidance` — scaling phase and position count guidance

### Watchlist and Symbol Tools (retained from v1)

- `get_watchlist` — full watchlist for a newsletter date
- `get_dca_candidates` — short-list candidates
- `get_deep_analysis` — WL Favorites deep-dive artifacts
- `get_symbol_history` — cross-newsletter appearance history
- `search_commentary` — FTS5 full-text search

### OS Workbook Tools (retained from v1, role clarified)

- `calculate_os_selectors` — newsletter-derived selector values
- `prepare_os_workbook` — create/update workbook metadata
- `generate_os_workbook` — generate Excel workbook (auto-copies to os_uploads)
- `ingest_os_workbook` — ingest refreshed live workbook snapshot
- `list_os_runs` — list OS runs by newsletter
- `report_os_run` — daily deviation report for one run
- `aggregate_os_week` — weekly rollup across all runs

### Entry Decision Tools (new in v3)

- `evaluate_entry_gates` — run full gate sequence for a symbol/newsletter/os_run
- `list_entry_decisions` — list pending/executed/expired decisions for a newsletter
- `get_entry_decision` — full gate detail for one decision
- `confirm_entry_execution` — operator confirms fill → creates cycle_layer

### Position Book Tools (new in v3)

- `get_position_book` — current state for a symbol/account
- `list_position_books` — all books with status and share counts
- `list_active_cycles` — all open cycle_layers sorted by expiration
- `get_cycle_layer` — full detail for one layer

### Exit Decision Tools (new in v3)

- `evaluate_exit_gates` — run exit logic for expiring layers
- `list_exit_decisions` — pending exit decisions for a date
- `confirm_exit_outcome` — operator confirms actual outcome → updates layer and book

### Rule Catalog Tools (new in v3)

- `list_rule_catalog` — all rules with source references and parameters
- `get_rule` — detail for one rule

### Report Tools (retained from v1)

- `generate_weekly_action_plan` — full Sunday report
- `generate_daily_brief` — morning monitoring brief
- `list_generated_reports` — report history
- `get_generated_report` — retrieve report content

### Portfolio Tools (retained from v1)

- `ingest_positions` — ingest broker positions CSV
- `list_strategy_rules` — inspect tunable thresholds

---

## 9. Module Architecture

```
database.py          Schema (SCHEMA_SQL), migrations, connect()
                     New: position_books, cycle_layers, entry_decisions,
                          exit_decisions, strategy_rule_catalog tables

ingestion.py         PDF parsing and fact storage
                     No change — stores facts only, applies no rules

rule_catalog.py      NEW — loads strategy_rule_catalog at startup
                     Provides gate definitions to the entry/exit engines

entry_engine.py      NEW — gate-based entry decision evaluation
                     evaluate_entry_gates(symbol, newsletter_id, os_run_id, account_id)
                     Returns EntryDecision with gates_json

exit_engine.py       NEW — exit decision evaluation for expiring layers
                     evaluate_exit_gates(layer_id)
                     Returns ExitDecision with rule_citations_json

position_book.py     NEW — position book and cycle layer management
                     create_layer(), update_layer_status(), update_book_shares()

decisions.py         RETAINED for weekly_decisions / compute_weekly_summary()
                     DEPRECATED: _build_strategy_context, score-based engine
                     These are replaced by entry_engine.py

os_workbooks.py      No change — generates Excel workbook
os_ingestion.py      No change — ingests refreshed workbook
os_reports.py        No change — daily OS deviation reports
os_weekly.py         No change — weekly OS aggregation
reports.py           No change — weekly action plan, daily brief
positions.py         No change — broker positions CSV ingestion
tools.py             Updated — new tools for entry/exit/position book
mcp_server.py        Updated — new tool registrations
cli.py               Updated — new CLI commands for entry/exit/book
```

---

## 10. Migration From v1 Implementation

### What Stays

All v1 code for PDF ingestion, OS workbook generation, OS ingestion, deviation tracking, report generation, and market environment tracking is retained unchanged. The facts layer is solid.

### What Is Superseded

The score-based decision engine in `decisions.py` (`_build_strategy_context`, `_build_bull_decision`, `_build_dca_decision`, `generate_weekend_decisions`) is superseded. It may be retained temporarily for reference but should not be used for live decisions once the v3 gate engine is operational.

`bull_strangle_decisions` and `dca_decisions` tables are superseded by `entry_decisions`. They may remain in the schema for historical record but new decisions write to `entry_decisions` only.

### Migration Steps

1. Add `strategy_rule_catalog`, `position_books`, `cycle_layers`, `entry_decisions`, `exit_decisions` as migration 3 in `database.py`
2. Seed `strategy_rule_catalog` with rules extracted from the Master Document (`references/master_document_rule_inventory.md`)
3. Build `rule_catalog.py` — loads catalog from DB, exposes gate definitions
4. Build `entry_engine.py` — implements gates 1–9
5. Build `exit_engine.py` — implements EXPIRY-001 through EXPIRY-004
6. Build `position_book.py` — layer creation, status updates, book management
7. Add new tools to `tools.py`, register in `mcp_server.py` and `cli.py`
8. Populate `earnings_calendar` from watchlist_entries.latest_earnings on next newsletter ingest
9. Update report generators to include cycle stack and entry decision status

### Pre-Migration Required Work

Before writing any code, extract the Master Document rules into structured form:

```
references/master_document_rule_inventory.md
```

Format for each rule:
```
Rule ID: ENTRY-STOCK-001
Area: stock_selection
Type: hard_gate
Description: Implied volatility must exceed 35%
Source document: Bull Strangle Master Document v8
Source section: Strategy Overview Core Elements — Pick Quality Stocks
Parameters: {"min_iv": 0.35}
Data column: watchlist_entries.implied_volatility, os_evaluation_rows.live_iv
```

This inventory is the ground truth that `strategy_rule_catalog` is seeded from. It must be completed before the gate engine can be built correctly.

---

*Document version 3.0 — 2026-04-26*
*Supersedes: BullStrangle_Newsletter_MCP_Architecture_Spec_v1.1_JSONB.md*
*Supersedes: BullStrangle_SystemArchitecture_v2.md*
*See also: BullStrangle_Implementation_Guide_v2.md*
