"""
PolarSync AI - Thermal Storage & Building Thermal Inertia Twin
Models station building capacitance, heat transfer losses, heat pump COP vs temperature,
and hot-water thermal storage tank.
"""

from typing import Dict, Any
from backend.config import CONFIG


class PolarThermalTwin:
    def __init__(
        self,
        initial_indoor_temp_c: float = 20.5,
        initial_tank_soc: float = 0.60
    ):
        self.indoor_temp_c = initial_indoor_temp_c
        self.thermal_tank_capacity_kwh = CONFIG.thermal_tank_capacity_kwh
        self.tank_stored_kwh = initial_tank_soc * self.thermal_tank_capacity_kwh
        self.internal_gains_kw = 3.5  # Constant thermal emission from occupants and electronics
        
    def calculate_cop(self, ambient_temp_c: float) -> float:
        """
        Thermodynamic COP of variable-refrigerant polar heat pump.
        COP degrades significantly below -30°C.
        """
        t_in_k = self.indoor_temp_c + 273.15
        delta_t = max(10.0, (self.indoor_temp_c - ambient_temp_c))
        # Carnot fraction ~ 0.42 with 18K refrigerant approach temperature
        cop = 0.42 * (t_in_k / (delta_t + 18.0))
        return float(max(1.15, min(4.2, cop)))

    def step(
        self,
        heat_pump_electric_kw: float,
        chp_heat_kw: float,
        ambient_temp_c: float,
        wind_speed_ms: float,
        dt_hours: float = 1.0,
        pre_heat_target_c: float = None
    ) -> Dict[str, Any]:
        """
        Simulates 1 time step of station thermal dynamics.
        """
        target_temp = pre_heat_target_c if pre_heat_target_c else CONFIG.station_target_temp_c
        
        # 1. Building Heat Loss (Conductive + Infiltration + Wind Chill)
        wind_chill_factor = 1.0 + 0.015 * wind_speed_ms
        heat_loss_kw = CONFIG.building_heat_loss_kw_per_c * (self.indoor_temp_c - ambient_temp_c) * wind_chill_factor
        heat_loss_kw = max(2.0, heat_loss_kw)
        
        # 2. Heat Pump Thermal Output
        cop = self.calculate_cop(ambient_temp_c)
        hp_elec_actual = max(0.0, min(CONFIG.heat_pump_rated_kw, heat_pump_electric_kw))
        hp_heat_kw = hp_elec_actual * cop
        
        # 3. Thermal Tank Management
        # Total heating available from HP + Fuel Cell CHP
        total_heat_input_kw = hp_heat_kw + chp_heat_kw
        net_heat_flow_kw = total_heat_input_kw + self.internal_gains_kw - heat_loss_kw
        
        tank_charge_discharge_kw = 0.0
        if net_heat_flow_kw > 0.0:
            # Surplus heat charges the thermal buffer tank
            available_tank_space = max(0.0, self.thermal_tank_capacity_kwh - self.tank_stored_kwh)
            storable_kwh = min(net_heat_flow_kw * dt_hours, available_tank_space)
            self.tank_stored_kwh += storable_kwh
            tank_charge_discharge_kw = storable_kwh / dt_hours
            excess_heat_to_bldg_kw = net_heat_flow_kw - tank_charge_discharge_kw
        else:
            # Deficit: thermal tank discharges to support building
            needed_kwh = abs(net_heat_flow_kw) * dt_hours
            extractable_kwh = min(needed_kwh, self.tank_stored_kwh)
            self.tank_stored_kwh -= extractable_kwh
            tank_charge_discharge_kw = -extractable_kwh / dt_hours
            excess_heat_to_bldg_kw = net_heat_flow_kw + (extractable_kwh / dt_hours)
            
        # 4. Building Temperature Update via Thermal Capacitance
        # dT = (Q_net * dt) / C_bldg
        temp_delta = (excess_heat_to_bldg_kw * dt_hours) / CONFIG.building_heat_cap_kwh_per_c
        self.indoor_temp_c += temp_delta
        
        # Tank standing heat loss to ambient (1.5% per hour)
        self.tank_stored_kwh = max(0.0, self.tank_stored_kwh * (1.0 - 0.015 * dt_hours))
        
        return {
            "indoor_temp_c": float(self.indoor_temp_c),
            "heat_pump_cop": float(cop),
            "heat_pump_electric_kw": float(hp_elec_actual),
            "heat_pump_thermal_kw": float(hp_heat_kw),
            "building_heat_loss_kw": float(heat_loss_kw),
            "tank_stored_kwh": float(self.tank_stored_kwh),
            "tank_soc": float(self.tank_stored_kwh / self.thermal_tank_capacity_kwh),
            "is_temp_safe": bool(self.indoor_temp_c >= CONFIG.station_min_safe_temp_c)
        }
