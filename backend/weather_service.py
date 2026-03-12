import httpx
from typing import Dict, Any

class WeatherService:
    def __init__(self):
        self.api_key = "f17694cd8c76e873c8985ac80f36c8c6"
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    async def get_weather(self, location: str) -> Dict[str, Any]:
        """
        Fetches current weather for the given location.
        Location format: "City, CountryCode" (e.g., "Kochi, IN")
        """
        params = {
            "q": location,
            "appid": self.api_key,
            "units": "metric"  # Get temperature in Celsius
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Map essential fields for our ML features
            # Based on notebook: WS_10m (Wind Speed), Temp_2m (Temperature)
            # Weather API provides speed at 10m usually.
            result = {
                "wind_speed": data["wind"]["speed"],
                "temp": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "raw": data
            }
            return result

weather_service = WeatherService()
