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
  - Bull Strangle promotion requires `100` shares in one account

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
   - DCA entry/add rules
   - DCA promotion to Bull Strangle
   - Bull Strangle entry rules
   - position sizing
   - account selection
   - risk controls
   - exit/roll/assignment handling
3. Store rules in database tables or versioned JSON snapshots.
4. Make weekend decisions explain which rules passed, failed, or were not applicable.
5. Add tests that lock expected behavior for representative cases.

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

### Step 5: Implement DCA Rules

DCA should evaluate:

- whether symbol is already held
- which account is the target account
- current shares in target account
- shares needed to reach `100`
- whether account has enough buying power
- whether DCA is allowed for new positions
- whether position is under target/max allocation
- whether market regime permits adding
- whether OS data is valid

Promotion rule:

- Promote to Bull Strangle evaluation only when one account has at least `100` shares.

### Step 6: Implement Bull Strangle Rules

Bull Strangle should evaluate:

- market gate
- watchlist eligibility
- OS validity
- option credit quality
- price/IV deviation from newsletter baseline
- account has at least `100` shares of the symbol
- shares are in one account
- account is eligible for covered call/put deployment
- no conflicting open options or pending orders

### Step 7: Explain Decisions

Every weekend decision row should include:

- rules passed
- rules failed
- rules not applicable
- source data snapshot
- selected account
- share count before action
- share target after action
- reason text suitable for a report

### Step 8: Add Tests

Add unit tests for:

- account-level 100-share promotion
- 100 shares split across accounts does not qualify
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
- DCA decisions include account, current shares, target shares, and shares needed
- Bull Strangle decisions include account and 100-share eligibility
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
