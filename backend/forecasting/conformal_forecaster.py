"""
PolarSync AI - Uncertainty-Aware Conformal Forecaster
Multi-horizon forecasting for Load, Wind Speed, Solar Irradiance, and Temperature.
Produces Quantile Predictions (q10, q50, q90) and Calibrated Conformal Prediction Intervals.
Reports MAE, MAPE, and Empirical Coverage (PICP) on held-out polar test data.
"""

import os
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from backend.config import CONFIG


class PolarConformalForecaster:
    def __init__(self, data_path: str = "backend/data/polar_year_8760.csv"):
        self.data_path = data_path
        self.models: Dict[str, Dict[str, Any]] = {}
        self.conformal_offsets: Dict[str, float] = {}
        self.metrics: Dict[str, Dict[str, float]] = {}
        self.is_trained = False
        
    def _create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Creates cyclical time features and lag predictors."""
        df = df.copy()
        df["sin_hour"] = np.sin(2 * np.pi * (df["hour"] % 24) / 24.0)
        df["cos_hour"] = np.cos(2 * np.pi * (df["hour"] % 24) / 24.0)
        df["sin_day"] = np.sin(2 * np.pi * df["day"] / 365.0)
        df["cos_day"] = np.cos(2 * np.pi * df["day"] / 365.0)
        
        # Targets
        df["total_load_kw"] = df["tier1_load_kw"] + df["tier2_load_kw"] + df["tier3_load_kw"]
        
        feature_cols = [
            "sin_hour", "cos_hour", "sin_day", "cos_day",
            "solar_elevation_deg", "ambient_temp_c", "wind_speed_ms"
        ]
        return df[feature_cols], df

    def train_and_calibrate(self, target_coverage: float = 0.90):
        """
        Trains Quantile Regressors (q10, q50, q90) and applies Split Conformal Prediction.
        """
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Polar dataset not found at {self.data_path}")
            
        raw_df = pd.read_csv(self.data_path)
        X, full_df = self._create_features(raw_df)
        
        targets = ["total_load_kw", "wind_speed_ms", "ghi_w_m2", "ambient_temp_c"]
        n_samples = len(X)
        
        # Train / Calibration / Test Split (70% / 15% / 15%)
        train_idx = int(0.70 * n_samples)
        cal_idx = int(0.85 * n_samples)
        
        X_train, X_cal, X_test = X.iloc[:train_idx], X.iloc[train_idx:cal_idx], X.iloc[cal_idx:]
        
        for tgt in targets:
            y = full_df[tgt]
            y_train, y_cal, y_test = y.iloc[:train_idx], y.iloc[train_idx:cal_idx], y.iloc[cal_idx:]
            
            # Train Quantile Models (q10, q50, q90)
            m_q10 = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, max_iter=60, random_state=42)
            m_q50 = HistGradientBoostingRegressor(loss="quantile", quantile=0.50, max_iter=60, random_state=42)
            m_q90 = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, max_iter=60, random_state=42)
            
            m_q10.fit(X_train, y_train)
            m_q50.fit(X_train, y_train)
            m_q90.fit(X_train, y_train)
            
            self.models[tgt] = {"q10": m_q10, "q50": m_q50, "q90": m_q90}
            
            # Conformal Calibration
            q10_cal = m_q10.predict(X_cal)
            q90_cal = m_q90.predict(X_cal)
            
            # Non-conformity scores: s_i = max(q10 - y, y - q90)
            scores = np.maximum(q10_cal - y_cal.values, y_cal.values - q90_cal)
            
            # (1 - alpha) quantile of scores
            alpha = 1.0 - target_coverage
            q_val = np.quantile(scores, np.clip(math.ceil((len(scores) + 1) * (1 - alpha)) / len(scores), 0.0, 1.0))
            self.conformal_offsets[tgt] = float(max(0.0, q_val))
            
            # Evaluate on held-out test set
            q10_test = m_q10.predict(X_test) - self.conformal_offsets[tgt]
            q50_test = m_q50.predict(X_test)
            q90_test = m_q90.predict(X_test) + self.conformal_offsets[tgt]
            
            mae = float(mean_absolute_error(y_test, q50_test))
            # Safe MAPE calculation avoiding zero division
            denom = np.where(np.abs(y_test.values) < 1e-3, 1.0, np.abs(y_test.values))
            mape = float(np.mean(np.abs((y_test.values - q50_test) / denom)) * 100.0)
            
            # Empirical coverage: fraction of test points inside [q10, q90]
            inside = (y_test.values >= q10_test) & (y_test.values <= q90_test)
            coverage = float(np.mean(inside) * 100.0)
            
            self.metrics[tgt] = {
                "mae": round(mae, 2),
                "mape_pct": round(mape, 2),
                "coverage_pct": round(coverage, 1),
                "target_coverage_pct": int(target_coverage * 100)
            }
            
        self.is_trained = True
        print("[PolarSync Forecaster] Successfully trained models with conformal coverage metrics:")
        for t, m in self.metrics.items():
            print(f"  - {t}: MAE={m['mae']}, MAPE={m['mape_pct']}%, Coverage={m['coverage_pct']}% (Target: {m['target_coverage_pct']}%)")

    def forecast_24h(self, current_features: Dict[str, float]) -> Dict[str, Dict[str, list]]:
        """Generates 24h rolling forecast bands."""
        if not self.is_trained:
            self.train_and_calibrate()
            
        cur_hour = int(current_features.get("hour", 0))
        cur_day = int(current_features.get("day", 1))
        lat_rad = math.radians(CONFIG.latitude)
        
        horizon = 24
        future_X = []
        
        for step in range(horizon):
            h = (cur_hour + step) % 24
            d = cur_day + ((cur_hour + step) // 24)
            
            sin_h = math.sin(2 * math.pi * h / 24.0)
            cos_h = math.cos(2 * math.pi * h / 24.0)
            sin_d = math.sin(2 * math.pi * d / 365.0)
            cos_d = math.cos(2 * math.pi * d / 365.0)
            
            # Solar elevation
            dec_rad = math.radians(23.45 * math.sin(math.radians((360 / 365) * (284 + d))))
            ha_rad = math.radians(15.0 * (h - 12.0))
            sin_elev = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
            elev = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))
            
            future_X.append([
                sin_h, cos_h, sin_d, cos_d,
                elev,
                current_features.get("ambient_temp_c", -20.0),
                current_features.get("wind_speed_ms", 9.0)
            ])
            
        feature_cols = [
            "sin_hour", "cos_hour", "sin_day", "cos_day",
            "solar_elevation_deg", "ambient_temp_c", "wind_speed_ms"
        ]
        X_df = pd.DataFrame(future_X, columns=feature_cols)
        forecast_results = {}
        
        for tgt, models in self.models.items():
            q10 = models["q10"].predict(X_df) - self.conformal_offsets[tgt]
            q50 = models["q50"].predict(X_df)
            q90 = models["q90"].predict(X_df) + self.conformal_offsets[tgt]
            
            # Monotonic quantile sorting (Rearrangement post-processing)
            q50 = np.maximum(q10, q50)
            q90 = np.maximum(q50, q90)
            
            if "load" in tgt or "wind" in tgt or "ghi" in tgt:
                q10 = np.maximum(0.0, q10)
                q50 = np.maximum(0.0, q50)
                q90 = np.maximum(0.0, q90)
                
            forecast_results[tgt] = {
                "lower_q10": [round(float(v), 2) for v in q10],
                "median_q50": [round(float(v), 2) for v in q50],
                "upper_q90": [round(float(v), 2) for v in q90]
            }
            
        return forecast_results


# Singleton instance
FORECASTER = PolarConformalForecaster()


if __name__ == "__main__":
    FORECASTER.train_and_calibrate()
