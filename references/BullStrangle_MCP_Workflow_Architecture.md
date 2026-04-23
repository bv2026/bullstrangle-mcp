# BullStrangle MCP Workflow Architecture

Version: 0.5
Date: 2026-04-22
Status: Implemented through v1 weekend decision generation

## Current Handoff State

As of April 22, 2026, the local implementation is packaged and runnable for the full v1 workflow:

- ingest weekly newsletter PDFs from `data/newsletters`
- generate an Option Samurai-enabled workbook from the newsletter watchlist
- ingest refreshed daily OS workbooks after Excel/Option Samurai recalculation
- store daily OS snapshots and deviations
- aggregate all OS uploads for a newsletter week
- ingest account-level positions and symbol rollups
- generate v1 weekend Bull Strangle and DCA candidate decisions
- expose the workflow through both CLI commands and Claude-compatible MCP tools

The immediate next operational step is to upload another refreshed OS workbook during market hours after the market opens. That will validate weekly aggregation across more than one daily snapshot.

Deferred by design:

- DCA holdings/account-state ingestion
- final DCA executable allocation logic
- tuned decision thresholds based on several live OS uploads
- full Master Document strategy extraction and rule implementation
- report persistence tables

Master Document status:

- `references/Bull Strangle Master Document - Version 8.pdf` is stored in the GitHub repo as the master strategy reference.
- The current v1 decision logic has not fully encoded the Master Document.
- Current strategy logic is based on newsletter appendix sections, Option Samurai integration artifacts, and workflow rules captured during implementation.
- Before locking final DCA/Bull Strangle decisions, the Master Document should be studied and converted into structured rules, tests, and decision snapshots.

New DCA/account rule captured:

- Positions may be distributed across multiple accounts for portfolio awareness.
- A DCA or Bull Strangle action must be deployed in exactly one account and cannot be split across accounts.
- DCA target is to build the selected account position to `100` shares.
- Once a symbol reaches `100` shares in a single account, it becomes eligible to be promoted from DCA to Bull Strangle evaluation.
- Consolidated symbol-level holdings can be used for exposure/risk awareness, but execution eligibility must be account-specific.

## Purpose

This document describes the current BullStrangle MCP database design and the intended workflow for moving from weekly newsletter ingestion to daily Option Samurai Excel snapshots, deviation tracking, and weekend-only DCA/Bull Strangle decisions.

The core design principle is separation of concerns:

- Newsletter data is the immutable baseline.
- Daily Option Samurai Excel uploads are market/live-data snapshots.
- Deviation history compares daily live data to the newsletter baseline.
- Final DCA and Bull Strangle decisions are generated once on the weekend.

## Workflow

### 1. Weekly Newsletter Ingestion

Input:

- Weekly Bull Strangle newsletter PDF under `data/newsletters`.

Process:

- Parse the newsletter PDF.
- Store newsletter metadata.
- Store consolidated watchlist rows.
- Store short-list membership.
- Store favorite/deep-analysis JSON.
- Store market environment metrics and useful market commentary.
- Store common strategy implementation references.

Output:

- Populated newsletter baseline tables.
- Option Samurai workbook generation can use `watchlist_entries`.

### 2. Option Samurai Workbook Generation

Input:

- `newsletters`
- `watchlist_entries`
- `short_list_entries`
- `market_environment`
- `strategy_reference_sections`

Process:

- Generate an Excel workbook with Option Samurai embedded formulas.
- The workbook is based on the newsletter watchlist universe and expiration cycle.
- Newsletter values remain immutable in the DB.

Planned output table:

- `os_workbooks`

### 3. Daily Market-Hours Excel Upload

Input:

- Refreshed Option Samurai Excel workbook uploaded by the user under `data/os_uploads`.

Process:

- Read the workbook as one uploaded run.
- Store one row per upload.
- Store one evaluated row per symbol.
- Compare each live OS row to the newsletter baseline.
- Store deviations for later decision analysis.

Important:

- `outputs/os_workbooks` is for generated workbook templates.
- `data/os_uploads` is for Excel-refreshed workbook uploads.
- Daily uploads do not create final trade decisions.
- Daily uploads only create OS snapshots and deviations.

Planned output tables:

- `os_evaluation_runs`
- `os_evaluation_rows`
- `watchlist_deviations`

### 4. Weekend Decision Generation

Input:

- `market_environment`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deep_analysis`
- `strategy_rules`
- `strategy_reference_sections`
- `os_evaluation_runs`
- `os_evaluation_rows`
- `watchlist_deviations`

Process:

- Run once per newsletter cycle after the trading week ends.
- Build one decision batch.
- Generate DCA decisions.
- Generate Bull Strangle decisions.
- Store decision rationale as JSON snapshots for auditability.

Planned output tables:

- `decision_batches`
- `dca_decisions`
- `bull_strangle_decisions`

### 5. Reporting

Reports are generated downstream from normalized database tables.

Reporting must not mutate source data or create decisions. Decisions are created by decision-generation jobs; reports only explain, summarize, and audit the current state.

Report triggers:

- After newsletter ingestion.
- After each daily OS Excel upload.
- After weekend decision generation.
- On demand from MCP tools.

Report outputs:

- Markdown first.
- HTML optional.
- Excel/PDF optional later.

Planned output tables:

- `report_templates`
- `report_runs`
- `generated_reports`

## Current Implemented Tables

### `newsletters`

One row per newsletter PDF.

Key fields:

- `publication_date`
- `entry_date`
- `target_expiration`
- `option_type`
- `days_to_expiration`
- `market_outlook`
- `strategy_notes`
- `market_commentary_structured`
- `pdf_path`
- `pdf_sha256`

### `newsletter_full_text`

Audit and reprocessing table. Stores full PDF text and extracted raw sections.

Current section names:

- `full_text`
- `watchlist_screening`
- `watchlist_option_prices`
- `short_lists`
- `watchlist_favorites`
- `stock_market_weekly_recap`
- `market_commentary`
- `market_environment`
- `strategy_reference`

### `watchlist_entries`

Canonical immutable newsletter watchlist baseline. This is the main watchlist table.

Consolidates:

- Watch List with Option Prices
- Additional screening details from Watch List for Entry / Expiration

Key fields:

- `newsletter_date`
- `expiration_date`
- `symbol`
- `description`
- `sector`
- `stock_price`
- `implied_volatility`
- `total_open_interest`
- `industry`
- `sub_sector`
- `weekly_options`
- `latest_earnings`
- `sell_call_strike`
- `sell_call_premium`
- `sell_put_strike`
- `sell_put_premium`
- `buy_put_strike`
- `buy_put_premium`
- `bull_strangle_return_pct`
- `put_credit_spread_return_pct`
- `covered_call_return_pct`
- `is_favorite`

Design rule:

- Do not overwrite these values with live OS Excel values. They are the newsletter baseline.

### `short_list_entries`

Large/small model-account short-list membership.

Key fields:

- `newsletter_date`
- `portfolio_type`
- `symbol`
- `rank`

### `watchlist_deep_analysis`

JSON-backed deep-analysis table for Watch List Favorites and proposed trade details.

Key fields:

- `newsletter_date`
- `symbol`
- `analysis_data`
- `favorite_rank`
- `has_proposed_trade`
- `source_pages`

### `market_environment`

Consolidated market table. Stores normalized market metrics plus useful market commentary.

Included narrative pages:

- Stock Market Weekly Recap
- Market Overview - S&P 500 text page
- Market Environment Awareness

Skipped chart-only pages:

- Weekly Sectors
- Sector 1 Year Charts
- Sector Price Change

Key normalized fields:

- `sp500_price`
- `sp500_200dma`
- `sp500_vs_200dma`
- `sp500_above_200dma`
- `vix`
- `vix_below_25`
- `breadth_pct`
- `breadth_above_40`
- `trend_score`
- `volatility_score`
- `breadth_score`
- `hybrid_score`
- `hybrid_bullish`
- `market_status`
- `market_regime`
- `investment_percent`
- `cash_reserve_target`
- `all_criteria_met`
- `consecutive_weeks_met`
- `deployment_approved`
- `recommended_position_count`
- `scaling_phase`

Commentary fields:

- `commentary_raw_text`
- `commentary_json`
- `commentary_source_pages`

### `weekly_decisions`

Market-level weekly deploy/pause state only. This is not a symbol-level final decision table.

Key fields:

- `publication_date`
- `all_criteria_met`
- `consecutive_weeks_met`
- `deployment_approved`
- `action_taken`
- `decision_rationale`

### `symbol_history`

Symbol appearance history derived at newsletter ingestion time.

Key fields:

- `symbol`
- `publication_date`
- `on_watchlist`
- `on_short_list`
- `metadata`

### `os_workbooks`

Option Samurai workbook metadata and formula contract table.

Current implemented behavior:

- Calculates newsletter-average option distance selectors from `watchlist_entries`.
- Rounds selectors to the configured increment, currently nearest `0.5%`.
- Stores the strike rounding policy used by workbook generation.
- Stores delta fallback bands for OptionGeeks/Greeks selection.
- Stores `formula_contract_json` so daily uploads can be interpreted against the exact selector policy used for that week.

Current CLI:

- `os-selectors <newsletter_date>` calculates rounded selectors without writing a metadata row.
- `prepare-os-workbook <newsletter_date>` creates or updates the `os_workbooks` metadata row.

April 17, 2026 selector output:

- sell call average `3.93%`, rounded selector `4.0%`
- sell put average `-3.63%`, rounded selector `-3.5%`
- buy put average `-13.28%`, rounded selector `-13.5%`

### `strategy_reference_sections`

Common strategy appendix/reference content. Stored once as common reference, not per newsletter.

Current common rows:

- Strategy Benefits
- Strategy Implementation - Core Elements
- Trade Management Suggestions

### `strategy_rules`

Structured strategy rules extracted/seeded from the common reference layer.

Current rule categories:

- `entry`
- `exit`
- `risk`

## Removed Table

### `watchlist_decisions`

Removed from the current design.

Reason:

- The user workflow creates final decisions only after a full week of daily OS Excel uploads.
- Symbol-level watchlist decisions should not be generated at newsletter ingestion time.
- Future decision tables should be explicit:
  - `dca_decisions`
  - `bull_strangle_decisions`

## OS Excel Tables And Workflow

Status:

- Implemented: generated OS workbook metadata.
- Implemented: OS workbook generation.
- Implemented: daily refreshed workbook ingestion.
- Implemented: daily OS evaluation rows.
- Implemented: watchlist deviations from newsletter baseline.
- Implemented: daily OS run audit/deviation report.
- Implemented: weekly aggregation across multiple daily OS runs.
- Implemented: v1 weekend decision batches and final DCA/Bull Strangle decisions.
- Pending: tune decision criteria after real multi-day OS upload history.

## Option Samurai Workbook Contract

Source artifacts reviewed:

- `osamurai/BullStrangle_Template.xlsx`
- `osamurai/os_Excel addin fields.xlsx`
- `osamurai/os-Excel & Google Sheets Integration.pdf`
- `osamurai/os_filters_june2025-1.pdf`

The existing `BullStrangle_Template.xlsx` is useful as a formula reference, but the MCP does not need to preserve its exact tab layout. The future generated workbook should be simpler and purpose-built for the MCP workflow.

### Formula Functions

The Option Samurai Excel add-in exposes modular UDFs.

Official syntax from the PDF:

- `OPTIONSAMURAI.STOCK(ticker, field1, field2, ...)`
- `OPTIONSAMURAI.OPTION(ticker, call_or_put, expiration, strike_or_filter, field1, field2, ...)`

Excel stores the formulas in the reviewed workbook as:

- `_xldudf_optionsamurai_stock(...)`
- `_xldudf_optionsamurai_option(...)`

The generated workbook should use the Excel UDF form because that is what the existing workbook uses successfully.

Example stock formulas:

```text
=_xldudf_optionsamurai_stock(A6,"stock_last")
=_xldudf_optionsamurai_stock(A6,"stock_iv")
=_xldudf_optionsamurai_stock(A6,"sector")
=_xldudf_optionsamurai_stock(A6,"industry")
=_xldudf_optionsamurai_stock(A6,"earnings_date")
=_xldudf_optionsamurai_stock(A6,"perf_m")
=_xldudf_optionsamurai_stock(A6,"perf_q")
=_xldudf_optionsamurai_stock(A6,"sma_50d")
=_xldudf_optionsamurai_stock(A6,"sma_200d")
=_xldudf_optionsamurai_stock(A6,"stock_iv_rv_pr")
=_xldudf_optionsamurai_stock(A6,"atr_percent")
=_xldudf_optionsamurai_stock(A6,"short_ratio")
```

Example option formulas:

```text
;; Preferred v1: selector percentages are generated from the newsletter baseline,
;; not hard-coded.
=_xldudf_optionsamurai_option(E10,"CALL",$B$3,$B$4,"strike")
=_xldudf_optionsamurai_option(E10,"CALL",$B$3,$B$4,"bid")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,$B$5,"strike")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,$B$5,"bid")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,$B$6,"strike")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,$B$6,"ask")
=_xldudf_optionsamurai_option(E10,"CALL",$B$3,$B$4,"delta")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,$B$5,"delta")
=_xldudf_optionsamurai_option(E10,"CALL",$B$3,TEXT(X10,"0"),"prob_otm")
=_xldudf_optionsamurai_option(E10,"PUT",$B$3,TEXT(AA10,"0"),"prob_otm")
```

Floating option selectors supported by Option Samurai include:

- explicit expiration date, such as `2026-05-15`
- DTE selector, such as `>30`
- moneyness selector, such as `1.5%` or `-1.5%`
- delta selector, such as `25d`
- N-th strike selector, such as `3N` or `-4N`
- OTM/ITM selectors, such as `4OTM`

For BullStrangle workflow v1, use newsletter-derived selectors:

- expiration from `newsletters.target_expiration`
- call selector from average newsletter call distance
- put selector from average newsletter put distance
- optional reference strikes using delta selectors

Recommended generated workbook parameter cells:

- `$B$3`: target expiration date from `newsletters.target_expiration`
- `$B$4`: call selector, formatted as a positive percentage string
- `$B$5`: put selector, formatted as a negative percentage string
- `$B$6`: buy put selector, formatted as a negative percentage string
- `$B$7`: selector source, such as `newsletter_average` or `delta_fallback`

Newsletter average selector calculation:

- `avg_call_distance_pct = AVG((sell_call_strike - stock_price) / stock_price)` across valid rows in the newsletter watchlist
- `avg_put_distance_pct = AVG((sell_put_strike - stock_price) / stock_price)` across valid rows in the newsletter watchlist
- Round selector percentages before generating OS formulas.
- Default selector rounding: nearest `0.5%`.
- Format the call selector as `+N.N%`, for example `4.0%`
- Format the put selector as `-N.N%`, for example `-3.5%`
- Exclude rows with missing stock price or missing strike.
- Store the generated selector values on the workbook metadata row so daily uploads can be audited against the exact formula contract used that week.

Strike rounding rule:

- Avoid passing unrounded calculated strike prices into OS formulas because OS may return null when an exact strike does not exist.
- Prefer rounded percentage selectors where possible, letting Option Samurai resolve the nearest available contract.
- When an explicit calculated strike must be used, round it to a configurable strike increment before generating the formula.
- Default strike rounding policy:
  - stock price under `$25`: nearest `$0.50`
  - `$25` to `$100`: nearest `$1.00`
  - `$100` to `$250`: nearest `$2.50`
  - over `$250`: nearest `$5.00`
- Preserve both `target_strike_raw` and `target_strike_rounded` when explicit strikes are generated, so null OS returns can be debugged.

If the newsletter average is not feasible because the baseline strikes are missing, inconsistent, or too noisy, use an Option Samurai delta fallback based on the Option Greeks filter:

- Days to expiration: 22 to 35
- Leg 1: Buy PUT delta from 10 to 15
- Leg 2: Sell PUT delta from 15 to 20
- Leg 3: Sell CALL delta from 25 to 30

Implementation note:

- If the Excel UDF supports only single delta selectors, use midpoint selectors for formula generation: `12d` for the buy put, `17d` for the sell put, and `27d` for the sell call.
- If Option Samurai range filters are only available through an OptionGeeks/screener export, ingest the exported candidate rows as an OS source table and map them back to `watchlist_entries` by symbol, expiration, and leg.
- The selected method must be recorded as metadata because deviation tracking depends on knowing whether the workbook used newsletter-average moneyness selectors or delta-band selectors.

### Generated Workbook Shape

Implemented v1 generated workbook tabs:

1. `OS_Live`
2. `Baseline`
3. `Instructions`
4. hidden `Metadata`

Avoid carrying forward the old `Criteria`, `Rules`, or manual decision tabs. Decision logic belongs in DB decision batches, not in the workbook.

#### `OS_Live`

One row per `watchlist_entries` symbol for the newsletter cycle.

Current generated workbook command:

```powershell
python -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-os-workbook 2026-04-17 --output-dir outputs\os_workbooks
```

Current output example:

- `outputs/os_workbooks/BullStrangle_OS_Live_2026-04-17.xlsx`

Required input columns:

- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `watchlist_entry_id`
- `symbol`

Recommended live/formula columns:

- `live_stock_price`
- `live_stock_iv`
- `live_sector`
- `live_industry`
- `live_earnings_date`
- `perf_1m`
- `perf_3m`
- `sma_50d_distance`
- `sma_200d_distance`
- `ma_pass_count`
- `selector_source`
- `call_selector_pct`
- `put_selector_pct`
- `sell_call_strike`
- `sell_call_bid`
- `sell_call_delta`
- `sell_put_strike`
- `sell_put_bid`
- `sell_put_delta_abs`
- `buy_put_strike`
- `buy_put_ask`
- `buy_put_delta_abs`
- `total_credit`
- `bull_strangle_return_pct`
- `covered_call_strike`
- `covered_call_bid`
- `covered_call_return_pct`
- `cash_secured_put_strike`
- `cash_secured_put_bid`
- `cash_secured_put_return_pct`
- `prob_profit_estimate`
- `prob_loss_estimate`
- `call_distance_pct`
- `put_distance_pct`
- `strike_gap`
- `trade_signal`
- `sell_call_27d_strike`
- `sell_call_27d_bid`
- `sell_put_17d_strike`
- `sell_put_17d_bid`
- `buy_put_12d_strike`
- `buy_put_12d_ask`
- `call_prob_otm`
- `put_prob_otm`
- `prob_both_otm`
- `iv_rv_percentile`
- `atr_percent`
- `short_ratio`

`trade_signal` can be present as an informational Excel formula, but final trade approval must still be generated in weekend DB decisions.

#### `Baseline`

Read-only copy of newsletter baseline fields from `watchlist_entries`.

Recommended fields:

- `newsletter_date`
- `expiration_date`
- `symbol`
- `description`
- `sector`
- `stock_price`
- `implied_volatility`
- `total_open_interest`
- `industry`
- `sub_sector`
- `weekly_options`
- `latest_earnings`
- `sell_call_strike`
- `sell_call_premium`
- `sell_put_strike`
- `sell_put_premium`
- `buy_put_strike`
- `buy_put_premium`
- `bull_strangle_return_pct`
- `put_credit_spread_return_pct`
- `covered_call_return_pct`
- `is_favorite`

#### `Instructions`

Short instructions only:

- open with Option Samurai add-in enabled
- refresh formulas
- upload the workbook back to MCP daily during market hours
- final decisions are weekend-only

### Formula Fields to Prioritize

The field-name workbook contains 97 OS fields. For v1, prioritize only the fields needed for live snapshots and deviations:

Stock fields:

- `name`
- `stock_last`
- `stock_iv`
- `sector`
- `industry`
- `earnings_date`
- `weekly_options`
- `total_oi`
- `perf_m`
- `perf_q`
- `sma_50d`
- `sma_200d`
- `stock_iv_rv_pr`
- `atr_percent`
- `short_ratio`

Option fields:

- `strike`
- `bid`
- `ask`
- `mid`
- `bid_ask_spread`
- `bid_ask_spread_pc`
- `open_interest`
- `volume`
- `iv`
- `delta`
- `theta`
- `prob_otm`
- `moneyness`

The complete field audit is stored in:

- `data/os_formula_contract.json`

### `os_workbooks`

Tracks generated OS Excel workbooks. Implemented.

Implemented fields include:

- `workbook_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `generated_path`
- `generated_at`
- `template_version`
- `selector_source`
- `call_selector_pct`
- `put_selector_pct`
- `buy_put_selector_pct`
- `selector_rounding_increment_pct`
- `strike_rounding_policy_json`
- `buy_put_delta_min`
- `buy_put_delta_max`
- `sell_put_delta_min`
- `sell_put_delta_max`
- `sell_call_delta_min`
- `sell_call_delta_max`
- `formula_contract_json`
- `status`
- `workbook_hash`

`selector_source` determines how option legs were selected:

- `newsletter_average`: use average strike distance from `watchlist_entries`.
- `delta_fallback`: use the Option Greeks delta bands when newsletter-average selectors are not usable.

`formula_contract_json` should preserve the exact selectors, selector rounding increment, strike rounding policy, and formula assumptions used for that generated workbook. This allows a later OS upload to be interpreted correctly even if the selector policy changes in a future week.

### `os_evaluation_runs`

One row per uploaded/refreshed Excel workbook. Implemented.

Implemented fields:

- `run_id`
- `workbook_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `trading_date`
- `uploaded_path`
- `uploaded_at`
- `market_data_as_of`
- `row_count`
- `populated_live_value_count`
- `formula_cell_count`
- `status`
- `raw_workbook_hash`
- `validation_json`

Current ingest command:

```powershell
python -m bullstrangle_mcp.cli --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-17.xlsx --trading-date 2026-04-22
```

Current example run:

- `run_id`: `1`
- `newsletter_date`: `2026-04-17`
- `trading_date`: `2026-04-22`
- `row_count`: `24`
- `populated_live_value_count`: `214`
- `formula_cell_count`: `696`
- `status`: `ingested`

### `os_evaluation_rows`

One row per symbol per uploaded Excel run. Implemented.

Implemented fields:

- `evaluation_row_id`
- `run_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `watchlist_entry_id`
- `symbol`
- `live_stock_price`
- `live_stock_iv`
- `live_sector`
- `live_industry`
- `live_earnings_date`
- `perf_1m`
- `perf_3m`
- `sma_50d`
- `sma_200d`
- `selector_source`
- `call_selector_pct`
- `put_selector_pct`
- `buy_put_selector_pct`
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
- `bull_strangle_return_pct`
- `call_distance_pct`
- `put_distance_pct`
- `buy_put_distance_pct`
- `call_prob_otm`
- `put_prob_otm`
- `prob_both_otm`
- `iv_rv_percentile`
- `atr_percent`
- `short_ratio`
- `raw_row_json`

The exact physical workbook columns can evolve, but ingestion should map them into the canonical row fields above.

### `watchlist_deviations`

Daily comparison between newsletter baseline and live OS Excel values. Implemented.

Implemented fields:

- `deviation_id`
- `run_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `watchlist_entry_id`
- `symbol`
- `stock_price_deviation`
- `stock_price_deviation_pct`
- `iv_deviation`
- `sell_call_strike_deviation`
- `sell_put_strike_deviation`
- `buy_put_strike_deviation`
- `total_credit_deviation`
- `raw_deviation_json`
- `created_at`

Current daily report command:

```powershell
python -m bullstrangle_mcp.cli --db data\bullstrangle.db report-os-run 1 --output reports\2026-04-22\os_run_1.md
```

Current daily report example:

- report path: `reports/2026-04-22/os_run_1.md`
- missing/error rows: `1` (`IMVT`)
- largest price deviations: `DJT`, `NTAP`, `SHLD`, `GDS`, `NFLX`

### `os_weekly_symbol_aggregates`

Weekly aggregation table across all daily OS uploads for one newsletter cycle. Implemented.

Implemented fields:

- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `symbol`
- `watchlist_entry_id`
- `run_count`
- `first_run_id`
- `latest_run_id`
- `first_trading_date`
- `latest_trading_date`
- `first_live_stock_price`
- `latest_live_stock_price`
- `min_live_stock_price`
- `max_live_stock_price`
- `latest_live_stock_iv`
- `latest_sell_call_strike`
- `latest_sell_call_bid`
- `latest_sell_put_strike`
- `latest_sell_put_bid`
- `latest_buy_put_strike`
- `latest_buy_put_ask`
- `latest_total_credit`
- `min_total_credit`
- `max_total_credit`
- `worst_abs_stock_price_deviation_pct`
- `worst_abs_total_credit_deviation`
- `missing_core_value_days`
- `is_week_valid`
- `aggregate_json`

Current weekly aggregation command:

```powershell
python -m bullstrangle_mcp.cli --db data\bullstrangle.db aggregate-os-week 2026-04-17 --output reports\2026-04-22\os_week_2026-04-17.md
```

Current weekly aggregation report example:

- report path: `reports/2026-04-22/os_week_2026-04-17.md`
- OS run count: `1`
- symbols: `24`
- valid symbols: `23`
- invalid symbols: `1` (`IMVT`)
- largest price deviations: `DJT`, `NTAP`, `SHLD`, `GDS`, `NFLX`
- largest credit deviations: `NTAP`, `EWW`, `ICLN`, `NFLX`, `URBN`

### Current MCP Tools

Implemented Claude-compatible MCP tools:

- `ingest_newsletter`
- `ingest_newsletter_directory`
- `list_newsletters`
- `get_newsletter`
- `get_newsletter_by_date`
- `calculate_os_selectors`
- `prepare_os_workbook`
- `generate_os_workbook`
- `ingest_os_workbook`
- `ingest_positions`
- `report_os_run`
- `aggregate_os_week`
- `generate_weekend_decisions`

## Position Tables

### `position_import_runs`

One row per imported positions CSV.

Implemented fields:

- `position_run_id`
- `source_path`
- `imported_at`
- `row_count`
- `account_count`
- `symbol_count`
- `total_market_value`
- `total_cost_basis`
- `status`
- `validation_json`

### `account_positions`

One row per account/symbol holding from the latest positions export.

Implemented fields:

- `position_run_id`
- `account_name`
- `symbol`
- `quantity`
- `current_price`
- `average_price`
- `market_value`
- `cost_basis`
- `unrealized_gain_loss`
- `unrealized_gain_loss_pct`
- `raw_row_json`

### `symbol_position_rollups`

Symbol-level exposure view plus single-account execution eligibility.

Implemented fields:

- `position_run_id`
- `symbol`
- `total_quantity`
- `total_market_value`
- `total_cost_basis`
- `weighted_average_price`
- `account_count`
- `max_account_quantity`
- `bull_strangle_ready`
- `eligible_account`
- `dca_target_account`
- `shares_to_100`
- `accounts_json`

Design rule:

- `total_quantity` is only for exposure awareness.
- `bull_strangle_ready` is true only when one account has at least `100` shares.
- DCA and Bull Strangle recommendations must point to one account.

## Weekend Decision Tables

### `decision_batches`

One row per weekend decision run. Implemented.

Implemented fields:

- `decision_batch_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `decision_date`
- `source_run_start_date`
- `source_run_end_date`
- `market_environment_id`
- `os_run_count`
- `status`
- `created_at`
- `source_snapshot_json`

### `bull_strangle_decisions`

Final weekend Bull Strangle decisions. Implemented v1.

Reads:

- `market_environment`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deep_analysis`
- `strategy_rules`
- `strategy_reference_sections`
- `os_evaluation_rows`
- `watchlist_deviations`

Implemented fields:

- `decision_id`
- `decision_batch_id`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `watchlist_entry_id`
- `symbol`
- `final_decision`
- `priority_rank`
- `market_approved`
- `os_week_valid`
- `latest_total_credit`
- `latest_live_stock_price`
- `max_price_deviation_pct`
- `max_credit_deviation`
- `rules_applied_json`
- `criteria_json`
- `source_snapshot_json`
- `reason`
- `created_at`

Current v1 decision policy:

- `APPROVE` when market deployment is approved, weekly OS data is valid, total credit is positive, price deviation is under `8%`, and credit deviation is under `$2.50`.
- `WATCH` when the symbol has valid OS data and positive credit but at least one other v1 gate is not passed.
- `SKIP` when required OS values are missing or credit is not usable.

### `dca_decisions`

Final weekend DCA decisions. Implemented v1.

Reads:

- `market_environment`
- `watchlist_entries`
- `watchlist_deep_analysis`
- `strategy_rules`
- `strategy_reference_sections`
- `os_evaluation_rows`
- `watchlist_deviations`
- future holdings/account state

Implemented fields:

- `decision_id`
- `decision_batch_id`
- `newsletter_id`
- `newsletter_date`
- `symbol`
- `watchlist_entry_id`
- `final_decision`
- `priority_rank`
- `market_allocation_ok`
- `dca_candidate_score`
- `latest_live_price`
- `weekly_price_trend`
- `max_price_deviation_pct`
- `rules_applied_json`
- `criteria_json`
- `source_snapshot_json`
- `reason`
- `created_at`

Current v1 decision policy:

- `APPROVE` when market allocation is above zero, weekly OS data is valid, candidate score is at least `1.0`, and price deviation is under `8%`.
- `WATCH` when market allocation exists and candidate score passes but at least one other v1 gate is not passed.
- `SKIP` when allocation, candidate score, or OS data is not usable.
- Holdings/account state is not yet implemented, so DCA decisions are candidate decisions rather than executable allocation instructions.

Required account-aware DCA behavior for the next implementation pass:

- Ingest positions by account and by symbol.
- Also build a consolidated symbol view for exposure awareness.
- Choose a single target account for each DCA recommendation.
- Do not split a DCA recommendation across multiple accounts.
- Calculate shares needed to reach `100` shares in the selected account.
- Promote a symbol to Bull Strangle eligibility only when one account holds at least `100` shares.
- Treat symbols with `100` total shares spread across multiple accounts as not yet Bull Strangle-ready unless a single account has `100` shares.

Current weekend decision command:

```powershell
python -m bullstrangle_mcp.cli --db data\bullstrangle.db generate-weekend-decisions 2026-04-17 --decision-date 2026-04-25 --output reports\2026-04-22\weekend_decisions_2026-04-17.md
```

Current April 17 v1 decision output using one OS upload:

- decision batch: `1`
- Bull Strangle: `22 APPROVE`, `0 WATCH`, `2 SKIP`
- DCA: `22 APPROVE`, `1 WATCH`, `1 SKIP`

## Planned Reporting Tables

### `report_templates`

Stores reusable report templates and report metadata.

Proposed fields:

- `template_id`
- `template_name`
- `report_type`
- `template_version`
- `description`
- `template_content`
- `required_sources_json`
- `is_active`
- `created_at`

Initial report types:

- `newsletter_ingestion_summary`
- `daily_os_deviation`
- `weekly_market_environment`
- `weekend_decision_summary`
- `bull_strangle_decision`
- `dca_decision`
- `audit_report`

### `report_runs`

One row per report generation event.

Proposed fields:

- `report_run_id`
- `report_type`
- `newsletter_id`
- `newsletter_date`
- `expiration_date`
- `decision_batch_id`
- `os_evaluation_run_id`
- `status`
- `generated_at`
- `source_snapshot_json`
- `warnings_json`

### `generated_reports`

Stores report content and optional output paths.

Proposed fields:

- `report_id`
- `report_run_id`
- `report_type`
- `title`
- `format`
- `content`
- `output_path`
- `created_at`

Supported formats:

- `markdown`
- `html`
- `xlsx`
- `pdf`

v1 should generate Markdown only. Other formats can be generated from Markdown later.

## Planned Reports

### Newsletter Ingestion Summary

Generated after PDF ingestion.

Reads:

- `newsletters`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deep_analysis`
- `market_environment`
- `strategy_reference_sections`
- `newsletter_full_text`

Purpose:

- Confirm publication date, entry date, expiration date.
- Confirm watchlist count.
- Confirm short-list count.
- Confirm favorite/deep-analysis count.
- Confirm market environment metrics.
- Flag missing or low-confidence extraction.

### Daily OS Deviation Report

Generated after each uploaded/refreshed OS Excel workbook.

Reads:

- `os_evaluation_runs`
- `os_evaluation_rows`
- `watchlist_deviations`
- `watchlist_entries`

Purpose:

- Show live OS values versus newsletter baseline.
- Highlight large price, IV, strike, and premium deviations.
- Flag stale/missing OS formulas.
- Flag missing symbols or unexpected extra symbols.

### Weekly Market Environment Report

Generated on demand and as part of weekend decision reports.

Reads:

- `market_environment`

Purpose:

- Summarize market regime.
- Explain deploy/pause state.
- Include useful commentary from `commentary_json`.
- Show consecutive-week rule state.

### Weekend Decision Summary

Generated after weekend decision batch.

Reads:

- `decision_batches`
- `bull_strangle_decisions`
- `dca_decisions`
- `market_environment`

Purpose:

- Provide one high-level weekend action plan.
- Summarize approved, skipped, and watch-only symbols.
- Separate Bull Strangle and DCA actions.

### Bull Strangle Decision Report

Generated after weekend Bull Strangle decisions.

Reads:

- `bull_strangle_decisions`
- `watchlist_entries`
- `short_list_entries`
- `watchlist_deviations`
- `os_evaluation_rows`
- `market_environment`
- `strategy_rules`

Purpose:

- Explain final approve/skip/watch decisions symbol by symbol.
- Include rules applied.
- Include market gate state.
- Include latest and max weekly deviations.
- Include OS signal summary.

### DCA Decision Report

Generated after weekend DCA decisions.

Reads:

- `dca_decisions`
- `watchlist_entries`
- `watchlist_deep_analysis`
- `watchlist_deviations`
- `os_evaluation_rows`
- `market_environment`
- future holdings/account state

Purpose:

- Explain DCA buy/hold/skip decisions.
- Include share targets and current holdings once holdings are implemented.
- Include price/IV trend from daily OS snapshots.

### Audit Report

Generated on demand.

Reads all relevant tables.

Purpose:

- Detect missing newsletter sections.
- Detect missing OS uploads.
- Detect missing OS symbols.
- Detect stale workbook uploads.
- Detect formula errors imported from Excel.
- Detect ungenerated weekend decisions.
- Detect incomplete report generation.

## Open Design Points

1. Exact OS Excel input/output columns.
2. Workbook template format and formula zones.
3. Whether DCA candidate ranking is explicit in the newsletter or inferred from favorites/short list.
4. Account selection policy for DCA and Bull Strangle execution when positions are spread across accounts.
5. Exact weekend aggregation policy: latest OS upload plus weekly max deviations is the recommended v1 default.
6. Thresholds for acceptable deviation from newsletter baseline.
7. Report template format and final output directory convention.
8. Whether generated reports are stored only in DB or also written to files under `reports/`.

## Next Steps

1. Done: inspect the Option Samurai Excel workbook/template.
2. Define the generated workbook contract:
   - sheets
   - headers
   - formula columns
   - user-edit columns
   - protected ranges
3. Implement `os_workbooks`.
4. Implement workbook generation from `watchlist_entries`.
5. Implement daily Excel upload ingestion:
   - `os_evaluation_runs`
   - `os_evaluation_rows`
6. Implement `watchlist_deviations`.
7. Done: implement weekly OS aggregation across all daily runs for one newsletter cycle.
8. Done: define v1 weekend decision rule set with concrete criteria.
9. Done: implement `decision_batches`.
10. Done: implement `bull_strangle_decisions`.
11. Done: implement `dca_decisions`.
12. Extract Master Document strategy rules into structured implementation tasks.
13. Tune weekend decision criteria after several daily OS uploads.
14. Done: add DCA holdings/account input and single-account execution selection.
15. Add reports:
   - daily OS deviation report
   - weekend Bull Strangle decision report
   - weekend DCA decision report
16. Add report persistence:
   - `report_templates`
   - `report_runs`
   - `generated_reports`

## Architect Review

### Requirements Captured

The design now captures the core workflow requirements:

- Weekly PDF newsletter ingestion.
- Consolidated immutable newsletter watchlist baseline.
- Watch List with Option Prices and Watch List screening details in one table.
- Short-list membership retained separately.
- Watch List Favorites and proposed trades stored as JSON.
- Market recap, S&P market overview text, and market environment combined into `market_environment`.
- Chart-only market overview pages skipped because charts can be recreated later from normalized data.
- Common strategy implementation appendix stored once as common reference.
- Option Samurai workbook generation implemented from newsletter baseline.
- Option Samurai formulas documented from the provided workbook and PDFs.
- Daily Excel uploads implemented as OS evaluation runs and rows.
- Daily deviations from newsletter baseline implemented.
- Daily OS run audit/deviation report implemented.
- Weekly OS aggregation implemented.
- V1 weekend decision batch generation implemented.
- V1 Bull Strangle decisions implemented.
- V1 DCA candidate decisions implemented.
- Claude-compatible MCP server implemented.
- DCA and Bull Strangle decisions generated only once on the weekend.
- Placeholder `watchlist_decisions` removed.
- Reporting layer planned downstream from normalized data.

### Current Implemented Scope

Implemented:

- PDF ingestion.
- Current DB schema for newsletter baseline.
- Consolidated watchlist baseline.
- Market environment and commentary consolidation.
- Common strategy reference extraction.
- Full raw section text for audit/reprocessing.
- OS workbook metadata table.
- Newsletter-average OS selector calculation.
- Rounded selector and strike rounding policy persistence.
- OS workbook generation.
- Daily uploaded workbook ingestion.
- Daily OS evaluation row storage.
- Deviation tracking.
- Daily OS run audit/deviation report.
- Claude-compatible MCP server.

Not yet implemented:

- Tuned decision thresholds based on real multi-day OS uploads.
- Holdings/account state for DCA executable allocation decisions.
- Report persistence tables (`report_templates`, `report_runs`, `generated_reports`).
- Weekend decision reports.

### Architectural Strengths

- Immutable baseline: newsletter values are not overwritten by daily live data.
- Clean temporal separation: daily OS snapshots versus weekend decisions.
- Auditability: raw PDF text and JSON snapshots are retained.
- Lean current schema: no premature symbol-level decision table at newsletter ingestion time.
- Clear future decision tables: DCA and Bull Strangle decisions are separated.
- Reporting is downstream-only, reducing the risk of report code mutating source data.

### Risks and Gaps

1. OS workbook import fidelity

The exact uploaded workbook shape must be controlled. If users manually change sheet names or headers, ingestion may fail or mis-map values.

Mitigation:

- Generate the workbook from MCP.
- Include hidden metadata columns.
- Validate required headers before ingest.

2. Option Samurai formula values may import as formulas, cached values, or blanks

Python readers usually read cached Excel formula results only if Excel saved the recalculated workbook.

Mitigation:

- Require user to open workbook, refresh OS formulas, save, and upload.
- Ingest with both formula and cached-value checks.
- Add audit report for blank or stale OS values.

3. DCA requirements still need holdings/account state

Current DCA rows are candidate decisions. Executable DCA decisions still require current shares by account, target account selection, available cash, and account constraints. A DCA or Bull Strangle action must be assigned to exactly one account.

Mitigation:

- Add a future holdings/account import layer before final DCA decision implementation.
- Enforce single-account execution and `100`-share promotion eligibility.

4. Weekend decision aggregation rule is v1 only

The implemented v1 uses latest upload values plus weekly max deviation metrics. This should be tuned once several daily OS uploads exist for a newsletter cycle.

Mitigation:

- Start with latest upload plus max deviation metrics.
- Keep all daily rows so aggregation can evolve.

5. Strategy rules need deeper formalization

Current v1 decision gates are explicit in code and stored in JSON snapshots. The seeded `strategy_rules` table is not yet the primary rule execution engine.

Mitigation:

- Convert decision criteria into explicit parameterized rules when implementing weekend decisions.

6. Reporting output convention is not set

Reports can live only in DB, only as files, or both.

Mitigation:

- Store all reports in DB.
- Also write Markdown files under `reports/YYYY-MM-DD/` for user access.

### Recommended Implementation Order

1. Done: lock generated workbook contract for selector calculation and rounding.
2. Done: implement `os_workbooks` metadata and formula contract persistence.
3. Done: generate the simplified `OS_Live` workbook from `watchlist_entries`.
4. Done: implement upload validation and `os_evaluation_runs`.
5. Done: implement `os_evaluation_rows`.
6. Done: implement `watchlist_deviations`.
7. Done: implement daily OS deviation report.
8. Done: implement weekly OS aggregation across all daily runs for one newsletter cycle.
9. Done: define v1 weekend decision criteria and aggregation policy.
10. Done: implement `decision_batches`.
11. Done: implement `bull_strangle_decisions`.
12. Done: implement v1 `dca_decisions`.
13. Next: tune decision criteria after multiple daily OS uploads.
14. Done: implement DCA holdings/account input and single-account execution selection.
15. Implement weekend reports.
16. Add report persistence tables if report history needs to be queryable from DB.
