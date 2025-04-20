import streamlit as st
import pandas as pd
import plotly.express as px
import json # Import json library
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import threading
import time

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

from src.ui.alerts import display_alerts_section
from src.ui.recommendations import display_recommendations_section
# Import simulation functions
from src.agents.simulation_agent import simulate_resource_change, simulate_target_adjustment, calculate_projected_outcomes
# Import agent classes
import autogen
from src.agents.monitoring_agent import MonitoringAgent
from src.agents.recommendation_agent import RecommendationAgent
from src.agents.simulation_agent import SimulationAgent
# Import simulation tools (needed if UserProxy executes them)
from src.agents.simulation_agent import simulate_resource_change, simulate_target_adjustment 
# Import monitoring tools (assuming they are moved or defined)
# from src.tools.monitoring_tools import analyze_utilization, forecast_next_month_utilization
# Utility for loading LLM config (assuming it exists)
from src.utils.config import load_llm_config 

# Initialize session state for simulation results if they don't exist
if 'resource_change_result' not in st.session_state:
    st.session_state.resource_change_result = None
if 'target_adjustment_result' not in st.session_state:
    st.session_state.target_adjustment_result = None
# Initialize simulation history
if 'simulation_history' not in st.session_state:
    st.session_state.simulation_history = []
# Initialize chat messages
if 'messages' not in st.session_state:
    st.session_state.messages = [] 
    # Add initial greeting from agent if desired
    # st.session_state.messages.append({"role": "assistant", "content": "Hello! How can I help you with resource monitoring today?", "timestamp": datetime.now().strftime("%H:%M:%S")})

# Initialize session state
if 'chat_agents_initialized' not in st.session_state:
    st.session_state.chat_agents_initialized = False
if 'user_proxy' not in st.session_state:
    st.session_state.user_proxy = None
if 'monitoring_agent' not in st.session_state:
    st.session_state.monitoring_agent = None
if 'recommendation_agent' not in st.session_state:
    st.session_state.recommendation_agent = None
if 'simulation_agent' not in st.session_state:
    st.session_state.simulation_agent = None
if 'group_chat_manager' not in st.session_state:
    st.session_state.group_chat_manager = None

# Page configuration
st.set_page_config(
    page_title="Resource Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- Custom CSS (Optional) ---
# Remove unused CSS
st.markdown("""
<style>
    /* Add any custom styles here if needed */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem;
    }
    /* Add styles for buttons if desired */
    /* .stButton>button { 
        border: 1px solid #ccc;
        border-radius: 4px;
    } */
</style>
""", unsafe_allow_html=True)

# Helper function to generate sample data
def generate_sample_data(days=90):
    today = datetime.now().date()
    dates = [today - timedelta(days=i) for i in range(days)]
    dates.reverse()
    
    # Simulate utilization data
    utilization = pd.Series(
        [75 + (i % 15) * (1 if i % 2 == 0 else -1) + (i // 10) for i in range(days)],
        index=pd.to_datetime(dates)
    )
    utilization = utilization.clip(50, 95) # Keep utilization between 50% and 95%
    
    # Sample alerts (you might fetch these from your agent)
    alerts = [
        {
            "level": "CRITICAL",
            "metric": "Utilization",
            "details": "Resource 'Team A' exceeded critical threshold (95%) with 98%",
            "timestamp": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "level": "WARNING",
            "metric": "Capacity",
            "details": "Project 'Omega' approaching capacity limit (85% reached)",
            "timestamp": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "level": "INFO",
            "metric": "Trend",
            "details": "Sustained upward trend in 'Support Team' utilization over 7 days",
            "timestamp": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

    # Sample recommendations
    recommendations = [
        {
            "category": "Resource Optimization",
            "title": "Optimize Resource Allocation for Team B",
            "description": "Team B shows consistent underutilization (avg 60%). Consider reallocating tasks or cross-training.",
            "impact_level": "High",
            "estimated_impact": {"cost_savings": 5000.00, "efficiency_gain": 15},
            "timestamp": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "category": "Capacity Planning",
            "title": "Increase Capacity for Project Alpha",
            "description": "Project Alpha hitting 90% capacity frequently. Plan for additional resources.",
            "impact_level": "Medium",
            "estimated_impact": {"time_savings": 40},
            "timestamp": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    
    return utilization, alerts, recommendations

# Function to create utilization trend chart
def create_utilization_chart(utilization_data: pd.Series):
    fig = px.line(
        utilization_data,
        title="Overall Utilization Trend",
        labels={"index": "Date", "value": "Utilization (%)"},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        xaxis_title="",
        yaxis_title="Utilization %",
        title_font_size=18,
        title_x=0.05 # Left-align title
    )
    fig.update_traces(line_color='#1f77b4', hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Utilization: %{y:.1f}%<extra></extra>')
    # Add a horizontal line for target utilization (e.g., 80%)
    fig.add_hline(y=80, line_dash="dash", line_color="green", annotation_text="Target (80%)", annotation_position="bottom right")
    # Add a horizontal line for critical threshold (e.g., 90%)
    fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Critical (90%)", annotation_position="top right")
    return fig

# Function to display simulation results nicely
def display_simulation_results(result_key):
    result = st.session_state.get(result_key)
    if result:
        with st.container(border=True):
            st.write("--- Simulation Results ---")
            if result.get("status") == "success":
                st.success(result.get("summary", "Simulation completed successfully."))
                
                sim_type = result.get("simulation_type")
                
                if sim_type == "resource_change":
                    col_base, col_sim = st.columns(2)
                    with col_base:
                        st.write("**Baseline State**")
                        st.metric("Utilization", f"{result['baseline_state']['utilization_percent']:.1f}%")
                        st.write(f"Source Hours: {result['baseline_state']['source_hours']:.1f}")
                        st.write(f"Target Hours: {result['baseline_state']['target_hours']:.1f}")
                        st.write(f"Other Hours: {result['baseline_state']['other_hours']:.1f}")
                    with col_sim:
                        st.write("**Simulated State**")
                        st.metric("Utilization", f"{result['simulated_state']['utilization_percent']:.1f}%", delta=f"{result['impact']['utilization_change_percent']:.1f}% pts")
                        st.write(f"Source Hours: {result['simulated_state']['source_hours']:.1f}")
                        st.write(f"Target Hours: {result['simulated_state']['target_hours']:.1f}")
                        st.write(f"Other Hours: {result['simulated_state']['other_hours']:.1f}")
                elif sim_type == "target_adjustment":
                    analysis = result.get("simulated_impact_analysis", {})
                    st.metric("New Target Utilization", f"{analysis.get('new_target_utilization_percent', 'N/A'):.1f}%", delta=f"{analysis.get('required_utilization_change_percent', 0):.1f}% vs actual")
                    st.write(f"**Feasibility:** {analysis.get('feasibility', 'Unknown')}")
                    for note in analysis.get('feasibility_notes', []):
                        st.caption(note)
                    st.write(f"Required Avg Hours Change/Resource: {analysis.get('required_hours_change_per_resource_per_week', 0):.1f} hrs/wk")
                    st.write(f"(Baseline Actual Util: {result['baseline_state']['current_actual_utilization_percent']:.1f}%)")
                
                with st.expander("View Raw Result Data"):
                     st.json(result)
                     
            elif result.get("status") == "pending_implementation":
                st.info(result.get("message", "Further calculation pending implementation."))
                if "simulation_summary" in result:
                     st.write(f"Input Summary: {result['simulation_summary']}")
                     
            elif result.get("status") == "skipped":
                st.warning(result.get("message", "Simulation step skipped."))
            else: # Error or other status
                st.error(f"Simulation Error: {result.get('message', 'Unknown error')}")
                
            # Add Clear and Download buttons side-by-side
            col_btn1, col_btn2 = st.columns([1, 1]) 
            with col_btn1:
                if st.button("Clear Simulation Result", key=f"clear_{result_key}", use_container_width=True):
                    st.session_state[result_key] = None
                    st.rerun()
            
            with col_btn2:
                if result: # Only show download if there's a result
                    try:
                        json_string = json.dumps(result, indent=2)
                        sim_type = result.get("simulation_type", "unknown")
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"simulation_{sim_type}_{ts}.json"
                        
                        st.download_button(
                           label="Download Result as JSON",
                           data=json_string,
                           file_name=file_name,
                           mime="application/json",
                           key=f"download_{result_key}",
                           use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error preparing download: {e}")

# Placeholder function for displaying chat messages
def display_chat_messages():
    """Displays the chat messages stored in session state with agent indicators."""
    if not st.session_state.messages:
        st.info("Start the conversation by typing below...")
        return
        
    # Define CSS for agent badges
    st.markdown("""
    <style>
    .agent-badge {
        display: inline-block;
        border-radius: 3px;
        padding: 2px 6px;
        margin-right: 5px;
        font-size: 0.7em;
        font-weight: bold;
    }
    .main-agent {
        background-color: #2E86C1;
        color: white;
    }
    .monitoring-agent {
        background-color: #27AE60;
        color: white;
    }
    .recommendation-agent {
        background-color: #F39C12;
        color: white;
    }
    .simulation-agent {
        background-color: #8E44AD;
        color: white;
    }
    .user-proxy {
        background-color: #E74C3C;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            msg_content = message.get("content", "")
            timestamp = message.get("timestamp", "")
            
            # If this is an assistant message and has an agent field, show the agent badge
            if message["role"] == "assistant" and "agent" in message:
                agent = message["agent"]
                agent_class = "main-agent"
                
                if "Monitoring" in agent:
                    agent_class = "monitoring-agent"
                elif "Recommendation" in agent:
                    agent_class = "recommendation-agent"
                elif "Simulation" in agent:
                    agent_class = "simulation-agent"
                elif "User_Proxy" in agent:
                    agent_class = "user-proxy"
                    
                # Display agent badge
                st.markdown(f'<div class="agent-badge {agent_class}">{agent}</div>', unsafe_allow_html=True)
                
            # Display the message content
            st.markdown(msg_content)
            
            # Display timestamp if available
            if timestamp:
                st.caption(f"_{timestamp}_")

# --- Agent Initialization Function ---
def initialize_chat_agents():
    """Initializes the UserProxyAgent, specialist agents, and GroupChatManager."""
    if st.session_state.chat_agents_initialized:
        return True
        
    try:
        llm_config = load_llm_config() 
        if not llm_config:
            st.error("LLM Configuration failed. Chat agents cannot be initialized.")
            return False

        # Ensure the configuration has the required Azure OpenAI settings
        if not all(key in llm_config["config_list"][0] for key in ["api_type", "api_version", "base_url"]):
            st.error("Invalid Azure OpenAI configuration. Missing required fields.")
            return False

        # --- User Proxy Agent --- 
        st.session_state.user_proxy = autogen.UserProxyAgent(
            name="User_Proxy",
            human_input_mode="NEVER", 
            max_consecutive_auto_reply=5,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config=False,  
            llm_config=llm_config,
            system_message="""You are the orchestrator of a Resource Monitoring System.

IMPORTANT: This is a specialized system for resource monitoring ONLY.

For queries outside our domain (weather, news, sports, entertainment, etc.):
- DO NOT forward these to specialist agents
- Respond directly that we're a resource monitoring system and cannot help with those topics
- Suggest using appropriate services for those queries
- End the conversation with TERMINATE

For simple greetings or general queries about the system:
- Respond with helpful information about what our system can do
- End the conversation with TERMINATE

For complex technical requests related to resource monitoring:
- Relay user questions to the appropriate specialist:
  - Monitoring_Expert: For data analysis, metrics, and utilization questions
  - Recommendation_Expert: For optimization suggestions and best practices
  - Simulation_Expert: For what-if scenarios and impact analysis

After specialist responses, summarize the final response for the user.
Reply TERMINATE after the final summary.

Always maintain a professional, helpful tone. Provide clear, actionable information."""
        )
        
        # --- Specialist Agents --- 
        st.session_state.monitoring_agent = MonitoringAgent(
            name="Monitoring_Expert", 
            llm_config=llm_config,
            system_message="""You are the Monitoring Expert. Focus on analyzing resource utilization data, 
            metrics, and performance indicators. When asked about monitoring topics, 
            provide specific, actionable insights. Wait for the User_Proxy to ask you questions 
            before responding. Keep responses focused and relevant to monitoring."""
        )
        
        st.session_state.recommendation_agent = RecommendationAgent(
            name="Recommendation_Expert", 
            llm_config=llm_config,
            system_message="""You are the Recommendation Expert. Focus on providing optimization 
            suggestions based on resource data. When asked about recommendations, 
            provide specific, actionable suggestions. Wait for the User_Proxy to ask you questions 
            before responding. Keep responses focused and relevant to optimization."""
        )
        
        st.session_state.simulation_agent = SimulationAgent(
            name="Simulation_Expert", 
            llm_config=llm_config,
            system_message="""You are the Simulation Expert. Focus on what-if scenarios and 
            impact analysis of resource changes. When asked about simulations, 
            provide specific steps and projected outcomes. Wait for the User_Proxy to ask you questions 
            before responding. Keep responses focused and relevant to simulations."""
        )
        
        # --- Group Chat Setup --- 
        agents = [
            st.session_state.user_proxy, 
            st.session_state.monitoring_agent,
            st.session_state.recommendation_agent,
            st.session_state.simulation_agent
        ]
        
        group_chat = autogen.GroupChat(
            agents=agents,
            messages=[],
            max_round=12
        )
        
        st.session_state.group_chat_manager = autogen.GroupChatManager(
            groupchat=group_chat, 
            llm_config=llm_config
        )
        
        st.session_state.chat_agents_initialized = True
        logger.info("Chat agents and GroupChat initialized successfully.") 
        return True

    except Exception as e:
        logger.error(f"Error initializing chat agents: {e}", exc_info=True)
        st.error(f"Failed to initialize chat agents: {e}")
        st.session_state.chat_agents_initialized = False
        return False

# Main app function
def main():
    st.title("Resource Monitoring Dashboard")
    
    # --- Attempt to initialize agents --- 
    # Moved initialization call here
    if not st.session_state.chat_agents_initialized:
        initialize_chat_agents() # Attempt initialization on first run / if failed
        
    # --- Data Loading & Filtering (Sidebar) --- 
    days_to_show = st.sidebar.slider("Select Time Range (Days)", 7, 180, 90)
    utilization_data, alerts, recommendations = generate_sample_data(days=days_to_show)

    # --- Setup Tabs ---
    tab_titles = ["Overview", "Alerts", "Recommendations", "Simulation / What-If", "Chat"]
    overview_tab, alerts_tab, recommendations_tab, simulation_tab, chat_tab = st.tabs(tab_titles)

    # --- Overview Tab --- 
    with overview_tab:
        st.header("Dashboard Overview")
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                delta_utilization = None
                if len(utilization_data) > 1:
                    delta_utilization = utilization_data.iloc[-1] - utilization_data.iloc[-2]
                st.metric("Current Utilization", f"{utilization_data.iloc[-1]:.1f}%", f"{delta_utilization:.1f}%" if delta_utilization is not None else None)
            with col2:
                st.metric("Active Alerts", len(alerts))
            with col3:
                st.metric("Pending Recommendations", len(recommendations))
            with col4:
                st.metric("Avg Utilization", f"{utilization_data.mean():.1f}%", delta=None)
        st.plotly_chart(create_utilization_chart(utilization_data), use_container_width=True)

    # --- Alerts Tab --- 
    with alerts_tab:
        display_alerts_section(alerts) 

    # --- Recommendations Tab --- 
    with recommendations_tab:
        display_recommendations_section(recommendations)

    # --- Simulation Tab ---
    with simulation_tab:
        st.header("What-If Scenario Simulation")
        st.info("Use the forms below to simulate potential changes and see their projected impact on resource utilization and feasibility.")
        
        st.divider()

        # --- Resource Allocation Change Section --- 
        with st.container(border=True):
            st.subheader("Simulate Resource Allocation Change")
            with st.form(key='resource_change_sim_form'):
                st.write("Enter details for moving resource hours between assignments:")
                resource_id = st.text_input("Resource ID", "employee_123")
                col_src, col_tgt = st.columns(2)
                with col_src:
                    st.write("**Source Assignment**")
                    source_project_id = st.text_input("Source Project/Team ID", "Project_Alpha", key="rc_src_proj")
                    source_allocated_hours = st.number_input(
                        "Current Allocated Hrs/Wk", 
                        min_value=0.0, value=25.0, step=1.0, key="rc_src_hrs",
                        help="Enter the hours currently allocated *to this specific source assignment* for the resource."
                    )
                with col_tgt:
                    st.write("**Target Assignment**")
                    target_project_id = st.text_input("Target Project/Team ID", "Project_Beta", key="rc_tgt_proj")
                    target_allocated_hours = st.number_input(
                        "Current Allocated Hrs/Wk", 
                        min_value=0.0, value=5.0, step=1.0, key="rc_tgt_hrs",
                        help="Enter the hours currently allocated *to this specific target assignment* for the resource."
                    )
                hours_to_move = st.number_input("Hrs/Wk to Move", min_value=0.1, value=10.0, step=0.5, key="rc_move_hrs")
                timeframe_weeks = st.number_input("Timeframe (Weeks)", min_value=1, value=4, step=1, key="rc_timeframe")
                submit_rc = st.form_submit_button(label='Run Resource Change Simulation')

            if submit_rc:
                # Basic Validation
                valid = True
                if not resource_id: st.error("Resource ID required."); valid = False
                if not source_project_id: st.error("Source Project ID required."); valid = False
                if not target_project_id: st.error("Target Project ID required."); valid = False
                if hours_to_move <= 0: st.error("Hours to move must be positive."); valid = False
                
                if valid:
                    # Prepare params for the function call
                    source_assignment = {"project_id": source_project_id, "allocated_hours": source_allocated_hours}
                    target_assignment = {"project_id": target_project_id, "allocated_hours": target_allocated_hours}
                    
                    # Call the simulation function
                    with st.spinner("Running simulation..."):
                        result = simulate_resource_change(
                            resource_id=resource_id, 
                            source_assignment=source_assignment,
                            target_assignment=target_assignment,
                            hours_to_move=hours_to_move,
                            timeframe_weeks=timeframe_weeks
                        )
                        st.session_state.resource_change_result = result
                        # Add to history if successful
                        if result.get("status") == "success":
                            st.session_state.simulation_history.append(result)
                    st.rerun()
                    
            display_simulation_results('resource_change_result')
        
        # --- Target Utilization Adjustment Section --- 
        with st.container(border=True):
            st.subheader("Simulate Target Utilization Adjustment")
            with st.form(key='target_adjust_sim_form'):
                st.write("Select scope and new target utilization:")
                target_scope = st.selectbox("Target Scope", ["global", "team", "resource", "project"], index=1, key="ta_scope")
                scope_id_val = None
                if target_scope != "global":
                    scope_id_val = st.text_input(f"{target_scope.capitalize()} ID", f"{target_scope.capitalize()}_XYZ", key="ta_scope_id")
                
                current_target_util = st.number_input("Current Target Utilization (%)", min_value=0.0, max_value=100.0, value=80.0, step=1.0, key="ta_current")
                new_target_util = st.number_input("New Target Utilization (%)", min_value=0.0, max_value=100.0, value=85.0, step=1.0, key="ta_new")
                timeframe_weeks_ta = st.number_input("Timeframe (Weeks)", min_value=1, value=4, step=1, key="ta_timeframe")
                
                submit_ta = st.form_submit_button(label='Run Target Adjustment Simulation')
                
            if submit_ta:
                # Basic Validation
                valid = True
                if target_scope != "global" and not scope_id_val: st.error(f"{target_scope.capitalize()} ID required."); valid = False
                if not 0 <= current_target_util <= 100: st.error("Current target must be 0-100."); valid = False
                if not 0 <= new_target_util <= 100: st.error("New target must be 0-100."); valid = False
                
                if valid:
                    # Call the simulation function
                    with st.spinner("Running simulation..."):
                        result = simulate_target_adjustment(
                            target_scope=target_scope,
                            scope_id=scope_id_val,
                            current_target_utilization=current_target_util,
                            new_target_utilization=new_target_util,
                            timeframe_weeks=timeframe_weeks_ta
                        )
                        st.session_state.target_adjustment_result = result
                        # Add to history if successful
                        if result.get("status") == "success":
                            st.session_state.simulation_history.append(result)
                    st.rerun()

            display_simulation_results('target_adjustment_result')
        
        # --- Simulation History Section ---
        with st.container(border=True):
            st.subheader("Simulation History (Current Session)")
            
            if not st.session_state.simulation_history:
                st.caption("No simulations run in this session yet.")
            else:
                # Display history in reverse chronological order
                for i, history_item in enumerate(reversed(st.session_state.simulation_history)):
                    sim_type = history_item.get("simulation_type", "Unknown")
                    summary = history_item.get("summary", "No summary available.")
                    params = history_item.get("parameters", {})
                    expander_title = f"Run {len(st.session_state.simulation_history) - i}: {sim_type.replace('_', ' ').title()} - {summary[:50]}..."
                    
                    with st.expander(expander_title):
                        st.write(f"**Type:** {sim_type.replace('_', ' ').title()}")
                        st.write("**Parameters:**")
                        st.json(params)
                        st.write("**Result Summary:**")
                        st.success(summary) # Or use display_simulation_results logic if needed
                        # Optionally add more details from the history_item here
                
                if st.button("Clear History"):
                    st.session_state.simulation_history = []
                    st.rerun()

    # --- Chat Tab ---
    with chat_tab:
        st.header("Chat with Resource Agent")
        
        if not st.session_state.chat_agents_initialized:
            st.warning("Chat agents are not initialized. Please check configuration and logs.")
        else:
            display_chat_messages()
            
            if user_input := st.chat_input("Ask about resources, alerts, recommendations, or run simulations...", 
                                          disabled=not st.session_state.chat_agents_initialized):
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.session_state.messages.append({"role": "user", "content": user_input, "timestamp": timestamp})
                
                # --- Process User Input --- 
                with st.spinner("Processing your request..."):
                    try:
                        # Handle simple greetings or out-of-domain queries directly
                        simple_greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]
                        
                        # Define out-of-domain topics (weather, news, general knowledge, etc.)
                        out_of_domain_keywords = ["weather", "news", "sports", "movie", "music", "food", "restaurant", 
                                                 "recipe", "travel", "vacation", "hotel", "flight"]
                        
                        # Check if query is a simple greeting
                        if user_input.lower().strip() in simple_greetings:
                            # Direct response for simple greetings
                            greeting_response = {
                                "role": "assistant", 
                                "agent": "Main Agent",
                                "content": "Hello! I'm your Resource Monitoring Assistant. I can help you with resource utilization, recommendations, alerts, and simulations. How can I assist you today?",
                                "timestamp": datetime.now().strftime("%H:%M:%S")
                            }
                            st.session_state.messages.append(greeting_response)
                            st.rerun()  # Show the greeting immediately before continuing
                        
                        # Check if query is about out-of-domain topics
                        elif any(keyword in user_input.lower() for keyword in out_of_domain_keywords):
                            # Direct response for out-of-domain queries
                            out_of_domain_response = {
                                "role": "assistant", 
                                "agent": "Main Agent",
                                "content": f"I'm a Resource Monitoring Assistant specialized in resource utilization, alerts, recommendations, and simulations. For information about {user_input}, please check a dedicated service for that topic. Is there anything I can help you with regarding resource management?",
                                "timestamp": datetime.now().strftime("%H:%M:%S")
                            }
                            st.session_state.messages.append(out_of_domain_response)
                            st.rerun()  # Show the response immediately before continuing
                        
                        # For domain-specific queries, use the multi-agent system
                        else:
                            # Don't reset messages, maintain conversation history
                            if not st.session_state.group_chat_manager.groupchat.messages:
                                # If it's the first message, add system context
                                context_message = {
                                    "role": "system",
                                    "content": """This is a resource monitoring system. You have access to:
                                    1. Monitoring capabilities for resource utilization
                                    2. Recommendation generation for optimization
                                    3. Simulation tools for what-if analysis
                                    4. Historical data and alerts
                                    
                                    Coordinate with specialist agents and use appropriate tools when needed.
                                    
                                    IMPORTANT: For non-system related questions (weather, news, etc.), respond directly
                                    that you're a resource monitoring system and cannot help with those topics."""
                                }
                                st.session_state.group_chat_manager.groupchat.messages.append(context_message)
                            
                            # Create a placeholder to show progress
                            response_placeholder = st.empty()
                            response_placeholder.info("Processing your request. Please wait...")
                            
                            # Prepare the message with context
                            full_message = f"""Current request: {user_input}
                            
                            Remember to:
                            1. Coordinate with specialist agents for their expertise
                            2. Use monitoring tools when data analysis is needed
                            3. Run simulations when what-if scenarios are requested
                            4. Provide clear, actionable responses
                            5. If this question is not about resource monitoring (e.g., weather, news), respond directly that you're a resource monitoring system."""
                            
                            # Use a simpler approach without callbacks
                            try:
                                # Initiate the chat - this is a blocking call that will complete when conversation ends
                                chat_result = st.session_state.user_proxy.initiate_chat(
                                    st.session_state.group_chat_manager,
                                    message=full_message,
                                    clear_history=False  # Maintain history for context
                                )
                                
                                # Process the completed chat result
                                # Extract messages from the chat history
                                all_messages = []
                                if hasattr(st.session_state.group_chat_manager.groupchat, "messages"):
                                    all_messages = st.session_state.group_chat_manager.groupchat.messages
                                
                                # Filter and process messages
                                processed_messages = []
                                for msg in all_messages:
                                    # Skip system messages
                                    if msg.get("role") == "system":
                                        continue
                                        
                                    # Process user and assistant messages
                                    agent_name = "Assistant"
                                    content = msg.get("content", "")
                                    
                                    # Try to identify the agent from the message
                                    if msg.get("name"):
                                        agent_name = msg.get("name")
                                    elif " (to " in content and content.startswith(("Monitoring_Expert", "Recommendation_Expert", "Simulation_Expert", "User_Proxy")):
                                        agent_name = content.split(" (to ")[0]
                                        content = content.split(":", 1)[1].strip() if ":" in content else content
                                    
                                    # Skip TERMINATE messages and internal coordination
                                    if "TERMINATE" in content and len(content) < 20:
                                        continue
                                    if content.startswith(("I'll relay", "Let me ask")) and len(content) < 100:
                                        continue
                                    
                                    # Add meaningful messages to our display list
                                    if len(content) > 20 and msg.get("role") == "assistant":  # Skip very short messages
                                        processed_messages.append({
                                            "role": "assistant",
                                            "agent": agent_name,
                                            "content": content,
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        })
                                
                                # Clear the placeholder
                                response_placeholder.empty()
                                
                                # Add messages to the chat history
                                if processed_messages:
                                    # Show up to 3 most meaningful messages (sorted by length as a heuristic)
                                    messages_to_show = sorted(processed_messages, key=lambda x: len(x["content"]), reverse=True)[:3]
                                    for msg in messages_to_show:
                                        st.session_state.messages.append(msg)
                                else:
                                    # Fallback if no suitable messages were found
                                    st.session_state.messages.append({
                                        "role": "assistant",
                                        "agent": "Main Agent",
                                        "content": "I apologize, but I couldn't process your request properly. Could you please try again?",
                                        "timestamp": datetime.now().strftime("%H:%M:%S")
                                    })
                                
                            except Exception as e:
                                logger.error(f"Error during agent chat: {e}", exc_info=True)
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "agent": "Main Agent",
                                    "content": f"I apologize, but I encountered an error while processing your request: {str(e)}. Please try again.",
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                })
                            
                            # Rerun to update the UI with new messages
                            st.rerun()
                            
                    except Exception as e:
                        logger.error(f"Error during agent chat: {e}", exc_info=True)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "agent": "Main Agent",
                            "content": "I apologize, but I encountered an error while processing your request. Please try again.",
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        st.rerun()  # Important to update the UI immediately
                
                st.rerun() # Rerun to display the new messages

if __name__ == "__main__":
    main() 