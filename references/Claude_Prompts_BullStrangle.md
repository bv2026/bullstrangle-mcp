# Claude Prompts For BullStrangle

Date: 2026-04-26
Updated: 2026-04-27 (added prompts 35–55 for gate engine, exit monitoring, backtest, and May cycle monitoring; added prompts 56–63 for workflow commands and Phase 7 reports; added prompt 64 for tool-explicit WL Favorites; updated prompts 15–16 to name get_deep_analysis explicitly; full ambiguity and consistency pass — fixed prompts 1, 3, 20–23, 27, 28, 49, 50, 51, 54, 55)
Audience: Claude Desktop operator

Use these prompts after the BullStrangle MCP server is configured in Claude Desktop.

## General Notes

- Replace newsletter dates and symbol names when needed.
- **All dates in the prompts below (e.g. `2026-04-24`, `2026-04-28`) are examples — replace with the current newsletter date and trading date before use.**
- Use absolute dates, not relative wording ("2026-04-24" not "last Friday").
- Tell Claude to use the BullStrangle MCP tools.
- Ask for concise output when you want action-first summaries.
- If Claude Desktop is unavailable, use the CLI fallback commands in `references/BullStrangle_Usage_Guide.md`.
- **Tool specificity matters:** For WL Favorites narrative analysis (Darren's technical write-up, trade cost table, scenario returns), you **must** explicitly say "use the `get_deep_analysis` tool" — otherwise Claude may call `get_newsletter_by_date` or `get_watchlist`, which return only structured watchlist fields, not the narrative. This was a confirmed failure mode on 2026-04-27.
- **v1 vs v3 engine:** Prompts 20–23 use the legacy v1 decision engine (`generate_weekend_decisions`). For actual trading decisions use the v3 gate engine prompts (32–37). Do not mix the two.

---

## Newsletter & Ingestion

## 1. Inspect Newsletter

> ⚠️ **Tool note:** Use `get_newsletter_by_date` for the newsletter summary. Do not use `get_watchlist` alone — it lacks the market environment and short list sections.

```text
Use the BullStrangle MCP tools — call `get_newsletter_by_date` for date 2026-04-24 — and show me the ingested newsletter. Summarize the market environment, short list, and watchlist highlights.
```

## 2. Generate OS Workbook

```text
Use the BullStrangle MCP tools to generate the Option Samurai workbook for newsletter date 2026-04-24 and tell me the output file path plus the selector values being used.
```

## 3. Validate Refreshed Upload Before Ingest

> ⚠️ **Superseded by Prompt 57.** Phase W added `daily-ingest` as the preferred ingest command; use Prompt 57 instead. This prompt asks Claude for a CLI command rather than calling an MCP tool, which is inconsistent with the rest of the workflow. Kept here for reference only.

```text
Use the BullStrangle MCP workflow context and tell me the exact next command I should run to ingest the refreshed workbook for newsletter date 2026-04-24 using trading date 2026-04-28. Assume the refreshed file is under data\os_uploads.
```

## 4. Ingest OS Workbook And Summarize

```text
Use the BullStrangle MCP tools to ingest the refreshed OS workbook at data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx for trading date 2026-04-28, then summarize the returned run id and ingestion status.
```

## 5. Daily OS Report

```text
Use the BullStrangle MCP tools to report the latest OS run for newsletter date 2026-04-24 and give me the most important missing values, largest price deviations, and largest credit deviations.
```

## 6. Weekly Aggregation

```text
Use the BullStrangle MCP tools to aggregate the OS week for newsletter date 2026-04-24 and give me a concise summary of invalid symbols, top price deviations, and top credit deviations.
```

## 7. Ingest Positions

```text
Use the BullStrangle MCP tools to ingest positions from data\positions\positions.csv and summarize account counts, symbol counts, and which symbols are already stock-backed Bull Strangle ready in one account.
```

---

## Market Environment

## 8. Check Current Deployment Status

```text
Use the BullStrangle MCP tools to check whether deployment is currently approved. Show the per-criterion breakdown (hybrid score, S&P vs 200-DMA, VIX, breadth), consecutive weeks met, and the recommended action.
```

## 9. Get Market Environment Snapshot

```text
Use the BullStrangle MCP tools to get the current market environment. Show hybrid score, market status, investment percent, VIX, breadth, S&P vs 200-DMA, scaling phase, and recommended position count.
```

## 10. Review Market History

```text
Use the BullStrangle MCP tools to show the last 8 weeks of market environment history. For each week show: date, hybrid score, market status, deployment approved, and consecutive weeks met.
```

## 11. Get Scaling Guidance

```text
Use the BullStrangle MCP tools to get scaling guidance for this week. Explain what scaling phase we are in, how many positions are recommended, and what that means for new deployments.
```

---

## Watchlist & Symbols

## 12. Get Full Watchlist

```text
Use the BullStrangle MCP tools to get the full watchlist for newsletter date 2026-04-24. Show symbol, price, IV, sector, strikes, bull strangle return %, and flag any WL Favorites.
```

## 13. Get DCA Candidates

```text
Use the BullStrangle MCP tools to get the DCA candidates for newsletter date 2026-04-24. Show rank, symbol, portfolio type, price, IV, and sector. Separate large-portfolio and small-portfolio lists.
```

## 14. Get Eligible Symbols (Approved Only)

```text
Use the BullStrangle MCP tools to get the symbols approved for bull strangle deployment from newsletter date 2026-04-24. Show rank, symbol, live credit, price deviation, selected account, shares held, and shares to 100.
```

## 15. Deep Dive on WL Favorites

> ⚠️ **Tool note:** Claude must call `get_deep_analysis` for this prompt. If it calls `get_newsletter_by_date` or `get_watchlist` instead, it will not have Darren's narrative and will hallucinate a response. Say "using the `get_deep_analysis` tool" explicitly.

```text
Use the BullStrangle MCP tools — specifically the `get_deep_analysis` tool — to get the WL Favorites deep analysis for newsletter date 2026-04-24. For each favorite, summarize Darren's technical assessment, the proposed trade structure (strikes, premiums, total investment, max gain %), and key risk factors.
```

## 16. Explain One WL Favorite

> ⚠️ **Tool note:** Same as Prompt 15 — must use `get_deep_analysis`, not `get_newsletter_by_date`.

```text
Use the BullStrangle MCP tools — specifically the `get_deep_analysis` tool — to get the WL Favorites deep analysis for newsletter date 2026-04-24 for symbol NEE only. Explain the proposed trade in plain English, including the total investment required, what max gain looks like, and the main risks.
```

## 17. Search Newsletter Commentary

```text
Use the BullStrangle MCP tools to search the newsletter commentary for "VIX" and show the top 5 matching sections with newsletter date, section name, and the relevant snippet.
```

## 18. Search For A Market Theme

```text
Use the BullStrangle MCP tools to search newsletter commentary for "breadth" and summarize how Darren has discussed market breadth across the last several newsletters. Note any trend or change in tone.
```

## 19. Symbol History

```text
Use the BullStrangle MCP tools to get symbol history for NTAP for newsletter date 2026-04-24. Tell me whether it is new, when it first appeared, and which prior newsletters included it.
```

---

## Weekend Decisions (v1 Legacy Engine)

> ⚠️ **LEGACY — Do not use for live trading decisions.** Prompts 20–23 call `generate_weekend_decisions`, which is the v1 scoring engine (deprecated). The output uses a different scoring model than the v3 gate engine and is no longer the source of truth for deployment decisions. **For actual entry decisions, use the Gate Validation prompts (32–37).** These prompts remain here for historical comparison and backtest context only.

## 20. Weekend Decisions Summary

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 with decision date 2026-04-27. Summarize preferred actions, Bull Strangle approvals, DCA approvals, and the main watch or skip reasons.
```

## 21. Focus On Bull Strangle Only

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and show me only the Bull Strangle APPROVE names ranked by priority with score, selected account, and reason.
```

## 22. Focus On DCA Only

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and show me only the DCA APPROVE names with selected account, account shares, shares to 100, and reason.
```

## 23. Explain One Symbol

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and explain symbol NTAP in plain English. Include selected action, strategy score, rule passes, rule fails, and the final Bull Strangle and DCA outcomes.
```

---

## Report Generation

## 24. Generate Sunday Action Plan

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24. Show the full report including market environment status, re-entry criteria table, DCA candidates, strangle eligibility summary, watchlist analysis, WL Favorites deep dives, action items for this week and next, and key reminders.
```

## 25. Generate Daily Brief

```text
Use the BullStrangle MCP tools to generate today's daily brief. Show the current market environment status, all active position cycles with days to expiration, and any alerts I should act on today.
```

## 26. Generate And Save Action Plan

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24 and save it to outputs\reports\2026-04-24\action_plan.md. Confirm the output path when done.
```

## 27. Morning Standup Brief

```text
Use the BullStrangle MCP tools to give me my morning trading standup. Check deployment approval, show active cycles with days to expiration, flag any cycles expiring this week, and tell me if there are any symbols that passed all 9 gates from the latest gate validation run (v3 entry engine — use list_entry_decisions, not generate_weekend_decisions).
```

## 28. Full Sunday Workflow In One Prompt

```text
Use the BullStrangle MCP tools to run the full Sunday workflow for newsletter date 2026-04-24:
1. Check deployment approval status
2. Get the watchlist and DCA candidates
3. Get eligible symbols (APPROVE)
4. Get WL Favorites deep analysis — use the `get_deep_analysis` tool for date 2026-04-24; do not use get_watchlist or get_newsletter_by_date for this step
5. Generate the weekly action plan
Summarize each step and end with the complete action plan report.
```

---

## Rule Catalog

## 29. List All Strategy Gates

```text
Use the BullStrangle MCP tools to list all hard gate rules from the rule catalog. For each gate show the rule_id, description, and key threshold parameters.
```

## 30. Explain A Specific Rule

```text
Use the BullStrangle MCP tools to get the full detail for rule GATE-SS-005 (earnings clear days). Explain what it means, what the threshold is, and what data is checked.
```

## 31. List Exit Rules

```text
Use the BullStrangle MCP tools to list all rules in the exit area of the rule catalog. For each rule show the rule_id, type, description, and key parameters like trigger thresholds and recommended actions.
```

---

## Gate Validation (Entry Engine — v3)

## 32. Validate This Week's Newsletter

```text
Use the BullStrangle MCP tools to evaluate all 9 entry gates for every watchlist symbol in newsletter 2026-04-24. Show which symbols passed all gates, which failed and at which gate, and what percentage align with Darren's Short List.
```

## 33. Validate One Symbol

```text
Use the BullStrangle MCP tools to evaluate the 9 entry gates for symbol NTAP against newsletter 2026-04-24. Show each gate result — gate number, rule cited, actual value, threshold, pass/fail, and reason if failed. End with the overall decision.
```

## 34. Gate Report (Full — Save To File)

```text
Use the BullStrangle MCP tools to generate the full gate validation report for newsletter date 2026-04-24 and save it to outputs\reports\gate_report_2026-04-24.md. Include gate pass/fail table, alignment with Short List, and key observations.
```

## 35. Explain Why A Symbol Was Rejected

```text
Use the BullStrangle MCP tools to evaluate entry gates for symbol AAL against newsletter 2026-04-24 and explain in plain English exactly why it did or did not pass. Which gate failed, what was the actual value, what was the threshold, and what would need to change for it to pass?
```

## 36. Gate Alignment Summary Across All Newsletters

```text
Use the BullStrangle MCP tools to validate all ingested newsletters against the 9 entry gates. For each week show: deployment status, total symbols evaluated, gate pass rate, alignment with Darren's Short List. Identify any weeks where gate logic diverged significantly from the Short List.
```

## 37. List Persisted Gate Decisions

```text
Use the BullStrangle MCP tools to list the last 30 entry decisions. Show newsletter date, symbol, all-gates-pass status, first failing gate, decision type, and whether the symbol was on the Short List.
```

---

## Exit Monitoring (Exit Engine — v3)

## 38. Morning Exit Check (With Live Prices)

```text
Use the BullStrangle MCP tools to generate today's exit monitoring report for the small portfolio. Auto-resolve any expired positions first, then show all open positions grouped by urgency: IMMEDIATE action needed, review this week, and hold. For each position show: symbol, expiration, DTE, live price, % change from entry, nearest strike distance, and recommended action.
```

## 39. Exit Report — Offline Mode

```text
Use the BullStrangle MCP tools to generate the exit monitoring report for the small portfolio without fetching live prices. Show all active positions, their entry data, strikes, and whether any expiry or earnings triggers are active.
```

## 40. Exit Report For Large Portfolio

```text
Use the BullStrangle MCP tools to generate the exit monitoring report for the large portfolio with live prices. Highlight any positions that need attention this week (DTE ≤ 7, stock near a strike, or earnings during holding period).
```

## 41. Explain One Position's Exit Status

```text
Use the BullStrangle MCP tools to evaluate exit triggers for the CELH position in the small portfolio. Explain each trigger that was checked, what the actual value was, what the threshold was, and what action is recommended.
```

## 42. Auto-Resolve Expired Positions

```text
Use the BullStrangle MCP tools to auto-resolve any expired positions for the small portfolio. Show which newsletter weeks were processed, which positions were closed, their final outcome (BOTH_OTM / CALL_ASSIGNED / PUT_ASSIGNED), and the P&L for each.
```

---

## Portfolio Performance & Backtest

## 43. Small Portfolio Performance Summary

```text
Use the BullStrangle MCP tools to get the portfolio performance for the small portfolio (Darren's top picks). Show the week-by-week equity curve, cumulative P&L, win rate, max drawdown, and overall return. Note any open positions not yet in the curve.
```

## 44. Large Portfolio Performance Summary

```text
Use the BullStrangle MCP tools to get the portfolio performance for the large portfolio (all 10 ranks). Show the week-by-week equity curve, cumulative P&L, win rate, max drawdown, and overall return. Compare key metrics to the small portfolio.
```

## 45. Compare Small vs Large Portfolio

```text
Use the BullStrangle MCP tools to get portfolio performance for both the small and large portfolios. Present them side by side: total P&L, overall return %, win rate, max drawdown %, and best/worst week for each. Interpret the difference — what does this say about Darren's curation quality?
```

## 46. Full Backtest Report

```text
Use the BullStrangle MCP tools to generate the full backtest report for the small portfolio. Include the week-by-week position table with symbols, strikes, close prices, outcomes, and P&L, followed by the equity curve and summary statistics.
```

## 47. Best And Worst Trades

```text
Use the BullStrangle MCP tools to generate the backtest report for the small portfolio and identify the best and worst individual trades. For each, explain: what the setup was, what outcome occurred (BOTH_OTM / CALL_ASSIGNED / PUT_ASSIGNED), and what drove the P&L result.
```

## 48. Open Positions Capital At Risk

```text
Use the BullStrangle MCP tools to get portfolio performance for the small portfolio and focus on the open positions section. Show each open newsletter week, its expiration date, number of positions, and total capital at risk. Are any of these expiring in the next two weeks?
```

---

## May Cycle Monitoring (Combined Workflows)

## 49. Monday Morning Full Check

> ℹ️ **Phase W update:** This prompt predates the `daily-ingest` and `generate_daily_brief` workflow commands. For the current preferred Monday morning routine, use **Prompt 57** (daily-ingest) and **Prompt 59** (daily brief). This prompt remains useful for a manual override when you want to drive each step explicitly.

```text
Use the BullStrangle MCP tools to run my Monday morning monitoring routine:
1. Auto-resolve any expired positions for the small portfolio
2. Generate the exit monitoring report for the small portfolio with live prices
3. Show portfolio performance summary (equity curve through today)
Flag anything that needs action today and anything expiring this week.
```

## 50. Post-Newsletter Sunday Workflow

> ℹ️ **Phase W update:** This prompt predates `weekend-setup` and `generate_daily_brief`. The current full Sunday workflow is **Prompt 63**, which includes `weekend-setup` as the first step. This prompt remains valid as a gate-and-performance-focused variant if you've already run weekend-setup separately.

```text
Use the BullStrangle MCP tools to run the full Sunday workflow for newsletter date 2026-04-24:
1. Check deployment approval and market environment
2. Evaluate all 9 entry gates for this week's watchlist
3. Show gate alignment with the Short List
4. Generate the gate validation report
5. Check exit status for all open positions
6. Show current portfolio performance for small and large portfolios
Summarize each step and end with the key actions for the week.
```

## 51. End-Of-Week Performance Digest

```text
Use the BullStrangle MCP tools to give me an end-of-week digest for the current expiration cycle:
1. Auto-resolve any newly expired positions
2. Show updated portfolio performance for the small portfolio (equity curve, P&L, win rate)
3. List any positions still open and their expiration dates
4. Note whether this week's resolved positions were wins or losses and why
```

## 52. Strategy Validation Check

```text
Use the BullStrangle MCP tools to assess how well the gate engine is tracking Darren's actual selections:
1. Validate all newsletters with the entry engine
2. Show alignment % between gate decisions and Short List for each deployed week
3. Identify which gates are causing the most rejections
4. Summarize whether the strategy logic is consistent with Darren's curation
```

## 53. Full Portfolio Reconciliation

```text
Use the BullStrangle MCP tools to do a complete portfolio reconciliation for the small portfolio:
1. Generate the backtest report
2. List all open positions with live prices and exit trigger status
3. Show equity curve and drawdown
4. Flag any positions that need action this week
Present as a one-page summary suitable for a weekly review.
```

---

## Utility Prompts

## 54. Audit What Has Been Ingested

```text
Use the BullStrangle MCP tools to audit what has been ingested. List all newsletters with their dates, whether OS workbooks have been run for each, and whether positions have been ingested. Tell me what is missing before I should trust the gate decisions (v3 entry engine).
```

## 55. Ask For CLI Commands Only

> ℹ️ **Phase W update:** The preferred Monday morning CLI commands are now `weekend-setup` (Sunday) and `daily-ingest` (Monday). The commands below are the manual equivalents if you need to run steps individually. See `references/BullStrangle_Usage_Guide.md` for the full CLI reference.

```text
Using the BullStrangle workflow, give me only the PowerShell CLI commands I need to run today's Monday morning routine: run daily-ingest for today's trading date, auto-resolve expired positions, check exit status, and see the current portfolio performance. Use the small portfolio. No explanations — just the exact commands.
```

---

## Workflow Commands (Phase W)

## 56. Sunday Setup — New Newsletter

```text
Use the BullStrangle MCP tools to run the Sunday setup for newsletter date 2026-04-24. The PDF is at data\newsletters\newsletter.pdf. Run weekend-setup, confirm the workbook was generated and copied to data\os_uploads, and tell me the output path so I know what to open in Excel.
```

## 57. Daily Ingest + Report

```text
Use the BullStrangle MCP tools to run the daily ingest for newsletter date 2026-04-24 with trading date 2026-04-28. Find the refreshed workbook in data\os_uploads, ingest it, and generate the OS run report. Give me the run_id, row count, and the report file path.
```

## 58. Recover From Stale Workbook

```text
Use the BullStrangle MCP tools to ingest the OS workbook at data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx for trading date 2026-04-28 with regenerate-if-stale enabled. Explain whether the workbook was stale, whether a fresh one was generated, and what run_id was produced.
```

---

## Daily Brief & Weekly Plan (Phase 7)

## 59. Morning Daily Brief

```text
Use the BullStrangle MCP tools to generate today's daily brief. Show:
1. Any exit alerts that need action today (CLOSE_IMMEDIATELY, EXIT_MONDAY, REVIEW)
2. All open positions with days to expiration
3. Gate status for the latest newsletter week
Start with the most urgent items.
```

## 60. Daily Brief — Exits Only

```text
Use the BullStrangle MCP tools to generate the daily brief and focus only on exit alerts. For each alert show: symbol, expiration, DTE, recommended action, and the trigger that fired. Sort by urgency: CLOSE_IMMEDIATELY first, then EXIT_MONDAY, then REVIEW.
```

## 61. Weekly Action Plan — Gate Summary Focus

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24 and focus on the gate validation summary. Show: how many symbols passed all gates, how many are on WATCH, how many were skipped. Then show the Short List alignment percentage and which gate is causing the most rejections.
```

## 62. Weekly Action Plan — Active Positions Focus

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24 and focus on the active positions section. For each open position show: symbol, expiration, days to expiration, call strike, put strike, credit received, and capital at risk. Flag any positions expiring in the next 10 days.
```

## 63. Full Sunday Workflow — Action Plan + Gate Report + Exit Check

```text
Use the BullStrangle MCP tools to run the complete Sunday workflow for newsletter date 2026-04-24:
1. Run weekend-setup to confirm the workbook is ready
2. Generate the gate report and show the Short List alignment summary
3. Generate the weekly action plan — include gate summary, active positions, and DCA candidates
4. Generate the exit report for the small portfolio and flag anything needing attention this week
End with a priority-ordered action list for Monday.
```

---

## Tool-Explicit Prompts (Disambiguation Variants)

These prompts are identical in intent to earlier prompts but name the MCP tool explicitly. Use these when Claude has previously called the wrong tool or you want to prevent ambiguity.

## 64. WL Favorites Deep Analysis — Tool Explicit

> **Why this exists:** On 2026-04-27 Claude called `get_newsletter_by_date` instead of `get_deep_analysis` for a WL Favorites request, then reported that "the deep analysis is not included in the structured data" — which was false. The data was there; the wrong tool was called. This prompt prevents that by naming the tool.

```text
Use the BullStrangle MCP tools — call the `get_deep_analysis` tool — to retrieve Darren's WL Favorites deep analysis for newsletter date 2026-04-24. Do not call get_newsletter_by_date or get_watchlist for this request; those tools do not contain the narrative analysis.

For each WL Favorite returned, provide:
1. Darren's technical assessment (chart pattern, momentum, key levels, catalyst)
2. Proposed trade structure: legs, strikes, premiums, total investment, max gain $, max gain %
3. Scenario return table if included (price at expiration vs. P&L)
4. Key risk factors (assignment levels, downside, earnings, sector risk)
5. Overall conviction signal: is this a confirmed breakout or a conditional/speculative setup?
```
