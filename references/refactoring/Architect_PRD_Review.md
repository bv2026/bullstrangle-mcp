# BullStrangle Architect PRD Review

Status: Architecture Review
Date: 2026-05-25
Reviewed artifacts:
- `BullStrangle_Product_Spec_Refactor_PRD.md`
- `BullStrangle_Refactor_Design_Notes.md`
- `diagrams/bullstrangle_agents_architecture.svg`
- `diagrams/bullstrangle_db_architecture.svg`

## Executive Assessment

The PRD is directionally sound. It correctly shifts BullStrangle from an artifact-centric newsletter and Option Samurai workflow into a strategy operating layer built around newsletter candidates, live option chains, internally calculated P/L and probability, paper trading, outcome attribution, and future live-trading readiness.

The main architecture concern is scope compression. The PRD asks for a live scanner, provider abstraction, normalized market snapshots, P/L engine, probability engine, rule catalog, decision engine, portfolio layer, paper execution lifecycle, monitoring, scenario attribution, confidence scoring, and future live execution schema. That is the right target architecture, but engineering should not start until the first vertical slice is narrowed to a minimal contract and state model.

Recommendation: approve the product direction, but do not approve implementation until the P0 decisions in this review are resolved. The MVP should be one-symbol, paper-only, Tradier-backed, additive-schema, and replayable. Everything else should hang off that spine.

## Critical Architecture Findings

| Area | Finding | Severity | Required Action |
|---|---|---:|---|
| Scope | MVP includes too many new domains unless bounded to one-symbol paper lifecycle only. | High | Lock MVP to quote, chain, selected legs, P/L, probability, decision, trade intent, order draft, simulated fill, replay report. |
| Schema | PRD lists many tables but not primary keys, foreign keys, uniqueness, state transitions, or event semantics. | High | Produce v2 ERD/table spec before coding. |
| Execution safety | Live-trading guardrails are stated but not sufficient for broker integration. | High | Define disabled-by-default live mode, approval semantics, idempotency, kill switch, account allowlist, and stale-data blockers. |
| Provider | Tradier is preferred, but provider contract lacks entitlement, rate-limit, stale quote, corporate-action, and greeks-null behavior. | High | Approve normalized provider contract and error model before scanner work. |
| Pricing | P/L, probability, paper fill, and order draft pricing can diverge if pricing policy is not centralized. | High | Define one pricing policy object persisted on every scan/decision/fill. |
| Rule ownership | Many P0 items are marked `Needs Rule Input`. Engineering cannot infer them safely. | High | Confirm strike delta bands, liquidity thresholds, P/L formulas, pricing, portfolio sizing, and probability assumptions. |
| Existing system | Current DB has legacy OS/gate tables and migrations; PRD does not specify coexistence mapping. | Medium | Use additive v2 tables and compatibility views/adapters, not destructive migration. |
| Agents | Multi-agent model is useful conceptually but can over-architect the implementation. | Medium | Implement modules/services first; expose agents later if needed. |

## Unclear, Conflicting, Missing, Or Over-Scoped Requirements

### Unclear Requirements

- `Four-week target expiration` needs exact selection logic: nearest listed expiration to 28 calendar days, minimum DTE, max DTE, weekly/monthly preference, holiday handling, and what to do when no chain exists.
- `Live stock price` is ambiguous: last, bid/ask mid, mark, NBBO midpoint, previous close, or provider quote field.
- `Capital required` is not defined for a bull strangle with long stock, short call, short put, and protective put. It must specify buying-power model, cash-secured assumption, margin assumption, and whether assignment reserve is included.
- `Maximum modeled loss` is unclear because the protective put limits one downside leg but the strategy also includes stock ownership and short put assignment behavior.
- `Probability of profit` needs a payoff definition, transaction cost handling, and whether it is expiration-only or path-aware.
- `Confidence level` is listed but not calibrated. It needs either deterministic thresholds for MVP or should be deferred.
- `Portfolio fit` needs concrete rules for cash, buying power, sector/theme exposure, duplicate symbols, and assignment capacity.
- `Newsletter intelligence` extraction asks for thesis, risk posture, caution language, week-over-week changes, and confidence signals. This is valuable but not defined enough for deterministic acceptance tests.

### Conflicting Requirements

- The PRD says the product should not replace Darren's watchlist scanner in the first refactor, but also requires live strike selection using strategy delta rules in P0. This is acceptable only if the universe remains newsletter-derived and live selection only chooses option legs.
- The PRD states provider abstraction is required, but MVP says provider abstraction beyond isolating Tradier is not included. The correct compromise is a minimal interface with only quote, chain, health, and normalized errors.
- Paper trading is required before live trading, but MVP includes order draft and lifecycle concepts. That is fine if order drafts are broker-neutral and no broker submission path exists in MVP.
- Option Samurai is fallback only, but newsletter replication mode references published strikes and OS benchmark fields. The architecture must keep OS out of the critical decision path while allowing comparison data.
- `Architect confirms no future schema redesign is needed for live trading` is too absolute. The realistic acceptance criterion should be: no lifecycle model rewrite should be needed; additive live-trading tables/columns may still be required.

### Missing Requirements

- No formal lifecycle state machine for candidate, decision, intent, order draft, approval, order, fill, position, lifecycle event, and outcome.
- No data-retention/audit policy for raw provider payloads, normalized snapshots, broker payloads, and generated reports.
- No versioning model for formulas, strategy rules, strike selection rules, pricing policy, and probability model.
- No definition of replay determinism: which inputs must be frozen so a decision can be reproduced exactly.
- No handling for market closed, delayed quotes, halted symbols, missing chains, missing greeks, stale quotes, crossed/locked markets, zero bid, or no open interest.
- No assignment simulation policy for paper trading.
- No commission/fees model.
- No split/dividend/corporate-action handling.
- No account model for live readiness: broker account id, paper account id, portfolio-to-account mapping, buying power source, and account permission validation.
- No concurrency/idempotency requirements for repeated scan runs, duplicate paper trades, duplicate order drafts, or retrying provider calls.
- No explicit user/operator identity model for approvals.

### Over-Scoped Requirements

- Full newsletter intelligence extraction should not block the scanner MVP. Store raw text and current structured fields first; advanced thesis extraction can be P1/P2.
- Multi-agent orchestration should not be the first implementation unit. Build deterministic services with stable contracts first.
- System confidence metrics should not be P1 unless simplified. Meaningful system confidence needs closed trade samples and should mature after paper history exists.
- Full monitoring and all scenario recommendations are too broad for MVP. MVP only needs lifecycle records that can support monitoring later.
- Shadow trading and live order schema should be designed now, but implementation should wait until paper lifecycle is stable.

## Schema Risks

### Coexistence With Current Schema

Current implementation already has core artifact tables (`newsletters`, `newsletter_full_text`, `watchlist_entries`, `short_list_entries`), OS workflow tables (`os_workbooks`, `os_evaluation_runs`, `os_evaluation_rows`, `watchlist_deviations`, aggregates), and v3 gate/lifecycle tables (`strategy_rule_catalog`, `position_books`, `cycle_layers`, `entry_decisions`, `exit_decisions`).

Risk: introducing `entry_decisions_v2`, `paper_trades`, and execution tables without mapping current entities can create duplicate truths.

Architecture decision: v2 should be additive. Current tables should remain source of truth for artifact ingestion. New v2 decision and execution tables should reference existing `newsletter_id`, `watchlist_entry_id`, and `short_list_entries` where possible. Legacy OS/gate tables should be read-only compatibility inputs during transition.

### Table Design Risks

- `live_option_chains` as a single flat table may become large quickly. It needs a run/snapshot parent and row child structure, indexed by provider, symbol, expiration, quote timestamp, right, and strike.
- Option contracts need stable identifiers. Symbol, expiration, right, and strike are not enough for all providers unless OCC symbol/root/multiplier are stored.
- Prices need decimal precision policy. SQLite `REAL` can introduce rounding drift for P/L. Store normalized decimal strings or integer cents where correctness matters.
- Rule catalog needs version validity (`effective_from`, `effective_to`, `status`) and immutable evaluated rule snapshots. A mutable catalog alone is not replayable.
- P/L and probability evaluations should store formula/model version, input snapshot references, and assumptions JSON. Storing only outputs is insufficient.
- `trade_scorecards` should not be the only place for decision evidence. Rule evidence, data quality evidence, and calculation evidence need normalized or structured JSON records tied to the decision.
- `paper_trades` risks duplicating `trade_intents`. Prefer `trade_intents` plus execution mode and fill source, with portfolio-specific projections/views if possible.
- `live_positions` should not be a strategy-only position table after broker fills. It needs reconciliation to broker account positions and should distinguish broker-synced positions from strategy-intended positions.
- Assignment events must be first-class and many-to-one with trade/position lifecycle. Assignment can be partial.
- Fills must support partial fills, per-leg fills, commissions, fees, and fill source. A single fill row per order is not enough.
- `operator_approvals` must be immutable and scoped to exact order draft version. Approval should not silently carry over if price, quantity, account, or legs change.

### Migration Risks

- Existing migrations are additive and should stay that way. Do not rewrite `SCHEMA_SQL` as the only migration path.
- Historical OS and gate decisions use different semantics than v2 `ACCEPT/WATCH/REJECT`. Backfilling them into v2 without marking source/version would pollute evidence.
- Current `cycle_layers` has some lifecycle concepts, but it is not sufficient for shared paper/live execution. It should either be deprecated behind a compatibility view or explicitly mapped to the new lifecycle.
- Current `strategy_rule_catalog` exists but may not support rule classification, retirement, effective dating, or immutable snapshots. Extending it is safer than creating a parallel unlinked rule catalog.

## Workflow Risks

- The workflow assumes newsletter ingestion has already extracted a reliable candidate universe. PDF parsing quality remains a dependency and should keep ingestion quality warnings in the scan report.
- Live scan timing matters. Running outside market hours or with delayed data can materially change candidate quality.
- Newsletter replication and live strike-selection are different products. Comparing them is valuable, but the decision engine must know which mode generated each candidate.
- Re-running a scanner can create duplicate decisions or paper trades unless scan runs, selected candidates, trade intents, and order drafts have idempotency keys.
- `DATA_UNAVAILABLE` is mentioned operationally but not in the decision status set. Add either a fourth decision status or a separate data status that blocks `ACCEPT`.
- Portfolio rules can change a symbol decision from acceptable to not actionable. The system should distinguish `strategy_decision` from `portfolio_actionability`.
- Scenario attribution depends on monitoring and fills. It cannot be accurate if paper fills are unrealistic or marks are sparse.
- Accepted-vs-rejected outcome comparison requires storing rejected candidates and their selected hypothetical legs through expiration. This must be designed at MVP time if confidence reporting is expected later.

## Live-Trading Safety Gaps

Live trading should remain impossible in MVP. Future live readiness needs stronger explicit guardrails than the PRD currently states.

Required before any live path exists:

- Global live-trading feature flag defaulted off.
- Separate environment/config flag for order submission, independent of shadow mode.
- Account allowlist and portfolio-to-account mapping.
- Operator approval tied to an immutable order draft version.
- Idempotency key/client order id generated before submission and persisted.
- Stale-data hard block for live orders.
- Quote freshness threshold and market-hours validation.
- Max order size, max contracts, max notional, max buying-power usage, and max loss guardrails.
- Duplicate-order prevention across retries and process restarts.
- Broker response and request payload audit storage.
- Pre-submit validation that broker account positions match expected strategy state, or explicit override.
- Kill switch that prevents new live submissions while preserving read-only reconciliation.
- Dry-run/shadow mode that exercises order construction without broker submission.
- Manual override/audit trail for approvals, cancellations, and rejected broker orders.

Additional live-trading concern: broker-synced positions becoming source of truth after live fills is correct, but the PRD must specify reconciliation behavior when broker state conflicts with BullStrangle state.

## Provider And Data Risks

- Tradier greeks, IV, volume, and open interest may be missing, delayed, or stale depending on entitlement and market state.
- Option chains may include adjusted contracts, weeklies, non-standard roots, or contracts with zero bid/ask. Selection logic must filter these deliberately.
- Provider timestamp semantics vary. The contract must distinguish provider quote timestamp, retrieval timestamp, and scan run timestamp.
- Bid/ask spread calculations require consistent handling of zero bid, null ask, crossed markets, and wide markets.
- Rate limits can affect full-watchlist scans. The provider layer needs backoff, partial-run status, and resumability.
- Earnings data from newsletters may not be current enough for live entry. If earnings are a hard safety rule, a live earnings provider or explicit stale warning is needed.
- Dividend assumptions affect probability and early assignment risk for calls. The initial probability model can ignore dividends only if this assumption is stored and reported.
- OS benchmark values are not authoritative live data. They should be stored with source and timestamp and never overwrite live provider snapshots.
- Provider abstraction should not flatten away useful raw fields. Store raw payload JSON alongside normalized fields for audit/debug.

## Decisions Required Before Engineering Starts

### P0 Product And Strategy Decisions

- Confirm MVP symbol selection process: manual selected newsletter symbol, latest short-list symbol, or configured input.
- Confirm exact target expiration selection rule and acceptable DTE range.
- Confirm delta bands/targets for short call, short put, and protective put.
- Confirm protective put selection rule: delta, strike distance, premium ratio, max debit, or other.
- Confirm default pricing policy for paper fills and P/L: conservative bid for shorts and ask for longs is recommended for MVP.
- Confirm liquidity thresholds: minimum bid, maximum spread, minimum OI, minimum volume, and missing-greeks behavior.
- Confirm P/L formulas for total credit, capital required, downside breakeven, called-away profit, put-assigned cost basis, max modeled loss, return on capital, and annualized return.
- Confirm first probability model and assumptions: lognormal expiration model, IV source, risk-free rate, dividend assumption, DTE convention, and transaction costs.
- Confirm Gate 7 representation: retired/advisory by default, never hard reject unless rule version explicitly enables it.
- Confirm Large/Small portfolio sizing assumptions for paper mode.

### P0 Architecture Decisions

- Use additive v2 schema coexisting with current artifact and OS/gate tables.
- Define normalized market data provider interface and typed errors.
- Define scan run, option chain snapshot, selected leg, P/L evaluation, probability evaluation, and decision table contracts.
- Define immutable rule/policy/model versioning and evaluated snapshots.
- Define decision status model, including how `DATA_UNAVAILABLE` is represented.
- Define lifecycle state machine for paper now and live later.
- Define idempotency keys for scan runs, trade intents, order drafts, and future broker orders.
- Define decimal/rounding policy for prices and P/L.
- Define replay contract: minimum persisted inputs required to reproduce decision outputs.

### P1 Decisions That Can Follow MVP Design But Precede Full Paper Run

- Full portfolio allocation and exposure model.
- Sector/theme taxonomy source.
- Duplicate symbol policy across Large and Small books.
- Monitoring cadence and mark price policy.
- Scenario classification automation details.
- Confidence scoring formula and thresholds.
- Reporting formats beyond the one-symbol replay report.

## What Can Be Deferred

- Live broker order submission implementation.
- Broker MCP/control-plane integration for execution.
- Shadow mode implementation, beyond schema compatibility.
- Full dashboard.
- Full newsletter intelligence NLP extraction.
- Automated exit recommendations.
- System-level confidence thresholds for shadow/live promotion.
- Provider implementations beyond Tradier.
- OS deprecation completion. Keep OS as benchmark/fallback until live scanner has enough paper evidence.
- Advanced portfolio optimization and sector/theme concentration logic.
- Historical backtesting of all legacy newsletters under the new model.
- Multi-agent runtime orchestration. Use service boundaries first.

## Recommended MVP Boundary

The MVP should implement one vertical slice only:

1. Choose one existing `watchlist_entries` row from an ingested newsletter.
2. Pull a live quote from Tradier through a minimal provider interface.
3. Pull one expiration option chain from Tradier and persist raw plus normalized snapshot data.
4. Select three legs using provisional approved strike rules.
5. Price the candidate using one persisted pricing policy.
6. Calculate P/L using one versioned formula set.
7. Calculate probability using one documented model.
8. Produce one `ACCEPT`, `WATCH`, `REJECT`, or data-blocked decision with evidence.
9. Create a paper-mode trade intent, order draft, order legs, and simulated fill.
10. Generate a replayable report from persisted data.
11. Prove no live order path exists in MVP.

## Recommended Engineering Readiness Gate

Engineering should start only after these artifacts exist and are approved:

- Provider interface specification.
- V2 additive schema specification with migration/coexistence plan.
- Pricing policy specification.
- Strike selection specification.
- P/L formula specification.
- Probability model specification.
- Decision evidence contract.
- Paper lifecycle state machine.
- Live safety design, even if live implementation is out of scope.
- One-symbol MVP acceptance fixture using `AA` or another selected newsletter symbol.

## Acceptance Criteria Revisions

Replace this acceptance criterion:

- `Architect confirms no future schema redesign is needed for live trading.`

With:

- `Architect confirms the v2 lifecycle model supports paper, shadow, and live execution through additive schema evolution, without rewriting decision, intent, order draft, fill, lifecycle event, or outcome semantics.`

Add these acceptance criteria:

- Every v2 decision links to immutable market data snapshot, rule version, pricing policy, P/L formula version, probability model version, and source newsletter candidate.
- A repeated scan for the same newsletter symbol, mode, provider, expiration, and timestamp bucket cannot create duplicate paper trades without an explicit operator action.
- Live order submission is structurally impossible in MVP and remains disabled by default in later phases.
- Provider failures produce data-blocked decisions, not rejects and not silent skips.
- Paper fills are no more favorable than the configured conservative pricing policy.

## Architecture Recommendation

Proceed with Phase 0 architecture hardening before implementation. The PRD should be revised into a smaller engineering-ready MVP package plus a target architecture appendix. The target architecture is sound, but the implementation plan must be contract-first: provider contract, schema, pricing policy, formulas, probability model, rule versioning, and lifecycle states must be decided before code is written.

The first implementation should be a thin, deterministic, replayable paper-trading spine. Do not build the multi-agent surface, live broker controls, full confidence layer, or full monitoring system until that spine is proven with one symbol and then the full newsletter watchlist.
