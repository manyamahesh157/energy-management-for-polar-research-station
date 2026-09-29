"""
PolarSync AI - Criticality-Tiered Load Orchestrator (Feature B)
Manages staged load shedding and automatic restoration across 3 priority tiers:
Tier 1: Life support, medical, communications (Inviolable 100%)
Tier 2: Scientific radars, LIDAR, ice-core freezers (Prioritized)
Tier 3: Comfort, auxiliary heating, field EV/drone charging (Flexible / Sheddable)
Provides an operator-editable priority configuration.
"""

from typing import Dict, Any, Tuple
from pydantic import BaseModel


class LoadTierConfig(BaseModel):
    tier1_weight: float = 1.00      # Life support priority weight
    tier2_weight: float = 0.85      # Science priority weight
    tier3_weight: float = 0.40      # Comfort & vehicles priority weight
    tier1_min_ratio: float = 1.00   # Inviolable 100% floor
    tier2_min_ratio: float = 0.50   # 50% minimum science preservation in deficit
    tier3_min_ratio: float = 0.00   # Can be 100% shed if needed


class LoadOrchestrator:
    def __init__(self, config: LoadTierConfig = None):
        self.config = config if config else LoadTierConfig()
        self.last_shed_tier = "None"
        self.shedding_active = False

    def update_priority_table(self, new_config: Dict[str, float]):
        """Allows operator to adjust tier priorities live from dashboard."""
        if "tier2_weight" in new_config:
            self.config.tier2_weight = float(new_config["tier2_weight"])
        if "tier3_weight" in new_config:
            self.config.tier3_weight = float(new_config["tier3_weight"])
        if "tier2_min_ratio" in new_config:
            self.config.tier2_min_ratio = float(new_config["tier2_min_ratio"])

    def orchestrate_loads(
        self,
        available_power_kw: float,
        t1_demand_kw: float,
        t2_demand_kw: float,
        t3_demand_kw: float,
        heat_pump_demand_kw: float
    ) -> Dict[str, Any]:
        """
        Determines served ratios for each load tier to match available generation & storage.
        Tier 1 is always 100% protected.
        """
        essential_demand = t1_demand_kw + heat_pump_demand_kw
        remaining_power = available_power_kw - essential_demand
        
        # Tier 1 is always served 100%
        t1_ratio = 1.0
        
        if remaining_power >= (t2_demand_kw + t3_demand_kw):
            # All tiers served 100%
            self.shedding_active = False
            self.last_shed_tier = "None"
            return {
                "tier1_served_ratio": 1.0,
                "tier2_served_ratio": 1.0,
                "tier3_served_ratio": 1.0,
                "shedding_active": False,
                "shed_tier_name": "None",
                "shed_power_kw": 0.0
            }
            
        self.shedding_active = True
        
        if remaining_power >= t2_demand_kw:
            # Tier 2 fully served, Tier 3 partially shed
            t2_ratio = 1.0
            t3_avail = max(0.0, remaining_power - t2_demand_kw)
            t3_ratio = max(self.config.tier3_min_ratio, min(1.0, t3_avail / max(0.1, t3_demand_kw)))
            self.last_shed_tier = "Tier 3 (Comfort & Vehicles)"
            shed_kw = t3_demand_kw * (1.0 - t3_ratio)
        elif remaining_power > 0.0:
            # Tier 3 completely shed, Tier 2 partially shed down to floor
            t3_ratio = self.config.tier3_min_ratio
            t2_ratio = max(self.config.tier2_min_ratio, min(1.0, remaining_power / max(0.1, t2_demand_kw)))
            self.last_shed_tier = "Tier 3 (100% Shed) + Tier 2 (Science Throttled)"
            shed_kw = t3_demand_kw + (t2_demand_kw * (1.0 - t2_ratio))
        else:
            # Extreme deficit: Tier 3 and Tier 2 dropped to their minimum allowable bounds
            t3_ratio = self.config.tier3_min_ratio
            t2_ratio = self.config.tier2_min_ratio
            self.last_shed_tier = "CRITICAL: Tier 2 Science at Minimum Safe Floor"
            shed_kw = t3_demand_kw * (1.0 - t3_ratio) + t2_demand_kw * (1.0 - t2_ratio)
            
        return {
            "tier1_served_ratio": float(t1_ratio),
            "tier2_served_ratio": float(t2_ratio),
            "tier3_served_ratio": float(t3_ratio),
            "shedding_active": True,
            "shed_tier_name": self.last_shed_tier,
            "shed_power_kw": float(shed_kw)
        }
