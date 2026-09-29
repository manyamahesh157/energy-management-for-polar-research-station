"""
PolarSync AI - Predictive Maintenance Engine (Feature I)
Anomaly detection using Isolation Forest on multi-modal polar sensor proxies:
1. Turbine vibration / acceleration proxy (bearing fatigue & ice mass imbalance)
2. PEM Electrolyzer stack cell voltage (membrane degradation & catalyst fouling)
3. Battery internal resistance (electrolyte degradation & SEI growth)
Outputs real-time anomaly scores and Remaining Useful Life (RUL) projections in operating hours.
"""

import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import IsolationForest


class PolarPredictiveMaintenance:
    def __init__(self):
        # Fit baseline model on nominal healthy operating parameters
        np.random.seed(42)
        n_samples = 600
        
        # Nominal distributions
        vib_nom = np.random.normal(0.45, 0.08, n_samples)          # 0.45 g vibration
        volt_nom = np.random.normal(1.85, 0.05, n_samples)         # 1.85 V per cell
        r_int_nom = np.random.normal(18.0, 1.2, n_samples)         # 18.0 mOhm
        
        X_nominal = np.column_stack([vib_nom, volt_nom, r_int_nom])
        self.model = IsolationForest(contamination=0.03, random_state=42)
        self.model.fit(X_nominal)
        
        # Asset lifecycle baselines (rated hours)
        self.turbine_max_hours = 35000.0
        self.electrolyzer_max_hours = 40000.0
        self.battery_max_hours = 45000.0
        
        self.turbine_run_hours = 8200.0
        self.electrolyzer_run_hours = 4100.0
        self.battery_run_hours = 12400.0

    def assess_health(
        self,
        turbine_vibration_g: float,
        electrolyzer_cell_v: float,
        battery_r_int_mohm: float,
        dt_hours: float = 1.0
    ) -> Dict[str, Any]:
        """
        Ingests real-time sensor metrics, computes anomaly scores, and updates RUL.
        """
        # Increment operating hours
        self.turbine_run_hours += dt_hours
        self.electrolyzer_run_hours += (dt_hours * 0.4)  # Operating ~40% of time
        self.battery_run_hours += dt_hours
        
        vec = np.array([[turbine_vibration_g, electrolyzer_cell_v, battery_r_int_mohm]])
        
        # Decision function: lower values mean more anomalous
        raw_score = float(self.model.decision_function(vec)[0])
        is_anomaly = bool(self.model.predict(vec)[0] == -1)
        
        # Normalized anomaly severity index (0.0 = Healthy, 1.0 = Critical Anomaly)
        anomaly_index = float(max(0.0, min(1.0, 0.5 - raw_score * 2.5)))
        
        # RUL estimation with degradation accelerations
        # Vibration acceleration factor
        vib_deg = max(1.0, (turbine_vibration_g / 0.45) ** 2.2)
        turbine_rul_hours = max(100.0, (self.turbine_max_hours - self.turbine_run_hours) / vib_deg)
        
        # Voltage drift acceleration factor
        volt_deg = max(1.0, ((electrolyzer_cell_v - 1.4) / 0.45) ** 1.8)
        el_rul_hours = max(100.0, (self.electrolyzer_max_hours - self.electrolyzer_run_hours) / volt_deg)
        
        # Resistance growth acceleration factor
        r_deg = max(1.0, (battery_r_int_mohm / 18.0) ** 2.0)
        bat_rul_hours = max(100.0, (self.battery_max_hours - self.battery_run_hours) / r_deg)
        
        status_alert = "NORMAL"
        if anomaly_index > 0.65 or is_anomaly:
            status_alert = "CRITICAL: Mechanical Anomaly / Component Stress Detected"
        elif anomaly_index > 0.40:
            status_alert = "ELEVATED: Early Wear Precursor Observed"

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anomaly_index, 3),
            "status_alert": status_alert,
            "turbine_vibration_g": round(float(turbine_vibration_g), 2),
            "electrolyzer_cell_v": round(float(electrolyzer_cell_v), 2),
            "battery_r_int_mohm": round(float(battery_r_int_mohm), 1),
            "turbine_rul_hours": round(float(turbine_rul_hours), 0),
            "electrolyzer_rul_hours": round(float(el_rul_hours), 0),
            "battery_rul_hours": round(float(bat_rul_hours), 0)
        }
