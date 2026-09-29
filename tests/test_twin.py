"""
Unit Tests for Physics-Informed Digital Twin
Verifies cold-climate battery derating, wind air density/feathering,
hydrogen conservation, and building thermal capacitance.
"""

import unittest
from backend.config import CONFIG
from backend.twin.battery import PolarBatteryTwin
from backend.twin.renewables import PolarRenewablesTwin
from backend.twin.hydrogen import PolarHydrogenTwin
from backend.twin.thermal import PolarThermalTwin


class TestPhysicsTwin(unittest.TestCase):
    def test_battery_cold_derating(self):
        bat = PolarBatteryTwin(nominal_capacity_kwh=250.0)
        cap_warm = bat.get_effective_capacity(temp_c=20.0)
        cap_subzero = bat.get_effective_capacity(temp_c=-15.0)
        cap_extreme = bat.get_effective_capacity(temp_c=-45.0)
        
        self.assertEqual(cap_warm, 250.0)
        self.assertLess(cap_subzero, cap_warm)
        self.assertLess(cap_extreme, cap_subzero)
        self.assertGreaterEqual(cap_extreme, 50.0)

    def test_battery_arrhenius_resistance(self):
        bat = PolarBatteryTwin()
        r_warm = bat.get_internal_resistance(temp_c=25.0)
        r_cold = bat.get_internal_resistance(temp_c=-35.0)
        
        self.assertGreater(r_cold, r_warm * 2.0)
        self.assertLessEqual(r_cold, 0.150)

    def test_wind_density_and_feathering(self):
        ren = PolarRenewablesTwin()
        res_gale = ren.calculate_wind_power(wind_speed_ms=28.0, ambient_temp_c=-20.0)
        self.assertTrue(res_gale["is_feathered"])
        self.assertEqual(res_gale["wind_power_kw"], 0.0)
        
        res_warm = ren.calculate_wind_power(wind_speed_ms=8.0, ambient_temp_c=5.0)
        res_cold = ren.calculate_wind_power(wind_speed_ms=8.0, ambient_temp_c=-40.0)
        self.assertGreater(res_cold["air_density_kg_m3"], res_warm["air_density_kg_m3"])
        self.assertGreater(res_cold["wind_power_kw"], res_warm["wind_power_kw"])

    def test_hydrogen_conservation(self):
        h2 = PolarHydrogenTwin(tank_capacity_kg=400.0, initial_h2_kg=100.0)
        prod_res = h2.run_electrolyzer(power_setpoint_kw=50.0, dt_hours=1.0)
        self.assertGreater(prod_res["h2_produced_kg"], 0.0)
        self.assertGreater(h2.current_h2_kg, 100.0)
        
        cur_h2 = h2.current_h2_kg
        fc_res = h2.run_fuel_cell(power_setpoint_kw=30.0, dt_hours=1.0)
        self.assertGreater(fc_res["fuel_cell_power_kw"], 0.0)
        self.assertGreater(fc_res["h2_consumed_kg"], 0.0)
        self.assertLess(h2.current_h2_kg, cur_h2)

    def test_thermal_building_inertia(self):
        thm = PolarThermalTwin(initial_indoor_temp_c=20.0, initial_tank_soc=0.0)
        res = thm.step(
            heat_pump_electric_kw=0.0,
            chp_heat_kw=0.0,
            ambient_temp_c=-40.0,
            wind_speed_ms=20.0,
            dt_hours=1.0
        )
        self.assertLess(res["indoor_temp_c"], 20.0)
        self.assertGreater(res["building_heat_loss_kw"], 10.0)


if __name__ == "__main__":
    unittest.main()
