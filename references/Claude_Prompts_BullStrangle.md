# Claude Prompts For BullStrangle

Date: 2026-04-23  
Updated: 2026-04-26 (added prompts 16–30 for new market intelligence, watchlist, and report tools)  
Audience: Claude Desktop operator

Use these prompts after the BullStrangle MCP server is configured in Claude Desktop.

## General Notes

- Replace newsletter dates when needed.
- Use absolute dates, not relative wording.
- Tell Claude to use the BullStrangle MCP tools.
- Ask for concise output when you want action-first summaries.

## 1. Inspect Newsletter

```text
Use the BullStrangle MCP tools and show me the ingested newsletter for 2026-04-24. Summarize the market environment, short list, and watchlist highlights.
```

## 2. Generate OS Workbook

```text
Use the BullStrangle MCP tools to generate the Option Samurai workbook for newsletter date 2026-04-24 and tell me the output file path plus the selector values being used.
```

## 3. Validate Refreshed Upload Before Ingest

```text
Use the BullStrangle MCP workflow context and tell me the exact next command I should run to ingest the refreshed workbook for newsletter date 2026-04-24 using trading date 2026-04-23. Assume the refreshed file is under data\os_uploads.
```

## 4. Ingest OS Workbook And Summarize

```text
Use the BullStrangle MCP tools to ingest the refreshed OS workbook at data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx for trading date 2026-04-23, then summarize the returned run id and ingestion status.
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

## 8. Weekend Decisions

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 with decision date 2026-04-23. Summarize preferred actions, Bull Strangle approvals, DCA approvals, and the main watch or skip reasons.
```

## 9. Focus On Bull Strangle Only

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and show me only the Bull Strangle APPROVE names ranked by priority with score, selected account, and reason.
```

## 10. Focus On DCA Only

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and show me only the DCA APPROVE names with selected account, account shares, shares to 100, and reason.
```

## 11. Explain One Symbol

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and explain symbol NTAP in plain English. Include selected action, strategy score, rule passes, rule fails, and the final Bull Strangle and DCA outcomes.
```

## 12. Compare Symbols

```text
Use the BullStrangle MCP tools to generate weekend decisions for newsletter date 2026-04-24 and compare NTAP, IBIT, SHLD, and IMVT. Explain why each one landed in Bull Strangle, DCA, Watch, or Skip.
```

## 13. Audit The Dry Run

```text
Use the BullStrangle MCP tools to audit the current dry run for newsletter date 2026-04-24. Tell me what has been ingested, what reports exist logically, and what is still missing before I should trust the weekend decisions.
```

## 14. Ask For Commands Only

```text
Using the BullStrangle workflow, give me only the next three PowerShell commands to run for the 2026-04-24 newsletter after I save the refreshed workbook in data\os_uploads.
```

## 15. Ask For A Weekend Operator Summary

```text
Use the BullStrangle MCP tools to generate the weekend decision summary for newsletter date 2026-04-24 and write it like an operator handoff: what is approved now, what is DCA only, what is watch-only, and what still needs review.
```

---

## Market Intelligence Prompts *(added 2026-04-26)*

## 16. Check Current Deployment Status

```text
Use the BullStrangle MCP tools to check whether deployment is currently approved. Show the per-criterion breakdown (hybrid score, S&P vs 200-DMA, VIX, breadth), consecutive weeks met, and the recommended action.
```

## 17. Get Market Environment Snapshot

```text
Use the BullStrangle MCP tools to get the current market environment. Show hybrid score, market status, investment percent, VIX, breadth, S&P vs 200-DMA, scaling phase, and recommended position count.
```

## 18. Review Market History

```text
Use the BullStrangle MCP tools to show the last 8 weeks of market environment history. For each week show: date, hybrid score, market status, deployment approved, and consecutive weeks met.
```

## 19. Get Scaling Guidance

```text
Use the BullStrangle MCP tools to get scaling guidance for this week. Explain what scaling phase we are in, how many positions are recommended, and what that means for new deployments.
```

## 20. Check Active Cycles

```text
Use the BullStrangle MCP tools to show all active position cycles (newsletters with unexpired target expirations). For each cycle show the newsletter date, expiration date, days remaining, and market status. Flag any expiring within 7 days.
```

---

## Watchlist & Symbol Prompts *(added 2026-04-26)*

## 21. Get Full Watchlist

```text
Use the BullStrangle MCP tools to get the full watchlist for newsletter date 2026-04-24. Show symbol, price, IV, sector, strikes, bull strangle return %, and flag any WL Favorites.
```

## 22. Get DCA Candidates

```text
Use the BullStrangle MCP tools to get the DCA candidates for newsletter date 2026-04-24. Show rank, symbol, portfolio type, price, IV, and sector. Separate large-portfolio and small-portfolio lists.
```

## 23. Get Eligible Symbols (Approved Only)

```text
Use the BullStrangle MCP tools to get the symbols approved for bull strangle deployment from newsletter date 2026-04-24. Show rank, symbol, live credit, price deviation, selected account, shares held, and shares to 100.
```

## 24. Get Watch List Symbols

```text
Use the BullStrangle MCP tools to get all symbols on WATCH (not yet approved) for newsletter date 2026-04-24. For each, explain the strategy score, band, and what would need to change for it to move to APPROVE.
```

## 25. Deep Dive on WL Favorites

```text
Use the BullStrangle MCP tools to get the WL Favorites deep analysis for newsletter date 2026-04-24. For each favorite, summarize Darren's technical assessment, the proposed trade structure (strikes, premiums, total investment, max gain %), and key risk factors.
```

## 26. Explain One WL Favorite

```text
Use the BullStrangle MCP tools to get the WL Favorites deep analysis for newsletter date 2026-04-24, specifically for symbol NEE. Explain the proposed trade in plain English, including the total investment required, what max gain looks like, and the main risks.
```

## 27. Search Newsletter Commentary

```text
Use the BullStrangle MCP tools to search the newsletter commentary for "VIX" and show the top 5 matching sections with newsletter date, section name, and the relevant snippet.
```

## 28. Search For A Market Theme

```text
Use the BullStrangle MCP tools to search newsletter commentary for "breadth" and summarize how Darren has discussed market breadth across the last several newsletters. Note any trend or change in tone.
```

---

## Report Generation Prompts *(added 2026-04-26)*

## 29. Generate Sunday Action Plan

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24. Show the full report including market environment status, re-entry criteria table, DCA candidates, strangle eligibility summary, watchlist analysis, WL Favorites deep dives, action items for this week and next, and key reminders.
```

## 30. Generate Daily Brief

```text
Use the BullStrangle MCP tools to generate today's daily brief. Show the current market environment status, all active position cycles with days to expiration, and any alerts I should act on today.
```

## 31. Generate And Save Action Plan

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date 2026-04-24 and save it to outputs\reports\2026-04-24\action_plan.md. Confirm the output path when done.
```

## 32. Review Previously Generated Reports

```text
Use the BullStrangle MCP tools to list all generated reports. Show report id, type, newsletter date, and when it was generated. Then retrieve the most recent weekly action plan and summarize the key action items from it.
```

## 33. Full Sunday Workflow In One Prompt

```text
Use the BullStrangle MCP tools to run the full Sunday workflow for newsletter date 2026-04-24:
1. Check deployment approval status
2. Get the watchlist and DCA candidates
3. Get eligible symbols (APPROVE)
4. Get WL Favorites deep analysis
5. Generate the weekly action plan
Summarize each step and end with the complete action plan report.
```

## 34. Morning Standup Brief

```text
Use the BullStrangle MCP tools to give me my morning trading standup. Check deployment approval, show active cycles with days to expiration, flag any cycles expiring this week, and tell me if there are any approved symbols from the latest decision run.
```
