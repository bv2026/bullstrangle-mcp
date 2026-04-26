# BullStrangle Operator Runbook

Date: 2026-04-26
Audience: operator — CLI-first reference for when Claude Desktop is unavailable

This runbook covers two scenarios:
1. **Weekly Monitoring Runbook** — the recurring routine for the May 2026 validation cycle
2. **New Week Runbook** — what to do when a new newsletter arrives

All commands are PowerShell CLI. Run from `C:\work\bullstrangle-mcp`.
If `bullstrangle` entry point is not available, substitute `python -m bullstrangle_mcp.cli`.

---

## Weekly Monitoring Runbook (May 2026 Cycle)

### Monday Morning — ~10 minutes

Run after market opens (or before reviewing anything).

**Step 1 — Auto-resolve expired positions**

Closes any cycle layers whose expiration date has passed, fetches yfinance closing prices, and records final P&L.

```powershell
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type small
```

Expected output: lists which newsletter weeks were processed, which symbols closed, their outcome (BOTH_OTM / CALL_ASSIGNED / PUT_ASSIGNED), and P&L per position.
If no positions expired: "No expired ACTIVE layers found" — this is normal midweek.

**Step 2 — Exit monitoring report**

Reviews all still-open positions for urgency triggers (DTE, strike proximity, earnings, extreme drop).

```powershell
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --output outputs\reports\exit_report_small.md
```

Review the report for:
- `CLOSE_IMMEDIATELY` — act today
- `EXIT_MONDAY` — close at open this week (DTE ≤ 7)
- `REVIEW` — stock near a strike or earnings risk; watch closely
- `HOLD` — no action needed

Offline version (skip live price fetch):

```powershell
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --no-price
```

**Step 3 — Quick performance check**

```powershell
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type small
```

Prints: equity curve by week, cumulative P&L, overall return %, win rate, max drawdown, open positions.

---

### When New Newsletter Arrives (Sunday Night)

Drop the PDF into `data\newsletters\`, then run one command:

```powershell
bullstrangle --db data\bullstrangle.db weekend-setup 2026-04-24 --pdf data\newsletters\newsletter.pdf
```

This does everything in sequence:
1. Ingests the PDF into the newsletter DB
2. Generates the OS Excel workbook → `outputs\workbooks\`
3. Auto-copies the workbook to `data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx`

If the newsletter is already ingested (e.g. you ran `ingest-pdf` separately), omit `--pdf`:

```powershell
bullstrangle --db data\bullstrangle.db weekend-setup 2026-04-24
```

After `weekend-setup` completes, open `data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx` in Excel.

**Step 2 — Evaluate gates (can do now, before OS data)**

```powershell
bullstrangle --db data\bullstrangle.db gate-report 2026-04-24 --output outputs\reports\gate_report_2026-04-24.md
```

**Step 3 — Seed paper-trade positions (if deployment approved)**

Only once per new newsletter week:

```powershell
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type small
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type large
```

---

### Daily (Market Hours, Mon–Fri)

Open `data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx` in Excel, enable the Option Samurai add-in, refresh, save. Then run one command:

```powershell
bullstrangle --db data\bullstrangle.db daily-ingest 2026-04-24 --trading-date 2026-04-28
```

This does everything in sequence:
1. Finds the refreshed workbook in `data\os_uploads\`
2. Ingests it (auto-recovers from stale newsletter_id if needed — no manual fix required)
3. Generates the OS run report → `outputs\reports\os_run_<run_id>_2026-04-28.md`

Output includes `run_id` and `report_path` for reference.

**Manual fallback** (if you need to split the steps):

```powershell
# Step 1 — ingest only
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28

# Step 2 — report only (use run_id from step 1)
bullstrangle --db data\bullstrangle.db report-os-run 8 --output outputs\reports\os_run_8.md

# If you get a stale workbook error, add --regenerate-if-stale:
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28 --regenerate-if-stale
```

---

### Weekend (Saturday / Sunday)

**Step 1 — Aggregate the week's OS runs**

```powershell
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --output outputs\reports\os_week_2026-04-24.md
```

**Step 2 — Full backtest report**

```powershell
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type small --output outputs\reports\backtest_small.md
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type large --output outputs\reports\backtest_large.md
```

**Step 3 — Ingest updated positions**

After exporting from broker:

```powershell
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
```

---

## Full CLI Reference

### Workflow Commands (preferred)

```powershell
# Sunday: ingest PDF + generate workbook in one step
bullstrangle --db data\bullstrangle.db weekend-setup 2026-04-24 --pdf data\newsletters\newsletter.pdf

# Sunday: newsletter already ingested, just regenerate workbook
bullstrangle --db data\bullstrangle.db weekend-setup 2026-04-24

# Daily: ingest refreshed workbook + generate report in one step
bullstrangle --db data\bullstrangle.db daily-ingest 2026-04-24 --trading-date 2026-04-28
```

### Database & Newsletters

```powershell
bullstrangle --db data\bullstrangle.db init-db
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\file.pdf
bullstrangle --db data\bullstrangle.db ingest-pdf data\newsletters\file.pdf --force
bullstrangle --db data\bullstrangle.db ingest-dir data\newsletters
bullstrangle --db data\bullstrangle.db list-newsletters
bullstrangle --db data\bullstrangle.db show-newsletter 2026-04-24
bullstrangle --db data\bullstrangle.db symbol-history NTAP --newsletter-date 2026-04-24
```

### OS Workbook

```powershell
bullstrangle --db data\bullstrangle.db os-selectors 2026-04-24
bullstrangle --db data\bullstrangle.db generate-os-workbook 2026-04-24 --output-dir outputs\workbooks
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28
bullstrangle --db data\bullstrangle.db ingest-os-workbook data\os_uploads\BullStrangle_OS_Live_2026-04-24.xlsx --trading-date 2026-04-28 --regenerate-if-stale
bullstrangle --db data\bullstrangle.db list-os-runs --newsletter-date 2026-04-24
bullstrangle --db data\bullstrangle.db report-os-run 5 --output outputs\reports\os_run_5.md
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24
bullstrangle --db data\bullstrangle.db aggregate-os-week 2026-04-24 --output outputs\reports\os_week_2026-04-24.md
```

### Rule Catalog

```powershell
bullstrangle --db data\bullstrangle.db list-rule-catalog
bullstrangle --db data\bullstrangle.db list-rule-catalog --area exit
bullstrangle --db data\bullstrangle.db list-rule-catalog --type hard_gate
bullstrangle --db data\bullstrangle.db get-rule GATE-SS-001
bullstrangle --db data\bullstrangle.db get-rule EXIT-001
```

### Gate Validation (Entry Engine)

```powershell
bullstrangle --db data\bullstrangle.db evaluate-entry NTAP --newsletter-date 2026-04-24
bullstrangle --db data\bullstrangle.db evaluate-newsletter 2026-04-24
bullstrangle --db data\bullstrangle.db validate-all
bullstrangle --db data\bullstrangle.db gate-report 2026-04-24 --output outputs\reports\gate_report_2026-04-24.md
bullstrangle --db data\bullstrangle.db list-entry-decisions
bullstrangle --db data\bullstrangle.db list-entry-decisions --newsletter-date 2026-04-24
```

### Exit Monitoring

```powershell
bullstrangle --db data\bullstrangle.db evaluate-exit --layer-id 42
bullstrangle --db data\bullstrangle.db evaluate-exit-batch
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --no-price
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type small --output outputs\reports\exit_report_small.md
bullstrangle --db data\bullstrangle.db exit-report --portfolio-type large --output outputs\reports\exit_report_large.md
bullstrangle --db data\bullstrangle.db list-exit-decisions
```

### Position Book & Backtest

```powershell
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type small
bullstrangle --db data\bullstrangle.db seed-cycle-layers 2026-04-24 --portfolio-type large
bullstrangle --db data\bullstrangle.db resolve-outcomes 2026-04-24
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type small
bullstrangle --db data\bullstrangle.db auto-resolve --portfolio-type large
bullstrangle --db data\bullstrangle.db backtest-all --portfolio-type small
bullstrangle --db data\bullstrangle.db backtest-all --portfolio-type large
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type small
bullstrangle --db data\bullstrangle.db portfolio-performance --portfolio-type large
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type small --output outputs\reports\backtest_small.md
bullstrangle --db data\bullstrangle.db backtest-report --portfolio-type large --output outputs\reports\backtest_large.md
```

### Positions & Weekend Decisions

```powershell
bullstrangle --db data\bullstrangle.db ingest-positions data\positions\positions.csv
bullstrangle --db data\bullstrangle.db generate-weekend-decisions 2026-04-24 --decision-date 2026-04-27 --output outputs\reports\weekend_2026-04-24.md
```

---

## Exit Trigger Reference

| Action | Meaning | What To Do |
|--------|---------|-----------|
| `CLOSE_IMMEDIATELY` | Earnings this week or extreme drop (>30%) | Close the position today |
| `EXIT_MONDAY` | DTE ≤ 7 — expiring very soon | Close at open Monday |
| `REVIEW` | Stock within 3% of a strike, or below put strike | Watch closely; consider closing |
| `NEEDS_RESOLUTION` | DTE ≤ 0 — should have closed already | Run `auto-resolve` |
| `HOLD` | No triggers fired | No action needed |

---

## DB Quick-Check

```powershell
python -c "
import sqlite3
conn = sqlite3.connect('data/bullstrangle.db')
tables = [
    'newsletters', 'cycle_layers', 'entry_decisions',
    'exit_decisions', 'os_evaluation_runs',
]
for t in tables:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:<35} {n}')
print()
rows = conn.execute(
    'SELECT portfolio_type, status, COUNT(*) as n FROM cycle_layers '
    'WHERE account_id = ? GROUP BY portfolio_type, status ORDER BY portfolio_type, status',
    ('paper_trade',)
).fetchall()
for r in rows:
    print(r[0], r[1], r[2])
"
```

---

## Current Baseline (2026-04-26)

| Item | Value |
|------|-------|
| Newsletters ingested | 18 |
| Strategy rules | 47 |
| Small portfolio — closed trades | 25 |
| Small portfolio — P&L | +$434 (+0.76%) |
| Small portfolio — win rate | 52% |
| Small portfolio — max drawdown | -4.1% |
| Large portfolio — closed trades | 74 |
| Large portfolio — P&L | -$38,408 (-10.75%) |
| Large portfolio — win rate | 50% |
| Large portfolio — max drawdown | -11.3% |
| Open (small) | 8 positions — exp 2026-05-15 and 2026-05-22 |
| Open (large) | 19 positions — exp 2026-05-15 and 2026-05-22 |

---

## Success Criteria For May Cycle

The May 2026 validation cycle is successful if:

- Gate engine continues to show 75%+ alignment with Short List on deployed weeks
- Small portfolio maintains positive cumulative P&L through May expiration
- Auto-resolve correctly closes all May-expiring positions without manual intervention
- Exit report surfaces any REVIEW / EXIT_MONDAY triggers before they become problems
- Large vs small comparison remains consistent (small outperforms large)
