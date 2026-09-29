"""
Unit Tests for Deterministic Safety Shield
Verifies inviolability of life-support Tier 1, battery cryogenic SOC floors,
H2 pressure bounds, and generator anti-wet-stacking clamp.
"""

import unittest
from backend.config import CONFIG
from backend.safety.shield import PolarSafetyShield


class TestSafetyShield(unittest.TestCase):
    def test_safety_shield_tier1_inviolable(self):
        shield = PolarSafetyShield()
        rogue_actions = {
            "tier1_served_ratio": 0.20,
            "tier2_served_ratio": 1.00,
            "tier3_served_ratio": 1.00,
            "battery_kw": 0.0,
            "diesel_kw": 0.0
        }
        twin_state = {"battery_soc": 0.5, "effective_capacity_kwh": 250.0}
        weather = {"ambient_temp_c": -25.0}
        
        safe = shield.filter_actions(rogue_actions, twin_state, weather, storm_mode=False, step_idx=1)
        self.assertEqual(safe["tier1_served_ratio"], 1.0)
        self.assertGreaterEqual(shield.total_vetoes_count, 1)
        self.assertTrue(any(v.rule_id == "RULE_01" for v in shield.audit_log))

    def test_safety_shield_battery_soc_floor(self):
        shield = PolarSafetyShield()
        excessive_discharge = {
            "battery_kw": 75.0,
            "diesel_kw": 0.0,
            "tier1_served_ratio": 1.0
        }
        twin_state = {"battery_soc": 0.22, "effective_capacity_kwh": 250.0}
        weather = {"ambient_temp_c": -30.0}
        
        safe = shield.filter_actions(excessive_discharge, twin_state, weather, storm_mode=False, step_idx=2)
        self.assertLess(safe["battery_kw"], 10.0)
        self.assertGreater(safe["diesel_kw"], 0.0)
        self.assertTrue(any(v.rule_id == "RULE_02" for v in shield.audit_log))

    def test_safety_shield_h2_overpressure(self):
        shield = PolarSafetyShield()
        h2_overload = {
            "electrolyzer_kw": 60.0,
            "battery_kw": 0.0,
            "tier1_served_ratio": 1.0
        }
        twin_state = {
            "h2_tank_pressure_bar": 346.0,
            "h2_tank_soc": 0.99,
            "battery_soc": 0.6
        }
        weather = {"ambient_temp_c": -15.0}
        
        safe = shield.filter_actions(h2_overload, twin_state, weather, storm_mode=False, step_idx=3)
        self.assertEqual(safe["electrolyzer_kw"], 0.0)
        self.assertTrue(any(v.rule_id == "RULE_03" for v in shield.audit_log))

    def test_safety_shield_diesel_wet_stacking_clamp(self):
        shield = PolarSafetyShield()
        low_load_diesel = {
            "diesel_kw": 10.0,
            "tier1_served_ratio": 1.0
        }
        twin_state = {"battery_soc": 0.5}
        weather = {"ambient_temp_c": -20.0}
        
        safe = shield.filter_actions(low_load_diesel, twin_state, weather, storm_mode=False, step_idx=4)
        self.assertEqual(safe["diesel_kw"], 30.0)
        self.assertTrue(any(v.rule_id == "RULE_06" for v in shield.audit_log))


if __name__ == "__main__":
    unittest.main()
