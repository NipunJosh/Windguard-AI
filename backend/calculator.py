import math
import os
import json
import asyncio
import urllib.request
import urllib.error
from typing import List, Dict, Any
from .schemas import Recommendation

GENAI_AVAILABLE = True # Bypassing for OpenRouter

class WindCalculator:
    def __init__(self):
        # Sample power curve for a 2.5MW turbine
        # (Wind Speed in m/s, Power in kW)
        self.power_curve = [
            (0, 0), (2, 0), (3, 20), (4, 100), (5, 250), (6, 450), (7, 750),
            (8, 1100), (9, 1500), (10, 2000), (11, 2500), (12, 2500),
            (25, 2500), (26, 0)
        ]

    def calculate_generation(self, wind_speed: float, installed_capacity_mw: float) -> float:
        """
        Uses a standard power curve interpolation to calculate power output.
        Result in MW.
        """
        if wind_speed < 2 or wind_speed > 25:
            return 0.0
            
        # Interpolate power curve
        p_prev, w_prev = 0, 0
        for w, p in self.power_curve:
            if wind_speed <= w:
                if w == w_prev: return p / 1000.0
                ratio = (wind_speed - w_prev) / (w - w_prev)
                interpolated_kw = p_prev + ratio * (p - p_prev)
                # Scale by capacity (assuming 2.5MW base turbine)
                num_turbines = installed_capacity_mw / 2.5
                return (interpolated_kw * num_turbines) / 1000.0
            p_prev, w_prev = p, w
        return 0.0

    def check_constraints(self, generation_mw: float, transformer_capacity_mw: float) -> Dict[str, Any]:
        curtailment_required = max(0, generation_mw - transformer_capacity_mw)
        evacuation_possible = min(generation_mw, transformer_capacity_mw)
        return {
            "curtailment_required": curtailment_required,
            "evacuation_possible": evacuation_possible,
            "is_constrained": curtailment_required > 0
        }

    def generate_recommendations(self, risk_level: str, loss_val: float, is_constrained: bool, 
                                 price: float, demand: float) -> List[Recommendation]:
        recs = []
        
        if is_constrained:
            recs.append(Recommendation(
                category="SAFETY",
                message="Transformer limit exceeded. Immediate curtailment required to prevent evacuation failure.",
                priority="HIGH"
            ))
            
        if risk_level == "HIGH":
            recs.append(Recommendation(
                category="OPERATIONAL",
                message=f"High risk of energy loss ({loss_val:.2f} MW). Review equipment health and grid stability.",
                priority="HIGH"
            ))
        elif risk_level == "MEDIUM":
             recs.append(Recommendation(
                category="OPERATIONAL",
                message="Moderate variability detected. Monitor turbine performance frequently.",
                priority="MEDIUM"
            ))

        if price < 2500: # Low price threshold for example
             recs.append(Recommendation(
                category="REVENUE",
                message="Low electricity price detected. Consider maintenance window if loss is occurring.",
                priority="LOW"
            ))
            
        if not recs:
            recs.append(Recommendation(
                category="OPERATIONAL",
                message="System operating within normal parameters. No immediate action required.",
                priority="LOW"
            ))
            
        return recs

    async def generate_ai_recommendations(self, risk_level: str, loss_val: float, is_constrained: bool, 
                                 price: float, demand: float, transformer_mw: float, generation_mw: float) -> List[Recommendation]:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not GENAI_AVAILABLE or not api_key:
            return self.generate_recommendations(risk_level, loss_val, is_constrained, price, demand)
            
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://windguard.com",
                "X-Title": "WindGuard AI"
            }
            
            models_to_try = [
                "google/gemma-4-26b-a4b-it",
                "meta-llama/llama-3.1-8b-instruct:free",
                "mistralai/mistral-7b-instruct:free",
                "google/gemini-2.0-flash-lite-preview-02-05:free"
            ]
            
            text = ""
            for model_name in models_to_try:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
                
                def fetch_data(req_obj):
                    with urllib.request.urlopen(req_obj) as response:
                        return json.loads(response.read().decode('utf-8'))
                        
                try:
                    response_data = await asyncio.to_thread(fetch_data, req)
                    if 'choices' in response_data:
                        text = response_data['choices'][0]['message']['content'].strip()
                        print(f"Rec API: Success with {model_name}")
                        break
                except Exception as model_err:
                    print(f"Rec API: Model {model_name} failed. Error: {model_err}")
                    continue
                    
            if not text:
                return self.generate_recommendations(risk_level, loss_val, is_constrained, price, demand)
                
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            text = text.strip()
                
            recs_data = json.loads(text)
            recs = []
            for item in recs_data:
                recs.append(Recommendation(
                    category=item.get("category", "OPERATIONAL").upper(),
                    message=item.get("message", "Review system metrics."),
                    priority=item.get("priority", "MEDIUM").upper()
                ))
            return recs
        except Exception as e:
            print(f"GenAI Recommendation Error: {e}")
            return self.generate_recommendations(risk_level, loss_val, is_constrained, price, demand)

calculator = WindCalculator()
