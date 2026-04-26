from bullstrangle_mcp.database import connect
conn = connect("data/bullstrangle.db")
for table in ["exit_decisions", "cycle_layers", "position_books"]:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    print(f"\n{table}:")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")

# Also check what active cycle_layers look like
print("\n--- Active cycle_layers ---")
rows = conn.execute("""
    SELECT cl.*, n.publication_date, n.target_expiration
    FROM cycle_layers cl
    JOIN newsletters n ON n.newsletter_id = cl.newsletter_id
    WHERE cl.status = 'ACTIVE'
    ORDER BY cl.newsletter_id
""").fetchall()
for r in rows:
    print(dict(r))

# Check rule catalog for EXPIRY rules
print("\n--- EXPIRY rules in catalog ---")
rows = conn.execute("""
    SELECT rule_id, rule_area, rule_type, description, parameters_json
    FROM strategy_rule_catalog
    WHERE rule_area = 'exit'
    ORDER BY rule_id
""").fetchall()
for r in rows:
    print(dict(r))
