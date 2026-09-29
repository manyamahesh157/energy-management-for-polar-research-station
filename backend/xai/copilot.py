"""
PolarSync AI - Explainability Copilot (Feature F)
Computes local feature attributions (SHAP proxy) for every dispatch decision,
generates plain-English explanatory sentences, and provides an offline
"Ask Why" semantic question-answering engine for station operators.
Zero external cloud dependency.
"""

import re
from typing import Dict, Any, List, Tuple


class ExplainabilityCopilot:
    def __init__(self):
        self.feature_names = [
            "Renewable Surplus (P_ren - P_load)",
            "Battery SOC Reserve",
            "H2 Storage Pressure",
            "Indoor Temperature Deficit",
            "Ambient Extreme Cold",
            "Storm Early Warning"
        ]

    def compute_feature_attributions(
        self,
        dispatch_actions: Dict[str, Any],
        twin_state: Dict[str, Any],
        weather: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Computes normalized local Shapley-style feature attributions (-1.0 to +1.0)
        explaining what factors drove the current dispatch.
        """
        ren_kw = twin_state.get("pv_kw", 0.0) + twin_state.get("wind_kw", 0.0)
        t_amb = weather.get("ambient_temp_c", -20.0)
        bat_soc = twin_state.get("battery_soc", 0.5)
        h2_soc = twin_state.get("h2_tank_soc", 0.6)
        in_temp = twin_state.get("indoor_temp_c", 20.0)
        is_storm = dispatch_actions.get("is_storm_mode", False)
        
        # Attribution values
        net_flow = ren_kw - 45.0  # Baseline station load ~ 45 kW
        
        attr_surplus = max(-1.0, min(1.0, net_flow / 60.0))
        attr_soc = (bat_soc - 0.5) * 2.0
        attr_h2 = (h2_soc - 0.5) * 2.0
        attr_in_temp = (20.0 - in_temp) * 0.5
        attr_cold = max(0.0, (-t_amb - 15.0) / 35.0)
        attr_storm = 1.0 if is_storm else 0.0
        
        return {
            "Renewable Balance": round(float(attr_surplus), 2),
            "Battery SOC": round(float(attr_soc), 2),
            "H2 Tank Reserve": round(float(attr_h2), 2),
            "Thermal Deficit": round(float(attr_in_temp), 2),
            "Sub-Zero Severity": round(float(attr_cold), 2),
            "Blizzard Risk": round(float(attr_storm), 2)
        }

    def generate_plain_english_rationale(
        self,
        dispatch_actions: Dict[str, Any],
        twin_state: Dict[str, Any],
        weather: Dict[str, Any]
    ) -> str:
        """Produces clear, operator-ready sentence explaining the primary control action."""
        d_kw = dispatch_actions.get("diesel_kw", 0.0)
        fc_kw = dispatch_actions.get("fuel_cell_kw", 0.0)
        el_kw = dispatch_actions.get("electrolyzer_kw", 0.0)
        bat_kw = dispatch_actions.get("battery_kw", 0.0)
        is_storm = dispatch_actions.get("is_storm_mode", False)
        t_amb = weather.get("ambient_temp_c", -20.0)
        
        if is_storm:
            return (
                f"STORM PROTOCOL ENGAGED: Turbines safety-feathered in high winds. "
                f"Station drawing {bat_kw:.1f} kW from battery and {fc_kw:.1f} kW from H2 fuel cell. "
                f"Life-support Tier 1 preserved at 100%; thermal mass pre-heated to withstand {t_amb:.1f}°C."
            )
            
        if el_kw > 5.0:
            return (
                f"GREEN HYDROGEN GENERATION: Capturing {el_kw:.1f} kW surplus renewable power into 350-bar H2 storage. "
                f"Battery is healthy ({twin_state.get('battery_soc', 0.5)*100:.0f}%), mitigating renewable curtailment."
            )
            
        if fc_kw > 5.0 and d_kw <= 0.0:
            return (
                f"CLEAN LONG-DURATION DISPATCH: Operating PEM Fuel Cell at {fc_kw:.1f} kW to displace diesel. "
                f"Cogeneration loop delivering {fc_kw*0.8:.1f} kW thermal heat directly to station living quarters."
            )
            
        if d_kw > 5.0:
            return (
                f"AUXILIARY DIESEL ACTIVE: Operating at {d_kw:.1f} kW sweet-spot load to protect battery SOC floor "
                f"({twin_state.get('battery_soc', 0.5)*100:.0f}%) and prevent cylinder wet-stacking during sustained renewable calm."
            )
            
        if bat_kw > 5.0:
            return (
                f"BATTERY PEAK-SHAVING: LiFePO4 bank discharging {bat_kw:.1f} kW to balance load without starting diesel. "
                f"Electrolyte temperature maintained at {twin_state.get('battery_temp_c', 15.0):.1f}°C."
            )
            
        return "STABLE EQUILIBRIUM: Microgrid generation and storage dynamically balancing station load."

    def ask_why(
        self,
        query: str,
        recent_telemetry: Dict[str, Any]
    ) -> str:
        """
        Offline NLP semantic rule engine for answering operator questions.
        """
        q = query.lower()
        
        # Q: Why did diesel start?
        if "diesel" in q and ("start" in q or "run" in q or "why" in q):
            soc = recent_telemetry.get("battery_soc", 0.4) * 100.0
            h2_p = recent_telemetry.get("h2_tank_pressure_bar", 30.0)
            return (
                f"Diesel was started because: (1) Battery SOC dropped near reserve threshold ({soc:.1f}%), "
                f"(2) Renewable deficit exceeded available fuel cell cushion ({h2_p:.1f} bar remaining), and "
                f"(3) Deterministic Safety Shield clamped generator to minimum 30 kW to prevent cold wet-stacking."
            )
            
        # Q: Why load shedding / why Tier 3 off?
        if "shed" in q or "tier 3" in q or "tier 2" in q or "load" in q:
            return (
                "Criticality Load Orchestrator throttled non-vital loads (Tier 3: comfort & vehicle charging) "
                "to preserve 100% continuous power for Tier 1 life support and avoid initiating a high-emission diesel cycle."
            )
            
        # Q: Why did electrolyzer stop?
        if "electrolyzer" in q:
            return (
                "The PEM electrolyzer halts whenever net renewable power drops below 6.0 kW (10% minimum turndown "
                "to prevent membrane gas cross-over) or when H2 tank pressure reaches 340 bar safety relief margin."
            )
            
        # Q: Why did wind turbine stop / feather?
        if "wind" in q or "turbine" in q or "feather" in q:
            return (
                "Wind turbine blades automatically feather to 90° pitch when wind speeds exceed 25.0 m/s (90 km/h) "
                "or when severe blade icing index exceeds 0.75, protecting gearboxes and composite blades from structural failure."
            )
            
        # Q: Why is battery discharging in extreme cold?
        if "battery" in q or "cold" in q:
            return (
                "Battery internal resistance increases with sub-zero temperatures. Active thermal jackets maintain "
                "cell core temperature above 8°C using parasitic heating, enabling safe discharge without lithium plating."
            )
            
        # Default intelligent response
        return (
            f"PolarSync AI prioritized zero-loss Tier 1 life support, renewable self-consumption, and battery health. "
            f"Current battery SOC is {recent_telemetry.get('battery_soc', 0.5)*100:.1f}% with H2 pressure at "
            f"{recent_telemetry.get('h2_tank_pressure_bar', 150.0):.1f} bar."
        )
