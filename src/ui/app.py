import streamlit as st
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.ui.alerts import display_alerts_section
from src.ui.recommendations import display_recommendations_section

# Page configuration
st.set_page_config(
    page_title="Resource Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 2rem;
        color: #2E59D9;
        text-align: center;
    }
    .metric-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .metric-label {
        color: #666;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Header
    st.markdown('<h1 class="main-header">Resource Monitoring Dashboard</h1>',
                unsafe_allow_html=True)
    
    # Time range selector
    col1, col2 = st.columns(2)
    with col1:
        time_range = st.selectbox(
            "Time Range",
            options=["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Custom"],
            index=0
        )
    
    with col2:
        if time_range == "Custom":
            end_date = st.date_input("End Date", datetime.now())
            start_date = st.date_input(
                "Start Date",
                end_date - timedelta(days=7)
            )
        else:
            end_date = datetime.now()
            days_map = {
                "Last 24 Hours": 1,
                "Last 7 Days": 7,
                "Last 30 Days": 30
            }
            start_date = end_date - timedelta(days=days_map[time_range])
    
    # Summary metrics
    st.markdown("### Summary Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Current Utilization</div>
            <div class="metric-value">85%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Active Alerts</div>
            <div class="metric-value">5</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Pending Actions</div>
            <div class="metric-value">3</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Efficiency Score</div>
            <div class="metric-value">92</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Tabs for Alerts and Recommendations
    tab1, tab2 = st.tabs(["📊 Alerts", "💡 Recommendations"])
    
    with tab1:
        # Sample alerts data - replace with actual data
        alerts = [
            {
                "level": "CRITICAL",
                "message": "High resource utilization detected",
                "metric": "CPU Usage",
                "value": 95.5,
                "threshold": 90.0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "level": "WARNING",
                "message": "Memory usage approaching threshold",
                "metric": "Memory",
                "value": 82.3,
                "threshold": 85.0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        display_alerts_section(alerts)
    
    with tab2:
        # Sample recommendations data - replace with actual data
        recommendations = [
            {
                "category": "Resource Optimization",
                "title": "Optimize Resource Allocation",
                "description": "Current resource utilization patterns suggest potential for optimization",
                "impact_level": "High",
                "estimated_impact": {
                    "cost_savings": 5000.00,
                    "efficiency_gain": 15,
                    "time_savings": 20
                },
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "category": "Cost Reduction",
                "title": "Cost Reduction Opportunity",
                "description": "Analysis shows potential cost savings in resource usage",
                "impact_level": "Medium",
                "estimated_impact": {
                    "cost_savings": 3000.00,
                    "efficiency_gain": 10,
                    "time_savings": 15
                },
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        display_recommendations_section(recommendations)

if __name__ == "__main__":
    main() 