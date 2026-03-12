import pandas as pd
from backend.database_service import db_service
from datetime import datetime
import os

EXCEL_PATH = r"D:\JK N\final_P\hourlyLoadDataIndia.xlsx"

def bootstrap():
    print("Starting Bootstrap...")
    if not os.path.exists(EXCEL_PATH):
        print(f"Error: {EXCEL_PATH} not found.")
        return

    # Read the last 200 rows to ensure we have at least 168 after drops
    df = pd.read_excel(EXCEL_PATH)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    # Take the last 168 hours
    recent_data = df.tail(168)
    
    print(f"Inserting {len(recent_data)} records into SQLite...")
    
    for _, row in recent_data.iterrows():
        # Using default values for missing signals (as they are not in the XLSX)
        # Price: 3500 (average), Wind: 4.0 m/s, Temp: 25.0 C
        db_service.insert_record(
            timestamp=row['datetime'],
            demand=row['National Hourly Demand'],
            price=3500.0, 
            wind_speed=4.0,
            temp=25.0
        )
    
    print("Bootstrap complete. Local database history.db initialized.")

if __name__ == "__main__":
    bootstrap()
