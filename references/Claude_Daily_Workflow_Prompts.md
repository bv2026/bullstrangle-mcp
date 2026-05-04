# Claude Daily Workflow Prompts For BullStrangle

Date: 2026-05-04
Audience: Claude Desktop operator

Use this short guide for the normal BullStrangle daily workflow. The full prompt library still exists in `references/Claude_Prompts_BullStrangle.md`, but this file is the simpler daily cockpit.

## Fill These In First

Before copying a prompt, replace the placeholders:

- `<NEWSLETTER_DATE>`: Friday newsletter date, for example `2026-05-01`
- `<TRADING_DATE>`: today's trading date, for example `2026-05-04`
- `<PRIOR_NEWSLETTER_DATE>`: prior Friday newsletter date, for example `2026-04-24`
- `<PRIOR_TRADING_DATE>`: prior cycle trading date, for example `2026-04-28`
- `<NEWSLETTER_PDF>`: saved newsletter PDF path, for example `data\newsletters\newsletter.pdf`

Optional copy/paste context block:

```text
Context:
NEWSLETTER_DATE = <NEWSLETTER_DATE>
TRADING_DATE = <TRADING_DATE>
PRIOR_NEWSLETTER_DATE = <PRIOR_NEWSLETTER_DATE>
PRIOR_TRADING_DATE = <PRIOR_TRADING_DATE>
NEWSLETTER_PDF = <NEWSLETTER_PDF>

Use those values for all placeholders in the prompt below.
```

## Non-Negotiable Guardrail

For OS ingest, daily ingest, OS run reports, weekly OS aggregation, and any report that depends on fresh tool data:

- Claude must use the BullStrangle MCP tools.
- Claude must return receipt/provenance fields from the tool result.
- If the tool fails, Claude must answer `TOOL FAILED` and stop.
- If any required receipt field is missing, Claude must answer `TOOL RESULT INCOMPLETE` and stop.
- Claude must not infer row counts, invent run IDs, invent symbols, or produce narrative-only success summaries.

## 1. Daily Ingest After Excel Refresh

Use this after opening the Option Samurai workbook in Excel, refreshing formulas, and saving the workbook.

```text
Use the BullStrangle MCP tools to run the daily ingest for newsletter date <NEWSLETTER_DATE> with trading date <TRADING_DATE>. Find the refreshed workbook in data\os_uploads, ingest it, and generate the OS run report.

Return only these receipt fields from the tool result:
- run_id
- newsletter_date
- trading_date
- row_count
- status
- report_path

If any field is missing, say TOOL RESULT INCOMPLETE and stop.
If the tool fails, say TOOL FAILED and stop.
Do not infer row counts or invent run ids.
```

## 2. Daily OS Run Report

Use this when you want the latest run quality check and the important deviations.

```text
Use the BullStrangle MCP tools to report the latest OS run for newsletter date <NEWSLETTER_DATE>.

First show the run receipt from the tool result:
- run_id
- newsletter_date
- trading_date
- row_count
- status

Then summarize:
- missing or error rows
- largest price deviations
- largest credit deviations

If the receipt is missing, say TOOL RESULT INCOMPLETE and stop.
If the tool fails, say TOOL FAILED and stop.
Do not infer values.
```

## 3. Weekly OS Aggregation

Use this after at least one OS workbook has been ingested for the week.

```text
Use the BullStrangle MCP tools to aggregate the OS week for newsletter date <NEWSLETTER_DATE>.

First print these provenance fields from the tool result:
- newsletter_id
- newsletter_date
- expiration_date
- run_count
- run_ids
- symbol_count
- valid_symbol_count
- invalid_symbol_count

Then summarize:
- invalid symbols
- top price deviations
- top credit deviations

If the tool fails, say TOOL FAILED and stop.
If any provenance field is missing, say TOOL RESULT INCOMPLETE and stop.
Do not infer symbols, run counts, or deviations.
```

## 4A. Same Newsletter: Compare Trading Dates

Use this after at least two OS runs exist for the same newsletter week.

```text
Use the BullStrangle MCP tools to compare OS runs for the same newsletter date, <NEWSLETTER_DATE>.

Compare:
- latest/current trading date: <TRADING_DATE>
- prior trading date for the same newsletter: the immediately previous OS run for <NEWSLETTER_DATE>

Important: compare only OS runs from the same newsletter date, <NEWSLETTER_DATE>. "Prior run" means the previous run_id for the same newsletter_date, not the prior newsletter week. Do not compare <NEWSLETTER_DATE> against any other newsletter date. If the only available comparison is a different newsletter date, say WRONG COMPARISON and stop.

First print these provenance fields:
- newsletter_date
- latest_run_id
- latest_trading_date
- prior_run_id
- prior_trading_date
- latest_row_count
- prior_row_count
- compared_symbol_count

Then summarize:
- symbols with the largest stock price changes
- symbols with the largest total credit changes, comparing actual total_credit between the two runs
- symbols that moved into or out of any warning/deviation bucket
- any missing or invalid symbols in either run

If the tool does not provide a direct comparison tool, use the available OS report/aggregation tool results for the latest and prior runs only. If there are fewer than two runs for the newsletter, say NOT ENOUGH RUNS and stop.
If the tool fails, say TOOL FAILED and stop.
If any provenance field is missing, say TOOL RESULT INCOMPLETE and stop.
Do not infer prior run values, symbol changes, or deviation changes.
```

## 4B. Cross Newsletter: Compare Current Cycle Vs Prior Cycle

Use this when you want to compare the latest OS run from the current newsletter cycle against a specific OS run from the prior newsletter cycle.

```text
Use the BullStrangle MCP tools to compare these two OS runs:

Current cycle:
- newsletter_date: <NEWSLETTER_DATE>
- trading_date: <TRADING_DATE>

Prior cycle:
- newsletter_date: <PRIOR_NEWSLETTER_DATE>
- trading_date: <PRIOR_TRADING_DATE>

Important: this is a cross-newsletter comparison. Do not substitute the prior run from the same newsletter. Do not choose dates automatically. If either exact newsletter_date + trading_date pair is not found, say RUN NOT FOUND and stop.

First print these provenance fields:
- current_newsletter_date
- current_trading_date
- current_run_id
- current_row_count
- prior_newsletter_date
- prior_trading_date
- prior_run_id
- prior_row_count
- overlapping_symbol_count
- overlapping_symbols
- current_only_symbol_count
- current_only_symbols
- prior_only_symbol_count
- prior_only_symbols

Then summarize:
- overlapping symbols with the largest stock price changes, sorted by absolute percentage change descending
- overlapping symbols with the largest total credit changes, comparing actual total_credit between the two runs and sorted by absolute dollar change descending
- symbols newly added in the current cycle
- symbols dropped from the prior cycle
- warning/deviation bucket changes for overlapping symbols
- run-level missing/error symbols in either exact run
- weekly aggregate invalid symbols only if explicitly requested; keep these separate from run-level missing/error rows

If the tool fails, say TOOL FAILED and stop.
If any provenance field is missing, say TOOL RESULT INCOMPLETE and stop.
Before summarizing, verify that each count exactly matches the number of symbols in its printed list. If any count/list mismatch exists, say SYMBOL SET MISMATCH and stop.
Do not put the same symbol in more than one of these lists: overlapping_symbols, current_only_symbols, prior_only_symbols. If a symbol appears in more than one list, say SYMBOL SET MISMATCH and stop.
Do not derive run-level missing/error status from weekly aggregate invalid-symbol counts. Weekly invalid symbols can reflect missing days across multiple runs and are not the same as missing/error rows in the exact compared run.
Do not infer run ids, row counts, symbol overlap, or changes.
```

## 5. Morning Daily Brief

Use this after daily ingest, or anytime you want the morning monitoring view.

```text
Use the BullStrangle MCP tools to generate today's daily brief.

Start with:
- report date
- latest newsletter date used
- whether there are any urgent exit alerts

Then show:
- CLOSE_IMMEDIATELY alerts
- EXIT_MONDAY alerts
- REVIEW alerts
- active positions with days to expiration
- latest gate status summary

If the tool fails, say TOOL FAILED and stop.
Do not invent active positions or alerts.
Do not mix gate-approved symbols into the open positions list. Keep these as separate sections:
- Open positions: only currently active/open cycle layers.
- Gate-approved symbols: candidates from the latest newsletter that passed all gates but are not necessarily open positions.
```

## 6. Exit Monitoring Only

Use this when you only care about open positions and exit triggers.

```text
Use the BullStrangle MCP tools to generate the exit monitoring report for all ACTIVE positions.

Return:
- report date
- generated timestamp or price-as-of timestamp, if provided by the tool
- active layer count
- alerts grouped by urgency
- symbol
- expiration
- DTE
- recommended action
- trigger that fired

If the tool fails, say TOOL FAILED and stop.
If no active positions exist, say that explicitly.
Do not invent positions or alerts.
Note that live/current prices can change between runs. Do not reuse prices from earlier reports unless the tool explicitly returns them for this run.
```

## 7. Market Intelligence Brief

Use this when you want the market regime and deployment context without a full action plan.

```text
Use the BullStrangle MCP tools to generate a market intelligence brief for the latest newsletter week.

Show:
- current market status
- deployment approval status
- hybrid score
- consecutive weeks met
- VIX
- breadth
- S&P vs 200-DMA
- scaling phase
- recommended position count
- any change from the prior newsletter week

If the tool fails, say TOOL FAILED and stop.
Do not infer market values. Use only MCP tool results.
```

## 8. Sunday Setup For New Newsletter

Use this once a new newsletter PDF has been saved.

```text
Use the BullStrangle MCP tools to run weekend setup for newsletter date <NEWSLETTER_DATE>. The PDF is at <NEWSLETTER_PDF>.

Return only:
- newsletter_id
- newsletter_date
- watchlist_count
- workbook_path
- copied_upload_path
- status

If any field is missing, say TOOL RESULT INCOMPLETE and stop.
If the tool fails, say TOOL FAILED and stop.
Do not infer watchlist count or workbook paths.
```

## 9. Sunday Weekly Action Plan

Use this after weekend setup and gate evaluation are ready.

```text
Use the BullStrangle MCP tools to generate the weekly action plan for newsletter date <NEWSLETTER_DATE>.

Start with:
- newsletter_date
- report_path, if saved
- market status
- deployment approval status

Then summarize:
- gate validation summary
- eligible symbols
- DCA candidates
- WL Favorites
- active positions
- next actions

If the tool fails, say TOOL FAILED and stop.
Do not invent eligible symbols, DCA candidates, or WL Favorites.
```

## Recommended Daily Order

1. Refresh and save Excel workbook.
2. Run Prompt 1: Daily Ingest After Excel Refresh.
3. Run Prompt 2: Daily OS Run Report.
4. Run Prompt 4A for same-newsletter trading-date changes, or Prompt 4B for current cycle vs prior cycle.
5. Run Prompt 5: Morning Daily Brief.
6. If positions are near expiration or alerts appear, run Prompt 6: Exit Monitoring Only.
7. Run Prompt 7: Market Intelligence Brief when you want the market/deployment context.
8. At week review time, run Prompt 3: Weekly OS Aggregation.

