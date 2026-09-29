"""
PolarSync AI - Carbon & Cost Ledger (Feature L)
Real-time running ticker for environmental and economic impact:
1. Cumulative Liters of polar diesel saved
2. Cumulative kg CO2 emissions avoided (2.68 kg CO2/L)
3. Financial savings in INR based on adjustable delivered fuel price (air drop/ship logistics)
4. Running savings velocity ticker (INR/hour, kg CO2/hour).
"""

from typing import Dict, Any
from backend.config import CONFIG


class CarbonCostLedger:
    def __init__(self, fuel_price_inr_per_l: float = CONFIG.delivered_fuel_cost_inr_per_l):
        self.fuel_price_inr_per_l = fuel_price_inr_per_l
        self.co2_factor_kg_per_l = CONFIG.diesel_co2_kg_per_l
        self.cumulative_diesel_actual_l = 0.0
        self.cumulative_diesel_baseline_l = 0.0
        self.steps_recorded = 0

    def update_step(
        self,
        actual_liters_step: float,
        baseline_liters_step: float,
        dt_hours: float = 1.0
    ):
        """Records 1 time step."""
        self.steps_recorded += 1
        self.cumulative_diesel_actual_l += actual_liters_step
        self.cumulative_diesel_baseline_l += baseline_liters_step

    def get_ledger_metrics(self) -> Dict[str, Any]:
        """Calculates running ledger KPIs and ticker outputs."""
        liters_saved = max(0.0, self.cumulative_diesel_baseline_l - self.cumulative_diesel_actual_l)
        co2_avoided_kg = liters_saved * self.co2_factor_kg_per_l
        co2_emitted_kg = self.cumulative_diesel_actual_l * self.co2_factor_kg_per_l
        
        inr_saved = liters_saved * self.fuel_price_inr_per_l
        inr_spent = self.cumulative_diesel_actual_l * self.fuel_price_inr_per_l
        
        hours_elapsed = max(1.0, float(self.steps_recorded))
        hourly_savings_inr = inr_saved / hours_elapsed
        hourly_co2_avoided_kg = co2_avoided_kg / hours_elapsed
        
        savings_pct = (liters_saved / max(1.0, self.cumulative_diesel_baseline_l)) * 100.0

        return {
            "delivered_fuel_price_inr_l": float(self.fuel_price_inr_per_l),
            "liters_consumed": round(float(self.cumulative_diesel_actual_l), 1),
            "liters_saved": round(float(liters_saved), 1),
            "savings_pct": round(float(savings_pct), 1),
            "co2_emitted_kg": round(float(co2_emitted_kg), 1),
            "co2_avoided_kg": round(float(co2_avoided_kg), 1),
            "co2_avoided_tons": round(float(co2_avoided_kg / 1000.0), 2),
            "inr_spent": round(float(inr_spent), 0),
            "inr_saved": round(float(inr_saved), 0),
            "inr_saved_lakhs": round(float(inr_saved / 100000.0), 2),
            "hourly_savings_rate_inr": round(float(hourly_savings_inr), 1),
            "hourly_co2_avoided_kg": round(float(hourly_co2_avoided_kg), 2)
        }
