"""
PolarSync AI - Smart Hydrogen Microgrid Digital Twin
PEM Electrolyzer, High-Pressure H2 Storage (350 bar) with Compressibility & Permeation,
and Combined Heat & Power (CHP) PEM Fuel Cell.
"""

from typing import Dict, Any
from backend.config import CONFIG


class PolarHydrogenTwin:
    def __init__(
        self,
        tank_capacity_kg: float = CONFIG.h2_tank_capacity_kg,
        initial_h2_kg: float = 240.0  # 60% initial charge
    ):
        self.tank_capacity_kg = tank_capacity_kg
        self.current_h2_kg = initial_h2_kg
        self.h2_lhv_kwh_per_kg = 33.33  # Lower heating value of hydrogen
        self.compressor_kwh_per_kg = 2.4  # Multi-stage compression to 350 bar
        self.daily_permeation_rate = 0.0005  # 0.05% loss per day
        self.electrolyzer_cur_kw = 0.0
        self.fuel_cell_cur_kw = 0.0
        
    @property
    def pressure_bar(self) -> float:
        """
        Calculates real tank pressure considering real-gas compressibility factor Z(p).
        """
        fill_fraction = max(0.0, min(1.0, self.current_h2_kg / self.tank_capacity_kg))
        # Z-factor for H2 at 350 bar is ~ 1.22
        z_factor = 1.0 + 0.22 * fill_fraction
        return max(CONFIG.h2_tank_min_bar, fill_fraction * CONFIG.h2_tank_max_bar * (1.0 / z_factor))

    @property
    def soc(self) -> float:
        return max(0.0, min(1.0, self.current_h2_kg / self.tank_capacity_kg))

    def run_electrolyzer(
        self,
        power_setpoint_kw: float,
        dt_hours: float = 1.0
    ) -> Dict[str, float]:
        """
        Consumes electrical power to produce green H2.
        Includes part-load efficiency penalties and compressor parasitics.
        """
        # Ramp rate limiting: max 30 kW change per hour
        max_ramp = 30.0 * dt_hours
        delta = power_setpoint_kw - self.electrolyzer_cur_kw
        actual_kw = self.electrolyzer_cur_kw + max(-max_ramp, min(max_ramp, delta))
        actual_kw = max(0.0, min(CONFIG.electrolyzer_rated_kw, actual_kw))
        
        if actual_kw < CONFIG.electrolyzer_min_load_kw:
            # Below 10% turndown, electrolyzer shuts down to prevent hydrogen cross-over
            actual_kw = 0.0
            
        self.electrolyzer_cur_kw = actual_kw
        
        if actual_kw <= 0.0:
            return {
                "electrolyzer_power_kw": 0.0,
                "h2_produced_kg": 0.0,
                "compression_power_kw": 0.0,
                "waste_heat_kw": 0.0
            }
            
        # Specific power consumption curve: 50 kWh/kg at rated, 56 kWh/kg at low load
        load_ratio = actual_kw / CONFIG.electrolyzer_rated_kw
        kwh_per_kg = CONFIG.electrolyzer_kwh_per_kg + 6.0 * (1.0 - load_ratio)
        
        raw_h2_kg = (actual_kw * dt_hours) / kwh_per_kg
        compression_kw = (raw_h2_kg * self.compressor_kwh_per_kg) / dt_hours
        
        # Check available tank space
        space_kg = max(0.0, self.tank_capacity_kg - self.current_h2_kg)
        actual_h2_kg = min(raw_h2_kg, space_kg)
        self.current_h2_kg += actual_h2_kg
        
        # Electrolyzer thermal waste heat (~25% of input electrical energy)
        waste_heat_kw = actual_kw * 0.25
        
        return {
            "electrolyzer_power_kw": float(actual_kw),
            "h2_produced_kg": float(actual_h2_kg),
            "compression_power_kw": float(compression_kw),
            "waste_heat_kw": float(waste_heat_kw)
        }

    def run_fuel_cell(
        self,
        power_setpoint_kw: float,
        dt_hours: float = 1.0
    ) -> Dict[str, float]:
        """
        Consumes stored H2 to supply electric power and cogenerated thermal heat (CHP).
        """
        requested_kw = max(0.0, min(CONFIG.fuel_cell_rated_kw, power_setpoint_kw))
        if requested_kw <= 0.0:
            self.fuel_cell_cur_kw = 0.0
            return {
                "fuel_cell_power_kw": 0.0,
                "h2_consumed_kg": 0.0,
                "chp_thermal_heat_kw": 0.0
            }
            
        # Fuel cell electrical efficiency: 50%
        # Chemical energy needed: P_chem = P_elec / 0.50
        chem_energy_needed_kwh = (requested_kw * dt_hours) / CONFIG.fuel_cell_eff_electrical
        h2_needed_kg = chem_energy_needed_kwh / self.h2_lhv_kwh_per_kg
        
        # Usable H2 above safety cushion (15 bar ~ 18 kg H2)
        min_reserve_kg = self.tank_capacity_kg * (CONFIG.h2_tank_min_bar / CONFIG.h2_tank_max_bar)
        available_h2_kg = max(0.0, self.current_h2_kg - min_reserve_kg)
        
        actual_h2_kg = min(h2_needed_kg, available_h2_kg)
        self.current_h2_kg -= actual_h2_kg
        
        actual_power_kw = (actual_h2_kg * self.h2_lhv_kwh_per_kg * CONFIG.fuel_cell_eff_electrical) / dt_hours
        self.fuel_cell_cur_kw = actual_power_kw
        
        # Combined Heat & Power (CHP): 40% of chemical LHV recovered as hot water / space heating
        chp_heat_kw = (actual_h2_kg * self.h2_lhv_kwh_per_kg * CONFIG.fuel_cell_eff_thermal) / dt_hours
        
        return {
            "fuel_cell_power_kw": float(actual_power_kw),
            "h2_consumed_kg": float(actual_h2_kg),
            "chp_thermal_heat_kw": float(chp_heat_kw)
        }

    def apply_hourly_losses(self, dt_hours: float = 1.0):
        """Applies permeation and micro-leak losses."""
        hourly_loss = self.current_h2_kg * (self.daily_permeation_rate / 24.0) * dt_hours
        self.current_h2_kg = max(0.0, self.current_h2_kg - hourly_loss)
