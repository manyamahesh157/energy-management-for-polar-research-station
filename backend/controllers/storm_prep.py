"""
PolarSync AI - Storm-Prep Mode Controller (Feature D)
Forecast-triggered blizzard and icing early-warning protocol.
Pre-charges BESS to 100%, pre-heats station thermal mass, tops off thermal storage,
and issues emergency recall for polar rovers and survey UAVs.
"""

from typing import Dict, Any


class StormPrepController:
    def __init__(self):
        self.storm_mode_active = False
        self.storm_severity = 0.0
        self.preheat_target_c = 22.5
        self.recall_field_units = False
        self.storm_status_message = "Normal: Atmospheric conditions nominal"

    def evaluate_storm_trigger(
        self,
        current_weather: Dict[str, Any],
        forecast_24h: Dict[str, Any] = None,
        manual_override: bool = False,
        manual_severity: float = 3.0
    ) -> bool:
        """
        Detects oncoming blizzard from current weather, 24h forecast, or manual operator trigger.
        """
        is_blizzard = current_weather.get("is_blizzard", False)
        wind_spd = current_weather.get("wind_speed_ms", 8.0)
        severity = current_weather.get("storm_severity", 0.0)
        
        # Check forecast for impending storm within 12h
        impending_storm = False
        if forecast_24h and "wind_speed_ms" in forecast_24h:
            max_future_wind = max(forecast_24h["wind_speed_ms"]["upper_q90"][:12])
            if max_future_wind > 22.0:
                impending_storm = True
                
        if manual_override:
            self.storm_mode_active = True
            self.storm_severity = manual_severity
            self.recall_field_units = True
            self.storm_status_message = f"ACTIVE: Category {manual_severity:.0f} Polar Blizzard Emergency Protocol Enacted"
            return True
        elif is_blizzard or wind_spd > 21.0 or impending_storm:
            self.storm_mode_active = True
            self.storm_severity = max(1.0, severity)
            self.recall_field_units = True
            self.storm_status_message = f"ACTIVE: Forecast Blizzard Warning (Wind: {wind_spd:.1f} m/s, Sev: {self.storm_severity:.0f})"
            return True
        else:
            self.storm_mode_active = False
            self.storm_severity = 0.0
            self.recall_field_units = False
            self.storm_status_message = "Normal: All microgrid subsystems nominal"
            return False

    def get_storm_modifications(self) -> Dict[str, Any]:
        """
        Returns setpoint adjustments for storage, thermal mass, and load priorities.
        """
        if not self.storm_mode_active:
            return {
                "preheat_target_c": 20.0,
                "target_battery_soc": 0.85,
                "recall_field_units": False,
                "storm_mode_active": False,
                "deicing_active": False
            }
            
        return {
            "preheat_target_c": self.preheat_target_c,
            "target_battery_soc": 1.00,  # Top off to 100%
            "recall_field_units": True,
            "storm_mode_active": True,
            "deicing_active": True
        }
