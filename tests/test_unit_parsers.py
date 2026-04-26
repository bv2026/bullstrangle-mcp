"""Unit tests for PDF parser functions and the strategy-context builder.

These tests run entirely in-memory — no PDF file required — so they belong
to the ``unit`` marker and always run.  They complement the integration suite
(test_ingestion_smoke.py) which exercises the full ingest pipeline against a
real PDF.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from bullstrangle_mcp.ingestion import (
    PageText,
    build_ingestion_quality_report,
    build_warnings,
    parse_market_environment,
    parse_short_lists,
    parse_watchlist_option_prices,
    parse_watchlist_screening_details,
)
from bullstrangle_mcp.decisions import DEFAULT_RULES, _build_strategy_context


# ── helpers ──────────────────────────────────────────────────────────────────

def _watchlist_line(
    symbol: str = "NTAP",
    description: str = "NetApp Inc",
    price: str = "100.00",
    iv: str = "34",
    sector: str = "Technology",
    rest: str = "104.00 1.25 96.00 1.10 88.00 0.55 5.00 2.00 1.00",
) -> str:
    """Build a synthetic watchlist line in the format the PDF parser expects."""
    return f"{symbol} {description} {price}$ {iv}% {sector} {rest}"


def _market_env_line(
    dt: str = "4/17/2026",
    spx: str = "7126.06",
    vix: str = "17.48",
    breadth: str = "59.84",
    dma: str = "6685.57",
    trend: str = "1",
    vix_score: str = "1",
    breadth_score: str = "0",
    hybrid: str = "2",
    regime: str = "full",
    position: str = "100",
    cash: str = "25",
) -> str:
    return (
        f"{dt} {spx} {vix} {breadth} {dma} "
        f"{trend} {vix_score} {breadth_score} {hybrid} "
        f"{regime} {position}% {cash}%"
    )


def _approved_market() -> dict[str, Any]:
    return {
        "deployment_approved": 1,
        "investment_percent": 100,
        "hybrid_score": 2,
        "market_status": "green",
        "market_regime": "full_exposure",
    }


def _week_row(
    symbol: str = "NTAP",
    stock_price: float = 100.0,
    latest_total_credit: float | None = 2.50,
    latest_live_stock_price: float | None = 99.0,
    sell_call_strike: float | None = 104.0,
    worst_abs_stock_price_deviation_pct: float | None = 0.01,
    worst_abs_total_credit_deviation: float | None = 0.20,
    is_week_valid: int = 1,
    is_favorite: int = 0,
    newsletter_id: int = 1,
    newsletter_date: str = "2026-04-17",
    expiration_date: str = "2026-05-15",
    entry_id: int = 1,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "stock_price": stock_price,
        "latest_total_credit": latest_total_credit,
        "latest_live_stock_price": latest_live_stock_price,
        "sell_call_strike": sell_call_strike,
        "worst_abs_stock_price_deviation_pct": worst_abs_stock_price_deviation_pct,
        "worst_abs_total_credit_deviation": worst_abs_total_credit_deviation,
        "is_week_valid": is_week_valid,
        "is_favorite": is_favorite,
        "newsletter_id": newsletter_id,
        "newsletter_date": newsletter_date,
        "expiration_date": expiration_date,
        "entry_id": entry_id,
    }


# ── parse_watchlist_option_prices ─────────────────────────────────────────────

@pytest.mark.unit
def test_parse_watchlist_option_prices_happy_path():
    line = _watchlist_line()
    page = PageText(page_number=3, text=line)
    rows = parse_watchlist_option_prices([page])

    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "NTAP"
    assert row["description"] == "NetApp Inc"
    assert row["stock_price"] == 100.0
    assert row["implied_volatility"] == pytest.approx(0.34)
    assert row["sector"] == "Technology"
    assert row["sell_call_strike"] == 104.0
    assert row["sell_call_premium"] == 1.25
    assert row["sell_put_strike"] == 96.0
    assert row["sell_put_premium"] == 1.10
    assert row["buy_put_strike"] == 88.0
    assert row["buy_put_premium"] == 0.55
    assert row["bull_strangle_return_pct"] == 5.0
    assert row["put_credit_spread_return_pct"] == 2.0
    assert row["covered_call_return_pct"] == 1.0
    assert row["source_page"] == 3


@pytest.mark.unit
def test_parse_watchlist_option_prices_iv_stored_as_fraction():
    """IV is given as a percent integer in the PDF but stored as a 0-1 fraction."""
    line = _watchlist_line(iv="45")
    page = PageText(page_number=1, text=line)
    rows = parse_watchlist_option_prices([page])
    assert rows[0]["implied_volatility"] == pytest.approx(0.45)


@pytest.mark.unit
def test_parse_watchlist_option_prices_skips_lines_with_too_few_numbers():
    """A line missing one or more numeric columns must be silently dropped."""
    # Only 8 numbers in rest (need 9)
    short_rest = "104.00 1.25 96.00 1.10 88.00 0.55 5.00 2.00"
    line = _watchlist_line(rest=short_rest)
    page = PageText(page_number=1, text=line)
    rows = parse_watchlist_option_prices([page])
    assert rows == []


@pytest.mark.unit
def test_parse_watchlist_option_prices_deduplicates_by_symbol():
    """When the same symbol appears on two pages only one row is kept.
    dedupe_by_symbol retains the first occurrence."""
    page1 = PageText(page_number=1, text=_watchlist_line(symbol="NTAP", price="99.00"))
    page2 = PageText(page_number=2, text=_watchlist_line(symbol="NTAP", price="101.00"))
    rows = parse_watchlist_option_prices([page1, page2])
    assert len(rows) == 1
    assert rows[0]["stock_price"] == 99.0  # first-seen wins


@pytest.mark.unit
def test_parse_watchlist_option_prices_multiple_symbols():
    text = "\n".join([
        _watchlist_line(symbol="NTAP", description="NetApp Inc"),
        _watchlist_line(symbol="AAPL", description="Apple Inc", sector="Technology"),
    ])
    page = PageText(page_number=1, text=text)
    rows = parse_watchlist_option_prices([page])
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"NTAP", "AAPL"}


@pytest.mark.unit
def test_parse_watchlist_option_prices_ignores_non_matching_lines():
    text = "This is a header line\nAnother non-data line\n" + _watchlist_line()
    page = PageText(page_number=1, text=text)
    rows = parse_watchlist_option_prices([page])
    assert len(rows) == 1


@pytest.mark.unit
def test_parse_watchlist_option_prices_corrects_split_crml_symbol():
    line = (
        "C RML C RITIC AL METALS C ORP 11.51$ 120% Materials "
        "12.00$ 1.10$ 11.00$ 1.25$ 10.00$ 1.00$ 25.7% 13.3% 10.6%"
    )
    rows = parse_watchlist_option_prices([PageText(page_number=9, text=line)])

    assert len(rows) == 1
    assert rows[0]["symbol"] == "CRML"
    assert rows[0]["description"] == "RML CRITICAL METALS CORP"
    assert rows[0]["stock_price"] == 11.51
    assert rows[0]["parser_correction"] == {
        "from_symbol": "C",
        "to_symbol": "CRML",
        "reason": "description_correction",
    }

    report = build_ingestion_quality_report(rows, {"watchlist_option_prices": [PageText(9, line)]})
    assert report["parser_correction_count"] == 1
    assert report["suspicious_single_letter_count"] == 0
    assert report["parser_corrections"][0]["to_symbol"] == "CRML"


@pytest.mark.unit
def test_parse_watchlist_option_prices_keeps_valid_single_letter_symbol():
    line = _watchlist_line(symbol="C", description="Citigroup Inc", price="128.00", sector="Financials")
    rows = parse_watchlist_option_prices([PageText(page_number=1, text=line)])

    assert rows[0]["symbol"] == "C"
    assert rows[0]["description"] == "Citigroup Inc"
    assert "validation_warning" not in rows[0]


@pytest.mark.unit
def test_parse_watchlist_option_prices_keeps_known_single_letter_growth_symbol():
    line = _watchlist_line(symbol="S", description="SentinelOne Inc Class A", price="14.24", sector="Technology")
    rows = parse_watchlist_option_prices([PageText(page_number=1, text=line)])

    assert rows[0]["symbol"] == "S"
    assert rows[0]["description"] == "SentinelOne Inc Class A"
    assert "validation_warning" not in rows[0]


@pytest.mark.unit
def test_parse_watchlist_option_prices_flags_unknown_single_letter_symbol():
    line = _watchlist_line(symbol="Q", description="Quantum Widgets Inc", sector="Technology")
    rows = parse_watchlist_option_prices([PageText(page_number=1, text=line)])

    assert rows[0]["symbol"] == "Q"
    assert "Single-letter ticker is not in known single-letter ticker allowlist" in rows[0]["validation_warning"]

    report = build_ingestion_quality_report(rows, {"watchlist_option_prices": [PageText(1, line)]})
    warnings = build_warnings(rows, {}, {"watchlist_option_prices": [PageText(1, line)]}, report)

    assert report["status"] == "needs_review"
    assert report["suspicious_single_letter_count"] == 1
    assert any("Suspicious single-letter ticker Q" in warning for warning in warnings)


@pytest.mark.unit
def test_parse_watchlist_screening_details_matches_split_crml_symbol():
    line = "C RML C ritical Metals Corp 11.51 121.31% 295597Mining - Misc Basic Materials Yes N/A Materials"
    details = parse_watchlist_screening_details([PageText(page_number=8, text=line)], {"CRML"})

    assert set(details) == {"CRML"}
    assert details["CRML"]["screening_name"] == "Critical Metals Corp"
    assert details["CRML"]["total_open_interest"] == 295597


@pytest.mark.unit
def test_parse_short_lists_matches_split_crml_symbol():
    line = "C RML C ritical Metals Corp 11.51 121.31% 295597Mining - Misc Basic Materials Yes N/A Materials"
    rows = parse_short_lists([PageText(page_number=10, text=line)], {"CRML"})

    assert len(rows) == 1
    assert rows[0]["symbol"] == "CRML"
    assert rows[0]["portfolio_type"] == "large"


# ── parse_market_environment ──────────────────────────────────────────────────

@pytest.mark.unit
def test_parse_market_environment_happy_path():
    line = _market_env_line()
    page = PageText(page_number=1, text=line)
    env = parse_market_environment([page], date(2026, 4, 17))

    assert env["sp500_price"] == pytest.approx(7126.06)
    assert env["sp500_200dma"] == pytest.approx(6685.57)
    assert env["vix"] == pytest.approx(17.48)
    assert env["breadth_pct"] == pytest.approx(59.84)
    assert env["trend_score"] == 1
    assert env["volatility_score"] == 1
    assert env["breadth_score"] == 0
    assert env["hybrid_score"] == 2
    assert env["market_regime"] == "full"
    assert env["investment_percent"] == 100
    assert env["cash_reserve_target"] == pytest.approx(25.0)


@pytest.mark.unit
def test_parse_market_environment_derived_fields():
    """Fields computed from parsed values (above_200dma, vix_below_25, etc.) are correct."""
    line = _market_env_line(spx="7126.06", dma="6685.57", vix="17.48", breadth="59.84", hybrid="2")
    env = parse_market_environment([PageText(1, line)], date(2026, 4, 17))

    assert env["sp500_above_200dma"] is True
    assert env["vix_below_25"] is True
    assert env["breadth_above_40"] is True
    assert env["hybrid_bullish"] is True
    assert env["all_criteria_met"] is True
    assert env["sp500_vs_200dma"] == pytest.approx(7126.06 - 6685.57)


@pytest.mark.unit
def test_parse_market_environment_all_criteria_not_met_when_vix_high():
    line = _market_env_line(vix="26.00")  # above 25 threshold
    env = parse_market_environment([PageText(1, line)], date(2026, 4, 17))
    assert env["vix_below_25"] is False
    assert env["all_criteria_met"] is False
    assert env["deployment_approved"] is False


@pytest.mark.unit
def test_parse_market_environment_selects_matching_date_row():
    """When multiple env rows are present the row matching publication_date is used."""
    older = _market_env_line(dt="4/10/2026", vix="30.00")
    current = _market_env_line(dt="4/17/2026", vix="17.48")
    page = PageText(1, older + "\n" + current)
    env = parse_market_environment([page], date(2026, 4, 17))
    # Must pick the 4/17/2026 row, not the older one
    assert env["vix"] == pytest.approx(17.48)


@pytest.mark.unit
def test_parse_market_environment_empty_pages_returns_empty_dict():
    env = parse_market_environment([], date(2026, 4, 17))
    assert env == {}


@pytest.mark.unit
def test_parse_market_environment_no_matching_line_returns_empty_dict():
    page = PageText(1, "No data here at all\nJust text")
    env = parse_market_environment([page], date(2026, 4, 17))
    assert env == {}


# ── _build_strategy_context ───────────────────────────────────────────────────

@pytest.mark.unit
def test_build_strategy_context_bull_strangle_path():
    """Market approved + good OS data + no existing position → BULL_STRANGLE."""
    ctx = _build_strategy_context(
        market=_approved_market(),
        row=_week_row(),
        position=None,
        positions_available=False,
        short_list_symbols=set(),
    )
    assert ctx["selected_action"] == "BULL_STRANGLE"
    assert ctx["market_approved"] == 1
    assert ctx["os_valid"] == 1
    assert ctx["strategy_band"] in {"strong", "moderate"}
    assert isinstance(ctx["strategy_score"], float)


@pytest.mark.unit
def test_build_strategy_context_dca_path():
    """Partial position (< 100 shares in one account) + price attractive → DCA."""
    position = {
        "max_account_quantity": 50,
        "total_quantity": 50,
        "bull_strangle_ready": 0,
        "shares_to_100": 50,
        "dca_target_account": "INDIVIDUAL",
    }
    row = _week_row(
        latest_live_stock_price=96.0,  # ≤ baseline * 0.97 → price_attractive_for_dca
        stock_price=100.0,
        sell_call_strike=104.0,
    )
    ctx = _build_strategy_context(
        market=_approved_market(),
        row=row,
        position=position,
        positions_available=True,
        short_list_symbols=set(),
    )
    assert ctx["selected_action"] == "DCA"
    assert ctx["accumulation_preferred"] is True
    assert ctx["account_shares"] == 50.0


@pytest.mark.unit
def test_build_strategy_context_watch_path():
    """Poor OS data (is_week_valid=0) with moderate score lands in WATCH."""
    ctx = _build_strategy_context(
        market=_approved_market(),
        row=_week_row(is_week_valid=0),
        position=None,
        positions_available=False,
        short_list_symbols=set(),
    )
    # Without os_valid the strategy can't be BULL_STRANGLE; score may still be watch-band
    assert ctx["os_valid"] == 0
    assert ctx["selected_action"] in {"WATCH", "SKIP"}


@pytest.mark.unit
def test_build_strategy_context_skip_path():
    """Market not approved + bad data → SKIP."""
    market = {
        "deployment_approved": 0,
        "investment_percent": 0,
        "hybrid_score": -2,
        "market_status": "red",
        "market_regime": "pause",
    }
    row = _week_row(
        is_week_valid=0,
        latest_total_credit=None,
        worst_abs_stock_price_deviation_pct=0.20,
        worst_abs_total_credit_deviation=5.00,
    )
    ctx = _build_strategy_context(
        market=market,
        row=row,
        position=None,
        positions_available=False,
        short_list_symbols=set(),
    )
    assert ctx["selected_action"] == "SKIP"
    assert ctx["strategy_band"] == "weak"


@pytest.mark.unit
def test_build_strategy_context_short_list_boosts_score():
    """Being on the short list adds +1 to strategy_score."""
    row = _week_row(symbol="NTAP")
    ctx_no_short = _build_strategy_context(
        market=_approved_market(), row=row, position=None,
        positions_available=False, short_list_symbols=set(),
    )
    ctx_short = _build_strategy_context(
        market=_approved_market(), row=row, position=None,
        positions_available=False, short_list_symbols={"NTAP"},
    )
    assert ctx_short["strategy_score"] == ctx_no_short["strategy_score"] + 1.0
    assert ctx_short["is_short_listed"] is True


@pytest.mark.unit
def test_build_strategy_context_respects_custom_rules():
    """Passing a looser rule set allows a symbol that would fail the default threshold."""
    row = _week_row(
        worst_abs_stock_price_deviation_pct=0.12,  # > default 0.08 — would fail
        worst_abs_total_credit_deviation=0.10,
    )
    # With default rules this deviation is too large — score penalty applies
    ctx_default = _build_strategy_context(
        market=_approved_market(), row=row, position=None,
        positions_available=False, short_list_symbols=set(),
    )
    # With loosened rules the deviation is within threshold — score is higher
    loose_rules = {
        "bull_strangle": {
            "max_price_deviation_pct": 0.15,  # wider gate
            "max_credit_deviation": 2.50,
            "minimum_total_credit": 0.01,
        },
        "dca": DEFAULT_RULES["dca"],
    }
    ctx_loose = _build_strategy_context(
        market=_approved_market(), row=row, position=None,
        positions_available=False, short_list_symbols=set(),
        rules=loose_rules,
    )
    assert ctx_loose["strategy_score"] > ctx_default["strategy_score"]
