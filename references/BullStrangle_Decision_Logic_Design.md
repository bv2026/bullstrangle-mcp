# BullStrangle Decision Logic Design

Date: 2026-04-23
Status: design target for next implementation pass

## Core Principle

Bull Strangle is the primary strategy decision.

DCA is not a mandatory first step and is not a universal prerequisite for Bull Strangle entry.

Instead, each weekend decision should:

1. score the setup
2. choose one preferred action

## Shared Strategy Score

Every symbol should receive a shared `strategy_score` based on:

- market regime and deployment state
- newsletter/watchlist quality
- short-list/favorite status
- live option premium quality
- OS data validity
- weekly price/credit deviation profile
- price attractiveness relative to the intended strike structure

Output:

- `strategy_score`
- `strategy_band`
- rule pass/fail detail

## Action Branching

After scoring, branch to one preferred action:

- `BULL_STRANGLE`
- `DCA`
- `WATCH`
- `SKIP`

Interpretation:

- `BULL_STRANGLE`: direct strategy entry is preferred now
- `DCA`: setup still scores well, but accumulation is the preferred entry path
- `WATCH`: setup is interesting but not ready
- `SKIP`: setup is weak or invalid

## Bull Strangle Intent

Bull Strangle should be chosen when:

- strategy score is strong
- market and strategy gates are satisfied
- premium quality is acceptable
- direct strategy entry is preferred
- one execution account can be selected

Important:

- Bull Strangle should not be rejected solely because the stock is not already built through DCA.
- A stock-backed Bull Strangle implementation may require `100` shares in one account, but that is an implementation path, not the universal approval rule.

## DCA Intent

DCA should be chosen when:

- strategy score is still good
- accumulation is preferred over immediate Bull Strangle entry
- one target account can be selected
- the live price supports the later Bull Strangle structure

DCA should explicitly track:

- `selected_account`
- `current_account_shares`
- `shares_to_100`
- `current_account_avg_cost`
- `live_price`
- strike context

## Account Rule

- A DCA or Bull Strangle action must map to exactly one account.
- Exposure can be viewed at consolidated symbol level.
- Execution eligibility must be account-specific.
- `100` shares split across multiple accounts does not satisfy a one-account stock-backed requirement.

## Recommended Data Outputs

Every final weekend decision row should include:

- `strategy_score`
- `selected_action`
- `selected_account`
- `rules_passed_json`
- `rules_failed_json`
- `source_snapshot_json`
- reason text

## Implementation Impact

The current v1 decision code should be revised so that:

- Bull Strangle is no longer globally gated by one-account 100-share ownership
- DCA is no longer limited to already-held symbols
- the engine computes shared score first, then chooses action type
