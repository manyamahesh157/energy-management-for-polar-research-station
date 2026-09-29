"""
PolarSync AI - Integrated Station Digital Twin
Coordinates Battery, Hydrogen (Electrolyzer + Tank + Fuel Cell), Renewables (Wind + Solar),
Thermal Heating, Auxiliary Diesel, and Tiered Station Loads.
"""

from typing import Dict, Any
from backend.config import CONFIG
from backend.twin.battery import PolarBatteryTwin
from backend.twin.renewables import PolarRenewablesTwin
from backend.twin.hydrogen import PolarHydrogenTwin
from backend.twin.thermal import PolarThermalTwin


class PolarStationTwin:
    def __init__(self):
        self.battery = PolarBatteryTwin()
        self.renewables = PolarRenewablesTwin()
        self.hydrogen = PolarHydrogenTwin()
        self.thermal = PolarThermalTwin()
        
        # Diesel Generator State
        self.diesel_is_running = False
        self.diesel_starts_count = 0
        self.total_diesel_run_hours = 0.0
        self.total_fuel_liters = 0.0
        self.total_co2_kg = 0.0
        
        # Microgrid Metrics
        self.total_unserved_kwh = 0.0
        self.total_curtailment_kwh = 0.0
        self.total_renewable_generated_kwh = 0.0

    def step(
        self,
        weather: Dict[str, Any],
        dispatch_actions: Dict[str, float],
        dt_hours: float = 1.0,
        storm_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Executes 1 simulation step.
        dispatch_actions: {
            'battery_kw': float (pos=discharge, neg=charge),
            'electrolyzer_kw': float,
            'fuel_cell_kw': float,
            'diesel_kw': float,
            'heat_pump_kw': float,
            'tier1_served_ratio': float (0.0 to 1.0),
            'tier2_served_ratio': float (0.0 to 1.0),
            'tier3_served_ratio': float (0.0 to 1.0)
        }
        """
        # 1. Weather Inputs
        ghi = weather.get("ghi_w_m2", 0.0)
        t_amb = weather.get("ambient_temp_c", -20.0)
        w_spd = weather.get("wind_speed_ms", 8.0)
        elev = weather.get("solar_elevation_deg", 10.0)
        snow_occ = weather.get("snow_occlusion", 0.0)
        icing = weather.get("icing_index", 0.0)
        
        # 2. Renewable Generation
        pv_res = self.renewables.calculate_pv_power(
            ghi_w_m2=ghi,
            ambient_temp_c=t_amb,
            solar_elevation_deg=elev,
            snow_occlusion=snow_occ,
            active_heating=storm_mode
        )
        pv_kw = pv_res["pv_power_kw"]
        
        wind_res = self.renewables.calculate_wind_power(
            wind_speed_ms=w_spd,
            ambient_temp_c=t_amb,
            icing_index=icing,
            deicing_active=storm_mode
        )
        wind_kw = wind_res["wind_power_kw"]
        total_ren_kw = pv_kw + wind_kw
        self.total_renewable_generated_kwh += total_ren_kw * dt_hours
        
        # 3. Hydrogen Microgrid
        el_cmd = dispatch_actions.get("electrolyzer_kw", 0.0)
        el_res = self.hydrogen.run_electrolyzer(el_cmd, dt_hours=dt_hours)
        
        fc_cmd = dispatch_actions.get("fuel_cell_kw", 0.0)
        fc_res = self.hydrogen.run_fuel_cell(fc_cmd, dt_hours=dt_hours)
        self.hydrogen.apply_hourly_losses(dt_hours=dt_hours)
        
        # 4. Thermal Dynamics
        hp_cmd = dispatch_actions.get("heat_pump_kw", 12.0)
        th_res = self.thermal.step(
            heat_pump_electric_kw=hp_cmd,
            chp_heat_kw=fc_res["chp_thermal_heat_kw"],
            ambient_temp_c=t_amb,
            wind_speed_ms=w_spd,
            dt_hours=dt_hours
        )
        
        # 5. Station Electrical Loads
        t1_raw = weather.get("tier1_load_kw", CONFIG.tier1_life_support_base_kw)
        t2_raw = weather.get("tier2_load_kw", CONFIG.tier2_science_base_kw)
        t3_raw = weather.get("tier3_load_kw", CONFIG.tier3_comfort_base_kw)
        
        t1_ratio = dispatch_actions.get("tier1_served_ratio", 1.0)
        t2_ratio = dispatch_actions.get("tier2_served_ratio", 1.0)
        t3_ratio = dispatch_actions.get("tier3_served_ratio", 1.0)
        
        t1_served_kw = t1_raw * t1_ratio
        t2_served_kw = t2_raw * t2_ratio
        t3_served_kw = t3_raw * t3_ratio
        
        # Unserved loads
        unserved_step_kwh = ((t1_raw - t1_served_kw) + (t2_raw - t2_served_kw) + (t3_raw - t3_served_kw)) * dt_hours
        self.total_unserved_kwh += max(0.0, unserved_step_kwh)
        
        total_elec_load_kw = t1_served_kw + t2_served_kw + t3_served_kw + hp_cmd + el_res["compression_power_kw"]
        
        # 6. Battery Dispatch
        bat_cmd = dispatch_actions.get("battery_kw", 0.0)
        bat_res = self.battery.step(
            power_kw=bat_cmd,
            ambient_temp_c=t_amb,
            dt_hours=dt_hours,
            parasitic_heating_override=storm_mode
        )
        bat_actual_kw = bat_res["actual_power_kw"]
        
        # 7. Auxiliary Diesel Generation
        diesel_cmd = dispatch_actions.get("diesel_kw", 0.0)
        diesel_actual_kw = 0.0
        fuel_consumed_l = 0.0
        
        if diesel_cmd > 5.0:
            # Enforce minimum generator load ratio (30 kW)
            diesel_actual_kw = max(CONFIG.diesel_rated_kw * CONFIG.diesel_min_load_ratio, min(CONFIG.diesel_rated_kw, diesel_cmd))
            if not self.diesel_is_running:
                self.diesel_starts_count += 1
                self.diesel_is_running = True
            self.total_diesel_run_hours += dt_hours
            
            # Specific fuel consumption: 0.27 L/kWh
            fuel_consumed_l = diesel_actual_kw * CONFIG.diesel_l_per_kwh * dt_hours
            self.total_fuel_liters += fuel_consumed_l
            self.total_co2_kg += fuel_consumed_l * CONFIG.diesel_co2_kg_per_l
        else:
            self.diesel_is_running = False

        # 8. Net Power Balance & Curtailment
        total_supply_kw = total_ren_kw + fc_res["fuel_cell_power_kw"] + diesel_actual_kw + bat_actual_kw
        total_demand_kw = total_elec_load_kw + el_res["electrolyzer_power_kw"]
        
        curtailment_kw = max(0.0, total_supply_kw - total_demand_kw)
        deficit_kw = max(0.0, total_demand_kw - total_supply_kw)
        self.total_curtailment_kwh += curtailment_kw * dt_hours
        self.total_unserved_kwh += deficit_kw * dt_hours

        return {
            "pv_kw": float(pv_kw),
            "wind_kw": float(wind_kw),
            "total_renewable_kw": float(total_ren_kw),
            "battery_kw": float(bat_actual_kw),
            "battery_soc": float(bat_res["soc"]),
            "battery_soh": float(bat_res["soh"]),
            "battery_temp_c": float(bat_res["cell_temp_c"]),
            "battery_r_int_mohm": float(bat_res["internal_resistance_mohm"]),
            "electrolyzer_kw": float(el_res["electrolyzer_power_kw"]),
            "fuel_cell_kw": float(fc_res["fuel_cell_power_kw"]),
            "h2_tank_soc": float(self.hydrogen.soc),
            "h2_tank_pressure_bar": float(self.hydrogen.pressure_bar),
            "h2_stored_kg": float(self.hydrogen.current_h2_kg),
            "diesel_kw": float(diesel_actual_kw),
            "diesel_running": bool(self.diesel_is_running),
            "fuel_liters_step": float(fuel_consumed_l),
            "indoor_temp_c": float(th_res["indoor_temp_c"]),
            "thermal_tank_soc": float(th_res["tank_soc"]),
            "heat_pump_kw": float(th_res["heat_pump_electric_kw"]),
            "t1_served_kw": float(t1_served_kw),
            "t2_served_kw": float(t2_served_kw),
            "t3_served_kw": float(t3_served_kw),
            "curtailment_kw": float(curtailment_kw),
            "deficit_kw": float(deficit_kw),
            "is_feathered": bool(wind_res["is_feathered"]),
            "feathering_reason": str(wind_res["feathering_reason"])
        }
