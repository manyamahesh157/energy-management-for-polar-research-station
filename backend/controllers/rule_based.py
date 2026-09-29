"""
PolarSync AI - Baseline (a): Rule-Based Diesel-Hybrid Controller
Standard myopic polar station logic:
Dispatches renewables, then battery peak shaving.
Starts diesel generator when battery hits 35% SOC, runs at high load until 75% SOC.
No seasonal hydrogen planning, no thermal pre-heating, no forecast awareness.
"""

from typing import Dict, Any
from backend.config import CONFIG


class RuleBasedDieselController:
    def __init__(self):
        self.diesel_is_on = False
        self.name = "Rule-Based Diesel-Hybrid"

    def dispatch(
        self,
        twin_state: Dict[str, Any],
        weather: Dict[str, Any],
        dt_hours: float = 1.0
    ) -> Dict[str, float]:
        pv_kw = twin_state.get("pv_kw", 0.0)
        wind_kw = twin_state.get("wind_kw", 0.0)
        total_ren_kw = pv_kw + wind_kw
        
        t1 = weather.get("tier1_load_kw", 18.0)
        t2 = weather.get("tier2_load_kw", 14.0)
        t3 = weather.get("tier3_load_kw", 10.0)
        t_amb = weather.get("ambient_temp_c", -20.0)
        
        # Fixed heat pump load based on outdoor temp
        hp_kw = max(6.0, min(24.0, 10.0 + 0.3 * (-t_amb)))
        total_load_kw = t1 + t2 + t3 + hp_kw
        
        net_surplus_kw = total_ren_kw - total_load_kw
        soc = twin_state.get("battery_soc", 0.5)
        
        battery_kw = 0.0
        electrolyzer_kw = 0.0
        fuel_cell_kw = 0.0
        diesel_kw = 0.0
        
        # Generator Hysteresis (Starts at 35%, stops at 75%)
        if soc <= 0.35:
            self.diesel_is_on = True
        elif soc >= 0.75:
            self.diesel_is_on = False
            
        if net_surplus_kw >= 0.0:
            # Surplus power: charge battery first, then discard excess (naive)
            battery_charge_needed = min(abs(net_surplus_kw), CONFIG.battery_max_charge_kw)
            battery_kw = -battery_charge_needed  # Negative = charging
            # In naive baseline, electrolyzer is only run if battery is completely full (>95%)
            if soc >= 0.95:
                electrolyzer_kw = min(CONFIG.electrolyzer_rated_kw, net_surplus_kw - battery_charge_needed)
        else:
            deficit_kw = abs(net_surplus_kw)
            if self.diesel_is_on:
                # Run diesel at 70% rated load
                diesel_kw = 70.0
                gen_surplus = diesel_kw - deficit_kw
                if gen_surplus > 0:
                    battery_kw = -min(gen_surplus, CONFIG.battery_max_charge_kw)
                else:
                    battery_kw = min(abs(gen_surplus), CONFIG.battery_max_discharge_kw)
            else:
                # Discharge battery to cover deficit
                battery_kw = min(deficit_kw, CONFIG.battery_max_discharge_kw)
                rem_deficit = deficit_kw - battery_kw
                if rem_deficit > 5.0:
                    # Emergency diesel start
                    self.diesel_is_on = True
                    diesel_kw = 60.0

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
