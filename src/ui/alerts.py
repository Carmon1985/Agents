import streamlit as st
from typing import List, Dict, Any
from datetime import datetime

def get_alert_color(level: str) -> str:
    """Return the color code for different alert levels."""
    colors = {
        "CRITICAL": "#FF4B4B",
        "WARNING": "#FFA500",
        "INFO": "#3366CC"
    }
    return colors.get(level, "#808080")

def format_metric_value(value: float, threshold: float) -> str:
    """Format the metric value and threshold for display."""
    return f"{value:.1f} (Threshold: {threshold:.1f})"

def display_alert_card(alert: Dict[str, Any]):
    """Display a single alert card with styling."""
    alert_color = get_alert_color(alert["level"])
    
    st.markdown(f"""
    <div style="
        border-left: 4px solid {alert_color};
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: white;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="
                    background-color: {alert_color};
                    color: white;
                    padding: 0.2rem 0.5rem;
                    border-radius: 3px;
                    font-size: 0.8rem;">
                    {alert["level"]}
                </span>
                <span style="margin-left: 0.5rem; font-weight: bold;">
                    {alert["metric"]}
                </span>
            </div>
            <div style="color: #666; font-size: 0.8rem;">
                {alert["timestamp"]}
            </div>
        </div>
        <div style="margin: 0.5rem 0;">
            {alert["message"]}
        </div>
        <div style="color: #666; font-size: 0.9rem;">
            Value: {format_metric_value(alert["value"], alert["threshold"])}
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_alerts_section(alerts: List[Dict[str, Any]]):
    """Display the alerts section with filtering and sorting options."""
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        level_filter = st.multiselect(
            "Filter by Level",
            options=["CRITICAL", "WARNING", "INFO"],
            default=["CRITICAL", "WARNING", "INFO"]
        )
    
    with col2:
        metric_filter = st.multiselect(
            "Filter by Metric",
            options=list(set(alert["metric"] for alert in alerts)),
            default=list(set(alert["metric"] for alert in alerts))
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Time (Newest First)", "Time (Oldest First)", "Level (High to Low)", "Level (Low to High)"],
            index=0
        )
    
    # Apply filters
    filtered_alerts = [
        alert for alert in alerts
        if alert["level"] in level_filter and
        alert["metric"] in metric_filter
    ]
    
    # Apply sorting
    if sort_by == "Time (Newest First)":
        filtered_alerts.sort(key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S"), reverse=True)
    elif sort_by == "Time (Oldest First)":
        filtered_alerts.sort(key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S"))
    elif sort_by == "Level (High to Low)":
        level_priority = {"CRITICAL": 3, "WARNING": 2, "INFO": 1}
        filtered_alerts.sort(key=lambda x: level_priority[x["level"]], reverse=True)
    else:  # Level (Low to High)
        level_priority = {"CRITICAL": 3, "WARNING": 2, "INFO": 1}
        filtered_alerts.sort(key=lambda x: level_priority[x["level"]])
    
    # Display alert count
    st.markdown(f"### Active Alerts ({len(filtered_alerts)})")
    
    if not filtered_alerts:
        st.info("No alerts match the selected filters.")
        return
    
    # Display alerts
    for alert in filtered_alerts:
        display_alert_card(alert) 