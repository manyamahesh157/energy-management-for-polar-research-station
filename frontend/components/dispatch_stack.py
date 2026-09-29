"""
PolarSync AI - 7-Day Dispatch Stack & Storage State Component
Visualizes:
1. 7-Day (168-hour) continuous dispatch stacked area chart
2. Multi-storage dynamics: Battery SOC %, H2 Pressure (bar), Indoor vs Ambient Temperature
3. 24h Conformal Forecast fan chart with calibrated quantile intervals (q10, q50, q90).
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any


def create_7day_dispatch_stack(df_history: pd.DataFrame, theme: str = "dark") -> go.Figure:
    """
    Renders 7-day stacked generation dispatch meeting demand.
    """
    fig = go.Figure()
    
    x = df_history["hour"] if "hour" in df_history.columns else np.arange(len(df_history))
    
    # Generation layers
    fig.add_trace(go.Scatter(
        x=x, y=df_history.get("pv_kw", 0.0),
        mode='lines', stackgroup='one', name='Solar PV',
        line=dict(width=0.5, color='#f59e0b'), fillcolor='rgba(245, 158, 11, 0.7)'
    ))
    fig.add_trace(go.Scatter(
        x=x, y=df_history.get("wind_kw", 0.0),
        mode='lines', stackgroup='one', name='Wind Turbines',
        line=dict(width=0.5, color='#38bdf8'), fillcolor='rgba(56, 189, 248, 0.7)'
    ))
    fig.add_trace(go.Scatter(
        x=x, y=df_history.get("fuel_cell_kw", 0.0),
        mode='lines', stackgroup='one', name='PEM Fuel Cell (H2)',
        line=dict(width=0.5, color='#10b981'), fillcolor='rgba(16, 185, 129, 0.7)'
    ))
    
    # Battery discharge (positive only)
    bat_discharge = np.maximum(0.0, df_history.get("battery_kw", 0.0))
    fig.add_trace(go.Scatter(
        x=x, y=bat_discharge,
        mode='lines', stackgroup='one', name='Battery Discharge',
        line=dict(width=0.5, color='#a855f7'), fillcolor='rgba(168, 85, 247, 0.7)'
    ))
    fig.add_trace(go.Scatter(
        x=x, y=df_history.get("diesel_kw", 0.0),
        mode='lines', stackgroup='one', name='Diesel Genset',
        line=dict(width=0.5, color='#ef4444'), fillcolor='rgba(239, 68, 68, 0.75)'
    ))
    
    # Total station load line overlay
    total_load = (
        df_history.get("tier1_load_kw", 18.0) +
        df_history.get("tier2_load_kw", 14.0) +
        df_history.get("tier3_load_kw", 10.0) +
        df_history.get("heat_pump_kw", 12.0)
    )
    fig.add_trace(go.Scatter(
        x=x, y=total_load,
        mode='lines', name='Total Station Demand (kW)',
        line=dict(color='#ffffff', width=2.5, dash='dash')
    ))

    paper_bg = "#0f172a" if theme == "dark" else "#ffffff"
    font_color = "#f8fafc" if theme == "dark" else "#0f172a"

    fig.update_layout(
        title="<b>7-Day Continuous Microgrid Dispatch Stack (168 Hours)</b>",
        xaxis=dict(title="Polar Year Hour", gridcolor="#1e293b", color=font_color),
        yaxis=dict(title="Power (kW)", gridcolor="#1e293b", color=font_color),
        paper_bgcolor=paper_bg,
        plot_bgcolor=paper_bg,
        font=dict(color=font_color, family="Segoe UI, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=55, b=35),
        height=380
    )
    return fig


def create_storage_state_monitors(df_history: pd.DataFrame, theme: str = "dark") -> go.Figure:
    """
    Renders multi-subplot storage status: Battery SOC, H2 Tank Pressure, Building Temp.
    """
    x = df_history["hour"] if "hour" in df_history.columns else np.arange(len(df_history))
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Battery Bank State of Charge (SOC %)",
            "Hydrogen Storage Tank Pressure (bar)",
            "Station Indoor vs. Ambient Temperature (°C)"
        )
    )
    
    # 1. Battery SOC
    soc_pct = df_history.get("battery_soc", 0.5) * 100.0
    fig.add_trace(go.Scatter(
        x=x, y=soc_pct, mode='lines', name='Battery SOC (%)',
        line=dict(color='#a855f7', width=2.5), fill='tozeroy', fillcolor='rgba(168, 85, 247, 0.2)'
    ), row=1, col=1)
    # Add 20% floor reference line
    fig.add_hline(y=20.0, line_dash="dash", line_color="#ef4444", annotation_text="Safety Floor (20%)", row=1, col=1)

    # 2. H2 Pressure
    h2_press = df_history.get("h2_tank_pressure_bar", 180.0)
    fig.add_trace(go.Scatter(
        x=x, y=h2_press, mode='lines', name='H2 Pressure (bar)',
        line=dict(color='#10b981', width=2.5), fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.2)'
    ), row=2, col=1)
    fig.add_hline(y=340.0, line_dash="dash", line_color="#ef4444", annotation_text="Safety Relief (340 bar)", row=2, col=1)

    # 3. Temperatures
    t_in = df_history.get("indoor_temp_c", 20.0)
    t_amb = df_history.get("ambient_temp_c", -25.0)
    fig.add_trace(go.Scatter(
        x=x, y=t_in, mode='lines', name='Indoor Habitat Temp (°C)',
        line=dict(color='#38bdf8', width=2.5)
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=x, y=t_amb, mode='lines', name='Outside Ambient Temp (°C)',
        line=dict(color='#64748b', width=1.5, dash='dot')
    ), row=3, col=1)
    fig.add_hline(y=16.0, line_dash="dash", line_color="#ef4444", annotation_text="Habitat Safety Floor (16°C)", row=3, col=1)

    paper_bg = "#0f172a" if theme == "dark" else "#ffffff"
    font_color = "#f8fafc" if theme == "dark" else "#0f172a"

    fig.update_layout(
        paper_bgcolor=paper_bg,
        plot_bgcolor=paper_bg,
        font=dict(color=font_color, family="Segoe UI, sans-serif"),
        height=520,
        margin=dict(l=40, r=20, t=40, b=30),
        showlegend=False
    )
    fig.update_xaxes(gridcolor="#1e293b", color=font_color)
    fig.update_yaxes(gridcolor="#1e293b", color=font_color)
    return fig


def create_conformal_forecast_chart(fc_data: Dict[str, Any], target_name: str = "total_load_kw", theme: str = "dark") -> go.Figure:
    """
    Renders 24h Conformal Prediction Interval Fan Chart (q10 - q50 - q90).
    """
    fig = go.Figure()
    if target_name not in fc_data:
        return fig
        
    bands = fc_data[target_name]
    steps = np.arange(1, 25)
    
    q10 = bands["lower_q10"]
    q50 = bands["median_q50"]
    q90 = bands["upper_q90"]
    
    # Upper bound (invisible line)
    fig.add_trace(go.Scatter(
        x=steps, y=q90, mode='lines', line=dict(width=0),
        showlegend=False, name='Upper Bound (q90)'
    ))
    # Lower bound with fill to upper bound -> Conformal 90% Confidence Band
    fig.add_trace(go.Scatter(
        x=steps, y=q10, mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(56, 189, 248, 0.25)',
        name='90% Conformal Prediction Interval'
    ))
    # Median line
    fig.add_trace(go.Scatter(
        x=steps, y=q50, mode='lines+markers',
        line=dict(color='#38bdf8', width=2.5),
        name='Median Forecast (q50)'
    ))

    paper_bg = "#0f172a" if theme == "dark" else "#ffffff"
    font_color = "#f8fafc" if theme == "dark" else "#0f172a"
    
    display_titles = {
        "total_load_kw": "24-Hour Station Electrical Load Forecast (kW)",
        "wind_speed_ms": "24-Hour Polar Wind Speed Forecast (m/s)",
        "ghi_w_m2": "24-Hour Solar Irradiance Forecast (W/m²)",
        "ambient_temp_c": "24-Hour Ambient Temperature Forecast (°C)"
    }

    fig.update_layout(
        title=f"<b>{display_titles.get(target_name, target_name)}</b>",
        xaxis=dict(title="Hours Ahead (t + k)", gridcolor="#1e293b", color=font_color),
        yaxis=dict(title="Forecast Value", gridcolor="#1e293b", color=font_color),
        paper_bgcolor=paper_bg,
        plot_bgcolor=paper_bg,
        font=dict(color=font_color, family="Segoe UI, sans-serif"),
        margin=dict(l=40, r=20, t=45, b=35),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig
