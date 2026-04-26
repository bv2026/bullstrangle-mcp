"""Report generation for the Bull Strangle Newsletter MCP.

Implements the weekly action plan and daily brief reports described in
the architecture spec (Section 6).  Reports are rendered as Markdown
strings and optionally written to disk.  Generated reports are logged in
the generated_reports table so they can be retrieved later.

Table dependencies (created via migration _m002 in database.py):
  - generated_reports
  - report_subscriptions  (reserved for future scheduling)
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

    Covers all 10 sections from the spec:
      1. Market Environment Status
      2. Re-Entry Criteria Table
      3. DCA Candidate Updates
      4. Strangle Trades Eligibility Summary
      5. Watch List Analysis
      6. Action Items
      7. Portfolio Summary
      8. Key Reminders
      9. Next Sunday Workflow
      10. Appendix (Data Reconciliation Issues)
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
        batch = _fetch_latest_batch(conn, newsletter["newsletter_id"])
        approved_symbols, watch_symbols, skip_symbols = _fetch_symbol_decisions(conn, batch)

    ctx = _build_context(
        newsletter, env, wd, watchlist, short_list,
        deep_analysis, approved_symbols, watch_symbols, today,
    )
    markdown = _render_weekly_action_plan(ctx)

    _save_report(
        db_path,
        report_type="weekly_action_plan",
        newsletter_id=newsletter["newsletter_id"],
        report_date=today,
        markdown=markdown,
        data_snapshot=ctx,
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
    approved = ctx["approved_symbols"]
    watching = ctx["watch_symbols"]
    today = ctx["today"]

    approved_marker = "✅" if env.get("deployment_approved") else "⚠️"
    consecutive = env.get("consecutive_weeks_met") or 0
    action = wd.get("action_taken", "monitor_only") if wd else "unknown"
    market_status = env.get("market_status", "unknown").upper()
    status_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(market_status, "⚪")

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

    lines += [
        "",
        # ── Section 4 ──
        "## 4. STRANGLE TRADES ELIGIBILITY SUMMARY",
        "",
        f"- **Total watchlist symbols:** {len(watchlist)}",
        f"- **Approved (APPROVE):** {len(approved)}",
        f"- **On watch (WATCH):** {len(watching)}",
        "",
    ]

    if approved:
        lines += ["### ✅ Approved for Deployment", ""]
        lines += [
            "| Rank | Symbol | Credit | Live Price | Price Dev | Account | Acct Shares | To 100 | Score |",
            "|------|--------|--------|------------|-----------|---------|-------------|--------|-------|",
        ]
        for row in approved[:15]:
            lines.append(
                f"| {row.get('priority_rank', '')} | **{row['symbol']}** "
                f"| {_fmt_price(row.get('latest_total_credit'))} "
                f"| {_fmt_price(row.get('latest_live_stock_price'))} "
                f"| {_fmt_pct_raw(row.get('max_price_deviation_pct'))} "
                f"| {row.get('selected_account') or ''} "
                f"| {_fmt_int(row.get('account_shares'))} "
                f"| {_fmt_int(row.get('shares_to_100'))} "
                f"| {_fmt(row.get('strategy_score'))} |"
            )
        lines.append("")

    if watching:
        lines += ["### 👀 On Watch", ""]
        lines += ["| Rank | Symbol | Score | Band | Reason |", "|------|--------|-------|------|--------|"]
        for row in watching[:10]:
            lines.append(
                f"| {row.get('priority_rank', '')} | {row['symbol']} "
                f"| {_fmt(row.get('strategy_score'))} | {row.get('strategy_band', '')} "
                f"| {(row.get('reason') or '')[:80]} |"
            )
        lines.append("")

    lines += [
        # ── Section 5 ──
        "## 5. WATCH LIST ANALYSIS",
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

    lines += ["", "## 6. WL FAVORITES — DEEP ANALYSIS", ""]
    if deep_analysis:
        for sym, da in deep_analysis.items():
            analysis = da.get("analysis_data") or {}
            lines += [
                f"### {sym}",
                "",
                f"**Rank:** {da.get('favorite_rank', '?')}  ",
            ]
            if isinstance(analysis, dict):
                company = analysis.get("company_name") or analysis.get("sector") or ""
                if company:
                    lines.append(f"**Company:** {company}  ")
                summary = analysis.get("source_summary") or ""
                if summary:
                    # Show first 500 chars
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

    lines += [
        # ── Section 6 ──
        "## 7. ACTION ITEMS",
        "",
        "### This Week",
    ]
    if env.get("deployment_approved"):
        lines += [
            "- [ ] Review APPROVE list above and confirm position sizing",
            "- [ ] Run Option Samurai on generated Excel workbook",
            "- [ ] Execute approved trades via broker",
            "- [ ] Update position tracker after execution",
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

    lines += [
        "",
        "### Next Week",
        f"- [ ] Await next newsletter (approx. {newsletter.get('publication_date')} + 7 days)",
        "- [ ] Verify market criteria status again",
        "- [ ] Review any open positions approaching expiration",
        "",
        # ── Section 8 ──
        "## 8. KEY REMINDERS",
        "",
        "- **2-Consecutive-Week Rule:** All 4 criteria must be met for 2 consecutive weeks before deploying",
        "- **100-Share Requirement:** Bull Strangle requires exactly 100 shares per position",
        "- **Earnings Safety:** Avoid symbols with earnings before option expiration",
        "- **Exit at 50%:** Close positions when 50% of max profit is reached",
        "- **Stock Called Away:** Close naked puts for small debit; let calls expire",
        "",
        # ── Section 9 ──
        "## 9. NEXT SUNDAY WORKFLOW",
        "",
        "```",
        "1. Receive Darren's PDF newsletter",
        "2. Run: ingest_newsletter(pdf_path)",
        "3. Run: generate_os_workbook(newsletter_date)",
        "4. Open Excel, run Option Samurai (Ctrl+Shift+Alt+F9)",
        "5. Review TRADE? column, add notes",
        "6. Save as _evaluated.xlsx",
        "7. Run: generate_weekend_decisions(newsletter_date)",
        "8. Run: generate_weekly_action_plan(newsletter_date)",
        "```",
        "",
        # ── Section 10 ──
        "## 10. APPENDIX — DATA NOTES",
        "",
        f"- Newsletter ingested: {newsletter.get('publication_date')}",
        f"- Watchlist symbols: {len(watchlist)}",
        f"- Short-list DCA candidates: {len(short_list)}",
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

    Covers:
      1. Market Environment Check (latest state)
      2. Active Cycles (open position books)
      3. Alerts & Actions (upcoming expirations, scaling guidance)
    """
    initialize_database(db_path)
    today = date.today().isoformat()

    with connect(db_path) as conn:
        env = _fetch_latest_env(conn)
        active = _fetch_active_cycles(conn, today)
        latest_batch = _fetch_latest_any_batch(conn)
        approved, watching, _ = _fetch_symbol_decisions(conn, latest_batch)

    markdown = _render_daily_brief(today, env, active, approved, watching)

    _save_report(
        db_path,
        report_type="daily_brief",
        newsletter_id=env.get("newsletter_id") if env else None,
        report_date=today,
        markdown=markdown,
        data_snapshot={"env": env, "active_cycles": len(active)},
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
    active: list[dict[str, Any]],
    approved: list[dict[str, Any]],
    watching: list[dict[str, Any]],
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

    lines += ["## 2. ACTIVE CYCLES", ""]
    if active:
        lines += [
            "| Newsletter Date | Expiration | Days Left | Status | Positions |",
            "|-----------------|------------|-----------|--------|-----------|",
        ]
        for row in active:
            days_left = row.get("days_until_expiration")
            days_str = f"{days_left:.0f}" if days_left is not None else "?"
            alert = " ⚠️" if days_left is not None and days_left <= 7 else ""
            lines.append(
                f"| {row['publication_date']} | {row.get('target_expiration', 'N/A')} "
                f"| {days_str}{alert} | {(row.get('market_status') or '').upper()} "
                f"| {row.get('watchlist_count', 0)} |"
            )
    else:
        lines.append("*No active cycles (all expirations are in the past).*")

    lines += [
        "",
        "## 3. ALERTS & ACTIONS",
        "",
    ]
    alerts: list[str] = []
    for row in active:
        days_left = row.get("days_until_expiration")
        if days_left is not None and days_left <= 7:
            alerts.append(
                f"⚠️ **{row['publication_date']}** cycle expires in **{days_left:.0f} days** "
                f"({row.get('target_expiration')}) — review open positions"
            )
        if days_left is not None and days_left <= 3:
            alerts.append(
                f"🚨 **URGENT:** {row['publication_date']} cycle expires in {days_left:.0f} days "
                "— close or roll positions today"
            )

    if env and not env.get("deployment_approved"):
        if env.get("all_criteria_met"):
            consecutive = env.get("consecutive_weeks_met") or 0
            alerts.append(
                f"⏳ Market Week {consecutive}/2 — hold off new strangles until next newsletter confirms"
            )
        else:
            alerts.append("🔴 Market criteria NOT met — no new strangle deployments")

    if approved:
        alerts.append(
            f"✅ {len(approved)} symbol(s) APPROVED in latest decision batch — "
            f"see: {', '.join(r['symbol'] for r in approved[:5])}"
        )
    if watching:
        alerts.append(
            f"👀 {len(watching)} symbol(s) on WATCH — "
            f"{', '.join(r['symbol'] for r in watching[:5])}"
        )

    if alerts:
        for alert in alerts:
            lines.append(f"- {alert}")
    else:
        lines.append("- No active alerts.")

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


def _fetch_latest_batch(conn, newsletter_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM decision_batches
        WHERE newsletter_id = ?
        ORDER BY decision_date DESC
        LIMIT 1
        """,
        (newsletter_id,),
    ).fetchone()
    return dict(row) if row else None


def _fetch_latest_any_batch(conn) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM decision_batches ORDER BY decision_date DESC, newsletter_date DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def _fetch_symbol_decisions(
    conn, batch: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not batch:
        return [], [], []
    batch_id = batch["decision_batch_id"]
    rows = conn.execute(
        """
        SELECT bsd.symbol, bsd.final_decision, bsd.selected_action, bsd.priority_rank,
               bsd.strategy_score, bsd.strategy_band, bsd.latest_total_credit,
               bsd.latest_live_stock_price, bsd.max_price_deviation_pct,
               bsd.selected_account, bsd.account_shares, bsd.shares_to_100, bsd.reason
        FROM bull_strangle_decisions bsd
        WHERE bsd.decision_batch_id = ?
        ORDER BY bsd.priority_rank
        """,
        (batch_id,),
    ).fetchall()
    approved = [dict(r) for r in rows if r["final_decision"] == "APPROVE"]
    watching = [dict(r) for r in rows if r["final_decision"] == "WATCH"]
    skipped = [dict(r) for r in rows if r["final_decision"] == "SKIP"]
    return approved, watching, skipped


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


def _build_context(
    newsletter: dict[str, Any],
    env: dict[str, Any],
    wd: dict[str, Any] | None,
    watchlist: list[dict[str, Any]],
    short_list: list[dict[str, Any]],
    deep_analysis: dict[str, Any],
    approved_symbols: list[dict[str, Any]],
    watch_symbols: list[dict[str, Any]],
    today: str,
) -> dict[str, Any]:
    return {
        "newsletter": newsletter,
        "env": env,
        "wd": wd,
        "watchlist": watchlist,
        "short_list": short_list,
        "deep_analysis": deep_analysis,
        "approved_symbols": approved_symbols,
        "watch_symbols": watch_symbols,
        "today": today,
    }


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
    """Recursively sanitise a context dict for JSON storage, capping depth at 4."""
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
    """Format a fraction already in 0–1 range as percent."""
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
