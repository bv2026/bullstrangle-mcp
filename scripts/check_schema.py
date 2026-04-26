from bullstrangle_mcp.database import connect
conn = connect("data/bullstrangle.db")
for table in ["os_weekly_symbol_aggregates", "os_evaluation_rows", "entry_decisions"]:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    print(f"\n{table}:")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")
