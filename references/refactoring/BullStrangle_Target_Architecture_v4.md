# BullStrangle Target Architecture v4

Status: Target Architecture Draft
Date: 2026-05-25
Scope: Refactor architecture for live option-chain scanning, paper/shadow/live lifecycle readiness, portfolio learning, and Option Samurai deprecation.

Inputs:
- `references/refactoring/BullStrangle_Product_Spec_Refactor_PRD.md`
- `references/refactoring/Architect_PRD_Review.md`
- `references/refactoring/BullStrangle_Refactor_Design_Notes.md`
- `references/BullStrangle_Architecture_Spec_v3.md`
- `references/BullStrangle_Implementation_Plan_v3.md`

Related diagrams:
- `references/refactoring/diagrams/bullstrangle_agents_architecture.svg`
- `references/refactoring/diagrams/bullstrangle_db_architecture.svg`

## 1. Architecture Position

v4 is the target architecture for the refactor. It does not rewrite or invalidate v3 as the current-state implementation. v3 remains the historical/current operating model for newsletter ingestion, OS workbook generation/ingestion, gate evaluation, cycle layers, reports, and backtest/paper monitoring.

v4 changes the strategic architecture in one major way: Option Samurai Excel stops being the execution data plane. BullStrangle becomes a strategy operating layer that uses Darren's newsletter for candidate selection and live option-chain data for executable trade construction, P/L, probability, paper trading, and eventual live readiness.

The target workflow is:

```text
newsletter intelligence
  -> live market-data provider
  -> live scanner
  -> P/L + probability
  -> entry decision
  -> paper portfolio
  -> monitoring
  -> outcome attribution
  -> confidence scoring
```

The live-trading-ready workflow is:

```text
entry decision
  -> trade intent
  -> order draft
  -> operator approval
  -> paper fill or live broker order
  -> fills
  -> position lifecycle
  -> outcome
```

## 2. Current-State Problems

The current v3 implementation solved important operational problems, but it remains constrained by the OS workbook loop.

Current-state strengths:
- Newsletter ingestion and immutable artifact storage exist.
- Watchlist and short-list extraction exist.
- Strategy rule catalog and gate engine exist.
- Entry and exit engine concepts exist.
- Large/Small portfolio separation has begun through `portfolio_type`.
- Reports and workflow commands exist.
- Existing DB migrations are additive and should be preserved.

Current-state problems:
- Execution data depends on generated Option Samurai workbooks, manual Excel refresh, and workbook re-ingestion.
- Option Samurai fields shape downstream decisions too strongly, including Gate 7 moving-average alignment and workbook-only SMA fields.
- Current gate logic can over-filter trades after Darren has already curated the watchlist.
- The system tracks historical/paper cycle layers but does not yet have a clean paper/shadow/live execution lifecycle with intents, order drafts, approvals, fills, and broker reconciliation.
- P/L and probability are not first-class internally versioned engines with stored assumptions.
- Current paper trading/backtest logic is useful but not a shared lifecycle model for future live trading.
- Provider independence is not implemented for live option-chain enumeration.
- Confidence scoring is not yet a durable feedback loop from accepted, watched, and rejected candidates through expiration.

## 3. Product And Architecture Principles

- Darren's newsletter remains the source of candidate symbols and market thesis.
- The first refactor does not replace Darren's stock-selection process.
- Live strike selection chooses option legs from the newsletter-derived universe; it does not create a generic options scanner.
- Option Samurai becomes a fallback and benchmark, not the normal execution data path.
- P/L and probability are calculated internally and persisted with versions, inputs, and assumptions.
- Greeks are inputs and diagnostics, not final probability answers.
- Large and Small portfolios are separate books with separate capacity, performance, and confidence metrics.
- Paper, shadow, and live execution share one lifecycle model.
- Live order submission is structurally disabled until later phases and always requires explicit operator approval.
- Provider-specific clients sit behind a provider contract. Core scanner, decision, P/L, probability, and portfolio logic never import a broker-specific client directly.
- v4 schema changes are additive. Existing v3 tables remain historical/current-state sources during migration.

## 4. Target Multi-Agent Architecture

The target agent model is a set of service boundaries first. It should not require runtime multi-agent orchestration in the MVP.

| Agent/Service | Responsibility | MVP |
|---|---|---:|
| Ingestion Agent | Parse newsletter PDFs and store artifacts, watchlist rows, short-list rows, market environment, source lineage. | Existing/current |
| Newsletter Intelligence Agent | Extract thesis, risk posture, cautions, sector/theme emphasis, week-over-week changes. | Defer advanced extraction |
| Strategy Rule Agent | Maintain versioned hard, soft, and advisory rules; retire Gate 7 as hard reject by default. | Required as rule/policy source |
| Market Data Agent | Normalize provider quotes, option chains, freshness, errors, raw payloads. | Required |
| Live Scanner Agent | Run newsletter replication and live strike-selection modes. | Required |
| P/L Agent | Compute credit, capital, breakevens, returns, modeled losses, scenario table. | Required |
| Probability Agent | Compute internal probability metrics with stored model assumptions. | Required |
| Entry Decision Agent | Produce ACCEPT/WATCH/REJECT/DATA_UNAVAILABLE with evidence and explanation. | Required |
| Portfolio Manager Agent | Own Large/Small books, sizing, exposure, assignment capacity, duplicate policy. | Minimal in MVP |
| Paper Trading Agent | Create paper trade intents, order drafts, simulated fills, lifecycle events. | Required in MVP |
| Execution Agent | Own shadow/live order drafts, approvals, broker orders, fills, idempotency. | Schema only in MVP |
| Monitoring Agent | Mark open positions, detect proximity and scenario risks. | P1 |
| Outcome Attribution Agent | Classify outcomes and compare expected vs realized P/L/probability. | P1/P2 |
| Confidence Agent | Produce trade-level and system-level confidence metrics. | Start simple, mature later |
| Reporting/Briefing Agent | Produce replay reports, weekly paper reports, monitoring and confidence reports. | MVP replay report |

Implementation guidance: build deterministic Python modules/services first. Only expose these as MCP tools or agents after the contracts stabilize.

## 5. Data Domains And v4 Schema Proposal

### 5.1 Schema Strategy

v4 schema is additive. Do not destructively migrate v3 tables. The v3 artifact layer remains authoritative for ingested newsletters.

Current tables to retain:
- `newsletters`
- `newsletter_full_text`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deep_analysis`
- `market_environment`
- `weekly_decisions`
- `symbol_history`
- `strategy_reference_sections`
- `strategy_rules`
- `strategy_rule_catalog`
- `os_workbooks`
- `os_evaluation_runs`
- `os_evaluation_rows`
- `watchlist_deviations`
- `os_weekly_symbol_aggregates`
- `position_books`
- `cycle_layers`
- `entry_decisions`
- `exit_decisions`
- `position_import_runs`
- `account_positions`
- `symbol_position_rollups`
- `generated_reports`
- `report_subscriptions`
- `earnings_calendar`

Current tables to treat as historical/compatibility only:
- `decision_batches`
- `bull_strangle_decisions`
- `dca_decisions`

New v4 tables should use an explicit suffix only where needed to avoid semantic collisions. Recommended names below use clear nouns instead of relying only on `v2` suffixes.

### 5.2 Artifact Domain

Existing artifact tables remain source of truth. Additions are optional and not MVP blockers.

| Table | Purpose | Priority |
|---|---|---:|
| `newsletter_source_facts` | Field-level lineage for extracted facts: table, row id, field name, page/span, extraction confidence. | P1 |
| `newsletter_intelligence` | Structured market thesis, risk posture, warnings, themes, week-over-week changes. | P1 |

### 5.3 Rule And Policy Domain

The current `strategy_rule_catalog` should be extended or paired with immutable policy version tables. Do not create a second unlinked rule catalog.

| Table | Purpose | Priority |
|---|---|---:|
| `strategy_policy_versions` | Versioned bundle of rule catalog version, strike policy, pricing policy, P/L formula version, probability model version. | P0 |
| `pricing_policies` | Named pricing policy and parameters. | P0 |
| `strike_selection_policies` | Delta bands, expiration policy, liquidity tie-breakers, protective put rule. | P0 |
| `formula_versions` | P/L formula metadata and assumptions. | P0 |
| `probability_model_versions` | Probability model metadata and assumptions. | P0 |
| `evaluated_rule_evidence` | Immutable evaluated rule rows linked to decisions. Can be JSON in MVP if normalized table is deferred. | P1 |

Minimum fields for policy tables:

```text
policy_id/version_id
name
status: draft | active | retired
parameters_json
created_at
effective_from
effective_to
notes
```

### 5.4 Market Data Domain

| Table | Purpose | Priority |
|---|---|---:|
| `market_data_runs` | One provider retrieval/scan run with provider, mode, timestamps, status, errors. | P0 |
| `stock_quote_snapshots` | Normalized stock quote rows linked to run. | P0 |
| `option_chain_snapshots` | Parent chain snapshot: symbol, expiration, provider, as-of timestamps. | P0 |
| `option_chain_rows` | One row per option contract in a chain snapshot. | P0 |
| `provider_health_events` | Auth/rate-limit/freshness/provider error events. | P1 |

Minimum `market_data_runs` fields:

```text
run_id
provider_id
provider_name
run_type: quote | option_chain | scan
started_at
completed_at
status: success | partial | failed
request_json
error_type
error_message
raw_response_ref or raw_response_json
```

Minimum `stock_quote_snapshots` fields:

```text
quote_id
run_id
symbol
bid
ask
last
mark
mid
volume
provider_quote_timestamp
retrieved_at
is_delayed
raw_payload_json
```

Minimum `option_chain_rows` fields:

```text
option_row_id
chain_snapshot_id
provider_contract_id
occ_symbol
underlying_symbol
expiration_date
right: call | put
strike
multiplier
bid
ask
mid
last
mark
delta
gamma
theta
vega
rho
iv
volume
open_interest
provider_quote_timestamp
retrieved_at
is_adjusted
is_weekly
raw_payload_json
```

### 5.5 Scanner And Decision Domain

| Table | Purpose | Priority |
|---|---|---:|
| `live_watchlist_snapshots` | One scanner candidate output per symbol/mode/run. | P0 |
| `selected_trade_legs` | Selected call/put/protective put alternatives and final legs. | P0 |
| `pl_evaluations` | Versioned P/L outputs and assumptions. | P0 |
| `pl_scenario_rows` | Scenario table across expiration prices. | P1 |
| `probability_evaluations` | Versioned probability outputs and assumptions. | P0 |
| `entry_decisions_v4` | New decision record with evidence and replay links. | P0 |
| `trade_scorecards` | Component confidence scores. | P1 |

Minimum `live_watchlist_snapshots` fields:

```text
snapshot_id
newsletter_id
watchlist_entry_id
short_list_id nullable
symbol
portfolio_type nullable: large | small
scan_mode: newsletter_replication | live_strike_selection
market_data_run_id
stock_quote_id
chain_snapshot_id
expiration_date
pricing_policy_id
strike_selection_policy_id
selected_at
status: selected | data_unavailable | no_eligible_chain | no_eligible_strikes
status_reason
raw_selection_json
```

Minimum `selected_trade_legs` fields:

```text
leg_id
snapshot_id
leg_role: long_stock | short_call | short_put | long_put
option_row_id nullable
underlying_symbol
right nullable
strike nullable
expiration_date nullable
quantity
side: buy | sell
raw_bid
raw_ask
raw_mid
execution_price
execution_price_source
delta/iv/liquidity fields copied for replay
selection_rank
selection_reason
```

Minimum `entry_decisions_v4` fields:

```text
decision_id
newsletter_id
watchlist_entry_id
snapshot_id
pl_evaluation_id
probability_evaluation_id
policy_version_id
portfolio_type nullable
symbol
decision_status: ACCEPT | WATCH | REJECT | DATA_UNAVAILABLE
strategy_decision_status
portfolio_actionability_status
confidence_level: HIGH | MEDIUM | LOW | REJECT nullable
rule_evidence_json
liquidity_summary_json
explanation
idempotency_key
created_at
```

`DATA_UNAVAILABLE` is deliberately included as a first-class outcome. Provider failures and stale data should not be encoded as rejects.

### 5.6 Execution Domain

| Table | Purpose | Priority |
|---|---|---:|
| `trade_intents` | Strategy intent to trade from accepted decision. | P0 |
| `order_drafts` | Broker-neutral order draft. | P0 |
| `order_draft_legs` | Legs for draft order. | P0 |
| `operator_approvals` | Immutable approvals tied to exact order draft version. | P2 schema design, implementation later |
| `broker_orders` | Submitted live orders and raw broker payloads. | P2 |
| `broker_order_legs` | Broker order leg mapping. | P2 |
| `fills` | Simulated/manual/broker fills, supports partial fills. | P0 for simulated fills, P2 live |
| `fill_legs` | Per-leg fill details. | P1/P2 |
| `live_positions` | Broker-synced positions and reconciliation status. | P2 |
| `assignment_events` | Partial/full assignments, early assignment, call-away events. | P1/P2 |
| `trade_lifecycle_events` | Immutable lifecycle event stream. | P0 |
| `trade_outcomes` | Final realized/modeled outcome attribution. | P1 |

Minimum lifecycle states:

```text
candidate_created
accepted
watched
rejected
data_unavailable
trade_intent_created
order_draft_created
approval_pending
approval_approved
approval_rejected
paper_filled
submitted_live
partially_filled
filled
cancelled
rejected_by_broker
open
monitoring
assigned
called_away
expired
closed
restarted
outcome_recorded
```

MVP implements only paper path through `paper_filled`, `open`, and lifecycle events required for replay.

### 5.7 Portfolio And Confidence Domain

| Table | Purpose | Priority |
|---|---|---:|
| `paper_portfolios` | Separate Large and Small paper books and assumptions. | P1 |
| `portfolio_snapshots` | Cash, buying power, reserved capital, exposure, open intents/trades. | P1 |
| `paper_trade_marks` | Periodic mark-to-market records. | P1 |
| `system_confidence_metrics` | Periodic system-level confidence metrics. | P1/P2 |
| `scenario_scoreboard_snapshots` | Distribution and P/L by Darren scenario. | P1 |

Avoid duplicating lifecycle data in `paper_trades` if `trade_intents`, `order_drafts`, `fills`, and lifecycle events already represent paper trades. Prefer portfolio views over duplicate state tables.

## 6. Market Data Provider Contract

Core scanner logic depends on a provider interface, not a broker client.

Minimum provider capabilities:

```text
get_stock_quote(symbol) -> StockQuoteResult
get_option_chain(symbol, expiration_date) -> OptionChainResult
get_provider_status() -> ProviderStatus
```

Future capabilities:

```text
list_expirations(symbol) -> ExpirationListResult
get_contract_quote(occ_symbol/provider_contract_id) -> OptionQuoteResult
get_market_clock() -> MarketClockResult
```

Required normalized stock quote fields:

```text
provider_id
symbol
bid
ask
last
mark
mid
volume
provider_quote_timestamp
retrieved_at
is_delayed
freshness_seconds
raw_payload_json
```

Required normalized option chain row fields:

```text
provider_id
provider_contract_id
occ_symbol
underlying_symbol
expiration_date
right
strike
multiplier
bid
ask
mid
last
mark
delta
iv
volume
open_interest
provider_quote_timestamp
retrieved_at
is_adjusted
is_weekly
raw_payload_json
```

Strongly recommended optional option fields:

```text
gamma
theta
vega
rho
description
root_symbol
native_option_type
exchange
```

Provider calls must return typed errors instead of crashing the scan run.

Error categories:

```text
auth_failed
permission_or_entitlement_denied
rate_limited
symbol_not_found
expiration_not_found
market_closed
stale_data
partial_data
missing_critical_fields
network_error
provider_error
normalization_error
```

Failure behavior:
- Auth failures produce actionable operator messages.
- Rate limits mark run partial and allow retry/resume.
- Missing bid/ask blocks selected contracts.
- Missing greeks can either block or warn depending on the approved strike-selection policy.
- Stale data blocks live execution and should create at least a warning for paper/shadow.
- Provider failure creates `DATA_UNAVAILABLE`, not `REJECT`.

Every provider result must distinguish:
- `provider_quote_timestamp`: timestamp claimed by provider for quote/chain row.
- `retrieved_at`: timestamp BullStrangle retrieved the data.
- `scan_started_at` / `scan_completed_at`: scanner run timestamps.

## 7. Tradier Provider Strategy

Tradier direct API is the first provider because a live AA test returned a usable option chain with bid, ask, open interest, volume, IV, greeks, and prices close to newsletter/OS values.

Strategy:
- Implement `TradierOptionChainProvider` inside BullStrangle first, behind the provider contract.
- Use existing Tradier token/config from local broker configuration if available, but do not make BullStrangle core depend on broker control-plane modules.
- Normalize Tradier quote and chain payloads into the v4 provider contract.
- Persist raw Tradier payload JSON with every normalized quote/chain snapshot.
- Treat Tradier as replaceable. Scanner, P/L, probability, decision, portfolio, and execution modules must depend only on normalized provider dataclasses/tables.
- Later, optionally expose Tradier option-chain access through broker MCP or another shared provider service. Do not block the v4 MVP on broker-platform changes.

Tradier-specific risks:
- Auth and account entitlements may differ across environments.
- Greeks may be null or delayed for some contracts.
- Rate limits may affect full-watchlist scans.
- Contract identifiers and timestamp semantics must be normalized carefully.
- The provider may return adjusted or non-standard contracts that should be filtered unless explicitly supported.

## 8. Live Scanner Modes

The scanner supports two modes. Both persist complete inputs, selected legs, pricing policy, and output evidence.

### 8.1 Newsletter Replication Mode

Purpose: validation and transition from OS.

Inputs:
- Newsletter watchlist row.
- Published short call, short put, and protective put strikes.
- Target expiration from newsletter or selected four-week rule.
- Live quote and chain snapshot.

Behavior:
- Match newsletter-published strikes to live chain rows.
- Refresh bid/ask/mid, greeks, IV, volume, OI.
- Calculate executable credit under the active pricing policy.
- Compare refreshed output to newsletter/OS benchmark where available.
- Determine whether Darren's published trade is still executable.

This mode should not require OS workbook fields.

### 8.2 Live Strike-Selection Mode

Purpose: target execution workflow.

Inputs:
- Newsletter-derived candidate symbol.
- Live stock quote.
- Target expiration.
- Live option chain.
- Strike-selection policy.
- Pricing policy.
- Liquidity policy.

Behavior:
- Select short call, short put, and protective put from the live chain.
- Use configured delta bands/targets and liquidity constraints.
- Apply tie-breakers deterministically.
- Persist selected legs and rejected/nearby alternatives for explainability.
- Feed P/L, probability, decision, and paper lifecycle creation.

## 9. Strike-Selection Design

The strike selector is deterministic and policy-driven.

Inputs:

```text
symbol
stock_quote
option_chain_snapshot
target_expiration
strike_selection_policy
liquidity_policy
pricing_policy
scan_mode
```

Expiration selection open decisions:
- Default target is closest listed expiration to 28 calendar days from scan date.
- Need approved min DTE and max DTE bounds.
- Need policy for weekly vs monthly expirations.
- Need behavior when no chain exists in the acceptable range.

Recommended provisional behavior:
- Choose listed expiration with smallest absolute distance from 28 calendar days.
- Require 21 to 35 DTE unless explicitly overridden.
- If no eligible expiration exists, return `DATA_UNAVAILABLE` or `NO_ELIGIBLE_EXPIRATION`, not `REJECT`.

Required policy decisions:
- Short call positive delta target or band.
- Short put negative delta target or band.
- Protective put selection rule: delta, distance, premium ratio, max debit, or fixed relation to short put.
- Liquidity thresholds and tie-breakers.

Recommended deterministic tie-break order:

1. Contract passes critical data checks.
2. Contract passes liquidity checks.
3. Delta closest to target or inside band.
4. Narrower bid/ask spread.
5. Higher open interest.
6. Higher volume.
7. Strike farther from stock if still tied for short legs.

Each selected leg stores:
- Selected contract fields.
- Rule that selected it.
- Delta distance from target.
- Spread and liquidity evidence.
- Alternative candidate summary.
- Rejection reasons for nearest alternatives where practical.

## 10. Pricing Policy

Pricing policy must be centralized and persisted. It affects P/L, probability inputs, paper fills, order drafts, and confidence.

Recommended MVP pricing policy: conservative executable pricing.

- Short option credit uses bid or bid-adjusted price.
- Long option debit uses ask or ask-adjusted price.
- Mid is computed and reported but not used as default paper fill unless approved.
- Stock entry price uses ask for buy-side stock assumptions in paper mode, or configured stock mark if approved.
- Store raw bid/ask/mid and selected execution price separately.

Required fields:

```text
pricing_policy_id
policy_name
short_option_price_source: bid | mid | bid_adjusted
long_option_price_source: ask | mid | ask_adjusted
stock_buy_price_source: ask | mid | last | mark
stock_sell_price_source: bid | mid | last | mark
spread_adjustment_json
commission_model_json
rounding_policy_json
```

Paper fill rule: simulated fills must not be more favorable than the configured pricing policy.

Live order draft rule: limit prices derive from the same policy but can include an operator-approved limit offset.

## 11. P/L Engine

The P/L engine computes deterministic outputs from selected legs, stock quote, pricing policy, and formula version.

Required outputs:
- Total credit.
- Capital required.
- Downside breakeven.
- Called-away profit.
- Put-assigned cost basis.
- Maximum modeled loss.
- Return on capital.
- Annualized return.
- Scenario table across prices at expiration.

Required inputs to persist:

```text
selected legs and execution prices
stock price assumption
contract multiplier
quantity
commission/fee assumption
capital model: cash_secured | margin | custom
formula_version_id
calculation_timestamp
```

Formula decisions required before engineering:
- Whether capital required includes stock cost plus cash-secured short put reserve minus credit.
- Whether protective put limits are modeled against only assigned shares, existing shares, or total downside exposure.
- Whether commissions and fees are included in MVP.
- Annualization convention: 365 calendar days, 252 trading days, or DTE-based simple annualization.
- Whether called-away profit includes stock appreciation from current entry stock price or newsletter published price.

At minimum, generate scenario rows for:
- Far below protective put.
- At protective put.
- At short put.
- At downside breakeven.
- Between short put and short call.
- At short call.
- Above short call.

Scenario rows should include stock P/L, option P/L by leg, total P/L, assignment/call-away status, and notes.

## 12. Probability Engine

The probability engine computes internal probability metrics. OS probability values are benchmark data only.

Required outputs:
- Probability of profit.
- Probability short call expires OTM.
- Probability short put expires OTM.
- Probability stock finishes between short strikes.
- Model name.
- Model version.
- Model assumptions.
- Input IV and timestamp.

Recommended MVP model: lognormal expiration distribution using selected IV.

Inputs:

```text
spot price
DTE
short call strike
short put strike
protective put strike
selected IV or per-leg IV policy
risk-free rate assumption
dividend assumption
pricing/P&L payoff definition
```

Assumptions must be explicit:
- Expiration-only model, not path-aware.
- No claim of equivalence with Option Samurai probability.
- If dividends are ignored, store `dividend_assumption: ignored`.
- If a flat risk-free rate is used, store the rate and source.

Probability risks:
- IV choice matters: ATM IV, short-leg IV, blended IV, or provider underlying IV will produce different probabilities.
- Delta is not probability of profit.
- Early assignment risk is path-dependent and not captured by simple expiration probability.
- Probability outputs should inform decisions but should not be represented as certainty.

## 13. Entry Decision Model

The entry decision combines rule evidence, scanner output, P/L, probability, liquidity, portfolio fit, and confidence.

Decision statuses:

```text
ACCEPT
WATCH
REJECT
DATA_UNAVAILABLE
```

`DATA_UNAVAILABLE` covers provider failure, stale data, missing chain, missing critical fields, and no eligible expiration. It is not a strategy rejection.

Every decision stores:
- Source newsletter and watchlist entry.
- Scan mode.
- Market data snapshot links.
- Selected legs.
- Pricing policy.
- Strike-selection policy.
- P/L evaluation.
- Probability evaluation.
- Rule evidence.
- Liquidity summary.
- Portfolio fit summary.
- Confidence level where available.
- Human-readable explanation.

Separate these concepts:
- `strategy_decision_status`: does the trade structure pass strategy/P&L/probability/liquidity rules?
- `portfolio_actionability_status`: can the Large or Small book take this trade now given cash, exposure, duplicate policy, and assignment capacity?

A trade may be strategy-acceptable but not portfolio-actionable.

## 14. Portfolio Management: Large And Small Books

Large and Small portfolios are independent strategy books.

Track per book:
- Portfolio type: `large` or `small`.
- Current and target positions.
- Cash or buying power assumptions.
- Reserved assignment capacity.
- Maximum concurrent positions.
- Allocation per symbol.
- Allocation per sector/theme.
- Duplicate exposure across books.
- Open trade intents, order drafts, fills, and lifecycle statuses.

MVP does not need full allocation optimization. It should store portfolio type when known and preserve enough links for later Large/Small reporting.

P1 full-watchlist paper run should implement:
- Separate paper books for Large and Small.
- Independent max position counts.
- Independent capital assumptions.
- Duplicate symbol policy.
- Assignment reserve tracking.

Open duplicate policy decision:
- Allow same symbol in Large and Small independently.
- Warn but allow.
- Reject duplicate exposure.

Recommendation: warn but allow during paper trading, because the purpose is to compare book behavior. Revisit before live trading.

## 15. Paper, Shadow, And Live Execution Lifecycle

Paper, shadow, and live modes use the same lifecycle entities:

```text
EntryDecision
  -> TradeIntent
  -> OrderDraft
  -> OperatorApproval
  -> BrokerOrder or PaperFill
  -> Fill
  -> PositionLifecycle
  -> Outcome
```

MVP implements paper-only lifecycle with no live submission code path.

Execution modes:

```text
planning: parse/analyze only; no trade intents.
paper: create trade intents, order drafts, simulated fills, lifecycle events.
shadow: create order drafts and approvals; no broker submission.
live: submit approved broker orders, only after future readiness gates.
```

Default mode remains `paper` until explicitly changed after confidence and approval requirements are met.

Before live implementation exists:
- Global live feature flag defaults off.
- Separate broker submission flag defaults off.
- No live order tool is registered in MVP.
- Live-capable order drafts require idempotency keys.
- Approval is tied to immutable order draft version.
- Quote freshness and market-hours checks are hard blockers for live.
- Account allowlist and max order guardrails are required.
- Broker request/response payloads are stored for auditability.
- Broker-synced positions become source of truth after live fill, with reconciliation events when state conflicts.
- Kill switch prevents new live submissions while preserving read-only reconciliation.

## 16. Trade-Management Scenarios

Darren's five trade-management scenarios become outcome categories.

| Scenario | Trigger | Management Rule |
|---|---|---|
| `EARLY_CALL` | Stock called away before expiration. | Close naked put around 0.05 to 0.10 where available, otherwise wait. |
| `EARLY_ASSIGNMENT` | Short put assigned before expiration. | Sell all shares and close naked call around 0.05 to 0.10 where available, otherwise wait. |
| `STOCK_CALLED_AWAY` | Covered stock called away at/near expiration. | Best-case maximum-profit closure, no action required. |
| `OPTIONS_EXPIRED_STOCK_KEPT` | Options expire and stock is retained. | Usually continue and sell next-cycle calls/puts; compare against better candidates. |
| `STOCK_ASSIGNED` | Stock closes below put strike and additional shares assigned. | Usually sell all shares and find new candidate; if still desired, sell half and restart. |

Scenario tracking fields:

```text
management_scenario
scenario_triggered_at
scenario_trigger_price
short_call_close_price
short_put_close_price
shares_sold
shares_assigned
restart_next_cycle
operator_override
scenario_notes
```

Monitoring requirements:
- Detect stock above short call strike.
- Detect stock below short put strike.
- Detect proximity to either strike.
- Track whether short options can be closed in the 0.05 to 0.10 range.
- Classify expiration outcomes automatically where possible.
- Allow operator override with audit notes.

## 17. Confidence Scoring

Confidence is evidence-based and should mature over paper history.

Trade-level component scores:
- Data freshness score.
- Liquidity score.
- P/L attractiveness score.
- Probability score.
- Newsletter alignment score.
- Rule-compliance score.
- Portfolio-fit score.

Final levels:

```text
HIGH
MEDIUM
LOW
REJECT
```

MVP can store component placeholders but should not overstate confidence until formulas are approved.

System-level metrics:
- Win rate.
- Average return.
- Max drawdown.
- Assignment frequency.
- Called-away rate.
- Expected-vs-realized P/L.
- Accepted-vs-rejected outcome comparison.
- Large versus Small performance.
- Newsletter replication versus live strike-selection performance.

Readiness thresholds:
- Shadow mode threshold: open decision.
- Live mode threshold: open decision.
- Minimum sample size and performance thresholds must be explicit before live trading is considered.

## 18. Option Samurai Excel Deprecation Plan

Option Samurai is not removed immediately. It is demoted in phases.

### Phase OS-0: Current State

OS workbook remains operational and feeds existing v3 workflows.

### Phase OS-1: Benchmark

Live scanner runs alongside OS. Reports compare:
- Newsletter published strikes.
- OS refreshed values.
- Live provider refreshed values.
- Live strike-selection output.

### Phase OS-2: Fallback

Live scanner becomes normal paper path. OS workbook remains available when provider chain data is unavailable or for manual benchmark checks.

### Phase OS-3: Deprecated Normal Workflow

OS workbook generation/re-ingestion is no longer required for the normal BullStrangle workflow. Existing OS tables remain historical and may still be used for old reports or transition analysis.

Deprecation rule: do not delete OS tables or code during v4 MVP. Stop making new strategic logic depend on OS-only fields.

Gate 7 policy: moving-average alignment from OS SMA fields is advisory/retired by default and cannot reject trades unless a future rule version explicitly re-enables it as a hard gate.

## 19. Migration Strategy From Current DB/Workflow

Migration principles:
- Additive migrations only.
- Existing v3 tables stay intact.
- New v4 tables reference existing newsletter and watchlist IDs.
- Historical decisions are not blindly backfilled into v4 decisions.
- Current OS/gate data can be used as benchmark and compatibility input.
- Existing reports continue to work during migration.

Mapping current to target:

| Current v3 Entity | v4 Role |
|---|---|
| `newsletters` | Source newsletter dimension. |
| `watchlist_entries` | Candidate universe source. |
| `short_list_entries` | Large/Small source membership. |
| `market_environment` | Market context and possible advisory/portfolio input. |
| `strategy_rule_catalog` | Extend for versioned hard/soft/advisory rule model. |
| `os_evaluation_rows` | Benchmark/fallback provider data, not primary. |
| `entry_decisions` | Historical/current gate decisions. New live-scanner decisions go to `entry_decisions_v4` or compatible extension. |
| `cycle_layers` | Historical/current paper/backtest layer model. Map to new trade lifecycle where needed. |
| `position_books` | Current position concept; may feed portfolio manager but should not replace execution lifecycle. |

Migration steps:

1. Add provider, market snapshot, scanner, P/L, probability, decision, and lifecycle tables.
2. Add policy/version tables for pricing, strike selection, formulas, and probability model.
3. Implement one-symbol paper-only slice using existing `watchlist_entries`.
4. Generate replay report from v4 tables.
5. Run full watchlist paper scan while leaving v3 OS workflow intact.
6. Compare OS vs live scanner outputs over multiple newsletters.
7. Move paper portfolio reporting from `cycle_layers`-only view toward shared lifecycle views.
8. Defer live broker integration until confidence and safety gates are approved.

## 20. Phased Rollout Plan

### Phase 0: Architecture Hardening

Deliverables:
- Provider contract.
- v4 additive schema specification.
- Pricing policy.
- Strike-selection policy.
- P/L formula specification.
- Probability model specification.
- Decision evidence contract.
- Paper lifecycle state machine.
- Live safety design.

Exit criteria: engineering-ready MVP package approved.

### Phase 1: One-Symbol Vertical Slice

Deliverables:
- Tradier quote and option chain retrieval.
- Persisted market snapshots.
- Live strike selection.
- P/L and probability calculation.
- Entry decision with explanation.
- Paper trade intent, order draft, simulated fill, lifecycle event.
- Replay report.

Explicitly out of scope: live order submission, full dashboard, full monitoring, full confidence layer.

### Phase 2: Full Watchlist Paper Run

Deliverables:
- Run scanner for all newsletter symbols.
- Support newsletter replication and live strike-selection side by side.
- Create Large and Small paper books.
- Produce weekly paper entry report.

### Phase 3: Monitoring And Scenarios

Deliverables:
- Mark open paper trades.
- Detect strike proximity and close-price availability.
- Classify Darren scenarios.
- Produce scenario scoreboard.

### Phase 4: Confidence Reporting

Deliverables:
- Expected-vs-realized P/L.
- Accepted-vs-rejected outcome comparison.
- Large versus Small comparison.
- Rule attribution.
- Provider quality metrics.

### Phase 5: Shadow Trading

Deliverables:
- Order drafts and approval workflow.
- No live submission.
- Compare system recommendations against operator actions.

### Phase 6: Live Readiness

Deliverables:
- Broker integration behind execution interface.
- Live safety controls.
- Account allowlist.
- Idempotent live order submission.
- Broker reconciliation.
- Explicit operator approval and confidence threshold checks.

## 21. Architecture Decisions And Tradeoffs

### Decision: Create v4 target doc instead of editing v3

Rationale: v3 is an active/current implementation record. Editing it into a target architecture would blur history and current behavior.

Tradeoff: docs now have two architecture versions. Mitigation: v4 explicitly maps from v3 and states what remains current.

### Decision: Additive schema, not in-place rewrite

Rationale: current DB has valuable ingested newsletters, OS history, gate decisions, and paper/backtest data.

Tradeoff: temporary duplication and compatibility complexity. Mitigation: explicit mapping, read-only legacy mode, and v4 views/reports.

### Decision: Provider contract first

Rationale: scanner, P/L, probability, and decision logic should not depend on Tradier-specific payloads.

Tradeoff: more upfront design. Mitigation: keep MVP provider interface minimal.

### Decision: Tradier direct first

Rationale: current broker MCP/control plane does not expose normalized option-chain enumeration with greeks; Tradier direct API appears viable.

Tradeoff: local provider code before shared broker-platform integration. Mitigation: isolate provider behind contract and persist raw payloads.

### Decision: Conservative pricing by default

Rationale: paper trading should not overstate returns.

Tradeoff: some paper fills may be worse than achievable live execution. Mitigation: report bid/ask/mid and policy price separately.

### Decision: Include `DATA_UNAVAILABLE`

Rationale: data failure is not a strategy rejection and must not pollute confidence metrics.

Tradeoff: more decision statuses. Mitigation: separate strategy status from data status if UI/reporting needs simplification.

### Decision: Paper lifecycle shares live lifecycle semantics

Rationale: future live trading should not require schema redesign.

Tradeoff: more tables than a simple paper-trade table. Mitigation: MVP uses only the subset needed for paper path.

### Decision: Defer multi-agent runtime orchestration

Rationale: service boundaries matter more than agent runtime complexity in MVP.

Tradeoff: less visible agent architecture early. Mitigation: module boundaries match agent responsibilities.

## 22. Open Questions

P0 before engineering:
- What exact symbol should the MVP use: `AA`, latest short-list symbol, or operator-supplied symbol?
- What is the exact expiration selection rule and acceptable DTE range?
- What are the short call, short put, and protective put delta targets/bands?
- How is the protective put selected: delta, distance, premium ratio, max debit, or another rule?
- What is the minimum acceptable liquidity threshold for spread width, OI, volume, bid, and missing greeks?
- What is the approved default pricing policy for paper fills?
- What are the exact P/L formulas and capital model?
- What is the first probability model and IV selection policy?
- Should commissions/fees be included in MVP calculations?
- How should `DATA_UNAVAILABLE` appear in reports and confidence metrics?
- Should current `entry_decisions` be extended or should v4 decisions use `entry_decisions_v4`?

P1 before full paper run:
- What are Large and Small capital assumptions?
- What are Large and Small max concurrent position limits?
- What is the duplicate-symbol policy across Large and Small books?
- What is the sector/theme taxonomy source?
- What monitoring cadence is required for paper trades?
- What paper assignment simulation policy should be used?
- What are initial confidence scoring thresholds?

P2 before shadow/live:
- What sample size and performance metrics are required before shadow mode?
- What sample size and performance metrics are required before live mode?
- Which broker account IDs are allowed for live trading?
- What are max order size, max notional, max contracts, and max buying-power limits?
- Who can approve live orders and how is identity recorded?
- What is the reconciliation process when broker state conflicts with BullStrangle state?

## 23. Engineering Readiness Checklist

Engineering should not start the v4 MVP until these are approved:
- Provider contract and typed error model.
- Tradier provider normalization spec.
- Additive v4 schema migration plan.
- Pricing policy.
- Strike-selection policy.
- P/L formula spec.
- Probability model spec.
- Decision evidence schema.
- Paper lifecycle state machine.
- Live safety design, even with live out of scope.
- One-symbol MVP acceptance fixture.

## 24. MVP Acceptance Criteria

MVP is complete when:
- One selected newsletter symbol can be scanned with Tradier live data.
- Live stock quote and option chain are normalized and persisted.
- Selected legs are persisted with source option-chain rows and pricing policy.
- P/L and probability outputs are calculated and persisted with versions and assumptions.
- Entry decision is produced with status, evidence, and explanation.
- Paper trade intent, order draft, simulated fill, and lifecycle event are created.
- A report can replay the decision from stored data.
- Provider failure produces `DATA_UNAVAILABLE`.
- Paper fill prices are no more favorable than policy prices.
- No live order can be submitted.
- OS Excel is not required for the MVP path.

## 25. Summary

v4 keeps the useful v3 foundation and replaces the brittle execution data plane. The refactor should be built around a narrow, replayable, paper-only vertical slice: newsletter candidate, Tradier quote/chain, live strike selection, conservative pricing, internal P/L, internal probability, explainable decision, and shared execution lifecycle records.

The architecture is intentionally live-ready but not live-enabled. Live trading is a later phase gated by paper evidence, explicit confidence thresholds, broker reconciliation, operator approval, and hard safety controls.
