from pathlib import Path

from bullstrangle_mcp.database import connect
from bullstrangle_mcp.positions import ingest_positions, latest_position_rollups


def test_ingest_positions_builds_account_rollups(tmp_path):
    csv_path = tmp_path / "positions.csv"
    csv_path.write_text(
        "\n".join(
            [
                "ACCOUNT,Symbol,Quantity, Price , AVG PRICE , Market Value , Cost Basis ",
                'A1,XYZ,60, $10.00 , $9.00 ," $600.00 "," $540.00 "',
                'A2,XYZ,50, $10.00 , $8.00 ," $500.00 "," $400.00 "',
                'A1,ABC,100, $20.00 , $18.00 ," $2,000.00 "," $1,800.00 "',
            ]
        ),
        encoding="utf-8",
    )
    db = tmp_path / "bullstrangle.db"

    result = ingest_positions(csv_path, db)
    rollups = latest_position_rollups(db)

    assert result["row_count"] == 3
    assert result["account_count"] == 2
    assert result["symbol_count"] == 2
    assert result["bull_strangle_ready_symbols"] == ["ABC"]
    assert rollups["ABC"]["bull_strangle_ready"] == 1
    assert rollups["ABC"]["eligible_account"] == "A1"
    assert rollups["ABC"]["shares_to_100"] == 0
    assert rollups["XYZ"]["total_quantity"] == 110
    assert rollups["XYZ"]["max_account_quantity"] == 60
    assert rollups["XYZ"]["bull_strangle_ready"] == 0
    assert rollups["XYZ"]["shares_to_100"] == 40

    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM account_positions").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM symbol_position_rollups").fetchone()[0] == 2
