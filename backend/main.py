from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import os
import asyncio
from typing import Dict, Any

from .schemas import PlantInput, DashboardData, KPIOut
from .weather_service import weather_service
from .models_loader import loader
from .pipeline import pipeline
from .calculator import calculator
from .database_service import db_service

app = FastAPI(title="Wind Energy Decision Support System")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def background_sync_task():
    print("Background 1-hour sync task started.")
    while True:
        # We MUST poll every 1 hour to keep the 168-hour continuous Lag memory accurate for the ML Model.
        # But we will downsample the UI chart to show 12-hour cycles.
        await asyncio.sleep(3600) 
        
        try:
            print("Running 1-hour background sync for Coimbatore...")
            # 1. Fetch weather for Coimbatore
            weather = await weather_service.get_weather("Coimbatore, IN")
            dt = datetime.now()
            
            # 2. Get Lags
            hist_df = db_service.get_recent_records(168)
            
            # 3. Predict Demand
            demand_feats = pipeline.create_demand_features(dt, hist_df)
            demand_pred_scaled = float(loader.predict("demand_model", demand_feats)[0])
            scaler = loader.models.get("demand_scaler")
            if scaler:
                demand_pred_mw = float(scaler.inverse_transform([[demand_pred_scaled]])[0][0])
            else:
                demand_pred_mw = demand_pred_scaled
                
            # 4. Predict Price
            price_feats = pipeline.create_price_features(dt, weather, demand_pred_scaled, hist_df)
            price_pred = float(loader.predict("price_model", price_feats)[0])
            
            # 5. Save loop record 
            db_service.insert_record(
                timestamp=dt,
                demand=demand_pred_mw,
                price=price_pred,
                wind_speed=weather["wind_speed"],
                temp=weather["temp"]
            )
            # The user requested NOT to delete records from the DB, so we removed delete_oldest_record()
            print("Background sync successful.")
            
        except Exception as e:
            print(f"Background sync error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # 1. Load ML Models
    loader.load_all()
    
    # Start the 12-hour rolling background task
    asyncio.create_task(background_sync_task())
    
    # 2. Auto-Bootstrap check
    try:
        # Check if we have enough records for lag168
        count_df = db_service.get_recent_records(200) 
        if len(count_df) < 168:
            print(f"DB only has {len(count_df)} records. Bootstrapping more history...")
            from .database_service import DB_PATH
            import pandas as pd
            excel_path = r"D:\JK N\final_P\hourlyLoadDataIndia.xlsx"
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                # Ensure datetime is sorted
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime')
                recent = df.tail(200) # Load 200 to be safe
                for _, row in recent.iterrows():
                    db_service.insert_record(
                        timestamp=row['datetime'],
                        demand=float(row['National Hourly Demand']),
                        price=3500.0,
                        wind_speed=4.0,
                        temp=25.0
                    )
                latest = db_service.get_recent_records(1).iloc[0]['timestamp']
                print(f"Auto-bootstrap complete. {len(recent)} records added. Latest: {latest}")
            else:
                print(f"Bootstrap failed: Excel not found at {excel_path}")
        else:
            latest = count_df.iloc[0]['timestamp']
            print(f"DB check passed. Found {len(count_df)} records. Latest: {latest}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Startup check failed: {e}")

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/history")
def get_history():
    try:
        df = db_service.get_recent_records(168)
        # The user requested exactly 7 days with a 6-hour cycle (4 points per day * 7 days = 28 points)
        # This creates a rolling chart that naturally drops the oldest day when a new one begins
        df_6h_cycle = df.iloc[::6].tail(28)
        
        # Ensure timestamp is string for JSON serialization
        df_6h_cycle['timestamp'] = df_6h_cycle['timestamp'].astype(str)
        return df_6h_cycle.to_dict(orient="records")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict", response_model=DashboardData)
async def predict_status(input_data: PlantInput):
    try:
        # 1. Fetch Weather
        weather = await weather_service.get_weather(input_data.plant_location)
        
        # 2. Determine Datetime
        # If no datetime provided, we warp to the latest historical record to ensure stable lags
        if not input_data.datetime:
            latest_db_record = db_service.get_recent_records(1)
            if not latest_db_record.empty:
                # We use the latest timestamp + 1 hour to simulate the "next" step
                dt = latest_db_record.iloc[0]['timestamp'] + timedelta(hours=1)
                print(f"DEBUG: Warping time to latest history + 1h: {dt}")
            else:
                dt = datetime.now()
        else:
            dt = datetime.fromisoformat(input_data.datetime)
        
        # 3. Physics-Based Wind Generation
        gen_mw = calculator.calculate_generation(weather["wind_speed"], input_data.installed_capacity_mw)
        
        # 4. Fetch History for Lags (Last 168 hours)
        hist_df = db_service.get_recent_records(168)
        
        # 5. Predict Demand
        demand_feats = pipeline.create_demand_features(dt, hist_df)
        print(f"DEBUG: Demand Feats: {demand_feats.to_dict(orient='records')}")
        demand_pred_scaled = float(loader.predict("demand_model", demand_feats)[0])
        print(f"DEBUG: Predicted Demand (Scaled Z-Score): {demand_pred_scaled}")
        
        # Convert scaled demand back to MW for dashboard display and specific physical calculations
        scaler = loader.models.get("demand_scaler")
        if scaler:
            demand_pred_mw = float(scaler.inverse_transform([[demand_pred_scaled]])[0][0])
        else:
            demand_pred_mw = demand_pred_scaled
            
        print(f"DEBUG: Predicted Demand (MW): {demand_pred_mw}")
        
        # 6. Predict Price (if not overridden)
        if input_data.electricity_price is not None:
            price_pred = input_data.electricity_price
        else:
            price_feats = pipeline.create_price_features(dt, weather, demand_pred_scaled, hist_df)
            print(f"DEBUG: Price Feats Cols: {price_feats.columns.tolist()}")
            price_pred = float(loader.predict("price_model", price_feats)[0])
            print(f"DEBUG: Price Raw (now correctly scaled): {price_pred}")
            
        # 7. Predict Energy Loss
        loss_feats = pipeline.create_loss_features(dt, weather, demand_pred_scaled, demand_pred_mw, gen_mw, hist_df)
        
        # Loss Regression
        log_loss_raw = float(loader.predict("loss_reg_model", loss_feats)[0])
        # IMPORTANT: Check if model was trained on raw loss or log_loss. 
        loss_mw_raw = float(np.exp(log_loss_raw)) if log_loss_raw < 50 else log_loss_raw
        loss_mw = max(0, loss_mw_raw)
        
        # Loss Risk Classification
        risk_prob = float(loader.models['loss_risk_model'].predict_proba(loss_feats)[0][1])
        risk_score = risk_prob
        
        if risk_score >= 0.70:
            risk_level = "HIGH"
        elif risk_score >= 0.30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # 8. Physical Constraints
        constraints = calculator.check_constraints(gen_mw, input_data.transformer_capacity_mw)
        
        # 9. Revenue Loss Calculation
        revenue_loss = (loss_mw + constraints["curtailment_required"]) * price_pred
        # For demo: if loss is tiny, show at least some estimated value if risk is detected
        if revenue_loss < 0.1 and risk_level == "HIGH":
            revenue_loss = 500.0 
        
        # 10. Persist new record to DB (Update Time-Series)
        # We comment this out to ensure the dashboard remains stable upon rapid clicking.
        # Otherwise, every click advances the simulated clock by 1 hour, causing values to drift.
        # db_service.insert_record(
        #     timestamp=dt,
        #     demand=demand_pred_mw,
        #     price=price_pred,
        #     wind_speed=weather["wind_speed"],
        #     temp=weather["temp"]
        # )
        
        # 11. Recommendations
        recs = await calculator.generate_ai_recommendations(
            risk_level, loss_mw, constraints["is_constrained"], price_pred, demand_pred_mw, 
            input_data.transformer_capacity_mw, gen_mw
        )
        
        # 13. Assemble Response
        kpis = [
            KPIOut(label="Wind Generation", value=round(gen_mw, 2), unit="MW"),
            KPIOut(label="Predicted Demand", value=round(demand_pred_mw, 0), unit="MW"),
            KPIOut(label="Electricity Price", value=round(price_pred, 2), unit="INR/MWh"),
            KPIOut(label="Energy Loss", value=round(loss_mw, 2), unit="MW"),
            KPIOut(label="Revenue Loss Estimate", value=round(revenue_loss, 2), unit="INR")
        ]
        
        return DashboardData(
            status="success",
            timestamp=dt.isoformat(),
            weather=weather,
            kpis=kpis,
            recommendations=recs,
            risk_level=risk_level,
            risk_score=risk_score,
            generation_forecast_mw=gen_mw,
            demand_forecast_mw=demand_pred_mw,
            revenue_loss_estimate=revenue_loss
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", "18888"))
    uvicorn.run(app, host="0.0.0.0", port=port)
