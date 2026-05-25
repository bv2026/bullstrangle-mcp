# BullStrangle Refactor Product Requirements

Status: Draft for Architecture Review
Owner: Product
Audience: Architect, Engineering, Strategy Owner

## 1. Product Intent

BullStrangle should evolve from a newsletter/Excel automation tool into a strategy operating system for Darren Carlat's Bull Strangle workflow.

The product must:

- Ingest Darren's newsletter and preserve its market intelligence.
- Use the newsletter watchlist and Large/Small short lists as the candidate universe.
- Replace the brittle manual Option Samurai Excel workflow with live option-chain scanning.
- Evaluate trades using live market data, P/L, probability, and portfolio rules.
- Paper-trade Large and Small portfolios independently before live trading.
- Track trade-management scenarios and realized outcomes.
- Build confidence from evidence, not assumptions.
- Be designed so live trading can be added later without a schema redesign.

The target product is not a generic options scanner. It is a BullStrangle-specific operating layer that respects Darren's newsletter, strategy rules, and portfolio-management process.

## 2. Current Product Problems

The current project has become too artifact-centric.

Key problems:

- It parses many artifacts but has limited higher-level reasoning on top of ingested artifacts.
- Newsletter content contains rich market intelligence, but most downstream use is focused on watchlist extraction.
- Option Samurai Excel workflow is manual, brittle, and repeatedly re-ingested.
- Current gate logic can over-filter trades, especially Gate 7 moving-average alignment.
- Current workflow does not create a durable feedback loop to learn whether decisions work.
- Portfolio management and confidence scoring are not first-class product concepts.
- There is no clear transition path from paper trading to shadow trading to live trading.

## 3. Product Vision

Target workflow:

`newsletter intelligence -> live scanner -> P/L + probability -> entry decision -> paper portfolio -> monitoring -> outcome attribution -> confidence scoring`

Live-trading-ready workflow:

`entry decision -> trade intent -> order draft -> operator approval -> paper fill or live broker order -> fills -> position lifecycle -> outcome`

Option Samurai should become a temporary fallback and benchmark, not the strategic operating workflow.

## 4. Product Principles

- Darren's newsletter remains the primary source of candidate symbols and market thesis.
- The system should not attempt to replace Darren's watchlist scanner in the first refactor.
- Live execution quality should be determined from live option-chain data.
- Strike selection should be live when creating an executable trade.
- Greeks are inputs, not final probability answers.
- Probability and P/L must be calculated internally and stored with assumptions.
- Large and Small portfolios must be managed separately.
- Paper trading and live trading must use the same lifecycle model.
- Human approval is required before any live order submission.
- The product should be provider-agnostic: Tradier may be first, but the core should depend on a market-data provider contract.

## 5. Users And Jobs To Be Done

Primary user:

- Strategy operator managing BullStrangle candidates, entries, monitoring, and exits.

Jobs:

- Ingest the weekly newsletter and understand market context.
- See Darren's watchlist and Large/Small short-list candidates.
- Generate live executable trade candidates from current market data.
- Understand why a trade is accepted, watched, or rejected.
- Paper-trade the strategy before risking capital.
- Monitor open paper or live positions against Darren's trade-management scenarios.
- Build confidence that the automated system matches or improves the strategy process.

## 6. Functional Requirements

### 6.1 Newsletter Intelligence

The system shall ingest newsletter PDFs and persist:

- Full raw text by section.
- Watchlist with published prices, IV, earnings, strikes, and premiums.
- Large and Small short-list entries.
- Market environment metrics.
- Market commentary and thesis.
- Strategy reference text when present.
- Source page/span or lineage for extracted facts.

The system shall extract higher-level newsletter intelligence:

- Market thesis.
- Risk posture.
- Sector or theme emphasis.
- Caution/warning language.
- Week-over-week changes.
- Confidence or uncertainty signals from the newsletter text.

### 6.2 Strategy Rules

The system shall maintain a versioned strategy rule catalog.

Rules shall be executable or advisory:

- Hard rules reject trades.
- Soft rules create warnings or watch status.
- Advisory rules provide context only.

Gate 7 moving-average alignment shall be treated as a retirement candidate in the refactor:

- It shall not reject trades in the redesigned entry flow unless explicitly re-enabled.
- Moving-average alignment may be retained as advisory evidence.
- Option Samurai SMA fields shall not be required for entry decisions.

### 6.3 Market Data Provider

The system shall define a market-data provider contract independent of any broker MCP.

Minimum provider capabilities:

- Get live stock quote for a symbol.
- Get option chain for symbol and expiration.
- Return option rows with right, strike, bid, ask, mid, delta, IV, volume, open interest, and timestamp.
- Report provider status, freshness, and errors.

Initial provider:

- Tradier direct API is the preferred first implementation.
- A live test with `AA` and expiration `2026-06-18` returned 86 option contracts with greeks and matched newsletter/OS prices closely.

Provider constraints:

- Do not make BullStrangle core depend directly on `schwab-mcp-file`.
- Do not make the broker control plane a hard dependency for phase 1.
- Future providers may include broker MCP, Webull OpenAPI, Polygon, Intrinio, or OS fallback.

### 6.4 Live Watchlist Scanner

The scanner shall support two modes.

Newsletter replication mode:

- Use Darren's published strikes.
- Refresh live bid/ask/greeks.
- Determine whether the published trade is still executable.

Live strike-selection mode:

- Use live stock price.
- Use four-week target expiration.
- Pull live option chain.
- Select sell call, sell put, and protective put using strategy delta rules and liquidity constraints.
- Calculate live total credit and derived metrics.

Live strike-selection mode is the target execution workflow.

### 6.5 P/L Engine

The system shall calculate P/L for every candidate trade.

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

The P/L engine shall support accept/watch/reject decisions based on product-defined thresholds.

### 6.6 Probability Engine

The system shall calculate probability metrics internally.

Required outputs:

- Probability of profit.
- Probability short call expires OTM.
- Probability short put expires OTM.
- Probability stock finishes between short strikes.
- Model name.
- Model assumptions.
- Input IV and timestamp.

OS probability fields, if available, shall be used only for benchmark comparison during transition.

### 6.7 Entry Decision

The system shall produce an entry decision for each candidate:

- `ACCEPT`
- `WATCH`
- `REJECT`

Each decision shall include:

- Rule evidence.
- P/L summary.
- Probability summary.
- Liquidity summary.
- Portfolio fit.
- Confidence level.
- Human-readable explanation.

### 6.8 Portfolio Management

The system shall manage two independent strategy books:

- Large portfolio.
- Small portfolio.

The portfolio layer shall track:

- Current and target positions.
- Maximum concurrent positions.
- Allocation per symbol.
- Allocation per sector or theme.
- Assignment capacity.
- Cash or buying power reserved.
- Duplicate exposure across portfolios.
- Portfolio-level rule violations.

### 6.9 Paper Trading

The system shall paper-trade Large and Small portfolios before live trading.

Paper trades shall use:

- Live market data at decision time.
- Simulated order drafts.
- Simulated fills.
- The same lifecycle model intended for live trades.

Paper trading shall track:

- Entry assumptions.
- Marks over time.
- Exit triggers.
- Assignment scenarios.
- Realized or modeled P/L.
- Outcome category.

### 6.10 Trade Management Scenarios

The system shall model Darren's five trade-management scenarios:

- `EARLY_CALL`
- `EARLY_ASSIGNMENT`
- `STOCK_CALLED_AWAY`
- `OPTIONS_EXPIRED_STOCK_KEPT`
- `STOCK_ASSIGNED`

Scenario rules:

- Early call: close naked put around `$0.05` to `$0.10` where available, otherwise wait for put expiration.
- Early assignment: sell all shares and close naked call around `$0.05` to `$0.10` where available, otherwise wait for call expiration.
- Stock called away: best-case maximum-profit closure, no action required.
- Options expire and stock is kept: usually continue holding and sell next-cycle calls/puts, but compare against better candidates.
- Stock assignment: usually sell all shares and find a new candidate; if still desired, sell half and restart.

The system shall maintain a scenario scoreboard:

- Count by scenario.
- Percent by scenario.
- Realized P/L by scenario.
- Large versus Small breakdown.

### 6.11 Confidence Scoring

The system shall produce confidence at two levels.

Trade confidence:

- Data freshness score.
- Liquidity score.
- P/L attractiveness score.
- Probability score.
- Newsletter alignment score.
- Rule-compliance score.
- Portfolio-fit score.
- Final confidence level: `HIGH`, `MEDIUM`, `LOW`, or `REJECT`.

System confidence:

- Win rate.
- Average return.
- Max drawdown.
- Assignment frequency.
- Called-away rate.
- Expected-vs-realized P/L.
- Accepted-vs-rejected outcome comparison.
- Large portfolio versus Small portfolio performance.
- Newsletter replication versus live strike-selection performance.

Confidence shall be learned from paper-trading history before live trading is enabled.

### 6.12 Execution And Live Trading Readiness

The schema shall support live trading later without redesign.

Required lifecycle:

- Entry decision.
- Trade intent.
- Order draft.
- Operator approval.
- Paper fill or live broker order.
- Fills.
- Position lifecycle.
- Outcome.

Live trading guardrails:

- No live order shall be submitted without explicit operator approval.
- Broker responses and payloads shall be stored for auditability.
- Broker-synced positions shall become source of truth after live fills.
- Paper and shadow modes shall remain available after live mode exists.
- Live mode shall remain disabled until confidence thresholds are met.

## 7. Non-Functional Requirements

Auditability:

- Every decision must be traceable to newsletter, rules, market data, provider, and timestamp.

Provider independence:

- Core logic must not depend on a specific broker or market-data vendor.

Explainability:

- Every accept/watch/reject decision must have human-readable reasoning.

Reproducibility:

- Saved market snapshots must allow later replay of decisions.

Safety:

- Live order submission must require human approval and idempotency controls.

Incremental delivery:

- Product must be deliverable in vertical slices.

## 8. Proposed Data Domains

Artifact domain:

- newsletters
- newsletter_full_text
- watchlist_entries
- short_list_entries
- os_evaluation_rows as fallback only

Knowledge domain:

- newsletter_intelligence
- strategy_rule_catalog
- trade_management_rules
- market_environment

Market data domain:

- market_data_runs
- live_option_chains
- live_watchlist_snapshots
- provider_health

Decision domain:

- pl_evaluations
- probability_evaluations
- entry_decisions_v2
- trade_scorecards

Execution domain:

- trade_intents
- order_drafts
- order_draft_legs
- operator_approvals
- broker_orders
- broker_order_legs
- fills
- live_positions
- assignment_events
- trade_lifecycle_events
- trade_outcomes

Portfolio/confidence domain:

- paper_portfolios
- paper_trades
- paper_trade_marks
- portfolio_snapshots
- system_confidence_metrics

## 9. Proposed Agent Model

- Ingestion Agent.
- Newsletter Intelligence Agent.
- Strategy Rule Agent.
- Market Data Agent.
- Live Scanner Agent.
- P/L and Probability Agent.
- Entry Decision Agent.
- Portfolio Manager Agent.
- Paper Trading Agent.
- Execution Agent.
- Monitoring Agent.
- Outcome Attribution Agent.
- Confidence Agent.
- Reporting/Briefing Agent.

## 10. MVP Scope

MVP shall prove one thin vertical slice:

1. Select one newsletter symbol.
2. Pull live stock quote from Tradier.
3. Pull live option chain from Tradier.
4. Select live strikes using provisional delta rules.
5. Calculate P/L and probability.
6. Produce accept/watch/reject decision.
7. Create paper trade intent and simulated fill.
8. Store enough data to replay and explain the decision.

MVP shall not include:

- Live order submission.
- Full dashboard.
- Full automated exit management.
- Provider abstraction beyond what is required to isolate Tradier.
- Replacement of all current reports.

## 11. Phased Roadmap

Phase 0: Architecture hardening

- Architect reviews this PRD.
- Define final provider contract.
- Define v2 schema.
- Define rule thresholds.
- Define P/L and probability formulas.
- Define confidence scoring MVP.

Phase 1: One-symbol vertical slice

- Tradier quote and chain retrieval.
- Live strike selection.
- P/L and probability output.
- Paper trade intent.
- Explainable decision.

Phase 2: Full watchlist paper run

- Run all newsletter symbols.
- Generate live watchlist snapshot.
- Create Large and Small paper books.
- Produce paper entry report.

Phase 3: Monitoring and scenarios

- Update marks.
- Detect trade-management scenarios.
- Track expiration and assignment outcomes.
- Build scenario scoreboard.

Phase 4: Confidence reporting

- Expected-vs-realized metrics.
- Accepted-vs-rejected comparison.
- Large versus Small comparison.
- Rule attribution.

Phase 5: Shadow trading

- Generate order drafts and approvals.
- Do not submit live orders.
- Compare system recommendations with operator action.

Phase 6: Live trading readiness

- Enable broker execution only after explicit approval, guardrails, and confidence thresholds.

## 12. Acceptance Criteria

Architecture acceptance:

- Architect confirms no future schema redesign is needed for live trading.
- Architect confirms provider interface isolates Tradier.
- Architect confirms paper, shadow, and live execution share one lifecycle.

Product acceptance:

- User can see why each trade is accepted, watched, or rejected.
- User can compare Darren published strikes versus live strike selection.
- User can paper-trade Large and Small portfolios separately.
- User can track outcomes using Darren's scenario taxonomy.
- User can see confidence metrics improve or deteriorate over time.

MVP acceptance:

- For a selected symbol, the system can reproduce the Tradier chain test manually observed for `AA`.
- The system can produce a complete decision record with market data, selected legs, P/L, probability, and explanation.
- The system can create a paper trade lifecycle record without live execution.

## 13. Risks

Decision quality risk:

- Technical chain data may work, but rules may be poorly calibrated.

Probability model risk:

- Internal probability may differ from OS or Darren expectations.

Provider risk:

- Tradier rate limits, data quality, auth, or greeks availability may affect reliability.

Overbuilding risk:

- Multi-agent architecture can become too complex if not delivered in thin slices.

False confidence risk:

- Paper trading must account for bid/ask, slippage, liquidity, and assignment behavior.

Live trading safety risk:

- Live mode must remain disabled until approval and confidence controls are mature.

## 14. Open Questions For Architect

- Should v2 schema coexist with current tables or migrate current tables in place?
- Should Tradier direct provider live inside BullStrangle first, or should broker platform be extended first?
- What is the minimum normalized option-chain contract?
- What pricing policy should the scanner use: bid, ask, mid, or conservative executable price?
- What delta bands should live strike-selection use for each leg?
- What is the minimum acceptable liquidity threshold?
- What is the first probability model and what assumptions must be stored?
- How should Gate 7 be represented in the rule catalog after retirement as a hard gate?
- How should Large and Small portfolio sizing rules be represented?
- What confidence threshold is required before shadow mode?
- What confidence threshold is required before live mode?

