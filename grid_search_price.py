import joblib
import pandas as pd
import numpy as np
import os
from datetime import datetime
from backend.models_loader import loader
from backend.pipeline import pipeline

def grid_search_price():
    loader.load_all()
    dt = datetime(2024, 5, 1, 12, 0, 0) # Noon
    
    results = []
    
    # Grid parameters
    demands = [0, 10000, 50000, 100000, 200000, 500000]
    roll_prices = [0, 1, 100, 3500, 10000]
    temps = [10, 25, 40]
    winds = [0, 5, 15]
    
    print("\n--- Price Model Grid Search ---")
    print(f"{'Demand':<10} | {'RollPrice':<10} | {'Temp':<5} | {'Wind':<5} -> {'Prediction':<10}")
    print("-" * 60)
    
    count = 0
    for d in demands:
        for rp in roll_prices:
            for t in temps:
                for w in winds:
                    weather = {"wind_speed": w, "temp": t}
                    feat = pipeline.create_price_features(dt, weather, d, pd.DataFrame([{'price':rp}]))
                    pred = float(loader.predict("price_model", feat)[0])
                    if pred > 0:
                        print(f"{d:<10.0f} | {rp:<10.1f} | {t:<5.0f} | {w:<5.0f} -> {pred:<10.2f} (POSITIVE!)")
                    
                    count += 1
                    if count % 100 == 0:
                        print(f"... checked {count} combos ...")

    # Double check if EVERYTHING is negative
    all_preds = []
    for d in [50000, 200000]:
        for rp in [3500]:
            weather = {"wind_speed": 5, "temp": 25}
            feat = pipeline.create_price_features(dt, weather, d, pd.DataFrame([{'price':rp}]))
            all_preds.append(float(loader.predict("price_model", feat)[0]))
    
    if max(all_preds) < 0:
        print("\nWARNING: All scanned combinations returned negative values.")
        print(f"Max prediction found: {max(all_preds):.2f}")

if __name__ == "__main__":
    grid_search_price()
