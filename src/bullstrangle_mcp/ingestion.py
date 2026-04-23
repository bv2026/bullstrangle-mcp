from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .database import DEFAULT_DB_PATH, connect, initialize_database


SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "ETF",
    "Financials",
    "Healthcare",
    "Industrials",
    "Materials",
    "Real Estate",
    "Technology",
    "Utilities",
]

SECTOR_PATTERN = "|".join(re.escape(s) for s in SECTORS)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class PageText:
    page_number: int
    text: str


def ingest_newsletter(
    pdf_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    force: bool = False,
) -> dict[str, Any]:
    """Parse and ingest one weekly newsletter PDF into SQLite."""
    initialize_database(db_path)
    pdf = Path(pdf_path)
    pages = extract_pdf_pages(pdf)
    full_text = "\n\n".join(page.text for page in pages)

    publication_date = parse_publication_date(full_text, pdf)
    entry_date, expiration_date = parse_entry_expiration(full_text, publication_date)
    option_type = infer_option_type(full_text)
    sections = extract_sections(pages)
    watchlist = parse_watchlist_option_prices(sections.get("watchlist_option_prices", []))
    enrich_watchlist_with_screening_details(
        watchlist,
        parse_watchlist_screening_details(
            sections.get("watchlist_screening", []), {row["symbol"] for row in watchlist}
        ),
    )
    short_list = parse_short_lists(sections.get("short_lists", []), {row["symbol"] for row in watchlist})
    environment = parse_market_environment(sections.get("market_environment", []), publication_date)
    market_commentary = build_market_commentary(sections.get("market_commentary", []), environment)
    favorites = parse_watchlist_favorites(sections.get("watchlist_favorites", []), watchlist)

    target_expiration = expiration_date
    days_to_expiration = (target_expiration - entry_date).days if entry_date else 28
    file_hash = sha256_file(pdf)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT newsletter_id FROM newsletters WHERE publication_date = ?",
            (publication_date.isoformat(),),
        ).fetchone()
        if existing:
            if not force:
                raise ValueError(
                    "Newsletter already exists for "
                    f"{publication_date.isoformat()}; re-run with force=True to replace it."
                )
            conn.execute("DELETE FROM newsletters WHERE newsletter_id = ?", (existing["newsletter_id"],))

        cur = conn.execute(
            """
            INSERT INTO newsletters
            (publication_date, pdf_path, pdf_sha256, target_expiration, entry_date,
             option_type, days_to_expiration, market_outlook, strategy_notes,
             market_commentary_structured, ingestion_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pypdf')
            """,
            (
                publication_date.isoformat(),
                str(pdf.resolve()),
                file_hash,
                target_expiration.isoformat() if target_expiration else None,
                entry_date.isoformat() if entry_date else None,
                option_type,
                days_to_expiration,
                market_commentary["raw_text"],
                section_text(sections.get("strategy_reference", [])),
                json.dumps(market_commentary["commentary_json"], sort_keys=True),
            ),
        )
        newsletter_id = int(cur.lastrowid)

        insert_full_text_sections(conn, newsletter_id, publication_date, sections, full_text)
        insert_market_environment(conn, newsletter_id, publication_date, environment, market_commentary)
        insert_watchlist(conn, newsletter_id, publication_date, target_expiration, watchlist)
        insert_short_list(conn, newsletter_id, publication_date, short_list)
        mark_favorites_and_insert_analysis(conn, newsletter_id, publication_date, favorites)
        insert_reference_sections(conn, newsletter_id, publication_date, pdf, sections)
        insert_decisions_and_history(conn, newsletter_id, publication_date)
        conn.commit()

    return {
        "newsletter_id": newsletter_id,
        "publication_date": publication_date.isoformat(),
        "entry_date": entry_date.isoformat() if entry_date else None,
        "target_expiration": target_expiration.isoformat() if target_expiration else None,
        "option_type": option_type,
        "watchlist_count": len(watchlist),
        "watchlist_screening_detail_count": sum(
            1 for row in watchlist if row.get("total_open_interest") is not None
        ),
        "short_list_count": len(short_list),
        "favorite_count": len(favorites),
        "hybrid_score": environment.get("hybrid_score"),
        "market_status": environment.get("market_status"),
        "deployment_approved": bool(environment.get("deployment_approved")),
        "consecutive_weeks_met": environment.get("consecutive_weeks_met", 0),
        "ingestion_method": "pypdf",
        "warnings": build_warnings(watchlist, environment, sections),
        "status": "ingested",
    }


def extract_pdf_pages(pdf_path: Path) -> list[PageText]:
    reader = PdfReader(str(pdf_path))
    pages: list[PageText] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageText(idx, normalize_pdf_text(text)))
    return pages


def normalize_pdf_text(text: str) -> str:
    replacements = {
        "\u2022": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "C ommunication": "Communication",
        "C onsumer": "Consumer",
        "C overed": "Covered",
        "C redit": "Credit",
        "C all": "Call",
        "C ash": "Cash",
        "C orp": "Corp",
        "C ompany": "Company",
        "C omputers": "Computers",
        "C lean": "Clean",
        "C hemours": "Chemours",
        "C VS": "CVS",
        "C SC O": "CSCO",
        "C TRA": "CTRA",
        "C AVA": "CAVA",
        "PAC S": "PACS",
        "IC LN": "ICLN",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def parse_publication_date(full_text: str, pdf_path: Path) -> date:
    match = re.search(r"Week Ended\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", full_text)
    if match:
        return date(int(match.group(3)), MONTHS[match.group(1).lower()], int(match.group(2)))

    filename = pdf_path.stem.replace("-", " ")
    match = re.search(r"Week End\s+([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", filename)
    if match:
        return date(int(match.group(3)), MONTHS[match.group(1).lower()], int(match.group(2)))
    raise ValueError(f"Could not determine publication date for {pdf_path}")


def parse_entry_expiration(full_text: str, publication_date: date) -> tuple[date | None, date | None]:
    match = re.search(
        r"Watch List for\s+([A-Za-z]+)\s+(\d{1,2})\s+Entry\s*/\s*([A-Za-z]+)\s+(\d{1,2})\s+Expiration",
        full_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    entry = month_day_to_date(match.group(1), int(match.group(2)), publication_date)
    expiration = month_day_to_date(match.group(3), int(match.group(4)), publication_date)
    if expiration < entry:
        expiration = date(expiration.year + 1, expiration.month, expiration.day)
    return entry, expiration


def month_day_to_date(month_name: str, day: int, publication_date: date) -> date:
    month = MONTHS[month_name.lower()]
    year = publication_date.year
    candidate = date(year, month, day)
    if candidate < publication_date and month < publication_date.month:
        candidate = date(year + 1, month, day)
    return candidate


def infer_option_type(full_text: str) -> str:
    lower = full_text.lower()
    monthly_hits = len(re.findall(r"monthly option", lower))
    weekly_hits = len(re.findall(r"weekly option", lower))
    return "monthly" if monthly_hits > weekly_hits else "weekly"


def extract_sections(pages: list[PageText]) -> dict[str, list[PageText]]:
    sections: dict[str, list[PageText]] = {
        "watchlist_screening": [],
        "watchlist_option_prices": [],
        "short_lists": [],
        "stock_market_weekly_recap": [],
        "market_commentary": [],
        "market_environment": [],
        "watchlist_favorites": [],
        "strategy_reference": [],
    }
    for page in pages:
        text = page.text
        compact = " ".join(text.split())
        if "Watch List for" in text and "Symbol Name" in text:
            sections["watchlist_screening"].append(page)
        if "Watch List with Option Price" in text:
            sections["watchlist_option_prices"].append(page)
        if "The Short List" in text:
            sections["short_lists"].append(page)
        if "Stock Market Weekly Recap" in text:
            sections["stock_market_weekly_recap"].append(page)
            sections["market_commentary"].append(page)
        if (
            "Market Overview" in text
            and "S&P 500" in text
            and "Market Environment Awareness" not in text
        ):
            sections["market_commentary"].append(page)
        if "Market Environment Awareness" in text:
            sections["market_environment"].append(page)
            sections["market_commentary"].append(page)
        if "Watch List Favorites" in text or "Additional Detail" in text:
            sections["watchlist_favorites"].append(page)
        if (
            "Strategy Benefits" in text
            or "Strategy Overview Core Elements" in text
            or "Trade Management Suggestions" in text
        ):
            sections["strategy_reference"].append(page)
    return sections


def parse_watchlist_screening_details(
    pages: list[PageText], watchlist_symbols: set[str]
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    row_pattern = re.compile(
        r"^(?P<name>.+?)\s+"
        r"(?P<last>\d{1,4}(?:\.\d+)?)\s+"
        r"(?P<iv>\d{1,3}(?:\.\d+)?)%\s+"
        r"(?P<oi>\d{3,})\s*"
        r"(?P<tail>.+)$"
    )
    earnings_pattern = re.compile(r"(?P<weekly>Yes|No)\s+(?P<earnings>N/A|\d{1,2}/\d{1,2}/\d{4})")
    for page in pages:
        for line in page.text.splitlines():
            compact = " ".join(line.split())
            symbol, remainder = split_screening_symbol(compact, watchlist_symbols)
            if not symbol:
                continue
            match = row_pattern.match(remainder)
            if not match:
                continue
            tail = match.group("tail")
            earnings_match = earnings_pattern.search(tail)
            if not earnings_match:
                continue
            pre_earnings = tail[: earnings_match.start()].strip()
            post_earnings = tail[earnings_match.end() :].strip()
            sector = find_sector(post_earnings) or find_sector(tail)
            industry, sub_sector = split_industry_sub_sector(pre_earnings)
            details[symbol] = {
                "screening_name": cleanup_name(match.group("name")),
                "total_open_interest": int(match.group("oi")),
                "industry": industry,
                "sub_sector": sub_sector,
                "weekly_options": earnings_match.group("weekly") == "Yes",
                "latest_earnings": None
                if earnings_match.group("earnings") == "N/A"
                else earnings_match.group("earnings"),
                "screening_sector": sector,
                "screening_source_page": page.page_number,
                "screening_raw_line": compact,
            }
    return details


def split_screening_symbol(
    line: str, watchlist_symbols: set[str]
) -> tuple[str | None, str]:
    for symbol in sorted(watchlist_symbols, key=len, reverse=True):
        if line.startswith(f"{symbol} "):
            return symbol, line[len(symbol) + 1 :].strip()
    return None, line


def enrich_watchlist_with_screening_details(
    watchlist: list[dict[str, Any]], details: dict[str, dict[str, Any]]
) -> None:
    for row in watchlist:
        detail = details.get(row["symbol"])
        if not detail:
            continue
        row.update(detail)


def find_sector(text: str) -> str | None:
    for sector in SECTORS:
        if sector in text:
            return sector
    return None


def split_industry_sub_sector(value: str) -> tuple[str | None, str | None]:
    value = cleanup_name(value.replace("N/A N/A", "N/A"))
    if not value or value == "N/A":
        return None, None
    known_subsectors = [
        "Computers and Technology",
        "Consumer Discretionary",
        "Consumer Staples",
        "Retail-Wholesale",
        "Basic Materials",
        "Business Services",
        "Medical",
        "Transportation",
        "Finance",
        "Energy",
        "Technology",
    ]
    for sub_sector in known_subsectors:
        if value.endswith(sub_sector):
            industry = cleanup_name(value[: -len(sub_sector)])
            return industry or None, sub_sector
    parts = value.rsplit(" ", 2)
    return value, None


def build_market_commentary(pages: list[PageText], environment: dict[str, Any]) -> dict[str, Any]:
    unique_pages = dedupe_pages(pages)
    raw_text = section_text(unique_pages)
    commentary_json = {
        "sections": [],
        "market_environment_snapshot": {
            key: environment.get(key)
            for key in [
                "sp500_price",
                "sp500_200dma",
                "vix",
                "breadth_pct",
                "trend_score",
                "volatility_score",
                "breadth_score",
                "hybrid_score",
                "market_regime",
                "market_status",
                "investment_percent",
                "cash_reserve_target",
            ]
            if key in environment
        },
        "tags": infer_market_tags(raw_text, environment),
    }
    for page in unique_pages:
        title = infer_market_commentary_title(page.text)
        commentary_json["sections"].append(
            {
                "title": title,
                "page": page.page_number,
                "text": cleanup_repeated_headers(page.text),
            }
        )
    return {
        "raw_text": raw_text,
        "commentary_json": commentary_json,
        "source_pages": [page.page_number for page in unique_pages],
    }


def dedupe_pages(pages: list[PageText]) -> list[PageText]:
    seen: set[int] = set()
    result: list[PageText] = []
    for page in pages:
        if page.page_number in seen:
            continue
        seen.add(page.page_number)
        result.append(page)
    return result


def infer_market_commentary_title(text: str) -> str:
    compact = " ".join(text.split())
    if "Stock Market Weekly Recap" in compact:
        return "Stock Market Weekly Recap"
    if "Market Overview" in compact and "S&P 500" in compact:
        return "Market Overview - S&P 500"
    if "Market Environment Awareness" in compact:
        return "Market Environment Awareness"
    if "Market Overview" in compact:
        return "Market Overview"
    return "Market Commentary"


def infer_market_tags(raw_text: str, environment: dict[str, Any]) -> list[str]:
    text = raw_text.lower()
    tags: set[str] = set()
    if "uptrend" in text:
        tags.add("uptrend")
    if "defensive" in text:
        tags.add("defensive")
    if "constructive" in text:
        tags.add("constructive")
    if "risk-off" in text or "risk off" in text:
        tags.add("risk_off")
    if "technology" in text:
        tags.add("technology")
    if environment.get("hybrid_score") is not None:
        tags.add(f"hybrid_{environment['hybrid_score']}")
    if environment.get("market_regime"):
        tags.add(str(environment["market_regime"]).lower())
    return sorted(tags)


def parse_watchlist_option_prices(pages: list[PageText]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    row_pattern = re.compile(
        rf"^(?P<symbol>[A-Z0-9](?:[A-Z0-9 ]{{0,6}}?))\s+"
        rf"(?P<description>.+?)\s+"
        rf"(?P<last>\d{{1,4}}\.\d{{2}})\$\s+"
        rf"(?P<iv>\d{{1,3}})%\s+"
        rf"(?P<sector>{SECTOR_PATTERN})\s+"
        rf"(?P<rest>.+)$"
    )
    for page in pages:
        for line in page.text.splitlines():
            line = " ".join(line.split())
            match = row_pattern.match(line)
            if not match:
                continue
            rest = match.group("rest")
            nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", rest)]
            if len(nums) < 9:
                continue
            symbol = normalize_symbol(match.group("symbol"))
            rows.append(
                {
                    "symbol": symbol,
                    "description": cleanup_name(match.group("description")),
                    "stock_price": float(match.group("last")),
                    "implied_volatility": float(match.group("iv")) / 100.0,
                    "sector": match.group("sector"),
                    "sell_call_strike": nums[0],
                    "sell_call_premium": nums[1],
                    "sell_put_strike": nums[2],
                    "sell_put_premium": nums[3],
                    "buy_put_strike": nums[4],
                    "buy_put_premium": nums[5],
                    "bull_strangle_return_pct": nums[6],
                    "put_credit_spread_return_pct": nums[7],
                    "covered_call_return_pct": nums[8],
                    "source_page": page.page_number,
                    "raw_line": line,
                }
            )
    return dedupe_by_symbol(rows)


def parse_short_lists(pages: list[PageText], watchlist_symbols: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not pages:
        return rows

    for page in pages:
        portfolio = "large"
        ranks = {"large": 0, "small": 0}
        header_count = 0
        for line in page.text.splitlines():
            compact = " ".join(line.split())
            if compact.startswith("Symbol Name"):
                header_count += 1
                if header_count >= 2:
                    portfolio = "small"
                continue
            if not compact:
                continue
            first = normalize_symbol(compact.split(" ", 1)[0])
            if first in watchlist_symbols:
                ranks[portfolio] += 1
                rows.append(
                    {
                        "portfolio_type": portfolio,
                        "symbol": first,
                        "rank": ranks[portfolio],
                        "source_page": page.page_number,
                        "raw_line": compact,
                    }
                )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["portfolio_type"], row["symbol"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def parse_market_environment(pages: list[PageText], publication_date: date) -> dict[str, Any]:
    target = f"{publication_date.month}/{publication_date.day}/{publication_date.year}"
    row_pattern = re.compile(
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"(?P<spx>[\d,]+\.\d+)\s+"
        r"(?P<vix>\d+\.\d+)\s+"
        r"(?P<breadth>\d+\.\d+)\s+"
        r"(?P<dma>[\d,]+\.\d+)\s+"
        r"(?P<trend>-?\d+)\s+"
        r"(?P<vix_score>-?\d+)\s+"
        r"(?P<breadth_score>-?\d+)\s+"
        r"(?P<hybrid>-?\d+)\s+"
        r"(?P<regime>[A-Za-z]+)\s+"
        r"(?P<position>\d+)%\s+"
        r"(?P<cash>\d+(?:\.\d+)?)%"
    )
    latest: dict[str, Any] | None = None
    for page in pages:
        for line in page.text.splitlines():
            compact = " ".join(line.split())
            match = row_pattern.search(compact)
            if not match:
                continue
            row_date = match.group("date")
            parsed = {
                "raw_row": compact,
                "row_date": row_date,
                "sp500_price": number(match.group("spx")),
                "vix": number(match.group("vix")),
                "breadth_pct": number(match.group("breadth")),
                "sp500_200dma": number(match.group("dma")),
                "trend_score": int(match.group("trend")),
                "volatility_score": int(match.group("vix_score")),
                "breadth_score": int(match.group("breadth_score")),
                "hybrid_score": int(match.group("hybrid")),
                "market_regime": match.group("regime"),
                "investment_percent": int(match.group("position")),
                "cash_reserve_target": float(match.group("cash")),
            }
            latest = parsed
            if row_date == target:
                latest = parsed
                break
    if not latest:
        return {}

    spx = latest["sp500_price"]
    dma = latest["sp500_200dma"]
    vix = latest["vix"]
    breadth = latest["breadth_pct"]
    hybrid = latest["hybrid_score"]
    all_criteria_met = spx > dma and vix < 25 and breadth > 40 and hybrid >= 0
    latest.update(
        {
            "sp500_vs_200dma": spx - dma,
            "sp500_above_200dma": spx > dma,
            "vix_below_25": vix < 25,
            "breadth_above_40": breadth > 40,
            "hybrid_bullish": hybrid >= 0,
            "all_criteria_met": all_criteria_met,
            "market_status": status_from_investment(latest["investment_percent"], hybrid),
            "consecutive_weeks_met": 1 if all_criteria_met else 0,
            "deployment_approved": False,
            "recommended_position_count": 1 if all_criteria_met else 0,
            "scaling_phase": "rebuild_week1" if all_criteria_met else "pause",
        }
    )
    return latest


def parse_watchlist_favorites(pages: list[PageText], watchlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_description = {row["description"].lower(): row["symbol"] for row in watchlist}
    by_symbol = {row["symbol"]: row for row in watchlist}
    favorites: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    favorite_rank = 0

    title_pattern = re.compile(r"^(.+?)\s+\(([A-Z ]{1,8})\)\s+-\s+(.+?)\s+Sector$")
    for page in pages:
        lines = page.text.splitlines()
        page_text = "\n".join(lines)
        for line in lines:
            compact = " ".join(line.split())
            match = title_pattern.match(compact)
            if match:
                if current:
                    favorites.append(current)
                favorite_rank += 1
                symbol = normalize_symbol(match.group(2))
                current = {
                    "symbol": symbol,
                    "favorite_rank": favorite_rank,
                    "company_name": cleanup_name(match.group(1)),
                    "sector": cleanup_name(match.group(3)),
                    "pages": [page.page_number],
                    "content": [],
                }
        if current:
            current["pages"].append(page.page_number)
            current["content"].append(page_text)

    if current:
        favorites.append(current)

    merged: dict[str, dict[str, Any]] = {}
    for fav in favorites:
        existing = merged.get(fav["symbol"])
        if not existing:
            merged[fav["symbol"]] = fav
            continue
        existing["pages"].extend(fav["pages"])
        existing["content"].extend(fav["content"])

    normalized: list[dict[str, Any]] = []
    for fav in merged.values():
        symbol = fav["symbol"]
        content = "\n\n".join(fav["content"])
        proposed_trade = parse_proposed_trade(content, by_symbol.get(symbol, {}))
        normalized.append(
            {
                "symbol": symbol,
                "favorite_rank": fav["favorite_rank"],
                "analysis_data": {
                    "company_name": fav["company_name"],
                    "sector": fav["sector"],
                    "source_summary": cleanup_repeated_headers(content),
                    "proposed_trade": proposed_trade,
                },
                "has_proposed_trade": bool(proposed_trade),
                "source_pages": sorted(set(fav["pages"])),
            }
        )
    return normalized


def parse_proposed_trade(content: str, watchlist_row: dict[str, Any]) -> dict[str, Any]:
    if not watchlist_row and "Total Investment" not in content:
        return {}
    trade = {
        "structure": "bull_strangle",
        "stock": {
            "shares": 100,
            "price": watchlist_row.get("stock_price"),
        },
        "sell_call": {
            "strike": watchlist_row.get("sell_call_strike"),
            "premium": watchlist_row.get("sell_call_premium"),
        },
        "sell_put": {
            "strike": watchlist_row.get("sell_put_strike"),
            "premium": watchlist_row.get("sell_put_premium"),
        },
        "buy_put": {
            "strike": watchlist_row.get("buy_put_strike"),
            "premium": watchlist_row.get("buy_put_premium"),
        },
    }
    total = re.search(r"Total Investment\s+([\d,]+)\$", content)
    max_gain = re.search(r"Max Gain\s+([\d,]+)\$", content)
    max_gain_pct = re.search(r"Max Gain %\s+(\d+(?:\.\d+)?)%", content)
    if total or max_gain or max_gain_pct:
        trade["summary"] = {
            "total_investment": int(total.group(1).replace(",", "")) if total else None,
            "max_gain": int(max_gain.group(1).replace(",", "")) if max_gain else None,
            "max_gain_pct": float(max_gain_pct.group(1)) if max_gain_pct else None,
        }
    return trade


def insert_full_text_sections(
    conn,
    newsletter_id: int,
    publication_date: date,
    sections: dict[str, list[PageText]],
    full_text: str,
) -> None:
    rows = [("full_text", None, None, full_text)]
    for name, pages in sections.items():
        if not pages:
            continue
        page_numbers = [p.page_number for p in pages]
        rows.append((name, min(page_numbers), max(page_numbers), section_text(pages)))
    conn.executemany(
        """
        INSERT INTO newsletter_full_text
        (newsletter_id, newsletter_date, section_name, page_start, page_end, content)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (newsletter_id, publication_date.isoformat(), name, start, end, content)
            for name, start, end, content in rows
        ],
    )


def insert_market_environment(
    conn,
    newsletter_id: int,
    publication_date: date,
    env: dict[str, Any],
    commentary: dict[str, Any],
) -> None:
    if not env:
        return
    conn.execute(
        """
        INSERT INTO market_environment
        (newsletter_id, publication_date, sp500_price, sp500_200dma, sp500_vs_200dma,
         sp500_above_200dma, vix, vix_below_25, breadth_pct, breadth_above_40,
         trend_score, volatility_score, breadth_score, hybrid_score, hybrid_bullish,
         market_status, market_regime, investment_percent, cash_reserve_target,
         all_criteria_met, consecutive_weeks_met, deployment_approved,
         recommended_position_count, scaling_phase, raw_row, commentary_raw_text,
         commentary_json, commentary_source_pages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            newsletter_id,
            publication_date.isoformat(),
            env.get("sp500_price"),
            env.get("sp500_200dma"),
            env.get("sp500_vs_200dma"),
            bool_int(env.get("sp500_above_200dma")),
            env.get("vix"),
            bool_int(env.get("vix_below_25")),
            env.get("breadth_pct"),
            bool_int(env.get("breadth_above_40")),
            env.get("trend_score"),
            env.get("volatility_score"),
            env.get("breadth_score"),
            env.get("hybrid_score"),
            bool_int(env.get("hybrid_bullish")),
            env.get("market_status"),
            env.get("market_regime"),
            env.get("investment_percent"),
            env.get("cash_reserve_target"),
            bool_int(env.get("all_criteria_met")),
            env.get("consecutive_weeks_met", 0),
            bool_int(env.get("deployment_approved")),
            env.get("recommended_position_count", 0),
            env.get("scaling_phase"),
            env.get("raw_row"),
            commentary.get("raw_text"),
            json.dumps(commentary.get("commentary_json", {}), sort_keys=True),
            json.dumps(commentary.get("source_pages", [])),
        ),
    )


def insert_watchlist(
    conn,
    newsletter_id: int,
    publication_date: date,
    expiration_date: date | None,
    watchlist: list[dict[str, Any]],
) -> None:
    conn.executemany(
        """
        INSERT INTO watchlist_entries
        (newsletter_id, newsletter_date, expiration_date,
         symbol, description, sector, stock_price, implied_volatility,
         total_open_interest, industry, sub_sector, weekly_options, latest_earnings,
         sell_call_strike, sell_call_premium, sell_put_strike, sell_put_premium,
         buy_put_strike, buy_put_premium, bull_strangle_return_pct,
         put_credit_spread_return_pct, covered_call_return_pct, source_page, raw_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                newsletter_id,
                publication_date.isoformat(),
                expiration_date.isoformat() if expiration_date else None,
                row["symbol"],
                row["description"],
                row["sector"],
                row["stock_price"],
                row["implied_volatility"],
                row.get("total_open_interest"),
                row.get("industry"),
                row.get("sub_sector"),
                bool_int(row.get("weekly_options")) if row.get("weekly_options") is not None else None,
                row.get("latest_earnings"),
                row["sell_call_strike"],
                row["sell_call_premium"],
                row["sell_put_strike"],
                row["sell_put_premium"],
                row["buy_put_strike"],
                row["buy_put_premium"],
                row["bull_strangle_return_pct"],
                row["put_credit_spread_return_pct"],
                row["covered_call_return_pct"],
                row["source_page"],
                row["raw_line"],
            )
            for row in watchlist
        ],
    )


def insert_short_list(
    conn, newsletter_id: int, publication_date: date, short_list: list[dict[str, Any]]
) -> None:
    conn.executemany(
        """
        INSERT INTO short_list_entries
        (newsletter_id, newsletter_date, portfolio_type, symbol, rank, source_page, raw_line)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                newsletter_id,
                publication_date.isoformat(),
                row["portfolio_type"],
                row["symbol"],
                row["rank"],
                row["source_page"],
                row["raw_line"],
            )
            for row in short_list
        ],
    )


def mark_favorites_and_insert_analysis(
    conn, newsletter_id: int, publication_date: date, favorites: list[dict[str, Any]]
) -> None:
    for fav in favorites:
        row = conn.execute(
            "SELECT entry_id FROM watchlist_entries WHERE newsletter_id = ? AND symbol = ?",
            (newsletter_id, fav["symbol"]),
        ).fetchone()
        entry_id = row["entry_id"] if row else None
        if entry_id:
            conn.execute("UPDATE watchlist_entries SET is_favorite = 1 WHERE entry_id = ?", (entry_id,))
        conn.execute(
            """
            INSERT INTO watchlist_deep_analysis
            (watchlist_entry_id, newsletter_id, newsletter_date, symbol, analysis_data, is_favorite,
             favorite_rank, has_proposed_trade, source_pages)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                entry_id,
                newsletter_id,
                publication_date.isoformat(),
                fav["symbol"],
                json.dumps(fav["analysis_data"], sort_keys=True),
                fav["favorite_rank"],
                bool_int(fav["has_proposed_trade"]),
                json.dumps(fav["source_pages"]),
            ),
        )


def insert_reference_sections(
    conn,
    newsletter_id: int,
    publication_date: date,
    pdf: Path,
    sections: dict[str, list[PageText]],
) -> None:
    strategy_pages = sections.get("strategy_reference", [])
    if not strategy_pages:
        return
    titles = []
    for page in strategy_pages:
        if "Strategy Benefits" in page.text:
            titles.append(("Strategy Benefits", [page]))
        if "Strategy Overview Core Elements" in page.text:
            titles.append(("Strategy Implementation - Core Elements", [page]))
        if "Trade Management Suggestions" in page.text:
            titles.append(("Trade Management Suggestions", [page]))
    for title, pages in titles:
        page_numbers = [p.page_number for p in pages]
        conn.execute(
            """
            INSERT OR IGNORE INTO strategy_reference_sections
            (newsletter_id, source_newsletter_date, reference_scope, title, content,
             source_pdf_path, page_start, page_end)
            VALUES (?, ?, 'common', ?, ?, ?, ?, ?)
            """,
            (
                newsletter_id,
                publication_date.isoformat(),
                title,
                section_text(pages),
                str(pdf.resolve()),
                min(page_numbers),
                max(page_numbers),
            ),
        )


def insert_decisions_and_history(conn, newsletter_id: int, publication_date: date) -> None:
    env = conn.execute(
        "SELECT * FROM market_environment WHERE newsletter_id = ?", (newsletter_id,)
    ).fetchone()
    all_criteria_met = bool(env["all_criteria_met"]) if env else False
    consecutive = calculate_consecutive_weeks(conn, publication_date, all_criteria_met)
    deployment_approved = all_criteria_met and consecutive >= 2
    action = "deploy" if deployment_approved else ("monitor_only" if all_criteria_met else "pause")
    scaling_phase = "normal" if deployment_approved else ("rebuild_week1" if all_criteria_met else "pause")
    recommended_position_count = 3 if deployment_approved else (1 if all_criteria_met else 0)

    if env:
        conn.execute(
            """
            UPDATE market_environment
            SET consecutive_weeks_met = ?, deployment_approved = ?,
                recommended_position_count = ?, scaling_phase = ?
            WHERE newsletter_id = ?
            """,
            (consecutive, bool_int(deployment_approved), recommended_position_count, scaling_phase, newsletter_id),
        )

    rationale = {
        "decision": action,
        "reason": "Two-week confirmation met" if deployment_approved else (
            "Week 1 of confirmation" if all_criteria_met else "One or more market criteria failed"
        ),
        "criteria_status": {
            "all_criteria_met": all_criteria_met,
            "consecutive_weeks": {"value": consecutive, "threshold": 2, "passed": consecutive >= 2},
        },
    }
    conn.execute(
        """
        INSERT INTO weekly_decisions
        (newsletter_id, publication_date, all_criteria_met, consecutive_weeks_met,
         deployment_approved, action_taken, positions_deployed, symbols_deployed,
         decision_rationale)
        VALUES (?, ?, ?, ?, ?, ?, 0, '[]', ?)
        """,
        (
            newsletter_id,
            publication_date.isoformat(),
            bool_int(all_criteria_met),
            consecutive,
            bool_int(deployment_approved),
            action,
            json.dumps(rationale, sort_keys=True),
        ),
    )

    short_rows = conn.execute(
        "SELECT symbol, group_concat(portfolio_type) AS portfolios FROM short_list_entries WHERE newsletter_id = ? GROUP BY symbol",
        (newsletter_id,),
    ).fetchall()
    short_map = {row["symbol"]: row["portfolios"] for row in short_rows}

    entries = conn.execute(
        "SELECT * FROM watchlist_entries WHERE newsletter_id = ? ORDER BY symbol", (newsletter_id,)
    ).fetchall()
    priority = 0
    for entry in entries:
        on_short = entry["symbol"] in short_map
        if on_short:
            priority += 1
        eligible = deployment_approved and on_short
        reason = None if eligible else (
            "Market deployment not approved" if not deployment_approved else "Not on short list"
        )
        conn.execute(
            """
            INSERT INTO symbol_history
            (symbol, newsletter_id, publication_date, on_watchlist, on_short_list, metadata)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (
                entry["symbol"],
                newsletter_id,
                publication_date.isoformat(),
                bool_int(on_short),
                json.dumps({"source": "newsletter_ingestion"}, sort_keys=True),
            ),
        )


def calculate_consecutive_weeks(conn, publication_date: date, current_met: bool) -> int:
    if not current_met:
        return 0
    rows = conn.execute(
        """
        SELECT publication_date, all_criteria_met
        FROM market_environment
        WHERE publication_date < ?
        ORDER BY publication_date DESC
        """,
        (publication_date.isoformat(),),
    ).fetchall()
    count = 1
    for row in rows:
        if row["all_criteria_met"]:
            count += 1
        else:
            break
    return count


def section_text(pages: list[PageText]) -> str:
    return "\n\n".join(page.text for page in pages)


def section_page_map(sections: dict[str, list[PageText]]) -> dict[str, list[int]]:
    return {name: [page.page_number for page in pages] for name, pages in sections.items() if pages}


def build_warnings(watchlist: list[dict[str, Any]], env: dict[str, Any], sections: dict[str, list[PageText]]) -> list[str]:
    warnings: list[str] = []
    if not watchlist:
        warnings.append("No watchlist option-price rows extracted")
    if not env:
        warnings.append("Market environment row not extracted")
    for required in ["stock_market_weekly_recap", "short_lists", "strategy_reference"]:
        if not sections.get(required):
            warnings.append(f"Section missing: {required}")
    return warnings


def cleanup_repeated_headers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        compact = line.strip()
        if compact in {"Dual Edge Research", "Darren Carlat (214) 636-3133", "DualEdgeResearch@gmail.com"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def cleanup_name(value: str) -> str:
    return " ".join(value.replace("  ", " ").split()).strip()


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def dedupe_by_symbol(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        if row["symbol"] in seen:
            continue
        seen.add(row["symbol"])
        result.append(row)
    return result


def status_from_investment(investment_percent: int | None, hybrid_score: int | None) -> str:
    if investment_percent is not None:
        if investment_percent >= 75:
            return "green"
        if investment_percent >= 50:
            return "yellow"
        return "red"
    if hybrid_score is None:
        return "yellow"
    if hybrid_score >= 2:
        return "green"
    if hybrid_score >= 0:
        return "yellow"
    return "red"


def number(value: str) -> float:
    return float(value.replace(",", ""))


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_directory(
    directory: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    force: bool = False,
) -> list[dict[str, Any]]:
    results = []
    pdfs = sorted(Path(directory).glob("*.pdf"), key=publication_date_sort_key)
    for pdf in pdfs:
        try:
            results.append(ingest_newsletter(pdf, db_path, force=force))
        except Exception as exc:
            results.append(
                {
                    "pdf_path": str(pdf.resolve()),
                    "status": "error",
                    "error": str(exc),
                }
            )
    return results


def publication_date_sort_key(pdf: Path) -> tuple[date, str]:
    try:
        reader = PdfReader(str(pdf))
        first_pages = "\n".join((page.extract_text() or "") for page in reader.pages[:2])
        return parse_publication_date(normalize_pdf_text(first_pages), pdf), pdf.name
    except Exception:
        return date.max, pdf.name
