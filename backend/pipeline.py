import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any

class FeaturePipeline:
    def __init__(self):
        pass

    def _get_lag_value(self, df: pd.DataFrame, target_col: str, lag_hours: int) -> float:
        """
        Dynamically calculates lag by looking back in the time-series dataframe.
        Assumes df is sorted by timestamp.
        """
        if df.empty:
            return 0.0
        
        # Get the latest timestamp in the df
        latest_time = df['timestamp'].max()
        target_time = latest_time - timedelta(hours=lag_hours)
        
        # Find the record closest to target_time
        # We look for the record at exactly target_time or the closest one before it
        mask = df['timestamp'] <= target_time
        if not mask.any():
            return df[target_col].iloc[0] # Fallback to first available if lag is too far back
        
        return df[mask].iloc[-1][target_col]

    def create_demand_features(self, dt: datetime, hist_df: pd.DataFrame) -> pd.DataFrame:
        """
        Features: hour, dayofweek, month, lag1, lag24, lag168
        """
        from backend.models_loader import loader
        scaler = loader.models.get('demand_scaler')

        lag1_raw = self._get_lag_value(hist_df, "demand", 1)
        lag24_raw = self._get_lag_value(hist_df, "demand", 24)
        lag168_raw = self._get_lag_value(hist_df, "demand", 168)
        
        if scaler:
            raw_lags = pd.DataFrame({'National Hourly Demand': [lag1_raw, lag24_raw, lag168_raw]})
            scaled_lags = scaler.transform(raw_lags).flatten()
            lag1, lag24, lag168 = scaled_lags[0], scaled_lags[1], scaled_lags[2]
        else:
            lag1, lag24, lag168 = lag1_raw, lag24_raw, lag168_raw

        features = {
            "hour": dt.hour,
            "dayofweek": dt.weekday(),
            "month": dt.month,
            "lag1": lag1,
            "lag24": lag24,
            "lag168": lag168
        }
        return pd.DataFrame([features])

    def create_price_features(self, dt: datetime, weather: Dict[str, Any], demand_pred_scaled: float, hist_df: pd.DataFrame) -> pd.DataFrame:
        """
        Features: WS_10m, Temp_2m, hour, month, is_weekend, summer_peak, price_rolling_24, demand_pred
        """
        is_weekend = 1 if dt.weekday() >= 5 else 0
        summer_peak = 1 if dt.month in [4, 5, 6] and 10 <= dt.hour <= 16 else 0
        
        # Calculate 24h rolling price average from hist_df
        rolling_24 = hist_df['price'].tail(24).mean() if not hist_df.empty else 3500.0
        
        features = {
            "WS_10m": weather["wind_speed"],
            "Temp_2m": weather["temp"],
            "hour": dt.hour,
            "month": dt.month,
            "is_weekend": is_weekend,
            "summer_peak": summer_peak,
            "price_rolling_24": rolling_24,
            "demand_pred_scaled": demand_pred_scaled
        }
        cols = ['WS_10m', 'Temp_2m', 'hour', 'month', 'is_weekend', 'summer_peak', 'price_rolling_24', 'demand_pred_scaled']
        return pd.DataFrame([features])[cols]

    def create_loss_features(self, dt: datetime, weather: Dict[str, Any], demand_pred_scaled: float, demand_pred_mw: float, 
                             wind_gen_forecast: float, hist_df: pd.DataFrame) -> pd.DataFrame:
        """
        Features: forecast wind onshore day ahead, WS_10m, Temp_2m, hour, month, 
                  demand_pred, wind_volatility, demand_roll, stress, evening_peak
        """
        evening_peak = 1 if 18 <= dt.hour <= 22 else 0
        stress = wind_gen_forecast / (demand_pred_mw + 1)
        
        from backend.models_loader import loader
        scaler = loader.models.get('demand_scaler')
        if not hist_df.empty and scaler:
            raw_roll = hist_df['demand'].tail(24).to_frame(name='National Hourly Demand')
            scaled_roll = scaler.transform(raw_roll).flatten()
            demand_roll = scaled_roll.mean()
        elif not hist_df.empty:
            demand_roll = hist_df['demand'].tail(24).mean()
        else:
            demand_roll = demand_pred_scaled

        wind_vol = hist_df['wind_speed'].tail(24).std() if not hist_df.empty else 0.5
        if pd.isna(wind_vol): wind_vol = 0.5

        features = {
            "forecast wind onshore day ahead": wind_gen_forecast,
            "WS_10m": weather["wind_speed"],
            "Temp_2m": weather["temp"],
            "hour": dt.hour,
            "month": dt.month,
            "demand_pred_scaled": demand_pred_scaled,
            "wind_volatility": wind_vol,
            "demand_roll_scaled": demand_roll,
            "stress": stress,
            "evening_peak": evening_peak
        }
        cols = ['forecast wind onshore day ahead', 'WS_10m', 'Temp_2m', 'hour', 'month', 'demand_pred_scaled', 'wind_volatility', 'demand_roll_scaled', 'stress', 'evening_peak']
        return pd.DataFrame([features])[cols]

    def create_risk_features(self, dt: datetime, weather: Dict[str, Any], demand_pred_scaled: float, demand_pred_mw: float, 
                             wind_gen_forecast: float, hist_df: pd.DataFrame) -> pd.DataFrame:
        # Same as loss for these models
        return self.create_loss_features(dt, weather, demand_pred_scaled, demand_pred_mw, wind_gen_forecast, hist_df)

pipeline = FeaturePipeline()
