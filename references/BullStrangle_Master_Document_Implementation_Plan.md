# BullStrangle Master Document Implementation Plan

Date: 2026-04-22
Status: planned

## Purpose

The file `references/Bull Strangle Master Document - Version 8.pdf` is the master strategy reference. It is included in the GitHub repo, but its full strategy logic is not yet implemented.

This document defines a simple implementation plan for converting the Master Document into structured rules, database records, tests, and weekend decision logic.

## Current State

Already implemented:

- Newsletter PDF ingestion.
- Strategy appendix extraction from newsletters.
- Option Samurai workbook generation.
- Daily OS workbook ingestion.
- Weekly OS aggregation.
- V1 Bull Strangle decision table.
- V1 DCA candidate decision table.
- Account-aware DCA rule documented:
  - one recommendation maps to one account
  - DCA target is `100` shares in that account
  - `100` shares in one account enables stock-backed Bull Strangle implementations

Not yet implemented:

- Full Master Document strategy extraction.
- Master Document-backed rule catalog.
- Master Document-backed DCA/Bull Strangle decision engine.
- Account-aware DCA execution logic.
- Strategy-specific unit/integration tests from Master Document examples.

## Implementation Goals

1. Convert the Master Document into a structured rule inventory.
2. Separate rules by strategy area:
   - market regime
   - watchlist eligibility
   - shared strategy scoring
   - action selection between Bull Strangle and DCA
   - DCA entry/add rules
   - Bull Strangle entry rules
   - position sizing
   - account selection
   - risk controls
   - exit/roll/assignment handling
3. Store rules in database tables or versioned JSON snapshots.
4. Make weekend decisions explain which rules passed, failed, or were not applicable.
5. Add tests that lock expected behavior for representative cases.
6. Ensure Bull Strangle and DCA are treated as parallel action choices, not a mandatory sequence.

## Simple Work Plan

### Step 1: Extract Rule Sections

Read the Master Document and create a rule extraction file:

```text
references/master_document_rule_inventory.md
```

For each rule, capture:

- rule id
- section/page source
- strategy area
- plain-English rule
- required input data
- output decision effect
- whether the rule is hard gate, score, warning, or informational

Example:

```text
Rule ID: DCA-ACCOUNT-001
Area: DCA account selection
Source: Master Document page/section TBD
Rule: DCA action must be executed in a single account.
Inputs: account positions, symbol, target shares
Effect: reject split-account recommendations
Type: hard gate
```

### Step 2: Define Data Requirements

Map every extracted rule to data already available or still missing.

Likely existing inputs:

- `market_environment`
- `watchlist_entries`
- `watchlist_deep_analysis`
- `short_list_entries`
- `os_evaluation_rows`
- `watchlist_deviations`
- `os_weekly_symbol_aggregates`
- `positions.csv`

Likely missing inputs:

- cash/buying power by account
- target/max position size by account
- account eligibility for DCA
- account eligibility for Bull Strangle
- open options positions
- pending orders
- last DCA action date

### Step 3: Add Position Tables

Implement account-aware position ingestion from `data/positions/positions.csv`.

Recommended tables:

- `position_import_runs`
- `account_positions`
- `symbol_position_rollups`

Important:

- Store account-level rows exactly.
- Build symbol rollups for exposure awareness only.
- Do not use rollups to determine Bull Strangle promotion.

### Step 4: Add Rule Catalog

Recommended tables:

- `strategy_rule_versions`
- `strategy_rule_catalog`

Fields should include:

- `rule_id`
- `rule_area`
- `rule_name`
- `rule_type`
- `rule_description`
- `source_document`
- `source_page`
- `parameters_json`
- `is_active`

Keep the initial implementation simple. JSON parameters are acceptable until rule logic stabilizes.

### Step 5: Implement Shared Strategy Score

Before choosing Bull Strangle or DCA, compute a shared strategy score for each symbol.

Score inputs should include:

- market regime
- newsletter/watchlist quality
- short-list/favorite status
- live option premium quality
- data validity
- weekly price/credit deviation
- live price attractiveness relative to strike structure

The output should include:

- `strategy_score`
- `strategy_band`
- rule pass/fail detail

### Step 6: Implement Action Selection

After the strategy score is computed, select one preferred action:

- `BULL_STRANGLE`
- `DCA`
- `WATCH`
- `SKIP`

Decision intent:

- `BULL_STRANGLE`: direct strategy entry is preferred
- `DCA`: setup still scores well, but accumulation is preferred
- `WATCH`: setup is promising but not ready
- `SKIP`: setup is weak or invalid

### Step 7: Implement DCA Rules

DCA should evaluate:

- which account is the target account
- current shares in target account
- shares needed to reach `100`
- whether account has enough buying power
- whether DCA is allowed for new positions
- whether position is under target/max allocation
- whether market regime permits adding
- whether OS data is valid
- whether the acquisition price supports the future strike structure

### Step 8: Implement Bull Strangle Rules

Bull Strangle should evaluate:

- market gate
- watchlist eligibility
- shared strategy score
- OS validity
- option credit quality
- price/IV deviation from newsletter baseline
- account is eligible for covered call/put deployment
- no conflicting open options or pending orders
- whether the chosen Bull Strangle implementation is direct-entry or stock-backed

### Step 9: Explain Decisions

Every weekend decision row should include:

- rules passed
- rules failed
- rules not applicable
- selected action type
- strategy score
- source data snapshot
- selected account
- share count before action
- share target after action
- reason text suitable for a report

### Step 10: Add Tests

Add unit tests for:

- Bull Strangle direct entry path without preexisting 100 shares
- DCA chosen even though Bull Strangle setup also scores well
- DCA shares-to-target calculation
- account selection behavior
- missing cash/buying power behavior
- Bull Strangle account eligibility gate

Add integration tests for:

- ingest `positions.csv`
- create DCA decisions with account context
- promote one symbol to Bull Strangle when one account has `100` shares

## Acceptance Criteria

The Master Document implementation is ready when:

- extracted rules are documented with source references
- rule catalog exists in DB or versioned JSON
- weekend decisions include a shared strategy score and one selected action type
- DCA decisions include account, current shares, target shares, and shares needed
- Bull Strangle decisions include account context and direct-entry versus stock-backed rationale
- no DCA/Bull Strangle decision splits one action across accounts
- decisions clearly explain rule pass/fail outcomes
- unit and integration tests cover the account and promotion rules

## Deferred Until Later

- Automated order placement.
- Broker API integration.
- Intraday decision generation.
- Multi-account optimization.
- Tax-lot optimization.
- Options assignment/roll automation.
