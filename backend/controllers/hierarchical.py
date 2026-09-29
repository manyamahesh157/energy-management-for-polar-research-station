"""
PolarSync AI - Proposed Hierarchical Dispatch Controller
Layer 1: Seasonal Long-Duration Hydrogen Storage Trajectory (Polar Night Preparation)
Layer 2: Daily Forecast-Aware MPC & Storm-Prep Thermal Inertia Storage
Layer 3: Hourly Safety-Shielded Real-Time Dispatch with Criticality Load Orchestration
"""

import math
from typing import Dict, Any, List
from backend.config import CONFIG
from backend.safety.shield import PolarSafetyShield
from backend.controllers.load_orchestrator import LoadOrchestrator
from backend.controllers.storm_prep import StormPrepController


class PolarSyncHierarchicalController:
    def __init__(self, shield: PolarSafetyShield = None):
        self.name = "PolarSync Hierarchical (Proposed)"
        self.shield = shield if shield else PolarSafetyShield()
        self.load_orchestrator = LoadOrchestrator()
        self.storm_prep = StormPrepController()
        
    def get_seasonal_h2_target_soc(self, day_of_year: int) -> float:
        """
        Seasonal macro-trajectory for Antarctic station (~70°S).
        Target is 95% full by Day 135 (start of polar night),
        drawn down safely across polar winter to 30% by Day 220,
        then refilled during spring/summer 24h midnight sun.
        """
        if day_of_year < 135:
            return 0.65 + 0.30 * (day_of_year / 135.0)
        elif day_of_year <= 220:
            progress = (day_of_year - 135) / 85.0
            return 0.95 - 0.60 * progress
        else:
            progress = (day_of_year - 220) / 145.0
            return 0.35 + 0.30 * progress

    def dispatch(
        self,
        twin_state: Dict[str, Any],
        weather: Dict[str, Any],
        forecast_24h: Dict[str, Any] = None,
        manual_storm_trigger: bool = False,
        step_idx: int = 0,
        dt_hours: float = 1.0
    ) -> Dict[str, Any]:
        """
        Executes hierarchical decision logic and filters through the deterministic safety shield.
        """
        day_of_year = int(weather.get("day", 1))
        t_amb = weather.get("ambient_temp_c", -20.0)
        w_spd = weather.get("wind_speed_ms", 8.0)
        pv_kw = twin_state.get("pv_kw", 0.0)
        wind_kw = twin_state.get("wind_kw", 0.0)
        total_ren_kw = pv_kw + wind_kw
        
        bat_soc = twin_state.get("battery_soc", 0.5)
        h2_soc = twin_state.get("h2_tank_soc", 0.6)
        h2_pressure = twin_state.get("h2_tank_pressure_bar", 200.0)
        in_temp = twin_state.get("indoor_temp_c", 20.0)
        eff_cap = twin_state.get("effective_capacity_kwh", CONFIG.battery_nominal_kwh)
        
        t1_raw = weather.get("tier1_load_kw", CONFIG.tier1_life_support_base_kw)
        t2_raw = weather.get("tier2_load_kw", CONFIG.tier2_science_base_kw)
        t3_raw = weather.get("tier3_load_kw", CONFIG.tier3_comfort_base_kw)
        
        # 1. Storm-Prep Assessment
        is_storm = self.storm_prep.evaluate_storm_trigger(
            current_weather=weather,
            forecast_24h=forecast_24h,
            manual_override=manual_storm_trigger
        )
        storm_mods = self.storm_prep.get_storm_modifications()
        
        # Thermal setpoint & heat pump demand
        target_indoor_c = storm_mods["preheat_target_c"]
        temp_deficit = target_indoor_c - in_temp
        hp_kw = max(8.0, min(CONFIG.heat_pump_rated_kw, 11.0 + 0.32 * max(0.0, -t_amb) + 2.5 * max(0.0, temp_deficit)))
        
        total_nominal_load = t1_raw + t2_raw + t3_raw + hp_kw
        net_surplus_kw = total_ren_kw - total_nominal_load
        
        seasonal_target_h2_soc = self.get_seasonal_h2_target_soc(day_of_year)
        min_allowed_soc = CONFIG.battery_storm_min_soc if is_storm else CONFIG.battery_min_soc
        
        raw_bat_kw = 0.0
        raw_el_kw = 0.0
        raw_fc_kw = 0.0
        raw_diesel_kw = 0.0
        
        if net_surplus_kw >= 0.0:
            # RENEWABLE SURPLUS:
            # 1. Charge battery up to target (85% normal, 100% storm)
            target_soc = storm_mods["target_battery_soc"]
            if bat_soc < target_soc:
                storable_kwh = max(0.0, (target_soc - bat_soc) * eff_cap)
                bat_charge_kw = min(net_surplus_kw, min(CONFIG.battery_max_charge_kw, storable_kwh / dt_hours))
                raw_bat_kw = -bat_charge_kw
                rem_surplus = net_surplus_kw - bat_charge_kw
            else:
                rem_surplus = net_surplus_kw
                
            # 2. Absorb remaining surplus into PEM Electrolyzer
            if rem_surplus >= CONFIG.electrolyzer_min_load_kw and h2_pressure < (CONFIG.h2_tank_max_bar - 15.0):
                raw_el_kw = min(CONFIG.electrolyzer_rated_kw, rem_surplus)
                
            load_orch = {
                "tier1_served_ratio": 1.0,
                "tier2_served_ratio": 1.0,
                "tier3_served_ratio": 1.0,
                "shedding_active": False,
                "shed_tier_name": "None",
                "shed_power_kw": 0.0
            }
        else:
            # RENEWABLE DEFICIT:
            deficit_kw = abs(net_surplus_kw)
            
            # Step 1: Hydrogen Fuel Cell Dispatch (Clean power + CHP heat)
            # Run fuel cell if H2 pressure is above minimum safety cushion
            if h2_pressure > (CONFIG.h2_tank_min_bar + 10.0) and h2_soc > 0.08:
                fc_cmd = min(CONFIG.fuel_cell_rated_kw, deficit_kw)
                raw_fc_kw = fc_cmd
                deficit_kw -= fc_cmd
                
            # Step 2: Battery BESS Discharge
            safe_discharge_cap_kwh = max(0.0, (bat_soc - min_allowed_soc) * eff_cap)
            bat_avail_kw = min(CONFIG.battery_max_discharge_kw, safe_discharge_cap_kwh / dt_hours)
            
            bat_discharge_kw = min(bat_avail_kw, deficit_kw)
            raw_bat_kw = bat_discharge_kw
            deficit_kw -= bat_discharge_kw
            
            # Step 3: Criticality Load Shedding before starting diesel
            if 0.0 < deficit_kw <= (t3_raw * 0.85):
                load_orch = self.load_orchestrator.orchestrate_loads(
                    available_power_kw=total_ren_kw + raw_fc_kw + raw_bat_kw,
                    t1_demand_kw=t1_raw,
                    t2_demand_kw=t2_raw,
                    t3_demand_kw=t3_raw,
                    heat_pump_demand_kw=hp_kw
                )
                deficit_kw = 0.0  # Completely resolved by non-critical load shedding!
            else:
                load_orch = self.load_orchestrator.orchestrate_loads(
                    available_power_kw=total_ren_kw + raw_fc_kw + raw_bat_kw + CONFIG.diesel_rated_kw,
                    t1_demand_kw=t1_raw,
                    t2_demand_kw=t2_raw,
                    t3_demand_kw=t3_raw,
                    heat_pump_demand_kw=hp_kw
                )
                
            # Step 4: Auxiliary Diesel Backup (Zero-blackout guarantee)
            if deficit_kw > 0.5:
                min_diesel = CONFIG.diesel_rated_kw * CONFIG.diesel_min_load_ratio
                raw_diesel_kw = max(min_diesel, min(CONFIG.diesel_rated_kw, deficit_kw))
                
                # If running at min_diesel exceeds deficit, dump surplus into battery
                gen_excess = raw_diesel_kw - deficit_kw
                if gen_excess > 1.0 and raw_bat_kw <= 0.0:
                    raw_bat_kw -= min(gen_excess, CONFIG.battery_max_charge_kw)

        proposed = {
            "battery_kw": float(raw_bat_kw),
            "electrolyzer_kw": float(raw_el_kw),
            "fuel_cell_kw": float(raw_fc_kw),
            "diesel_kw": float(raw_diesel_kw),
            "heat_pump_kw": float(hp_kw),
            "tier1_served_ratio": float(load_orch["tier1_served_ratio"]),
            "tier2_served_ratio": float(load_orch["tier2_served_ratio"]),
            "tier3_served_ratio": float(load_orch["tier3_served_ratio"])
        }
        
        # 4. Deterministic Safety Shield Filter
        safe_actions = self.shield.filter_actions(
            proposed_actions=proposed,
            twin_state=twin_state,
            weather=weather,
            storm_mode=is_storm,
            step_idx=step_idx
        )
        
        safe_actions["is_storm_mode"] = is_storm
        safe_actions["storm_message"] = self.storm_prep.storm_status_message
        safe_actions["seasonal_target_h2_soc"] = seasonal_target_h2_soc
        safe_actions["shedding_active"] = load_orch["shedding_active"]
        safe_actions["shed_tier_name"] = load_orch["shed_tier_name"]
        
        return safe_actions
