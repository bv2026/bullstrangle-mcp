# BullStrangle Refactor Design Notes

Status: Draft

## Project Identity And Repository Boundary

The refactor should start in a new self-contained GitHub repository before implementation work begins.

Recommended finalized identity:

- Product name: `BullStrangle Platform`
- GitHub repository: `bullstrangle-platform`
- Python package: `bullstrangle_platform`
- PostgreSQL schema namespace: `bullstrangle`
- CLI command namespace: `bs-platform`
- MCP server name: `bullstrangle_platform_mcp`

Rationale:

- A separate repository makes the legacy/runtime boundary enforceable instead of relying on discipline inside one tree.
- It prevents accidental imports from legacy `src/bullstrangle_mcp`.
- It gives the new PostgreSQL migration stream, MCP tool surface, config, tests, and release cadence a clean lifecycle.
- The current `bullstrangle-mcp` repository should keep the planning documents and legacy runtime unchanged.

## Gate 7 Retirement Candidate

Gate 7 currently applies a moving-average alignment filter from Option Samurai workbook fields
(`sma_50d`, `sma_200d`) after the newsletter watchlist has already been curated.

Refactor rule:

- Do not let Gate 7 reject trades in the redesigned entry flow.
- Treat moving-average alignment as an optional diagnostic signal only.
- Do not require Option Samurai SMA fields for entry decisions.
- Preserve the Master Strategy rule in the rule catalog, but map it to advisory evidence unless the user explicitly re-enables it as a hard gate.

Rationale:

- Darren's newsletter watchlist is the primary stock-selection layer.
- Reapplying trend filters after watchlist curation can double-filter the same thesis and reject otherwise valid newsletter trades.
- The current implementation depends on refreshed Option Samurai Excel fields, which keeps the workflow tied to a brittle manual workbook loop.
- Removing Gate 7 as a hard gate reduces false rejections and helps decouple the decision engine from Excel.

## Live Watchlist Scanner Replacement

The refactor target is a deterministic live-watchlist scanner, not a replacement for Darren's watchlist.

MVP source rule:

- Use the current newsletter screenshot/table as the operational MVP source.
- Create a current fixture watchlist from manually entered or manually corrected rows.
- Treat the current fixture path as a temporary Phase 0/1 bootstrap only; it should be deprecated after newsletter ingestion/import is reliable.
- Scan fixture symbols sequentially.
- If a symbol lacks sufficient live data, mark that symbol `DATA_UNAVAILABLE` with reason and continue to the next symbol.
- MVP succeeds when at least one current-fixture symbol completes live quote, option chain, selected legs, P/L, probability, decision, and paper lifecycle.
- Keep the earlier AA/2026-06-18 test only as a frozen regression/benchmark fixture.

Target workflow:

1. Ingest Darren's newsletter watchlist as the candidate universe.
2. Pull live stock prices and live option chains at execution time.
3. Select strikes from the live chain using the strategy's expiration and delta rules.
4. Calculate live credit, breakevens, return, annualized return, and full P/L outcomes.
5. Calculate probability metrics from live chain inputs instead of relying on Option Samurai output.
6. Accept, watch, or reject the trade from the live P/L and probability profile.

The redesigned workflow should replace the manual loop:

`newsletter -> generated OS workbook -> Excel refresh -> workbook re-ingest -> decision gates`

with:

`newsletter watchlist -> live option-chain scanner -> P/L engine -> probability engine -> entry decision`

Portfolio loop:

`entry decision -> paper portfolio execution -> live monitoring -> exit/outcome tracking -> confidence scoring`

Execution loop:

`entry decision -> trade intent -> order draft -> operator approval -> paper fill or live broker order -> fills -> position lifecycle -> outcome`

Inputs:

- Newsletter watchlist symbols.
- Newsletter IV and earnings data where already provided.
- Four-week target expiration, per Darren's core principle.
- Live stock price.
- Live option chain for the target expiration.

Computation:

- Select sell call, sell put, and protective put from the live option chain using configured delta bands and strategy rules.
- Calculate total credit from live bid/ask or midpoint policy.
- Calculate return, annualized return, distance from stock price, breakevens, and P/L outcomes.
- Calculate probability metrics using live stock price, strike, expiration, IV, and model assumptions.
- Persist a live watchlist snapshot with provider, timestamp, expiration, selected legs, deltas, prices, and computed credit.

Scanner modes:

- Newsletter replication mode: use Darren's published strikes, refresh live bid/ask/greeks, and answer whether the published trade is still executable.
- Live strike-selection mode: select strikes from the live option chain at scan time, using today's stock price and strategy delta rules.

Live strike-selection mode is the target execution workflow. Newsletter replication mode is useful for validation and transition.

P/L engine:

- Compute covered-call upside if called away.
- Compute short-put assignment outcome.
- Compute protective-put downside behavior.
- Compute downside breakeven after total credit.
- Compute capital required and return on capital.
- Compute annualized return.
- Compute outcome table across price scenarios at expiration.
- Reject trades where the live P/L profile does not meet strategy thresholds.

Probability engine:

- Do not depend on Option Samurai probability fields.
- Greeks do not directly provide probability of profit/loss; they provide model inputs and sensitivities.
- Use live stock price, expiration, selected strikes, IV, and chain greeks to calculate internal probability estimates.
- Store the model name, assumptions, input IV, and calculation timestamp with every probability output.
- Treat OS probability values, if present during transition, as comparison data only.

Provider rule:

- Use an explicit market-data provider interface.
- Prefer MCP-backed providers for live stock quotes and option chains.
- Do not make `schwab-mcp-file` a BullStrangle dependency for this purpose.
- `C:\work\webull-platform` currently exposes stock quotes but its `wb_get_options_chain` tool is a placeholder that reports option chains are not available through that SDK.
- The scanner needs a real option-chain source, either by exposing the needed chain-read operation from `webull-openapi` or by using another broker MCP provider such as Tradier or TradeStation if they provide chain greeks, bid, ask, strike, and expiration.
- Based on a live AA test, direct Tradier API is a viable first provider: it returned the 2026-06-18 option chain with bid, ask, open interest, volume, IV, and greeks, and matched the newsletter's AA strikes/prices closely.

Option Samurai role:

- Do not keep Option Samurai Excel as the strategic architecture.
- Keep OS Excel only as a temporary fallback and benchmark while the live scanner is validated.
- Stop designing downstream decision logic around repeated OS workbook re-ingestion.
- Retire the OS workbook from the normal workflow once the live scanner has been validated over multiple newsletters.

## Broker MCP Capability Review

Current finding:

- Schwab, Tradier, and TradeStation in `C:\work\brokers` do not currently expose a normalized option-chain MCP tool through the broker control plane.
- The broker control plane currently exposes accounts, balances, positions, transactions, instruments, quotes, futures-specific Schwab reads, full snapshot, and context-read tools.
- Those tools are useful for account state and live stock/option-contract quote lookup, but they are not sufficient by themselves to build the scanner because the scanner needs expiration-level option chain enumeration and greeks.

Schwab:

- Current local adapter has `get_quotes(symbols)` and account/position reads.
- Current surfaced Schwab SmartSpreads MCP tools provide futures/equity quotes, equity/option positions, transactions, auth checks, and futures utilities.
- No exposed option-chain read tool was found.
- Conclusion: useful for positions and possibly quoting already-known option symbols, not enough for selecting strikes by delta.

Tradier:

- Current local adapter has accounts, balances, positions, transactions, and quotes.
- The normalizer understands option metadata from existing positions, but the client does not currently implement chain, expiration, strike, or greeks endpoints.
- Conclusion: likely a good candidate to add a provider because Tradier's domain fits options, but the local MCP/adapter needs a new option-chain surface before BullStrangle can use it.

TradeStation:

- Current local adapter has accounts, balances, positions, transactions, and quote snapshots.
- Local documentation explicitly lists option chains, spread quotes, option analytics, and option-chain streaming as missing/out of scope for the current adapter.
- Conclusion: not currently usable for the scanner without extending the adapter.

Implementation requirement:

- Add or expose a provider tool with this minimum contract:
  - input: `symbol`, `expiration_date`
  - output: option rows with `right`, `strike`, `bid`, `ask`, `mid`, `delta`, `volume`, `open_interest`, and quote timestamp
- The BullStrangle scanner should depend only on this normalized provider contract, not on any broker-specific client.

Preferred first implementation:

- Add a BullStrangle-side `TradierOptionChainProvider` that uses the existing Tradier token/config from `C:\work\brokers`.
- Normalize Tradier option rows into a BullStrangle market-data contract.
- Keep this provider behind an interface so it can later be replaced by a broker MCP tool or another data vendor without changing scanner/decision logic.
- Add a later broker-platform enhancement to expose this as a proper MCP tool, but do not block the BullStrangle refactor on that.

Minimal live snapshot fields:

- `newsletter_id`
- `newsletter_date`
- `symbol`
- `live_stock_price`
- `expiration_date`
- `sell_call_strike`
- `sell_call_bid`
- `sell_call_delta`
- `sell_put_strike`
- `sell_put_bid`
- `sell_put_delta`
- `buy_put_strike`
- `buy_put_ask`
- `buy_put_delta`
- `total_credit`
- `return_pct`
- `source_provider`
- `market_data_as_of`

Additional decision-layer fields:

- `capital_required`
- `downside_breakeven`
- `called_away_profit`
- `put_assigned_cost_basis`
- `max_modeled_loss`
- `return_on_capital_pct`
- `annualized_return_pct`
- `prob_profit`
- `prob_short_call_otm`
- `prob_short_put_otm`
- `prob_between_short_strikes`
- `probability_model`
- `probability_inputs_json`

## Portfolio Management And Confidence Layer

The redesigned system needs a portfolio-management layer, not just symbol-level entry decisions.

Darren publishes two short-list portfolio concepts:

- Large portfolio.
- Small portfolio.

The system should preserve those portfolios as separate paper-trading books and evaluate them independently.

Goals:

- Build confidence before live deployment.
- Measure whether live scanner decisions improve or degrade Darren's published portfolio guidance.
- Track realized outcomes against expected P/L and probability assumptions.
- Identify which rules are actually predictive and which rules are over-filtering.
- Develop a confidence score for the system itself, not just for individual trades.

Paper-trading workflow:

1. Ingest newsletter watchlist and Large/Small short lists.
2. Run the live scanner during the intended entry window.
3. Build executable trade candidates from live market data.
4. Apply P/L, probability, liquidity, earnings, and portfolio-sizing rules.
5. Create paper trades for accepted candidates in the Large and Small books.
6. Track live marks, assignment risk, strike proximity, exit triggers, and trade-management scenarios.
7. Close, roll, expire, or restart paper trades according to strategy rules.
8. Store realized P/L, management scenario, and compare outcomes to expected P/L and probability estimates.

Portfolio-level rules:

- Keep Large and Small portfolio sizing separate.
- Track maximum concurrent positions by portfolio.
- Track allocation per symbol, per sector, and per strategy cycle.
- Avoid duplicate exposure where the same symbol appears across lists unless explicitly allowed.
- Track cash reserved, buying power impact, and assignment capacity.
- Enforce earnings and expiration rules consistently at the portfolio level.

Portfolio scoring:

- Score each paper trade at entry with:
  - data freshness score
  - liquidity score
  - P/L attractiveness score
  - probability score
  - newsletter alignment score
  - rule-compliance score
  - portfolio-fit score
- Store both component scores and a final confidence level.
- Confidence levels should be interpretable, for example:
  - `HIGH`: clean data, strong P/L, strong probability, good liquidity, fits portfolio.
  - `MEDIUM`: acceptable but has one or two cautions.
  - `LOW`: weak execution quality or conflicting evidence.
  - `REJECT`: violates hard risk, earnings, liquidity, or portfolio constraints.

System confidence:

- Confidence in the automation should be learned from paper-trading history.
- Track win rate, average return, max drawdown, assignment frequency, expected-vs-realized P/L, and rule attribution.
- Compare:
  - Darren published strikes refreshed with live data.
  - Live strike-selection output.
  - Accepted trades versus rejected trades.
  - Large portfolio versus Small portfolio.
- Promote rules only when paper-trading evidence supports them.
- Demote or retire rules that repeatedly reject winners or admit poor trades.

Recommended tables:

- `paper_portfolios`
- `paper_trades`
- `paper_trade_legs`
- `paper_trade_marks`
- `paper_trade_events`
- `portfolio_snapshots`
- `trade_scorecards`
- `system_confidence_metrics`

Recommended agents:

- Portfolio Manager Agent: owns Large/Small books, sizing, allocation, and exposure.
- Paper Trading Agent: creates simulated trades from accepted live scanner decisions.
- Monitoring Agent: updates live marks, risk proximity, and exit triggers.
- Outcome Attribution Agent: compares expected versus realized outcomes.
- Confidence Agent: produces trade-level and system-level confidence scores.

This layer is the feedback mechanism the current project lacks. Without it, the system can parse artifacts and generate reports, but it cannot learn whether its decisions are improving.

## Execution And Live Trading Readiness

The schema should be designed for live trading from the beginning, even while live trading remains disabled.

Design principle:

- Paper trading and live trading should share the same lifecycle model.
- Paper trades use simulated fills and simulated lifecycle events.
- Live trades use broker orders, broker fills, broker-synced positions, assignment events, and operator approvals.
- The decision engine should not need to be redesigned when live trading is enabled.

Execution stages:

1. `EntryDecision`: strategy accepts, watches, or rejects a candidate.
2. `TradeIntent`: an accepted strategy trade that may be paper-traded or submitted live.
3. `OrderDraft`: broker-neutral order structure with legs, quantity, limit credit/debit, and time in force.
4. `OperatorApproval`: explicit human approval before any live order is submitted.
5. `BrokerOrder`: submitted live order, broker id, account id, status, and native payload.
6. `Fill`: live or simulated fill records with quantity, price, commission, and timestamp.
7. `PositionLifecycle`: open, adjusted, assigned, called away, expired, closed, or restarted.
8. `Outcome`: realized P/L, management scenario, and attribution back to expected P/L/probability.

Recommended execution tables:

- `trade_intents`
- `order_drafts`
- `order_draft_legs`
- `operator_approvals`
- `broker_orders`
- `broker_order_legs`
- `fills`
- `live_positions`
- `assignment_events`
- `trade_lifecycle_events`
- `trade_outcomes`

Required fields and concepts:

- `execution_mode`: `paper`, `live`, or `shadow`.
- `source_decision_id`: links execution back to the accepted entry decision.
- `portfolio_type`: `large` or `small`.
- `account_id`: paper account id or broker account id.
- `broker`: nullable for paper, populated for live.
- `order_status`: draft, approved, submitted, filled, partially filled, cancelled, rejected, expired.
- `fill_source`: simulated, broker_api, manual_import.
- `native_order_payload_json`: raw broker payload for auditability.
- `native_fill_payload_json`: raw broker fill payload for auditability.
- `approval_status`: pending, approved, rejected, expired.
- `approved_by`, `approved_at`, `approval_notes`.
- `idempotency_key` or `client_order_id` to prevent duplicate live orders.
- `lifecycle_status`: open, monitoring, closing, closed, assigned, called_away, expired, restarted.

Live trading guardrails:

- Never submit a live order without an approved `operator_approvals` row.
- Store every broker payload and response for auditability.
- Reconcile live broker positions back to BullStrangle trade intents.
- Treat broker-synced positions as source of truth after live fill.
- Keep paper/shadow execution available even after live mode exists.
- Live order tools should remain disabled until paper-trading confidence metrics meet an explicit threshold.

Shadow mode:

- Shadow mode should create order drafts and simulated fills from live market data but not submit orders.
- It is the bridge between paper trading and live trading.
- Shadow output should be compared to actual operator trades, if any, to validate readiness.

## Trade Management Scenario Rules

Portfolio monitoring and paper-trade outcomes should be guided by Darren's trade-management taxonomy.

Scenario 1: Early Call

- Trigger: stock is called away before expiration.
- Management rule: close the naked put when it can be bought back for approximately `$0.05` to `$0.10` per contract.
- Otherwise wait for put expiration.
- Outcome category: `EARLY_CALL`.

Scenario 2: Early Assignment

- Trigger: stock is assigned before expiration from the short put.
- Management rule: sell all shares and close the naked call when it can be bought back for approximately `$0.05` to `$0.10` per contract.
- Otherwise wait for call expiration.
- Outcome category: `EARLY_ASSIGNMENT`.

Scenario 3: Stock Called Away

- Trigger: covered stock is called away at or before expiration.
- Management rule: this is the best-case closed-at-maximum-profit scenario.
- No action is required after closure.
- Outcome category: `STOCK_CALLED_AWAY`.

Scenario 4: Options Expiration

- Trigger: options expire and stock is kept.
- Management rule: usually continue holding and sell new calls and puts for the next cycle.
- Re-evaluate the stock against other watchlist candidates and replace it if a better candidate exists.
- Outcome category: `OPTIONS_EXPIRED_STOCK_KEPT`.

Scenario 5: Stock Assignment

- Trigger: stock closes below the put strike and additional shares are assigned.
- Management rule: usually sell all shares and look for a new candidate for the next cycle.
- If the operator still likes the stock, sell half the shares and start over.
- Outcome category: `STOCK_ASSIGNED`.

Scenario scoreboard:

- Track count and percent by outcome category.
- At minimum:
  - `STOCK_CALLED_AWAY`
  - `OPTIONS_EXPIRED_STOCK_KEPT`
  - `STOCK_ASSIGNED`
  - `EARLY_CALL`
  - `EARLY_ASSIGNMENT`
- Compare BullStrangle paper-trading outcomes to Darren's historical distribution when available.
- Use the distribution to calibrate confidence, assignment capacity, and portfolio sizing.

Recommended scenario fields:

- `management_scenario`
- `scenario_triggered_at`
- `scenario_trigger_price`
- `short_call_close_price`
- `short_put_close_price`
- `shares_sold`
- `shares_assigned`
- `restart_next_cycle`
- `operator_override`
- `scenario_notes`

Monitoring requirements:

- Detect when stock price is above short call strike, below short put strike, or near either strike.
- Track whether short call or naked put can be closed in the `$0.05` to `$0.10` range.
- Track expiration outcome automatically.
- Record whether the next-cycle action is continue, replace, sell all shares, sell half shares, or no action.
