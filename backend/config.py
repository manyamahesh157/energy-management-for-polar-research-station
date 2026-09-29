"""
PolarSync AI - Central Configuration
Polar Station Parameters (Calibrated to Indian Antarctic Station Maitri / Bharati ~70°S)
"""

from pydantic import BaseModel
from typing import Dict, Any


class StationConfig(BaseModel):
    # Station Identity
    station_name: str = "PolarSync-Maitri"
    latitude: float = -70.767
    longitude: float = 11.733
    elevation_m: float = 117.0
    
    # Renewable Generation Capacities
    pv_capacity_kw: float = 80.0          # Bifacial polar solar PV array
    wind_capacity_kw: float = 120.0       # 2 x 60 kW Arctic-rated wind turbines
    wind_cut_in_ms: float = 3.0           # Cut-in wind speed (m/s)
    wind_rated_ms: float = 11.5          # Rated wind speed (m/s)
    wind_cut_out_ms: float = 25.0         # Safety feathering cut-out (m/s)
    
    # Battery Energy Storage System (BESS)
    battery_nominal_kwh: float = 250.0    # LiFePO4 cold-adapted battery
    battery_min_soc: float = 0.20         # Nominal minimum SOC
    battery_storm_min_soc: float = 0.35   # Reserved floor during storm mode
    battery_max_charge_kw: float = 75.0   # Max charge rate
    battery_max_discharge_kw: float = 75.0 # Max discharge rate
    battery_nominal_temp_c: float = 20.0  # Nominal operating temp
    
    # Hydrogen Microgrid (Long-Duration Storage)
    electrolyzer_rated_kw: float = 60.0   # PEM Electrolyzer
    electrolyzer_min_load_kw: float = 6.0 # 10% minimum turndown
    electrolyzer_kwh_per_kg: float = 52.0 # Specific energy consumption
    h2_tank_capacity_kg: float = 400.0    # 400 kg H2 ~ 13.3 MWh chemical energy
    h2_tank_max_bar: float = 350.0        # Max pressure rating
    h2_tank_min_bar: float = 15.0         # Minimum safety pad pressure
    fuel_cell_rated_kw: float = 45.0      # PEM Fuel Cell
    fuel_cell_eff_electrical: float = 0.50 # 50% electrical efficiency
    fuel_cell_eff_thermal: float = 0.40    # 40% thermal cogeneration efficiency
    
    # Thermal & Building Inertia
    station_area_m2: float = 850.0        # Heated station floor area
    building_heat_cap_kwh_per_c: float = 4.5 # Thermal inertia capacitance
    building_heat_loss_kw_per_c: float = 0.85 # Overall heat transfer coefficient (UA)
    station_target_temp_c: float = 20.0   # Life support target temperature
    station_min_safe_temp_c: float = 16.0 # Critical safety floor for habitat
    thermal_tank_capacity_kwh: float = 150.0 # Insulated hot water thermal buffer
    heat_pump_rated_kw: float = 30.0      # Variable refrigerant heat pump
    
    # Auxiliary Diesel Generators (N+1 redundancy)
    diesel_rated_kw: float = 100.0        # 2 x 50 kW gensets
    diesel_min_load_ratio: float = 0.30   # Minimum 30% load to prevent wet stacking
    diesel_l_per_kwh: float = 0.27        # Specific fuel consumption (L/kWh)
    diesel_co2_kg_per_l: float = 2.68     # CO2 emissions factor (kg CO2/L)
    delivered_fuel_cost_inr_per_l: float = 320.0 # Polar delivered cost (air drop / ship)
    
    # Load Breakdown Baselines (kW)
    tier1_life_support_base_kw: float = 18.0  # Inviolable (oxygen, comms, medical, freeze prevention)
    tier2_science_base_kw: float = 14.0       # Atmospheric radar, ice coring, seismology
    tier3_comfort_base_kw: float = 10.0       # Auxiliary heating, laundry, non-essential tools
    tier3_vehicle_charge_kw: float = 12.0     # Snowmobiles, UAV drone recharge


CONFIG = StationConfig()
