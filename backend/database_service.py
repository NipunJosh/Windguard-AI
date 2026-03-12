import pandas as pd
from datetime import datetime
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# We default to the Supabase connection string provided
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres.rbujvskwenrfujuufzkr:kOywvwleCUBGuDz6@aws-1-ap-south-1.pooler.supabase.com:5432/postgres")

class DatabaseService:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self._init_db()

    def _init_db(self):
        # We rely on sqlalchemy or the migration script entirely for table creation in Postgres,
        # but here is a safe initialization just in case.
        with self.engine.connect() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS history (
                    timestamp TIMESTAMP PRIMARY KEY,
                    demand FLOAT,
                    price FLOAT,
                    wind_speed FLOAT,
                    temp FLOAT
                )
            '''))
            conn.commit()

    def insert_record(self, timestamp: datetime, demand: float, price: float, wind_speed: float, temp: float):
        # Use ON CONFLICT DO UPDATE since it's Postgres
        query = text('''
            INSERT INTO history (timestamp, demand, price, wind_speed, temp) 
            VALUES (:ts, :dem, :pri, :ws, :temp)
            ON CONFLICT (timestamp) DO UPDATE SET 
                demand = EXCLUDED.demand,
                price = EXCLUDED.price,
                wind_speed = EXCLUDED.wind_speed,
                temp = EXCLUDED.temp
        ''')
        with self.engine.connect() as conn:
            conn.execute(query, {
                "ts": timestamp, 
                "dem": demand, 
                "pri": price, 
                "ws": wind_speed, 
                "temp": temp
            })
            conn.commit()

    def get_recent_records(self, hours: int = 168) -> pd.DataFrame:
        query = f"SELECT * FROM history ORDER BY timestamp DESC LIMIT {hours}"
        df = pd.read_sql_query(query, self.engine)
        # Ensure timestamp is datetime and sort ascending for lag calculation
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
        return df

    def delete_oldest_record(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE timestamp = (SELECT MIN(timestamp) FROM history)")
        conn.commit()
        conn.close()

db_service = DatabaseService()
