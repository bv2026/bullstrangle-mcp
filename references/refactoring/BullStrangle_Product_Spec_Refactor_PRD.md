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
- Be implemented as a new self-contained project from scratch.
- Use PostgreSQL as the primary runtime database.
- Treat the legacy BullStrangle runtime and legacy SQLite database as import/context sources only, never runtime dependencies.
- Finalize the new project identity and GitHub repository before implementation begins.

The target product is not a generic options scanner. It is a BullStrangle-specific operating layer that respects Darren's newsletter, strategy rules, and portfolio-management process.

Recommended implementation identity:

- Product name: `BullStrangle Platform`
- GitHub repository: `bullstrangle-platform`
- Python package: `bullstrangle_platform`
- PostgreSQL schema namespace: `bullstrangle`
- CLI command namespace: `bs-platform`
- MCP server name: `bullstrangle_platform_mcp`

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
- The refactor should be a new self-contained project with its own package, PostgreSQL schema, migrations, MCP server, configuration, provider abstraction, and tests.
- The legacy BullStrangle runtime must remain untouched and operational during the refactor.
- Legacy SQLite data may be read only through explicit one-way import/migration steps.
- The new runtime must not import legacy modules or query legacy SQLite tables at runtime.

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
- That `AA` test is a frozen regression/benchmark fixture only. The operational MVP should use the current newsletter screenshot/table available at implementation time.

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
- `DATA_UNAVAILABLE`

`DATA_UNAVAILABLE` is a first-class decision state for provider failure, stale data, missing chain, missing critical fields, or missing eligible expiration. It is not a strategy rejection and must not pollute rejected-trade outcome metrics.

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
- Live mode shall require a separate documented Product Owner approval milestone before it can be enabled. Engineering configuration alone shall not be sufficient to enable live order submission.

## 7. Non-Functional Requirements

Auditability:

- Every decision must be traceable to newsletter, rules, market data, provider, and timestamp.

Provider independence:

- Core logic must not depend on a specific broker or market-data vendor.

Legacy isolation:

- New runtime logic must not depend on legacy BullStrangle modules, legacy SQLite tables, or Option Samurai Excel.
- Legacy code and data may be used only for documentation/context or explicit one-way import into PostgreSQL.

Database platform:

- PostgreSQL is required for the new runtime.
- SQLite is allowed only as a legacy import source.

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
- entry_decisions
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

MVP shall prove one thin vertical slice from a current-newsletter table fixture:

1. Capture the current newsletter watchlist table from screenshot/PDF/table input.
2. Create a temporary/current newsletter fixture table from the captured rows.
3. Process symbols sequentially using the newsletter expiration and published row values.
4. Pull live stock quote from Tradier.
5. Pull live option chain from Tradier.
6. Try newsletter replication using published strikes.
7. Optionally run live strike-selection mode using provisional delta rules.
8. Calculate P/L and probability for symbols with sufficient data.
9. Produce accept/watch/reject/data-unavailable decisions.
10. Create paper trade intent and simulated fill for at least one valid symbol.
11. Store enough data to replay and explain the decisions.

MVP shall not include:

- Live order submission.
- Full dashboard.
- Full automated exit management.
- Provider abstraction beyond what is required to isolate Tradier.
- Replacement of all current reports.
- Full newsletter ingestion.
- Legacy SQLite import as a prerequisite for MVP.
- OCR-grade screenshot ingestion. Manual correction/table entry is acceptable for MVP.

## 11. Phased Roadmap

Product milestones:

1. Foundation and PostgreSQL schema.
2. Current-newsletter fixture MVP.
3. Full watchlist paper run.
4. Monitoring and outcomes.
5. Confidence reporting.
6. Shadow mode.
7. Live readiness.

Live readiness requires a separate documented Product Owner approval milestone. Engineering configuration alone shall not enable live order submission.

Phase 0: Architecture hardening

- Architect reviews this PRD.
- Define final provider contract.
- Define PostgreSQL target schema.
- Define rule thresholds.
- Define P/L and probability formulas.
- Define confidence scoring MVP.

Phase 1: Current-newsletter fixture vertical slice

- Current newsletter screenshot/table fixture capture with manual correction.
- Sequential symbol scan with `DATA_UNAVAILABLE` skip-and-continue behavior.
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

- Given a current newsletter screenshot/table fixture, the system can scan symbols sequentially until at least one symbol completes live quote, option chain, selected legs, P/L, probability, decision, and paper lifecycle.
- Symbols that cannot be evaluated due to missing/stale provider data are marked `DATA_UNAVAILABLE` with reason and do not block the rest of the run.
- The frozen `AA` example may be retained as a regression/benchmark fixture, but it is not the operational MVP source.
- The system can produce complete decision records with market data, selected legs, P/L, probability, and explanation.
- The system can create a paper trade lifecycle record without live execution.
- The system uses PostgreSQL as the runtime database.
- The system has no runtime dependency on legacy modules, legacy SQLite, or Option Samurai Excel.

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
- Live mode must not be enabled by engineering configuration alone; it requires a documented Product Owner approval milestone.

## 14. Open Questions For Architect

- Confirm final GitHub repository creation timing and owner for `bullstrangle-platform`.
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

## 15. Requirement Priority Legend

Priorities:

- `P0`: Required for the first usable vertical slice.
- `P1`: Required for full paper-trading workflow.
- `P2`: Required before shadow or live-trading readiness.
- `P3`: Useful enhancement after core workflow is stable.

Requirement states:

- `Defined`: product requirement is clear enough for architecture design.
- `Needs Rule Input`: requires strategy-owner confirmation.
- `Needs Architecture`: requires schema, module, or platform design decision.

## 16. Numbered Product Requirements

### 16.1 Artifact And Newsletter Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-ART-001 | P0 | System shall ingest weekly newsletter PDF and persist raw full text by section. | Defined | Given a newsletter PDF, the DB contains full text and section records with newsletter id. |
| BS-ART-002 | P0 | System shall extract watchlist rows with symbol, last price, IV, sector, published strikes, published option prices, and returns where present. | Defined | Given a watchlist page, extracted rows match a manual sample for at least five symbols. |
| BS-ART-003 | P0 | System shall extract Large and Small short-list membership independently. | Defined | Given a newsletter, symbols can be queried by portfolio type `large` or `small`. |
| BS-ART-004 | P1 | System shall preserve source lineage for extracted fields including page or section reference. | Needs Architecture | Given any extracted fact, user can trace it back to source section/page. |
| BS-ART-005 | P1 | System shall extract market thesis, risk posture, sector emphasis, cautions, and week-over-week changes. | Needs Architecture | Weekly report contains structured newsletter intelligence beyond watchlist rows. |
| BS-ART-006 | P0 | MVP shall support a current-newsletter screenshot/table fixture path before full PDF ingestion. | Defined | Operator can enter or correct rows from the current newsletter screenshot/table and create a current fixture watchlist. |

### 16.2 Strategy Rule Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-RULE-001 | P0 | System shall maintain versioned strategy rules with hard, soft, and advisory classifications. | Defined | Decision output includes rule version and rule classification for evaluated rules. |
| BS-RULE-002 | P0 | Gate 7 moving-average alignment shall not reject trades in the redesigned flow unless explicitly re-enabled. | Defined | A candidate cannot be rejected solely because OS SMA fields are missing or below threshold. |
| BS-RULE-003 | P1 | System shall expose hard-rule failures separately from soft warnings and advisory evidence. | Defined | Decision explanation separates rejection reasons from warnings and context. |
| BS-RULE-004 | P1 | Rule thresholds shall not be hard-coded inside decision logic where a catalog entry exists. | Needs Architecture | Static/code review shows thresholds loaded from catalog/config for strategy rules. |
| BS-RULE-005 | P1 | Retired or advisory rules shall remain auditable for historical comparison. | Defined | Reports can show that Gate 7 was evaluated as advisory/retired. |

### 16.3 Market Data Provider Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-MD-001 | P0 | System shall define a provider-neutral market data interface. | Needs Architecture | Scanner can call provider interface without importing a broker-specific client in core logic. |
| BS-MD-002 | P0 | Provider shall return live stock quote with bid, ask, last, mark or mid, timestamp, and provider id. | Defined | For at least one current fixture symbol with live data, provider returns stock quote and timestamp. |
| BS-MD-003 | P0 | Provider shall return option chain by symbol and expiration. | Defined | For at least one current fixture symbol and newsletter expiration, provider returns option rows. |
| BS-MD-004 | P0 | Option chain row shall include right, strike, bid, ask, mid, delta, IV, volume, open interest, and quote timestamp where available. | Defined | Returned chain rows include required normalized fields or explicit nulls with provider metadata. |
| BS-MD-005 | P1 | Provider shall report rate-limit, auth, freshness, and partial-data errors in normalized form. | Needs Architecture | Failed provider call returns typed error and does not crash the scan run. |
| BS-MD-006 | P1 | System shall support OS as fallback/benchmark but not as primary live provider. | Defined | Scanner can run without OS workbook ingestion. |

### 16.4 Live Scanner Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-SCAN-001 | P0 | Scanner shall support newsletter replication mode using published strikes and refreshed live prices/greeks. | Defined | For at least one current fixture row, published strikes can be refreshed from Tradier chain. |
| BS-SCAN-002 | P0 | Scanner shall support live strike-selection mode using live stock price and option-chain greeks. | Defined | For at least one current fixture symbol, scanner selects call, short put, and long put from chain. |
| BS-SCAN-003 | P0 | MVP shall use the newsletter-provided expiration from the current fixture table. | Defined | Scan uses fixture expiration and does not move the target date during validation. |
| BS-SCAN-004 | P0 | Scanner shall persist selected legs, source provider, timestamp, pricing policy, and mode. | Needs Architecture | Live snapshot row can reproduce selected legs and price inputs. |
| BS-SCAN-005 | P1 | Scanner shall filter or warn on insufficient liquidity. | Needs Rule Input | Candidate with low OI/volume or wide spread receives warning or rejection according to threshold. |
| BS-SCAN-006 | P1 | Scanner shall compare newsletter replication output versus live strike-selection output. | Defined | Report shows published-strike trade and live-selected trade side by side. |
| BS-SCAN-007 | P0 | Scanner shall continue to the next fixture symbol when one symbol is data-unavailable. | Defined | A symbol with missing chain/bid/ask is marked `DATA_UNAVAILABLE`, and the batch continues. |

### 16.5 Strike Selection Rule Requirements

Initial rule placeholders require strategy-owner confirmation.

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-STRIKE-001 | P0 | Short call shall be selected from live chain by configured positive delta target or band. | Needs Rule Input | Given a delta band, scanner chooses nearest eligible call strike. |
| BS-STRIKE-002 | P0 | Short put shall be selected from live chain by configured negative delta target or band. | Needs Rule Input | Given a delta band, scanner chooses nearest eligible put strike. |
| BS-STRIKE-003 | P0 | Protective put shall be selected by configured delta, premium ratio, or distance rule. | Needs Rule Input | Scanner documents which rule selected the protective put. |
| BS-STRIKE-004 | P1 | Strike selection shall support liquidity tie-breakers. | Needs Rule Input | If two strikes are equally close by delta, scanner chooses more liquid contract. |
| BS-STRIKE-005 | P1 | Strike selection shall record rejected alternative strikes for explainability. | Needs Architecture | Snapshot includes candidate alternatives or an explanation JSON. |

### 16.6 Pricing Policy Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-PRICE-001 | P0 | System shall define pricing policy used for credit calculation. | Needs Rule Input | Decision record states bid, ask, mid, or conservative policy. |
| BS-PRICE-002 | P0 | Default paper-trading price shall be conservative enough to avoid overstated returns. | Needs Rule Input | Paper fill price is not more favorable than configured policy. |
| BS-PRICE-003 | P1 | System shall store raw bid/ask and computed execution price separately. | Defined | DB row contains both raw market data and selected execution price. |
| BS-PRICE-004 | P2 | Shadow/live order drafts shall use limit prices derived from configured execution policy. | Needs Rule Input | Order draft limit credit matches pricing policy output. |

### 16.7 P/L Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-PL-001 | P0 | System shall compute total credit from selected legs. | Defined | Credit equals short call credit plus short put credit minus long put debit. |
| BS-PL-002 | P0 | System shall compute downside breakeven. | Needs Rule Input | Formula is documented and output is stored. |
| BS-PL-003 | P0 | System shall compute called-away profit. | Needs Rule Input | Output matches manual calculation for one sample trade. |
| BS-PL-004 | P0 | System shall compute return on capital and annualized return. | Needs Rule Input | Output matches documented formula for one sample trade. |
| BS-PL-005 | P1 | System shall generate scenario P/L table across expiration prices. | Defined | Candidate report includes P/L rows below put, between strikes, above call. |
| BS-PL-006 | P1 | System shall reject/watch trades based on configured minimum P/L thresholds. | Needs Rule Input | Candidate below threshold receives WATCH or REJECT according to rules. |

### 16.8 Probability Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-PROB-001 | P0 | System shall calculate probability metrics internally, not rely on OS probability fields. | Defined | Probability output exists when OS workbook is absent. |
| BS-PROB-002 | P0 | First probability model shall be documented with assumptions. | Needs Rule Input | Decision record includes model name and input assumptions. |
| BS-PROB-003 | P0 | System shall calculate probability stock finishes between short strikes. | Needs Architecture | Output exists for selected trade with model inputs stored. |
| BS-PROB-004 | P1 | System shall calculate probability short call and short put expire OTM. | Needs Architecture | Output has separate call OTM and put OTM probabilities. |
| BS-PROB-005 | P1 | System shall benchmark internal probabilities against OS values if OS values are available. | Defined | Report shows internal probability versus OS probability for comparison period. |

### 16.9 Decision Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-DEC-001 | P0 | System shall classify each candidate as ACCEPT, WATCH, REJECT, or DATA_UNAVAILABLE. | Defined | Current fixture run produces one of the four statuses for every attempted symbol. |
| BS-DEC-002 | P0 | Decision shall include human-readable explanation. | Defined | User can read why a candidate was accepted, watched, rejected, or marked data-unavailable. |
| BS-DEC-003 | P0 | Decision shall link to market data snapshot, P/L evaluation, probability evaluation, and rules. | Needs Architecture | Decision can be replayed from stored references. |
| BS-DEC-004 | P1 | Decision shall include component scorecard and confidence level. | Defined | Decision output includes freshness, liquidity, P/L, probability, rule, portfolio-fit scores. |
| BS-DEC-005 | P1 | Rejected trades shall be retained for later outcome comparison. | Defined | Rejected candidate remains queryable and can be compared at expiration. |

### 16.10 Portfolio Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-PORT-001 | P1 | System shall manage Large and Small portfolios independently. | Defined | Paper books exist separately for `large` and `small`. |
| BS-PORT-002 | P1 | Portfolio shall track cash/buying-power reservation and assignment capacity. | Needs Rule Input | Paper portfolio report shows reserved capital and assignment capacity. |
| BS-PORT-003 | P1 | Portfolio shall enforce max concurrent positions by portfolio. | Needs Rule Input | Scanner does not create more paper trades than configured portfolio limit. |
| BS-PORT-004 | P1 | Portfolio shall track sector/theme exposure. | Needs Architecture | Portfolio report groups exposure by sector or theme. |
| BS-PORT-005 | P2 | System shall handle duplicate symbols across Large and Small portfolios according to configured policy. | Needs Rule Input | Duplicate symbol receives allowed, warning, or reject behavior. |

### 16.11 Paper, Shadow, And Live Execution Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-EXEC-001 | P1 | Paper trades shall use the same lifecycle model intended for live trades. | Defined | Paper trade has trade intent, order draft, simulated fill, lifecycle events, and outcome. |
| BS-EXEC-002 | P1 | System shall support shadow mode that creates order drafts without submitting live orders. | Defined | Shadow run produces order draft and approval status but no broker order id. |
| BS-EXEC-003 | P2 | Live trading shall require explicit operator approval before broker submission. | Defined | Attempted live order without approval is blocked. |
| BS-EXEC-004 | P2 | Live orders shall store broker order ids and native broker payloads. | Needs Architecture | Submitted order has auditable native payload. |
| BS-EXEC-005 | P2 | Fills shall be stored independently from orders. | Needs Architecture | Partial fill can be represented. |
| BS-EXEC-006 | P2 | Broker-synced live positions shall reconcile back to trade intents. | Needs Architecture | Open broker position can be traced to originating strategy decision. |

### 16.12 Monitoring And Scenario Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-MON-001 | P1 | System shall monitor open paper trades against short call and short put strikes. | Defined | Mark report flags near-call and near-put risk. |
| BS-MON-002 | P1 | System shall track whether short options can be closed around `$0.05` to `$0.10`. | Defined | Monitoring report includes close-price availability for open short options. |
| BS-MON-003 | P1 | System shall classify outcomes into Darren's five trade-management scenarios. | Defined | Closed paper trade has one scenario outcome. |
| BS-MON-004 | P1 | System shall maintain scenario scoreboard by count and percent. | Defined | Report shows scenario distribution. |
| BS-MON-005 | P2 | System shall recommend next-cycle action after each scenario. | Needs Rule Input | Outcome includes continue, replace, sell all, sell half, or no action. |

### 16.13 Confidence Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-CONF-001 | P1 | System shall store trade-level confidence component scores. | Defined | Trade scorecard contains component scores. |
| BS-CONF-002 | P1 | System shall calculate system-level confidence from paper-trading outcomes. | Needs Rule Input | Confidence report updates after closed paper trades. |
| BS-CONF-003 | P1 | System shall compare accepted, watched, and rejected candidates after expiration. | Defined | Report shows whether rejected candidates would have worked. |
| BS-CONF-004 | P2 | System shall define threshold for moving from paper to shadow mode. | Needs Rule Input | Shadow mode remains disabled until threshold is configured/met. |
| BS-CONF-005 | P2 | System shall define threshold for moving from shadow to live mode. | Needs Rule Input | Live mode remains disabled until threshold is configured/met and Product Owner live-readiness approval is documented. |

### 16.14 Reporting Requirements

| ID | Priority | Requirement | State | Acceptance Test |
|---|---|---|---|---|
| BS-RPT-001 | P0 | MVP shall produce an explainable current-fixture decision report. | Defined | Report includes every attempted fixture symbol, quote/chain status, selected legs when available, P/L, probability, and decision. |
| BS-RPT-002 | P1 | Weekly paper portfolio report shall show Large and Small books separately. | Defined | Report has distinct Large and Small sections. |
| BS-RPT-003 | P1 | Report shall compare newsletter replication mode with live strike-selection mode. | Defined | Report displays both structures where available. |
| BS-RPT-004 | P1 | Monitoring report shall show open trade status and scenario risk. | Defined | Report flags trades near strike or management trigger. |
| BS-RPT-005 | P1 | Confidence report shall show scenario scoreboard and expected-vs-realized outcomes. | Defined | Report includes distribution and performance metrics. |

## 17. Operational Requirements

Operating cadence:

- Weekly ingestion should run after newsletter publication.
- Live scanner should run during the intended trade-entry window.
- Monitoring should run at least daily for paper trades and more frequently near expiration or strike proximity.
- Expiration processing should run after market close on expiration date.
- Confidence metrics should update after each closed or expired trade.

Operational modes:

- `planning`: parse and analyze without creating trades.
- `paper`: create simulated trades and lifecycle events.
- `shadow`: create order drafts and approvals without broker submission.
- `live`: submit approved orders to broker.

Default mode shall be `paper` until confidence and approval requirements are explicitly met.

Failure behavior:

- Provider failure should mark affected candidates as `DATA_UNAVAILABLE`, not silently accept or reject them.
- Symbol-level data failure should not stop the MVP run; the scanner should continue to the next current-fixture symbol.
- Partial option-chain data should create warnings and exclude contracts with missing critical fields.
- Stale data should block live execution and warn for paper/shadow execution.
- Auth failures should create actionable operator messages.

Audit behavior:

- Every scan run should store provider, timestamp, mode, pricing policy, selected rule version, and source newsletter.
- Every decision should be replayable from stored snapshot data.
- Every live-capable order draft should include idempotency key/client order id before submission.

## 18. Initial Rule Defaults To Confirm

These are not final rules. They are placeholders for strategy-owner and architect review.

Expiration:

- MVP uses the newsletter expiration from the current fixture table so validation does not move while implementation is in progress.
- Post-MVP default target is the listed expiration closest to four weeks from scan date.

Pricing:

- Paper mode should use conservative executable pricing:
  - short option credit at bid or bid-adjusted price.
  - long option debit at ask or ask-adjusted price.
  - mid may be reported but should not be the default paper fill unless approved.

Liquidity:

- Candidate should warn or reject if selected option has missing bid/ask.
- Candidate should warn or reject if bid/ask spread exceeds configured percent or dollar threshold.
- Candidate should warn or reject if open interest or volume is below configured threshold.

Probability:

- Initial model may use lognormal expiration probability from selected IV.
- Store IV source, days to expiration, stock price, strikes, rate assumption, and dividend assumption.
- Do not claim equivalence with OS probability.

Portfolio:

- Large and Small portfolios should have independent max position counts and capital assumptions.
- Duplicates across Large and Small should be allowed only if configured.

Confidence:

- No live trading until paper history meets explicitly configured sample size and performance thresholds.
- No shadow trading until current-fixture MVP and full-watchlist paper runs are stable.

## 19. Implementation-Ready Deliverables For Architect

The Architect should produce:

- Updated target architecture document.
- PostgreSQL target schema design with one-way legacy import strategy.
- Provider interface specification.
- Tradier provider design.
- Scanner algorithm specification.
- P/L formula specification.
- Probability model specification.
- Paper/shadow/live lifecycle state machine.
- Portfolio and confidence scoring design.
- OS deprecation plan.
- Risk and rollout plan.

## 20. Definition Of Ready For Engineering

Engineering should not begin full implementation until:

- New GitHub repository `bullstrangle-platform` is created or explicitly approved for creation.
- Project identity is approved: `BullStrangle Platform`, package `bullstrangle_platform`, CLI `bs-platform`, MCP server `bullstrangle_platform_mcp`, PostgreSQL schema `bullstrangle`.
- Repository and folder layout are approved.
- Agent/sub-agent scaffolding and write ownership boundaries are approved.
- MCP-builder compliance checklist is approved, including strict tool naming, typed schemas, annotations, pagination, truncation, actionable errors, tests, and read-only evaluations.
- Provider contract is approved.
- PostgreSQL target schema is approved.
- Current-newsletter fixture MVP scope is locked.
- Fixture capture path is approved: screenshot/table input with manual correction is acceptable; OCR-grade ingestion is deferred.
- Initial strike-selection rules are confirmed.
- Initial pricing policy is confirmed.
- Initial P/L formulas are confirmed.
- Initial probability model is confirmed.
- Paper execution lifecycle is approved.
- Live trading guardrails are approved even if live mode remains disabled.
- Legacy isolation and no-runtime-dependency checks are approved.

## 21. Definition Of Done For MVP

MVP is done when:

- Current newsletter screenshot/table fixture can be captured into watchlist rows.
- Scanner processes fixture symbols sequentially and continues past symbol-level `DATA_UNAVAILABLE` failures.
- At least one current-fixture symbol can be scanned with Tradier live data.
- Live option chain is normalized and persisted.
- Newsletter replication and/or live strikes are selected according to approved provisional rules.
- P/L and probability outputs are calculated and persisted.
- Entry decision is produced with explanation and supports `DATA_UNAVAILABLE`.
- Paper trade intent, order draft, simulated fill, and lifecycle event are created.
- Report can replay the decision from stored data.
- No live order can be submitted.
- OS Excel is not required for the MVP path.
- PostgreSQL is the only runtime database.
- Legacy SQLite is not queried by runtime services.
