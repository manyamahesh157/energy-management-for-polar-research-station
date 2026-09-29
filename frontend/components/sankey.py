"""
PolarSync AI - Dynamic Power Flow Sankey Component
Visualizes instantaneous power distribution across generation, microgrid bus,
short-term/long-term storage, and tiered loads using Plotly.
"""

from typing import Dict, Any
import plotly.graph_objects as go


def create_power_flow_sankey(telemetry: Dict[str, Any], theme: str = "dark") -> go.Figure:
    """
    Constructs an interactive Plotly Sankey diagram representing power flow.
    """
    pv_kw = max(0.0, float(telemetry.get("pv_kw", 0.0)))
    wind_kw = max(0.0, float(telemetry.get("wind_kw", 0.0)))
    bat_kw = float(telemetry.get("battery_kw", 0.0))
    fc_kw = max(0.0, float(telemetry.get("fuel_cell_kw", 0.0)))
    diesel_kw = max(0.0, float(telemetry.get("diesel_kw", 0.0)))
    
    t1_kw = max(0.0, float(telemetry.get("t1_served_kw", 18.0)))
    t2_kw = max(0.0, float(telemetry.get("t2_served_kw", 14.0)))
    t3_kw = max(0.0, float(telemetry.get("t3_served_kw", 10.0)))
    hp_kw = max(0.0, float(telemetry.get("heat_pump_kw", 12.0)))
    el_kw = max(0.0, float(telemetry.get("electrolyzer_kw", 0.0)))
    curtail_kw = max(0.0, float(telemetry.get("curtailment_kw", 0.0)))
    
    # Battery discharge is a source; battery charge is a sink
    bat_discharge_kw = max(0.0, bat_kw) if bat_kw > 0.0 else 0.0
    bat_charge_kw = abs(bat_kw) if bat_kw < 0.0 else 0.0

    # Node Index Mapping
    # Sources: 0=Solar PV, 1=Wind Turbines, 2=Battery Discharge, 3=Fuel Cell, 4=Diesel Backup
    # Bus: 5=Microgrid Bus
    # Sinks: 6=Tier 1 Life Support, 7=Tier 2 Science Lab, 8=Tier 3 Comfort & Fleet,
    #        9=Heat Pump Heating, 10=Battery Charging, 11=PEM Electrolyzer, 12=Curtailment
    labels = [
        f"Solar PV ({pv_kw:.1f} kW)",
        f"Wind Turbines ({wind_kw:.1f} kW)",
        f"Battery Disch ({bat_discharge_kw:.1f} kW)",
        f"PEM Fuel Cell ({fc_kw:.1f} kW)",
        f"Diesel Genset ({diesel_kw:.1f} kW)",
        "Microgrid Bus (400V)",
        f"Tier 1 Life Support ({t1_kw:.1f} kW)",
        f"Tier 2 Science ({t2_kw:.1f} kW)",
        f"Tier 3 Comfort/EV ({t3_kw:.1f} kW)",
        f"Heat Pump Heating ({hp_kw:.1f} kW)",
        f"Battery Charging ({bat_charge_kw:.1f} kW)",
        f"Electrolyzer H2 ({el_kw:.1f} kW)",
        f"Curtailment ({curtail_kw:.1f} kW)"
    ]

    source_indices = []
    target_indices = []
    values = []
    link_colors = []

    # Sources -> Bus (5)
    if pv_kw > 0.1:
        source_indices.append(0); target_indices.append(5); values.append(pv_kw)
        link_colors.append("rgba(251, 191, 36, 0.55)")  # Amber
    if wind_kw > 0.1:
        source_indices.append(1); target_indices.append(5); values.append(wind_kw)
        link_colors.append("rgba(56, 189, 248, 0.55)")  # Sky blue
    if bat_discharge_kw > 0.1:
        source_indices.append(2); target_indices.append(5); values.append(bat_discharge_kw)
        link_colors.append("rgba(168, 85, 247, 0.55)")  # Purple
    if fc_kw > 0.1:
        source_indices.append(3); target_indices.append(5); values.append(fc_kw)
        link_colors.append("rgba(52, 211, 153, 0.55)")  # Emerald green
    if diesel_kw > 0.1:
        source_indices.append(4); target_indices.append(5); values.append(diesel_kw)
        link_colors.append("rgba(239, 68, 68, 0.55)")   # Red

    # Bus (5) -> Sinks
    if t1_kw > 0.1:
        source_indices.append(5); target_indices.append(6); values.append(t1_kw)
        link_colors.append("rgba(147, 51, 234, 0.55)")  # Deep purple
    if t2_kw > 0.1:
        source_indices.append(5); target_indices.append(7); values.append(t2_kw)
        link_colors.append("rgba(59, 130, 246, 0.55)")  # Blue
    if t3_kw > 0.1:
        source_indices.append(5); target_indices.append(8); values.append(t3_kw)
        link_colors.append("rgba(245, 158, 11, 0.55)")  # Orange
    if hp_kw > 0.1:
        source_indices.append(5); target_indices.append(9); values.append(hp_kw)
        link_colors.append("rgba(236, 72, 153, 0.55)")  # Pink
    if bat_charge_kw > 0.1:
        source_indices.append(5); target_indices.append(10); values.append(bat_charge_kw)
        link_colors.append("rgba(168, 85, 247, 0.55)")  # Purple
    if el_kw > 0.1:
        source_indices.append(5); target_indices.append(11); values.append(el_kw)
        link_colors.append("rgba(16, 185, 129, 0.55)")  # Green
    if curtail_kw > 0.1:
        source_indices.append(5); target_indices.append(12); values.append(curtail_kw)
        link_colors.append("rgba(156, 163, 175, 0.45)") # Gray

    # Default fallback flow if zero
    if not values:
        source_indices.append(1); target_indices.append(5); values.append(1.0); link_colors.append("rgba(56, 189, 248, 0.3)")
        source_indices.append(5); target_indices.append(6); values.append(1.0); link_colors.append("rgba(147, 51, 234, 0.3)")

    node_colors = [
        "#f59e0b", "#38bdf8", "#a855f7", "#10b981", "#ef4444",
        "#64748b",
        "#8b5cf6", "#3b82f6", "#f97316", "#ec4899", "#a855f7", "#059669", "#94a3b8"
    ]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=18,
            thickness=22,
            line=dict(color="#1e293b", width=1.5),
            label=labels,
            color=node_colors
        ),
        link=dict(
            source=source_indices,
            target=target_indices,
            value=values,
            color=link_colors
        )
    )])

    paper_bg = "#0f172a" if theme == "dark" else "#ffffff"
    font_color = "#f8fafc" if theme == "dark" else "#0f172a"

    fig.update_layout(
        title_text="<b>Real-Time Dynamic Microgrid Power Flow (kW)</b>",
        font=dict(size=12, color=font_color, family="Segoe UI, sans-serif"),
        paper_bgcolor=paper_bg,
        plot_bgcolor=paper_bg,
        margin=dict(l=20, r=20, t=45, b=20),
        height=360
    )
    return fig
