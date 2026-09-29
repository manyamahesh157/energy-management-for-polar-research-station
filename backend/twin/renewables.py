"""
PolarSync AI - Renewable Generation Digital Twin
Hybrid Polar Solar PV (Bifacial + Albedo + Snow Occlusion + Cryogenic Voltage Boost)
and Arctic Wind Turbines (Air Density Scaling + Blade Icing + Storm Feathering).
"""

import math
from typing import Dict, Any
from backend.config import CONFIG


class PolarRenewablesTwin:
    def __init__(
        self,
        pv_capacity_kw: float = CONFIG.pv_capacity_kw,
        wind_capacity_kw: float = CONFIG.wind_capacity_kw
    ):
        self.pv_capacity_kw = pv_capacity_kw
        self.wind_capacity_kw = wind_capacity_kw
        self.standard_air_density = 1.225  # kg/m^3 at 15°C sea level
        self.pv_temp_coeff = -0.0035       # -0.35%/°C (cold increases silicon bandgap voltage)
        
    def calculate_pv_power(
        self,
        ghi_w_m2: float,
        ambient_temp_c: float,
        solar_elevation_deg: float,
        snow_occlusion: float = 0.0,
        active_heating: bool = False
    ) -> Dict[str, float]:
        """
        Computes solar PV output under Antarctic conditions.
        """
        if solar_elevation_deg <= 0.0 or ghi_w_m2 <= 0.0:
            return {"pv_power_kw": 0.0, "snow_loss_kw": 0.0, "cold_gain_kw": 0.0}
            
        # Snow clearing: active heating or high wind clears snow
        effective_snow_occlusion = max(0.0, snow_occlusion - (0.4 if active_heating else 0.0))
        
        # Freezing ambient temperature increases PV cell efficiency!
        cell_temp_c = ambient_temp_c + (ghi_w_m2 / 800.0) * 20.0
        temp_factor = 1.0 + self.pv_temp_coeff * (cell_temp_c - 25.0)
        temp_factor = max(0.9, min(1.22, temp_factor))
        
        # Bifacial rear-side snow albedo gain (0.82 albedo for Antarctic ice sheet)
        bifaciality = 0.70
        albedo = 0.82
        bifacial_factor = 1.0 + (bifaciality * albedo * 0.25)
        
        raw_power_kw = self.pv_capacity_kw * (ghi_w_m2 / 1000.0) * bifacial_factor
        power_with_temp_kw = raw_power_kw * temp_factor
        actual_power_kw = power_with_temp_kw * (1.0 - effective_snow_occlusion)
        
        snow_loss_kw = power_with_temp_kw - actual_power_kw
        cold_gain_kw = max(0.0, power_with_temp_kw - raw_power_kw)
        
        return {
            "pv_power_kw": float(max(0.0, min(self.pv_capacity_kw * 1.25, actual_power_kw))),
            "snow_loss_kw": float(max(0.0, snow_loss_kw)),
            "cold_gain_kw": float(cold_gain_kw)
        }

    def calculate_wind_power(
        self,
        wind_speed_ms: float,
        ambient_temp_c: float,
        icing_index: float = 0.0,
        deicing_active: bool = False
    ) -> Dict[str, Any]:
        """
        Computes wind turbine generation considering cryogenic air density,
        blade icing degradation, and safety feathering in storm winds (>25 m/s).
        """
        # Cryogenic air density scaling: rho = p / (R_spec * T)
        # Cold Antarctic air is significantly denser, packing more kinetic energy
        temp_k = max(210.0, ambient_temp_c + 273.15)
        air_density = self.standard_air_density * (288.15 / temp_k)
        density_ratio = air_density / self.standard_air_density
        
        # 1. Storm Safety Feathering Check
        # Turbines cut out at > 25 m/s to prevent structural blade shedding or gearbox fire
        is_feathered = False
        feathering_reason = "Normal"
        
        if wind_speed_ms >= CONFIG.wind_cut_out_ms:
            is_feathered = True
            feathering_reason = f"Storm High-Wind Cut-out ({wind_speed_ms:.1f} m/s >= {CONFIG.wind_cut_out_ms} m/s)"
            return {
                "wind_power_kw": 0.0,
                "air_density_kg_m3": float(air_density),
                "icing_penalty_kw": 0.0,
                "is_feathered": True,
                "feathering_reason": feathering_reason,
                "deicing_parasitic_kw": 6.0 if deicing_active else 0.0
            }
            
        if wind_speed_ms < CONFIG.wind_cut_in_ms:
            return {
                "wind_power_kw": 0.0,
                "air_density_kg_m3": float(air_density),
                "icing_penalty_kw": 0.0,
                "is_feathered": False,
                "feathering_reason": "Below Cut-in Speed",
                "deicing_parasitic_kw": 6.0 if deicing_active else 0.0
            }
            
        # 2. Aerodynamic Power Curve with Density Scaling
        if wind_speed_ms < CONFIG.wind_rated_ms:
            # Cubic region P ~ v^3 * (rho / rho_0)
            norm_v = (wind_speed_ms - CONFIG.wind_cut_in_ms) / (CONFIG.wind_rated_ms - CONFIG.wind_cut_in_ms)
            base_power_kw = self.wind_capacity_kw * (norm_v ** 2.8) * density_ratio
        else:
            # Rated region with active pitch regulation
            base_power_kw = self.wind_capacity_kw * min(1.15, density_ratio)
            
        # 3. Blade Icing Derating
        # Icing disrupts laminar boundary layer, lowering lift/drag ratio
        effective_icing = max(0.0, icing_index - (0.75 if deicing_active else 0.0))
        icing_penalty_factor = 1.0 - (0.42 * effective_icing)
        
        actual_wind_power_kw = base_power_kw * icing_penalty_factor
        icing_penalty_kw = base_power_kw - actual_wind_power_kw
        
        deicing_kw = 6.0 if deicing_active else 0.0  # 3 kW per turbine for blade heating elements
        net_wind_power_kw = max(0.0, actual_wind_power_kw - deicing_kw)
        
        return {
            "wind_power_kw": float(min(self.wind_capacity_kw * 1.18, net_wind_power_kw)),
            "air_density_kg_m3": float(air_density),
            "icing_penalty_kw": float(icing_penalty_kw),
            "is_feathered": False,
            "feathering_reason": "Normal Operation",
            "deicing_parasitic_kw": float(deicing_kw)
        }
