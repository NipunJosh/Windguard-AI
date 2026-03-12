import joblib
import os
from typing import Dict, Any

# Paths relative to the script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.dirname(BASE_DIR)

class ModelLoader:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.model_names = [
            "demand_model.pkl",
            "price_model.pkl",
            "loss_reg_model.pkl",
            "loss_risk_model.pkl",
            "demand_scaler.pkl"
        ]

    def load_all(self):
        for name in self.model_names:
            path = os.path.join(MODELS_DIR, name)
            if os.path.exists(path):
                print(f"Loading model: {name}")
                self.models[name.replace(".pkl", "")] = joblib.load(path)
            else:
                raise FileNotFoundError(f"Model file not found: {path}")
        return self.models

    def predict(self, model_key: str, features_df):
        """
        Executes prediction for a specific model key.
        The caller must ensure features_df has the correct columns.
        """
        if model_key not in self.models:
            raise KeyError(f"Model {model_key} not loaded.")
        return self.models[model_key].predict(features_df)

# Global instances
loader = ModelLoader()
