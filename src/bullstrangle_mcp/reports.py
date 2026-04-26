"""Report generation for the Bull Strangle Newsletter MCP.

Implements the weekly action plan and daily brief reports described in
the architecture spec (Section 6).  Reports are rendered as Markdown
strings and optionally written to disk.  Generated reports are logged in
the generated_reports table so they can be retrieved later.

Phase 7 update: reports now pull from the live gate engine (entry_decisions),
exit engine (exit_decisions), and position book (cycle_layers) instead of the
deprecated v1 decision_batches / bull_strangle_decisions tables.

Table dependencies (created via migration _m002 and _m003 in database.py):
  - generated_reports
  - report_subscriptions  (reserved for future scheduling)
  - entry_decisions        (Phase 7 — gate engine output)
  - exit_decisions         (Phase 7 — exit engine output)
  - cycle_layers           (Phase 7 — open position book)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database


# ── Weekly Action Plan ────────────────────────────────────────────────────────


def generate_weekly_action_plan(
    newsletter_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the Sunday weekly action plan report for one newsletter date.

    Sections:
      1. Market Environment Status
      2. Re-Entry Criteria Table
      3. DCA Candidate Updates (Short List)
      4. Gate Validation Summary  ← Phase 7: entry_decisions
      5. Active Positions This Cycle  ← Phase 7: cycle_layers
      6. Watch List Analysis
      7. WL Favorites Deep Analysis
      8. Action Items
      9. Key Reminders
      10. Next Sunday Workflow
      11. Appendix
    """
    initialize_database(db_path)
    today = date.today().isoformat()

    with connect(db_path) as conn:
        newsletter = _require_newsletter(conn, newsletter_date)
        env = _fetch_env(conn, newsletter["newsletter_id"])
        wd = _fetch_weekly_decision(conn, newsletter["newsletter_id"])
        watchlist = _fetch_watchlist(conn, newsletter["newsletter_id"])
        short_list = _fetch_short_list(conn, newsletter["newsletter_id"])
        deep_analysis = _fetch_deep_analysis(conn, newsletter["newsletter_id"])
        entry_decisions = _fetch_entry_decisions_latest(conn, newsletter["newsletter_id"])
        active_layers = _fetch_active_layers_for_newsletter(conn, newsletter["newsletter_id"], today)

    ctx = {
        "newsletter": newsletter,
        "env": env,
        "wd": wd,
        "watchlist": watchlist,
        "short_list": short_list,
        "deep_analysis": deep_analysis,
        "entry_decisions": entry_decisions,
        "active_layers": active_layers,
        "today": today,
    }
    markdown = _render_weekly_action_plan(ctx)

    _save_report(
        db_path,
        report_type="weekly_action_plan",
        newsletter_id=newsletter["newsletter_id"],
        report_date=today,
        markdown=markdown,
        data_snapshot={
            "newsletter_date": newsletter_date,
            "env": env,
            "active_layers": len(active_layers),
            "gate_decisions": len(entry_decisions),
        },
        output_path=output_path,
    )

    result: dict[str, Any] = {
        "report_type": "weekly_action_plan",
        "newsletter_date": newsletter_date,
        "generated_date": today,
        "markdown": markdown,
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        result["output_path"] = str(out.resolve())
    return result


def _render_weekly_action_plan(ctx: dict[str, Any]) -> str:
    env = ctx["env"]
    wd = ctx["wd"]
    newsletter = ctx["newsletter"]
    watchlist = ctx["watchlist"]
    short_list = ctx["short_list"]
    deep_analysis = ctx["deep_analysis"]
    entry_decisions = ctx["entry_decisions"]  # list of dicts from entry_decisions table
    active_layers = ctx["active_layers"]
    today = ctx["today"]

    approved_marker = "✅" if env.get("deployment_approved") else "⚠️"
    consecutive = env.get("consecutive_weeks_met") or 0
    action = wd.get("action_taken", "monitor_only") if wd else "unknown"
    market_status = env.get("market_status", "unknown").upper()
    status_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(market_status, "⚪")

    # Categorise gate decisions
    gate_pass = [d for d in entry_decisions if d["decision_type"] == "BULL_STRANGLE"]
    gate_watch = [d for d in entry_decisions if d["decision_type"] == "WATCH"]
    gate_skip = [d for d in entry_decisions if d["decision_type"] == "SKIP"]

    # Short list sets for alignment check
    sl_symbols = {r["symbol"] for r in short_list}

    lines: list[str] = [
        f"# Bull Strangle Strategy — {newsletter['publication_date']}",
        "",
        f"**Generated:** {today}  ",
        f"**Cycle:** {newsletter['publication_date']} entry / {newsletter.get('target_expiration', 'TBD')} expiration  ",
        f"**Environment:** Week {consecutive} of 2 under 2-consecutive-week rule  ",
        f"**Status:** {action.replace('_', ' ').title()}  ",
        "",
        "---",
        "",
        # ── Section 1 ──
        "## 1. MARKET ENVIRONMENT STATUS",
        "",
        f"**{approved_marker} WEEK {consecutive} OF 2**",
        "",
        f"### Current Metrics ({newsletter['publication_date']})",
        f"- **Hybrid Score:** {env.get('hybrid_score', 'N/A')} {status_emoji}",
        f"- **Market Status:** {market_status}",
        f"- **Investment %:** {env.get('investment_percent', 'N/A')}%",
        f"- **S&P 500:** {_fmt(env.get('sp500_price'))} vs 200-DMA {_fmt(env.get('sp500_200dma'))} "
        f"({'✅ Above' if env.get('sp500_above_200dma') else '❌ Below'})",
        f"- **VIX:** {_fmt(env.get('vix'))} ({'✅ < 25' if env.get('vix_below_25') else '❌ ≥ 25'})",
        f"- **Breadth:** {_fmt(env.get('breadth_pct'))}% ({'✅ > 40%' if env.get('breadth_above_40') else '❌ ≤ 40%'})",
        f"- **Scaling Phase:** {env.get('scaling_phase', 'N/A')}",
        f"- **Recommended Positions:** {env.get('recommended_position_count', 0)}",
        "",
        # ── Section 2 ──
        "## 2. RE-ENTRY CRITERIA STATUS",
        "",
        "| Criterion | Status | Current | Target |",
        "|-----------|--------|---------|--------|",
        f"| Hybrid Score ≥ 0 | {'✅ Pass' if env.get('hybrid_bullish') else '❌ Fail'} | {env.get('hybrid_score', 'N/A')} | ≥ 0 |",
        f"| S&P 500 > 200-DMA | {'✅ Pass' if env.get('sp500_above_200dma') else '❌ Fail'} | {_fmt(env.get('sp500_price'))} | > {_fmt(env.get('sp500_200dma'))} |",
        f"| VIX < 25 | {'✅ Pass' if env.get('vix_below_25') else '❌ Fail'} | {_fmt(env.get('vix'))} | < 25 |",
        f"| Breadth > 40% | {'✅ Pass' if env.get('breadth_above_40') else '❌ Fail'} | {_fmt(env.get('breadth_pct'))}% | > 40% |",
        f"| Consecutive Weeks | {'✅ Met' if consecutive >= 2 else '⏳ Pending'} | {consecutive} | 2 |",
        "",
        # ── Section 3 ──
        "## 3. DCA CANDIDATE UPDATES",
        "",
    ]

    if short_list:
        lines += [
            "| Rank | Symbol | Portfolio | Price | IV | Sector |",
            "|------|--------|-----------|-------|----|--------|",
        ]
        for row in short_list[:10]:
            lines.append(
                f"| {row.get('rank', '')} | **{row['symbol']}** | {row.get('portfolio_type', '')} "
                f"| {_fmt_price(row.get('stock_price'))} | {_fmt_pct(row.get('implied_volatility'))} "
                f"| {row.get('sector', '')} |"
            )
    else:
        lines.append("*No DCA candidates extracted for this newsletter.*")

    # ── Section 4 — Gate Validation Summary ──────────────────────────────────
    lines += [
        "",
        "## 4. GATE VALIDATION SUMMARY",
        "",
    ]

    if entry_decisions:
        # Short list alignment
        sl_pass = [d for d in gate_pass if d["symbol"] in sl_symbols]
        sl_total = len(sl_symbols)
        alignment_pct = round(len(sl_pass) / sl_total * 100) if sl_total else 0

        lines += [
            f"- **Symbols evaluated:** {len(entry_decisions)}",
            f"- **Passed all gates (BULL_STRANGLE):** {len(gate_pass)}",
            f"- **Watch (soft gate miss):** {len(gate_watch)}",
            f"- **Skip (hard gate fail):** {len(gate_skip)}",
            f"- **Short List gate alignment:** {len(sl_pass)}/{sl_total} ({alignment_pct}%)",
            "",
        ]

        if gate_pass:
            lines += ["### ✅ Passed All Gates — BULL_STRANGLE Eligible", ""]
            lines += [
                "| Symbol | Live Price | IV | Credit | Call Strike | Put Strike | Short List |",
                "|--------|------------|----|----|-------------|------------|------------|",
            ]
            for d in gate_pass:
                sl_marker = "⭐" if d["symbol"] in sl_symbols else ""
                lines.append(
                    f"| **{d['symbol']}** {sl_marker} "
                    f"| {_fmt_price(d.get('live_stock_price'))} "
                    f"| {_fmt_pct(d.get('live_iv'))} "
                    f"| {_fmt_price(d.get('live_total_credit'))} "
                    f"| {_fmt(d.get('live_call_strike'))} "
                    f"| {_fmt(d.get('live_put_strike'))} "
                    f"| {sl_marker} |"
                )
            lines.append("")

        if gate_watch:
            lines += ["### 👀 Watch — Soft Gate Miss", ""]
            lines += ["| Symbol | First Failing Gate | Short List |", "|--------|--------------------|------------|"]
            for d in gate_watch:
                sl_marker = "⭐" if d["symbol"] in sl_symbols else ""
                lines.append(
                    f"| {d['symbol']} | {d.get('first_failing_gate') or 'soft gate'} | {sl_marker} |"
                )
            lines.append("")

        # Gate failure breakdown
        fail_counts: dict[str, list[str]] = {}
        for d in gate_skip:
            gate = d.get("first_failing_gate") or "unknown"
            fail_counts.setdefault(gate, []).append(d["symbol"])
        if fail_counts:
            lines += ["### ❌ Hard Gate Failures", ""]
            lines += ["| Gate | Count | Symbols |", "|------|-------|---------|"]
            for gate, syms in sorted(fail_counts.items()):
                lines.append(f"| {gate} | {len(syms)} | {', '.join(syms)} |")
            lines.append("")

        # Short list symbols that failed gates
        sl_fail = [d for d in (gate_watch + gate_skip) if d["symbol"] in sl_symbols]
        if sl_fail:
            lines += ["### ⚠️ Short List Symbols That Failed Gates", ""]
            for d in sl_fail:
                gate = d.get("first_failing_gate") or "soft gate"
                lines.append(f"- **{d['symbol']}** ⭐ failed {gate}")
            lines.append("")
    else:
        lines += [
            "*No gate evaluations found for this newsletter. Run:*",
            f"```",
            f"bullstrangle --db <db> evaluate-newsletter {newsletter['publication_date']}",
            f"```",
            "",
        ]

    # ── Section 5 — Active Positions This Cycle ───────────────────────────────
    lines += ["## 5. ACTIVE POSITIONS THIS CYCLE", ""]

    if active_layers:
        total_credit = sum(r.get("total_credit_collected") or 0 for r in active_layers)
        total_capital = sum(r.get("invested_capital") or 0 for r in active_layers)
        lines += [
            f"- **Open positions:** {len(active_layers)}",
            f"- **Total credit collected:** {_fmt_price(total_credit)}",
            f"- **Capital at risk:** {_fmt_price(total_capital)}",
            "",
            "| Symbol | Account | Expiry | DTE | Entry | Call | Put | Credit | Capital |",
            "|--------|---------|--------|-----|-------|------|-----|--------|---------|",
        ]
        for r in active_layers:
            dte = r.get("dte")
            dte_str = f"{int(dte)}d" if dte is not None else "?"
            dte_flag = " ⚠️" if dte is not None and dte <= 7 else ""
            lines.append(
                f"| **{r['symbol']}** | {r.get('account_id', '')} "
                f"| {r.get('expiration_date', '')} | {dte_str}{dte_flag} "
                f"| {_fmt_price(r.get('stock_price_at_entry'))} "
                f"| {_fmt(r.get('call_strike'))} "
                f"| {_fmt(r.get('put_strike'))} "
                f"| {_fmt_price(r.get('total_credit_collected'))} "
                f"| {_fmt_price(r.get('invested_capital'))} |"
            )
        lines.append("")
    else:
        lines.append(
            "*No active positions for this newsletter week. "
            "Seed positions with: `seed-cycle-layers`*"
        )
        lines.append("")

    # ── Section 6 — Watch List Analysis ──────────────────────────────────────
    lines += [
        "## 6. WATCH LIST ANALYSIS",
        "",
        "| # | Symbol | Price | IV | Sector | Fav | Call | Put | Credit% |",
        "|---|--------|-------|----|--------|-----|------|-----|---------|",
    ]
    for i, row in enumerate(watchlist, 1):
        fav = "⭐" if row.get("is_favorite") else ""
        lines.append(
            f"| {i} | **{row['symbol']}** | {_fmt_price(row.get('stock_price'))} "
            f"| {_fmt_pct(row.get('implied_volatility'))} | {row.get('sector', '')} | {fav} "
            f"| {_fmt(row.get('sell_call_strike'))} | {_fmt(row.get('sell_put_strike'))} "
            f"| {_fmt_pct(row.get('bull_strangle_return_pct'))} |"
        )

    # ── Section 7 — WL Favorites ─────────────────────────────────────────────
    lines += ["", "## 7. WL FAVORITES — DEEP ANALYSIS", ""]
    if deep_analysis:
        for sym, da in deep_analysis.items():
            analysis = da.get("analysis_data") or {}
            lines += [f"### {sym}", "", f"**Rank:** {da.get('favorite_rank', '?')}  "]
            if isinstance(analysis, dict):
                company = analysis.get("company_name") or analysis.get("sector") or ""
                if company:
                    lines.append(f"**Company:** {company}  ")
                summary = analysis.get("source_summary") or ""
                if summary:
                    lines.append("")
                    lines.append(summary[:500].strip() + ("..." if len(summary) > 500 else ""))
                trade = analysis.get("proposed_trade") or {}
                if trade:
                    stock = trade.get("stock") or {}
                    call = trade.get("sell_call") or {}
                    put = trade.get("sell_put") or {}
                    buy_put = trade.get("buy_put") or {}
                    summary_trade = trade.get("summary") or {}
                    lines += [
                        "",
                        "**Proposed Trade:**",
                        f"- Stock: {stock.get('shares', 100)} shares @ ${_fmt(stock.get('price'))}",
                        f"- Sell Call: ${_fmt(call.get('strike'))} for ${_fmt(call.get('premium'))}",
                        f"- Sell Put: ${_fmt(put.get('strike'))} for ${_fmt(put.get('premium'))}",
                        f"- Buy Put: ${_fmt(buy_put.get('strike'))} for ${_fmt(buy_put.get('premium'))}",
                    ]
                    if summary_trade:
                        lines.append(
                            f"- Total Investment: ${summary_trade.get('total_investment', 'N/A')} | "
                            f"Max Gain: {summary_trade.get('max_gain_pct', 'N/A')}%"
                        )
            lines.append("")
    else:
        lines.append("*No WL Favorites deep analysis available for this newsletter.*")
        lines.append("")

    # ── Section 8 — Action Items ──────────────────────────────────────────────
    lines += ["## 8. ACTION ITEMS", "", "### This Week"]
    if env.get("deployment_approved"):
        if gate_pass:
            lines += [
                f"- [ ] {len(gate_pass)} symbol(s) cleared all gates: "
                f"{', '.join(d['symbol'] for d in gate_pass[:8])}",
                "- [ ] Confirm position sizing and execute via broker",
                "- [ ] Open Excel workbook, refresh Option Samurai, ingest via daily-ingest",
                "- [ ] Update position tracker after execution",
            ]
        else:
            lines += [
                "- [ ] Deployment approved but 0 symbols cleared all gates — review gate failures above",
                "- [ ] Check Gate 9 (live credit) — may need OS data refresh",
            ]
    elif env.get("all_criteria_met"):
        lines += [
            "- [ ] Monitor — Week 1 of confirmation, do NOT deploy new strangles",
            "- [ ] Continue tracking DCA accumulation candidates",
            "- [ ] Prepare Excel workbook for next week if criteria hold",
        ]
    else:
        lines += [
            "- [ ] Market criteria NOT met — no new strangle deployments",
            "- [ ] Review exit criteria for any existing open positions",
            "- [ ] Monitor DCA candidates for accumulation at favorable prices",
        ]

    if active_layers:
        expiring_soon = [r for r in active_layers if (r.get("dte") or 999) <= 7]
        if expiring_soon:
            lines.append(
                f"- [ ] ⚠️ {len(expiring_soon)} position(s) expire within 7 days: "
                f"{', '.join(r['symbol'] for r in expiring_soon)} — review exit report"
            )

    lines += [
        "",
        "### Next Week",
        f"- [ ] Await next newsletter (approx. {newsletter.get('publication_date')} + 7 days)",
        "- [ ] Verify market criteria status again",
        "- [ ] Review any open positions approaching expiration",
        "",
        # ── Section 9 ──
        "## 9. KEY REMINDERS",
        "",
        "- **2-Consecutive-Week Rule:** All 4 criteria must be met for 2 consecutive weeks before deploying",
        "- **100-Share Requirement:** Bull Strangle requires exactly 100 shares per position",
        "- **Earnings Safety:** Avoid symbols with earnings before option expiration",
        "- **Exit at 50%:** Close positions when 50% of max profit is reached",
        "- **Stock Called Away:** Close naked puts for small debit; let calls expire",
        "",
        # ── Section 10 ──
        "## 10. NEXT SUNDAY WORKFLOW",
        "",
        "```",
        "1. Drop Darren's PDF into data/newsletters/",
        "2. Run: bullstrangle --db <db> weekend-setup <date> --pdf <path>",
        "   (ingests PDF + generates OS workbook + copies to data/os_uploads/)",
        "3. Open data/os_uploads/BullStrangle_OS_Live_<date>.xlsx in Excel",
        "4. Enable Option Samurai add-in → Ctrl+Shift+Alt+F9 to refresh → Save",
        "5. Run: bullstrangle --db <db> daily-ingest <date> --trading-date <date>",
        "   (ingests OS data + generates run report in outputs/reports/)",
        "6. Run: bullstrangle --db <db> gate-report <date>",
        "7. Run: bullstrangle --db <db> generate-weekend-decisions <date>",
        "8. Run: bullstrangle --db <db> generate-weekly-action-plan <date>",
        "```",
        "",
        # ── Section 11 ──
        "## 11. APPENDIX — DATA NOTES",
        "",
        f"- Newsletter ingested: {newsletter.get('publication_date')}",
        f"- Watchlist symbols: {len(watchlist)}",
        f"- Short-list DCA candidates: {len(short_list)}",
        f"- Gate evaluations available: {len(entry_decisions)}",
        f"- Active positions this cycle: {len(active_layers)}",
        f"- WL Favorites with deep analysis: {len(deep_analysis)}",
        f"- Report generated: {today}",
        "",
        "---",
        f"*Generated by BullStrangle MCP — {today}*",
    ]
    return "\n".join(lines) + "\n"


# ── Daily Brief ───────────────────────────────────────────────────────────────


def generate_daily_brief(
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Generate a daily morning monitoring brief.

    Sections:
      1. Market Environment
      2. Active Cycles + Open Positions  ← Phase 7: cycle_layers
      3. Exit Alerts  ← Phase 7: exit_decisions
      4. Gate Status (latest newsletter)  ← Phase 7: entry_decisions
      5. Deployment Guidance
    """
    initialize_database(db_path)
    today = date.today().isoformat()

    with connect(db_path) as conn:
        env = _fetch_latest_env(conn)
        active_cycles = _fetch_active_cycles(conn, today)
        all_active_layers = _fetch_all_active_layers(conn, today)
        exit_alerts = _fetch_exit_alerts(conn)
        latest_entry_decisions = _fetch_latest_newsletter_entry_decisions(conn)

    markdown = _render_daily_brief(
        today, env, active_cycles, all_active_layers, exit_alerts, latest_entry_decisions
    )

    _save_report(
        db_path,
        report_type="daily_brief",
        newsletter_id=env.get("newsletter_id") if env else None,
        report_date=today,
        markdown=markdown,
        data_snapshot={
            "env": env,
            "active_cycles": len(active_cycles),
            "open_positions": len(all_active_layers),
            "exit_alerts": len(exit_alerts),
        },
        output_path=output_path,
    )

    result: dict[str, Any] = {
        "report_type": "daily_brief",
        "generated_date": today,
        "markdown": markdown,
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        result["output_path"] = str(out.resolve())
    return result


def _render_daily_brief(
    today: str,
    env: dict[str, Any] | None,
    active_cycles: list[dict[str, Any]],
    all_active_layers: list[dict[str, Any]],
    exit_alerts: list[dict[str, Any]],
    latest_entry_decisions: list[dict[str, Any]],
) -> str:
    lines: list[str] = [
        f"# Bull Strangle Daily Brief — {today}",
        "",
        "---",
        "",
        "## 1. MARKET ENVIRONMENT",
        "",
    ]
    if env:
        market_status = (env.get("market_status") or "unknown").upper()
        status_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(market_status, "⚪")
        approved_flag = "✅ APPROVED" if env.get("deployment_approved") else "⏳ NOT APPROVED"
        consecutive = env.get("consecutive_weeks_met") or 0
        lines += [
            f"**Status:** {status_emoji} {market_status}  ",
            f"**Deployment:** {approved_flag}  ",
            f"**Hybrid Score:** {env.get('hybrid_score', 'N/A')} | "
            f"**Consecutive Weeks:** {consecutive}/2 | "
            f"**VIX:** {_fmt(env.get('vix'))} | "
            f"**Breadth:** {_fmt(env.get('breadth_pct'))}%  ",
            f"**As of:** {env.get('publication_date', 'N/A')}",
            "",
        ]
    else:
        lines += ["*No market environment data available.*", ""]

    # ── Section 2 — Active Cycles + Open Positions ────────────────────────────
    lines += ["## 2. ACTIVE CYCLES & OPEN POSITIONS", ""]

    if active_cycles:
        lines += [
            "| Newsletter | Expiration | DTE | Status | Symbols |",
            "|------------|------------|-----|--------|---------|",
        ]
        for row in active_cycles:
            days_left = row.get("days_until_expiration")
            dte_str = f"{int(days_left)}d" if days_left is not None else "?"
            alert = " ⚠️" if days_left is not None and days_left <= 7 else ""
            lines.append(
                f"| {row['publication_date']} | {row.get('target_expiration', 'N/A')} "
                f"| {dte_str}{alert} | {(row.get('market_status') or '').upper()} "
                f"| {row.get('watchlist_count', 0)} |"
            )
        lines.append("")
    else:
        lines.append("*No active newsletter cycles.*")
        lines.append("")

    if all_active_layers:
        total_capital = sum(r.get("invested_capital") or 0 for r in all_active_layers)
        total_credit = sum(r.get("total_credit_collected") or 0 for r in all_active_layers)
        expiring_soon = [r for r in all_active_layers if (r.get("dte") or 999) <= 7]

        lines += [
            f"**Open positions:** {len(all_active_layers)} | "
            f"**Capital at risk:** {_fmt_price(total_capital)} | "
            f"**Total credit collected:** {_fmt_price(total_credit)}",
            "",
        ]

        if expiring_soon:
            lines += [f"⚠️ **{len(expiring_soon)} position(s) expire within 7 days:**", ""]
            for r in expiring_soon:
                dte = int(r.get("dte") or 0)
                lines.append(
                    f"- **{r['symbol']}** — exp {r.get('expiration_date')} ({dte}d) | "
                    f"call {_fmt(r.get('call_strike'))} / put {_fmt(r.get('put_strike'))} | "
                    f"entry {_fmt_price(r.get('stock_price_at_entry'))}"
                )
            lines.append("")

        lines += [
            "| Symbol | Newsletter | Expiry | DTE | Entry | Call | Put | Credit | Capital |",
            "|--------|------------|--------|-----|-------|------|-----|--------|---------|",
        ]
        for r in all_active_layers:
            dte = r.get("dte")
            dte_str = f"{int(dte)}d" if dte is not None else "?"
            dte_flag = " ⚠️" if dte is not None and dte <= 7 else ""
            lines.append(
                f"| **{r['symbol']}** | {r.get('newsletter_date', '')} "
                f"| {r.get('expiration_date', '')} | {dte_str}{dte_flag} "
                f"| {_fmt_price(r.get('stock_price_at_entry'))} "
                f"| {_fmt(r.get('call_strike'))} "
                f"| {_fmt(r.get('put_strike'))} "
                f"| {_fmt_price(r.get('total_credit_collected'))} "
                f"| {_fmt_price(r.get('invested_capital'))} |"
            )
        lines.append("")
    else:
        lines.append("*No open positions (cycle_layers) in the position book.*")
        lines.append("")

    # ── Section 3 — Exit Alerts ───────────────────────────────────────────────
    lines += ["## 3. EXIT ALERTS", ""]

    immediate = [a for a in exit_alerts if a["recommended_action"] == "CLOSE_IMMEDIATELY"]
    exit_mon = [a for a in exit_alerts if a["recommended_action"] == "EXIT_MONDAY"]
    review = [a for a in exit_alerts if a["recommended_action"] == "REVIEW"]

    if immediate:
        lines += [f"### 🚨 CLOSE IMMEDIATELY ({len(immediate)})", ""]
        for a in immediate:
            lines.append(
                f"- **{a['symbol']}** (layer {a['layer_id']}) — {a['action_reason']} "
                f"| eval {a['evaluation_date']}"
            )
        lines.append("")

    if exit_mon:
        lines += [f"### ⚠️ EXIT MONDAY ({len(exit_mon)})", ""]
        for a in exit_mon:
            lines.append(
                f"- **{a['symbol']}** (layer {a['layer_id']}) — {a['action_reason']} "
                f"| eval {a['evaluation_date']}"
            )
        lines.append("")

    if review:
        lines += [f"### 👀 REVIEW ({len(review)})", ""]
        for a in review[:10]:  # cap at 10 to avoid overwhelming the brief
            lines.append(
                f"- **{a['symbol']}** — {a['action_reason']} "
                f"| eval {a['evaluation_date']}"
            )
        if len(review) > 10:
            lines.append(f"- *...and {len(review) - 10} more — run exit-report for full list*")
        lines.append("")

    if not immediate and not exit_mon and not review:
        lines.append("*No active exit alerts. Run `exit-report` to refresh.*")
        lines.append("")

    # ── Section 4 — Gate Status (latest newsletter) ───────────────────────────
    lines += ["## 4. GATE STATUS — LATEST NEWSLETTER", ""]

    if latest_entry_decisions:
        newsletter_date = latest_entry_decisions[0].get("newsletter_date", "unknown")
        gate_pass = [d for d in latest_entry_decisions if d["decision_type"] == "BULL_STRANGLE"]
        gate_watch = [d for d in latest_entry_decisions if d["decision_type"] == "WATCH"]
        gate_skip = [d for d in latest_entry_decisions if d["decision_type"] == "SKIP"]

        lines += [
            f"**Newsletter:** {newsletter_date}",
            f"- ✅ Passed all gates: {len(gate_pass)} symbols"
            + (f" — {', '.join(d['symbol'] for d in gate_pass[:6])}" if gate_pass else ""),
            f"- 👀 Watch: {len(gate_watch)} symbols",
            f"- ❌ Skip: {len(gate_skip)} symbols",
            "",
        ]

        if gate_pass:
            lines += [
                "| Symbol | Live Price | Credit | Call | Put |",
                "|--------|------------|--------|------|-----|",
            ]
            for d in gate_pass:
                lines.append(
                    f"| **{d['symbol']}** "
                    f"| {_fmt_price(d.get('live_stock_price'))} "
                    f"| {_fmt_price(d.get('live_total_credit'))} "
                    f"| {_fmt(d.get('live_call_strike'))} "
                    f"| {_fmt(d.get('live_put_strike'))} |"
                )
            lines.append("")
    else:
        lines += [
            "*No gate evaluations found. Run:*",
            "```",
            "bullstrangle --db <db> evaluate-newsletter <date>",
            "```",
            "",
        ]

    # ── Section 5 — Deployment Guidance ──────────────────────────────────────
    lines += ["## 5. DEPLOYMENT GUIDANCE", ""]

    dep_alerts: list[str] = []

    # Expiration alerts from active cycles
    for row in active_cycles:
        days_left = row.get("days_until_expiration")
        if days_left is not None and days_left <= 3:
            dep_alerts.append(
                f"🚨 **URGENT:** {row['publication_date']} cycle expires in {int(days_left)}d "
                f"({row.get('target_expiration')}) — close or roll positions today"
            )
        elif days_left is not None and days_left <= 7:
            dep_alerts.append(
                f"⚠️ **{row['publication_date']}** cycle expires in {int(days_left)}d "
                f"({row.get('target_expiration')}) — review open positions"
            )

    if env and not env.get("deployment_approved"):
        if env.get("all_criteria_met"):
            consecutive = env.get("consecutive_weeks_met") or 0
            dep_alerts.append(
                f"⏳ Market Week {consecutive}/2 — hold off new strangles until next newsletter confirms"
            )
        else:
            dep_alerts.append("🔴 Market criteria NOT met — no new strangle deployments")
    elif env and env.get("deployment_approved"):
        dep_alerts.append("✅ Deployment approved — gate-eligible symbols listed in Section 4")

    if dep_alerts:
        for alert in dep_alerts:
            lines.append(f"- {alert}")
    else:
        lines.append("- No active deployment alerts.")

    lines += [
        "",
        "---",
        f"*Generated by BullStrangle MCP — {today}*",
    ]
    return "\n".join(lines) + "\n"


# ── DB helpers ────────────────────────────────────────────────────────────────


def _require_newsletter(conn, newsletter_date: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM newsletters WHERE publication_date = ?", (newsletter_date,)
    ).fetchone()
    if not row:
        raise ValueError(f"Newsletter not found for date: {newsletter_date}")
    return dict(row)


def _fetch_env(conn, newsletter_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM market_environment WHERE newsletter_id = ?", (newsletter_id,)
    ).fetchone()
    return dict(row) if row else {}


def _fetch_latest_env(conn) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM market_environment ORDER BY publication_date DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def _fetch_weekly_decision(conn, newsletter_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM weekly_decisions WHERE newsletter_id = ?", (newsletter_id,)
    ).fetchone()
    return dict(row) if row else None


def _fetch_watchlist(conn, newsletter_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM watchlist_entries WHERE newsletter_id = ? ORDER BY is_favorite DESC, symbol",
        (newsletter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_short_list(conn, newsletter_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT sl.*, we.stock_price, we.implied_volatility, we.sector
        FROM short_list_entries sl
        LEFT JOIN watchlist_entries we
          ON we.newsletter_id = sl.newsletter_id AND we.symbol = sl.symbol
        WHERE sl.newsletter_id = ?
        ORDER BY sl.portfolio_type, sl.rank
        """,
        (newsletter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_deep_analysis(conn, newsletter_id: int) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT * FROM watchlist_deep_analysis WHERE newsletter_id = ? ORDER BY favorite_rank",
        (newsletter_id,),
    ).fetchall()
    result = {}
    for row in rows:
        d = dict(row)
        sym = d["symbol"]
        raw = d.get("analysis_data")
        try:
            d["analysis_data"] = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            pass
        result[sym] = d
    return result


def _fetch_entry_decisions_latest(conn, newsletter_id: int) -> list[dict[str, Any]]:
    """Fetch the most recent gate evaluation per symbol for this newsletter.

    Uses the highest decision_id per symbol so repeated evaluations don't
    produce duplicate rows in the report.
    """
    rows = conn.execute(
        """
        SELECT ed.decision_id, ed.newsletter_id, ed.symbol, ed.evaluation_date,
               ed.decision_type, ed.first_failing_gate,
               ed.live_stock_price, ed.live_iv, ed.live_total_credit,
               ed.live_call_strike, ed.live_put_strike,
               n.publication_date AS newsletter_date
        FROM entry_decisions ed
        JOIN newsletters n ON n.newsletter_id = ed.newsletter_id
        WHERE ed.newsletter_id = ?
          AND ed.decision_id IN (
              SELECT MAX(decision_id)
              FROM entry_decisions
              WHERE newsletter_id = ?
              GROUP BY symbol
          )
        ORDER BY ed.decision_type, ed.symbol
        """,
        (newsletter_id, newsletter_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_latest_newsletter_entry_decisions(conn) -> list[dict[str, Any]]:
    """Fetch gate decisions for the most recently evaluated newsletter."""
    row = conn.execute(
        "SELECT newsletter_id FROM entry_decisions ORDER BY decision_id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return []
    return _fetch_entry_decisions_latest(conn, row["newsletter_id"])


def _fetch_active_layers_for_newsletter(
    conn, newsletter_id: int, today: str
) -> list[dict[str, Any]]:
    """ACTIVE cycle_layers for one newsletter week, with DTE computed."""
    rows = conn.execute(
        """
        SELECT cl.*,
               julianday(cl.expiration_date) - julianday(?) AS dte
        FROM cycle_layers cl
        WHERE cl.newsletter_id = ?
          AND cl.status = 'ACTIVE'
        ORDER BY cl.expiration_date, cl.symbol
        """,
        (today, newsletter_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_all_active_layers(conn, today: str) -> list[dict[str, Any]]:
    """All ACTIVE cycle_layers across all newsletters, with DTE and newsletter date."""
    rows = conn.execute(
        """
        SELECT cl.*,
               n.publication_date AS newsletter_date,
               julianday(cl.expiration_date) - julianday(?) AS dte
        FROM cycle_layers cl
        JOIN newsletters n ON n.newsletter_id = cl.newsletter_id
        WHERE cl.status = 'ACTIVE'
        ORDER BY cl.expiration_date, cl.symbol
        """,
        (today,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_exit_alerts(conn) -> list[dict[str, Any]]:
    """Most recent exit decision per layer where action is not HOLD.

    Returns CLOSE_IMMEDIATELY first, then EXIT_MONDAY, then REVIEW,
    then other non-HOLD actions — ordered by urgency then symbol.
    """
    rows = conn.execute(
        """
        SELECT ed.exit_decision_id, ed.layer_id, ed.evaluation_date,
               ed.recommended_action, ed.rule_citations_json,
               ed.trigger_values_json,
               cl.symbol, cl.expiration_date, cl.call_strike, cl.put_strike,
               cl.stock_price_at_entry,
               CASE ed.recommended_action
                   WHEN 'CLOSE_IMMEDIATELY' THEN 1
                   WHEN 'EXIT_MONDAY'       THEN 2
                   WHEN 'REVIEW'            THEN 3
                   ELSE                          4
               END AS urgency_order
        FROM exit_decisions ed
        JOIN cycle_layers cl ON cl.layer_id = ed.layer_id
        WHERE cl.status = 'ACTIVE'
          AND ed.recommended_action != 'HOLD'
          AND ed.exit_decision_id IN (
              SELECT MAX(exit_decision_id)
              FROM exit_decisions
              WHERE recommended_action != 'HOLD'
              GROUP BY layer_id
          )
        ORDER BY urgency_order, cl.symbol
        """,
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        # Flatten trigger_values for the reason string
        tv = {}
        try:
            tv = json.loads(d.get("trigger_values_json") or "{}")
        except (ValueError, TypeError):
            pass
        d["action_reason"] = tv.get("reason") or d["recommended_action"]
        result.append(d)
    return result


def _fetch_active_cycles(conn, today: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT n.newsletter_id, n.publication_date, n.target_expiration, n.option_type,
               COUNT(we.entry_id) AS watchlist_count,
               me.market_status, me.deployment_approved,
               julianday(n.target_expiration) - julianday(?) AS days_until_expiration
        FROM newsletters n
        LEFT JOIN watchlist_entries we ON we.newsletter_id = n.newsletter_id
        LEFT JOIN market_environment me ON me.newsletter_id = n.newsletter_id
        WHERE n.target_expiration >= ?
        GROUP BY n.newsletter_id
        ORDER BY n.target_expiration ASC
        """,
        (today, today),
    ).fetchall()
    return [dict(r) for r in rows]


def _save_report(
    db_path,
    report_type: str,
    newsletter_id: int | None,
    report_date: str,
    markdown: str,
    data_snapshot: dict[str, Any],
    output_path: str | Path | None,
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO generated_reports
            (report_type, newsletter_id, report_date, report_content, output_filepath, data_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_type,
                newsletter_id,
                report_date,
                markdown,
                str(Path(output_path).resolve()) if output_path else None,
                json.dumps(_safe_snapshot(data_snapshot), sort_keys=True),
            ),
        )
        conn.commit()


def _safe_snapshot(obj: Any, depth: int = 0) -> Any:
    if depth > 4:
        return str(obj)[:200]
    if isinstance(obj, dict):
        return {str(k): _safe_snapshot(v, depth + 1) for k, v in list(obj.items())[:50]}
    if isinstance(obj, (list, tuple)):
        return [_safe_snapshot(v, depth + 1) for v in obj[:50]]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)[:200]


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_price(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct_raw(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_int(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)
