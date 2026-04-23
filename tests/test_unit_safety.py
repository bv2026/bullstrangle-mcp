from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bullstrangle_mcp import ingestion
from bullstrangle_mcp.database import connect, initialize_database


def _patch_minimal_ingestion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ingestion,
        "extract_pdf_pages",
        lambda pdf: [ingestion.PageText(1, "dummy newsletter text")],
    )
    monkeypatch.setattr(
        ingestion,
        "parse_publication_date",
        lambda full_text, pdf: date(2026, 4, 17),
    )
    monkeypatch.setattr(
        ingestion,
        "parse_entry_expiration",
        lambda full_text, publication_date: (date(2026, 4, 20), date(2026, 5, 15)),
    )
    monkeypatch.setattr(ingestion, "infer_option_type", lambda full_text: "monthly")
    monkeypatch.setattr(
        ingestion,
        "extract_sections",
        lambda pages: {
            "watchlist_screening": [],
            "watchlist_option_prices": [],
            "short_lists": [],
            "stock_market_weekly_recap": [],
            "market_commentary": [],
            "market_environment": [],
            "watchlist_favorites": [],
            "strategy_reference": [],
        },
    )
    monkeypatch.setattr(
        ingestion,
        "parse_watchlist_option_prices",
        lambda pages: [
            {
                "symbol": "NTAP",
                "description": "NetApp",
                "stock_price": 100.0,
                "implied_volatility": 0.34,
                "sector": "Technology",
                "sell_call_strike": 104.0,
                "sell_call_premium": 1.25,
                "sell_put_strike": 96.0,
                "sell_put_premium": 1.10,
                "buy_put_strike": 88.0,
                "buy_put_premium": 0.55,
                "bull_strangle_return_pct": 5.0,
                "put_credit_spread_return_pct": 2.0,
                "covered_call_return_pct": 1.0,
                "source_page": 1,
                "raw_line": "NTAP minimal row",
            }
        ],
    )
    monkeypatch.setattr(ingestion, "parse_watchlist_screening_details", lambda pages, symbols: {})
    monkeypatch.setattr(ingestion, "enrich_watchlist_with_screening_details", lambda watchlist, details: None)
    monkeypatch.setattr(ingestion, "parse_short_lists", lambda pages, symbols: [])
    monkeypatch.setattr(
        ingestion,
        "parse_market_environment",
        lambda pages, publication_date: {
            "sp500_price": 7126.06,
            "sp500_200dma": 6685.57,
            "sp500_vs_200dma": 440.49,
            "sp500_above_200dma": True,
            "vix": 17.48,
            "vix_below_25": True,
            "breadth_pct": 59.84,
            "breadth_above_40": True,
            "trend_score": 1,
            "volatility_score": 1,
            "breadth_score": 0,
            "hybrid_score": 2,
            "hybrid_bullish": True,
            "market_status": "green",
            "market_regime": "full_exposure",
            "investment_percent": 100,
            "cash_reserve_target": 25.0,
            "all_criteria_met": True,
            "consecutive_weeks_met": 0,
            "deployment_approved": False,
            "recommended_position_count": 1,
            "scaling_phase": "rebuild_week1",
            "raw_row": "minimal env row",
        },
    )
    monkeypatch.setattr(
        ingestion,
        "build_market_commentary",
        lambda pages, environment: {
            "raw_text": "minimal commentary",
            "commentary_json": {"sections": []},
            "source_pages": [],
        },
    )
    monkeypatch.setattr(ingestion, "parse_watchlist_favorites", lambda pages, watchlist: [])


def test_ingest_newsletter_requires_force_to_replace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    _patch_minimal_ingestion(monkeypatch)
    db = tmp_path / "bullstrangle.db"
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    first = ingestion.ingest_newsletter(pdf, db)

    with pytest.raises(ValueError, match="force=True"):
        ingestion.ingest_newsletter(pdf, db)

    with connect(db) as conn:
        newsletters = conn.execute("SELECT newsletter_id, publication_date FROM newsletters").fetchall()
        assert len(newsletters) == 1
        assert newsletters[0]["newsletter_id"] == first["newsletter_id"]
        assert newsletters[0]["publication_date"] == "2026-04-17"

    replaced = ingestion.ingest_newsletter(pdf, db, force=True)

    with connect(db) as conn:
        newsletters = conn.execute("SELECT newsletter_id FROM newsletters").fetchall()
        assert len(newsletters) == 1
        assert newsletters[0]["newsletter_id"] == replaced["newsletter_id"]
        assert replaced["newsletter_id"] != first["newsletter_id"]


def test_ingest_directory_continues_after_pdf_error(tmp_path, monkeypatch: pytest.MonkeyPatch):
    good_pdf = tmp_path / "good.pdf"
    bad_pdf = tmp_path / "bad.pdf"
    good_pdf.write_bytes(b"%PDF-1.4\n")
    bad_pdf.write_bytes(b"%PDF-1.4\n")

    def fake_ingest(pdf_path, db_path, force=False):
        if Path(pdf_path).name == "bad.pdf":
            raise ValueError("broken pdf")
        return {"pdf_path": str(Path(pdf_path).resolve()), "status": "ingested"}

    monkeypatch.setattr(ingestion, "ingest_newsletter", fake_ingest)

    results = ingestion.ingest_directory(tmp_path, tmp_path / "bullstrangle.db")

    assert len(results) == 2
    assert any(row["status"] == "ingested" for row in results)
    error_row = next(row for row in results if row["status"] == "error")
    assert error_row["error"] == "broken pdf"
    assert error_row["pdf_path"].endswith("bad.pdf")


def test_database_connect_enables_wal_and_composite_index(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    with connect(db) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'os_evaluation_rows'"
            ).fetchall()
        }

    assert str(journal_mode).lower() == "wal"
    assert "idx_os_rows_newsletter_symbol" in indexes
