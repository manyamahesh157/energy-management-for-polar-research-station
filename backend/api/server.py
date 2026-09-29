"""
PolarSync AI - FastAPI Ingestion & Edge Server
Provides REST endpoints and WebSocket telemetry streaming for all microgrid components,
Safety Shield, Forecaster, Survival Planner, Chaos Injector, and XAI Copilot.
"""

import os
import json
import asyncio
import pandas as pd
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import CONFIG
from backend.twin.station_twin import PolarStationTwin
from backend.twin.calibrator import OnlineTwinCalibrator
from backend.safety.shield import PolarSafetyShield
from backend.controllers.hierarchical import PolarSyncHierarchicalController
from backend.controllers.rule_based import RuleBasedDieselController
from backend.forecasting.conformal_forecaster import FORECASTER
from backend.analytics.survival_planner import PolarSurvivalPlanner
from backend.analytics.logistics import PolarLogisticsOptimizer
from backend.analytics.ledger import CarbonCostLedger
from backend.xai.copilot import ExplainabilityCopilot
from backend.chaos.fault_injector import ChaosFaultInjector
from backend.maintenance.predictive import PolarPredictiveMaintenance
from backend.federated.fed_learning import FederatedStationOrchestrator
from backend.hil.mqtt_bridge import HIL_BRIDGE

app = FastAPI(
    title="PolarSync AI - Polar Microgrid Edge Engine",
    description="SIH26061: AI-Driven Smart Energy Management System for Polar Research Stations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Global Edge Engine State
# -------------------------------------------------------------
DATA_PATH = "backend/data/polar_year_8760.csv"
if os.path.exists(DATA_PATH):
    WEATHER_DF = pd.read_csv(DATA_PATH)
else:
    from backend.data_generator import generate_polar_year
    WEATHER_DF = generate_polar_year(DATA_PATH)

CURRENT_STEP = 3200  # Start around Antarctic mid-autumn / winter transition
TWIN = PolarStationTwin()
CALIBRATOR = OnlineTwinCalibrator()
SHIELD = PolarSafetyShield()
HIER_CONTROLLER = PolarSyncHierarchicalController(shield=SHIELD)
RULE_CONTROLLER = RuleBasedDieselController()
SURVIVAL_PLANNER = PolarSurvivalPlanner(n_scenarios=200)
LOGISTICS_OPT = PolarLogisticsOptimizer()
LEDGER = CarbonCostLedger()
COPILOT = ExplainabilityCopilot()
CHAOS = ChaosFaultInjector()
PRED_MAINT = PolarPredictiveMaintenance()
FED_ORCH = FederatedStationOrchestrator()

MANUAL_STORM_ACTIVE = False
MANUAL_STORM_SEVERITY = 3.0
LATEST_SNAPSHOT = {}


class ChaosToggleRequest(BaseModel):
    fault_name: str
    enabled: bool


class AskWhyRequest(BaseModel):
    query: str


class StepRequest(BaseModel):
    storm_active: Optional[bool] = False
    storm_severity: Optional[float] = 3.0
    fuel_price_inr: Optional[float] = 320.0


@app.get("/api/health")
def get_health():
    return {
        "status": "online",
        "station": CONFIG.station_name,
        "coordinates": f"{CONFIG.latitude}°, {CONFIG.longitude}°",
        "edge_mode": CHAOS.state.satellite_outage,
        "step": CURRENT_STEP
    }


@app.post("/api/step")
def advance_step(req: StepRequest = None):
    global CURRENT_STEP, LATEST_SNAPSHOT, MANUAL_STORM_ACTIVE, MANUAL_STORM_SEVERITY
    
    if req:
        MANUAL_STORM_ACTIVE = req.storm_active
        MANUAL_STORM_SEVERITY = req.storm_severity
        if req.fuel_price_inr:
            LEDGER.fuel_price_inr_per_l = req.fuel_price_inr
            
    CURRENT_STEP = (CURRENT_STEP + 1) % len(WEATHER_DF)
    raw_weather = WEATHER_DF.iloc[CURRENT_STEP].to_dict()
    
    # 1. State snapshot from previous step
    raw_twin_state = {
        "pv_kw": TWIN.renewables.calculate_pv_power(
            ghi_w_m2=raw_weather["ghi_w_m2"],
            ambient_temp_c=raw_weather["ambient_temp_c"],
            solar_elevation_deg=raw_weather["solar_elevation_deg"]
        )["pv_power_kw"],
        "wind_kw": TWIN.renewables.calculate_wind_power(
            wind_speed_ms=raw_weather["wind_speed_ms"],
            ambient_temp_c=raw_weather["ambient_temp_c"]
        )["wind_power_kw"],
        "battery_soc": TWIN.battery.soc,
        "battery_temp_c": TWIN.battery.cell_temp_c,
        "effective_capacity_kwh": TWIN.battery.get_effective_capacity(TWIN.battery.cell_temp_c),
        "h2_tank_soc": TWIN.hydrogen.soc,
        "h2_tank_pressure_bar": TWIN.hydrogen.pressure_bar,
        "indoor_temp_c": TWIN.thermal.indoor_temp_c
    }
    
    # 2. Chaos & Fault Injection
    weather, twin_state, diagnostics = CHAOS.apply_chaos(raw_weather, raw_twin_state)
    
    # 3. Forecast
    f_input = {
        "hour": CURRENT_STEP % 24,
        "day": (CURRENT_STEP // 24) + 1,
        "ambient_temp_c": weather["ambient_temp_c"],
        "wind_speed_ms": weather["wind_speed_ms"]
    }
    fc_bands = FORECASTER.forecast_24h(f_input)
    
    # 4. Hierarchical Controller Dispatch with Deterministic Safety Shield
    safe_actions = HIER_CONTROLLER.dispatch(
        twin_state=twin_state,
        weather=weather,
        forecast_24h=fc_bands,
        manual_storm_trigger=MANUAL_STORM_ACTIVE,
        step_idx=CURRENT_STEP
    )
    
    # 5. Baseline Dispatch for Comparison
    rule_actions = RULE_CONTROLLER.dispatch(twin_state=twin_state, weather=weather)
    
    # 6. Advance Twin
    step_res = TWIN.step(
        weather=weather,
        dispatch_actions=safe_actions,
        dt_hours=1.0,
        storm_mode=safe_actions["is_storm_mode"]
    )
    
    # 7. Self-Calibrating Twin Update (Feature C)
    calib_res = CALIBRATOR.update(
        measured_voltage_v=395.0 + 15.0 * step_res["battery_soc"],
        measured_current_a=(abs(step_res["battery_kw"]) * 1000.0) / 400.0,
        soc_estimate=step_res["battery_soc"],
        cell_temp_c=step_res["battery_temp_c"]
    )
    
    # 8. Carbon & Cost Ledger Update (Feature L)
    # Baseline fuel consumption ~ rule diesel output * 0.27
    baseline_liters = rule_actions["diesel_kw"] * CONFIG.diesel_l_per_kwh
    LEDGER.update_step(
        actual_liters_step=step_res["fuel_liters_step"],
        baseline_liters_step=baseline_liters
    )
    
    # 9. Predictive Maintenance Assessment (Feature I)
    vibration_proxy = 0.42 + (0.015 * weather["wind_speed_ms"]) + (0.35 if step_res["is_feathered"] else 0.0)
    cell_v_proxy = 1.82 + (0.003 * (step_res["electrolyzer_kw"] / 60.0) * 10.0)
    maint_res = PRED_MAINT.assess_health(
        turbine_vibration_g=vibration_proxy,
        electrolyzer_cell_v=cell_v_proxy,
        battery_r_int_mohm=calib_res["estimated_r_int_mohm"]
    )
    
    # 10. Explainability Copilot Rationale (Feature F)
    xai_sentence = COPILOT.generate_plain_english_rationale(safe_actions, step_res, weather)
    xai_shap = COPILOT.compute_feature_attributions(safe_actions, step_res, weather)
    
    # 11. HIL Bridge Telemetry Check (Feature K)
    active_telemetry = HIL_BRIDGE.get_active_telemetry(step_res)
    
    LATEST_SNAPSHOT = {
        "step": CURRENT_STEP,
        "hour_of_day": CURRENT_STEP % 24,
        "day_of_year": (CURRENT_STEP // 24) + 1,
        "weather": weather,
        "telemetry": active_telemetry,
        "diagnostics": diagnostics,
        "calibrator": calib_res,
        "maint": maint_res,
        "actions": safe_actions,
        "xai_sentence": xai_sentence,
        "xai_shap": xai_shap,
        "ledger": LEDGER.get_ledger_metrics(),
        "recent_vetoes": [v.to_dict() for v in SHIELD.audit_log[:5]]
    }
    
    return LATEST_SNAPSHOT


@app.get("/api/telemetry")
def get_telemetry():
    global LATEST_SNAPSHOT
    if not LATEST_SNAPSHOT:
        advance_step()
    return LATEST_SNAPSHOT


@app.get("/api/survival")
def get_survival_analysis():
    global LATEST_SNAPSHOT
    if not LATEST_SNAPSHOT:
        advance_step()
    bat_kwh = LATEST_SNAPSHOT["telemetry"].get("battery_soc", 0.5) * CONFIG.battery_nominal_kwh
    h2_kg = LATEST_SNAPSHOT["telemetry"].get("h2_stored_kg", 200.0)
    res = SURVIVAL_PLANNER.evaluate_survival(
        current_battery_kwh=bat_kwh,
        current_h2_kg=h2_kg,
        diesel_stock_liters=65000.0,
        current_day=LATEST_SNAPSHOT["day_of_year"]
    )
    return res


@app.post("/api/chaos/toggle")
def toggle_chaos(req: ChaosToggleRequest):
    return CHAOS.set_fault(req.fault_name, req.enabled)


@app.post("/api/chaos/reset")
def reset_chaos():
    CHAOS.reset_all()
    return {"status": "success", "message": "All faults cleared"}


@app.post("/api/xai/ask")
def ask_copilot(req: AskWhyRequest):
    global LATEST_SNAPSHOT
    if not LATEST_SNAPSHOT:
        advance_step()
    answer = COPILOT.ask_why(req.query, LATEST_SNAPSHOT.get("telemetry", {}))
    return {"query": req.query, "answer": answer}


@app.post("/api/federated/sync")
def federated_sync():
    return FED_ORCH.run_federated_round()


@app.post("/api/hil/toggle")
def toggle_hil(use_real: bool = Query(...)):
    HIL_BRIDGE.set_mode(use_real)
    return {"status": "success", "use_real_hardware": use_real}


@app.get("/api/benchmark")
def get_benchmark():
    from backend.controllers.benchmark import run_annual_benchmark
    return run_annual_benchmark()


@app.websocket("/ws/live")
async def websocket_live_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            snapshot = advance_step()
            await websocket.send_json(snapshot)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
