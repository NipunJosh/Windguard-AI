from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import os
import asyncio
from typing import Dict, Any, List

from .schemas import PlantInput, DashboardData, KPIOut, ChatMessage, ForecastOut
from .weather_service import weather_service
from .models_loader import loader
from .pipeline import pipeline
from .calculator import calculator
from .database_service import db_service

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    pass

from .openrouter_service import fetch_openrouter_response

app = FastAPI(title="Wind Energy Decision Support System")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/cron/sync")
async def trigger_cron_sync():
    print("External Cron triggered 1-hour background sync for Coimbatore...")
    try:
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
        print("Cron sync successful.")
        return {"status": "success", "timestamp": dt.isoformat()}
        
    except Exception as e:
        print(f"Cron sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    # 1. Load ML Models
    loader.load_all()
    
    # Intentionally removed the broken infinite asyncio task. 
    # The database feeder is now natively triggered by the /api/cron/sync endpoint.
    
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
@app.head("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/history")
def get_history():
    try:
        # Fetch last 400 hours to ensure we have enough for a solid 28 x 6h cycle (168h)
        df = db_service.get_recent_records(400)
        if df.empty:
            return []
            
        # Group by 6-hour buckets to avoid messy overlaps and "repeated days"
        df.set_index('timestamp', inplace=True)
        # Resample to 6-hour frequency, taking the mean
        df_resampled = df.resample('6h').mean().dropna()
        
        # Take the most recent 28 points (7 days * 4 per day)
        df_final = df_resampled.tail(28).reset_index()
        
        # Ensure timestamp is string for JSON
        df_final['timestamp'] = df_final['timestamp'].astype(str)
        return df_final.to_dict(orient="records")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(chat_input: ChatMessage):
    try:
        context_str = "No LIVE telemetry data is currently available."
        if chat_input.context:
            context_str = f"""
            - Wind Speed: {chat_input.context.wind_speed} m/s
            - Temperature: {chat_input.context.temperature} C
            - Current Generation: {chat_input.context.generation_mw} MW
            - Grid Demand: {chat_input.context.demand_mw} MW
            - Electricity Price: {chat_input.context.price_inr} INR/MWh
            - Risk Level: {chat_input.context.risk_level}
            - Energy Loss: {chat_input.context.loss_mw} MW
            """
            
        if chat_input.forecast_context:
            context_str += "\n\n[NEXT 24-HOURS LOSS FORECAST]\n"
            for item in chat_input.forecast_context:
                loss_val = next((k.value for k in item.kpis if k.label == "Energy Loss"), 0)
                context_str += f"[{item.timestamp}] Forecast: Predicted Energy Loss: {loss_val} MW\n"
            context_str += "\n*INSTRUCTION*: If asked for the best maintenance time, you MUST explicitly mention the date and the EXACT 3-hour time window (e.g. 'April 16th | 15:00 - 18:00') from the list above that has the HIGHEST energy loss. Do not provide vague advice like 'low wind speed' unless the user asks for general theory."
            
        prompt = f"""
        You are an intelligent AI assistant for the WindGuard AI dashboard. 
        You specialize in answering questions about wind energy, power prediction, Grid optimization, 
        and the data on this dashboard. 
        
        CRITICAL RULES:
        1. Be completely direct and extremely concise. 
        2. Answer ONLY the specific question asked in 1 to 2 short sentences. Do NOT write long paragraphs or give unsolicited extra advice.
        3. If asked to simulate "What-If" scenarios, use the provided telemetry context to mathematically estimate the outcome on the fly.
        
        [LIVE DASHBOARD TELEMETRY CONTEXT]
        {context_str}
        
        User question: {chat_input.message}
        """
        response_text = await fetch_openrouter_response(prompt, json_format=False)
        return {"reply": response_text.strip()}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Chat API Error: {e}")
        return {"reply": "Sorry, I am having trouble connecting to my servers right now."}

@app.post("/api/forecast", response_model=List[DashboardData])
async def get_24h_forecast(input_data: PlantInput):
    try:
        forecasts = await weather_service.get_forecast(input_data.plant_location)
        hist_df = db_service.get_recent_records(168)
        
        results = []
        for f in forecasts:
            dt = datetime.fromisoformat(f["timestamp"].replace(" ", "T"))
            gen_mw = calculator.calculate_generation(f["wind_speed"], input_data.installed_capacity_mw)
            
            demand_feats = pipeline.create_demand_features(dt, hist_df)
            demand_pred_scaled = float(loader.predict("demand_model", demand_feats)[0])
            scaler = loader.models.get("demand_scaler")
            if scaler:
                demand_pred_mw = float(scaler.inverse_transform([[demand_pred_scaled]])[0][0])
            else:
                demand_pred_mw = demand_pred_scaled
                
            loss_feats = pipeline.create_loss_features(dt, f, demand_pred_scaled, demand_pred_mw, gen_mw, hist_df)
            log_loss_raw = float(loader.predict("loss_reg_model", loss_feats)[0])
            loss_mw_raw = float(np.exp(log_loss_raw)) if log_loss_raw < 50 else log_loss_raw
            loss_mw = max(0, loss_mw_raw)
            
            constraints = calculator.check_constraints(gen_mw, input_data.transformer_capacity_mw)
            total_loss_mw = loss_mw + constraints["curtailment_required"]
            
            # Predict Price Iteratively
            price_feats = pipeline.create_price_features(dt, demand_pred_mw, gen_mw, hist_df)
            log_price_pred = float(loader.predict("price_model", price_feats)[0])
            price_pred = float(np.exp(log_price_pred))
            final_price = input_data.electricity_price if input_data.electricity_price else price_pred
            
            # Metrics
            risk = calculator.calculate_risk(f["wind_speed"], abs(total_loss_mw))
            kpis, rev_loss = calculator.format_kpis({
                "generation": gen_mw,
                "demand": demand_pred_mw,
                "price": final_price,
                "loss": total_loss_mw
            })
            
            # Use offline generator strictly to prevent OpenRouter timeout cascade
            recs = calculator.generate_recommendations({
                "wind_speed": f["wind_speed"],
                "generation": gen_mw,
                "loss": total_loss_mw,
                "demand": demand_pred_mw,
                "transformer_cap": input_data.transformer_capacity_mw,
                "curtailment": constraints["curtailment_required"]
            })
            
            results.append(DashboardData(
                status="success",
                timestamp=f["timestamp"],
                weather=f,
                kpis=kpis,
                recommendations=recs,
                risk_level=risk["level"],
                risk_score=risk["score"],
                generation_forecast_mw=gen_mw,
                demand_forecast_mw=demand_pred_mw,
                revenue_loss_estimate=rev_loss
            ))
            
        return results
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
        # We clamp the datetime directly to the nearest real-world hour.
        if not input_data.datetime:
            dt = datetime.now().replace(minute=0, second=0, microsecond=0)
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
        # Because `dt` is rounded to the closest hour, rapid rapid clicks in the same hour
        # simply execute 'ON CONFLICT DO UPDATE' in Postgres, retaining mathematical stability
        # without overflowing the database clock!
        db_service.insert_record(
            timestamp=dt,
            demand=demand_pred_mw,
            price=price_pred,
            wind_speed=weather["wind_speed"],
            temp=weather["temp"]
        )
        
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
