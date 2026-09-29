"""
PolarSync AI - Battery Energy Storage System (BESS) Digital Twin
Physics-based model with cold-climate electrochemical derating,
Arrhenius internal resistance, parasitic thermal jacket heating, and SoH degradation.
"""

import math
from typing import Dict, Any, Tuple
from backend.config import CONFIG


class PolarBatteryTwin:
    def __init__(
        self,
        nominal_capacity_kwh: float = CONFIG.battery_nominal_kwh,
        initial_soc: float = 0.85,
        cell_temp_c: float = 15.0
    ):
        self.nominal_capacity_kwh = nominal_capacity_kwh
        self.soc = initial_soc
        self.cell_temp_c = cell_temp_c
        self.soh = 1.0  # 100% State of Health initially
        self.nominal_r_int_ohms = 0.018  # Base internal resistance at 25°C
        self.activation_energy_ev = 0.28  # Arrhenius activation energy for LiFePO4
        self.kb_ev_k = 8.617333e-5      # Boltzmann constant in eV/K
        self.total_energy_throughput_kwh = 0.0
        self.cumulative_cycles = 0.0
        
    def get_effective_capacity(self, temp_c: float) -> float:
        """
        Calculates usable battery capacity derated by cryogenic electrolyte freezing.
        At 20°C: 100% capacity.
        At -10°C: ~80% capacity.
        At -30°C: ~55% capacity.
        At -50°C: ~32% capacity without thermal jacket.
        """
        if temp_c >= CONFIG.battery_nominal_temp_c:
            temp_derate = 1.0
        elif temp_c >= 0.0:
            temp_derate = 1.0 - 0.010 * (CONFIG.battery_nominal_temp_c - temp_c)
        else:
            # Steep electrochemical slowdown below 0°C
            temp_derate = 0.80 - 0.012 * abs(temp_c)
            
        temp_derate = max(0.20, min(1.0, temp_derate))
        return self.nominal_capacity_kwh * self.soh * temp_derate

    def get_internal_resistance(self, temp_c: float) -> float:
        """
        Arrhenius internal resistance model:
        R(T) = R_nom * exp( (E_a / k_B) * (1/T_cell - 1/T_nom) )
        Internal resistance increases up to 4-6x in extreme polar cold.
        """
        t_cell_k = max(210.0, temp_c + 273.15)
        t_nom_k = CONFIG.battery_nominal_temp_c + 273.15
        exponent = (self.activation_energy_ev / self.kb_ev_k) * ((1.0 / t_cell_k) - (1.0 / t_nom_k))
        # Cap multiplier between 0.8 and 7.5
        r_mult = min(7.5, max(0.8, math.exp(exponent)))
        # SoH degradation also increases baseline R_int
        soh_mult = 1.0 + 1.2 * (1.0 - self.soh)
        return self.nominal_r_int_ohms * r_mult * soh_mult

    def step(
        self,
        power_kw: float,
        ambient_temp_c: float,
        dt_hours: float = 1.0,
        parasitic_heating_override: bool = False
    ) -> Dict[str, Any]:
        """
        Simulates 1 time step for the BESS.
        power_kw: Positive = Discharging, Negative = Charging
        """
        # 1. Thermal Management & Parasitic Heater Loop
        # Battery container is insulated (heat loss to ambient = 0.045 kW/°C)
        insulation_loss_kw = 0.045 * (self.cell_temp_c - ambient_temp_c)
        
        # Parasitic heating engages if cell drops below 8°C or if override is set
        heater_power_kw = 0.0
        if self.cell_temp_c < 8.0 or parasitic_heating_override:
            # 2.0 kW active heating blanket to maintain electrolyte conductivity
            heater_power_kw = 2.2
            
        r_int = self.get_internal_resistance(self.cell_temp_c)
        effective_cap = self.get_effective_capacity(self.cell_temp_c)
        
        # Internal Joule heating: P_joule = I^2 * R ~ (P_kw / V_nom)^2 * R
        nominal_pack_voltage = 400.0  # 400V DC bus
        current_amps = (abs(power_kw) * 1000.0) / nominal_pack_voltage
        joule_heat_kw = (current_amps ** 2 * r_int) / 1000.0
        
        # Battery thermal capacitance: ~12 kWh/°C
        heat_net_kwh = (joule_heat_kw + heater_power_kw - insulation_loss_kw) * dt_hours
        self.cell_temp_c += heat_net_kwh / 12.0
        self.cell_temp_c = max(ambient_temp_c, min(35.0, self.cell_temp_c))
        
        # Total power drawn from battery includes cell power and parasitic heaters
        total_drawn_kw = power_kw + heater_power_kw
        
        # Round-trip Coulombic efficiency derated by cold
        coulomb_eff = max(0.75, 0.94 - 0.003 * max(0.0, 15.0 - self.cell_temp_c))
        
        if total_drawn_kw >= 0.0:
            # Discharging
            actual_discharge_kw = min(total_drawn_kw, CONFIG.battery_max_discharge_kw)
            energy_delta_kwh = actual_discharge_kw * dt_hours / coulomb_eff
            # Prevent SOC from dropping below absolute floor (0.05)
            max_available_kwh = max(0.0, (self.soc - 0.05) * effective_cap)
            energy_delta_kwh = min(energy_delta_kwh, max_available_kwh)
            self.soc -= energy_delta_kwh / effective_cap
            delivered_power_kw = (energy_delta_kwh * coulomb_eff) / dt_hours - heater_power_kw
        else:
            # Charging (total_drawn_kw is negative)
            charge_power_kw = min(abs(total_drawn_kw), CONFIG.battery_max_charge_kw)
            energy_delta_kwh = charge_power_kw * dt_hours * coulomb_eff
            max_storable_kwh = max(0.0, (1.0 - self.soc) * effective_cap)
            energy_delta_kwh = min(energy_delta_kwh, max_storable_kwh)
            self.soc += energy_delta_kwh / effective_cap
            delivered_power_kw = - (energy_delta_kwh / (coulomb_eff * dt_hours)) + heater_power_kw
            
        self.soc = max(0.05, min(1.0, self.soc))
        self.total_energy_throughput_kwh += abs(delivered_power_kw) * dt_hours
        self.cumulative_cycles = self.total_energy_throughput_kwh / (2.0 * self.nominal_capacity_kwh)
        
        # SoH degradation: 20% loss over 4000 full equivalent cycles + cold stress penalty
        cold_stress_factor = 1.0 + 0.02 * max(0.0, -self.cell_temp_c)
        cycle_fade = (self.cumulative_cycles / 4000.0) * 0.20 * cold_stress_factor
        self.soh = max(0.65, 1.0 - cycle_fade)
        
        return {
            "soc": float(self.soc),
            "soh": float(self.soh),
            "cell_temp_c": float(self.cell_temp_c),
            "effective_capacity_kwh": float(effective_cap),
            "internal_resistance_mohm": float(r_int * 1000.0),
            "parasitic_heater_kw": float(heater_power_kw),
            "actual_power_kw": float(delivered_power_kw),
            "cumulative_cycles": float(self.cumulative_cycles)
        }
