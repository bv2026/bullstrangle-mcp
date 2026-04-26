# Master Document Rule Inventory

Date: 2026-04-26
Source: Bull Strangle Master Document — Version 8.pdf (187 pages)
Status: ACTIVE — seed data for `strategy_rule_catalog` table

## Purpose

Every rule, gate, threshold, and guideline extracted from the Master Document.
Each row maps to one `strategy_rule_catalog` entry in the Phase 2 build.

Column definitions:
- `rule_id` — unique identifier used in code and DB
- `rule_area` — stock_selection / market_environment / strike_selection / capital / cycle / earnings / exit / formula
- `rule_type` — hard_gate (blocks entry/exit) / soft_gate (flags but does not block) / hard_rule (mandatory) / guideline (recommended) / optional_overlay / formula
- `source_section` — exact chapter and section in the Master Document
- `description` — plain English
- `parameters_json` — numeric thresholds or comparators
- `data_column_mapping` — which DB column or OS field provides the runtime value

---

## Stock Selection Gates

### GATE-SS-001 — Implied Volatility Ceiling

| Field | Value |
|---|---|
| rule_id | GATE-SS-001 |
| rule_area | stock_selection |
| rule_type | hard_gate |
| source_section | Chapter 3 §3.3, Chapter 5 §4.4, Appendix F Step 1 |
| description | Exclude any stock with implied volatility (IV) at or above 1.0. High IV signals instability; backtesting showed nearly all severe losses came from IV > 1.0 names. |
| parameters_json | `{"max_iv": 1.0, "comparator": "<"}` |
| data_column_mapping | `os_evaluation_rows.iv` or `watchlist_entries.iv` |

---

### GATE-SS-002 — Moving Average Alignment

| Field | Value |
|---|---|
| rule_id | GATE-SS-002 |
| rule_area | stock_selection |
| rule_type | hard_gate |
| source_section | Chapter 2 §3.3, Chapter 5 §4.1, Appendix C §2 |
| description | Stock must trade above at least 2 of the 4 key moving averages (20, 50, 100, 200-day). A stock below 3 or all 4 MAs is classified "broken" and excluded regardless of premium. |
| parameters_json | `{"ma_periods": [20, 50, 100, 200], "min_mas_above": 2, "broken_threshold": 2}` |
| data_column_mapping | `os_evaluation_rows.above_20ma`, `.above_50ma`, `.above_100ma`, `.above_200ma` (count of trues must be ≥ 2) |

---

### GATE-SS-003 — Option Chain Liquidity (No Zero Bids)

| Field | Value |
|---|---|
| rule_id | GATE-SS-003 |
| rule_area | stock_selection |
| rule_type | hard_gate |
| source_section | Chapter 5 §4.2, Appendix F Step 1 |
| description | The option chain must show active bid prices on both the call and put at the intended strikes. Zero-bid strikes are an automatic rejection — no exceptions regardless of how attractive the premium appears. |
| parameters_json | `{"min_bid": 0.01, "required_sides": ["call", "put"]}` |
| data_column_mapping | `os_evaluation_rows.call_bid`, `os_evaluation_rows.put_bid` (both must be > 0) |

---

### GATE-SS-004 — Minimum Premium Yield

| Field | Value |
|---|---|
| rule_id | GATE-SS-004 |
| rule_area | stock_selection |
| rule_type | soft_gate |
| source_section | Chapter 5 §4.2 |
| description | Combined call + put premium must yield at least 2% of the stock price. Wide spreads with a chain that still clears 2% are tradable (conditional). Chains below 2% are excluded. |
| parameters_json | `{"min_premium_yield_pct": 2.0, "comparator": ">="}` |
| data_column_mapping | `os_evaluation_rows.total_credit / os_evaluation_rows.stock_price * 100` |

---

### GATE-SS-005 — Earnings Clearance at Entry (45-Day Filter)

| Field | Value |
|---|---|
| rule_id | GATE-SS-005 |
| rule_area | earnings |
| rule_type | hard_gate |
| source_section | Chapter 13 §2, Appendix F Step 1 |
| description | No stock may be selected for a cycle if its next earnings announcement falls within 45 days of the trade entry date. This buffer eliminates most conflicts including date revisions of up to 2 weeks. Treat every published earnings date as real regardless of confirmed vs. estimated status. |
| parameters_json | `{"min_earnings_clear_days": 45, "comparator": ">"}` |
| data_column_mapping | `earnings_calendar.earnings_date` — must be > entry_date + 45 days |

---

### GATE-SS-006 — No Broken Chart (Support Failure)

| Field | Value |
|---|---|
| rule_id | GATE-SS-006 |
| rule_area | stock_selection |
| rule_type | hard_gate |
| source_section | Chapter 2 §3.3, Chapter 5 §2.2 |
| description | A stock trading below 3 or all 4 major moving averages (20, 50, 100, 200-day) is classified as "broken." Broken stocks are excluded completely — support has failed at all timeframes, momentum is decisively negative, and premium is not compensation for this structural risk. |
| parameters_json | `{"ma_periods": [20, 50, 100, 200], "max_mas_below": 2}` |
| data_column_mapping | Count of `os_evaluation_rows.above_NNma = false` must be ≤ 2 |

---

### GATE-SS-007 — No High-Flyer Behavior

| Field | Value |
|---|---|
| rule_id | GATE-SS-007 |
| rule_area | stock_selection |
| rule_type | soft_gate |
| source_section | Chapter 2 §3.2, Chapter 5 §2.1, §5 |
| description | Stocks stretched far above all moving averages and showing parabolic, gap-prone, or social-media-driven momentum are excluded. Practical test: if a 10% move in 2 weeks would feel normal for this stock, it is a high-flyer. Higher premium from high-flyers does not compensate for their tail risk. |
| parameters_json | `{"qualitative": true, "heuristic": "10pct_move_feels_normal"}` |
| data_column_mapping | Newsletter `watchlist_entries.is_high_flyer` flag (manual or screened) |

---

### GATE-SS-008 — Watchlist Membership Required

| Field | Value |
|---|---|
| rule_id | GATE-SS-008 |
| rule_area | stock_selection |
| rule_type | hard_gate |
| source_section | Chapter 8 §1, Appendix B glossary "Watch List" |
| description | Only stocks on the current weekly watch list may be used to initiate a cycle. The watch list is the pre-screened universe. Candidates outside the list are not eligible regardless of how attractive they appear on Monday morning. |
| parameters_json | `{"source": "watchlist_entries", "newsletter_date": "current"}` |
| data_column_mapping | `watchlist_entries` — symbol must exist for the current newsletter_id |

---

## Strike Selection Rules

### RULE-STRIKE-001 — Call Strike Formula

| Field | Value |
|---|---|
| rule_id | RULE-STRIKE-001 |
| rule_area | strike_selection |
| rule_type | hard_rule |
| source_section | Chapter 3 §6.3, Appendix E D.1 |
| description | Call strike = stock_price × 1.015, then round UP to the nearest available listed strike. This ensures the call is always at least 1.5% above the stock. Across hundreds of trades, resulting actual distances consistently land 2.0%–3.5% from the stock. |
| parameters_json | `{"offset_pct": 0.015, "direction": "above", "rounding": "up"}` |
| data_column_mapping | `watchlist_entries.sell_call_strike`, `os_evaluation_rows.stock_price` |

---

### RULE-STRIKE-002 — Put Strike Formula

| Field | Value |
|---|---|
| rule_id | RULE-STRIKE-002 |
| rule_area | strike_selection |
| rule_type | hard_rule |
| source_section | Chapter 3 §6.3, Appendix E D.1 |
| description | Put strike = stock_price × 0.985, then round DOWN to the nearest available listed strike. This ensures the put is always at least 1.5% below the stock. |
| parameters_json | `{"offset_pct": -0.015, "direction": "below", "rounding": "down"}` |
| data_column_mapping | `watchlist_entries.sell_put_strike`, `os_evaluation_rows.stock_price` |

---

### RULE-STRIKE-003 — Target Distance Band

| Field | Value |
|---|---|
| rule_id | RULE-STRIKE-003 |
| rule_area | strike_selection |
| rule_type | guideline |
| source_section | Chapter 3 §6.3, §6.5 |
| description | Resulting strike distances should land in the 2.0%–3.5% band from the stock price. This is a confirmation check, not a selection driver. Lower IV names cluster around 2.7%–2.9%; moderate IV around 3.3%; higher acceptable IV (0.8–1.0) around 3.6%+. The 1.5% rule self-adjusts via strike grid rounding. |
| parameters_json | `{"min_distance_pct": 2.0, "max_distance_pct": 3.5}` |
| data_column_mapping | Derived from `os_evaluation_rows.call_strike`, `.put_strike`, `.stock_price` |

---

### RULE-STRIKE-004 — Monday Price Adjustment

| Field | Value |
|---|---|
| rule_id | RULE-STRIKE-004 |
| rule_area | strike_selection |
| rule_type | hard_rule |
| source_section | Chapter 8 §5 |
| description | If the stock price has moved from Friday's close by the time Monday opens, slide BOTH strikes by approximately the same dollar amount the stock moved. This preserves the original gap (dollar distance) between call and put strikes. The goal is structural equivalence with the newsletter model, not arithmetic precision. |
| parameters_json | `{"adjustment": "slide_both_strikes_by_price_change", "preserve": "call_put_gap_dollars"}` |
| data_column_mapping | `watchlist_entries.price` (Friday close) vs. live Monday price |

---

## Capital & Position Sizing Rules

### RULE-CAPITAL-001 — 25% Excess Cash Buffer

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-001 |
| rule_area | capital |
| rule_type | hard_rule |
| source_section | Chapter 9 §4, Chapter 11, Appendix A "Capital & Risk Architecture" |
| description | Always maintain approximately 25% of total account value in unused cash. This is the single most important capital rule. The buffer eliminates margin stress, keeps Monday rotation funded, and reduces emotional pressure during drawdowns. The 25% is not leftover capital — it is a structural buffer. |
| parameters_json | `{"min_cash_buffer": 0.25, "comparator": ">="}` |
| data_column_mapping | `account_positions` cash balance / total account value |

---

### RULE-CAPITAL-002 — 75% Maximum Deployment

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-002 |
| rule_area | capital |
| rule_type | hard_rule |
| source_section | Chapter 6 §3.1, Appendix A "Capital & Risk Architecture" |
| description | Only 75% of total account value is eligible for deployment across all four active cycles at any time. Capital is allocated weekly not all at once. |
| parameters_json | `{"max_deployed_pct": 0.75}` |
| data_column_mapping | Total invested capital / total account value |

---

### RULE-CAPITAL-003 — Weekly Cycle Target Allocation

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-003 |
| rule_area | capital |
| rule_type | hard_rule |
| source_section | Chapter 6 §3.1 |
| description | Weekly target = (total_account_value × 0.75) / 4. Each new Monday cycle is funded to this target. The cycle target is the amount across ALL positions entered in that week's lane, not per individual trade. |
| parameters_json | `{"formula": "account_value * 0.75 / 4", "num_cycles": 4}` |
| data_column_mapping | `symbol_position_rollups.total_value` or account_positions sum |

---

### RULE-CAPITAL-004 — 100-Share Block Sizing

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-004 |
| rule_area | capital |
| rule_type | hard_rule |
| source_section | Chapter 4 §1, Chapter 6 §3.2 |
| description | Share counts must always be multiples of 100 because each option contract controls 100 shares. Choose the nearest 100-share increment that fits within the weekly target range without exceeding it. Dollar allocation stays consistent; share count flexes by stock price. |
| parameters_json | `{"share_increment": 100}` |
| data_column_mapping | `account_positions.quantity` must be divisible by 100 |

---

### RULE-CAPITAL-005 — Per-Position Sizing by Account Size

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-005 |
| rule_area | capital |
| rule_type | guideline |
| source_section | Chapter 11 §3, §4 |
| description | Position size as a percentage of total capital varies by account size. Three tiers apply: (1) $40k–$55k: ~6.3% per position, 3 trades/week. (2) $55k–$90k: ~4.7% per position, 4 trades/week. (3) $90k+: ~3.8% per position, 5 trades/week. Below $40k: 9.4%–18.8% per position with fewer positions. These are guidelines not rigid rules. |
| parameters_json | `{"tiers": [{"min_account": 40000, "max_account": 55000, "pct_per_position": 6.3, "trades_per_week": 3}, {"min_account": 55000, "max_account": 90000, "pct_per_position": 4.7, "trades_per_week": 4}, {"min_account": 90000, "max_account": null, "pct_per_position": 3.8, "trades_per_week": 5}]}` |
| data_column_mapping | Total account value from `account_positions` |

---

### RULE-CAPITAL-006 — Weekly Trade Count by Account Size

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-006 |
| rule_area | capital |
| rule_type | guideline |
| source_section | Chapter 11 §7.2 |
| description | Number of positions per weekly cycle guided by account size: $10k–$20k = 1 trade; $20k–$35k = 2 trades; $35k–$50k = 3 trades; $50k–$90k = 4 trades; $90k+ = up to 5 trades. |
| parameters_json | `{"tiers": [{"min": 10000, "max": 20000, "trades": 1}, {"min": 20000, "max": 35000, "trades": 2}, {"min": 35000, "max": 50000, "trades": 3}, {"min": 50000, "max": 90000, "trades": 4}, {"min": 90000, "max": null, "trades": 5}]}` |
| data_column_mapping | Total account value |

---

### RULE-CAPITAL-007 — Sector Concentration Limit

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-007 |
| rule_area | capital |
| rule_type | hard_rule |
| source_section | Appendix A "Stock, Volatility & Portfolio Filters" |
| description | Small accounts: no more than 1 stock per sector at any time. Large accounts: no more than 3 stocks per sector at any time. Sector diversification is a structural risk control not a preference. |
| parameters_json | `{"small_account_max_per_sector": 1, "large_account_max_per_sector": 3}` |
| data_column_mapping | `account_positions.sector` grouped count across open cycles |

---

### RULE-CAPITAL-008 — Invested Capital Formula

| Field | Value |
|---|---|
| rule_id | RULE-CAPITAL-008 |
| rule_area | formula |
| rule_type | formula |
| source_section | Chapter 10 §1.1, Appendix E D.2 |
| description | Invested Capital = (Shares Purchased × Stock Price) − Option Premium Collected. This is the net capital at risk for a position. Premium received upfront reduces the cash required. This metric replaces broker margin numbers as the position sizing reference. |
| parameters_json | `{"formula": "(shares * stock_price) - total_premium_collected"}` |
| data_column_mapping | `cycle_layers.shares`, `cycle_layers.stock_price_at_entry`, `cycle_layers.total_credit_collected` |

---

## Cycle & Timing Rules

### RULE-CYCLE-001 — Monday-Only Entry

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-001 |
| rule_area | cycle |
| rule_type | hard_rule |
| source_section | Chapter 1 §4, Chapter 6 §6, Appendix B "Monday-Only Decision Rule" |
| description | All new positions are entered on Monday only. No new trades are initiated mid-week. Monday morning is the decision window where watch list candidates are confirmed, strikes finalized, and orders placed. |
| parameters_json | `{"entry_day": "Monday"}` |
| data_column_mapping | `cycle_layers.open_date` must be a Monday |

---

### RULE-CYCLE-002 — ~25-Day Expiration Target

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-002 |
| rule_area | cycle |
| rule_type | hard_rule |
| source_section | Chapter 3 §1.4, Chapter 6 §1 |
| description | Options are always structured to expire approximately 4 Fridays after entry (~25 days to expiration). Weekly options are used by default; monthly options (third Friday) are considered only when the 4-Friday horizon aligns with that date, and only when liquidity and pricing are at least equal to the weekly equivalent. |
| parameters_json | `{"target_dte": 25, "min_dte": 23, "max_dte": 28, "prefer_weekly": true}` |
| data_column_mapping | `cycle_layers.expiration_date` — should be entry_date + ~25 days |

---

### RULE-CYCLE-003 — Four-Lane Ladder

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-003 |
| rule_area | cycle |
| rule_type | hard_rule |
| source_section | Chapter 6 §2, Appendix B "Cycle Ladder" |
| description | The portfolio always maintains 4 overlapping active cycles simultaneously, each staggered 1 week apart. Every Monday adds 1 new cycle to the lane vacated by Friday's expiration. Each Friday exactly 1 cycle expires. The ladder rolls forward automatically. |
| parameters_json | `{"num_concurrent_cycles": 4, "entry_cadence": "weekly", "expiration_cadence": "weekly"}` |
| data_column_mapping | `cycle_layers` where status = ACTIVE — count should be ≤ 4 |

---

### RULE-CYCLE-004 — Friday-Close → Monday-Open Decision Window

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-004 |
| rule_area | cycle |
| rule_type | hard_rule |
| source_section | Chapter 4 §5, Chapter 12 §1, Appendix B "Monday-Only Decision Rule" |
| description | All structural decisions — assignment resolution, share resets, new cycle entry — occur between Friday's close and Monday's open while markets are closed. No intraday adjustments are permitted. This prevents emotional, price-driven decisions and ensures all choices follow the written rules. |
| parameters_json | `{"decision_window": "Friday_close_to_Monday_open", "intraday_adjustments": false}` |
| data_column_mapping | `entry_decisions.decision_date` must be weekend or Monday pre-market |

---

### RULE-CYCLE-005 — No Mid-Week Adjustments

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-005 |
| rule_area | cycle |
| rule_type | hard_rule |
| source_section | Chapter 12 §1, §6 |
| description | Tuesday through Thursday: observe but do not alter open positions. No rolling, widening, closing, or adjusting option legs. No repair trades. Mid-week monitoring is informational only. Information gathered is held until the Friday-close → Monday-open window. The only exception is an earnings date change that pushes earnings before the upcoming weekend. |
| parameters_json | `{"allowed_actions_midweek": ["observe", "monitor_earnings_changes"], "prohibited": ["roll", "close_early", "adjust_strikes"]}` |
| data_column_mapping | No DB writes to `cycle_layers` status Tue–Thu except mandatory earnings override |

---

### RULE-CYCLE-006 — Execution Timing — Post-Open Wait

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-006 |
| rule_area | cycle |
| rule_type | guideline |
| source_section | Chapter 8 §4 |
| description | Enter new positions 15–30 minutes after the Monday open, after initial opening volatility has subsided and spreads have normalized. Do not enter at the open. |
| parameters_json | `{"wait_minutes_after_open": [15, 30]}` |
| data_column_mapping | `entry_decisions.executed_at` timestamp |

---

### RULE-CYCLE-007 — Execute Options Before Stock

| Field | Value |
|---|---|
| rule_id | RULE-CYCLE-007 |
| rule_area | cycle |
| rule_type | guideline |
| source_section | Chapter 8 §6.4 |
| description | Fill the option strangle first (both call and put as a single strangle order using a limit order), then buy the stock. Options are less liquid and more prone to slippage. Getting the credit locked in before the stock purchase avoids owning the stock without the premium secured. |
| parameters_json | `{"execution_order": ["strangle_limit_order", "stock_order"], "use_single_strangle_ticket": true}` |
| data_column_mapping | N/A — execution guideline |

---

## Earnings Rules

### RULE-EARN-001 — Mandatory Entry Block: Earnings in Cycle Window

| Field | Value |
|---|---|
| rule_id | RULE-EARN-001 |
| rule_area | earnings |
| rule_type | hard_gate |
| source_section | Chapter 8 §7, Chapter 13 §1, Appendix A "Earnings & Event Risk" |
| description | Do not open a Bull Strangle if the stock has an earnings announcement scheduled before the option expiration date. This rule is absolute — even an otherwise perfect setup is untradeable for that cycle if earnings fall before expiration. |
| parameters_json | `{"earnings_before_expiration": false}` |
| data_column_mapping | `earnings_calendar.earnings_date` must be > `cycle_layers.expiration_date` |

---

### RULE-EARN-002 — Saturday Watch List 45-Day Screen

| Field | Value |
|---|---|
| rule_id | RULE-EARN-002 |
| rule_area | earnings |
| rule_type | hard_rule |
| source_section | Chapter 13 §2 |
| description | The weekly watch list is built using a 45-day forward earnings filter. Any stock with an earnings report expected within 45 days of the Saturday prep date is excluded from consideration that week. This buffer covers the 4-week cycle window plus a 2-week revision buffer. |
| parameters_json | `{"earnings_exclusion_window_days": 45}` |
| data_column_mapping | `earnings_calendar.earnings_date` must be > Saturday_date + 45 |

---

### RULE-EARN-003 — Mid-Cycle Earnings Override (Mandatory Exit)

| Field | Value |
|---|---|
| rule_id | RULE-EARN-003 |
| rule_area | earnings |
| rule_type | hard_rule |
| source_section | Chapter 12 §4.2, Chapter 13 §3 |
| description | If a company revises its earnings date into the active 4-week cycle after a position is already open, the position must be closed. This overrides every other rule including the no-mid-week-adjustments rule. If announcement is before the upcoming weekend: close immediately (rare mid-week exit allowed). If announcement is after the upcoming weekend: sell all shares near next Monday open. |
| parameters_json | `{"action": "sell_all_shares", "timing": "before_announcement_or_monday_open", "override_priority": "highest"}` |
| data_column_mapping | `earnings_calendar.earnings_date` crosses into `cycle_layers.open_date` to `cycle_layers.expiration_date` |

---

### RULE-EARN-004 — Assignment Earnings Check

| Field | Value |
|---|---|
| rule_id | RULE-EARN-004 |
| rule_area | earnings |
| rule_type | hard_rule |
| source_section | Chapter 13 §4, Chapter 12 §2.1–2.3 |
| description | After any assignment (call or put), check whether the next 4-week cycle is clear of earnings before deciding whether to continue with the same stock. If the next cycle contains earnings: sell all shares on Monday, select a replacement from the watch list. If the cycle is clear: reset to original target share count and continue. |
| parameters_json | `{"check_after_assignment": true, "earnings_conflict_action": "sell_all_replace", "clear_action": "reset_and_continue"}` |
| data_column_mapping | `earnings_calendar.earnings_date` vs. next cycle's expiration window |

---

## Exit & Assignment Rules

### RULE-EXIT-001 — Hold to Expiration (Default)

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-001 |
| rule_area | exit |
| rule_type | hard_rule |
| source_section | Chapter 12 §2, §6, Appendix F Step 5 |
| description | Default behavior: let all options expire naturally on Friday. Do not close options early except for an earnings date change (mandatory) or extreme drop (optional overlay). No rolling, no mid-cycle closing for "profit taking," no defensive adjustments. Expiration is the primary resolution mechanism. |
| parameters_json | `{"hold_to_expiration": true, "early_close_exceptions": ["earnings_override", "extreme_drop_overlay"]}` |
| data_column_mapping | `cycle_layers.status` = ACTIVE until expiration_date |

---

### RULE-EXIT-002 — Call Assignment: Accept and Rotate

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-002 |
| rule_area | exit |
| rule_type | hard_rule |
| source_section | Chapter 12 §2.2, Chapter 4 §3.1 |
| description | When the call expires in-the-money, shares are sold at the call strike price. This is a maximum-profit outcome: stock gains up to the call strike + full call premium + full put premium. On Monday, the capital from the sale is available for a new cycle in a different (earnings-clear) stock. The ladder slot continues normally. |
| parameters_json | `{"action": "shares_called_away_at_strike", "premium_status": "keep_both_premiums", "next_step": "new_cycle_different_stock"}` |
| data_column_mapping | `cycle_layers.status` → CLOSED (call_assigned); `exit_decisions.actual_action` |

---

### RULE-EXIT-003 — Put Assignment: Reset to Target Size

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-003 |
| rule_area | exit |
| rule_type | hard_rule |
| source_section | Chapter 12 §2.3, Chapter 4 §3.2, Chapter 11 §8A |
| description | When the put expires in-the-money, additional shares are assigned at the put strike price. The effective cost basis is reduced by the combined premium collected. On Monday (assuming no earnings conflict in next cycle): sell excess shares above the original target quantity near the open; reset position to original target share count; sell new call and put against the reset position. Assignment is not a disruption — it is an expected reset event. |
| parameters_json | `{"action": "accept_put_assignment", "sell_excess_shares": true, "reset_to_original_target": true, "premium_reduces_cost_basis": true}` |
| data_column_mapping | `cycle_layers.target_shares`, `account_positions.quantity`; sell to return to target |

---

### RULE-EXIT-004 — Both Options Expire Worthless

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-004 |
| rule_area | exit |
| rule_type | hard_rule |
| source_section | Chapter 12 §2.1 |
| description | When both the call and put expire out-of-the-money: keep 100% of combined premium, retain underlying shares, no new shares assigned. On Monday, re-check earnings calendar for the upcoming cycle. If clear: sell new call and put against same position. If earnings conflict: sell shares and replace with new stock. |
| parameters_json | `{"action": "keep_all_premium", "retain_shares": true, "next_step": "check_earnings_then_new_cycle"}` |
| data_column_mapping | `cycle_layers.status` → CLOSED (both_expired_otm) |

---

### RULE-EXIT-005 — Early Call Assignment (Rare)

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-005 |
| rule_area | exit |
| rule_type | guideline |
| source_section | Chapter 11 §8.1 |
| description | Early call assignment occurs when the call is deep in-the-money with little time value remaining, typically near an ex-dividend date. Treat as a maximum-profit outcome. For the remaining short put: if trading at $0.05–$0.10, close it for pennies (preferred). Otherwise allow to expire. The ladder slot remains available for the next Monday cycle. |
| parameters_json | `{"remaining_put_close_threshold": 0.10, "action_if_below_threshold": "close_for_pennies"}` |
| data_column_mapping | `cycle_layers` remaining put option price |

---

### RULE-EXIT-006 (Optional) — Extreme Drop: 25% from Purchase Price

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-006 |
| rule_area | exit |
| rule_type | optional_overlay |
| source_section | Chapter 14 §2, Chapter 12 §4.1 |
| description | OPTIONAL OVERLAY — not part of core system, not in published performance results. If stock declines 25% or more from its original purchase price during the active cycle, exit the position at the next Monday open. Leave the cycle slot empty until its natural reset point. Do not replace immediately. |
| parameters_json | `{"threshold_pct": -25.0, "reference": "purchase_price", "action": "sell_all_monday_open", "leave_slot_empty": true}` |
| data_column_mapping | (`account_positions.current_price` - `cycle_layers.stock_price_at_entry`) / `cycle_layers.stock_price_at_entry` |

---

### RULE-EXIT-007 (Optional) — Extreme Drop: 15% Below Put Strike

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-007 |
| rule_area | exit |
| rule_type | optional_overlay |
| source_section | Chapter 14 §2 |
| description | OPTIONAL OVERLAY. If stock declines 15% or more below the put strike price during the active cycle, exit the position at the next Monday open. Leave the cycle slot empty until its natural reset point. |
| parameters_json | `{"threshold_pct": -15.0, "reference": "put_strike", "action": "sell_all_monday_open", "leave_slot_empty": true}` |
| data_column_mapping | (`account_positions.current_price` - `cycle_layers.put_strike`) / `cycle_layers.put_strike` |

---

### RULE-EXIT-008 (Optional) — Extreme Drop: 10% Violation of Long-Term Support

| Field | Value |
|---|---|
| rule_id | RULE-EXIT-008 |
| rule_area | exit |
| rule_type | optional_overlay |
| source_section | Chapter 14 §2 |
| description | OPTIONAL OVERLAY. If stock declines 10% or more below its identified long-term support level during the active cycle, exit the position at the next Monday open. Leave the cycle slot empty. Early exits during volatility spikes may reduce long-term returns even while improving tail-risk characteristics. |
| parameters_json | `{"threshold_pct": -10.0, "reference": "long_term_support", "action": "sell_all_monday_open", "leave_slot_empty": true}` |
| data_column_mapping | (`account_positions.current_price` - `watchlist_entries.support_level`) / `watchlist_entries.support_level` |

---

## Market Environment Overlay (Optional Enhancement)

### GATE-ENV-001 — Trend Component: SPX vs. 200-Day MA

| Field | Value |
|---|---|
| rule_id | GATE-ENV-001 |
| rule_area | market_environment |
| rule_type | optional_overlay |
| source_section | Chapter 20 §1, Appendix C §4 |
| description | Score component 1 of 3 for the Hybrid Market Environment Score. SPX above its 200-day moving average = +1. SPX below = -1. Scores range from -3 to +3 across all three components. |
| parameters_json | `{"indicator": "SPX_vs_200DMA", "above": 1, "below": -1}` |
| data_column_mapping | `market_environment.sp500_vs_200dma` |

---

### GATE-ENV-002 — Volatility Component: VIX Regime

| Field | Value |
|---|---|
| rule_id | GATE-ENV-002 |
| rule_area | market_environment |
| rule_type | optional_overlay |
| source_section | Chapter 20 §1, Appendix C §4 |
| description | Score component 2 of 3. VIX < 20 = calm = +1. VIX 20–30 = caution = 0. VIX > 30 = high stress = -1. |
| parameters_json | `{"calm_threshold": 20, "stress_threshold": 30, "calm_score": 1, "caution_score": 0, "stress_score": -1}` |
| data_column_mapping | `market_environment.vix` |

---

### GATE-ENV-003 — Breadth Component: % Stocks Above 50-Day MA

| Field | Value |
|---|---|
| rule_id | GATE-ENV-003 |
| rule_area | market_environment |
| rule_type | optional_overlay |
| source_section | Chapter 20 §1, Appendix C §4 |
| description | Score component 3 of 3. Percentage of S&P 500 stocks trading above their 50-day moving average. > 60% = healthy participation = +1. 40%–60% = neutral = 0. < 40% = deteriorating breadth = -1. Breadth tends to weaken before major declines. |
| parameters_json | `{"healthy_threshold": 60, "deteriorating_threshold": 40, "healthy_score": 1, "neutral_score": 0, "deteriorating_score": -1}` |
| data_column_mapping | `market_environment.pct_above_50dma` |

---

### RULE-ENV-001 — Hybrid Score to Exposure Mapping

| Field | Value |
|---|---|
| rule_id | RULE-ENV-001 |
| rule_area | market_environment |
| rule_type | optional_overlay |
| source_section | Chapter 20 §2, Appendix C §4 |
| description | Sum of the three component scores produces a Hybrid Score from -3 to +3. This score maps to a position-size scaling factor. All four weekly cycles continue to operate regardless of regime — only the size of positions and idle cash level change. Core rules (strike selection, earnings avoidance, expiration timing) are never altered. |
| parameters_json | `{"regimes": [{"label": "Full", "min_score": 2, "max_score": 3, "size_factor": 1.0}, {"label": "Moderate", "min_score": 0, "max_score": 1, "size_factor": 0.7}, {"label": "Defensive", "min_score": -3, "max_score": -1, "size_factor": 0.5}]}` |
| data_column_mapping | `market_environment.hybrid_score`, `market_environment.deployment_factor` |

---

### RULE-ENV-002 — Two-Consecutive-Week Confirmation

| Field | Value |
|---|---|
| rule_id | RULE-ENV-002 |
| rule_area | market_environment |
| rule_type | hard_rule |
| source_section | Newsletter implementation (referenced in weekly decision engine) |
| description | A market environment regime change is only acted on after 2 consecutive weeks in the new regime. Single-week readings are not sufficient to trigger a deployment change. This prevents whipsawing on brief market volatility. Already implemented in `compute_weekly_summary()` / `calculate_consecutive_weeks()` in decisions.py. |
| parameters_json | `{"min_consecutive_weeks": 2}` |
| data_column_mapping | `weekly_decisions.consecutive_weeks` |

---

## Return Formulas

### FORMULA-001 — Invested Capital

| Field | Value |
|---|---|
| rule_id | FORMULA-001 |
| rule_area | formula |
| rule_type | formula |
| source_section | Chapter 10 §1.1, Appendix E D.2 |
| description | Invested Capital = (Shares × Stock Price at Entry) − Total Premium Collected. This is the net capital committed to a position after premium received. Replaces broker margin numbers. |
| parameters_json | `{"formula": "(shares * entry_price) - total_premium_collected"}` |
| data_column_mapping | `cycle_layers.shares`, `cycle_layers.stock_price_at_entry`, `cycle_layers.total_credit_collected` |

---

### FORMULA-002 — Trade Return

| Field | Value |
|---|---|
| rule_id | FORMULA-002 |
| rule_area | formula |
| rule_type | formula |
| source_section | Appendix E D.3 |
| description | Trade Return % = Total P&L / Cash Invested. Total P&L = Stock P&L + Call Premium P&L + Put Premium P&L. Cash Invested = net capital allocated after subtracting premium collected. |
| parameters_json | `{"formula": "total_pnl / cash_invested", "components": ["stock_pnl", "call_pnl", "put_pnl"]}` |
| data_column_mapping | `exit_decisions.pnl_total`, `cycle_layers.invested_capital` |

---

### FORMULA-003 — Portfolio Return

| Field | Value |
|---|---|
| rule_id | FORMULA-003 |
| rule_area | formula |
| rule_type | formula |
| source_section | Appendix E D.4 |
| description | Portfolio Return = (Ending Portfolio Value − Beginning Portfolio Value) / Beginning Portfolio Value. Evaluate quarterly or annually — not week-by-week. |
| parameters_json | `{"formula": "(ending_value - beginning_value) / beginning_value"}` |
| data_column_mapping | Account total value over measurement period |

---

## Summary

### Rule counts by type

| Rule Type | Count |
|---|---|
| hard_gate | 8 |
| hard_rule | 16 |
| soft_gate | 2 |
| guideline | 7 |
| optional_overlay | 7 |
| formula | 3 |
| **Total** | **43** |

### Rule counts by area

| Area | Count |
|---|---|
| stock_selection | 8 |
| earnings | 4 |
| strike_selection | 4 |
| capital | 6 |
| cycle | 7 |
| exit | 8 |
| market_environment | 4 |
| formula | 3 |
| **Total** | **43** |

### Phase 2 loading note

`rule_catalog.py` → `load_rule_catalog()` should read this file and seed all 43 rows into `strategy_rule_catalog`. The `rule_id` column is the primary key. `parameters_json` is stored as JSON text. No gate in `entry_engine.py` or `exit_engine.py` may hard-code a numeric threshold — it must call `get_rule(rule_id)` and read the threshold from `parameters_json`.

### Key design decisions confirmed by Master Document

1. **Score-based decisions are wrong.** The strategy is gate-based: hard gates block entry; soft gates flag. No invented `strategy_score += 2.0`.
2. **Entry timing is Monday, not weekend batch.** Decisions are made Friday→Monday; execution is Monday morning post-open.
3. **OS workbook provides live prices for Gate confirmation.** Newsletter defines thesis/strikes; OS workbook confirms live credit at those strikes on entry day.
4. **Market environment overlay is OPTIONAL.** The core strategy works without it. The hybrid score adjusts position SIZE only, never the rules.
5. **Earnings rules have zero exceptions.** Even a profitable position mid-cycle is closed if earnings slip inside the window.
6. **Extreme drop rules are OPTIONAL.** Not in backtested or live performance data. Reduces tail risk at cost of long-term returns.
7. **2-consecutive-week confirmation rule is already implemented** in `decisions.py` — keep it.
