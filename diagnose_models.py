import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from backend.models_loader import loader
from backend.pipeline import pipeline
from backend.weather_service import weather_service

async def diagnostic_run():
    print("--- STARTING MODEL DIAGNOSTICS ---")
    loader.load_all()
    
    # Sample Input
    location = "Kochi, IN"
    capacity = 50.0
    transformer = 45.0
    dt = datetime.now()
    
    # 1. Weather
    print(f"\n[1] Fetching weather for {location}...")
    weather = await weather_service.get_weather(location)
    print(f"Weather: {weather}")
    
    # 2. Demand
    print("\n[2] Testing Demand Model...")
    hist_demand = {"lag1": 25000, "lag24": 26000, "lag168": 24000}
    demand_feats = pipeline.create_demand_features(dt, hist_demand)
    demand_raw = loader.predict("demand_model", demand_feats)[0]
    print(f"Demand Raw Output: {demand_raw}")
    
    # 3. Price
    print("\n[3] Testing Price Model...")
    hist_price = {"rolling_24": 3500}
    price_feats = pipeline.create_price_features(dt, weather, float(demand_raw), hist_price)
    price_raw = loader.predict("price_model", price_feats)[0]
    print(f"Price Raw Output: {price_raw}")
    
    # 4. Energy Loss (Regression)
    print("\n[4] Testing Loss Regression Model...")
    # Assume 10MW generation for test
    gen_mw = 10.0 
    hist_stats = {"max_demand": 60000, "wind_volatility": 0.45, "demand_roll": float(demand_raw) * 0.95}
    loss_feats = pipeline.create_loss_features(dt, weather, float(demand_raw), gen_mw, hist_stats)
    log_loss_raw = loader.predict("loss_reg_model", loss_feats)[0]
    loss_mw = np.exp(log_loss_raw)
    print(f"Loss Regression Raw (log): {log_loss_raw}")
    print(f"Loss MW (exp): {loss_mw}")
    
    # 5. Loss Risk (Classification)
    print("\n[5] Testing Loss Risk Model...")
    risk_raw = loader.predict("loss_risk_model", loss_feats)[0]
    print(f"Risk Classification Raw: {risk_raw}")
    
    print("\n--- DIAGNOSTICS COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(diagnostic_run())
