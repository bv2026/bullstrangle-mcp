from __future__ import annotations

from bullstrangle_mcp.database import connect, initialize_database
from bullstrangle_mcp.tools import get_symbol_history_tool


def _seed_newsletter(conn, newsletter_id: int, publication_date: str) -> None:
    conn.execute(
        """
        INSERT INTO newsletters
        (newsletter_id, publication_date, pdf_path, pdf_sha256, target_expiration,
         entry_date, option_type, days_to_expiration, ingestion_method)
        VALUES (?, ?, ?, ?, ?, ?, 'weekly', 28, 'test')
        """,
        (
            newsletter_id,
            publication_date,
            f"C:/tmp/{publication_date}.pdf",
            f"hash-{newsletter_id}",
            "2026-05-15",
            publication_date,
        ),
    )


def test_get_symbol_history_tool_marks_existing_symbol_correctly(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    with connect(db) as conn:
        _seed_newsletter(conn, 1, "2026-03-27")
        _seed_newsletter(conn, 2, "2026-04-17")
        conn.executemany(
            """
            INSERT INTO symbol_history
            (symbol, newsletter_id, publication_date, on_watchlist, on_short_list, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("NTAP", 1, "2026-03-27", 1, 0, "{}"),
                ("NTAP", 2, "2026-04-17", 1, 1, "{}"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO watchlist_entries
            (newsletter_id, newsletter_date, expiration_date, symbol, description, sector, stock_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-03-27", "2026-04-24", "NTAP", "NetApp", "Technology", 98.0),
                (2, "2026-04-17", "2026-05-15", "NTAP", "NetApp", "Technology", 104.0),
            ],
        )
        conn.commit()

    result = get_symbol_history_tool("NTAP", str(db), "2026-04-17")

    assert result["symbol"] == "NTAP"
    assert result["occurrence_count"] == 2
    assert result["present_on_newsletter_date"] is True
    assert result["is_new_for_newsletter_date"] is False
    assert result["prior_occurrence_count"] == 1
    assert result["latest_prior_publication_date"] == "2026-03-27"
    assert result["watchlist_count"] == 2
    assert result["short_list_count"] == 1


def test_get_symbol_history_tool_marks_first_appearance_as_new(tmp_path):
    db = tmp_path / "bullstrangle.db"
    initialize_database(db)

    with connect(db) as conn:
        _seed_newsletter(conn, 1, "2026-04-17")
        conn.execute(
            """
            INSERT INTO symbol_history
            (symbol, newsletter_id, publication_date, on_watchlist, on_short_list, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("IMVT", 1, "2026-04-17", 1, 1, "{}"),
        )
        conn.commit()

    result = get_symbol_history_tool("IMVT", str(db), "2026-04-17")

    assert result["present_on_newsletter_date"] is True
    assert result["is_new_for_newsletter_date"] is True
    assert result["prior_occurrence_count"] == 0
