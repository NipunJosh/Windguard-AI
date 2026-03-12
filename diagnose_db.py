import sqlite3
import os
import pandas as pd

DB_PATH = r"D:\JK N\final_P\backend\history.db"

print(f"Checking DB at: {DB_PATH}")
print(f"File exists: {os.path.exists(DB_PATH)}")

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY timestamp DESC LIMIT 5", conn)
    print("\n--- Latest 5 Rows ---")
    print(df)
    
    total = pd.read_sql_query("SELECT COUNT(*) as count FROM history", conn)
    print(f"\nTotal Records: {total.iloc[0]['count']}")
    
    # Check for 0 value records that might be poisoning the mean
    zeros = pd.read_sql_query("SELECT COUNT(*) as count FROM history WHERE demand = 0", conn)
    print(f"Zero Demand Records: {zeros.iloc[0]['count']}")
    
    conn.close()
else:
    print("DB FILE MISSING!")
