"""
PolarSync AI - Deterministic Safety Shield (Feature E)
Inviolable deterministic safety layer that intercepts, inspects, vetoes,
or clips any AI or optimization dispatch action before actuation.
Guarantees station survival, life-support continuity, and equipment integrity.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from backend.config import CONFIG


class VetoRecord:
    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        severity: str,
        original_val: Any,
        shielded_val: Any,
        reason: str,
        step_idx: int = 0
    ):
        self.timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.step_idx = step_idx
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity  # 'CRITICAL', 'WARNING', 'INFO'
        self.original_val = original_val
        self.shielded_val = shielded_val
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "step_idx": self.step_idx,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "original_val": str(self.original_val),
            "shielded_val": str(self.shielded_val),
            "reason": self.reason
        }


class PolarSafetyShield:
    def __init__(self, max_audit_records: int = 200):
        self.max_audit_records = max_audit_records
        self.audit_log: List[VetoRecord] = []
        self.total_vetoes_count = 0
        self.last_diesel_start_step = -999
        self.diesel_running = False

    def log_veto(
        self,
        rule_id: str,
        rule_name: str,
        severity: str,
        original_val: Any,
        shielded_val: Any,
        reason: str,
        step_idx: int = 0
    ):
        self.total_vetoes_count += 1
        record = VetoRecord(
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            original_val=original_val,
            shielded_val=shielded_val,
            reason=reason,
            step_idx=step_idx
        )
        self.audit_log.insert(0, record)
        if len(self.audit_log) > self.max_audit_records:
            self.audit_log.pop()

    def filter_actions(
        self,
        proposed_actions: Dict[str, float],
        twin_state: Dict[str, Any],
        weather: Dict[str, Any],
        storm_mode: bool = False,
        step_idx: int = 0
    ) -> Dict[str, float]:
        """
        Deterministic safety pass. Inspects all proposed dispatch setpoints.
        Returns guaranteed safe actions with audit logging of any vetoes.
        """
        safe_actions = dict(proposed_actions)
        
        # -------------------------------------------------------------
        # RULE 01: Tier 1 Life Support Inviolability (CRITICAL)
        # -------------------------------------------------------------
        t1_ratio = safe_actions.get("tier1_served_ratio", 1.0)
        if t1_ratio < 0.999:
            safe_actions["tier1_served_ratio"] = 1.0
            self.log_veto(
                rule_id="RULE_01",
                rule_name="Tier 1 Life Support Inviolable",
                severity="CRITICAL",
                original_val=f"{t1_ratio*100:.1f}%",
                shielded_val="100.0%",
                reason="AI attempted to curtail Tier 1 habitat life support or comms. Life support cannot be shed under any circumstance.",
                step_idx=step_idx
            )
            
        # -------------------------------------------------------------
        # RULE 02: Battery SOC Floor & Storm Cushion (CRITICAL)
        # -------------------------------------------------------------
        bat_kw = safe_actions.get("battery_kw", 0.0)
        current_soc = twin_state.get("battery_soc", 0.5)
        min_allowed_soc = CONFIG.battery_storm_min_soc if storm_mode else CONFIG.battery_min_soc
        
        if bat_kw > 0.0:  # Discharging
            # Check if discharging at this rate would breach floor
            eff_cap = twin_state.get("effective_capacity_kwh", CONFIG.battery_nominal_kwh)
            projected_soc = current_soc - (bat_kw * 1.0) / max(1.0, eff_cap)
            if projected_soc < min_allowed_soc:
                max_safe_discharge_kw = max(0.0, (current_soc - min_allowed_soc) * eff_cap)
                clipped_shortfall = bat_kw - max_safe_discharge_kw
                safe_actions["battery_kw"] = max_safe_discharge_kw
                
                # Critical safety guarantee: If battery discharge is restricted, route shortfall to diesel
                cur_diesel = safe_actions.get("diesel_kw", 0.0)
                safe_actions["diesel_kw"] = max(cur_diesel, min(CONFIG.diesel_rated_kw, cur_diesel + clipped_shortfall))
                
                self.log_veto(
                    rule_id="RULE_02",
                    rule_name="Battery Cryogenic SOC Floor",
                    severity="CRITICAL" if storm_mode else "WARNING",
                    original_val=f"Bat: {bat_kw:.1f} kW",
                    shielded_val=f"Bat: {max_safe_discharge_kw:.1f} kW, Diesel: {safe_actions['diesel_kw']:.1f} kW",
                    reason=f"Discharge clipped to prevent SOC breaching {min_allowed_soc*100:.0f}% minimum reserve floor (Current SOC: {current_soc*100:.1f}%). Routed shortfall to diesel.",
                    step_idx=step_idx
                )

        # -------------------------------------------------------------
        # RULE 03: H2 Tank High-Pressure Safety Limit (CRITICAL)
        # -------------------------------------------------------------
        el_kw = safe_actions.get("electrolyzer_kw", 0.0)
        h2_pressure = twin_state.get("h2_tank_pressure_bar", 200.0)
        h2_soc = twin_state.get("h2_tank_soc", 0.6)
        
        if el_kw > 0.0 and (h2_pressure >= CONFIG.h2_tank_max_bar - 10.0 or h2_soc >= 0.98):
            safe_actions["electrolyzer_kw"] = 0.0
            self.log_veto(
                rule_id="RULE_03",
                rule_name="H2 Overpressure Protection",
                severity="CRITICAL",
                original_val=f"{el_kw:.1f} kW",
                shielded_val="0.0 kW",
                reason=f"Electrolyzer tripped: H2 tank pressure ({h2_pressure:.1f} bar) within safety relief margin of {CONFIG.h2_tank_max_bar} bar.",
                step_idx=step_idx
            )

        # -------------------------------------------------------------
        # RULE 04: H2 Tank Cushion / Minimum Pressure (WARNING)
        # -------------------------------------------------------------
        fc_kw = safe_actions.get("fuel_cell_kw", 0.0)
        if fc_kw > 0.0 and h2_pressure <= CONFIG.h2_tank_min_bar + 2.0:
            safe_actions["fuel_cell_kw"] = 0.0
            self.log_veto(
                rule_id="RULE_04",
                rule_name="H2 Low Cushion Protection",
                severity="WARNING",
                original_val=f"{fc_kw:.1f} kW",
                shielded_val="0.0 kW",
                reason=f"Fuel cell disabled: H2 tank pressure ({h2_pressure:.1f} bar) at minimum seal cushion of {CONFIG.h2_tank_min_bar} bar.",
                step_idx=step_idx
            )

        # -------------------------------------------------------------
        # RULE 05: Habitat Anti-Freezing & Minimum Heat (CRITICAL)
        # -------------------------------------------------------------
        indoor_temp = twin_state.get("indoor_temp_c", 20.0)
        hp_kw = safe_actions.get("heat_pump_kw", 10.0)
        
        if indoor_temp < CONFIG.station_min_safe_temp_c + 1.0 and hp_kw < 16.0:
            # Force heat pump or thermal heating to protect station habitat and pipes
            safe_actions["heat_pump_kw"] = 22.0
            self.log_veto(
                rule_id="RULE_05",
                rule_name="Habitat Freeze Protection",
                severity="CRITICAL",
                original_val=f"{hp_kw:.1f} kW",
                shielded_val="22.0 kW",
                reason=f"Station indoor temperature dropped to {indoor_temp:.1f}°C (Threshold: {CONFIG.station_min_safe_temp_c}°C). Forced maximum heat pump heating.",
                step_idx=step_idx
            )

        # -------------------------------------------------------------
        # RULE 06: Diesel Wet-Stacking & Minimum Runtime
        # -------------------------------------------------------------
        diesel_kw = safe_actions.get("diesel_kw", 0.0)
        min_load = CONFIG.diesel_rated_kw * CONFIG.diesel_min_load_ratio
        
        if 0.0 < diesel_kw < min_load:
            safe_actions["diesel_kw"] = min_load
            self.log_veto(
                rule_id="RULE_06",
                rule_name="Genset Anti-Wet-Stacking Clamp",
                severity="WARNING",
                original_val=f"{diesel_kw:.1f} kW",
                shielded_val=f"{min_load:.1f} kW",
                reason=f"Diesel genset load below 30% ({min_load:.0f} kW) causes unburned fuel deposition and wet stacking in polar cold. Boosted to minimum floor.",
                step_idx=step_idx
            )
            
        # Update running state
        if safe_actions.get("diesel_kw", 0.0) > 5.0:
            if not self.diesel_running:
                self.last_diesel_start_step = step_idx
                self.diesel_running = True
        else:
            self.diesel_running = False

        return safe_actions
