# Claude Prompts For BullStrangle

Date: 2026-04-23
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
