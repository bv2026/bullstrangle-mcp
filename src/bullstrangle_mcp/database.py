from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/bullstrangle.db")


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS newsletters (
    newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_date TEXT NOT NULL UNIQUE,
    pdf_path TEXT NOT NULL,
    pdf_sha256 TEXT NOT NULL,
    target_expiration TEXT,
    entry_date TEXT,
    option_type TEXT,
    days_to_expiration INTEGER,
    market_outlook TEXT,
    strategy_notes TEXT,
    market_commentary_structured TEXT,
    ingestion_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    ingestion_method TEXT NOT NULL DEFAULT 'pypdf'
);

CREATE INDEX IF NOT EXISTS idx_newsletters_pub_date
ON newsletters(publication_date);

CREATE TABLE IF NOT EXISTS newsletter_full_text (
    text_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT,
    section_name TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    content TEXT NOT NULL,
    UNIQUE(newsletter_id, section_name)
);

CREATE VIRTUAL TABLE IF NOT EXISTS newsletter_search USING fts5(
    section_name,
    content,
    content='newsletter_full_text',
    content_rowid='text_id'
);

CREATE TRIGGER IF NOT EXISTS newsletter_full_text_ai
AFTER INSERT ON newsletter_full_text BEGIN
    INSERT INTO newsletter_search(rowid, section_name, content)
    VALUES (new.text_id, new.section_name, new.content);
END;

CREATE TRIGGER IF NOT EXISTS newsletter_full_text_ad
AFTER DELETE ON newsletter_full_text BEGIN
    INSERT INTO newsletter_search(newsletter_search, rowid, section_name, content)
    VALUES('delete', old.text_id, old.section_name, old.content);
END;

CREATE TRIGGER IF NOT EXISTS newsletter_full_text_au
AFTER UPDATE ON newsletter_full_text BEGIN
    INSERT INTO newsletter_search(newsletter_search, rowid, section_name, content)
    VALUES('delete', old.text_id, old.section_name, old.content);
    INSERT INTO newsletter_search(rowid, section_name, content)
    VALUES (new.text_id, new.section_name, new.content);
END;

CREATE TABLE IF NOT EXISTS market_environment (
    env_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL UNIQUE REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    publication_date TEXT NOT NULL UNIQUE,
    sp500_price REAL,
    sp500_200dma REAL,
    sp500_vs_200dma REAL,
    sp500_above_200dma INTEGER,
    vix REAL,
    vix_below_25 INTEGER,
    breadth_pct REAL,
    breadth_above_40 INTEGER,
    trend_score INTEGER,
    volatility_score INTEGER,
    breadth_score INTEGER,
    hybrid_score INTEGER,
    hybrid_bullish INTEGER,
    market_status TEXT,
    market_regime TEXT,
    investment_percent INTEGER,
    cash_reserve_target REAL,
    all_criteria_met INTEGER,
    consecutive_weeks_met INTEGER DEFAULT 0,
    deployment_approved INTEGER DEFAULT 0,
    recommended_position_count INTEGER DEFAULT 0,
    scaling_phase TEXT,
    raw_row TEXT,
    commentary_raw_text TEXT,
    commentary_json TEXT,
    commentary_source_pages TEXT
);

CREATE INDEX IF NOT EXISTS idx_market_env_pub_date
ON market_environment(publication_date);

CREATE TABLE IF NOT EXISTS strategy_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_category TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    rule_description TEXT NOT NULL,
    rule_parameters TEXT,
    source_section TEXT,
    is_active INTEGER DEFAULT 1,
    created_date TEXT DEFAULT CURRENT_DATE,
    UNIQUE(rule_name, rule_category)
);

CREATE TABLE IF NOT EXISTS strategy_reference_sections (
    reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER REFERENCES newsletters(newsletter_id) ON DELETE SET NULL,
    source_newsletter_date TEXT,
    reference_scope TEXT DEFAULT 'common',
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_pdf_path TEXT,
    page_start INTEGER,
    page_end INTEGER,
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reference_scope, title)
);

CREATE TABLE IF NOT EXISTS weekly_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL UNIQUE REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    publication_date TEXT NOT NULL,
    all_criteria_met INTEGER NOT NULL,
    consecutive_weeks_met INTEGER NOT NULL,
    deployment_approved INTEGER NOT NULL,
    action_taken TEXT NOT NULL,
    positions_deployed INTEGER DEFAULT 0,
    symbols_deployed TEXT,
    decision_rationale TEXT,
    rule_violations TEXT,
    decision_timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT,
    expiration_date TEXT,
    symbol TEXT NOT NULL,
    description TEXT,
    sector TEXT,
    stock_price REAL,
    implied_volatility REAL,
    total_open_interest INTEGER,
    industry TEXT,
    sub_sector TEXT,
    weekly_options INTEGER,
    latest_earnings TEXT,
    sell_call_strike REAL,
    sell_call_premium REAL,
    sell_put_strike REAL,
    sell_put_premium REAL,
    buy_put_strike REAL,
    buy_put_premium REAL,
    bull_strangle_return_pct REAL,
    put_credit_spread_return_pct REAL,
    covered_call_return_pct REAL,
    is_favorite INTEGER DEFAULT 0,
    darren_notes TEXT,
    source_page INTEGER,
    raw_line TEXT,
    UNIQUE(newsletter_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_symbol
ON watchlist_entries(symbol);

CREATE TABLE IF NOT EXISTS short_list_entries (
    short_list_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT,
    portfolio_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    rank INTEGER,
    source_page INTEGER,
    raw_line TEXT,
    UNIQUE(newsletter_id, portfolio_type, symbol)
);

CREATE INDEX IF NOT EXISTS idx_short_list_symbol
ON short_list_entries(symbol);

CREATE TABLE IF NOT EXISTS watchlist_deep_analysis (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT,
    symbol TEXT NOT NULL,
    analysis_data TEXT NOT NULL,
    is_favorite INTEGER DEFAULT 1,
    favorite_rank INTEGER,
    has_earnings INTEGER DEFAULT 0,
    has_proposed_trade INTEGER DEFAULT 0,
    analysis_type TEXT DEFAULT 'wl_favorite',
    source_pages TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(newsletter_id, symbol)
);

CREATE TABLE IF NOT EXISTS symbol_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    publication_date TEXT NOT NULL,
    on_watchlist INTEGER DEFAULT 0,
    on_short_list INTEGER DEFAULT 0,
    on_dca_candidates INTEGER DEFAULT 0,
    dca_rank INTEGER,
    dca_score INTEGER,
    metadata TEXT,
    UNIQUE(symbol, newsletter_id)
);

CREATE TABLE IF NOT EXISTS os_workbooks (
    workbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    generated_path TEXT,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    template_version TEXT NOT NULL DEFAULT 'os_live_v1',
    selector_source TEXT NOT NULL,
    avg_sell_call_distance_pct REAL,
    avg_sell_put_distance_pct REAL,
    avg_buy_put_distance_pct REAL,
    call_selector_pct REAL,
    put_selector_pct REAL,
    buy_put_selector_pct REAL,
    selector_rounding_increment_pct REAL NOT NULL DEFAULT 0.5,
    strike_rounding_policy_json TEXT,
    buy_put_delta_min REAL,
    buy_put_delta_max REAL,
    sell_put_delta_min REAL,
    sell_put_delta_max REAL,
    sell_call_delta_min REAL,
    sell_call_delta_max REAL,
    formula_contract_json TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    workbook_hash TEXT,
    UNIQUE(newsletter_id, template_version, selector_source)
);

CREATE INDEX IF NOT EXISTS idx_os_workbooks_newsletter_date
ON os_workbooks(newsletter_date);

CREATE TABLE IF NOT EXISTS os_evaluation_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workbook_id INTEGER REFERENCES os_workbooks(workbook_id) ON DELETE SET NULL,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    trading_date TEXT,
    uploaded_path TEXT NOT NULL,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    market_data_as_of TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    populated_live_value_count INTEGER NOT NULL DEFAULT 0,
    formula_cell_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    raw_workbook_hash TEXT,
    validation_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_os_runs_newsletter_date
ON os_evaluation_runs(newsletter_date);

CREATE TABLE IF NOT EXISTS os_evaluation_rows (
    evaluation_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES os_evaluation_runs(run_id) ON DELETE CASCADE,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    live_stock_price REAL,
    live_stock_iv REAL,
    live_sector TEXT,
    live_industry TEXT,
    live_earnings_date TEXT,
    perf_1m REAL,
    perf_3m REAL,
    sma_50d REAL,
    sma_200d REAL,
    iv_rv_percentile REAL,
    atr_percent REAL,
    short_ratio REAL,
    sell_call_strike REAL,
    sell_call_bid REAL,
    sell_call_delta REAL,
    sell_put_strike REAL,
    sell_put_bid REAL,
    sell_put_delta REAL,
    buy_put_strike REAL,
    buy_put_ask REAL,
    buy_put_delta REAL,
    total_credit REAL,
    bull_strangle_return_pct REAL,
    call_distance_pct REAL,
    put_distance_pct REAL,
    buy_put_distance_pct REAL,
    call_prob_otm REAL,
    put_prob_otm REAL,
    prob_both_otm REAL,
    selector_source TEXT,
    call_selector_pct REAL,
    put_selector_pct REAL,
    buy_put_selector_pct REAL,
    raw_row_json TEXT,
    UNIQUE(run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_os_rows_symbol
ON os_evaluation_rows(symbol);

CREATE TABLE IF NOT EXISTS watchlist_deviations (
    deviation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES os_evaluation_runs(run_id) ON DELETE CASCADE,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    stock_price_deviation REAL,
    stock_price_deviation_pct REAL,
    iv_deviation REAL,
    sell_call_strike_deviation REAL,
    sell_put_strike_deviation REAL,
    buy_put_strike_deviation REAL,
    total_credit_deviation REAL,
    raw_deviation_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_deviations_newsletter_date
ON watchlist_deviations(newsletter_date);

CREATE TABLE IF NOT EXISTS os_weekly_symbol_aggregates (
    aggregate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    symbol TEXT NOT NULL,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    run_count INTEGER NOT NULL DEFAULT 0,
    first_run_id INTEGER,
    latest_run_id INTEGER,
    first_trading_date TEXT,
    latest_trading_date TEXT,
    first_live_stock_price REAL,
    latest_live_stock_price REAL,
    min_live_stock_price REAL,
    max_live_stock_price REAL,
    latest_live_stock_iv REAL,
    latest_sell_call_strike REAL,
    latest_sell_call_bid REAL,
    latest_sell_put_strike REAL,
    latest_sell_put_bid REAL,
    latest_buy_put_strike REAL,
    latest_buy_put_ask REAL,
    latest_total_credit REAL,
    min_total_credit REAL,
    max_total_credit REAL,
    worst_abs_stock_price_deviation_pct REAL,
    worst_abs_total_credit_deviation REAL,
    missing_core_value_days INTEGER NOT NULL DEFAULT 0,
    is_week_valid INTEGER NOT NULL DEFAULT 1,
    aggregate_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(newsletter_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_os_weekly_aggregates_newsletter_date
ON os_weekly_symbol_aggregates(newsletter_date);

CREATE TABLE IF NOT EXISTS decision_batches (
    decision_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    decision_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    source_run_start_date TEXT,
    source_run_end_date TEXT,
    market_environment_id INTEGER REFERENCES market_environment(env_id) ON DELETE SET NULL,
    position_run_id INTEGER REFERENCES position_import_runs(position_run_id) ON DELETE SET NULL,
    os_run_count INTEGER NOT NULL DEFAULT 0,
    strategy_logic_version TEXT,
    status TEXT NOT NULL DEFAULT 'generated',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    source_snapshot_json TEXT,
    UNIQUE(newsletter_id, decision_date)
);

CREATE INDEX IF NOT EXISTS idx_decision_batches_newsletter_date
ON decision_batches(newsletter_date);

CREATE TABLE IF NOT EXISTS bull_strangle_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_batch_id INTEGER NOT NULL REFERENCES decision_batches(decision_batch_id) ON DELETE CASCADE,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    expiration_date TEXT,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    final_decision TEXT NOT NULL,
    priority_rank INTEGER,
    selected_action TEXT,
    strategy_score REAL,
    strategy_band TEXT,
    market_approved INTEGER NOT NULL DEFAULT 0,
    os_week_valid INTEGER NOT NULL DEFAULT 0,
    latest_total_credit REAL,
    latest_live_stock_price REAL,
    max_price_deviation_pct REAL,
    max_credit_deviation REAL,
    rules_applied_json TEXT,
    rules_passed_json TEXT,
    rules_failed_json TEXT,
    criteria_json TEXT,
    source_snapshot_json TEXT,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(decision_batch_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_bull_strangle_decisions_newsletter_date
ON bull_strangle_decisions(newsletter_date);

CREATE TABLE IF NOT EXISTS dca_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_batch_id INTEGER NOT NULL REFERENCES decision_batches(decision_batch_id) ON DELETE CASCADE,
    newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
    newsletter_date TEXT NOT NULL,
    watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    final_decision TEXT NOT NULL,
    priority_rank INTEGER,
    selected_action TEXT,
    strategy_score REAL,
    strategy_band TEXT,
    market_allocation_ok INTEGER NOT NULL DEFAULT 0,
    dca_candidate_score REAL,
    latest_live_price REAL,
    weekly_price_trend REAL,
    max_price_deviation_pct REAL,
    rules_applied_json TEXT,
    rules_passed_json TEXT,
    rules_failed_json TEXT,
    criteria_json TEXT,
    source_snapshot_json TEXT,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(decision_batch_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_dca_decisions_newsletter_date
ON dca_decisions(newsletter_date);

CREATE TABLE IF NOT EXISTS position_import_runs (
    position_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER NOT NULL DEFAULT 0,
    account_count INTEGER NOT NULL DEFAULT 0,
    symbol_count INTEGER NOT NULL DEFAULT 0,
    total_market_value REAL,
    total_cost_basis REAL,
    status TEXT NOT NULL DEFAULT 'imported',
    validation_json TEXT
);

CREATE TABLE IF NOT EXISTS account_positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_run_id INTEGER NOT NULL REFERENCES position_import_runs(position_run_id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    current_price REAL,
    average_price REAL,
    market_value REAL,
    cost_basis REAL,
    unrealized_gain_loss REAL,
    unrealized_gain_loss_pct REAL,
    raw_row_json TEXT,
    UNIQUE(position_run_id, account_name, symbol)
);

CREATE INDEX IF NOT EXISTS idx_account_positions_symbol
ON account_positions(symbol);

CREATE TABLE IF NOT EXISTS symbol_position_rollups (
    rollup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_run_id INTEGER NOT NULL REFERENCES position_import_runs(position_run_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    total_quantity REAL NOT NULL DEFAULT 0,
    total_market_value REAL,
    total_cost_basis REAL,
    weighted_average_price REAL,
    account_count INTEGER NOT NULL DEFAULT 0,
    max_account_quantity REAL NOT NULL DEFAULT 0,
    bull_strangle_ready INTEGER NOT NULL DEFAULT 0,
    eligible_account TEXT,
    dca_target_account TEXT,
    shares_to_100 REAL,
    accounts_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(position_run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_symbol_position_rollups_symbol
ON symbol_position_rollups(symbol);
"""


SEED_RULES_SQL = """
INSERT OR IGNORE INTO strategy_rules
(rule_category, rule_name, rule_description, rule_parameters, source_section)
VALUES
('entry', 'Quality stock filter',
 'Pick technically strong stocks from tested stock search engines with sufficient IV, price range, open interest, and no earnings during the holding period.',
 '{"implied_volatility_min":0.35,"last_price_min":10,"last_price_max":120,"open_interest_min":25000,"avoid_earnings_during_holding_period":true}',
 'Strategy Overview Core Elements'),
('entry', 'Bull strangle construction',
 'Buy stock in 100-share increments, sell out-of-the-money calls four weeks out, and sell out-of-the-money puts four weeks out.',
 '{"share_increment":100,"call_moneyness":"OTM","put_moneyness":"OTM","target_days_to_expiration":28}',
 'Strategy Overview Core Elements'),
('risk', 'Market environment investment percent',
 'Use market environment status to size exposure: green 75%, yellow 50%, red 0-25%.',
 '{"green_investment_percent":75,"yellow_investment_percent":50,"red_investment_percent_range":[0,25]}',
 'Strategy Overview Core Elements'),
('exit', 'Stock called away',
 'If stock is called away prior to expiration, look to close naked puts for a small debit; otherwise wait for put expiration.',
 '{"close_naked_put_debit_min":0.05,"close_naked_put_debit_max":0.10}',
 'Trade Management Suggestions'),
('exit', 'Stock assigned',
 'If stock is assigned prior to expiration, sell all shares and look to close naked calls for a small debit; otherwise wait for call expiration.',
 '{"close_naked_call_debit_min":0.05,"close_naked_call_debit_max":0.10}',
 'Trade Management Suggestions'),
('exit', 'Both options expire',
 'When both options expire and stock is kept, usually continue holding and sell calls and puts for the next cycle unless better watchlist candidates exist.',
 '{"roll_to_next_cycle":true,"reevaluate_against_watchlist":true}',
 'Trade Management Suggestions');
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        ensure_schema_migrations(conn)
        conn.executescript(SEED_RULES_SQL)


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    """Apply lightweight migrations for local SQLite databases."""
    ensure_column(conn, "newsletter_full_text", "newsletter_date", "TEXT")
    ensure_column(conn, "market_environment", "commentary_raw_text", "TEXT")
    ensure_column(conn, "market_environment", "commentary_json", "TEXT")
    ensure_column(conn, "market_environment", "commentary_source_pages", "TEXT")
    ensure_column(conn, "watchlist_entries", "newsletter_date", "TEXT")
    ensure_column(conn, "watchlist_entries", "expiration_date", "TEXT")
    ensure_column(conn, "watchlist_entries", "total_open_interest", "INTEGER")
    ensure_column(conn, "watchlist_entries", "industry", "TEXT")
    ensure_column(conn, "watchlist_entries", "sub_sector", "TEXT")
    ensure_column(conn, "watchlist_entries", "weekly_options", "INTEGER")
    ensure_column(conn, "watchlist_entries", "latest_earnings", "TEXT")
    ensure_column(conn, "short_list_entries", "newsletter_date", "TEXT")
    ensure_column(conn, "watchlist_deep_analysis", "newsletter_date", "TEXT")
    ensure_os_workbooks_schema(conn)
    ensure_os_ingestion_schema(conn)
    ensure_os_weekly_aggregation_schema(conn)
    ensure_decision_schema(conn)
    ensure_position_schema(conn)

    backfill_newsletter_date(conn, "newsletter_full_text")
    backfill_newsletter_date(conn, "watchlist_entries")
    backfill_newsletter_date(conn, "short_list_entries")
    backfill_newsletter_date(conn, "watchlist_deep_analysis")
    conn.execute(
        """
        UPDATE watchlist_entries
        SET expiration_date = (
            SELECT target_expiration FROM newsletters
            WHERE newsletters.newsletter_id = watchlist_entries.newsletter_id
        )
        WHERE expiration_date IS NULL
        """
    )
    ensure_date_indexes(conn)


def ensure_os_workbooks_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_workbooks (
            workbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            generated_path TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            template_version TEXT NOT NULL DEFAULT 'os_live_v1',
            selector_source TEXT NOT NULL,
            avg_sell_call_distance_pct REAL,
            avg_sell_put_distance_pct REAL,
            avg_buy_put_distance_pct REAL,
            call_selector_pct REAL,
            put_selector_pct REAL,
            buy_put_selector_pct REAL,
            selector_rounding_increment_pct REAL NOT NULL DEFAULT 0.5,
            strike_rounding_policy_json TEXT,
            buy_put_delta_min REAL,
            buy_put_delta_max REAL,
            sell_put_delta_min REAL,
            sell_put_delta_max REAL,
            sell_call_delta_min REAL,
            sell_call_delta_max REAL,
            formula_contract_json TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            workbook_hash TEXT,
            UNIQUE(newsletter_id, template_version, selector_source)
        )
        """
    )
    for column_name, column_type in {
        "newsletter_date": "TEXT",
        "expiration_date": "TEXT",
        "generated_path": "TEXT",
        "generated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        "template_version": "TEXT NOT NULL DEFAULT 'os_live_v1'",
        "selector_source": "TEXT NOT NULL DEFAULT 'newsletter_average'",
        "avg_sell_call_distance_pct": "REAL",
        "avg_sell_put_distance_pct": "REAL",
        "avg_buy_put_distance_pct": "REAL",
        "call_selector_pct": "REAL",
        "put_selector_pct": "REAL",
        "buy_put_selector_pct": "REAL",
        "selector_rounding_increment_pct": "REAL NOT NULL DEFAULT 0.5",
        "strike_rounding_policy_json": "TEXT",
        "buy_put_delta_min": "REAL",
        "buy_put_delta_max": "REAL",
        "sell_put_delta_min": "REAL",
        "sell_put_delta_max": "REAL",
        "sell_call_delta_min": "REAL",
        "sell_call_delta_max": "REAL",
        "formula_contract_json": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'planned'",
        "workbook_hash": "TEXT",
    }.items():
        ensure_column(conn, "os_workbooks", column_name, column_type)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_os_workbooks_newsletter_date ON os_workbooks(newsletter_date)"
    )


def ensure_os_ingestion_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_evaluation_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workbook_id INTEGER REFERENCES os_workbooks(workbook_id) ON DELETE SET NULL,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            trading_date TEXT,
            uploaded_path TEXT NOT NULL,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            market_data_as_of TEXT,
            row_count INTEGER NOT NULL DEFAULT 0,
            populated_live_value_count INTEGER NOT NULL DEFAULT 0,
            formula_cell_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            raw_workbook_hash TEXT,
            validation_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_evaluation_rows (
            evaluation_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES os_evaluation_runs(run_id) ON DELETE CASCADE,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
            symbol TEXT NOT NULL,
            live_stock_price REAL,
            live_stock_iv REAL,
            live_sector TEXT,
            live_industry TEXT,
            live_earnings_date TEXT,
            perf_1m REAL,
            perf_3m REAL,
            sma_50d REAL,
            sma_200d REAL,
            iv_rv_percentile REAL,
            atr_percent REAL,
            short_ratio REAL,
            sell_call_strike REAL,
            sell_call_bid REAL,
            sell_call_delta REAL,
            sell_put_strike REAL,
            sell_put_bid REAL,
            sell_put_delta REAL,
            buy_put_strike REAL,
            buy_put_ask REAL,
            buy_put_delta REAL,
            total_credit REAL,
            bull_strangle_return_pct REAL,
            call_distance_pct REAL,
            put_distance_pct REAL,
            buy_put_distance_pct REAL,
            call_prob_otm REAL,
            put_prob_otm REAL,
            prob_both_otm REAL,
            selector_source TEXT,
            call_selector_pct REAL,
            put_selector_pct REAL,
            buy_put_selector_pct REAL,
            raw_row_json TEXT,
            UNIQUE(run_id, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_deviations (
            deviation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES os_evaluation_runs(run_id) ON DELETE CASCADE,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
            symbol TEXT NOT NULL,
            stock_price_deviation REAL,
            stock_price_deviation_pct REAL,
            iv_deviation REAL,
            sell_call_strike_deviation REAL,
            sell_put_strike_deviation REAL,
            buy_put_strike_deviation REAL,
            total_credit_deviation REAL,
            raw_deviation_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, symbol)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_os_runs_newsletter_date ON os_evaluation_runs(newsletter_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_os_rows_symbol ON os_evaluation_rows(symbol)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_deviations_newsletter_date ON watchlist_deviations(newsletter_date)"
    )


def ensure_os_weekly_aggregation_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_weekly_symbol_aggregates (
            aggregate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            symbol TEXT NOT NULL,
            watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
            run_count INTEGER NOT NULL DEFAULT 0,
            first_run_id INTEGER,
            latest_run_id INTEGER,
            first_trading_date TEXT,
            latest_trading_date TEXT,
            first_live_stock_price REAL,
            latest_live_stock_price REAL,
            min_live_stock_price REAL,
            max_live_stock_price REAL,
            latest_live_stock_iv REAL,
            latest_sell_call_strike REAL,
            latest_sell_call_bid REAL,
            latest_sell_put_strike REAL,
            latest_sell_put_bid REAL,
            latest_buy_put_strike REAL,
            latest_buy_put_ask REAL,
            latest_total_credit REAL,
            min_total_credit REAL,
            max_total_credit REAL,
            worst_abs_stock_price_deviation_pct REAL,
            worst_abs_total_credit_deviation REAL,
            missing_core_value_days INTEGER NOT NULL DEFAULT 0,
            is_week_valid INTEGER NOT NULL DEFAULT 1,
            aggregate_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(newsletter_id, symbol)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_os_weekly_aggregates_newsletter_date ON os_weekly_symbol_aggregates(newsletter_date)"
    )


def ensure_decision_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_batches (
            decision_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            decision_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            source_run_start_date TEXT,
            source_run_end_date TEXT,
            market_environment_id INTEGER REFERENCES market_environment(env_id) ON DELETE SET NULL,
            position_run_id INTEGER REFERENCES position_import_runs(position_run_id) ON DELETE SET NULL,
            os_run_count INTEGER NOT NULL DEFAULT 0,
            strategy_logic_version TEXT,
            status TEXT NOT NULL DEFAULT 'generated',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source_snapshot_json TEXT,
            UNIQUE(newsletter_id, decision_date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bull_strangle_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_batch_id INTEGER NOT NULL REFERENCES decision_batches(decision_batch_id) ON DELETE CASCADE,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            expiration_date TEXT,
            watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
            symbol TEXT NOT NULL,
            final_decision TEXT NOT NULL,
            priority_rank INTEGER,
            selected_action TEXT,
            strategy_score REAL,
            strategy_band TEXT,
            market_approved INTEGER NOT NULL DEFAULT 0,
            os_week_valid INTEGER NOT NULL DEFAULT 0,
            latest_total_credit REAL,
            latest_live_stock_price REAL,
            max_price_deviation_pct REAL,
            max_credit_deviation REAL,
            rules_applied_json TEXT,
            rules_passed_json TEXT,
            rules_failed_json TEXT,
            criteria_json TEXT,
            source_snapshot_json TEXT,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(decision_batch_id, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dca_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_batch_id INTEGER NOT NULL REFERENCES decision_batches(decision_batch_id) ON DELETE CASCADE,
            newsletter_id INTEGER NOT NULL REFERENCES newsletters(newsletter_id) ON DELETE CASCADE,
            newsletter_date TEXT NOT NULL,
            watchlist_entry_id INTEGER REFERENCES watchlist_entries(entry_id) ON DELETE SET NULL,
            symbol TEXT NOT NULL,
            final_decision TEXT NOT NULL,
            priority_rank INTEGER,
            selected_action TEXT,
            strategy_score REAL,
            strategy_band TEXT,
            market_allocation_ok INTEGER NOT NULL DEFAULT 0,
            dca_candidate_score REAL,
            latest_live_price REAL,
            weekly_price_trend REAL,
            max_price_deviation_pct REAL,
            rules_applied_json TEXT,
            rules_passed_json TEXT,
            rules_failed_json TEXT,
            criteria_json TEXT,
            source_snapshot_json TEXT,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(decision_batch_id, symbol)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_batches_newsletter_date ON decision_batches(newsletter_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bull_strangle_decisions_newsletter_date ON bull_strangle_decisions(newsletter_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dca_decisions_newsletter_date ON dca_decisions(newsletter_date)"
    )
    ensure_column(conn, "decision_batches", "position_run_id", "INTEGER")
    ensure_column(conn, "decision_batches", "strategy_logic_version", "TEXT")
    for table_name in ["bull_strangle_decisions", "dca_decisions"]:
        ensure_column(conn, table_name, "selected_action", "TEXT")
        ensure_column(conn, table_name, "strategy_score", "REAL")
        ensure_column(conn, table_name, "strategy_band", "TEXT")
        ensure_column(conn, table_name, "selected_account", "TEXT")
        ensure_column(conn, table_name, "account_shares", "REAL")
        ensure_column(conn, table_name, "consolidated_shares", "REAL")
        ensure_column(conn, table_name, "shares_to_100", "REAL")
        ensure_column(conn, table_name, "rules_passed_json", "TEXT")
        ensure_column(conn, table_name, "rules_failed_json", "TEXT")


def ensure_position_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS position_import_runs (
            position_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER NOT NULL DEFAULT 0,
            account_count INTEGER NOT NULL DEFAULT 0,
            symbol_count INTEGER NOT NULL DEFAULT 0,
            total_market_value REAL,
            total_cost_basis REAL,
            status TEXT NOT NULL DEFAULT 'imported',
            validation_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS account_positions (
            position_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_run_id INTEGER NOT NULL REFERENCES position_import_runs(position_run_id) ON DELETE CASCADE,
            account_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            current_price REAL,
            average_price REAL,
            market_value REAL,
            cost_basis REAL,
            unrealized_gain_loss REAL,
            unrealized_gain_loss_pct REAL,
            raw_row_json TEXT,
            UNIQUE(position_run_id, account_name, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_position_rollups (
            rollup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_run_id INTEGER NOT NULL REFERENCES position_import_runs(position_run_id) ON DELETE CASCADE,
            symbol TEXT NOT NULL,
            total_quantity REAL NOT NULL DEFAULT 0,
            total_market_value REAL,
            total_cost_basis REAL,
            weighted_average_price REAL,
            account_count INTEGER NOT NULL DEFAULT 0,
            max_account_quantity REAL NOT NULL DEFAULT 0,
            bull_strangle_ready INTEGER NOT NULL DEFAULT 0,
            eligible_account TEXT,
            dca_target_account TEXT,
            shares_to_100 REAL,
            accounts_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(position_run_id, symbol)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_account_positions_symbol ON account_positions(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_position_rollups_symbol ON symbol_position_rollups(symbol)")


def ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def backfill_newsletter_date(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute(
        f"""
        UPDATE {table_name}
        SET newsletter_date = (
            SELECT publication_date FROM newsletters
            WHERE newsletters.newsletter_id = {table_name}.newsletter_id
        )
        WHERE newsletter_date IS NULL
        """
    )


def ensure_date_indexes(conn: sqlite3.Connection) -> None:
    date_indexes = {
        "idx_full_text_newsletter_date": ("newsletter_full_text", "newsletter_date"),
        "idx_watchlist_newsletter_date": ("watchlist_entries", "newsletter_date"),
        "idx_watchlist_expiration_date": ("watchlist_entries", "expiration_date"),
        "idx_short_list_newsletter_date": ("short_list_entries", "newsletter_date"),
        "idx_deep_analysis_newsletter_date": ("watchlist_deep_analysis", "newsletter_date"),
    }
    for index_name, (table_name, column_name) in date_indexes.items():
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"
        )
