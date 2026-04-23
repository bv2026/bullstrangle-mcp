from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB_PATH, connect, initialize_database


REQUIRED_COLUMNS = {
    "ACCOUNT",
    "Symbol",
    "Quantity",
    "Price",
    "AVG PRICE",
    "Market Value",
    "Cost Basis",
}


def ingest_positions(
    csv_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    initialize_database(db_path)
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Positions CSV not found: {path}")

    rows = _read_positions(path)
    accounts = {row["account_name"] for row in rows}
    symbols = {row["symbol"] for row in rows}
    total_market_value = sum(row["market_value"] or 0 for row in rows)
    total_cost_basis = sum(row["cost_basis"] or 0 for row in rows)
    validation = _validate_rows(rows)
    if validation["duplicate_account_symbol_rows"]:
        raise ValueError(
            f"Duplicate account/symbol rows found in positions CSV: {validation['duplicate_account_symbol_rows']}"
        )

    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO position_import_runs
            (source_path, row_count, account_count, symbol_count,
             total_market_value, total_cost_basis, status, validation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(path.resolve()),
                len(rows),
                len(accounts),
                len(symbols),
                total_market_value,
                total_cost_basis,
                "imported",
                json.dumps(validation, sort_keys=True),
            ),
        )
        position_run_id = int(cur.lastrowid)
        _insert_account_positions(conn, position_run_id, rows)
        rollups = _build_rollups(position_run_id, rows)
        _insert_rollups(conn, rollups)
        conn.commit()

    return {
        "position_run_id": position_run_id,
        "source_path": str(path.resolve()),
        "row_count": len(rows),
        "account_count": len(accounts),
        "symbol_count": len(symbols),
        "total_market_value": round(total_market_value, 2),
        "total_cost_basis": round(total_cost_basis, 2),
        "bull_strangle_ready_symbols": [
            row["symbol"] for row in rollups if row["bull_strangle_ready"]
        ],
        "validation": validation,
        "status": "imported",
    }


def latest_position_rollups(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, dict[str, Any]]:
    return latest_position_state(db_path)[1]


def latest_position_state(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> tuple[int | None, dict[str, dict[str, Any]]]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        run = conn.execute(
            "SELECT MAX(position_run_id) AS position_run_id FROM position_import_runs"
        ).fetchone()
        if not run or run["position_run_id"] is None:
            return None, {}
        rows = conn.execute(
            """
            SELECT *
            FROM symbol_position_rollups
            WHERE position_run_id = ?
            """,
            (run["position_run_id"],),
        ).fetchall()
    return int(run["position_run_id"]), {row["symbol"]: dict(row) for row in rows}


def _read_positions(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Positions CSV has no header row: {path}")
        normalized_headers = {header: header.strip() for header in reader.fieldnames}
        stripped = set(normalized_headers.values())
        missing = REQUIRED_COLUMNS - stripped
        if missing:
            raise ValueError(f"Positions CSV missing required columns: {sorted(missing)}")

        for raw in reader:
            row = {
                normalized_headers[key]: value
                for key, value in raw.items()
                if key is not None
            }
            account = str(row.get("ACCOUNT", "")).strip()
            symbol = str(row.get("Symbol", "")).strip().upper()
            if not account or not symbol:
                continue
            quantity = _to_float(row.get("Quantity"))
            current_price = _to_float(row.get("Price"))
            average_price = _to_float(row.get("AVG PRICE"))
            market_value = _to_float(row.get("Market Value"))
            cost_basis = _to_float(row.get("Cost Basis"))
            gain_loss = (
                market_value - cost_basis
                if market_value is not None and cost_basis is not None
                else None
            )
            gain_loss_pct = (
                gain_loss / cost_basis
                if gain_loss is not None and cost_basis not in (None, 0)
                else None
            )
            rows.append(
                {
                    "account_name": account,
                    "symbol": symbol,
                    "quantity": quantity or 0,
                    "current_price": current_price,
                    "average_price": average_price,
                    "market_value": market_value,
                    "cost_basis": cost_basis,
                    "unrealized_gain_loss": gain_loss,
                    "unrealized_gain_loss_pct": gain_loss_pct,
                    "raw_row_json": json.dumps(row, sort_keys=True),
                }
            )
    return rows


def _insert_account_positions(conn, position_run_id: int, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO account_positions
        (position_run_id, account_name, symbol, quantity, current_price,
         average_price, market_value, cost_basis, unrealized_gain_loss,
         unrealized_gain_loss_pct, raw_row_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                position_run_id,
                row["account_name"],
                row["symbol"],
                row["quantity"],
                row["current_price"],
                row["average_price"],
                row["market_value"],
                row["cost_basis"],
                row["unrealized_gain_loss"],
                row["unrealized_gain_loss_pct"],
                row["raw_row_json"],
            )
            for row in rows
        ],
    )


def _build_rollups(position_run_id: int, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["symbol"]].append(row)

    rollups = []
    for symbol, symbol_rows in sorted(grouped.items()):
        total_quantity = sum(row["quantity"] or 0 for row in symbol_rows)
        total_market_value = sum(row["market_value"] or 0 for row in symbol_rows)
        total_cost_basis = sum(row["cost_basis"] or 0 for row in symbol_rows)
        max_row = max(symbol_rows, key=lambda row: row["quantity"] or 0)
        max_quantity = max_row["quantity"] or 0
        ready_rows = [row for row in symbol_rows if (row["quantity"] or 0) >= 100]
        eligible_account = (
            sorted(ready_rows, key=lambda row: (-(row["quantity"] or 0), row["account_name"]))[0][
                "account_name"
            ]
            if ready_rows
            else None
        )
        dca_target = eligible_account or max_row["account_name"]
        shares_to_100 = max(0, 100 - max_quantity)
        accounts_json = json.dumps(
            [
                {
                    "account_name": row["account_name"],
                    "quantity": row["quantity"],
                    "market_value": row["market_value"],
                    "cost_basis": row["cost_basis"],
                }
                for row in sorted(symbol_rows, key=lambda item: item["account_name"])
            ],
            sort_keys=True,
        )
        rollups.append(
            {
                "position_run_id": position_run_id,
                "symbol": symbol,
                "total_quantity": total_quantity,
                "total_market_value": total_market_value,
                "total_cost_basis": total_cost_basis,
                "weighted_average_price": (
                    total_cost_basis / total_quantity if total_quantity else None
                ),
                "account_count": len({row["account_name"] for row in symbol_rows}),
                "max_account_quantity": max_quantity,
                "bull_strangle_ready": 1 if eligible_account else 0,
                "eligible_account": eligible_account,
                "dca_target_account": dca_target,
                "shares_to_100": shares_to_100,
                "accounts_json": accounts_json,
            }
        )
    return rollups


def _insert_rollups(conn, rollups: list[dict[str, Any]]) -> None:
    columns = [
        "position_run_id",
        "symbol",
        "total_quantity",
        "total_market_value",
        "total_cost_basis",
        "weighted_average_price",
        "account_count",
        "max_account_quantity",
        "bull_strangle_ready",
        "eligible_account",
        "dca_target_account",
        "shares_to_100",
        "accounts_json",
    ]
    placeholders = ", ".join(["?"] * len(columns))
    conn.executemany(
        f"INSERT INTO symbol_position_rollups ({', '.join(columns)}) VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rollups],
    )


def _validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    duplicates = defaultdict(int)
    for row in rows:
        duplicates[(row["account_name"], row["symbol"])] += 1
    duplicate_rows = [
        {"account_name": account, "symbol": symbol, "count": count}
        for (account, symbol), count in duplicates.items()
        if count > 1
    ]
    return {
        "duplicate_account_symbol_rows": duplicate_rows,
        "negative_quantity_rows": [
            {"account_name": row["account_name"], "symbol": row["symbol"]}
            for row in rows
            if (row["quantity"] or 0) < 0
        ],
    }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "").replace('"', "")
    if not text:
        return None
    return float(text)
