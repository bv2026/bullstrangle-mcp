"""position_book.py — Strategy validator using Darren's Short List as positions.

Phase 5 (revised design):
- ``seed_from_short_list`` creates cycle_layer records from newsletter Short List
  symbols joined to their watchlist strikes/premiums.
- ``resolve_outcomes`` fetches actual closing prices at expiration via yfinance
  and computes P&L for each layer.
- ``generate_backtest_report`` produces a week-by-week markdown report.
- ``backtest_all`` is the one-shot: seed + resolve every approved newsletter.

Design decisions:
- portfolio_type = "small" (user's choice for validation).
- account_id = "paper_trade" for all seeded layers (not a real broker account).
- Symbols on the Short List that have no watchlist entry are skipped with a
  ``no_watchlist`` flag in the result — they can't be validated without strikes.
- yfinance is used for historical close prices; network failures are caught and
  the layer is left ACTIVE with a note so it can be retried.
- All writes use INSERT OR IGNORE / UPDATE patterns so the function is safe to
  call more than once.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .database import connect, initialize_database

# ---------------------------------------------------------------------------
# yfinance import — soft dependency so the module still loads if unavailable
# ---------------------------------------------------------------------------

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False


PAPER_ACCOUNT = "paper_trade"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_close(symbol: str, target_date: str) -> float | None:
    """Fetch the closing price for *symbol* on *target_date* (YYYY-MM-DD).

    Options expire on Fridays.  If *target_date* is a trading holiday, yfinance
    will return the nearest prior session — that's acceptable for validation.
    Returns ``None`` on any fetch failure.
    """
    if not _YF_AVAILABLE:
        return None
    try:
        d = date.fromisoformat(target_date)
        end = (d + timedelta(days=3)).isoformat()  # buffer for weekends
        hist = yf.Ticker(symbol).history(start=target_date, end=end)
        if hist.empty:
            return None
        return float(hist["Close"].iloc[0])
    except Exception:
        return None


def _compute_pnl(
    close: float,
    stock_price: float,
    call_strike: float,
    put_strike: float,
    call_prem: float,
    put_prem: float,
    shares: int = 100,
) -> dict[str, Any]:
    """Compute bull-strangle P&L at expiration.

    Returns outcome, pnl_stock, pnl_call, pnl_put, pnl_total, return_pct.

    Invested capital = (stock_price - call_prem - put_prem) * shares
    (net cash after collecting premium upfront).

    Outcomes:
      CALL_ASSIGNED  close > call_strike  → shares called away at call_strike
      PUT_ASSIGNED   close < put_strike   → 100 additional shares assigned
      BOTH_OTM       otherwise            → all options expire worthless
    """
    total_credit = (call_prem + put_prem) * shares
    invested_capital = (stock_price - call_prem - put_prem) * shares

    if close > call_strike:
        outcome = "CALL_ASSIGNED"
        pnl_stock = (call_strike - stock_price) * shares   # sold at strike
        pnl_call = call_prem * shares                       # kept
        pnl_put = put_prem * shares                         # kept (OTM)
    elif close < put_strike:
        outcome = "PUT_ASSIGNED"
        pnl_stock = (close - stock_price) * shares          # original shares MTM
        pnl_call = call_prem * shares                       # kept (OTM)
        # Put assigned: collect premium, take on shares at put_strike vs close
        pnl_put = (put_prem - (put_strike - close)) * shares
    else:
        outcome = "BOTH_OTM"
        pnl_stock = (close - stock_price) * shares          # unrealised
        pnl_call = call_prem * shares                       # kept
        pnl_put = put_prem * shares                         # kept

    pnl_total = pnl_stock + pnl_call + pnl_put
    return_pct = (pnl_total / invested_capital * 100) if invested_capital else 0.0

    return {
        "outcome": outcome,
        "close_price": close,
        "pnl_stock": round(pnl_stock, 2),
        "pnl_call": round(pnl_call, 2),
        "pnl_put": round(pnl_put, 2),
        "pnl_total": round(pnl_total, 2),
        "total_credit": round(total_credit, 2),
        "invested_capital": round(invested_capital, 2),
        "return_pct": round(return_pct, 2),
    }


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def seed_from_short_list(
    newsletter_date: str,
    db_path: str | Path,
    portfolio_type: str = "small",
) -> dict[str, Any]:
    """Create cycle_layer records from the Short List for one newsletter week.

    Only runs when ``weekly_decisions.deployment_approved = 1`` for that week.
    Symbols with no watchlist entry (no strikes/premiums available) are skipped.
    Already-seeded layers (UNIQUE on newsletter_id + symbol + account_id) are
    left untouched — calling this twice is safe.

    Returns a summary dict with seeded, skipped, and already_exists lists.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        # Resolve newsletter_id and check deployment approval
        nl = conn.execute(
            """
            SELECT n.newsletter_id, n.publication_date, n.entry_date,
                   n.target_expiration, wd.deployment_approved, wd.action_taken
            FROM newsletters n
            LEFT JOIN weekly_decisions wd ON wd.newsletter_id = n.newsletter_id
            WHERE n.publication_date = ?
            """,
            (newsletter_date,),
        ).fetchone()

        if nl is None:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")

        if not nl["deployment_approved"]:
            return {
                "newsletter_date": newsletter_date,
                "action_taken": nl["action_taken"],
                "seeded": [],
                "skipped": [],
                "already_exists": [],
                "message": f"Deployment not approved for {newsletter_date} "
                           f"(action={nl['action_taken']}) — nothing seeded.",
            }

        newsletter_id = nl["newsletter_id"]
        open_date = nl["entry_date"]
        expiration_date = nl["target_expiration"]

        # Pull short list symbols + watchlist data
        short_list = conn.execute(
            """
            SELECT s.symbol, s.rank,
                   w.entry_id AS watchlist_entry_id,
                   w.stock_price, w.sell_call_strike AS call_strike,
                   w.sell_put_strike AS put_strike,
                   w.sell_call_premium AS call_prem,
                   w.sell_put_premium AS put_prem,
                   w.bull_strangle_return_pct AS expected_return_pct
            FROM short_list_entries s
            LEFT JOIN watchlist_entries w
                   ON w.newsletter_id = s.newsletter_id AND w.symbol = s.symbol
            WHERE s.newsletter_id = ? AND s.portfolio_type = ?
            ORDER BY s.rank
            """,
            (newsletter_id, portfolio_type),
        ).fetchall()

        seeded, skipped, already_exists = [], [], []

        for row in short_list:
            symbol = row["symbol"]

            # Must have watchlist data to validate
            if row["stock_price"] is None:
                skipped.append({"symbol": symbol, "reason": "no_watchlist_entry"})
                continue

            # Check if already seeded (idempotent)
            existing = conn.execute(
                """
                SELECT layer_id FROM cycle_layers
                WHERE newsletter_id = ? AND symbol = ? AND account_id = ?
                """,
                (newsletter_id, symbol, PAPER_ACCOUNT),
            ).fetchone()
            if existing:
                already_exists.append(symbol)
                continue

            stock_price = row["stock_price"]
            call_prem = row["call_prem"] or 0.0
            put_prem = row["put_prem"] or 0.0
            total_credit = (call_prem + put_prem) * 100
            invested_capital = (stock_price - call_prem - put_prem) * 100

            conn.execute(
                """
                INSERT INTO cycle_layers
                    (newsletter_id, symbol, account_id, open_date, expiration_date,
                     status, shares, stock_price_at_entry, call_strike, put_strike,
                     call_premium_collected, put_premium_collected,
                     total_credit_collected, invested_capital, notes)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', 100, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    newsletter_id, symbol, PAPER_ACCOUNT,
                    open_date, expiration_date,
                    stock_price, row["call_strike"], row["put_strike"],
                    call_prem, put_prem, total_credit, invested_capital,
                    f"paper_trade | rank={row['rank']} | expected={row['expected_return_pct']}%",
                ),
            )
            seeded.append({
                "symbol": symbol,
                "rank": row["rank"],
                "stock_price": stock_price,
                "call_strike": row["call_strike"],
                "put_strike": row["put_strike"],
                "expected_return_pct": row["expected_return_pct"],
            })

        conn.commit()

    return {
        "newsletter_date": newsletter_date,
        "expiration_date": expiration_date,
        "portfolio_type": portfolio_type,
        "action_taken": nl["action_taken"],
        "seeded": seeded,
        "skipped": skipped,
        "already_exists": already_exists,
    }


def resolve_outcomes(
    newsletter_date: str,
    db_path: str | Path,
) -> dict[str, Any]:
    """Fetch expiration-date closing prices and compute P&L for seeded layers.

    Only processes ACTIVE layers whose expiration_date is today or earlier.
    Open (future-expiring) layers are returned in ``pending`` without change.
    Network failures leave the layer ACTIVE with a ``price_fetch_failed`` note.
    """
    initialize_database(db_path)
    today = date.today().isoformat()

    with connect(db_path) as conn:
        nl = conn.execute(
            "SELECT newsletter_id FROM newsletters WHERE publication_date = ?",
            (newsletter_date,),
        ).fetchone()
        if nl is None:
            raise ValueError(f"Newsletter not found for date: {newsletter_date}")

        newsletter_id = nl["newsletter_id"]

        layers = conn.execute(
            """
            SELECT layer_id, symbol, expiration_date, shares,
                   stock_price_at_entry, call_strike, put_strike,
                   call_premium_collected, put_premium_collected, notes
            FROM cycle_layers
            WHERE newsletter_id = ? AND account_id = ? AND status = 'ACTIVE'
            """,
            (newsletter_id, PAPER_ACCOUNT),
        ).fetchall()

        resolved, pending, failed = [], [], []

        for layer in layers:
            exp = layer["expiration_date"]

            if exp > today:
                pending.append({"symbol": layer["symbol"], "expiration_date": exp})
                continue

            close = _fetch_close(layer["symbol"], exp)

            if close is None:
                conn.execute(
                    "UPDATE cycle_layers SET notes = notes || ' | price_fetch_failed' "
                    "WHERE layer_id = ?",
                    (layer["layer_id"],),
                )
                failed.append({"symbol": layer["symbol"], "expiration_date": exp})
                continue

            pnl = _compute_pnl(
                close=close,
                stock_price=layer["stock_price_at_entry"],
                call_strike=layer["call_strike"],
                put_strike=layer["put_strike"],
                call_prem=layer["call_premium_collected"],
                put_prem=layer["put_premium_collected"],
                shares=layer["shares"],
            )

            # Update cycle_layers
            conn.execute(
                """
                UPDATE cycle_layers SET
                    status = 'CLOSED',
                    close_date = ?,
                    close_reason = ?,
                    close_stock_price = ?,
                    pnl_stock = ?,
                    pnl_call = ?,
                    pnl_put = ?,
                    pnl_total = ?
                WHERE layer_id = ?
                """,
                (
                    exp,
                    pnl["outcome"],
                    close,
                    pnl["pnl_stock"],
                    pnl["pnl_call"],
                    pnl["pnl_put"],
                    pnl["pnl_total"],
                    layer["layer_id"],
                ),
            )

            # Record exit decision
            trigger = json.dumps({
                "close_price": close,
                "call_strike": layer["call_strike"],
                "put_strike": layer["put_strike"],
                "invested_capital": pnl["invested_capital"],
                "return_pct": pnl["return_pct"],
            })
            conn.execute(
                """
                INSERT INTO exit_decisions
                    (layer_id, evaluation_date, recommended_action,
                     rule_citations_json, trigger_values_json,
                     actual_action, confirmed_at, confirmed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    layer["layer_id"],
                    exp,
                    pnl["outcome"],
                    json.dumps(["RULE-EXIT-001", "RULE-EXIT-002", "RULE-EXIT-003", "RULE-EXIT-004"]),
                    trigger,
                    pnl["outcome"],
                    exp,
                    "backtest",
                ),
            )

            resolved.append({
                "symbol": layer["symbol"],
                "expiration_date": exp,
                "close_price": close,
                "outcome": pnl["outcome"],
                "pnl_total": pnl["pnl_total"],
                "return_pct": pnl["return_pct"],
                "invested_capital": pnl["invested_capital"],
            })

        conn.commit()

    return {
        "newsletter_date": newsletter_date,
        "resolved": resolved,
        "pending": pending,
        "failed": failed,
    }


def backtest_all(
    db_path: str | Path,
    portfolio_type: str = "small",
) -> dict[str, Any]:
    """Seed and resolve all approved newsletters in one call.

    For each newsletter with deployment_approved=1:
    1. seed_from_short_list
    2. resolve_outcomes (if expiration is past)

    Returns a summary of all weeks processed.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        approved_dates = conn.execute(
            """
            SELECT n.publication_date
            FROM newsletters n
            JOIN weekly_decisions wd ON wd.newsletter_id = n.newsletter_id
            WHERE wd.deployment_approved = 1
            ORDER BY n.publication_date
            """,
        ).fetchall()

    results = []
    for row in approved_dates:
        pub = row["publication_date"]
        seed_result = seed_from_short_list(pub, db_path, portfolio_type)
        resolve_result = resolve_outcomes(pub, db_path)
        results.append({
            "newsletter_date": pub,
            "seeded_count": len(seed_result["seeded"]),
            "skipped_count": len(seed_result["skipped"]),
            "already_existed": len(seed_result["already_exists"]),
            "resolved_count": len(resolve_result["resolved"]),
            "pending_count": len(resolve_result["pending"]),
            "failed_count": len(resolve_result["failed"]),
        })

    return {"portfolio_type": portfolio_type, "weeks_processed": len(results), "results": results}


def generate_backtest_report(
    db_path: str | Path,
    portfolio_type: str = "small",
) -> str:
    """Generate a markdown backtest report across all closed cycle layers.

    Shows week-by-week outcomes with symbol-level detail, cumulative P&L,
    win rate, and best/worst trades.
    """
    initialize_database(db_path)
    with connect(db_path) as conn:
        weeks = conn.execute(
            """
            SELECT n.publication_date, n.target_expiration,
                   COUNT(*) as total,
                   SUM(CASE WHEN cl.status = 'CLOSED' THEN 1 ELSE 0 END) as closed,
                   SUM(CASE WHEN cl.status = 'ACTIVE' THEN 1 ELSE 0 END) as active,
                   SUM(cl.pnl_total) as week_pnl,
                   SUM(cl.invested_capital) as week_invested
            FROM cycle_layers cl
            JOIN newsletters n ON n.newsletter_id = cl.newsletter_id
            WHERE cl.account_id = ?
            GROUP BY cl.newsletter_id
            ORDER BY n.publication_date
            """,
            (PAPER_ACCOUNT,),
        ).fetchall()

        layers = conn.execute(
            """
            SELECT n.publication_date, n.target_expiration,
                   cl.symbol, cl.status, cl.close_reason,
                   cl.stock_price_at_entry, cl.call_strike, cl.put_strike,
                   cl.call_premium_collected, cl.put_premium_collected,
                   cl.close_stock_price, cl.pnl_total, cl.invested_capital,
                   cl.notes
            FROM cycle_layers cl
            JOIN newsletters n ON n.newsletter_id = cl.newsletter_id
            WHERE cl.account_id = ?
            ORDER BY n.publication_date, cl.symbol
            """,
            (PAPER_ACCOUNT,),
        ).fetchall()

    if not layers:
        return "# Backtest Report\n\nNo cycle layers found. Run `backtest_all` first.\n"

    # Group layers by week
    by_week: dict[str, list] = {}
    for layer in layers:
        pub = layer["publication_date"]
        by_week.setdefault(pub, []).append(layer)

    total_pnl = 0.0
    total_invested = 0.0
    total_trades = 0
    wins = 0

    lines = [
        "# Bull Strangle Backtest Report",
        f"\n**Portfolio type:** {portfolio_type}  **Account:** {PAPER_ACCOUNT}",
        f"**Weeks analysed:** {len(by_week)}",
        "",
    ]

    outcome_emoji = {
        "BOTH_OTM": "[OTM]",
        "CALL_ASSIGNED": "[CALL]",
        "PUT_ASSIGNED": "[PUT]",
        None: "[OPEN]",
    }

    for pub, week_layers in sorted(by_week.items()):
        exp = week_layers[0]["target_expiration"]
        week_pnl = sum(l["pnl_total"] or 0 for l in week_layers if l["status"] == "CLOSED")
        week_invested = sum(l["invested_capital"] or 0 for l in week_layers)
        week_ret = (week_pnl / week_invested * 100) if week_invested else 0.0
        n_closed = sum(1 for l in week_layers if l["status"] == "CLOSED")
        n_active = sum(1 for l in week_layers if l["status"] == "ACTIVE")

        total_pnl += week_pnl
        total_invested += week_invested

        status_str = f"{n_closed} closed" + (f", {n_active} open" if n_active else "")
        lines.append(f"## {pub}  ->  exp {exp}  ({status_str})")
        lines.append("")
        lines.append(f"| Symbol | Entry $ | Call | Put | Close $ | Outcome | P&L | Ret% |")
        lines.append(f"|--------|---------|------|-----|---------|---------|-----|------|")

        for l in week_layers:
            outcome = l["close_reason"]
            emoji = outcome_emoji.get(outcome, "⏳")
            close_str = f"{l['close_stock_price']:.2f}" if l["close_stock_price"] else "—"
            pnl_str = f"${l['pnl_total']:+.0f}" if l["pnl_total"] is not None else "—"
            ret_pct = (
                (l["pnl_total"] / l["invested_capital"] * 100)
                if l["pnl_total"] is not None and l["invested_capital"]
                else None
            )
            ret_str = f"{ret_pct:+.1f}%" if ret_pct is not None else "—"
            call_prem = l["call_premium_collected"] or 0
            put_prem = l["put_premium_collected"] or 0
            lines.append(
                f"| {l['symbol']:<6} | {l['stock_price_at_entry'] or 0:.2f} "
                f"| {l['call_strike'] or 0:.1f}@{call_prem:.2f} "
                f"| {l['put_strike'] or 0:.1f}@{put_prem:.2f} "
                f"| {close_str} | {emoji} {outcome or 'OPEN'} | {pnl_str} | {ret_str} |"
            )
            if l["status"] == "CLOSED":
                total_trades += 1
                if l["pnl_total"] and l["pnl_total"] > 0:
                    wins += 1

        if n_closed > 0:
            lines.append(f"\n**Week P&L:** ${week_pnl:+.0f}  |  **Week return:** {week_ret:+.2f}%\n")
        lines.append("")

    # Summary
    overall_ret = (total_pnl / total_invested * 100) if total_invested else 0.0
    win_rate = (wins / total_trades * 100) if total_trades else 0.0

    lines.append("---")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Closed trades | {total_trades} |")
    lines.append(f"| Wins (P&L > 0) | {wins} ({win_rate:.0f}%) |")
    lines.append(f"| Total P&L | ${total_pnl:+,.0f} |")
    lines.append(f"| Total invested | ${total_invested:,.0f} |")
    lines.append(f"| Overall return | {overall_ret:+.2f}% |")

    if total_trades > 0:
        all_closed = [l for l in layers if l["status"] == "CLOSED" and l["pnl_total"] is not None]
        if all_closed:
            best = max(all_closed, key=lambda l: l["pnl_total"])
            worst = min(all_closed, key=lambda l: l["pnl_total"])
            best_ret = best["pnl_total"] / best["invested_capital"] * 100 if best["invested_capital"] else 0
            worst_ret = worst["pnl_total"] / worst["invested_capital"] * 100 if worst["invested_capital"] else 0
            lines.append(
                f"| Best trade | {best['symbol']} ({best['publication_date']}) "
                f"${best['pnl_total']:+.0f} / {best_ret:+.1f}% |"
            )
            lines.append(
                f"| Worst trade | {worst['symbol']} ({worst['publication_date']}) "
                f"${worst['pnl_total']:+.0f} / {worst_ret:+.1f}% |"
            )

    lines.append("")
    return "\n".join(lines)
