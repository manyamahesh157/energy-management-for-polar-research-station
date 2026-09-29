"""
PolarSync AI - Resupply & Logistics Optimizer (Feature H)
Translates polar microgrid diesel savings into strategic mission logistics:
1. Resupply missions avoided (LC-130 Hercules air drops and Icebreaker voyages)
2. Next resupply date recommendation based on stock depletion curve
3. Fuel stock trajectory tracking and 30-day emergency buffer preservation.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from backend.config import CONFIG


class PolarLogisticsOptimizer:
    def __init__(
        self,
        initial_tank_capacity_l: float = 120000.0,  # 120k L station fuel depot
        emergency_buffer_l: float = 25000.0        # 25k L untouchable reserve
    ):
        self.tank_capacity_l = initial_tank_capacity_l
        self.emergency_buffer_l = emergency_buffer_l
        self.lc130_cargo_flight_liters = 15000.0   # Capacity of single polar LC-130 flight
        self.icebreaker_tank_liters = 90000.0      # Capacity of chartered resupply ship

    def calculate_logistics_impact(
        self,
        current_stock_liters: float,
        baseline_annual_fuel_l: float,
        actual_annual_fuel_l: float,
        current_daily_burn_rate_l: float
    ) -> Dict[str, Any]:
        """
        Computes missions avoided, financial savings, and resupply deadline.
        """
        liters_saved = max(0.0, baseline_annual_fuel_l - actual_annual_fuel_l)
        
        # Missions avoided
        flights_avoided = liters_saved / self.lc130_cargo_flight_liters
        ships_avoided = liters_saved / self.icebreaker_tank_liters
        
        # Financial logistics savings (INR)
        cost_saved_inr = liters_saved * CONFIG.delivered_fuel_cost_inr_per_l
        
        # Resupply date projection
        usable_stock_l = max(0.0, current_stock_liters - self.emergency_buffer_l)
        burn_rate = max(15.0, current_daily_burn_rate_l)
        
        days_to_depletion = usable_stock_l / burn_rate
        today = datetime.now()
        target_resupply_date = today + timedelta(days=int(days_to_depletion))
        
        urgency = "LOW"
        if days_to_depletion < 45:
            urgency = "CRITICAL: Urgent Resupply Flight Booking Required"
        elif days_to_depletion < 90:
            urgency = "MEDIUM: Schedule Summer Icebreaker Voyage"
        else:
            urgency = "OPTIMAL: Ample Logistics Cushion"

        return {
            "liters_saved_annual": round(float(liters_saved), 1),
            "cost_saved_inr": round(float(cost_saved_inr), 0),
            "cost_saved_crores_inr": round(float(cost_saved_inr / 1e7), 2),
            "lc130_flights_avoided": round(float(flights_avoided), 2),
            "icebreaker_voyages_avoided": round(float(ships_avoided), 2),
            "days_to_resupply_deadline": round(float(days_to_depletion), 1),
            "recommended_resupply_date": target_resupply_date.strftime("%Y-%m-%d"),
            "logistics_urgency": urgency,
            "emergency_buffer_liters": float(self.emergency_buffer_l)
        }
