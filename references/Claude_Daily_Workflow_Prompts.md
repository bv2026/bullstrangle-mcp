# Claude Daily Workflow Prompts For BullStrangle

Date: 2026-05-04
Audience: Claude Desktop operator

Use this short guide for the normal BullStrangle daily workflow. The full prompt library still exists in `references/Claude_Prompts_BullStrangle.md`, but this file is the simpler daily cockpit.

## Fill These In First

Before copying a prompt, replace the placeholders:

- `<NEWSLETTER_DATE>`: Friday newsletter date, for example `2026-05-01`
- `<TRADING_DATE>`: today's trading date, for example `2026-05-04`
- `<NEWSLETTER_PDF>`: saved newsletter PDF path, for example `data\newsletters\newsletter.pdf`

Optional copy/paste context block:

```text
Context:
NEWSLETTER_DATE = <NEWSLETTER_DATE>
TRADING_DATE = <TRADING_DATE>
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

## 4. What Changed Since Last OS Run

Use this after at least two OS runs exist for the same newsletter week.

```text
Use the BullStrangle MCP tools to compare the latest OS run against the prior OS run for newsletter date <NEWSLETTER_DATE>.

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
- symbols with the largest total credit changes
- symbols that moved into or out of any warning/deviation bucket
- any missing or invalid symbols in either run

If the tool does not provide a direct comparison tool, use the available OS report/aggregation tool results for the latest and prior runs only. If there are fewer than two runs for the newsletter, say NOT ENOUGH RUNS and stop.
If the tool fails, say TOOL FAILED and stop.
If any provenance field is missing, say TOOL RESULT INCOMPLETE and stop.
Do not infer prior run values, symbol changes, or deviation changes.
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
4. Run Prompt 4: What Changed Since Last OS Run when at least two runs exist.
5. Run Prompt 5: Morning Daily Brief.
6. If positions are near expiration or alerts appear, run Prompt 6: Exit Monitoring Only.
7. Run Prompt 7: Market Intelligence Brief when you want the market/deployment context.
8. At week review time, run Prompt 3: Weekly OS Aggregation.

