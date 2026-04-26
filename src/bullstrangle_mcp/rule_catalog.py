"""rule_catalog.py — Strategy rule catalog for the v3 gate-based engine.

Responsibilities:
- Seed ``strategy_rule_catalog`` from the embedded 43-rule inventory (derived
  from the Master Document rule inventory in
  ``references/master_document_rule_inventory.md``).
- Query rules by area, type, or id.
- Provide the ``RuleDefinition`` dataclass used by entry_engine and exit_engine.

**Design constraint:** No gate in ``entry_engine.py`` or ``exit_engine.py`` may
hard-code a numeric threshold.  All thresholds come from ``get_rule(rule_id)``
reading ``parameters_json`` from this catalog.  That way an operator can adjust
thresholds in the DB and re-run decisions without changing code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .database import connect, initialize_database

# ---------------------------------------------------------------------------
# Canonical seed data — all 43 rules from the Master Document rule inventory.
# Stored here so the catalog is always self-contained and testable without the
# reference .md file.  The rule_id is the primary key; a second load is a no-op
# (INSERT OR IGNORE).
# ---------------------------------------------------------------------------

_SEED_RULES: list[dict[str, Any]] = [
    # ── Stock Selection Gates ─────────────────────────────────────────────
    {
        "rule_id": "GATE-SS-001",
        "rule_area": "stock_selection",
        "rule_type": "hard_gate",
        "source_section": "Chapter 3 §3.3, Chapter 5 §4.4, Appendix F Step 1",
        "description": (
            "Exclude any stock with implied volatility (IV) at or above 1.0. "
            "High IV signals instability; backtesting showed nearly all severe "
            "losses came from IV > 1.0 names."
        ),
        "parameters_json": json.dumps({"max_iv": 1.0, "comparator": "<"}),
        "data_column_mapping": "os_evaluation_rows.iv or watchlist_entries.iv",
    },
    {
        "rule_id": "GATE-SS-002",
        "rule_area": "stock_selection",
        "rule_type": "hard_gate",
        "source_section": "Chapter 2 §3.3, Chapter 5 §4.1, Appendix C §2",
        "description": (
            "Stock must trade above at least 2 of the 4 key moving averages "
            "(20, 50, 100, 200-day). A stock below 3 or all 4 MAs is classified "
            "'broken' and excluded regardless of premium."
        ),
        "parameters_json": json.dumps(
            {"ma_periods": [20, 50, 100, 200], "min_mas_above": 2, "broken_threshold": 2}
        ),
        "data_column_mapping": (
            "os_evaluation_rows.above_20ma, .above_50ma, .above_100ma, .above_200ma "
            "(count of trues must be >= 2)"
        ),
    },
    {
        "rule_id": "GATE-SS-003",
        "rule_area": "stock_selection",
        "rule_type": "hard_gate",
        "source_section": "Chapter 5 §4.2, Appendix F Step 1",
        "description": (
            "The option chain must show active bid prices on both the call and put "
            "at the intended strikes. Zero-bid strikes are an automatic rejection — "
            "no exceptions regardless of how attractive the premium appears."
        ),
        "parameters_json": json.dumps(
            {"min_bid": 0.01, "required_sides": ["call", "put"]}
        ),
        "data_column_mapping": (
            "os_evaluation_rows.call_bid, os_evaluation_rows.put_bid (both must be > 0)"
        ),
    },
    {
        "rule_id": "GATE-SS-004",
        "rule_area": "stock_selection",
        "rule_type": "soft_gate",
        "source_section": "Chapter 5 §4.2",
        "description": (
            "Combined call + put premium must yield at least 2% of the stock price. "
            "Chains below 2% are excluded."
        ),
        "parameters_json": json.dumps({"min_premium_yield_pct": 2.0, "comparator": ">="}),
        "data_column_mapping": (
            "os_evaluation_rows.total_credit / os_evaluation_rows.stock_price * 100"
        ),
    },
    {
        "rule_id": "GATE-SS-005",
        "rule_area": "earnings",
        "rule_type": "hard_gate",
        "source_section": "Chapter 13 §2, Appendix F Step 1",
        "description": (
            "No stock may be selected for a cycle if its next earnings announcement "
            "falls within 45 days of the trade entry date. Treat every published "
            "earnings date as real regardless of confirmed vs. estimated status."
        ),
        "parameters_json": json.dumps(
            {"min_earnings_clear_days": 45, "comparator": ">"}
        ),
        "data_column_mapping": (
            "earnings_calendar.earnings_date — must be > entry_date + 45 days"
        ),
    },
    {
        "rule_id": "GATE-SS-006",
        "rule_area": "stock_selection",
        "rule_type": "hard_gate",
        "source_section": "Chapter 2 §3.3, Chapter 5 §2.2",
        "description": (
            "A stock trading below 3 or all 4 major moving averages is classified "
            "as 'broken.' Broken stocks are excluded completely — support has failed "
            "at all timeframes."
        ),
        "parameters_json": json.dumps(
            {"ma_periods": [20, 50, 100, 200], "max_mas_below": 2}
        ),
        "data_column_mapping": (
            "Count of os_evaluation_rows.above_NNma = false must be <= 2"
        ),
    },
    {
        "rule_id": "GATE-SS-007",
        "rule_area": "stock_selection",
        "rule_type": "soft_gate",
        "source_section": "Chapter 2 §3.2, Chapter 5 §2.1, §5",
        "description": (
            "Stocks stretched far above all moving averages and showing parabolic, "
            "gap-prone, or social-media-driven momentum are excluded. Practical test: "
            "if a 10% move in 2 weeks would feel normal for this stock, it is a "
            "high-flyer. Higher premium does not compensate for tail risk."
        ),
        "parameters_json": json.dumps(
            {"qualitative": True, "heuristic": "10pct_move_feels_normal"}
        ),
        "data_column_mapping": "watchlist_entries.is_high_flyer flag (manual or screened)",
    },
    {
        "rule_id": "GATE-SS-008",
        "rule_area": "stock_selection",
        "rule_type": "hard_gate",
        "source_section": "Chapter 8 §1, Appendix B glossary 'Watch List'",
        "description": (
            "Only stocks on the current weekly watch list may be used to initiate a "
            "cycle. Candidates outside the list are not eligible regardless of how "
            "attractive they appear on Monday morning."
        ),
        "parameters_json": json.dumps(
            {"source": "watchlist_entries", "newsletter_date": "current"}
        ),
        "data_column_mapping": (
            "watchlist_entries — symbol must exist for the current newsletter_id"
        ),
    },
    # ── Strike Selection ───────────────────────────────────────────────────
    {
        "rule_id": "RULE-STRIKE-001",
        "rule_area": "strike_selection",
        "rule_type": "hard_rule",
        "source_section": "Chapter 3 §6.3, Appendix E D.1",
        "description": (
            "Call strike = stock_price × 1.015, then round UP to the nearest "
            "available listed strike. This ensures the call is always at least "
            "1.5% above the stock."
        ),
        "parameters_json": json.dumps(
            {"offset_pct": 0.015, "direction": "above", "rounding": "up"}
        ),
        "data_column_mapping": (
            "watchlist_entries.sell_call_strike, os_evaluation_rows.stock_price"
        ),
    },
    {
        "rule_id": "RULE-STRIKE-002",
        "rule_area": "strike_selection",
        "rule_type": "hard_rule",
        "source_section": "Chapter 3 §6.3, Appendix E D.1",
        "description": (
            "Put strike = stock_price × 0.985, then round DOWN to the nearest "
            "available listed strike. This ensures the put is always at least "
            "1.5% below the stock."
        ),
        "parameters_json": json.dumps(
            {"offset_pct": -0.015, "direction": "below", "rounding": "down"}
        ),
        "data_column_mapping": (
            "watchlist_entries.sell_put_strike, os_evaluation_rows.stock_price"
        ),
    },
    {
        "rule_id": "RULE-STRIKE-003",
        "rule_area": "strike_selection",
        "rule_type": "guideline",
        "source_section": "Chapter 3 §6.3, §6.5",
        "description": (
            "Resulting strike distances should land in the 2.0%–3.5% band from the "
            "stock price. This is a confirmation check, not a selection driver."
        ),
        "parameters_json": json.dumps(
            {"min_distance_pct": 2.0, "max_distance_pct": 3.5}
        ),
        "data_column_mapping": (
            "Derived from os_evaluation_rows.call_strike, .put_strike, .stock_price"
        ),
    },
    {
        "rule_id": "RULE-STRIKE-004",
        "rule_area": "strike_selection",
        "rule_type": "hard_rule",
        "source_section": "Chapter 8 §5",
        "description": (
            "If the stock price has moved from Friday's close by the time Monday "
            "opens, slide BOTH strikes by approximately the same dollar amount. "
            "This preserves the original call-put dollar gap."
        ),
        "parameters_json": json.dumps(
            {
                "adjustment": "slide_both_strikes_by_price_change",
                "preserve": "call_put_gap_dollars",
            }
        ),
        "data_column_mapping": (
            "watchlist_entries.price (Friday close) vs. live Monday price"
        ),
    },
    # ── Capital & Position Sizing ──────────────────────────────────────────
    {
        "rule_id": "RULE-CAPITAL-001",
        "rule_area": "capital",
        "rule_type": "hard_rule",
        "source_section": "Chapter 9 §4, Chapter 11, Appendix A 'Capital & Risk Architecture'",
        "description": (
            "Always maintain approximately 25% of total account value in unused cash. "
            "The buffer eliminates margin stress, keeps Monday rotation funded, and "
            "reduces emotional pressure during drawdowns."
        ),
        "parameters_json": json.dumps({"min_cash_buffer": 0.25, "comparator": ">="}),
        "data_column_mapping": (
            "account_positions cash balance / total account value"
        ),
    },
    {
        "rule_id": "RULE-CAPITAL-002",
        "rule_area": "capital",
        "rule_type": "hard_rule",
        "source_section": "Chapter 6 §3.1, Appendix A 'Capital & Risk Architecture'",
        "description": (
            "Only 75% of total account value is eligible for deployment across all "
            "four active cycles at any time."
        ),
        "parameters_json": json.dumps({"max_deployed_pct": 0.75}),
        "data_column_mapping": "Total invested capital / total account value",
    },
    {
        "rule_id": "RULE-CAPITAL-003",
        "rule_area": "capital",
        "rule_type": "hard_rule",
        "source_section": "Chapter 6 §3.1",
        "description": (
            "Weekly target = (total_account_value × 0.75) / 4. Each new Monday cycle "
            "is funded to this target across ALL positions entered in that week's lane."
        ),
        "parameters_json": json.dumps(
            {"formula": "account_value * 0.75 / 4", "num_cycles": 4}
        ),
        "data_column_mapping": (
            "symbol_position_rollups.total_value or account_positions sum"
        ),
    },
    {
        "rule_id": "RULE-CAPITAL-004",
        "rule_area": "capital",
        "rule_type": "hard_rule",
        "source_section": "Chapter 4 §1, Chapter 6 §3.2",
        "description": (
            "Share counts must always be multiples of 100 because each option contract "
            "controls 100 shares."
        ),
        "parameters_json": json.dumps({"share_increment": 100}),
        "data_column_mapping": "account_positions.quantity must be divisible by 100",
    },
    {
        "rule_id": "RULE-CAPITAL-005",
        "rule_area": "capital",
        "rule_type": "guideline",
        "source_section": "Chapter 11 §3, §4",
        "description": (
            "Position size as a percentage of total capital varies by account size. "
            "$40k–$55k: ~6.3% per position, 3 trades/week. "
            "$55k–$90k: ~4.7% per position, 4 trades/week. "
            "$90k+: ~3.8% per position, 5 trades/week."
        ),
        "parameters_json": json.dumps(
            {
                "tiers": [
                    {"min_account": 40000, "max_account": 55000, "pct_per_position": 6.3, "trades_per_week": 3},
                    {"min_account": 55000, "max_account": 90000, "pct_per_position": 4.7, "trades_per_week": 4},
                    {"min_account": 90000, "max_account": None, "pct_per_position": 3.8, "trades_per_week": 5},
                ]
            }
        ),
        "data_column_mapping": "Total account value from account_positions",
    },
    {
        "rule_id": "RULE-CAPITAL-006",
        "rule_area": "capital",
        "rule_type": "guideline",
        "source_section": "Chapter 11 §7.2",
        "description": (
            "Number of positions per weekly cycle guided by account size. "
            "$10k–$20k=1 trade; $20k–$35k=2; $35k–$50k=3; $50k–$90k=4; $90k+=5."
        ),
        "parameters_json": json.dumps(
            {
                "tiers": [
                    {"min": 10000, "max": 20000, "trades": 1},
                    {"min": 20000, "max": 35000, "trades": 2},
                    {"min": 35000, "max": 50000, "trades": 3},
                    {"min": 50000, "max": 90000, "trades": 4},
                    {"min": 90000, "max": None, "trades": 5},
                ]
            }
        ),
        "data_column_mapping": "Total account value",
    },
    {
        "rule_id": "RULE-CAPITAL-007",
        "rule_area": "capital",
        "rule_type": "hard_rule",
        "source_section": "Appendix A 'Stock, Volatility & Portfolio Filters'",
        "description": (
            "Small accounts: no more than 1 stock per sector at any time. "
            "Large accounts: no more than 3 stocks per sector at any time."
        ),
        "parameters_json": json.dumps(
            {"small_account_max_per_sector": 1, "large_account_max_per_sector": 3}
        ),
        "data_column_mapping": (
            "account_positions.sector grouped count across open cycles"
        ),
    },
    {
        "rule_id": "RULE-CAPITAL-008",
        "rule_area": "formula",
        "rule_type": "formula",
        "source_section": "Chapter 10 §1.1, Appendix E D.2",
        "description": (
            "Invested Capital = (Shares Purchased × Stock Price) − Option Premium "
            "Collected. This is the net capital at risk. Premium received upfront "
            "reduces the cash required."
        ),
        "parameters_json": json.dumps(
            {"formula": "(shares * stock_price) - total_premium_collected"}
        ),
        "data_column_mapping": (
            "cycle_layers.shares, cycle_layers.stock_price_at_entry, "
            "cycle_layers.total_credit_collected"
        ),
    },
    # ── Cycle & Timing Rules ───────────────────────────────────────────────
    {
        "rule_id": "RULE-CYCLE-001",
        "rule_area": "cycle",
        "rule_type": "hard_rule",
        "source_section": "Chapter 1 §4, Chapter 6 §6, Appendix B 'Monday-Only Decision Rule'",
        "description": (
            "All new positions are entered on Monday only. No new trades are "
            "initiated mid-week."
        ),
        "parameters_json": json.dumps({"entry_day": "Monday"}),
        "data_column_mapping": "cycle_layers.open_date must be a Monday",
    },
    {
        "rule_id": "RULE-CYCLE-002",
        "rule_area": "cycle",
        "rule_type": "hard_rule",
        "source_section": "Chapter 3 §1.4, Chapter 6 §1",
        "description": (
            "Options are always structured to expire approximately 4 Fridays after "
            "entry (~25 days to expiration). Weekly options by default."
        ),
        "parameters_json": json.dumps(
            {"target_dte": 25, "min_dte": 23, "max_dte": 28, "prefer_weekly": True}
        ),
        "data_column_mapping": (
            "cycle_layers.expiration_date — should be entry_date + ~25 days"
        ),
    },
    {
        "rule_id": "RULE-CYCLE-003",
        "rule_area": "cycle",
        "rule_type": "hard_rule",
        "source_section": "Chapter 6 §2, Appendix B 'Cycle Ladder'",
        "description": (
            "The portfolio always maintains 4 overlapping active cycles "
            "simultaneously, each staggered 1 week apart. Every Monday adds 1 new "
            "cycle; every Friday exactly 1 cycle expires."
        ),
        "parameters_json": json.dumps(
            {
                "num_concurrent_cycles": 4,
                "entry_cadence": "weekly",
                "expiration_cadence": "weekly",
            }
        ),
        "data_column_mapping": "cycle_layers where status=ACTIVE — count should be <= 4",
    },
    {
        "rule_id": "RULE-CYCLE-004",
        "rule_area": "cycle",
        "rule_type": "hard_rule",
        "source_section": "Chapter 4 §5, Chapter 12 §1, Appendix B 'Monday-Only Decision Rule'",
        "description": (
            "All structural decisions occur between Friday's close and Monday's open "
            "while markets are closed. No intraday adjustments are permitted."
        ),
        "parameters_json": json.dumps(
            {
                "decision_window": "Friday_close_to_Monday_open",
                "intraday_adjustments": False,
            }
        ),
        "data_column_mapping": (
            "entry_decisions.decision_date must be weekend or Monday pre-market"
        ),
    },
    {
        "rule_id": "RULE-CYCLE-005",
        "rule_area": "cycle",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §1, §6",
        "description": (
            "Tuesday through Thursday: observe but do not alter open positions. "
            "No rolling, widening, closing, or adjusting option legs. The only "
            "exception is an earnings date change that pushes earnings before the "
            "upcoming weekend."
        ),
        "parameters_json": json.dumps(
            {
                "allowed_actions_midweek": ["observe", "monitor_earnings_changes"],
                "prohibited": ["roll", "close_early", "adjust_strikes"],
            }
        ),
        "data_column_mapping": (
            "No DB writes to cycle_layers status Tue–Thu except mandatory earnings override"
        ),
    },
    {
        "rule_id": "RULE-CYCLE-006",
        "rule_area": "cycle",
        "rule_type": "guideline",
        "source_section": "Chapter 8 §4",
        "description": (
            "Enter new positions 15–30 minutes after the Monday open, after initial "
            "opening volatility has subsided and spreads have normalized."
        ),
        "parameters_json": json.dumps({"wait_minutes_after_open": [15, 30]}),
        "data_column_mapping": "entry_decisions.executed_at timestamp",
    },
    {
        "rule_id": "RULE-CYCLE-007",
        "rule_area": "cycle",
        "rule_type": "guideline",
        "source_section": "Chapter 8 §6.4",
        "description": (
            "Fill the option strangle first (both call and put as a single strangle "
            "order using a limit order), then buy the stock."
        ),
        "parameters_json": json.dumps(
            {
                "execution_order": ["strangle_limit_order", "stock_order"],
                "use_single_strangle_ticket": True,
            }
        ),
        "data_column_mapping": "N/A — execution guideline",
    },
    # ── Earnings Rules ─────────────────────────────────────────────────────
    {
        "rule_id": "RULE-EARN-001",
        "rule_area": "earnings",
        "rule_type": "hard_gate",
        "source_section": "Chapter 8 §7, Chapter 13 §1, Appendix A 'Earnings & Event Risk'",
        "description": (
            "Do not open a Bull Strangle if the stock has an earnings announcement "
            "scheduled before the option expiration date. This rule is absolute — "
            "even an otherwise perfect setup is untradeable for that cycle."
        ),
        "parameters_json": json.dumps({"earnings_before_expiration": False}),
        "data_column_mapping": (
            "earnings_calendar.earnings_date must be > cycle_layers.expiration_date"
        ),
    },
    {
        "rule_id": "RULE-EARN-002",
        "rule_area": "earnings",
        "rule_type": "hard_rule",
        "source_section": "Chapter 13 §2",
        "description": (
            "The weekly watch list is built using a 45-day forward earnings filter. "
            "Any stock with an earnings report expected within 45 days of the Saturday "
            "prep date is excluded from consideration that week."
        ),
        "parameters_json": json.dumps({"earnings_exclusion_window_days": 45}),
        "data_column_mapping": "earnings_calendar.earnings_date must be > Saturday_date + 45",
    },
    {
        "rule_id": "RULE-EARN-003",
        "rule_area": "earnings",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §4.2, Chapter 13 §3",
        "description": (
            "If a company revises its earnings date into the active 4-week cycle after "
            "a position is already open, the position must be closed. This overrides "
            "every other rule including the no-mid-week-adjustments rule."
        ),
        "parameters_json": json.dumps(
            {
                "action": "sell_all_shares",
                "timing": "before_announcement_or_monday_open",
                "override_priority": "highest",
            }
        ),
        "data_column_mapping": (
            "earnings_calendar.earnings_date crosses into cycle_layers open_date "
            "to expiration_date"
        ),
    },
    {
        "rule_id": "RULE-EARN-004",
        "rule_area": "earnings",
        "rule_type": "hard_rule",
        "source_section": "Chapter 13 §4, Chapter 12 §2.1–2.3",
        "description": (
            "After any assignment (call or put), check whether the next 4-week cycle "
            "is clear of earnings. If earnings conflict: sell all shares Monday, select "
            "replacement. If clear: reset to original target share count and continue."
        ),
        "parameters_json": json.dumps(
            {
                "check_after_assignment": True,
                "earnings_conflict_action": "sell_all_replace",
                "clear_action": "reset_and_continue",
            }
        ),
        "data_column_mapping": "earnings_calendar.earnings_date vs. next cycle's expiration window",
    },
    # ── Exit & Assignment Rules ────────────────────────────────────────────
    {
        "rule_id": "RULE-EXIT-001",
        "rule_area": "exit",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §2, §6, Appendix F Step 5",
        "description": (
            "Default behavior: let all options expire naturally on Friday. Do not close "
            "options early except for an earnings date change (mandatory) or extreme "
            "drop (optional overlay). No rolling, no mid-cycle closing for profit taking."
        ),
        "parameters_json": json.dumps(
            {
                "hold_to_expiration": True,
                "early_close_exceptions": ["earnings_override", "extreme_drop_overlay"],
            }
        ),
        "data_column_mapping": "cycle_layers.status = ACTIVE until expiration_date",
    },
    {
        "rule_id": "RULE-EXIT-002",
        "rule_area": "exit",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §2.2, Chapter 4 §3.1",
        "description": (
            "When the call expires in-the-money, shares are sold at the call strike "
            "price (maximum-profit outcome). On Monday, capital is available for a "
            "new cycle in a different earnings-clear stock."
        ),
        "parameters_json": json.dumps(
            {
                "action": "shares_called_away_at_strike",
                "premium_status": "keep_both_premiums",
                "next_step": "new_cycle_different_stock",
            }
        ),
        "data_column_mapping": "cycle_layers.status → CLOSED (call_assigned)",
    },
    {
        "rule_id": "RULE-EXIT-003",
        "rule_area": "exit",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §2.3, Chapter 4 §3.2, Chapter 11 §8A",
        "description": (
            "When the put expires in-the-money, additional shares are assigned at the "
            "put strike price. On Monday: sell excess shares above original target; "
            "reset to original target share count; sell new call and put."
        ),
        "parameters_json": json.dumps(
            {
                "action": "accept_put_assignment",
                "sell_excess_shares": True,
                "reset_to_original_target": True,
                "premium_reduces_cost_basis": True,
            }
        ),
        "data_column_mapping": (
            "cycle_layers.target_shares, account_positions.quantity; sell to return to target"
        ),
    },
    {
        "rule_id": "RULE-EXIT-004",
        "rule_area": "exit",
        "rule_type": "hard_rule",
        "source_section": "Chapter 12 §2.1",
        "description": (
            "When both the call and put expire out-of-the-money: keep 100% of combined "
            "premium, retain underlying shares, no new shares assigned. On Monday, "
            "re-check earnings calendar for the upcoming cycle."
        ),
        "parameters_json": json.dumps(
            {
                "action": "keep_all_premium",
                "retain_shares": True,
                "next_step": "check_earnings_then_new_cycle",
            }
        ),
        "data_column_mapping": "cycle_layers.status → CLOSED (both_expired_otm)",
    },
    {
        "rule_id": "RULE-EXIT-005",
        "rule_area": "exit",
        "rule_type": "guideline",
        "source_section": "Chapter 11 §8.1",
        "description": (
            "Early call assignment occurs when the call is deep in-the-money with "
            "little time value remaining. For the remaining short put: if trading at "
            "$0.05–$0.10, close it for pennies. Otherwise allow to expire."
        ),
        "parameters_json": json.dumps(
            {
                "remaining_put_close_threshold": 0.10,
                "action_if_below_threshold": "close_for_pennies",
            }
        ),
        "data_column_mapping": "cycle_layers remaining put option price",
    },
    {
        "rule_id": "RULE-EXIT-006",
        "rule_area": "exit",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 14 §2, Chapter 12 §4.1",
        "description": (
            "OPTIONAL OVERLAY — not part of core system, not in published performance "
            "results. If stock declines 25% or more from its original purchase price "
            "during the active cycle, exit at the next Monday open."
        ),
        "parameters_json": json.dumps(
            {
                "threshold_pct": -25.0,
                "reference": "purchase_price",
                "action": "sell_all_monday_open",
                "leave_slot_empty": True,
            }
        ),
        "data_column_mapping": (
            "(account_positions.current_price - cycle_layers.stock_price_at_entry) "
            "/ cycle_layers.stock_price_at_entry"
        ),
    },
    {
        "rule_id": "RULE-EXIT-007",
        "rule_area": "exit",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 14 §2",
        "description": (
            "OPTIONAL OVERLAY. If stock declines 15% or more below the put strike "
            "price during the active cycle, exit at the next Monday open."
        ),
        "parameters_json": json.dumps(
            {
                "threshold_pct": -15.0,
                "reference": "put_strike",
                "action": "sell_all_monday_open",
                "leave_slot_empty": True,
            }
        ),
        "data_column_mapping": (
            "(account_positions.current_price - cycle_layers.put_strike) "
            "/ cycle_layers.put_strike"
        ),
    },
    {
        "rule_id": "RULE-EXIT-008",
        "rule_area": "exit",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 14 §2",
        "description": (
            "OPTIONAL OVERLAY. If stock declines 10% or more below its identified "
            "long-term support level during the active cycle, exit at the next Monday open."
        ),
        "parameters_json": json.dumps(
            {
                "threshold_pct": -10.0,
                "reference": "long_term_support",
                "action": "sell_all_monday_open",
                "leave_slot_empty": True,
            }
        ),
        "data_column_mapping": (
            "(account_positions.current_price - watchlist_entries.support_level) "
            "/ watchlist_entries.support_level"
        ),
    },
    # ── Market Environment Overlay ─────────────────────────────────────────
    {
        "rule_id": "GATE-ENV-001",
        "rule_area": "market_environment",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 20 §1, Appendix C §4",
        "description": (
            "Score component 1 of 3 for the Hybrid Market Environment Score. "
            "SPX above its 200-day MA = +1. SPX below = -1."
        ),
        "parameters_json": json.dumps(
            {"indicator": "SPX_vs_200DMA", "above": 1, "below": -1}
        ),
        "data_column_mapping": "market_environment.sp500_vs_200dma",
    },
    {
        "rule_id": "GATE-ENV-002",
        "rule_area": "market_environment",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 20 §1, Appendix C §4",
        "description": (
            "Score component 2 of 3. VIX < 20 = calm = +1. VIX 20–30 = caution = 0. "
            "VIX > 30 = high stress = -1."
        ),
        "parameters_json": json.dumps(
            {
                "calm_threshold": 20,
                "stress_threshold": 30,
                "calm_score": 1,
                "caution_score": 0,
                "stress_score": -1,
            }
        ),
        "data_column_mapping": "market_environment.vix",
    },
    {
        "rule_id": "GATE-ENV-003",
        "rule_area": "market_environment",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 20 §1, Appendix C §4",
        "description": (
            "Score component 3 of 3. Percentage of S&P 500 stocks trading above their "
            "50-day MA. >60% = healthy = +1. 40%–60% = neutral = 0. <40% = "
            "deteriorating = -1."
        ),
        "parameters_json": json.dumps(
            {
                "healthy_threshold": 60,
                "deteriorating_threshold": 40,
                "healthy_score": 1,
                "neutral_score": 0,
                "deteriorating_score": -1,
            }
        ),
        "data_column_mapping": "market_environment.pct_above_50dma",
    },
    {
        "rule_id": "RULE-ENV-001",
        "rule_area": "market_environment",
        "rule_type": "optional_overlay",
        "source_section": "Chapter 20 §2, Appendix C §4",
        "description": (
            "Hybrid Score from -3 to +3 maps to a position-size scaling factor. "
            "Full (+2/+3)=100%, Moderate (0/+1)=70%, Defensive (-3 to -1)=50%. "
            "All four weekly cycles continue regardless of regime — only size changes."
        ),
        "parameters_json": json.dumps(
            {
                "regimes": [
                    {"label": "Full", "min_score": 2, "max_score": 3, "size_factor": 1.0},
                    {"label": "Moderate", "min_score": 0, "max_score": 1, "size_factor": 0.7},
                    {"label": "Defensive", "min_score": -3, "max_score": -1, "size_factor": 0.5},
                ]
            }
        ),
        "data_column_mapping": (
            "market_environment.hybrid_score, market_environment.deployment_factor"
        ),
    },
    {
        "rule_id": "RULE-ENV-002",
        "rule_area": "market_environment",
        "rule_type": "hard_rule",
        "source_section": "Newsletter implementation (weekly decision engine)",
        "description": (
            "A market environment regime change is only acted on after 2 consecutive "
            "weeks in the new regime. Single-week readings are not sufficient to "
            "trigger a deployment change. Already implemented in "
            "compute_weekly_summary() / calculate_consecutive_weeks() in decisions.py."
        ),
        "parameters_json": json.dumps({"min_consecutive_weeks": 2}),
        "data_column_mapping": "weekly_decisions.consecutive_weeks",
    },
    # ── Return Formulas ────────────────────────────────────────────────────
    {
        "rule_id": "FORMULA-001",
        "rule_area": "formula",
        "rule_type": "formula",
        "source_section": "Chapter 10 §1.1, Appendix E D.2",
        "description": (
            "Invested Capital = (Shares × Stock Price at Entry) − Total Premium "
            "Collected. This is the net capital committed. Replaces broker margin numbers."
        ),
        "parameters_json": json.dumps(
            {"formula": "(shares * entry_price) - total_premium_collected"}
        ),
        "data_column_mapping": (
            "cycle_layers.shares, cycle_layers.stock_price_at_entry, "
            "cycle_layers.total_credit_collected"
        ),
    },
    {
        "rule_id": "FORMULA-002",
        "rule_area": "formula",
        "rule_type": "formula",
        "source_section": "Appendix E D.3",
        "description": (
            "Trade Return % = Total P&L / Cash Invested. "
            "Total P&L = Stock P&L + Call Premium P&L + Put Premium P&L."
        ),
        "parameters_json": json.dumps(
            {
                "formula": "total_pnl / cash_invested",
                "components": ["stock_pnl", "call_pnl", "put_pnl"],
            }
        ),
        "data_column_mapping": "exit_decisions.pnl_total, cycle_layers.invested_capital",
    },
    {
        "rule_id": "FORMULA-003",
        "rule_area": "formula",
        "rule_type": "formula",
        "source_section": "Appendix E D.4",
        "description": (
            "Portfolio Return = (Ending Portfolio Value − Beginning Portfolio Value) "
            "/ Beginning Portfolio Value. Evaluate quarterly or annually."
        ),
        "parameters_json": json.dumps(
            {"formula": "(ending_value - beginning_value) / beginning_value"}
        ),
        "data_column_mapping": "Account total value over measurement period",
    },
]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class RuleDefinition:
    """One row from ``strategy_rule_catalog``."""

    rule_id: str
    rule_area: str
    rule_type: str
    source_section: str
    description: str
    parameters_json: str  # raw JSON text — use .parameters for parsed dict
    data_column_mapping: str
    is_active: bool = True
    parameters: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.parameters_json and not self.parameters:
            try:
                self.parameters = json.loads(self.parameters_json)
            except (json.JSONDecodeError, TypeError):
                self.parameters = {}

    def get_param(self, key: str, default: Any = None) -> Any:
        """Convenience accessor — read one key from ``parameters``."""
        return self.parameters.get(key, default)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def load_rule_catalog(db_path: str | Path) -> int:
    """Seed ``strategy_rule_catalog`` with all 43 canonical rules.

    Uses ``INSERT OR IGNORE`` so the operation is idempotent — running it
    twice is safe and will not overwrite operator edits to existing rows.

    Returns the number of rows inserted (0 on subsequent calls).
    """
    initialize_database(db_path)
    inserted = 0
    with connect(db_path) as conn:
        for rule in _SEED_RULES:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO strategy_rule_catalog
                    (rule_id, rule_area, rule_type, source_section,
                     description, parameters_json, data_column_mapping)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule["rule_id"],
                    rule["rule_area"],
                    rule["rule_type"],
                    rule.get("source_section"),
                    rule["description"],
                    rule.get("parameters_json"),
                    rule.get("data_column_mapping"),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _row_to_rule(row: Any) -> RuleDefinition:
    return RuleDefinition(
        rule_id=row["rule_id"],
        rule_area=row["rule_area"],
        rule_type=row["rule_type"],
        source_section=row["source_section"] or "",
        description=row["description"],
        parameters_json=row["parameters_json"] or "{}",
        data_column_mapping=row["data_column_mapping"] or "",
        is_active=bool(row["is_active"]),
    )


def get_rule(db_path: str | Path, rule_id: str) -> RuleDefinition:
    """Fetch a single rule by ``rule_id``.

    Raises ``KeyError`` if the rule is not found or the catalog has not been
    seeded.  Call ``load_rule_catalog()`` once before querying.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM strategy_rule_catalog WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"Rule not found in catalog: {rule_id!r}")
    return _row_to_rule(row)


def get_gate_rules(
    db_path: str | Path,
    rule_area: str | None = None,
    rule_type: str | None = None,
    active_only: bool = True,
) -> list[RuleDefinition]:
    """Return rules filtered by area and/or type.

    Parameters
    ----------
    rule_area:
        One of stock_selection, earnings, strike_selection, capital, cycle,
        exit, market_environment, formula — or ``None`` for all areas.
    rule_type:
        One of hard_gate, soft_gate, hard_rule, guideline, optional_overlay,
        formula — or ``None`` for all types.
    active_only:
        If ``True`` (default) only ``is_active = 1`` rows are returned.
    """
    initialize_database(db_path)
    clauses: list[str] = []
    params: list[Any] = []
    if active_only:
        clauses.append("is_active = 1")
    if rule_area:
        clauses.append("rule_area = ?")
        params.append(rule_area)
    if rule_type:
        clauses.append("rule_type = ?")
        params.append(rule_type)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM strategy_rule_catalog {where} ORDER BY rule_area, rule_id"

    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_rule(r) for r in rows]


def list_rule_catalog(
    db_path: str | Path,
    rule_area: str | None = None,
    rule_type: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Return all catalog rules as plain dicts (MCP-friendly).

    Auto-seeds the catalog if it is empty.
    """
    initialize_database(db_path)
    # Auto-seed if catalog is empty
    with connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_rule_catalog"
        ).fetchone()[0]
    if count == 0:
        load_rule_catalog(db_path)

    rules = get_gate_rules(db_path, rule_area=rule_area, rule_type=rule_type, active_only=active_only)
    return [
        {
            "rule_id": r.rule_id,
            "rule_area": r.rule_area,
            "rule_type": r.rule_type,
            "source_section": r.source_section,
            "description": r.description,
            "parameters": r.parameters,
            "data_column_mapping": r.data_column_mapping,
            "is_active": r.is_active,
        }
        for r in rules
    ]
