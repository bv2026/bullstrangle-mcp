# Bull Strangle — System Architecture Design Document
**Version:** 2.0  
**Date:** April 6, 2026  
**Status:** Pre-build Review  
**Author:** Balaji + Claude

---

## Table of Contents

1. [Why We're Building This](#1-why-were-building-this)
2. [What We Evaluated and Why We Ruled It Out](#2-what-we-evaluated-and-why-we-ruled-it-out)
3. [Guiding Principles](#3-guiding-principles)
4. [What Stays — Permanent Constraints](#4-what-stays--permanent-constraints)
5. [How Claude Code and Claude Cowork Fit In](#5-how-claude-code-and-claude-cowork-fit-in)
6. [System Architecture — Full Picture](#6-system-architecture--full-picture)
7. [Multi-Agent Framework](#7-multi-agent-framework)
8. [Agent Definitions](#8-agent-definitions)
9. [Agent Interaction Map](#9-agent-interaction-map)
10. [Data Layer — SQLite Schema](#10-data-layer--sqlite-schema)
11. [MCP Server — Tool Definitions](#11-mcp-server--tool-definitions)
12. [Weekly Operational Rhythm](#12-weekly-operational-rhythm)
13. [Dashboard Design](#13-dashboard-design)
14. [Reporting vs Dashboard vs Analysis](#14-reporting-vs-dashboard-vs-analysis)
15. [Build Order & Phases](#15-build-order--phases)
16. [Architect Review — Concerns Raised and Resolved](#16-architect-review--concerns-raised-and-resolved)
17. [Risk Register](#17-risk-register)
18. [Open Questions](#18-open-questions)
19. [Appendix A — File & Folder Structure](#appendix-a--file--folder-structure)
20. [Appendix B — What the DB Enables That Excel Cannot](#appendix-b--what-the-db-enables-that-excel-cannot)
21. [Appendix C — Glossary](#appendix-c--glossary)

---

## 1. Why We're Building This

### The Core Problem
The existing workflow resets every Sunday. A fresh Excel workbook is generated, the watch list is populated, and everything from prior weeks is discarded. There is no institutional memory. No learning from history. No way to answer questions that span more than one week.

Specific things we cannot do today:
- "How many consecutive weeks has CSCO been on Darren's watch list?"
- "What was IV for SU the last time we entered a strangle on it?"
- "Which names were TRADE? YES but we passed on — what happened to their prices afterward?"
- "What is our actual personal win rate vs Darren's reported 71%?"
- "Which sectors cycle on/off Darren's list with market regime changes?"
- "Is IV for this name expanding or compressing over the last 8 weeks?"
- "Which DCA names did we buy when MA count was already deteriorating?"

### The Secondary Problem — Excel Doing Too Many Jobs
Excel was serving as both the live data retrieval tool (OptionSamurai UDFs) and the reporting/tracking layer (Newsletter tab, Deviations tab, DCA Holdings tab, Strangle Trades tab, Instructions, Formula Reference). This created:
- Weekly ZIP surgery complexity to preserve OptionSamurai webextension
- Cross-sheet formula fragility
- Manual yellow cell maintenance
- No history — tabs overwrote each week
- Cumbersome as trading scales to 3–4 concurrent positions

### The Solution
Separate the concerns cleanly:
- **Excel** does only what it uniquely can: host OptionSamurai live data (UDF formulas)
- **SQLite** stores everything persistent and historical
- **MCP Server** gives Claude persistent access to the database every session
- **Claude chat** is the intelligence and analysis layer — not the data pipeline
- **ETL scripts** handle deterministic data movement
- **Dashboard** shows current status at a glance

### What This Enables
Once even 4–6 weeks of data accumulates, Claude can answer all the questions above instantly, from any session, without any file uploads beyond the daily Excel tab.

### Long-Term Vision
This is designed as a three-phase progression:
```
Phase A — Local (now)
  SQLite + MCP server on your machine
  Claude connects via localhost
  No auth needed

Phase B — Dockerized locally
  docker-compose up → spins all containers
  Identical to cloud environment
  Full integration test before going live

Phase C — Cloud
  Same docker-compose deployed to VPS
  (Railway / Fly.io / DigitalOcean)
  Claude connects via public URL
  Auth added at this stage
  SQLite → PostgreSQL swap (connection string only)
```

**This progression shapes every design decision.** Code written now must work unchanged in Phase C.

---

## 2. What We Evaluated and Why We Ruled It Out

This section documents the full evaluation so we never revisit dead ends.

### Option Considered: Keep Excel Multi-Tab Forever
**Why considered:** All the work already done. Familiar.  
**Why ruled out:** Excel does not retain history between weeks. Tabs overwrite. No way to query across weeks. Grows increasingly unwieldy as trading scales. Does not solve the core problem at all.  
**Decision:** Excel reduced to 1 tab only (OS live data). Everything else moves out.

---

### Option Considered: Google Sheets as Database
**Why considered:** Cloud-native, always accessible, Claude might be able to read it.  
**Why ruled out (three reasons):**

**Reason 1 — Claude cannot read Google Sheets.**  
Tested directly. The Google Drive connector returns:
> "Only Google Docs are supported, and this document has a MIME type of application/vnd.google-apps.spreadsheet"
Cell data is inaccessible. This is a hard platform limitation, not a workaround-able issue.

**Reason 2 — Scaling math.**  
19 symbols × 52 weeks = ~1,000 rows/year for watch list history alone. Add trades, DCA purchases, market environment, notes — Sheets degrades above ~10,000 rows with formulas. Multiple tabs compound the problem.

**Reason 3 — Not a real database.**  
Cannot do SQL-style queries like "give me all weeks where CSCO IV > 40% and TRADE? was YES." Possible but painful in Sheets.

**Note on OptionSamurai Google Sheets Plugin:**  
Confirmed working — same UDF functions as Excel (slightly different names, no "OptionSamurai." prefix). The plugin is a full replacement for Excel from an OS data perspective. However, since Claude cannot read Sheets, this capability is irrelevant to our architecture. Excel remains the OS data container.

**Decision:** Google Sheets ruled out as database. Confirmed for OS live data if ever needed, but Excel stays.

---

### Option Considered: Google Sheets for Live Data + CSV Export for Claude
**Why considered:** Sheets as live OS container, export CSV for Claude to read.  
**Why ruled out:** Adds an extra manual step (export CSV) without solving the history problem. SQLite is simpler and more powerful.  
**Decision:** Rejected. SQLite + MCP is cleaner.

---

### Option Considered: JSON Files Per Week
**Why considered:** Lightweight — each Sunday generates a `week_2026-04-06.json`. Claude reads recent JSON files.  
**Why ruled out:** Claude can only hold 4–8 weeks of JSON in context window. Not queryable. No cross-week analysis. Grows into an unmanageable folder.  
**Decision:** Rejected. SQLite is the right tool.

---

### Option Considered: Two Google Sheets Files (Live + Database)
**Why considered:** `BullStrangle_Live.gsheet` for OS data, `BullStrangle_Database.gsheet` for history.  
**Why ruled out:** Claude still cannot read either Sheet. History in Sheets is not queryable. Same problems as above.  
**Decision:** Rejected. SQLite + MCP solves both problems cleanly.

---

### Option Considered: SQLite with Occasional Upload (No MCP)
**Why considered:** Simplest option — `.db` file uploaded when needed, Claude runs queries.  
**Why partially ruled out:** Works for ad-hoc queries but Claude only has history context when you remember to upload. Mid-week on Tuesday, if you ask "has CSCO been on the list 3 consecutive weeks?" Claude doesn't know unless you uploaded the .db that day. The friction compounds once trading is active.  
**Decision:** SQLite yes, but accessed via MCP server so Claude always has context automatically.

---

### Decision: SQLite + MCP Server (Local)
The right architecture for v1:
- SQLite is a single file, no server, runs anywhere
- MCP server is the interface layer — Claude queries it like any other tool
- No file uploads for history — Claude queries the DB automatically each session
- Designed for PostgreSQL from day one (SQLAlchemy ORM, Alembic migrations)
- Migration Phase A → Phase C is a connection string change, not a rewrite

---

## 3. Guiding Principles

1. **Additive, never destructive** — Excel workflow unchanged. MCP is a parallel layer on top.
2. **Deterministic pipelines** — Agents 1–8 are pure Python, no LLM. They do the same thing every time. Testable. Reliable.
3. **Intelligence concentrated in one place** — Only Agent 9 (Claude Chat) uses LLM reasoning. All other agents are dumb scripts.
4. **Claude reads freely, writes carefully** — Reads are open and automatic. All DB writes require explicit user confirmation in chat first.
5. **Brokers own current positions. SQLite owns context.** — Broker MCPs are authoritative for what you hold (quantity, current P&L). SQLite is authoritative for why you hold it, the strategy context, and history.
6. **Audit trail always** — Every write records timestamp, source, and session. Raw extractions preserved in full before normalization.
7. **PostgreSQL-ready from day one** — SQLAlchemy ORM throughout. Alembic migrations from first commit. Never raw SQL strings. Types chosen for PostgreSQL compatibility.
8. **Phase the build strictly** — Phase N must be stable and tested before Phase N+1 begins. No exceptions. This is how agent count creep is prevented.
9. **Cowork is convenience, not dependency** — Python orchestrator scripts are the backbone. Claude Cowork adds convenience on top. If Cowork is unavailable, the pipeline still runs.
10. **Poll/manual trigger for v1** — No event-driven automation in v1. Manual triggers are easier to debug and trust for trading-critical workflows. Event-driven comes in Phase 3+.

---

## 4. What Stays — Permanent Constraints

| Constraint | Reason | Impact on Architecture |
|------------|--------|----------------------|
| **Excel stays** | OptionSamurai add-in requires Excel. No REST API available from OS. Confirmed no plans to offer one. | Excel Tab 1 is a permanent local dependency. Cloud deployment always requires a local machine running Excel + OS to feed the DB. |
| **Excel = 1 tab only** | All other tabs replaced by SQLite + Claude chat | Massively simplifies ZIP surgery. Template complexity drops dramatically. |
| **OptionSamurai data via Excel upload** | No direct API from OS | You refresh Excel (Ctrl+Shift+Alt+F9), upload to Claude daily. This step cannot be automated away. |
| **Webull via CSV export** | No Webull MCP available or planned | Weekly CSV export from Webull → drop to Claude. Not screenshot — CSV is structured, reliable, stable. |
| **Local only for v1** | Simplicity, no auth, no infrastructure | No cloud deployment until Phase 7. Everything runs on your machine. |
| **SQLite now, PostgreSQL later** | Phase A → Phase C migration | Schema designed for PostgreSQL from day one. Migration = connection string change only. |

---

## 5. How Claude Code and Claude Cowork Fit In

This system is built using multiple Claude tools, each with a distinct role.

### Claude Code
**Role:** Builds and maintains the entire codebase.

Claude Code runs in your terminal with persistent access to your local filesystem. It writes files, runs Python, executes scripts, manages the codebase, and tests iteratively. It is the right tool for:
- Building the SQLite schema and SQLAlchemy models
- Building the MCP server and all tools
- Writing the ETL pipeline scripts
- Building the Excel generator (1-tab version)
- Writing the newsletter parser
- Writing the dashboard generator
- Setting up Alembic migrations
- Running tests

**First prompt for Claude Code:**
> "Build the SQLite schema for the BullStrangle MCP server. Six tables: market_environment, watch_list_history, os_snapshots, dca_holdings, trades, raw_extractions. Use SQLAlchemy ORM throughout so migration to PostgreSQL later is a connection string change only. Include Alembic for migrations. Create the initial migration and run it. Project folder: ~/BullStrangle/"

---

### Claude Cowork
**Role:** Automates triggers and file-based workflows as a convenience layer.

Cowork is a desktop tool for automating file and task management. It is useful for:
- Watching the `~/BullStrangle/newsletters/` folder — when a PDF appears, trigger `sunday_runner.py`
- Watching the `~/BullStrangle/exports/` folder — when a Webull CSV appears, trigger `webull_parser.py`
- Creating keyboard shortcuts to trigger common scripts

**Critical constraint:** Cowork is a convenience layer only — not a dependency. The Python orchestrator scripts (`sunday_runner.py`, `friday_runner.py`) must work when run directly from terminal. If Cowork is unavailable on Sunday morning, the pipeline still runs. Never design a step that only works through Cowork.

---

### Claude Chat (This Conversation)
**Role:** Intelligence, analysis, and decision support. The trading co-pilot.

Claude chat is NOT part of the data pipeline. It reads data from the MCP server and Excel uploads. It does analysis, recommendations, and decisions. It writes to the DB only after explicit user confirmation. It is the only component in the system that uses LLM reasoning.

---

## 6. System Architecture — Full Picture

```
LOCAL MACHINE
│
├─────────────────────────────────────────────────────────────────┐
│                      CLAUDE CHAT (Agent 9)                      │
│                      Intelligence Layer Only                    │
│                                                                 │
│  • Reads DB via MCP tools (automatic each session)             │
│  • Reads live OS data from Excel upload                        │
│  • Writes to DB only after explicit user confirmation          │
│  • Does NOT do raw data extraction or pipeline work            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP Protocol
├──────────────────────────▼──────────────────────────────────────┐
│                    MCP SERVER (Agent 7)                         │
│                    Memory Hub — Always Running                  │
│                                                                 │
│  • Exposes read + write tools to Claude                        │
│  • All agents and Claude talk to DB through here only          │
│  • No direct DB access from anywhere else                      │
│  • SQLAlchemy ORM → SQLite (PostgreSQL-ready)                  │
│  • Write confirmation protocol enforced here                   │
│  • All writes: timestamp + source + session_id                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ SQLAlchemy / ORM
├──────────────────────────▼──────────────────────────────────────┐
│                    SQLITE DATABASE                              │
│                    BullStrangle.db                              │
│                                                                 │
│  market_environment      watch_list_history                    │
│  os_snapshots            dca_holdings                          │
│  trades                  raw_extractions                       │
│                                                                 │
│  (dca_purchases and symbol_notes added in Phase 5)             │
└─────────────────────────────────────────────────────────────────┘

├─────────────────────────────────────────────────────────────────┐
│                   ETL PIPELINE SCRIPTS                          │
│                   Pure Python — No LLM — Deterministic          │
│                                                                 │
│  newsletter_parser.py    PDF → structured JSON → DB            │
│  excel_generator.py      DB → 1-tab Excel                      │
│  os_processor.py         Excel upload → os_snapshots in DB     │
│  broker_reconciler.py    Broker MCPs → holdings in DB          │
│  webull_parser.py        Webull CSV → purchases in DB          │
│  dashboard_generator.py  DB → dashboard.html                   │
│                                                                 │
│  sunday_runner.py        Orchestrates Sunday pipeline          │
│  friday_runner.py        Orchestrates Friday close             │
└─────────────────────────────────────────────────────────────────┘

├──────────────┬─────────────────┬─────────────────────────────────┐
│   EXCEL      │   DASHBOARD     │   BROKER MCPs                   │
│   (1 tab)    │   (static HTML) │                                  │
│              │                 │   TradeStation MCP (connected)   │
│   OS UDF     │   Manual        │   Tradier MCP (connected)        │
│   formulas   │   refresh       │   Schwab MCP (local, verify)     │
│   live data  │   on demand     │                                  │
└──────────────┴─────────────────┴─────────────────────────────────┘

EXTERNAL INPUTS (manual steps you own)
  • Darren's newsletter PDF → drop to ~/BullStrangle/newsletters/
  • Populated Excel → upload to Claude chat
  • Webull CSV export → drop to ~/BullStrangle/exports/
```

---

## 7. Multi-Agent Framework

This system is explicitly a **multi-agent architecture**. Naming it correctly is important — it shapes how we design, build, and debug.

### What Makes It Multi-Agent
Each agent has:
- A single, bounded responsibility
- Clear inputs and outputs
- No knowledge of what other agents are doing
- No direct communication with other agents

Agents communicate only through the shared data layer (Agent 7 — MCP Server). This is **loose coupling through a shared data hub** — the key architectural principle.

### The Three Categories of Agents

**Deterministic Pipeline Agents (Agents 1–6, 8)**
Pure Python. No LLM. Do the same thing every time. Build once, run forever.
- Agent 1: Newsletter Parser
- Agent 2: Excel Generator
- Agent 3: OS Processor
- Agent 4: Broker Reconciler
- Agent 5: Webull Parser
- Agent 6: Dashboard Generator
- Agent 8: Friday Runner

**Memory Hub (Agent 7)**
Always running. The only gateway to the database. No agent touches the DB directly.
- Agent 7: MCP Server

**Intelligence Agent (Agent 9)**
The only LLM. Reads from the hub. Writes only after confirmation. All judgment lives here.
- Agent 9: Claude Chat

### Why This Separation Matters
- If Agent 1 (newsletter parser) breaks, Agents 2–9 still work with existing DB data
- If Agent 4 (broker reconciler) is down, you get a warning but the rest of the session continues
- Claude chat (Agent 9) never needs to know how data got into the DB — it just reads it
- Each agent can be tested and replaced independently

---

## 8. Agent Definitions

### Agent 1 — Newsletter Parser

| Property | Detail |
|----------|--------|
| **Trigger** | `sunday_runner.py` calls it with PDF file path |
| **Input** | Darren's newsletter PDF |
| **Output** | Structured JSON → written to DB via MCP. Raw blob → `raw_extractions`. |
| **Tech** | Python + pdfplumber |
| **Error handling** | Always writes raw blob to `raw_extractions` first, regardless of parse success. Populates `warnings[]` array. Never silently writes bad data to normalized tables. |
| **Knows about** | PDF structure, newsletter format, data extraction patterns |
| **Does NOT know about** | Trading decisions, strategy context, what the data means |

**What it extracts (complete list — no silent skips):**
- Market environment: hybrid score + all 3 component values (trend, VIX, breadth)
- S&P price, S&P 200-DMA, exact % relationship
- VIX exact value
- Breadth exact value (% of S&P stocks above 50-DMA)
- All 4 re-entry criteria pass/fail status
- Full watch list: every symbol — NL price, IV, IV-RV percentile, call strike/bid, put strike/bid, total credit, weekly return %, prob both worthless, earnings date, ATR%, short ratio
- Large short list: all symbols
- Small short list: all symbols
- Watch list favorites: full trade detail for each
- Performance tables: Darren's win rate, avg weekly, total return, annualized, vs S&P
- Market recap: all index moves, drivers, Darren's bottom line narrative
- Any editorial or methodology changes — flagged explicitly

**Validation output:** Page count detected, page count processed, structure fingerprint (for detecting newsletter format changes week-over-week), warnings array.

---

### Agent 2 — Excel Generator

| Property | Detail |
|----------|--------|
| **Trigger** | `sunday_runner.py` calls it after Agent 1 completes |
| **Input** | Watch list symbols from DB |
| **Output** | `BullStrangle_YYYYMMDD.xlsx` — 1 tab only |
| **Tech** | Python + openpyxl + ZIP surgery (webextension preservation) |
| **Knows about** | OptionSamurai UDF structure, Excel format, ZIP surgery procedure |
| **Does NOT know about** | Trading decisions, what the data means |

**What changed from the old Excel (8 tabs → 1 tab):**

| Old Tab | Status | Where it went |
|---------|--------|---------------|
| 1. Bull Strangle - Option Samurai | ✅ Kept | Still Tab 1, the only tab |
| 2. Bull Strangle - Newsletter | ❌ Eliminated | Data lives in SQLite `watch_list_history` |
| 3. DCA Candidates | ❌ Eliminated | Claude generates from SQLite each session |
| 4. Bull Strangle - Deviations | ❌ Eliminated | Claude calculates in chat (OS vs NL from DB) |
| 5. Instructions | ❌ Eliminated | Lives in project docs |
| 6. Formula Reference | ❌ Eliminated | Lives in project docs |
| 7. DCA Candidates (Holdings) | ❌ Eliminated | Lives in SQLite `dca_holdings` |
| 8. Strangle Trades | ❌ Eliminated | Lives in SQLite `trades` |

**ZIP surgery still required** even for 1 tab — the OptionSamurai webextension registration must be preserved. But the complexity drops dramatically with only 1 tab to manage.

---

### Agent 3 — OS Processor

| Property | Detail |
|----------|--------|
| **Trigger** | You upload populated Excel to Claude chat |
| **Input** | Populated Excel file (Tab 1 with live OS UDF values) |
| **Output** | Row written to `os_snapshots` in DB for each symbol |
| **Tech** | Python reads Excel → writes to DB via MCP write tool |
| **Runs** | Sunday (after you return populated Excel) + every intraweek upload |
| **Audit** | Raw Excel file saved to `~/BullStrangle/exports/os_raw/YYYYMMDD_HHMM.xlsx` |
| **Knows about** | Excel column structure, OS field name mappings |
| **Does NOT know about** | Trading decisions |

**Critical role:** This agent closes the Sunday loop. Agent 1 writes NL prices. Agent 3 writes live OS values. Only when both are written can Claude compute deviations. The `captured_at` timestamp matters — intraday snapshots track when prices were captured, not just the date.

---

### Agent 4 — Broker Reconciler

| Property | Detail |
|----------|--------|
| **Trigger** | Automatic at start of every Claude chat session |
| **Input** | TradeStation MCP + Tradier MCP + Schwab MCP (local) |
| **Output** | `dca_holdings` and `trades` tables current in DB |
| **Tech** | Python calls broker MCPs → `reconcile_holdings()` MCP write tool |
| **Runs** | Every session, automatically, no prompt needed |
| **Knows about** | Broker MCP APIs, position data structures |
| **Does NOT know about** | Strategy context (that comes from user confirmation) |

**Reconciliation contract (critical — this resolves the two-sources-of-truth problem):**
- Broker MCPs = **authoritative for current positions and quantities**
- SQLite = **authoritative for strategy context, cost basis intent, and history**
- These serve different questions. They never compete.
- Discrepancies flagged to Claude for user resolution — never auto-resolved

**When discrepancy found:**
> "I see 25 new SU shares in Webull not reflected in the DB. Please drop the Webull CSV export to reconcile."

---

### Agent 5 — Webull Parser

| Property | Detail |
|----------|--------|
| **Trigger** | You drop Webull CSV export to Claude chat |
| **Input** | Webull trade history CSV file |
| **Output** | New purchase rows written to `dca_holdings` in DB |
| **Tech** | Python + pandas |
| **Runs** | On demand when you drop CSV |
| **Knows about** | Webull CSV format and column structure |
| **Does NOT know about** | Strategy context |

**Why CSV not screenshot:**
Screenshots are fragile — Webull UI changes break parsing. CSV is structured data with stable column names. Same manual step for you, much more reliable. If Webull changes CSV format, parser update is a small fix. If Webull changes its UI, screenshot parsing can break silently and produce wrong data.

---

### Agent 6 — Dashboard Generator

| Property | Detail |
|----------|--------|
| **Trigger** | "refresh dashboard" in Claude chat, or direct terminal command |
| **Input** | All DB tables (read-only) |
| **Output** | `~/BullStrangle/dashboard/dashboard.html` opened in browser |
| **Tech** | Python + Jinja2 HTML template |
| **Runs** | On demand |
| **Knows about** | DB schema, HTML generation |
| **Does NOT know about** | Strategy decisions |

**Key design decision — no running server:**  
The dashboard is a generated static HTML file. There is no Flask server, no FastAPI, no port to manage. When you want to see it, the script reads the DB and regenerates the file. Open in browser. This is the simplest possible implementation that meets the "static, manual refresh is fine" requirement.

---

### Agent 7 — MCP Server (Memory Hub)

| Property | Detail |
|----------|--------|
| **Trigger** | Always running as a local background process |
| **Input** | Queries and writes from Claude + all agents |
| **Output** | Structured data to all consumers |
| **Tech** | Python MCP server + SQLAlchemy ORM + SQLite |
| **Runs** | Always (lightweight, minimal resource usage) |
| **Knows about** | Schema, data integrity, write confirmation protocol |
| **Does NOT know about** | Strategy decisions |

**Architectural rule:** Every agent and Claude talk to the DB **only through this server**. No direct DB connections from any other component. This is how we maintain data integrity, enforce the write confirmation protocol at the infrastructure level (not just Claude instructions), and make the PostgreSQL migration seamless.

---

### Agent 8 — Friday Runner

| Property | Detail |
|----------|--------|
| **Trigger** | Manual run after market close Friday — `python runners/friday_runner.py` |
| **Input** | Broker MCPs (expiration outcomes for all open positions) |
| **Output** | Trade exits written to DB, cycle summary output |
| **Tech** | Python orchestrator calling broker MCPs → MCP write tools |
| **Runs** | Every Friday after close |

**What it does:**
1. Queries broker MCPs for all open position outcomes
2. Matches outcomes to open trades in SQLite
3. Flags each: CALLED / ASSIGNED / BOTH_EXPIRED / CLOSED_EARLY
4. Checks assigned positions: do any push shares to ≥100? Flag for graduation to Strangle eligible
5. Outputs cycle summary for Claude to review and confirm
6. Claude confirms → writes trade exits to DB

---

### Agent 9 — Co-Pilot (Claude Chat)

| Property | Detail |
|----------|--------|
| **Trigger** | You open a conversation |
| **Input** | Excel upload + MCP server queries (automatic) + broker MCPs |
| **Output** | Analysis, deviations, DCA updates, trade plans, historical queries |
| **Tech** | Claude chat (this) |
| **Runs** | On demand |
| **Knows about** | Everything strategic — combines all data sources with judgment |
| **Does NOT do** | Raw data extraction, pipeline work, writing without confirmation |

**What Claude does automatically at the start of every session:**
1. Calls `get_market_environment(weeks=2)` — current regime, re-entry criteria status
2. Calls `get_dca_holdings()` — accumulation status across all accounts
3. Calls `get_open_trades()` — any active strangles
4. Calls `get_current_watch_list()` — NL prices for deviations
5. Agent 4 fires (broker reconciliation) — holdings current
6. Reads uploaded Excel for live OS values (when provided)
7. Outputs full analysis

---

## 9. Agent Interaction Map

```
Newsletter PDF (you drop to folder)
      │
      ▼
[Agent 1: Newsletter Parser]
      │ writes market_environment,
      │ watch_list_history, raw_extractions
      ▼
[Agent 7: MCP Server / DB] ◄─────────────────────────────────────┐
      │                                                           │
      ▼                                                           │
[Agent 2: Excel Generator]                                        │
      │ writes BullStrangle_YYYYMMDD.xlsx                        │
      ▼                                                           │
You open Excel                                                    │
Ctrl+Shift+Alt+F9                                                │
Upload to Claude chat                                            │
      │                                                           │
      ▼                                                           │
[Agent 3: OS Processor] ──────────────────────────────────────────┤
      │ writes os_snapshots                                      │
      │ saves raw Excel to exports/os_raw/                       │
                                                                  │
Broker MCPs (every session, automatic)                           │
      │                                                           │
      ▼                                                           │
[Agent 4: Broker Reconciler] ─────────────────────────────────────┤
      │ reconciles dca_holdings, trades                          │
                                                                  │
Webull CSV (you drop when needed)                                │
      │                                                           │
      ▼                                                           │
[Agent 5: Webull Parser] ─────────────────────────────────────────┤
      │ writes dca_holdings                                      │
                                                                  │
"refresh dashboard" (on demand)                                  │
      │                                                           │
      ▼                                                           │
[Agent 6: Dashboard Generator]                                    │
      │ reads all tables                                         │
      ▼                                                           │
dashboard.html ──► Browser                                        │
                                                                  │
[Agent 7: MCP Server] ──────────────────────── Claude reads ◄────┘
                                                     │
                                         All data available
                                                     │
                                                     ▼
                                         [Agent 9: Claude Chat]
                                                     │
                                        Analysis, recommendations
                                                     │
                                         You confirm trade/purchase
                                                     │
                                         Claude states write intent
                                                     │
                                         You confirm: "yes"
                                                     │
                                         Claude writes via MCP ──► DB
```

---

## 10. Data Layer — SQLite Schema

### Design Rules
- SQLAlchemy ORM throughout — never raw SQL strings anywhere
- Alembic for all schema changes — from first commit, not retrofitted later
- Every table has: `id`, `created_at`
- Every pipeline-written table has: `source` (which agent wrote it), `session_id`
- PostgreSQL-compatible types used throughout (no SQLite-specific types)
- `raw_extractions` table is non-negotiable — audit trail for every Sunday extraction

### V1 Tables (6 — build in Phase 1)

---

#### Table: `market_environment`
One row per week. Primary reference for regime and re-entry criteria.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| week_date | DATE UNIQUE | Sunday newsletter date |
| hybrid_score | FLOAT | e.g. −2.0 |
| sp500 | FLOAT | S&P close price |
| sp500_200dma | FLOAT | 200-day MA value |
| sp500_vs_200dma_pct | FLOAT | % above/below 200-DMA |
| vix | FLOAT | VIX close |
| breadth | FLOAT | % S&P stocks above 50-DMA |
| regime | VARCHAR(20) | DEFENSIVE / MODERATE / FULL |
| crit_hybrid | VARCHAR(10) | PASS / FAIL |
| crit_sp500 | VARCHAR(10) | PASS / FAIL |
| crit_vix | VARCHAR(10) | PASS / FAIL |
| crit_breadth | VARCHAR(10) | PASS / FAIL |
| all_criteria_met | BOOLEAN | True only if all 4 pass |
| consecutive_moderate_weeks | INTEGER | Weeks at Hybrid ≥ 0 |
| darren_bottom_line | TEXT | Darren's market narrative verbatim |
| source | VARCHAR(50) | newsletter_parser |
| session_id | VARCHAR(50) | Extraction session identifier |
| created_at | TIMESTAMP | Auto-set on insert |

---

#### Table: `watch_list_history`
One row per symbol per week. The core institutional memory of the system.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| week_date | DATE | FK → market_environment.week_date |
| symbol | VARCHAR(10) | e.g. CSCO |
| company | VARCHAR(100) | Full company name |
| sector | VARCHAR(50) | |
| nl_price | FLOAT | Newsletter Friday close |
| iv | FLOAT | Implied volatility |
| iv_rv_percentile | FLOAT | IV vs realized vol percentile |
| call_strike | FLOAT | |
| call_bid | FLOAT | |
| call_dist_pct | FLOAT | % OTM at time of newsletter |
| put_strike | FLOAT | |
| put_bid | FLOAT | |
| put_dist_pct | FLOAT | % OTM at time of newsletter |
| total_credit | FLOAT | Call bid + put bid |
| weekly_return_pct | FLOAT | Total credit / stock price |
| prob_both_worthless | FLOAT | |
| trade_flag | VARCHAR(5) | YES / NO |
| on_short_list_large | BOOLEAN | |
| on_short_list_small | BOOLEAN | |
| is_wl_favorite | BOOLEAN | Darren's "Watch List Favorites" |
| earnings_date | DATE | Next earnings date at time of newsletter |
| atr_pct | FLOAT | Average True Range % |
| short_ratio | FLOAT | |
| weeks_on_list | INTEGER | Consecutive weeks on Darren's list |
| first_appeared_date | DATE | When this symbol first appeared |
| darren_notes | TEXT | Any Darren commentary on this name |
| source | VARCHAR(50) | newsletter_parser |
| session_id | VARCHAR(50) | |
| created_at | TIMESTAMP | |

**Composite unique constraint:** `(week_date, symbol)` — prevents duplicate entries.

---

#### Table: `os_snapshots`
One row per symbol per Excel upload. Multiple rows per symbol per week (intraday captures matter).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| snapshot_date | DATE | Calendar date of upload |
| captured_at | TIMESTAMP | **Exact time** — intraday timing matters for deviations |
| symbol | VARCHAR(10) | |
| os_price | FLOAT | Live price at capture time |
| os_iv | FLOAT | |
| os_iv_rv_percentile | FLOAT | |
| os_call_strike | FLOAT | Live recalculated strike |
| os_call_bid | FLOAT | |
| os_put_strike | FLOAT | Live recalculated strike |
| os_put_bid | FLOAT | |
| os_prob_both_worthless | FLOAT | |
| os_trade_flag | VARCHAR(5) | YES / NO — live filter result |
| ma_50d | FLOAT | 50-day MA value |
| ma_200d | FLOAT | 200-day MA value |
| perf_m | FLOAT | 1-month perf (20-DMA proxy) |
| perf_q | FLOAT | 1-quarter perf (100-DMA proxy) |
| atr_pct | FLOAT | |
| short_ratio | FLOAT | |
| raw_excel_path | VARCHAR(500) | Path to saved raw Excel file for audit |
| source | VARCHAR(50) | os_processor |
| session_id | VARCHAR(50) | |
| created_at | TIMESTAMP | |

**Note on `raw_excel_path`:** Every Excel upload is saved to `~/BullStrangle/exports/os_raw/YYYYMMDD_HHMM.xlsx` before processing. This path is stored here. If Agent 3 misreads a column mapping, the raw file is available for diagnosis.

---

#### Table: `dca_holdings`
One row per symbol per account. Updated in place when positions change.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| symbol | VARCHAR(10) | |
| company | VARCHAR(100) | |
| sector | VARCHAR(50) | |
| account | VARCHAR(20) | WEBULL / TRADIER / TRADESTATION / SCHWAB / ROBINHOOD / FIDELITY |
| shares_held | INTEGER | Current total in this account |
| avg_cost_basis | FLOAT | Blended average cost |
| target_shares | INTEGER | Default 100 |
| shares_remaining | INTEGER | Computed: target − held |
| status | VARCHAR(20) | ACCUMULATING / COMPLETE / PAUSED / GRADUATED |
| first_purchase_date | DATE | |
| last_purchase_date | DATE | |
| on_current_watchlist | BOOLEAN | Updated each Sunday |
| notes | TEXT | e.g. "dropped from WL this week — HOLD" |
| updated_at | TIMESTAMP | Updated on each reconciliation |
| created_at | TIMESTAMP | |

**Composite unique constraint:** `(symbol, account)` — one row per symbol per account.

---

#### Table: `trades`
One row per strangle position entry. Append only — rows are never deleted or edited (only `outcome`, `stock_exit_price`, `final_pnl_pct`, `updated_at` filled in on close).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| symbol | VARCHAR(10) | |
| account | VARCHAR(20) | Which broker account |
| cycle_start_date | DATE | Monday entry date |
| cycle_end_date | DATE | Friday expiry date |
| call_strike | FLOAT | |
| call_credit | FLOAT | Premium received |
| put_strike | FLOAT | |
| put_credit | FLOAT | Premium received |
| total_credit | FLOAT | Call + put credit |
| shares | INTEGER | Always 100 |
| stock_entry_price | FLOAT | Price paid for 100 shares |
| nl_price_at_entry | FLOAT | From watch_list_history (for context) |
| iv_at_entry | FLOAT | From os_snapshots |
| iv_rv_pct_at_entry | FLOAT | IV-RV percentile at entry |
| weeks_on_watchlist_at_entry | INTEGER | From watch_list_history |
| was_wl_favorite | BOOLEAN | Was it a WL Favorite that week |
| outcome | VARCHAR(20) | CALLED / ASSIGNED / BOTH_EXPIRED / CLOSED_EARLY — filled on close |
| stock_exit_price | FLOAT | Filled on close |
| final_pnl_pct | FLOAT | Filled on close |
| confirmed_by_user | BOOLEAN | Always True — never written without explicit confirmation |
| notes | TEXT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | Updated on close |

---

#### Table: `raw_extractions`
One row per Sunday newsletter extraction. The audit backbone.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| extraction_date | DATE | Sunday date |
| pdf_filename | VARCHAR(200) | Original filename |
| pages_found | INTEGER | Total pages detected by pdfplumber |
| pages_processed | INTEGER | Pages successfully extracted |
| structure_fingerprint | VARCHAR(200) | Hash/signature of newsletter structure — detect format changes |
| warnings | JSON | Array of any extraction issues found |
| raw_json | JSON | **Complete extraction before normalization** — full safety net |
| newsletter_version | VARCHAR(50) | Any format change flag vs prior week |
| source | VARCHAR(50) | newsletter_parser |
| created_at | TIMESTAMP | |

**Why this table is non-negotiable:** If Agent 1 misreads a strike price, a credit, or an earnings date, this table contains the raw JSON that was processed. You can diagnose exactly what was parsed and fix it without re-running the pipeline.

---

### Deferred Tables (Phase 5+)

**`dca_purchases`** — individual purchase records (date, shares, price, account, MA count at time of purchase). Deferred because holdings can be reconciled from broker MCPs in v1. Added in Phase 5 when purchase-level history becomes analytically useful.

**`symbol_notes`** — free-text notes on any symbol from any source (Darren, Claude, you). Deferred to Phase 5 — not needed until trading is active and observations worth capturing.

---

## 11. MCP Server — Tool Definitions

### Write Confirmation Protocol — Non-Negotiable
Before calling any write tool, Claude must:
1. State exactly what it is about to write, in plain language
2. Wait for explicit "yes" or "confirmed" from you in chat
3. Only then call the write tool

This protocol is enforced **at the MCP server level** (not just in Claude's instructions). Write tools check for a `confirmed=True` parameter. If not present, the tool returns a confirmation request instead of writing.

Example:
> **Claude:** "I'm about to record: SU purchase — 25 shares @ $64.20, Webull account, April 7 2026. MA count at purchase: 3/4. Confirm?"  
> **You:** "Yes"  
> **Claude:** [calls `write_dca_purchase(confirmed=True, ...)`]

---

### Phase 1 Tools — Build First

These are needed every single session from day one.

**Read Tools**

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_market_environment` | `weeks=8` | Recent weeks: hybrid score, S&P, VIX, breadth, all criteria, regime, streak |
| `get_regime_trend` | — | Consecutive weeks in current regime, direction of travel |
| `get_reentry_status` | — | Each of 4 criteria with current values and PASS/FAIL |
| `get_current_watch_list` | — | This week's full list — NL prices + most recent OS values merged |
| `get_dca_holdings` | — | All positions across all accounts: symbol, shares, target, cost basis, status |
| `get_open_trades` | — | All active strangles: symbol, strikes, credits, DTE, status |

**Write Tools**

| Tool | Parameters | Called by |
|------|------------|-----------|
| `write_market_environment` | All env fields + confirmed | Agent 1 (Sunday) |
| `write_watch_list_snapshot` | `week_date`, `symbols[]` + confirmed | Agent 1 (Sunday) |
| `write_os_snapshot` | `snapshot_date`, `symbols[]` + confirmed | Agent 3 (daily) |
| `reconcile_holdings` | `account`, `positions[]` | Agent 4 (auto — no confirmation needed for reads, confirmation for new writes) |

---

### Phase 2 Tools — Needs 4+ Weeks of Data

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_watch_list_history` | `symbol`, `weeks=8` | Full history: NL price, OS price, IV, strikes, TRADE? flag per week |
| `get_watch_list_streaks` | `min_weeks=3` | Symbols on list N+ consecutive weeks — Darren conviction signal |
| `get_watch_list_changes` | — | New names vs dropped vs prior week |
| `get_iv_trend` | `symbol`, `weeks=8` | IV value week over week — expanding or compressing? |
| `get_dca_purchase_history` | `symbol` | Every buy: date, shares, price, account, MA count at purchase |

---

### Phase 3 Tools — Needs 3+ Months of Data

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_performance_summary` | — | Our stats vs Darren's: win rate, avg weekly return, annualized, by regime, by sector |
| `get_missed_trades` | `weeks=4` | TRADE? YES names we didn't enter + subsequent price movement |
| `get_symbol_profile` | `symbol` | Everything: watch list history, DCA history, trade history, IV trend, notes |
| `get_sector_exposure` | — | Current exposure across open trades + DCA holdings by sector |
| `search_notes` | `symbol=None`, `keyword=None` | Free text search across all symbol notes (Phase 5 table) |

---

## 12. Weekly Operational Rhythm

### Sunday — Newsletter Day

```
Step 1.  You drop PDF to ~/BullStrangle/newsletters/
         (Cowork can watch folder and trigger; or run manually)

Step 2.  sunday_runner.py fires:
         a. Agent 1: PDF → structured JSON → DB
            - Writes market_environment (1 row)
            - Writes watch_list_history (1 row per symbol)
            - Writes raw_extractions (full audit blob)
            - Outputs: page count, warnings, structure fingerprint
         b. Agent 2: DB watch list → 1-tab Excel
            - BullStrangle_YYYYMMDD.xlsx in ~/BullStrangle/excel/

Step 3.  You open Excel
         Ctrl+Shift+Alt+F9 (refreshes all OS UDF values)

Step 4.  You upload populated Excel to Claude chat

Step 5.  Agent 3: OS values → os_snapshots in DB
         Raw Excel saved to exports/os_raw/ (audit copy)

Step 6.  Agent 4: Broker MCPs → reconcile holdings (automatic)
         Any discrepancies flagged (e.g., "Webull shows 25 new SU shares")

Step 7.  Claude (Agent 9): Full Sunday analysis output
         - Watch list changes vs prior week (new names, dropped, streaks)
         - Deviations: live OS values vs NL prices from DB
         - DCA candidate update: live prices, MA counts, scores, rankings
         - Re-entry criteria: current status + trend (how many weeks at current score)
         - Market environment narrative (Darren's bottom line)
         - Any editorial or methodology changes flagged

Step 8.  Optional: "refresh dashboard" → dashboard.html opens in browser

Sunday loop is now complete. DB has NL data + OS data for the week.
```

---

### Monday — Entry Day
*(Only executes fully when all 4 re-entry criteria are met)*

```
Pre-market:
  Note any overnight gaps vs Friday close

10:00 AM ET:
Step 1.  Open Excel, Ctrl+Shift+Alt+F9
Step 2.  Upload Excel to Claude
Step 3.  Agent 3: OS snapshot → DB (pre-market state captured)
Step 4.  Agent 4: Broker reconcile (automatic)
Step 5.  Claude: Full Monday Analysis Sequence
         - Deviations (anything moved since Sunday's NL prices?)
         - Strike adjustment flags (recalculate call/put distances for movers)
         - Ranked trade candidates (TRADE? YES names, scored)
         - Near misses (which filter failed and by how much)
         - Hard skips (leveraged ETF, earnings conflict, etc.)
         - Sector exposure map (existing + proposed)
         - Final recommendation: 1–3 entries in order of preference

Step 6.  You enter orders per trade plan
Step 7.  You confirm fills in chat:
         "Entered CSCO: call $82 @ $1.60, put $78 @ $1.40,
          bought 50 shares @ $79.50, TradeStation"
Step 8.  Claude confirms write intent, waits for "yes"
Step 9.  Claude writes trade entry to DB

If re-entry criteria NOT met:
  Step 5 = deviations + DCA update only
  No trade plan generated
  No entries
```

---

### Tuesday–Thursday — Monitor Only

```
~2:30–3:30 PM ET:
Step 1.  Ctrl+Shift+Alt+F9 on Excel
Step 2.  Upload Excel to Claude
Step 3.  Agent 3: OS snapshot → DB (intraday capture)
Step 4.  Agent 4: Broker reconcile (automatic)
Step 5.  Claude output:
         Section 1 — Deviations (always first)
           Per-symbol: Price Δ, Strike Δ with recalculated distances,
           Credit Δ with threshold verdict, gap-down flag
           Summary table with STATUS column
           Any FILTER FAIL or GAP-DOWN CAUTION called out explicitly
         Section 2 — DCA Candidate Update
           Live prices, MA counts, put distances, revised scores
         Section 3 — Open Position Status (when trades active)
           DTE, stock vs strike distances, any at-risk flags

Step 6.  No new entries. No adjustments to open positions.

If Webull buy today:
  Export CSV from Webull
  Drop CSV to Claude
  Agent 5 parses → Claude confirms → writes to DB
```

---

### Friday — Expiration Day

```
During market hours:
  Allow natural expiry. No intervention.

After close:
Step 1.  Run friday_runner.py (manual or Cowork scheduled)
Step 2.  Agent 8 queries broker MCPs for all outcomes
Step 3.  Claude reviews each outcome with you:
         "CSCO: both expired worthless. Confirm?"
Step 4.  Claude writes trade exits to DB (after each confirmation)
Step 5.  Claude: Cycle summary
         - Win/loss for closing cycle
         - P&L per trade
         - Running totals vs Darren benchmarks
Step 6.  Assigned shares check:
         Any put assignments → check if position reaches ≥100 shares
         If yes → flag for graduation to Strangle Trades eligible
Step 7.  Dashboard refresh → updated performance panel
```

---

### Saturday — Optional Review

```
No Excel needed.
Claude queries SQLite only via MCP (no file upload required):
  - Weekly performance summary
  - DCA pipeline status and what to watch for
  - 4-week market environment trend
  - Watch list streak analysis (once 4+ weeks of data)
  - Prep questions for Sunday newsletter
    "What are we watching for this week?"
```

---

## 13. Dashboard Design

### Philosophy
Dashboard = **current status only**. It answers one question: where do things stand right now?

Not a reporting tool. Not an analysis tool. Those are Claude's job. The dashboard is the always-available status panel — like a cockpit instrument cluster.

### Implementation — Static HTML File
No running web server. No Flask. No FastAPI. No ports.

The dashboard is a generated HTML file. When you want to see it:
```
"refresh dashboard"
  → Python reads DB
  → Writes ~/BullStrangle/dashboard/dashboard.html
  → Opens in default browser automatically
```

### Layout — Four Panels

```
┌─────────────────────────────────────────────────────────────────┐
│  BULL STRANGLE  |  Week of Apr 6 2026  |  ● DEFENSIVE  -2      │
├──────────────────┬──────────────────┬───────────────────────────┤
│  ENVIRONMENT     │  OPEN TRADES     │  DCA PIPELINE             │
│                  │                  │                           │
│  Hybrid:  -2     │  Active: 0       │  Accumulating (6)         │
│                  │                  │                           │
│  ✅ VIX   23.87  │  No active       │  CSCO   50/100  ██░░  🟡 │
│  ❌ S&P   below  │  strangles.      │  SU     25/100  █░░░  🟡 │
│  ❌ Breadth 28%  │  Re-entry        │  XLE    50/100  ██░░  🟡 │
│  ❌ Hybrid ×2    │  criteria not    │  HP     75/100  ███░  🟢 │
│                  │  yet met.        │  BMY    50/100  ██░░  🟡 │
│  1 of 4 ✅       │                  │  BP     50/100  ██░░  🟡 │
│                  │                  │                           │
│  2 wks           │                  │  Eligible:    0           │
│  Defensive       │                  │  Env Defensive            │
├──────────────────┴──────────────────┴───────────────────────────┤
│  WATCH LIST  —  19 symbols this week                            │
│                                                                 │
│  TRADE? YES: 0   TRADE? NO: 19   New this week: 3  Dropped: 2  │
│  Favorites: CSCO                                                │
│  Large short list: TGT  EWJ  IAU  KRE  HSBC  NTR  PAAS...     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  PERFORMANCE                                                    │
│                                                                 │
│  Darren:   71% win  |  0.75%/wk  |  38.94% annualized         │
│  Ours:     — (no closed trades recorded in this system yet)    │
│                                                                 │
│  DB last updated: Sun Apr 6 2026  2:34 PM                      │
└─────────────────────────────────────────────────────────────────┘
```

### Panel Definitions

**Environment Panel**
- Hybrid score + regime label (color coded: red=Defensive, yellow=Moderate, green=Full)
- All 4 re-entry criteria with ✅/❌ and actual values
- Count passing + consecutive weeks in current regime

**Open Trades Panel**
- Count of active strangles
- When active: each position — symbol, strikes, credit, DTE, stock vs strike distance
- When no positions: simple status message

**DCA Pipeline Panel**
- All accumulating positions: symbol, shares/target progress bar, status indicator
- Eligible count (≥100 shares + on watch list + env Moderate+)
- Names awaiting fills

**Watch List Panel**
- Symbol count, TRADE? YES count
- New names this week vs dropped
- Favorites and short list

**Performance Panel**
- Darren's reported stats (from latest newsletter in DB)
- Our actual stats computed from `trades` table
- Last DB update timestamp

### Phase 3 Dashboard Additions (deferred until data exists)
- IV trend sparklines per symbol
- Win rate by sector
- Weekly returns bar chart
- Market environment history timeline (4–8 weeks)
- DCA cost basis vs current price chart

---

## 14. Reporting vs Dashboard vs Analysis

These are three distinct things. Conflating them is how systems become cluttered and useless.

| Type | Question it answers | Format | When |
|------|--------------------|---------|----|
| **Dashboard** | Where do things stand right now? | Static HTML, manual refresh | On demand, always current |
| **Analysis** | What should I do and why? | Claude chat output | Every session, context-aware, judgment-driven |
| **Report** | What happened this week/cycle? | Structured summary (Phase 6) | Saturday, historical, backward-looking |

**Dashboard** is for status. Claude cannot always be open. The dashboard is the background awareness layer.

**Analysis** is for decisions. Claude reads the DB + live Excel and provides judgment. No dashboard can replicate this.

**Report** is for the record. Generated automatically Saturday. Contains the week's trades, performance vs benchmark, DCA activity, watch list changes. Deferred to Phase 6 — not enough data to make it meaningful until trading has been active for months.

---

## 15. Build Order & Phases

### Rule
Phase N must be stable and tested before Phase N+1 begins. This prevents agent count creep and ensures the foundation is solid before building on it.

---

### Phase 1 — Foundation (~Week 1)
**Goal:** MCP server running, Claude chat connects to DB, basic context available.

```
Claude Code builds:
  ✦ SQLite schema — 6 tables, indexes, composite unique constraints
  ✦ SQLAlchemy models (schema.py)
  ✦ Alembic setup + initial migration (run and verified)
  ✦ MCP server skeleton — all Phase 1 tools registered
  ✦ Phase 1 read tools implemented:
      get_market_environment, get_regime_trend, get_reentry_status,
      get_current_watch_list, get_dca_holdings, get_open_trades

Test criteria:
  □ Claude chat connects to MCP server
  □ All 6 read tools return correct empty-state responses
  □ Alembic migration runs clean
  □ Schema verified against PostgreSQL compatibility checklist
```

---

### Phase 2 — Sunday Pipeline (~Week 2)
**Goal:** Full Sunday loop works end to end. DB populated from real newsletter.

```
Claude Code builds:
  ✦ newsletter_parser.py (PDF → structured JSON, pdfplumber)
  ✦ excel_generator.py (1-tab Excel, ZIP surgery preserved)
  ✦ sunday_runner.py (orchestrates Agent 1 → Agent 2, error handling)
  ✦ MCP write tools: write_market_environment, write_watch_list_snapshot

Test criteria:
  □ Drop real Darren newsletter PDF
  □ sunday_runner.py completes without error
  □ market_environment table has correct row
  □ watch_list_history table has correct rows (count = watch list size)
  □ raw_extractions has full JSON blob
  □ Excel opens and accepts Ctrl+Shift+Alt+F9
  □ Structure fingerprint captured
```

---

### Phase 3 — OS Processor + Broker Integration (~Week 3)
**Goal:** Full daily loop works. Holdings always current from brokers.

```
Claude Code builds:
  ✦ os_processor.py (Excel upload → os_snapshots)
  ✦ broker_reconciler.py (TradeStation + Tradier + Schwab MCPs → DB)
  ✦ webull_parser.py (CSV → dca_holdings)
  ✦ MCP write tools: write_os_snapshot, reconcile_holdings

Test criteria:
  □ Upload populated Excel → os_snapshots populated correctly
  □ Raw Excel saved to exports/os_raw/
  □ Broker reconciler runs, dca_holdings updated
  □ Discrepancy detection works (introduce test discrepancy)
  □ Webull CSV parses correctly for all transaction types
```

---

### Phase 4 — Dashboard + Write Tools (~Week 4)
**Goal:** Dashboard live. Claude can write confirmed trades to DB.

```
Claude Code builds:
  ✦ dashboard_generator.py (DB → dashboard.html, Jinja2)
  ✦ MCP write tools: write_trade_entry, write_trade_exit,
    write_dca_purchase, update_dca_status
  ✦ friday_runner.py (Friday close orchestrator)
  ✦ Write confirmation enforcement in MCP server (confirmed=True check)

Test criteria:
  □ "refresh dashboard" opens correct HTML in browser
  □ Dashboard reflects current DB state
  □ Write tool refuses without confirmed=True
  □ Full trade entry/exit cycle tested end to end
  □ friday_runner.py processes test outcomes correctly
```

---

### Phase 5 — History & Analytics (after 4+ weeks of data)

```
Claude Code builds:
  ✦ Phase 2 MCP read tools:
      get_watch_list_history, get_watch_list_streaks,
      get_watch_list_changes, get_iv_trend, get_dca_purchase_history
  ✦ dca_purchases table (Alembic migration)
  ✦ symbol_notes table (Alembic migration)
  ✦ write_symbol_note tool

Test criteria:
  □ Watch list streak analysis returns correct results
  □ IV trend shows week-over-week changes correctly
  □ Symbol notes searchable
```

---

### Phase 6 — Performance & Reporting (after 3+ months of data)

```
Claude Code builds:
  ✦ Phase 3 MCP read tools:
      get_performance_summary, get_missed_trades,
      get_symbol_profile, get_sector_exposure
  ✦ Weekly report generator (DB → structured summary)
  ✦ Dashboard Phase 3 additions (charts, sparklines)

Test criteria:
  □ Performance summary matches manual calculation
  □ Missed trades analysis correct
  □ Weekly report generates with accurate data
```

---

### Phase 7 — Cloud Migration (when ready)

```
  ✦ Swap SQLite → PostgreSQL (connection string in config only)
  ✦ Verify all SQLAlchemy models work with PostgreSQL
  ✦ Dockerize: MCP server + PostgreSQL in docker-compose.yml
  ✦ Test docker-compose locally — identical behavior confirmed
  ✦ Deploy to cloud (Railway / Fly.io / DigitalOcean)
  ✦ Add API key authentication to MCP server
  ✦ Configure Claude.ai to connect via public URL

Note: Excel + OS add-in remain local permanently.
      Cloud deployment receives OS data via Excel uploads from your machine.
      This is an accepted permanent constraint — no workaround exists.
```

---

## 16. Architect Review — Concerns Raised and Resolved

This section documents every concern raised during the architecture review, with resolution status. Preserved here so we never revisit closed debates.

---

### Concern 1 — Claude as ETL Pipeline is Fragile ✅ Resolved

**Raised:** Having Claude do PDF extraction and DB writing creates an unreliable pipeline. If Claude misreads a page, bad data enters the DB. Context window timeouts could leave the DB half-written. Claude's extraction is non-deterministic.

**Resolution:**
- Claude is explicitly NOT in the data pipeline. Agents 1–8 are pure Python, deterministic, LLM-free.
- `newsletter_parser.py` runs autonomously on the PDF file.
- `raw_extractions` table stores the full extraction blob before normalization — bad data is diagnosable.
- `warnings[]` array in extraction output surfaces issues without silent failures.
- See: Section 3 (Principle 2), Section 8 (Agent 1 error handling), Section 8 (Agent 9 explicitly does NOT do pipeline work).

---

### Concern 2 — Two Sources of Truth for Positions ✅ Resolved

**Raised:** Broker MCPs, SQLite, and Webull would drift. Three sources all claiming to know your positions.

**Resolution:**
- Clear reconciliation contract defined: Broker MCPs own current positions and quantities. SQLite owns strategy context and history. They serve different questions and never compete.
- Agent 4 reconciles on every session — not periodically.
- Discrepancies flagged, never auto-resolved.
- See: Section 3 (Principle 5), Section 8 (Agent 4 — reconciliation contract).

---

### Concern 3 — Webull Gap is Permanent ✅ Resolved

**Raised:** Screenshot parsing is fragile. UI changes break it silently. Can produce wrong data.

**Resolution:**
- Switched to CSV export — structured data, stable column names.
- If Webull changes CSV format (rare), the parser update is a small targeted fix, not a fragile vision-based reparse.
- See: Section 4 (Permanent Constraints), Section 8 (Agent 5).

---

### Concern 4 — SQLite → PostgreSQL Not Just a Config Change ✅ Resolved

**Raised:** The claim that migration is just a connection string swap is an oversimplification. SQLite and PostgreSQL have type differences, BOOL handling, DATE handling, concurrent write access differences.

**Resolution:**
- SQLAlchemy ORM throughout — every query goes through models, never raw SQL.
- Alembic for all migrations from day one (not retrofitted in Phase 7).
- PostgreSQL-compatible types used in all column definitions from the start.
- Concurrent write access (SQLite limitation) is not an issue in Phase A/B (single user, single writer). By Phase C, PostgreSQL is in place.
- See: Section 3 (Principle 7), Section 10 (Design Rules).

---

### Concern 5 — MCP Server Scope Too Broad ✅ Resolved

**Raised:** 20+ tools designed upfront. Some tools require 3+ months of data that doesn't exist at launch. Building them all at once is wasted effort and adds fragility.

**Resolution:**
- Tools explicitly phased: Phase 1 (6 read + 4 write — build immediately), Phase 2 (5 tools — needs 4+ weeks), Phase 3 (5 tools — needs 3+ months).
- Tools in later phases are defined but not built until data exists to support them.
- See: Section 11 (MCP Tool Definitions, phased by data availability).

---

### Concern 6 — Sunday Script Does Too Much ✅ Resolved

**Raised:** One script doing PDF parsing, DB writing, and Excel generation is four concerns in one. If one step fails, behavior is unclear. Not independently testable.

**Resolution:**
- Fully separated: `newsletter_parser.py` (PDF → JSON), `db_writer.py` (JSON → DB), `excel_generator.py` (DB → Excel), `sunday_runner.py` (orchestrates the three, handles errors and reports status).
- Each module is independently testable.
- If DB write fails, Excel still generates. Error is specific and diagnosable.
- See: Section 8 (Agent 1 and Agent 2 are separate), Appendix A (file structure).

---

### Concern 7 — No Audit Trail ✅ Resolved (including gap fix)

**Raised:** Without an audit trail, bad writes are undetectable and unrecoverable.

**Resolution (newsletter data):**
- `raw_extractions` table stores the complete JSON blob from every Sunday extraction before normalization.
- Every table has `source`, `session_id`, `created_at`.
- `warnings[]` array surfaces extraction issues.

**Resolution (OS snapshot data — gap identified in review):**
- Every Excel upload is saved to `~/BullStrangle/exports/os_raw/YYYYMMDD_HHMM.xlsx` before processing.
- `raw_excel_path` column in `os_snapshots` stores the path to the raw file.
- If Agent 3 misreads a column mapping, the raw Excel file is available for diagnosis.
- See: Section 10 (os_snapshots table — `raw_excel_path` column).

---

### Concern 8 — Orchestrator Not Defined ✅ Resolved

**Raised:** With 9 agents, who decides sequencing? Who retries on failure? Who alerts on partial completion?

**Resolution:**
- Python orchestrator scripts are the backbone: `sunday_runner.py` sequences Agents 1 → 2, with explicit error handling at each step.
- `friday_runner.py` sequences Friday close.
- Claude Cowork can trigger these scripts (folder watch, keyboard shortcuts) but is a convenience layer only — scripts always work when run from terminal directly.
- See: Section 3 (Principle 9), Section 5 (Cowork role), Section 8 (Agent 6 — Sunday Runner, Agent 8 — Friday Runner).

---

### Concern 9 — Event-Driven vs Poll-Driven ✅ Decision Made

**Raised:** A mature system would be event-driven (PDF detected → auto-trigger). But event-driven is harder to debug and harder to trust for trading.

**Decision:** Stay poll/manual-trigger for v1. Manual triggers are simpler to debug and trust. Event-driven automation (via Cowork folder watching) added as a convenience layer in Phase 2+, never as a dependency.

---

### Concern 10 — Dashboard Scope ✅ Resolved

**Raised:** "Dashboard" was being used to mean four different things: pre-market Monday readiness, intraweek monitoring, performance tracking, DCA pipeline view.

**Decision:** One simple dashboard, one page, four panels. Current status only. Static HTML file, manual refresh. No running server. Charts deferred to Phase 6.

---

## 17. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Newsletter parser misreads PDF | High | High | `raw_extractions` audit table + raw file. `warnings[]` array. Structure fingerprint detects format changes. Claude reviews extraction output before confirming. |
| Darren changes newsletter format | Medium | High | Structure fingerprint comparison week-over-week. Claude flags if page count or section structure differs from prior week. Parser needs update but data is not lost — raw blob preserved. |
| Excel/OS add-in is permanent local dependency | Certain | Medium | Accepted and designed around. Cloud deployment always requires local Excel machine. Not a blocker for any phase. |
| Broker MCP unavailable during session | Low | Low | Claude falls back to last known DB state. Flags that reconciliation didn't run. Session continues with stale holdings data — noted in output. |
| SQLite → PostgreSQL migration surprises | Low | Medium | SQLAlchemy ORM throughout. Alembic from day one. PostgreSQL-compatible types. Test migration in Phase 7 before going live. |
| Agent count creep | Medium | Medium | Hard rule enforced: Phase N stable before Phase N+1. 9 agents is the defined ceiling — no new agents without explicit architectural review. |
| DB write without user confirmation | Low (by design) | High | Confirmation enforced at MCP server level (confirmed=True parameter), not just in Claude instructions. Two independent enforcement layers. |
| Webull CSV format changes | Low | Low | Targeted parser fix. Raw CSV preserved alongside DB write for diagnosis. |
| OS snapshot audit gap (silent misread) | Low | Medium | Raw Excel saved to exports/os_raw/ before processing. `raw_excel_path` in os_snapshots. |
| Cowork unavailable on Sunday | Low | Low | Python scripts always runnable from terminal. Cowork is convenience, not dependency. |

---

## 18. Open Questions

Decisions needed before or during specific build phases:

| # | Question | Options | Needed by |
|---|----------|---------|-----------|
| 1 | **Sunday runner trigger** — how does the pipeline start? | A: You run `python runners/sunday_runner.py` manually. B: Cowork watches `newsletters/` folder, triggers script when PDF appears. | Before Phase 2 |
| 2 | **Newsletter parser validation** — does Claude review extraction output before it's committed to DB? | A: Parser writes directly, Claude reviews via MCP read tools after. B: Parser outputs JSON to a staging area, Claude reviews in chat, you confirm, then JSON is committed to DB. | Before Phase 2 |
| 3 | **Strategy context on broker-sourced positions** — when Agent 4 finds a new position from TradeStation that isn't in the DB, how does "this was a DCA buy targeting Bull Strangle" get attached? | Deferred to Phase 5. For now: Claude flags new positions, you confirm context in chat. | Phase 5 |
| 4 | **Schwab MCP verification** — is `schwab-smartspreads` (local) already configured and returning positions correctly? | Need to test `get_equity_positions` and `get_futures_positions` tools before Phase 3. | Before Phase 3 |
| 5 | **Dashboard trigger** — how do you refresh the dashboard? | A: "refresh dashboard" prompt in Claude chat. B: `python pipeline/dashboard_generator.py` in terminal. C: Cowork shortcut key. | Before Phase 4 |
| 6 | **Error alerting** — if `sunday_runner.py` fails partway through (e.g., parser succeeds but Excel generation fails), how are you notified? | A: Script prints to terminal (works if you're watching). B: Script writes error to a log file + Cowork sends desktop notification. | Before Phase 2 |

---

## Appendix A — File & Folder Structure

```
~/BullStrangle/
│
├── db/
│   ├── BullStrangle.db              ← SQLite database (single file)
│   └── BullStrangle_backup_YYYYMMDD.db  ← Weekly backup before each Sunday run
│
├── excel/
│   ├── BullStrangle_Template.xlsx   ← Webextension donor (never modify, never delete)
│   └── BullStrangle_YYYYMMDD.xlsx  ← Generated each Sunday (download only)
│
├── newsletters/
│   └── DarrenNewsletter_YYYYMMDD.pdf   ← Drop PDFs here
│
├── exports/
│   ├── webull_YYYYMMDD.csv          ← Drop Webull CSVs here
│   └── os_raw/
│       └── YYYYMMDD_HHMM.xlsx       ← Raw Excel saved before OS processing (audit)
│
├── dashboard/
│   └── dashboard.html               ← Regenerated on demand, open in browser
│
├── mcp_server/
│   ├── server.py                    ← MCP server entry point (always running)
│   ├── config.py                    ← DB connection string (SQLite now, Postgres later)
│   ├── tools/
│   │   ├── read_tools.py            ← All get_* functions
│   │   └── write_tools.py           ← All write_* functions + confirmation enforcement
│   ├── models/
│   │   └── schema.py                ← SQLAlchemy ORM models
│   └── migrations/
│       ├── env.py                   ← Alembic environment
│       ├── script.py.mako           ← Migration template
│       └── versions/
│           └── 001_initial_schema.py  ← First migration
│
├── pipeline/
│   ├── newsletter_parser.py         ← Agent 1: PDF → structured JSON
│   ├── excel_generator.py           ← Agent 2: DB → 1-tab Excel
│   ├── os_processor.py              ← Agent 3: Excel upload → os_snapshots
│   ├── broker_reconciler.py         ← Agent 4: Broker MCPs → dca_holdings
│   ├── webull_parser.py             ← Agent 5: Webull CSV → dca_holdings
│   └── dashboard_generator.py      ← Agent 6: DB → dashboard.html
│
├── runners/
│   ├── sunday_runner.py             ← Orchestrates Agents 1 → 2
│   └── friday_runner.py            ← Orchestrates Friday close (Agent 8)
│
├── logs/
│   └── YYYYMMDD_sunday_run.log     ← Pipeline run logs
│
├── tests/
│   ├── test_schema.py
│   ├── test_newsletter_parser.py
│   ├── test_excel_generator.py
│   └── test_mcp_tools.py
│
└── README.md                        ← Setup instructions, how to run each phase
```

---

## Appendix B — What the DB Enables That Excel Cannot

Once even 4–6 weeks of data exists, Claude can answer these questions instantly from any session with no file upload:

**Watch List Intelligence**
- "Which symbols have been on Darren's list for 3+ consecutive weeks?" (conviction signal)
- "When did CSCO first appear on the list?"
- "What symbols dropped off this week vs last week — and why?"
- "Has Darren ever put XLE on the small short list while it was also on the large list?"

**IV & Screening Trends**
- "Is IV for SU expanding or compressing over the last 8 weeks?"
- "Which names had IV-RV percentile > 60% consistently for the last 4 weeks?"
- "When CSCO was TRADE? YES, what was its IV vs when it was TRADE? NO?"

**DCA & Position History**
- "What's our blended cost basis for SU across all lots?"
- "When we bought HP at $35.64, what was the MA count? Were we buying into deteriorating trend?"
- "Which DCA names are closest to reaching 100 shares?"

**Trade Performance**
- "What is our actual win rate vs Darren's reported 71%?"
- "Which sectors have our best and worst win rates?"
- "When we entered in Moderate environment vs Full environment, did outcomes differ?"
- "Which names did we skip that were TRADE? YES — what happened to their prices?"

**Market Regime Patterns**
- "How many weeks were we in Defensive before the last re-entry?"
- "Which watch list names consistently appeared during Defensive periods?"
- "What was the average Hybrid Score trajectory 4 weeks before re-entry in prior cycles?"

---

## Appendix C — Glossary

| Term | Definition |
|------|------------|
| **Agent** | A Python script or Claude instance with a single, bounded responsibility. Agents communicate only through Agent 7 (MCP Server). |
| **MCP Server** | Model Context Protocol server — exposes tools Claude can call directly. Agent 7 in this system. |
| **OS** | OptionSamurai — the options screener Excel/Sheets add-in providing live UDF data |
| **NL Price** | Newsletter price — Friday closing price as reported in Darren's newsletter. Written to `watch_list_history` by Agent 1. |
| **OS Snapshot** | Live OptionSamurai values captured at a specific moment from the uploaded Excel. Written to `os_snapshots` by Agent 3. |
| **Deviations** | Comparison of live OS values (from `os_snapshots`) vs NL prices (from `watch_list_history`) to flag significant moves between newsletter Friday close and current prices. Calculated by Claude in chat. |
| **Hybrid Score** | Darren's composite market environment score (−3 to +3) combining trend, VIX, and breadth components. |
| **Re-entry Criteria** | All 4 must pass simultaneously: (1) Hybrid ≥ 0 for 2 consecutive weeks, (2) S&P above 200-DMA, (3) VIX < 25, (4) Breadth > 40%. |
| **DCA** | Dollar Cost Averaging — accumulating shares incrementally over multiple days/weeks to build toward a 100-share strangle position. |
| **Graduated** | A DCA position that has reached ≥100 shares and meets all other eligibility criteria — ready for strangle deployment when environment turns Moderate+. |
| **ZIP Surgery** | Process of preserving OptionSamurai webextension registration files when building/modifying Excel workbooks via openpyxl (which would otherwise strip them). Still required for the 1-tab Excel. |
| **ETL** | Extract, Transform, Load — the deterministic data pipeline process (Agents 1–8). |
| **ORM** | Object Relational Mapper — SQLAlchemy layer that abstracts SQL queries into Python objects. Used throughout so PostgreSQL migration requires no code changes. |
| **Alembic** | Python database migration tool used alongside SQLAlchemy. All schema changes go through Alembic from day one. |
| **Structure Fingerprint** | A hash or signature of the newsletter's structure (page count, section headings, table counts) generated each Sunday to detect when Darren changes his newsletter format. |
| **Write Confirmation Protocol** | The rule that Claude must state exactly what it will write and receive explicit "yes" from you before calling any MCP write tool. Enforced at the MCP server level (confirmed=True parameter). |
| **Loose Coupling** | The architectural principle that no agent communicates directly with another. All inter-agent communication goes through the shared data hub (Agent 7). |
| **Reconciliation Contract** | The defined agreement that broker MCPs are authoritative for current positions/quantities, while SQLite is authoritative for strategy context and history. These never compete. |

---

*Document ends. Version 2.0.*  
*Next action: Balaji reviews, resolves Open Questions (Section 18), then Phase 1 build begins in Claude Code.*  
*First Claude Code prompt: Build SQLite schema + MCP server skeleton. See Section 15 Phase 1 for exact spec.*
