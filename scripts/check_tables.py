from bullstrangle_mcp.database import connect
conn = connect("data/bullstrangle.db")
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for r in rows:
    print(r[0])
