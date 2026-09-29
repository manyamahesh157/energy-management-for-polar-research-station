"""
PolarSync AI - 4-Way Controller Benchmark Engine
Simulates a full polar year (8760 hours) across identical weather for:
1. Rule-Based Diesel-Hybrid (Baseline a)
2. MPC Only (Baseline b)
3. RL Only (Baseline c)
4. PolarSync Hierarchical (Proposed)
Outputs honest KPIs: Fuel (L), CO2 (kg), Run-hours, Starts, Battery Cycles, Unserved Energy, Curtailment.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.config import CONFIG
from backend.twin.station_twin import PolarStationTwin
from backend.controllers.rule_based import RuleBasedDieselController
from backend.controllers.mpc_controller import PolarMPCController
from backend.controllers.rl_controller import PolarRLController
from backend.controllers.hierarchical import PolarSyncHierarchicalController


def run_annual_benchmark(data_path: str = "backend/data/polar_year_8760.csv") -> Dict[str, Any]:
    df = pd.read_csv(data_path)
    n_hours = len(df)
    
    controllers = [
        ("Rule-Based Diesel", RuleBasedDieselController()),
        ("MPC Only", PolarMPCController()),
        ("RL (TD3 Deep)", PolarRLController()),
        ("PolarSync Hierarchical", PolarSyncHierarchicalController())
    ]
    
    results = {}
    
    for name, ctrl in controllers:
        twin = PolarStationTwin()
        
        # Step through all 8760 hours
        for idx in range(n_hours):
            row = df.iloc[idx].to_dict()
            
            # Get current twin state snapshot
            twin_state = {
                "pv_kw": twin.renewables.calculate_pv_power(
                    ghi_w_m2=row["ghi_w_m2"],
                    ambient_temp_c=row["ambient_temp_c"],
                    solar_elevation_deg=row["solar_elevation_deg"],
                    snow_occlusion=row["snow_occlusion"]
                )["pv_power_kw"],
                "wind_kw": twin.renewables.calculate_wind_power(
                    wind_speed_ms=row["wind_speed_ms"],
                    ambient_temp_c=row["ambient_temp_c"],
                    icing_index=row["icing_index"]
                )["wind_power_kw"],
                "battery_soc": twin.battery.soc,
                "battery_temp_c": twin.battery.cell_temp_c,
                "effective_capacity_kwh": twin.battery.get_effective_capacity(twin.battery.cell_temp_c),
                "h2_tank_soc": twin.hydrogen.soc,
                "h2_tank_pressure_bar": twin.hydrogen.pressure_bar,
                "indoor_temp_c": twin.thermal.indoor_temp_c
            }
            
            # Dispatch command
            if name == "PolarSync Hierarchical":
                dispatch_actions = ctrl.dispatch(
                    twin_state=twin_state,
                    weather=row,
                    forecast_24h=None,
                    step_idx=idx
                )
            else:
                dispatch_actions = ctrl.dispatch(
                    twin_state=twin_state,
                    weather=row
                )
                
            # Advance twin
            twin.step(
                weather=row,
                dispatch_actions=dispatch_actions,
                dt_hours=1.0,
                storm_mode=row["is_blizzard"]
            )
            
        fuel_cost_inr = twin.total_fuel_liters * CONFIG.delivered_fuel_cost_inr_per_l
        
        results[name] = {
            "fuel_liters": round(float(twin.total_fuel_liters), 1),
            "co2_emitted_kg": round(float(twin.total_co2_kg), 1),
            "diesel_run_hours": round(float(twin.total_diesel_run_hours), 1),
            "genset_starts": int(twin.diesel_starts_count),
            "battery_cycles": round(float(twin.battery.cumulative_cycles), 1),
            "unserved_energy_kwh": round(float(twin.total_unserved_kwh), 1),
            "curtailment_kwh": round(float(twin.total_curtailment_kwh), 1),
            "fuel_cost_inr": round(float(fuel_cost_inr), 0)
        }
        
    # Compute relative savings vs Rule-Based baseline
    base_fuel = results["Rule-Based Diesel"]["fuel_liters"]
    for k in results:
        f = results[k]["fuel_liters"]
        saving_pct = ((base_fuel - f) / max(1.0, base_fuel)) * 100.0
        results[k]["fuel_saving_pct"] = round(float(saving_pct), 1)

    return results


if __name__ == "__main__":
    print("[Benchmark] Running 8760h comparison...")
    res = run_annual_benchmark()
    summary_df = pd.DataFrame(res).T
    print(summary_df.to_string())
