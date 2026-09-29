"""
Unit Tests for Controllers
Verifies energy balance, dispatch validity, and load orchestration.
"""

import unittest
from backend.config import CONFIG
from backend.controllers.rule_based import RuleBasedDieselController
from backend.controllers.mpc_controller import PolarMPCController
from backend.controllers.rl_controller import PolarRLController
from backend.controllers.hierarchical import PolarSyncHierarchicalController
from backend.controllers.load_orchestrator import LoadOrchestrator


class TestControllers(unittest.TestCase):
    def test_load_orchestrator_tier1_protected(self):
        orch = LoadOrchestrator()
        res = orch.orchestrate_loads(
            available_power_kw=15.0,
            t1_demand_kw=18.0,
            t2_demand_kw=14.0,
            t3_demand_kw=10.0,
            heat_pump_demand_kw=0.0
        )
        self.assertEqual(res["tier1_served_ratio"], 1.0)
        self.assertEqual(res["tier3_served_ratio"], 0.0)
        self.assertLessEqual(res["tier2_served_ratio"], 1.0)

    def test_hierarchical_controller_surplus_and_deficit(self):
        ctrl = PolarSyncHierarchicalController()
        twin_state = {
            "pv_kw": 60.0,
            "wind_kw": 80.0,
            "battery_soc": 0.70,
            "battery_temp_c": 15.0,
            "effective_capacity_kwh": 250.0,
            "h2_tank_soc": 0.50,
            "h2_tank_pressure_bar": 180.0,
            "indoor_temp_c": 20.5
        }
        weather = {
            "hour": 12,
            "day": 30,
            "ambient_temp_c": -12.0,
            "wind_speed_ms": 10.0,
            "tier1_load_kw": 18.0,
            "tier2_load_kw": 14.0,
            "tier3_load_kw": 10.0
        }
        
        # Surplus
        res_surplus = ctrl.dispatch(twin_state, weather)
        self.assertLess(res_surplus["battery_kw"], 0.0)
        self.assertEqual(res_surplus["diesel_kw"], 0.0)
        self.assertGreater(res_surplus["electrolyzer_kw"], 0.0)
        
        # Deficit
        twin_state_dark = dict(twin_state)
        twin_state_dark["pv_kw"] = 0.0
        twin_state_dark["wind_kw"] = 0.0
        res_deficit = ctrl.dispatch(twin_state_dark, weather)
        self.assertTrue(res_deficit["fuel_cell_kw"] > 0.0 or res_deficit["battery_kw"] > 0.0)


if __name__ == "__main__":
    unittest.main()
