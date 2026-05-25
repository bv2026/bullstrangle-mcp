# BullStrangle Target Schema v4

Status: Revised Target Schema Draft
Date: 2026-05-25
Scope: PostgreSQL schema design for the new self-contained BullStrangle refactor project.

## 1. Superseding Guardrails

This schema supersedes the prior SQLite-oriented draft.

Hard requirements:
- The refactor is a new self-contained project from scratch.
- Legacy BullStrangle runtime must remain untouched and operational.
- The new runtime must not depend on legacy Python modules or legacy SQLite tables.
- Legacy code/data may be read only for context or explicit one-way import.
- PostgreSQL is the primary runtime database.
- SQLite is legacy import source only, never the new runtime DB.
- PostgreSQL-native types and constraints are required.
- Use `jsonb` for raw provider payloads, rule evidence, model assumptions, probability inputs, broker payloads, and audit evidence.
- Use `timestamptz` for market data, provider timestamps, decisions, fills, lifecycle events, approvals, audit timestamps, and broker timestamps.
- Keep live trading readiness in the schema even while live execution is disabled initially.

## 2. Project Boundary

The new project owns its own PostgreSQL database, schema, migrations, data-access layer, provider clients, execution lifecycle, reports, and tests.

Legacy `bullstrangle-mcp` runtime remains separate:
- No imports from legacy runtime modules in the new runtime.
- No runtime reads from legacy SQLite tables.
- No shared writable database.
- No mutation of legacy SQLite data.
- Optional one-way import jobs may read legacy SQLite and write normalized rows into PostgreSQL import/staging tables.

Recommended PostgreSQL schema namespace:

```sql
CREATE SCHEMA IF NOT EXISTS bullstrangle;
```

All new runtime tables should live under `bullstrangle`.

## 3. Migration Tooling

Recommendation: use Alembic with SQLAlchemy 2.x.

Requirements:
- Alembic owns PostgreSQL DDL for the new project.
- Migrations are append-only and reviewed.
- Migrations must be idempotent at environment level but not silently skip incompatible drift.
- Local dev and test databases must be reproducible from migrations.
- Seed/reference data should be explicit migrations or deterministic seed scripts.
- Legacy import scripts are separate from runtime migrations.

Recommended migration layout:

```text
new-project/
  alembic.ini
  migrations/
    env.py
    versions/
  src/
    bullstrangle/
      db/
        models.py
        session.py
        import_legacy.py
```

## 4. PostgreSQL Type Strategy

Use PostgreSQL-native types:
- `bigserial` or `generated always as identity` for surrogate PKs.
- `uuid` for externally safe IDs, idempotency keys, and import batch IDs where useful.
- `numeric(18,6)` for prices, credits, P/L, rates, and capital values.
- `numeric(10,6)` for probabilities, deltas, IV, percentages, and scores.
- `integer`/`bigint` for counts and quantities.
- `text` for symbols, provider IDs, broker IDs, statuses, and notes.
- `date` for publication dates, expirations, and earnings dates.
- `timestamptz` for all event/audit/market timestamps.
- `jsonb` for raw payloads, evidence, assumptions, normalized snapshots, and extensible audit details.

Recommended extensions:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
```

Use `gen_random_uuid()` for UUID defaults.

## 5. Enum And Lookup Strategy

For values that may evolve often, prefer lookup/config tables or constrained `text` plus check constraints. Avoid hard PostgreSQL enum types unless the value set is very stable.

Use check constraints for core lifecycle states to catch invalid writes.

Core status values:
- decision status: `ACCEPT`, `WATCH`, `REJECT`, `DATA_UNAVAILABLE`
- execution mode: `planning`, `paper`, `shadow`, `live`
- order status: `draft`, `approval_pending`, `approved`, `submitted`, `partially_filled`, `filled`, `cancelled`, `rejected`, `expired`
- fill source: `simulated`, `broker_api`, `manual_import`
- lifecycle event types: stored in `lifecycle_event_types` lookup table or constrained in application code.

## 6. Legacy Import Boundary

SQLite legacy data is not part of the runtime schema. It may be imported through explicit one-way jobs.

Legacy import source examples:
- newsletters
- newsletter_full_text
- watchlist_entries
- short_list_entries
- market_environment
- os_evaluation_rows
- existing paper/backtest rows for historical comparison

Import principles:
- Every import run has an import batch row.
- Imported rows store legacy table name and legacy primary key for auditability.
- Imported rows become native PostgreSQL rows.
- Runtime code reads only PostgreSQL-native tables.
- Re-import must be idempotent by legacy source key and import version.

## 7. Import Tables

### 7.1 `legacy_import_batches`

```sql
CREATE TABLE bullstrangle.legacy_import_batches (
    import_batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name text NOT NULL,
    source_path text,
    source_hash text,
    import_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    error jsonb
);
```

Indexes:

```sql
CREATE INDEX idx_legacy_import_batches_source
ON bullstrangle.legacy_import_batches(source_name, import_version, started_at DESC);
```

### 7.2 Legacy Key Columns

Native imported tables should include:

```sql
legacy_import_batch_id uuid REFERENCES bullstrangle.legacy_import_batches(import_batch_id),
legacy_source_table text,
legacy_source_pk text
```

Add unique indexes where imported records need idempotency:

```sql
UNIQUE (legacy_source_table, legacy_source_pk)
```

## 8. Artifact And Newsletter Domain

### 8.1 `newsletters`

```sql
CREATE TABLE bullstrangle.newsletters (
    newsletter_id bigserial PRIMARY KEY,
    publication_date date NOT NULL UNIQUE,
    source_title text,
    source_uri text,
    source_sha256 text,
    target_expiration date,
    entry_date date,
    market_outlook text,
    strategy_notes text,
    raw_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    ingestion_method text,
    legacy_import_batch_id uuid REFERENCES bullstrangle.legacy_import_batches(import_batch_id),
    legacy_source_table text,
    legacy_source_pk text,
    UNIQUE (legacy_source_table, legacy_source_pk)
);
```

Indexes:

```sql
CREATE INDEX idx_newsletters_pub_date
ON bullstrangle.newsletters(publication_date DESC);
```

### 8.2 `newsletter_sections`

```sql
CREATE TABLE bullstrangle.newsletter_sections (
    section_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    section_name text NOT NULL,
    section_type text,
    page_start integer,
    page_end integer,
    content text NOT NULL,
    extraction_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (newsletter_id, section_name)
);
```

Indexes:

```sql
CREATE INDEX idx_newsletter_sections_newsletter
ON bullstrangle.newsletter_sections(newsletter_id);

CREATE INDEX idx_newsletter_sections_content_gin
ON bullstrangle.newsletter_sections USING gin (to_tsvector('english', content));
```

### 8.3 `watchlist_entries`

```sql
CREATE TABLE bullstrangle.watchlist_entries (
    watchlist_entry_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    symbol text NOT NULL,
    company_name text,
    sector text,
    industry text,
    sub_sector text,
    published_stock_price numeric(18,6),
    published_iv numeric(10,6),
    published_total_open_interest integer,
    earnings_date date,
    published_sell_call_strike numeric(18,6),
    published_sell_call_premium numeric(18,6),
    published_sell_put_strike numeric(18,6),
    published_sell_put_premium numeric(18,6),
    published_buy_put_strike numeric(18,6),
    published_buy_put_premium numeric(18,6),
    published_return_pct numeric(10,6),
    is_favorite boolean NOT NULL DEFAULT false,
    source_page integer,
    raw_line text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    legacy_import_batch_id uuid REFERENCES bullstrangle.legacy_import_batches(import_batch_id),
    legacy_source_table text,
    legacy_source_pk text,
    UNIQUE (newsletter_id, symbol),
    UNIQUE (legacy_source_table, legacy_source_pk)
);
```

Indexes:

```sql
CREATE INDEX idx_watchlist_entries_symbol
ON bullstrangle.watchlist_entries(symbol);

CREATE INDEX idx_watchlist_entries_newsletter
ON bullstrangle.watchlist_entries(newsletter_id);
```

### 8.4 `short_list_entries`

```sql
CREATE TABLE bullstrangle.short_list_entries (
    short_list_entry_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    watchlist_entry_id bigint REFERENCES bullstrangle.watchlist_entries(watchlist_entry_id) ON DELETE SET NULL,
    portfolio_type text NOT NULL CHECK (portfolio_type IN ('large','small')),
    symbol text NOT NULL,
    rank integer,
    source_page integer,
    raw_line text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    legacy_import_batch_id uuid REFERENCES bullstrangle.legacy_import_batches(import_batch_id),
    legacy_source_table text,
    legacy_source_pk text,
    UNIQUE (newsletter_id, portfolio_type, symbol),
    UNIQUE (legacy_source_table, legacy_source_pk)
);
```

Indexes:

```sql
CREATE INDEX idx_short_list_entries_newsletter_portfolio
ON bullstrangle.short_list_entries(newsletter_id, portfolio_type);

CREATE INDEX idx_short_list_entries_symbol
ON bullstrangle.short_list_entries(symbol);
```

### 8.5 `newsletter_intelligence`

```sql
CREATE TABLE bullstrangle.newsletter_intelligence (
    intelligence_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL UNIQUE REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    market_thesis text,
    risk_posture text,
    sector_emphasis jsonb NOT NULL DEFAULT '[]'::jsonb,
    theme_emphasis jsonb NOT NULL DEFAULT '[]'::jsonb,
    caution_language jsonb NOT NULL DEFAULT '[]'::jsonb,
    uncertainty_signals jsonb NOT NULL DEFAULT '[]'::jsonb,
    week_over_week_changes jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

## 9. Strategy, Rule, And Policy Domain

### 9.1 `strategy_rules`

```sql
CREATE TABLE bullstrangle.strategy_rules (
    rule_id bigserial PRIMARY KEY,
    rule_code text NOT NULL,
    rule_version text NOT NULL,
    rule_area text NOT NULL,
    rule_classification text NOT NULL CHECK (rule_classification IN ('hard','soft','advisory','retired')),
    description text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_reference text,
    effective_from timestamptz,
    effective_to timestamptz,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rule_code, rule_version)
);
```

Indexes:

```sql
CREATE INDEX idx_strategy_rules_area_status
ON bullstrangle.strategy_rules(rule_area, status);
```

### 9.2 `pricing_policies`

```sql
CREATE TABLE bullstrangle.pricing_policies (
    pricing_policy_id bigserial PRIMARY KEY,
    policy_code text NOT NULL,
    policy_version text NOT NULL,
    short_option_price_source text NOT NULL,
    long_option_price_source text NOT NULL,
    stock_buy_price_source text NOT NULL,
    stock_sell_price_source text NOT NULL,
    spread_adjustment jsonb NOT NULL DEFAULT '{}'::jsonb,
    commission_model jsonb NOT NULL DEFAULT '{}'::jsonb,
    rounding_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    effective_from timestamptz,
    effective_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_code, policy_version)
);
```

### 9.3 `strike_selection_policies`

```sql
CREATE TABLE bullstrangle.strike_selection_policies (
    strike_policy_id bigserial PRIMARY KEY,
    policy_code text NOT NULL,
    policy_version text NOT NULL,
    target_dte integer NOT NULL DEFAULT 28,
    min_dte integer,
    max_dte integer,
    expiration_selection_rule text NOT NULL,
    short_call_delta_min numeric(10,6),
    short_call_delta_max numeric(10,6),
    short_call_delta_target numeric(10,6),
    short_put_delta_min numeric(10,6),
    short_put_delta_max numeric(10,6),
    short_put_delta_target numeric(10,6),
    long_put_selection_rule text,
    long_put_delta_min numeric(10,6),
    long_put_delta_max numeric(10,6),
    long_put_delta_target numeric(10,6),
    min_bid numeric(18,6),
    max_spread_pct numeric(10,6),
    max_spread_abs numeric(18,6),
    min_open_interest integer,
    min_volume integer,
    missing_greeks_policy text NOT NULL DEFAULT 'warn',
    tie_breaker jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    effective_from timestamptz,
    effective_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_code, policy_version)
);
```

### 9.4 `pl_formula_versions`

```sql
CREATE TABLE bullstrangle.pl_formula_versions (
    pl_formula_version_id bigserial PRIMARY KEY,
    formula_code text NOT NULL,
    formula_version text NOT NULL,
    capital_model text NOT NULL,
    annualization_basis text NOT NULL,
    include_commissions boolean NOT NULL DEFAULT false,
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    effective_from timestamptz,
    effective_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (formula_code, formula_version)
);
```

### 9.5 `probability_model_versions`

```sql
CREATE TABLE bullstrangle.probability_model_versions (
    probability_model_version_id bigserial PRIMARY KEY,
    model_code text NOT NULL,
    model_version text NOT NULL,
    model_family text NOT NULL,
    iv_source_policy text NOT NULL,
    rate_source_policy text,
    dividend_policy text,
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    effective_from timestamptz,
    effective_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model_code, model_version)
);
```

### 9.6 `strategy_policy_versions`

```sql
CREATE TABLE bullstrangle.strategy_policy_versions (
    strategy_policy_version_id bigserial PRIMARY KEY,
    policy_code text NOT NULL,
    policy_version text NOT NULL,
    pricing_policy_id bigint NOT NULL REFERENCES bullstrangle.pricing_policies(pricing_policy_id),
    strike_policy_id bigint NOT NULL REFERENCES bullstrangle.strike_selection_policies(strike_policy_id),
    pl_formula_version_id bigint NOT NULL REFERENCES bullstrangle.pl_formula_versions(pl_formula_version_id),
    probability_model_version_id bigint NOT NULL REFERENCES bullstrangle.probability_model_versions(probability_model_version_id),
    rule_bundle jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('draft','active','retired')) DEFAULT 'draft',
    effective_from timestamptz,
    effective_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_code, policy_version)
);
```

## 10. Market Data Provider Domain

### 10.1 `market_data_runs`

```sql
CREATE TABLE bullstrangle.market_data_runs (
    market_data_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id text NOT NULL,
    provider_name text NOT NULL,
    provider_environment text,
    run_type text NOT NULL CHECK (run_type IN ('quote','option_chain','scan','mark')),
    symbol text,
    expiration_date date,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL CHECK (status IN ('started','success','partial','failed')) DEFAULT 'started',
    request jsonb NOT NULL DEFAULT '{}'::jsonb,
    error jsonb,
    raw_response jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

Indexes:

```sql
CREATE INDEX idx_market_data_runs_provider_time
ON bullstrangle.market_data_runs(provider_id, started_at DESC);

CREATE INDEX idx_market_data_runs_symbol_exp
ON bullstrangle.market_data_runs(symbol, expiration_date);

CREATE INDEX idx_market_data_runs_status
ON bullstrangle.market_data_runs(status);
```

### 10.2 `stock_quote_snapshots`

```sql
CREATE TABLE bullstrangle.stock_quote_snapshots (
    stock_quote_id bigserial PRIMARY KEY,
    market_data_run_id uuid NOT NULL REFERENCES bullstrangle.market_data_runs(market_data_run_id) ON DELETE CASCADE,
    provider_id text NOT NULL,
    symbol text NOT NULL,
    bid numeric(18,6),
    ask numeric(18,6),
    last numeric(18,6),
    mark numeric(18,6),
    mid numeric(18,6),
    volume bigint,
    provider_quote_at timestamptz,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    is_delayed boolean NOT NULL DEFAULT false,
    freshness_seconds integer,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (market_data_run_id, symbol)
);
```

Indexes:

```sql
CREATE INDEX idx_stock_quotes_symbol_time
ON bullstrangle.stock_quote_snapshots(symbol, retrieved_at DESC);
```

### 10.3 `option_chain_snapshots`

```sql
CREATE TABLE bullstrangle.option_chain_snapshots (
    chain_snapshot_id bigserial PRIMARY KEY,
    market_data_run_id uuid NOT NULL REFERENCES bullstrangle.market_data_runs(market_data_run_id) ON DELETE CASCADE,
    provider_id text NOT NULL,
    underlying_symbol text NOT NULL,
    expiration_date date NOT NULL,
    provider_chain_at timestamptz,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    is_delayed boolean NOT NULL DEFAULT false,
    row_count integer NOT NULL DEFAULT 0,
    status text NOT NULL CHECK (status IN ('complete','partial','failed')) DEFAULT 'complete',
    error jsonb,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (market_data_run_id, underlying_symbol, expiration_date)
);
```

Indexes:

```sql
CREATE INDEX idx_option_chain_symbol_exp_time
ON bullstrangle.option_chain_snapshots(underlying_symbol, expiration_date, retrieved_at DESC);
```

### 10.4 `option_chain_rows`

```sql
CREATE TABLE bullstrangle.option_chain_rows (
    option_row_id bigserial PRIMARY KEY,
    chain_snapshot_id bigint NOT NULL REFERENCES bullstrangle.option_chain_snapshots(chain_snapshot_id) ON DELETE CASCADE,
    provider_id text NOT NULL,
    provider_contract_id text,
    occ_symbol text,
    underlying_symbol text NOT NULL,
    expiration_date date NOT NULL,
    option_right text NOT NULL CHECK (option_right IN ('call','put')),
    strike numeric(18,6) NOT NULL,
    multiplier integer NOT NULL DEFAULT 100,
    bid numeric(18,6),
    ask numeric(18,6),
    mid numeric(18,6),
    last numeric(18,6),
    mark numeric(18,6),
    delta numeric(10,6),
    gamma numeric(10,6),
    theta numeric(10,6),
    vega numeric(10,6),
    rho numeric(10,6),
    iv numeric(10,6),
    volume bigint,
    open_interest bigint,
    provider_quote_at timestamptz,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    is_adjusted boolean NOT NULL DEFAULT false,
    is_weekly boolean,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (chain_snapshot_id, option_right, strike)
);
```

Indexes:

```sql
CREATE INDEX idx_option_rows_chain_right_strike
ON bullstrangle.option_chain_rows(chain_snapshot_id, option_right, strike);

CREATE INDEX idx_option_rows_occ_symbol
ON bullstrangle.option_chain_rows(occ_symbol);

CREATE INDEX idx_option_rows_underlying_exp
ON bullstrangle.option_chain_rows(underlying_symbol, expiration_date);
```

### 10.5 `provider_health_events`

```sql
CREATE TABLE bullstrangle.provider_health_events (
    provider_health_event_id bigserial PRIMARY KEY,
    provider_id text NOT NULL,
    market_data_run_id uuid REFERENCES bullstrangle.market_data_runs(market_data_run_id) ON DELETE SET NULL,
    event_type text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('info','warning','error','critical')) DEFAULT 'info',
    message text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

Indexes:

```sql
CREATE INDEX idx_provider_health_provider_time
ON bullstrangle.provider_health_events(provider_id, created_at DESC);
```

## 11. Scanner, P/L, Probability, And Decisions

### 11.1 `live_watchlist_snapshots`

```sql
CREATE TABLE bullstrangle.live_watchlist_snapshots (
    live_snapshot_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    watchlist_entry_id bigint REFERENCES bullstrangle.watchlist_entries(watchlist_entry_id) ON DELETE SET NULL,
    short_list_entry_id bigint REFERENCES bullstrangle.short_list_entries(short_list_entry_id) ON DELETE SET NULL,
    symbol text NOT NULL,
    portfolio_type text CHECK (portfolio_type IN ('large','small')),
    scan_mode text NOT NULL CHECK (scan_mode IN ('newsletter_replication','live_strike_selection')),
    market_data_run_id uuid REFERENCES bullstrangle.market_data_runs(market_data_run_id) ON DELETE SET NULL,
    stock_quote_id bigint REFERENCES bullstrangle.stock_quote_snapshots(stock_quote_id) ON DELETE SET NULL,
    chain_snapshot_id bigint REFERENCES bullstrangle.option_chain_snapshots(chain_snapshot_id) ON DELETE SET NULL,
    expiration_date date,
    strategy_policy_version_id bigint REFERENCES bullstrangle.strategy_policy_versions(strategy_policy_version_id) ON DELETE SET NULL,
    selected_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL CHECK (status IN ('selected','data_unavailable','no_eligible_chain','no_eligible_strikes')),
    status_reason text,
    raw_selection jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key uuid NOT NULL DEFAULT gen_random_uuid(),
    UNIQUE (idempotency_key)
);
```

Indexes:

```sql
CREATE INDEX idx_live_snapshots_newsletter_symbol
ON bullstrangle.live_watchlist_snapshots(newsletter_id, symbol);

CREATE INDEX idx_live_snapshots_mode_status
ON bullstrangle.live_watchlist_snapshots(scan_mode, status);
```

### 11.2 `selected_trade_legs`

```sql
CREATE TABLE bullstrangle.selected_trade_legs (
    selected_leg_id bigserial PRIMARY KEY,
    live_snapshot_id bigint NOT NULL REFERENCES bullstrangle.live_watchlist_snapshots(live_snapshot_id) ON DELETE CASCADE,
    option_row_id bigint REFERENCES bullstrangle.option_chain_rows(option_row_id) ON DELETE SET NULL,
    leg_role text NOT NULL CHECK (leg_role IN ('long_stock','short_call','short_put','long_put')),
    asset_type text NOT NULL CHECK (asset_type IN ('equity','option')),
    underlying_symbol text NOT NULL,
    option_right text CHECK (option_right IN ('call','put')),
    expiration_date date,
    strike numeric(18,6),
    quantity integer NOT NULL,
    side text NOT NULL CHECK (side IN ('buy','sell')),
    raw_bid numeric(18,6),
    raw_ask numeric(18,6),
    raw_mid numeric(18,6),
    execution_price numeric(18,6),
    execution_price_source text,
    delta numeric(10,6),
    iv numeric(10,6),
    volume bigint,
    open_interest bigint,
    spread_abs numeric(18,6),
    spread_pct numeric(10,6),
    selection_rank integer,
    selection_reason text,
    rejected_alternatives jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (live_snapshot_id, leg_role)
);
```

Indexes:

```sql
CREATE INDEX idx_selected_legs_snapshot
ON bullstrangle.selected_trade_legs(live_snapshot_id);
```

### 11.3 `pl_evaluations`

```sql
CREATE TABLE bullstrangle.pl_evaluations (
    pl_evaluation_id bigserial PRIMARY KEY,
    live_snapshot_id bigint NOT NULL REFERENCES bullstrangle.live_watchlist_snapshots(live_snapshot_id) ON DELETE CASCADE,
    pl_formula_version_id bigint REFERENCES bullstrangle.pl_formula_versions(pl_formula_version_id) ON DELETE SET NULL,
    pricing_policy_id bigint REFERENCES bullstrangle.pricing_policies(pricing_policy_id) ON DELETE SET NULL,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    stock_price_assumption numeric(18,6),
    total_credit numeric(18,6),
    capital_required numeric(18,6),
    downside_breakeven numeric(18,6),
    called_away_profit numeric(18,6),
    put_assigned_cost_basis numeric(18,6),
    max_modeled_loss numeric(18,6),
    return_on_capital_pct numeric(10,6),
    annualized_return_pct numeric(10,6),
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
    outputs jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

Indexes:

```sql
CREATE INDEX idx_pl_evaluations_snapshot
ON bullstrangle.pl_evaluations(live_snapshot_id);
```

### 11.4 `pl_scenario_rows`

```sql
CREATE TABLE bullstrangle.pl_scenario_rows (
    pl_scenario_row_id bigserial PRIMARY KEY,
    pl_evaluation_id bigint NOT NULL REFERENCES bullstrangle.pl_evaluations(pl_evaluation_id) ON DELETE CASCADE,
    scenario_label text NOT NULL,
    underlying_price numeric(18,6) NOT NULL,
    stock_pnl numeric(18,6),
    short_call_pnl numeric(18,6),
    short_put_pnl numeric(18,6),
    long_put_pnl numeric(18,6),
    total_pnl numeric(18,6),
    outcome_category text,
    notes text
);
```

### 11.5 `probability_evaluations`

```sql
CREATE TABLE bullstrangle.probability_evaluations (
    probability_evaluation_id bigserial PRIMARY KEY,
    live_snapshot_id bigint NOT NULL REFERENCES bullstrangle.live_watchlist_snapshots(live_snapshot_id) ON DELETE CASCADE,
    probability_model_version_id bigint REFERENCES bullstrangle.probability_model_versions(probability_model_version_id) ON DELETE SET NULL,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    input_stock_price numeric(18,6),
    input_iv numeric(10,6),
    input_dte integer,
    risk_free_rate numeric(10,6),
    dividend_assumption text,
    prob_profit numeric(10,6),
    prob_short_call_otm numeric(10,6),
    prob_short_put_otm numeric(10,6),
    prob_between_short_strikes numeric(10,6),
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
    outputs jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

Indexes:

```sql
CREATE INDEX idx_probability_evals_snapshot
ON bullstrangle.probability_evaluations(live_snapshot_id);
```

### 11.6 `entry_decisions`

This is the new project decision table. It is not the legacy SQLite `entry_decisions` table.

```sql
CREATE TABLE bullstrangle.entry_decisions (
    decision_id bigserial PRIMARY KEY,
    newsletter_id bigint NOT NULL REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE CASCADE,
    watchlist_entry_id bigint REFERENCES bullstrangle.watchlist_entries(watchlist_entry_id) ON DELETE SET NULL,
    live_snapshot_id bigint REFERENCES bullstrangle.live_watchlist_snapshots(live_snapshot_id) ON DELETE SET NULL,
    pl_evaluation_id bigint REFERENCES bullstrangle.pl_evaluations(pl_evaluation_id) ON DELETE SET NULL,
    probability_evaluation_id bigint REFERENCES bullstrangle.probability_evaluations(probability_evaluation_id) ON DELETE SET NULL,
    strategy_policy_version_id bigint REFERENCES bullstrangle.strategy_policy_versions(strategy_policy_version_id) ON DELETE SET NULL,
    symbol text NOT NULL,
    portfolio_type text CHECK (portfolio_type IN ('large','small')),
    decision_status text NOT NULL CHECK (decision_status IN ('ACCEPT','WATCH','REJECT','DATA_UNAVAILABLE')),
    strategy_decision_status text,
    portfolio_actionability_status text,
    confidence_level text CHECK (confidence_level IN ('HIGH','MEDIUM','LOW','REJECT') OR confidence_level IS NULL),
    rule_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    liquidity_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    portfolio_fit jsonb NOT NULL DEFAULT '{}'::jsonb,
    explanation text,
    decided_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key uuid NOT NULL DEFAULT gen_random_uuid(),
    UNIQUE (idempotency_key)
);
```

Indexes:

```sql
CREATE INDEX idx_entry_decisions_newsletter_symbol
ON bullstrangle.entry_decisions(newsletter_id, symbol);

CREATE INDEX idx_entry_decisions_status_time
ON bullstrangle.entry_decisions(decision_status, decided_at DESC);

CREATE INDEX idx_entry_decisions_rule_evidence_gin
ON bullstrangle.entry_decisions USING gin (rule_evidence);
```

## 12. Execution Lifecycle: Paper, Shadow, Live

### 12.1 `trade_intents`

```sql
CREATE TABLE bullstrangle.trade_intents (
    trade_intent_id bigserial PRIMARY KEY,
    decision_id bigint NOT NULL REFERENCES bullstrangle.entry_decisions(decision_id) ON DELETE CASCADE,
    newsletter_id bigint REFERENCES bullstrangle.newsletters(newsletter_id) ON DELETE SET NULL,
    symbol text NOT NULL,
    portfolio_type text CHECK (portfolio_type IN ('large','small')),
    execution_mode text NOT NULL CHECK (execution_mode IN ('planning','paper','shadow','live')),
    intent_status text NOT NULL DEFAULT 'created',
    account_id text,
    paper_portfolio_id bigint,
    quantity_multiplier integer NOT NULL DEFAULT 1,
    source_snapshot_id bigint REFERENCES bullstrangle.live_watchlist_snapshots(live_snapshot_id) ON DELETE SET NULL,
    idempotency_key uuid NOT NULL DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    UNIQUE (idempotency_key)
);
```

Indexes:

```sql
CREATE INDEX idx_trade_intents_decision
ON bullstrangle.trade_intents(decision_id);

CREATE INDEX idx_trade_intents_mode_status
ON bullstrangle.trade_intents(execution_mode, intent_status);
```

### 12.2 `order_drafts`

```sql
CREATE TABLE bullstrangle.order_drafts (
    order_draft_id bigserial PRIMARY KEY,
    trade_intent_id bigint NOT NULL REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE CASCADE,
    draft_version integer NOT NULL DEFAULT 1,
    execution_mode text NOT NULL CHECK (execution_mode IN ('paper','shadow','live')),
    broker text,
    account_id text,
    order_type text NOT NULL,
    time_in_force text,
    net_price_type text NOT NULL,
    limit_price numeric(18,6),
    pricing_policy_id bigint REFERENCES bullstrangle.pricing_policies(pricing_policy_id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'draft',
    idempotency_key uuid NOT NULL DEFAULT gen_random_uuid(),
    draft_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    UNIQUE (trade_intent_id, draft_version),
    UNIQUE (idempotency_key)
);
```

### 12.3 `order_draft_legs`

```sql
CREATE TABLE bullstrangle.order_draft_legs (
    order_draft_leg_id bigserial PRIMARY KEY,
    order_draft_id bigint NOT NULL REFERENCES bullstrangle.order_drafts(order_draft_id) ON DELETE CASCADE,
    selected_leg_id bigint REFERENCES bullstrangle.selected_trade_legs(selected_leg_id) ON DELETE SET NULL,
    leg_role text NOT NULL,
    asset_type text NOT NULL CHECK (asset_type IN ('equity','option')),
    symbol text NOT NULL,
    option_right text CHECK (option_right IN ('call','put') OR option_right IS NULL),
    expiration_date date,
    strike numeric(18,6),
    side text NOT NULL CHECK (side IN ('buy','sell')),
    quantity integer NOT NULL,
    limit_price numeric(18,6),
    order_leg_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

### 12.4 `operator_approvals`

```sql
CREATE TABLE bullstrangle.operator_approvals (
    approval_id bigserial PRIMARY KEY,
    order_draft_id bigint NOT NULL REFERENCES bullstrangle.order_drafts(order_draft_id) ON DELETE CASCADE,
    draft_version integer NOT NULL,
    approval_status text NOT NULL CHECK (approval_status IN ('pending','approved','rejected','expired')) DEFAULT 'pending',
    requested_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    approved_by text,
    expires_at timestamptz,
    approval_notes text,
    immutable_draft_hash text NOT NULL,
    approval_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (order_draft_id, draft_version)
);
```

### 12.5 `broker_orders`

```sql
CREATE TABLE bullstrangle.broker_orders (
    broker_order_id bigserial PRIMARY KEY,
    order_draft_id bigint NOT NULL REFERENCES bullstrangle.order_drafts(order_draft_id) ON DELETE CASCADE,
    approval_id bigint REFERENCES bullstrangle.operator_approvals(approval_id) ON DELETE SET NULL,
    broker text NOT NULL,
    broker_account_id text NOT NULL,
    broker_order_ref text,
    client_order_id text NOT NULL,
    order_status text NOT NULL,
    submitted_at timestamptz,
    last_status_at timestamptz,
    native_order_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    native_response jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (broker, broker_account_id, client_order_id)
);
```

Indexes:

```sql
CREATE INDEX idx_broker_orders_ref
ON bullstrangle.broker_orders(broker, broker_order_ref);
```

### 12.6 `broker_order_legs`

```sql
CREATE TABLE bullstrangle.broker_order_legs (
    broker_order_leg_id bigserial PRIMARY KEY,
    broker_order_id bigint NOT NULL REFERENCES bullstrangle.broker_orders(broker_order_id) ON DELETE CASCADE,
    order_draft_leg_id bigint REFERENCES bullstrangle.order_draft_legs(order_draft_leg_id) ON DELETE SET NULL,
    broker_leg_ref text,
    leg_role text,
    asset_type text NOT NULL,
    symbol text NOT NULL,
    side text NOT NULL,
    quantity integer NOT NULL,
    native_leg_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

### 12.7 `fills`

```sql
CREATE TABLE bullstrangle.fills (
    fill_id bigserial PRIMARY KEY,
    trade_intent_id bigint NOT NULL REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE CASCADE,
    order_draft_id bigint REFERENCES bullstrangle.order_drafts(order_draft_id) ON DELETE SET NULL,
    broker_order_id bigint REFERENCES bullstrangle.broker_orders(broker_order_id) ON DELETE SET NULL,
    fill_source text NOT NULL CHECK (fill_source IN ('simulated','broker_api','manual_import')),
    fill_status text NOT NULL DEFAULT 'filled',
    filled_at timestamptz NOT NULL DEFAULT now(),
    quantity_filled integer,
    net_price numeric(18,6),
    commission numeric(18,6),
    fees numeric(18,6),
    native_fill_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text
);
```

### 12.8 `fill_legs`

```sql
CREATE TABLE bullstrangle.fill_legs (
    fill_leg_id bigserial PRIMARY KEY,
    fill_id bigint NOT NULL REFERENCES bullstrangle.fills(fill_id) ON DELETE CASCADE,
    order_draft_leg_id bigint REFERENCES bullstrangle.order_draft_legs(order_draft_leg_id) ON DELETE SET NULL,
    broker_order_leg_id bigint REFERENCES bullstrangle.broker_order_legs(broker_order_leg_id) ON DELETE SET NULL,
    leg_role text NOT NULL,
    asset_type text NOT NULL,
    symbol text NOT NULL,
    option_right text,
    expiration_date date,
    strike numeric(18,6),
    side text NOT NULL CHECK (side IN ('buy','sell')),
    quantity_filled integer NOT NULL,
    fill_price numeric(18,6) NOT NULL,
    commission numeric(18,6),
    fees numeric(18,6),
    native_fill_leg_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

### 12.9 `trade_lifecycle_events`

```sql
CREATE TABLE bullstrangle.trade_lifecycle_events (
    lifecycle_event_id bigserial PRIMARY KEY,
    trade_intent_id bigint NOT NULL REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    event_status text,
    event_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL,
    related_order_draft_id bigint REFERENCES bullstrangle.order_drafts(order_draft_id) ON DELETE SET NULL,
    related_broker_order_id bigint REFERENCES bullstrangle.broker_orders(broker_order_id) ON DELETE SET NULL,
    related_fill_id bigint REFERENCES bullstrangle.fills(fill_id) ON DELETE SET NULL,
    event_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text
);
```

Indexes:

```sql
CREATE INDEX idx_lifecycle_events_intent_time
ON bullstrangle.trade_lifecycle_events(trade_intent_id, event_at);

CREATE INDEX idx_lifecycle_events_payload_gin
ON bullstrangle.trade_lifecycle_events USING gin (event_payload);
```

## 13. Live Positions, Assignments, Outcomes

### 13.1 `live_positions`

```sql
CREATE TABLE bullstrangle.live_positions (
    live_position_id bigserial PRIMARY KEY,
    trade_intent_id bigint REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE SET NULL,
    broker text NOT NULL,
    broker_account_id text NOT NULL,
    symbol text NOT NULL,
    asset_type text NOT NULL,
    quantity numeric(18,6) NOT NULL,
    average_price numeric(18,6),
    market_value numeric(18,6),
    broker_position_ref text,
    synced_at timestamptz NOT NULL DEFAULT now(),
    reconciliation_status text,
    native_position jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (broker, broker_account_id, symbol, asset_type, synced_at)
);
```

### 13.2 `assignment_events`

```sql
CREATE TABLE bullstrangle.assignment_events (
    assignment_event_id bigserial PRIMARY KEY,
    trade_intent_id bigint NOT NULL REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE CASCADE,
    fill_id bigint REFERENCES bullstrangle.fills(fill_id) ON DELETE SET NULL,
    event_type text NOT NULL CHECK (event_type IN ('early_call','early_assignment','expiration_assignment','called_away')),
    symbol text NOT NULL,
    option_right text CHECK (option_right IN ('call','put') OR option_right IS NULL),
    strike numeric(18,6),
    expiration_date date,
    quantity integer,
    shares_delta integer,
    event_price numeric(18,6),
    event_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL,
    native_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text
);
```

### 13.3 `trade_outcomes`

```sql
CREATE TABLE bullstrangle.trade_outcomes (
    trade_outcome_id bigserial PRIMARY KEY,
    trade_intent_id bigint NOT NULL UNIQUE REFERENCES bullstrangle.trade_intents(trade_intent_id) ON DELETE CASCADE,
    decision_id bigint REFERENCES bullstrangle.entry_decisions(decision_id) ON DELETE SET NULL,
    management_scenario text NOT NULL CHECK (
        management_scenario IN (
            'EARLY_CALL',
            'EARLY_ASSIGNMENT',
            'STOCK_CALLED_AWAY',
            'OPTIONS_EXPIRED_STOCK_KEPT',
            'STOCK_ASSIGNED'
        )
    ),
    outcome_status text NOT NULL CHECK (outcome_status IN ('modeled','realized','operator_overridden')) DEFAULT 'modeled',
    opened_at timestamptz,
    closed_at timestamptz,
    expiration_date date,
    entry_stock_price numeric(18,6),
    exit_stock_price numeric(18,6),
    total_credit numeric(18,6),
    realized_pnl numeric(18,6),
    modeled_pnl numeric(18,6),
    expected_pnl numeric(18,6),
    expected_prob_profit numeric(10,6),
    scenario_triggered_at timestamptz,
    scenario_trigger_price numeric(18,6),
    short_call_close_price numeric(18,6),
    short_put_close_price numeric(18,6),
    shares_sold integer,
    shares_assigned integer,
    restart_next_cycle boolean,
    operator_override boolean NOT NULL DEFAULT false,
    scenario_notes text,
    attribution jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz
);
```

## 14. Portfolio And Confidence

### 14.1 `paper_portfolios`

```sql
CREATE TABLE bullstrangle.paper_portfolios (
    paper_portfolio_id bigserial PRIMARY KEY,
    portfolio_type text NOT NULL CHECK (portfolio_type IN ('large','small')),
    portfolio_name text NOT NULL,
    status text NOT NULL CHECK (status IN ('active','paused','retired')) DEFAULT 'active',
    starting_cash numeric(18,6),
    target_cash numeric(18,6),
    max_concurrent_positions integer,
    assignment_capacity numeric(18,6),
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_type, portfolio_name)
);
```

### 14.2 `portfolio_snapshots`

```sql
CREATE TABLE bullstrangle.portfolio_snapshots (
    portfolio_snapshot_id bigserial PRIMARY KEY,
    paper_portfolio_id bigint REFERENCES bullstrangle.paper_portfolios(paper_portfolio_id) ON DELETE SET NULL,
    portfolio_type text NOT NULL CHECK (portfolio_type IN ('large','small')),
    snapshot_at timestamptz NOT NULL DEFAULT now(),
    cash_available numeric(18,6),
    buying_power numeric(18,6),
    capital_reserved numeric(18,6),
    assignment_capacity_used numeric(18,6),
    open_trade_count integer,
    sector_exposure jsonb NOT NULL DEFAULT '{}'::jsonb,
    symbol_exposure jsonb NOT NULL DEFAULT '{}'::jsonb,
    violations jsonb NOT NULL DEFAULT '[]'::jsonb,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

### 14.3 `trade_scorecards`

```sql
CREATE TABLE bullstrangle.trade_scorecards (
    trade_scorecard_id bigserial PRIMARY KEY,
    decision_id bigint NOT NULL UNIQUE REFERENCES bullstrangle.entry_decisions(decision_id) ON DELETE CASCADE,
    freshness_score numeric(10,6),
    liquidity_score numeric(10,6),
    pl_score numeric(10,6),
    probability_score numeric(10,6),
    newsletter_alignment_score numeric(10,6),
    rule_compliance_score numeric(10,6),
    portfolio_fit_score numeric(10,6),
    final_score numeric(10,6),
    confidence_level text CHECK (confidence_level IN ('HIGH','MEDIUM','LOW','REJECT') OR confidence_level IS NULL),
    score_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

### 14.4 `system_confidence_metrics`

```sql
CREATE TABLE bullstrangle.system_confidence_metrics (
    confidence_metric_id bigserial PRIMARY KEY,
    portfolio_type text CHECK (portfolio_type IN ('large','small') OR portfolio_type IS NULL),
    metric_period_start timestamptz,
    metric_period_end timestamptz,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    trade_count integer,
    closed_trade_count integer,
    win_rate numeric(10,6),
    average_return_pct numeric(10,6),
    max_drawdown_pct numeric(10,6),
    assignment_frequency numeric(10,6),
    called_away_rate numeric(10,6),
    expected_vs_realized_pnl numeric(18,6),
    accepted_vs_rejected jsonb NOT NULL DEFAULT '{}'::jsonb,
    replication_vs_live jsonb NOT NULL DEFAULT '{}'::jsonb,
    large_vs_small jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence_level text,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

### 14.5 `scenario_scoreboard_snapshots`

```sql
CREATE TABLE bullstrangle.scenario_scoreboard_snapshots (
    scenario_scoreboard_id bigserial PRIMARY KEY,
    portfolio_type text CHECK (portfolio_type IN ('large','small') OR portfolio_type IS NULL),
    snapshot_at timestamptz NOT NULL DEFAULT now(),
    period_start timestamptz,
    period_end timestamptz,
    early_call_count integer NOT NULL DEFAULT 0,
    early_assignment_count integer NOT NULL DEFAULT 0,
    stock_called_away_count integer NOT NULL DEFAULT 0,
    options_expired_stock_kept_count integer NOT NULL DEFAULT 0,
    stock_assigned_count integer NOT NULL DEFAULT 0,
    realized_pnl_total numeric(18,6),
    scenario_breakdown jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

## 15. Audit And Safety

### 15.1 `audit_events`

```sql
CREATE TABLE bullstrangle.audit_events (
    audit_event_id bigserial PRIMARY KEY,
    actor text,
    event_type text NOT NULL,
    entity_type text,
    entity_id text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    request_id uuid,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
```

Indexes:

```sql
CREATE INDEX idx_audit_events_entity
ON bullstrangle.audit_events(entity_type, entity_id);

CREATE INDEX idx_audit_events_time
ON bullstrangle.audit_events(occurred_at DESC);

CREATE INDEX idx_audit_events_evidence_gin
ON bullstrangle.audit_events USING gin (evidence);
```

### 15.2 Live Safety In Schema

Schema supports live readiness from day one:
- `operator_approvals` ties approval to exact `order_drafts.draft_version`.
- `broker_orders.client_order_id` is unique per broker/account.
- broker requests/responses are stored in `jsonb`.
- fills are independent from orders and support simulated, manual, and broker sources.
- `live_positions` stores broker-synced state separately from strategy intent.
- `assignment_events` and `trade_outcomes` model post-fill lifecycle and scenario attribution.

Live execution remains disabled by application configuration until confidence and safety gates are met.

## 16. Linkage And Replay

Primary replay chain:

```text
newsletters
  -> watchlist_entries
  -> live_watchlist_snapshots
  -> stock_quote_snapshots
  -> option_chain_snapshots
  -> option_chain_rows
  -> selected_trade_legs
  -> pl_evaluations
  -> probability_evaluations
  -> entry_decisions
  -> trade_intents
  -> order_drafts
  -> fills/fill_legs
  -> trade_lifecycle_events
  -> trade_outcomes
```

Policy replay chain:

```text
strategy_policy_versions
  -> pricing_policies
  -> strike_selection_policies
  -> pl_formula_versions
  -> probability_model_versions
  -> strategy_rules through rule_bundle jsonb
```

Provider failure chain:

```text
market_data_runs(status='failed' or 'partial')
  -> error jsonb
  -> live_watchlist_snapshots(status='data_unavailable')
  -> entry_decisions(decision_status='DATA_UNAVAILABLE')
```

## 17. Import/Migration Phases From Legacy SQLite

These are data import phases, not runtime dependencies.

Phase I0: Snapshot legacy source
- Copy legacy SQLite DB to read-only import location.
- Record file path/hash in `legacy_import_batches`.

Phase I1: Import artifacts
- Import newsletters, sections, watchlist entries, short-list entries, market environment context.
- Map legacy primary keys into `legacy_source_table` and `legacy_source_pk`.

Phase I2: Import benchmark OS data
- Import OS runs/rows only if needed for comparison.
- Store as benchmark tables or provider-like historical snapshots marked `provider_id='legacy_os'`.
- Do not use as primary runtime market data.

Phase I3: Import historical paper/backtest results
- Optional import of cycle-layer/backtest outcomes into native outcomes or separate historical comparison tables.
- Must be clearly marked as imported/modelled, not live provider-derived.

Phase I4: Cutover
- New runtime reads PostgreSQL only.
- Legacy system remains untouched and independently operational.

## 18. Local Dev And Test DB

Local dev:
- Use local PostgreSQL via Docker Compose or installed PostgreSQL.
- Database name example: `bullstrangle_dev`.
- Schema: `bullstrangle`.
- Run Alembic migrations from empty DB.
- Seed minimal policy rows and one fixture newsletter for local scanner tests.

Test DB:
- Use separate database: `bullstrangle_test`.
- Tests create/drop schema or use transaction rollback fixtures.
- No tests should require legacy SQLite unless explicitly marked import/integration.
- Provider tests should use recorded fixtures or provider mock payloads.
- Migration tests should run Alembic upgrade from base to head.

Recommended environment variables:

```text
BULLSTRANGLE_DATABASE_URL=postgresql+psycopg://...
BULLSTRANGLE_TEST_DATABASE_URL=postgresql+psycopg://...
BULLSTRANGLE_SCHEMA=bullstrangle
```

## 19. Index Summary

Critical indexes:
- newsletter date and watchlist symbol indexes.
- provider run provider/time and symbol/expiration indexes.
- option chain symbol/expiration/time indexes.
- option rows chain/right/strike indexes.
- live snapshot newsletter/symbol and mode/status indexes.
- entry decision newsletter/symbol and status/time indexes.
- trade intent mode/status indexes.
- lifecycle event intent/time indexes.
- GIN indexes on decision evidence, lifecycle event payloads, and audit evidence.

Partitioning is not needed for MVP. If option-chain volume grows, consider partitioning `option_chain_rows` by month of `retrieved_at` or by `expiration_date`.

## 20. Open Schema Decisions

- Whether to use PostgreSQL enum types for stable statuses or stay with check-constrained `text`.
- Whether to store exact monetary values in `numeric` only or also store integer cents for reconciliation.
- Whether imported OS benchmark rows should become `market_data_runs` with `provider_id='legacy_os'` or live in separate benchmark tables.
- Whether broker account metadata needs a dedicated `broker_accounts` table before shadow/live phases.
- Whether rejected candidates should be tracked through expiration without creating `trade_intents`.
- Whether `audit_events` should be append-only enforced by DB permissions/triggers.

## 21. Non-Goals

- No edits to legacy runtime code.
- No edits to `database.py`.
- No SQLite runtime design for the new project.
- No migrations are created by this document.
- No provider implementation.
- No live broker submission implementation.
