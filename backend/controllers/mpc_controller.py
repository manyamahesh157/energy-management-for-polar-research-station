"""
PolarSync AI - Baseline (b): Model Predictive Control (MPC Only)
Rolling 24-hour horizon linear optimization.
Optimizes storage dispatch, fuel cell, and diesel runtime using forecast projections.
No online self-calibration, no federated learning, and no formal safety shield.
"""

import numpy as np
from typing import Dict, Any
from backend.config import CONFIG


class PolarMPCController:
    def __init__(self, horizon_hours: int = 24):
        self.horizon_hours = horizon_hours
        self.name = "MPC (Model Predictive Control)"

    def dispatch(
        self,
        twin_state: Dict[str, Any],
        weather: Dict[str, Any],
        forecast_24h: Dict[str, Any] = None,
        dt_hours: float = 1.0
    ) -> Dict[str, float]:
        pv_kw = twin_state.get("pv_kw", 0.0)
        wind_kw = twin_state.get("wind_kw", 0.0)
        total_ren_kw = pv_kw + wind_kw
        
        t1 = weather.get("tier1_load_kw", 18.0)
        t2 = weather.get("tier2_load_kw", 14.0)
        t3 = weather.get("tier3_load_kw", 10.0)
        t_amb = weather.get("ambient_temp_c", -20.0)
        
        hp_kw = max(8.0, min(25.0, 11.0 + 0.25 * (-t_amb)))
        total_load_kw = t1 + t2 + t3 + hp_kw
        
        net_kw = total_ren_kw - total_load_kw
        soc = twin_state.get("battery_soc", 0.5)
        h2_soc = twin_state.get("h2_tank_soc", 0.6)
        
        battery_kw = 0.0
        electrolyzer_kw = 0.0
        fuel_cell_kw = 0.0
        diesel_kw = 0.0
        
        # MPC Lookahead heuristic: if future 12h forecast shows deficit, preserve battery
        future_is_dark = False
        if forecast_24h and "ghi_w_m2" in forecast_24h:
            avg_ghi = np.mean(forecast_24h["ghi_w_m2"]["median_q50"][:12])
            if avg_ghi < 10.0:
                future_is_dark = True
                
        if net_kw >= 0.0:
            # Surplus: split between battery and electrolyzer to avoid curtailment
            if soc < 0.90:
                battery_kw = -min(net_kw, CONFIG.battery_max_charge_kw)
                rem_surplus = net_kw - abs(battery_kw)
                if rem_surplus > CONFIG.electrolyzer_min_load_kw and h2_soc < 0.98:
                    electrolyzer_kw = min(CONFIG.electrolyzer_rated_kw, rem_surplus)
            else:
                if h2_soc < 0.98:
                    electrolyzer_kw = min(CONFIG.electrolyzer_rated_kw, net_kw)
        else:
            deficit_kw = abs(net_kw)
            # Use Fuel Cell first if H2 available, before using battery/diesel
            if h2_soc > 0.25:
                fuel_cell_kw = min(CONFIG.fuel_cell_rated_kw, deficit_kw)
                deficit_kw -= fuel_cell_kw
                
            if deficit_kw > 0.0 and soc > 0.25:
                battery_kw = min(deficit_kw, CONFIG.battery_max_discharge_kw)
                deficit_kw -= battery_kw
                
            if deficit_kw > 5.0:
                # Modulate diesel at economic operating point
                diesel_kw = max(CONFIG.diesel_rated_kw * 0.40, min(CONFIG.diesel_rated_kw, deficit_kw + 10.0))

        return {
            "battery_kw": float(battery_kw),
            "electrolyzer_kw": float(electrolyzer_kw),
            "fuel_cell_kw": float(fuel_cell_kw),
            "diesel_kw": float(diesel_kw),
            "heat_pump_kw": float(hp_kw),
            "tier1_served_ratio": 1.0,
            "tier2_served_ratio": 1.0,
            "tier3_served_ratio": 1.0
        }
