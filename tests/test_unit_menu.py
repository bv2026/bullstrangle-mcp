"""Unit tests for bullstrangle_menu.py helper functions."""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import bullstrangle_menu as menu


# ─── get_friday ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("today_str,expected_friday", [
    ("2026-05-10", "2026-05-08"),  # Sunday → previous Friday
    ("2026-05-08", "2026-05-08"),  # Friday → same day
    ("2026-05-11", "2026-05-08"),  # Monday → previous Friday
    ("2026-05-13", "2026-05-08"),  # Wednesday → previous Friday
    ("2026-05-14", "2026-05-08"),  # Thursday → previous Friday
])
def test_get_friday(today_str, expected_friday, monkeypatch):
    fake_today = date.fromisoformat(today_str)
    monkeypatch.setattr(menu, "date", type("FakeDate", (), {
        "today": staticmethod(lambda: fake_today),
    }))
    assert menu.get_friday() == expected_friday


# ─── format_table ────────────────────────────────────────────────────────────


def test_format_table_basic():
    rows = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    result = menu.format_table(rows, ["id", "name"])
    assert "Alice" in result
    assert "Bob" in result
    assert "(2 rows)" in result


def test_format_table_empty():
    assert "no data" in menu.format_table([])


def test_format_table_auto_columns():
    rows = [{"a": 1, "b": 2}]
    result = menu.format_table(rows)
    assert "a" in result
    assert "b" in result


def test_format_table_missing_column():
    rows = [{"a": 1}]
    result = menu.format_table(rows, ["a", "b"])
    assert "1" in result


# ─── report_path / daily_report_path ─────────────────────────────────────────


def test_report_path(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "REPORTS_DIR", tmp_path)
    p = menu.report_path("2026-05-08", "market_brief")
    assert p == tmp_path / "weekly" / "2026-05-08" / "market_brief.md"
    assert p.parent.exists()


def test_daily_report_path(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "REPORTS_DIR", tmp_path)
    p = menu.daily_report_path("2026-05-12", "gate_report")
    assert p == tmp_path / "daily" / "2026-05-12" / "gate_report.md"
    assert p.parent.exists()


# ─── save_path ───────────────────────────────────────────────────────────────


def test_save_path_weekly(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "REPORTS_DIR", tmp_path)
    result = menu.save_path("2026-05-08", "action_plan")
    assert "weekly" in result
    assert "action_plan.md" in result


def test_save_path_daily(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "REPORTS_DIR", tmp_path)
    result = menu.save_path("2026-05-12", "daily_brief", daily=True)
    assert "daily" in result
    assert "daily_brief.md" in result


# ─── latest_run_id ───────────────────────────────────────────────────────────


def test_latest_run_id_returns_most_recent(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "bullstrangle.db"
    db_path.parent.mkdir(parents=True)
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    monkeypatch.setattr(menu, "DB", str(db_path.relative_to(tmp_path)))

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE os_evaluation_runs (
            run_id INTEGER PRIMARY KEY,
            newsletter_date TEXT,
            trading_date TEXT
        )
    """)
    conn.execute("INSERT INTO os_evaluation_runs VALUES (10, '2026-05-08', '2026-05-12')")
    conn.execute("INSERT INTO os_evaluation_runs VALUES (11, '2026-05-08', '2026-05-13')")
    conn.execute("INSERT INTO os_evaluation_runs VALUES (12, '2026-05-01', '2026-05-05')")
    conn.commit()
    conn.close()

    assert menu.latest_run_id("2026-05-08") == "11"
    assert menu.latest_run_id("2026-05-01") == "12"
    assert menu.latest_run_id("2099-01-01") is None


def test_latest_run_id_no_db(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    monkeypatch.setattr(menu, "DB", "nonexistent.db")
    assert menu.latest_run_id("2026-05-08") is None


# ─── newsletter_exists ───────────────────────────────────────────────────────


def test_newsletter_exists(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "bullstrangle.db"
    db_path.parent.mkdir(parents=True)
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    monkeypatch.setattr(menu, "DB", str(db_path.relative_to(tmp_path)))

    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE newsletters (publication_date TEXT)")
    conn.execute("INSERT INTO newsletters VALUES ('2026-05-08')")
    conn.commit()
    conn.close()

    assert menu.newsletter_exists("2026-05-08") is True
    assert menu.newsletter_exists("2099-01-01") is False


def test_newsletter_exists_no_db(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    monkeypatch.setattr(menu, "DB", "nonexistent.db")
    assert menu.newsletter_exists("2026-05-08") is False


# ─── find_newsletter_pdf ─────────────────────────────────────────────────────


def test_find_newsletter_pdf_match(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    nl_dir = tmp_path / "data" / "newsletters"
    nl_dir.mkdir(parents=True)
    pdf = nl_dir / "BullStrangle_May_8_2026.pdf"
    pdf.write_text("fake")

    result = menu.find_newsletter_pdf("2026-05-08")
    assert result is not None
    assert result.name == "BullStrangle_May_8_2026.pdf"


def test_find_newsletter_pdf_no_match(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    nl_dir = tmp_path / "data" / "newsletters"
    nl_dir.mkdir(parents=True)
    (nl_dir / "BullStrangle_April_10_2026.pdf").write_text("fake")

    assert menu.find_newsletter_pdf("2026-05-08") is None


def test_find_newsletter_pdf_no_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    assert menu.find_newsletter_pdf("2026-05-08") is None


# ─── prompt_required ─────────────────────────────────────────────────────────


def test_prompt_required_with_value(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "AAPL")
    assert menu.prompt_required("Symbol") == "AAPL"


def test_prompt_required_empty(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = menu.prompt_required("Symbol")
    assert result == ""
    assert "Skipped" in capsys.readouterr().out


# ─── run_cmd error handling ──────────────────────────────────────────────────


def test_run_cmd_error_skips_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    report = str(tmp_path / "should_not_exist.md")
    menu.run_cmd(["--help-nonexistent"], report=report)
    assert not Path(report).exists()
    assert "ERROR" in capsys.readouterr().out


def test_run_cmd_success_saves_report(tmp_path, monkeypatch):
    monkeypatch.setattr(menu, "BASE_DIR", tmp_path)
    report = str(tmp_path / "output.md")
    menu.run_cmd(["--help"], report=report)
    assert Path(report).exists()
