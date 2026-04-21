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
    category: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[str] = None

class DashboardData(BaseModel):
    status: Optional[str] = "success"
    timestamp: str
    weather: Optional[dict] = None
    kpis: Optional[List[KPIOut]] = None
    recommendations: Optional[List[Recommendation]] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    generation_forecast_mw: Optional[float] = None
    demand_forecast_mw: Optional[float] = None
    revenue_loss_estimate: Optional[float] = None


class ForecastOut(BaseModel):
    timestamp: str
    loss_mw: float
    generation_mw: float

class ChatContext(BaseModel):
    wind_speed: Optional[float] = None
    temperature: Optional[float] = None
    generation_mw: Optional[float] = None
    demand_mw: Optional[float] = None
    price_inr: Optional[float] = None
    risk_level: Optional[str] = None
    loss_mw: Optional[float] = None

class ChatHistoryItem(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ForecastContext(BaseModel):
    timestamp: str
    loss_mw: Optional[float] = 0
    generation_mw: Optional[float] = 0

class ChatMessage(BaseModel):
    message: str
    context: Optional[ChatContext] = None
    forecast_context: Optional[List[ForecastContext]] = None
    plant_location: Optional[str] = "Coimbatore, IN"
    installed_capacity_mw: Optional[float] = 50
    transformer_capacity_mw: Optional[float] = 45
    history: Optional[List[ChatHistoryItem]] = []

