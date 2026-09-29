"""
PolarSync AI - Polar Year 8760-Hour Realistic Dataset Generator
Simulates atmospheric and physical conditions at ~70.77°S (Antarctica)
Features: Polar night, midnight sun, katabatic winds, blizzards, icing, and tiered loads.
"""

import os
import math
import numpy as np
import pandas as pd
from backend.config import CONFIG


def generate_polar_year(output_path: str = "backend/data/polar_year_8760.csv", seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    hours = 8760
    lat_rad = math.radians(CONFIG.latitude)
    
    # 1. Solar Irradiance Model (~70.77°S)
    irradiance = np.zeros(hours)
    solar_elevation = np.zeros(hours)
    
    for h in range(hours):
        day_of_year = (h // 24) + 1
        hour_of_day = h % 24
        
        # Solar declination angle
        declination_deg = 23.45 * math.sin(math.radians((360 / 365) * (284 + day_of_year)))
        dec_rad = math.radians(declination_deg)
        
        # Solar hour angle (solar noon at 12:00)
        hour_angle_deg = 15.0 * (hour_of_day - 12.0)
        ha_rad = math.radians(hour_angle_deg)
        
        # Elevation angle (sine of altitude)
        sin_elev = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
        elev_deg = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))
        solar_elevation[h] = elev_deg
        
        if elev_deg > 0:
            # Clear sky extraterrestrial + atmospheric absorption
            air_mass = 1.0 / (math.sin(math.radians(max(3.0, elev_deg))) + 0.05)
            beam_ghi = 1200.0 * (0.7 ** (air_mass ** 0.678)) * math.sin(math.radians(elev_deg))
            # Bifacial ground reflection boost (albedo ~ 0.82 for polar snow)
            albedo_gain = 1.15
            irradiance[h] = max(0.0, beam_ghi * albedo_gain)
        else:
            irradiance[h] = 0.0

    # 2. Ambient Temperature Profile (Extreme Sub-Zero Antarctic Continental Climate)
    # Seasonal base curve: warmest in Jan (day 1-31) ~ -5°C, coldest in July-Aug (day 180-240) ~ -38°C
    day_indices = np.arange(hours) / 24.0
    seasonal_temp = -22.0 + 17.0 * np.cos(2 * np.pi * (day_indices - 15) / 365.0)
    
    # Diurnal variation (smaller in winter, up to 5°C in summer)
    diurnal_amp = 1.5 + 3.5 * np.maximum(0.0, np.sin(2 * np.pi * (day_indices - 15) / 365.0))
    diurnal_variation = diurnal_amp * np.sin(2 * np.pi * (np.arange(hours) % 24 - 9) / 24.0)
    
    # Synoptic weather cycles (stochastic cold fronts and heat advection)
    synoptic_noise = np.convolve(np.random.normal(0, 4.0, hours), np.ones(36)/36, mode='same')
    temperature = seasonal_temp + diurnal_variation + synoptic_noise
    
    # 3. Wind Speed Model (Weibull + Katabatic Gusts + Blizzard Episodes)
    # Scale parameter k=2.0, c=9.5 m/s
    base_wind = np.random.weibull(2.1, hours) * 8.5
    smoothed_wind = np.convolve(base_wind, np.ones(6)/6, mode='same')
    
    # 4. Blizzard & Storm Events Injection
    # 10 realistic polar storms across the year with durations of 18 to 72 hours
    is_blizzard = np.zeros(hours, dtype=bool)
    storm_severity = np.zeros(hours)  # 0 to 5
    storm_starts = [310, 1150, 2200, 3450, 4200, 5100, 6300, 7150, 7900, 8400]
    
    wind_speed = smoothed_wind.copy()
    icing_index = np.zeros(hours)
    snow_occlusion = np.zeros(hours)
    
    for s_start in storm_starts:
        duration = int(np.random.randint(24, 72))
        s_end = min(hours, s_start + duration)
        severity = float(np.random.choice([1, 2, 3, 4, 5], p=[0.2, 0.3, 0.25, 0.15, 0.1]))
        
        is_blizzard[s_start:s_end] = True
        storm_severity[s_start:s_end] = severity
        
        # Blizzards spike wind speed up to 28 - 42 m/s and drop temperature
        storm_ramp = np.sin(np.linspace(0, np.pi, s_end - s_start))
        wind_speed[s_start:s_end] += (12.0 + severity * 4.5) * storm_ramp
        temperature[s_start:s_end] -= (4.0 + severity * 2.0) * storm_ramp
        
        # During blizzard, whiteout cuts direct solar irradiance by 85-100%
        irradiance[s_start:s_end] *= np.maximum(0.0, 1.0 - (0.6 + 0.08 * severity))
        # Severe blade icing & snow occlusion
        icing_index[s_start:min(hours, s_end + 36)] = np.minimum(1.0, 0.2 * severity)
        snow_occlusion[s_start:min(hours, s_end + 48)] = np.minimum(1.0, 0.25 * severity)

    # Clean bounds
    wind_speed = np.maximum(0.2, wind_speed)
    temperature = np.clip(temperature, -56.0, 4.0)
    
    # 5. Station Electrical & Thermal Demands (kW)
    # Tier 1: Inviolable life support & communications
    # Scales slightly with sub-zero temp due to pipe trace heaters and life support insulation
    t1_load = CONFIG.tier1_life_support_base_kw + 0.12 * np.maximum(0.0, -temperature)
    t1_load += np.random.normal(0, 0.4, hours)
    
    # Tier 2: Science & Laboratory equipment
    # Weekly scientific campaigns, radars, seismic instruments
    day_hour = np.arange(hours) % 24
    t2_active = np.where((day_hour >= 8) & (day_hour <= 20), 1.25, 0.85)
    t2_load = CONFIG.tier2_science_base_kw * t2_active + np.random.normal(0, 0.8, hours)
    
    # Tier 3: Comfort, Auxiliaries, Vehicle Charging
    # Drones and snowmobiles charged during day, restricted during blizzards
    t3_vehicles = np.where((day_hour >= 10) & (day_hour <= 18) & (~is_blizzard), CONFIG.tier3_vehicle_charge_kw, 1.5)
    t3_load = CONFIG.tier3_comfort_base_kw + t3_vehicles + np.random.normal(0, 0.7, hours)
    
    # Thermal Heating Demand (kW)
    # Conductive/infiltration building heat loss: Q = UA * (T_target - T_amb) + wind chill penalty
    wind_chill_factor = 1.0 + 0.015 * wind_speed
    thermal_heat_demand = CONFIG.building_heat_loss_kw_per_c * (CONFIG.station_target_temp_c - temperature) * wind_chill_factor
    thermal_heat_demand = np.maximum(5.0, thermal_heat_demand)

    df = pd.DataFrame({
        "hour": np.arange(hours),
        "day": (np.arange(hours) // 24) + 1,
        "solar_elevation_deg": np.round(solar_elevation, 2),
        "ghi_w_m2": np.round(irradiance, 2),
        "ambient_temp_c": np.round(temperature, 2),
        "wind_speed_ms": np.round(wind_speed, 2),
        "is_blizzard": is_blizzard,
        "storm_severity": np.round(storm_severity, 1),
        "icing_index": np.round(icing_index, 3),
        "snow_occlusion": np.round(snow_occlusion, 3),
        "tier1_load_kw": np.round(np.maximum(10.0, t1_load), 2),
        "tier2_load_kw": np.round(np.maximum(5.0, t2_load), 2),
        "tier3_load_kw": np.round(np.maximum(2.0, t3_load), 2),
        "thermal_demand_kw": np.round(thermal_heat_demand, 2)
    })
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[PolarSync DataGenerator] Successfully synthesized 8760 polar hours at {output_path}")
    return df


if __name__ == "__main__":
    generate_polar_year()
