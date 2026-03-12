from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PlantInput(BaseModel):
    plant_location: str = Field(..., example="Kochi, IN")
    datetime: Optional[str] = Field(None, description="ISO format date string. If empty, current time is used.")
    installed_capacity_mw: float = Field(..., gt=0)
    transformer_capacity_mw: float = Field(..., gt=0)
    electricity_price: Optional[float] = Field(None, description="Operator override for price (INR)")

class KPIOut(BaseModel):
    label: str
    value: float
    unit: str
    target: Optional[float] = None

class Recommendation(BaseModel):
    category: str  # "OPERATIONAL", "SAFETY", "REVENUE"
    message: str
    priority: str # "HIGH", "MEDIUM", "LOW"

class DashboardData(BaseModel):
    status: str
    timestamp: str
    weather: dict
    kpis: List[KPIOut]
    recommendations: List[Recommendation]
    risk_level: str # "LOW", "MEDIUM", "HIGH"
    risk_score: float
    generation_forecast_mw: float
    demand_forecast_mw: float
    revenue_loss_estimate: float
