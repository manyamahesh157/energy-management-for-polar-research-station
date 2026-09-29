"""
PolarSync AI - Chaos / Fault Injection Engine (Feature G)
Injects realistic polar hardware & communication faults:
1. Sensor dropout (telemetry loss / noise)
2. Satellite outage (auroral blackout / edge-only autonomous fallback)
3. Turbine mechanical trip (loss of 50% wind capacity)
4. PEM Electrolyzer trip (membrane safety lockout)
5. Sudden cold snap (-20°C temperature cliff)
6. Battery string cell failure (capacity derating & resistance spike)
Verifies graceful degradation and autonomous system recovery.
"""

from typing import Dict, Any, List, Tuple
from pydantic import BaseModel


class ChaosState(BaseModel):
    sensor_dropout: bool = False
    satellite_outage: bool = False
    turbine_fault: bool = False
    electrolyzer_trip: bool = False
    sudden_cold_snap: bool = False
    battery_cell_failure: bool = False


class ChaosFaultInjector:
    def __init__(self):
        self.state = ChaosState()
        self.active_faults_log: List[str] = []

    def set_fault(self, fault_name: str, enabled: bool) -> Dict[str, Any]:
        """Toggles a specific fault on or off."""
        if hasattr(self.state, fault_name):
            setattr(self.state, fault_name, enabled)
            action_desc = "ACTIVATED" if enabled else "CLEARED"
            msg = f"Fault '{fault_name}' {action_desc} by operator."
            self.active_faults_log.insert(0, msg)
            if len(self.active_faults_log) > 50:
                self.active_faults_log.pop()
            return {"status": "success", "message": msg, "state": self.state.dict()}
        return {"status": "error", "message": f"Unknown fault: {fault_name}"}

    def reset_all(self):
        """Clears all injected chaos faults."""
        self.state = ChaosState()
        self.active_faults_log.insert(0, "ALL CHAOS FAULTS CLEARED: Nominal baseline restored.")

    def apply_chaos(
        self,
        raw_weather: Dict[str, Any],
        raw_twin_state: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Applies active faults to environment and twin state, returning modified states
        and edge mode diagnostic indicators.
        """
        weather = dict(raw_weather)
        twin = dict(raw_twin_state)
        diagnostics = {
            "mode": "Central Normal",
            "edge_fallback_active": False,
            "degradation_level": "None",
            "active_fault_count": 0,
            "system_health_pct": 100.0
        }
        
        fault_count = sum(1 for v in self.state.dict().values() if v)
        diagnostics["active_fault_count"] = fault_count
        
        # 1. Satellite Outage -> Edge-Only Fallback
        if self.state.satellite_outage:
            diagnostics["mode"] = "EDGE-AUTONOMOUS (Satellite Scintillation / Link Severed)"
            diagnostics["edge_fallback_active"] = True
            diagnostics["system_health_pct"] -= 15.0
            
        # 2. Sensor Dropout
        if self.state.sensor_dropout:
            # Drop telemetry reading and replace with Kalman filter extrapolated prediction
            weather["wind_speed_ms"] = max(1.0, weather.get("wind_speed_ms", 8.0) * 0.92)  # Extrapolated
            weather["sensor_telemetry_valid"] = False
            diagnostics["system_health_pct"] -= 10.0
        else:
            weather["sensor_telemetry_valid"] = True

        # 3. Turbine Fault (Lose 1 of 2 turbines -> 50% capacity loss)
        if self.state.turbine_fault:
            twin["wind_kw"] = twin.get("wind_kw", 0.0) * 0.50
            twin["active_turbines"] = 1
            diagnostics["system_health_pct"] -= 20.0
        else:
            twin["active_turbines"] = 2

        # 4. Electrolyzer Trip
        if self.state.electrolyzer_trip:
            twin["electrolyzer_lockout"] = True
            twin["electrolyzer_kw"] = 0.0
            diagnostics["system_health_pct"] -= 15.0
        else:
            twin["electrolyzer_lockout"] = False

        # 5. Sudden Cold Snap (-20°C drop)
        if self.state.sudden_cold_snap:
            weather["ambient_temp_c"] = weather.get("ambient_temp_c", -20.0) - 20.0
            diagnostics["system_health_pct"] -= 15.0

        # 6. Battery Cell Failure (1 of 3 strings fails)
        if self.state.battery_cell_failure:
            twin["battery_soc"] = max(0.15, twin.get("battery_soc", 0.5) * 0.67)
            twin["battery_r_int_mohm"] = twin.get("battery_r_int_mohm", 18.0) * 2.2
            diagnostics["system_health_pct"] -= 25.0

        diagnostics["system_health_pct"] = max(10.0, diagnostics["system_health_pct"])
        if fault_count > 0:
            diagnostics["degradation_level"] = "CRITICAL" if fault_count >= 3 else "MODERATE"

        return weather, twin, diagnostics
