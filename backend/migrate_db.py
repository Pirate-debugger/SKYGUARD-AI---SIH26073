import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "skyguard.db")
conn = sqlite3.connect(db_path)

# Migrate readings table
existing_readings_cols = [r[1] for r in conn.execute("PRAGMA table_info(readings);").fetchall()]
new_readings_cols = [
    ("evidence_strength", "TEXT DEFAULT 'MEDIUM'"),
    ("imputed_values", "TEXT DEFAULT '{}'"),
    ("model_version", "TEXT DEFAULT 'v2.0.0'"),
    ("ruleset_version", "TEXT DEFAULT 'v2.0.0'"),
    ("feature_version", "TEXT DEFAULT 'v2.0.0'")
]

for col, col_type in new_readings_cols:
    if col not in existing_readings_cols:
        conn.execute(f"ALTER TABLE readings ADD COLUMN {col} {col_type};")
        print(f"Added column {col} to readings.")

# Migrate alerts table
existing_alerts_cols = [r[1] for r in conn.execute("PRAGMA table_info(alerts);").fetchall()]
for col, col_type in [("evidence_strength", "TEXT DEFAULT 'MEDIUM'")]:
    if col not in existing_alerts_cols:
        conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {col_type};")
        print(f"Added column {col} to alerts.")

conn.commit()
conn.close()
print("skyguard.db migration complete!")
