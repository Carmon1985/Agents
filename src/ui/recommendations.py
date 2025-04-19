import streamlit as st
from typing import List, Dict, Any
from datetime import datetime

def get_category_icon(category: str) -> str:
    """Return the appropriate icon for the recommendation category."""
    icons = {
        "Resource Optimization": "⚡",
        "Cost Reduction": "💰",
        "Performance": "🚀",
        "Capacity Planning": "📊",
        "Process Improvement": "🔄"
    }
    return icons.get(category, "📌")

def get_impact_color(impact: str) -> str:
    """Return the color code for different impact levels."""
    colors = {
        "High": "#28a745",    # Green
        "Medium": "#ffc107",  # Yellow
        "Low": "#6c757d"      # Gray
    }
    return colors.get(impact, "#6c757d")

def format_estimated_impact(impact: Dict[str, Any]) -> str:
    """Format the estimated impact details."""
    impact_text = []
    if "cost_savings" in impact:
        impact_text.append(f"Cost Savings: ${impact['cost_savings']:,.2f}")
    if "efficiency_gain" in impact:
        impact_text.append(f"Efficiency Gain: {impact['efficiency_gain']}%")
    if "time_savings" in impact:
        impact_text.append(f"Time Savings: {impact['time_savings']} hours/month")
    return " | ".join(impact_text) if impact_text else "Impact details not available"

def display_recommendation_card(recommendation: Dict[str, Any]):
    """Display a single recommendation card with styling."""
    impact_color = get_impact_color(recommendation["impact_level"])
    category_icon = get_category_icon(recommendation["category"])
    
    st.markdown(f"""
    <div style="
        border: 1px solid #e0e0e0;
        padding: 1.5rem;
        margin: 1rem 0;
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 1.2rem; margin-right: 0.5rem;">
                    {category_icon}
                </span>
                <span style="font-weight: bold; font-size: 1.1rem;">
                    {recommendation["category"]}
                </span>
            </div>
            <div>
                <span style="
                    background-color: {impact_color};
                    color: white;
                    padding: 0.2rem 0.8rem;
                    border-radius: 15px;
                    font-size: 0.8rem;">
                    {recommendation["impact_level"]} Impact
                </span>
            </div>
        </div>
        <div style="margin: 1rem 0;">
            <h4 style="margin: 0 0 0.5rem 0;">{recommendation["title"]}</h4>
            <p style="color: #666; margin: 0.5rem 0;">{recommendation["description"]}</p>
        </div>
        <div style="
            background-color: #f8f9fa;
            padding: 0.8rem;
            border-radius: 4px;
            margin: 0.5rem 0;">
            <strong>Estimated Impact:</strong><br>
            {format_estimated_impact(recommendation["estimated_impact"])}
        </div>
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
            padding-top: 0.5rem;
            border-top: 1px solid #e0e0e0;">
            <div style="color: #666; font-size: 0.9rem;">
                Generated: {recommendation["timestamp"]}
            </div>
            <div>
                <button style="
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                    cursor: pointer;">
                    Implement
                </button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_recommendations_section(recommendations: List[Dict[str, Any]]):
    """Display the recommendations section with filtering and categorization."""
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        category_filter = st.multiselect(
            "Filter by Category",
            options=list(set(rec["category"] for rec in recommendations)),
            default=list(set(rec["category"] for rec in recommendations))
        )
    
    with col2:
        impact_filter = st.multiselect(
            "Filter by Impact",
            options=["High", "Medium", "Low"],
            default=["High", "Medium", "Low"]
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Impact (High to Low)", "Impact (Low to High)", "Time (Newest First)", "Time (Oldest First)"],
            index=0
        )
    
    # Apply filters
    filtered_recommendations = [
        rec for rec in recommendations
        if rec["category"] in category_filter and
        rec["impact_level"] in impact_filter
    ]
    
    # Apply sorting
    if sort_by == "Impact (High to Low)":
        impact_priority = {"High": 3, "Medium": 2, "Low": 1}
        filtered_recommendations.sort(key=lambda x: impact_priority[x["impact_level"]], reverse=True)
    elif sort_by == "Impact (Low to High)":
        impact_priority = {"High": 3, "Medium": 2, "Low": 1}
        filtered_recommendations.sort(key=lambda x: impact_priority[x["impact_level"]])
    elif sort_by == "Time (Newest First)":
        filtered_recommendations.sort(key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S"), reverse=True)
    else:  # Time (Oldest First)
        filtered_recommendations.sort(key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S"))
    
    # Display recommendations count
    st.markdown(f"### Active Recommendations ({len(filtered_recommendations)})")
    
    if not filtered_recommendations:
        st.info("No recommendations match the selected filters.")
        return
    
    # Display recommendations
    for recommendation in filtered_recommendations:
        display_recommendation_card(recommendation) 