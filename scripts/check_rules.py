from bullstrangle_mcp.database import connect
conn = connect("data/bullstrangle.db")
rows = conn.execute("""
    SELECT rule_id, rule_area, rule_type, description, parameters_json
    FROM strategy_rule_catalog
    ORDER BY rule_area, rule_id
""").fetchall()
for r in rows:
    print(f"{r['rule_id']:20s} {r['rule_area']:20s} {r['rule_type']:20s}  {r['description'][:60]}")
