"""
PolarSync AI - Polar-Night Survival Planner (Feature A)
Runs a Monte Carlo ensemble (>=200 stochastic weather rollouts) during polar night / winter.
Calculates:
1. Days of autonomy remaining
2. Probability of blackout: P(blackout)
3. CVaR-95 of fuel consumption in the worst 5% extreme weather tail
4. Dynamic countdown to critical reserve depletion & recommended survival action.
"""

import numpy as np
from typing import Dict, Any, List
from backend.config import CONFIG


class PolarSurvivalPlanner:
    def __init__(self, n_scenarios: int = 250):
        self.n_scenarios = n_scenarios
        
    def evaluate_survival(
        self,
        current_battery_kwh: float,
        current_h2_kg: float,
        diesel_stock_liters: float,
        current_day: int = 150,  # Middle of Antarctic polar night
        daily_t1_base_kwh: float = 432.0,  # 18 kW * 24h
        daily_thermal_kwh: float = 380.0
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo ensemble across N stochastic polar weather paths.
        """
        np.random.seed(current_day)
        horizon_days = 90  # Look ahead 90 days of Antarctic winter
        
        # Chemical & electrical energy equivalents
        # 1 kg H2 ~ 33.33 kWh * 0.50 electrical = 16.66 kWh_e + 13.33 kWh_th
        h2_elec_kwh = max(0.0, (current_h2_kg - 18.0) * 16.66)
        h2_th_kwh = max(0.0, (current_h2_kg - 18.0) * 13.33)
        # 1 L Diesel ~ 3.70 kWh electrical (0.27 L/kWh) + 3.0 kWh thermal
        diesel_elec_kwh = diesel_stock_liters / CONFIG.diesel_l_per_kwh
        
        total_initial_energy = current_battery_kwh + h2_elec_kwh + diesel_elec_kwh
        
        fuel_needed_per_scenario = []
        blackout_occurred = 0
        autonomy_days_sim = []
        
        for sim in range(self.n_scenarios):
            # Stochastic weather path: wind speed variations + blizzard occurrences
            # Polar winter has ~20-30% probability of blizzard weeks with high wind or dead calms
            calm_days_count = 0
            curr_bat = current_battery_kwh
            curr_h2 = h2_elec_kwh
            curr_diesel = diesel_stock_liters
            survived_days = 0
            
            for d in range(horizon_days):
                # Daily stochastic wind generation (mean 120 kW nameplate * CF ~ 0.35)
                is_gale_blizzard = (np.random.rand() < 0.12)
                if is_gale_blizzard:
                    # Gale winds > 25 m/s cause safety feathering -> wind power drops to 0!
                    daily_wind_kwh = np.random.uniform(0.0, 300.0)
                    ambient_t = np.random.uniform(-52.0, -38.0)
                else:
                    cf = np.random.beta(2.5, 4.0)  # Typical polar wind capacity factor distribution
                    daily_wind_kwh = 120.0 * 24.0 * cf
                    ambient_t = np.random.uniform(-42.0, -22.0)
                    
                # Winter thermal demand increases with cold
                daily_heat_kwh = daily_thermal_kwh * (1.0 + 0.015 * abs(ambient_t))
                daily_total_elec_demand = daily_t1_base_kwh + (daily_heat_kwh / 2.2)  # Heat pump COP ~ 2.2
                
                net_day_kwh = daily_wind_kwh - daily_total_elec_demand
                
                if net_day_kwh >= 0:
                    # Surplus charges battery, then H2
                    curr_bat = min(CONFIG.battery_nominal_kwh, curr_bat + net_day_kwh)
                else:
                    def_kwh = abs(net_day_kwh)
                    # Use H2 first
                    if curr_h2 > 0:
                        used_h2 = min(curr_h2, def_kwh)
                        curr_h2 -= used_h2
                        def_kwh -= used_h2
                    # Use Battery
                    if def_kwh > 0 and curr_bat > (CONFIG.battery_nominal_kwh * 0.20):
                        avail_bat = curr_bat - (CONFIG.battery_nominal_kwh * 0.20)
                        used_bat = min(avail_bat, def_kwh)
                        curr_bat -= used_bat
                        def_kwh -= used_bat
                    # Use Diesel
                    if def_kwh > 0:
                        needed_l = def_kwh * CONFIG.diesel_l_per_kwh
                        if curr_diesel >= needed_l:
                            curr_diesel -= needed_l
                        else:
                            # Blackout! Reserves exhausted
                            break
                            
                survived_days += 1
                
            autonomy_days_sim.append(survived_days)
            fuel_used_l = diesel_stock_liters - curr_diesel
            fuel_needed_per_scenario.append(fuel_used_l)
            if survived_days < horizon_days:
                blackout_occurred += 1
                
        # Statistics
        p_blackout = blackout_occurred / self.n_scenarios
        mean_autonomy = float(np.mean(autonomy_days_sim))
        min_autonomy = float(np.min(autonomy_days_sim))
        
        # CVaR-95 of fuel consumption (expected fuel in worst 5% tail)
        sorted_fuel = np.sort(fuel_needed_per_scenario)
        tail_idx = int(0.95 * len(sorted_fuel))
        cvar_95_fuel_l = float(np.mean(sorted_fuel[tail_idx:]))
        median_fuel_l = float(np.median(sorted_fuel))
        
        # Recommended Operator Action based on risk threshold
        if p_blackout > 0.08 or min_autonomy < 35.0:
            rec_action = "CRITICAL: Enact Tier-2 Science Rationing (30% reduction) & lock auxiliary drone expeditions."
            risk_level = "CRITICAL"
        elif p_blackout > 0.02 or min_autonomy < 55.0:
            rec_action = "ELEVATED: Pre-heat thermal buffer using Fuel Cell CHP during windy intervals."
            risk_level = "ELEVATED"
        else:
            rec_action = "NOMINAL: Reserves adequate for full polar night mission profile."
            risk_level = "LOW RISK"

        return {
            "p_blackout": round(float(p_blackout), 3),
            "p_blackout_pct": round(float(p_blackout * 100.0), 1),
            "mean_autonomy_days": round(mean_autonomy, 1),
            "min_autonomy_days": round(min_autonomy, 1),
            "cvar95_fuel_liters": round(cvar_95_fuel_l, 1),
            "median_fuel_liters": round(median_fuel_l, 1),
            "recommended_action": rec_action,
            "risk_level": risk_level,
            "n_scenarios_evaluated": self.n_scenarios
        }
