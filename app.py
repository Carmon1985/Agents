import streamlit as st
import os
import sys
import logging
import json
from dotenv import load_dotenv
import autogen
from typing import Optional, Dict, Any, List
import datetime
from contextlib import contextmanager
import asyncio

from agents.specialized_agents import AgentCollaborationManager

# --- Page Setup Function ---
def setup_page():
    """Configures the Streamlit page settings."""
    # --- Page Configuration MUST be the first Streamlit command ---
    st.set_page_config(
        page_title="🤖 Resource Monitoring Agent Dashboard",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

# --- Initial Setup ---
setup_page() # Call the setup function

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
logger.info(f"Added {src_path} to sys.path")

# --- Load Environment Variables ---
load_dotenv()
logger.info(".env file loaded.")

# --- Import Tool Functions --- (Error handling included)
try:
    # These are the low-level DB query functions
    from src.db.query_functions import get_period_data as db_get_period_data, forecast_next_month_utilization as db_forecast_next_month_utilization
    logger.info("Query functions imported successfully.")
    TOOLS_LOADED = True
except ImportError as e:
    logger.error(f"Error importing query functions: {e}", exc_info=True)
    st.error(f"Failed to import database functions (query_functions.py). Check logs. Error: {e}")
    TOOLS_LOADED = False
    # Define placeholders if import fails
    def db_get_period_data(*args, **kwargs): return (0.0, 0.0, None) # Return tuple for placeholder
    def db_forecast_next_month_utilization(*args, **kwargs): return "Error: Tool function not loaded."

# --- Helper Function to Get Config --- (as before)
def get_llm_config():
    azure_endpoint = os.getenv("OPENAI_API_BASE")
    azure_deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")
    azure_api_version = os.getenv("OPENAI_API_VERSION")
    azure_api_key = os.getenv("OPENAI_API_KEY")
    azure_api_type = os.getenv("OPENAI_API_TYPE", "azure")
    missing_vars = []
    if not azure_endpoint: missing_vars.append("OPENAI_API_BASE")
    if not azure_deployment_name: missing_vars.append("OPENAI_DEPLOYMENT_NAME")
    if not azure_api_version: missing_vars.append("OPENAI_API_VERSION")
    if not azure_api_key: missing_vars.append("OPENAI_API_KEY")
    if missing_vars:
        st.error(f"Missing Azure OpenAI environment variables: {', '.join(missing_vars)}. Please check your .env file.")
        return None
    config_list = [{
        "model": azure_deployment_name,
        "api_key": azure_api_key,
        "base_url": azure_endpoint,
        "api_type": azure_api_type,
        "api_version": azure_api_version,
    }]
    return {"config_list": config_list, "temperature": 0, "timeout": 600, "cache_seed": None}

# --- Define Tool Schemas --- (as before)
analyze_utilization_tool = { "type": "function", "function": { "name": "analyze_utilization", "description": "Analyzes resource utilization for a given date range and optional employee ID by querying charged hours, capacity hours, and target utilization from the database. Returns structured JSON.", "parameters": { "type": "object", "properties": { "start_date": { "type": "string", "description": "The start date for the analysis period in YYYY-MM-DD format." }, "end_date": { "type": "string", "description": "The end date for the analysis period in YYYY-MM-DD format." }, "employee_id": { "type": "string", "description": "Optional. The specific employee ID to analyze. If omitted, analyzes aggregate utilization." } }, "required": ["start_date", "end_date"] } } }
forecast_utilization_tool = { "type": "function", "function": { "name": "forecast_next_month_utilization", "description": "Forecasts the next calendar month's resource utilization based on the average of a specified number of past months (forecast_window). Requires specifying how many total months of history (num_history_months) to fetch to calculate the average.", "parameters": { "type": "object", "properties": { "num_history_months": { "type": "integer", "description": "The total number of past months of historical data to retrieve." }, "current_date_str": { "type": "string", "description": "The current date (YYYY-MM-DD) used as the reference point for fetching history (history ends before this date's month)." }, "employee_id": { "type": "string", "description": "Optional. The specific employee ID to forecast for. If omitted, forecasts aggregate utilization." }, "forecast_window": { "type": "integer", "description": "Optional. The number of recent historical months (default 3) to average for the forecast.", "default": 3 } }, "required": ["num_history_months", "current_date_str"] } } }

# --- Define Wrapper Functions for Tools within App Scope ---
# Wrapper for analyze_utilization (calls the imported DB function)
def analyze_utilization(start_date: str, end_date: str, employee_id: Optional[str] = None) -> str:
    """
    Wrapper: Analyzes utilization, compares to target, classifies deviation, 
    and returns a structured JSON string with analysis details and alert level.
    Calls the underlying database query function.
    """
    # Check if the actual DB function was loaded
    if not TOOLS_LOADED or db_get_period_data is None:
         return json.dumps({"status": "ERROR", "message": "Database function (get_period_data) not loaded.", "details": {}, "alert_level": "ERROR"})
         
    SIGNIFICANT_DEVIATION_THRESHOLD = 5.0
    ALERT_THRESHOLD = SIGNIFICANT_DEVIATION_THRESHOLD
    result_data = {"status": "ERROR", "message": "Analysis did not complete.", "details": {}, "alert_level": "NONE"}
    
    try:
        logger.info(f"[Wrapper] Analyzing utilization for period {start_date} to {end_date}, Employee: {employee_id or 'All'}")
        # Call the imported DB function
        charged_hours, capacity_hours, target_utilization_ratio = db_get_period_data(start_date, end_date, employee_id)

        result_data["details"]["period_start"] = start_date
        result_data["details"]["period_end"] = end_date
        result_data["details"]["employee_id"] = employee_id or "All"

        if capacity_hours <= 0:
            logger.warning("[Wrapper] Capacity hours are zero or negative.")
            result_data["message"] = "Analysis Error: Capacity hours are zero or less, cannot calculate utilization."
            result_data["alert_level"] = "WARNING" 
            return json.dumps(result_data, indent=2)

        utilization_rate = (charged_hours / capacity_hours) * 100
        result_data["details"]["charged_hours"] = f"{charged_hours:.2f}"
        result_data["details"]["capacity_hours"] = f"{capacity_hours:.2f}"
        result_data["details"]["calculated_utilization_pct"] = f"{utilization_rate:.2f}"
        result_data["status"] = "OK"
        result_data["message"] = "Analysis successful."
        result_data["alert_level"] = "INFO"

        if target_utilization_ratio is not None:
            target_percentage = target_utilization_ratio * 100
            deviation = utilization_rate - target_percentage
            result_data["details"]["target_utilization_pct"] = f"{target_percentage:.2f}"
            result_data["details"]["deviation_pct"] = f"{deviation:.2f}"
            
            if deviation >= 0:
                deviation_status = "Met/Exceeded Target"
                result_data["alert_level"] = "INFO"
            elif abs(deviation) <= ALERT_THRESHOLD:
                deviation_status = "Slightly Below Target"
                result_data["alert_level"] = "WARNING"
            else:
                deviation_status = "Significantly Below Target"
                result_data["alert_level"] = "CRITICAL"
                
            result_data["details"]["deviation_status"] = deviation_status
            result_data["message"] = f"Analysis successful. Status: {deviation_status}"
        else:
            result_data["details"]["target_utilization_pct"] = "Not found"
            result_data["details"]["deviation_status"] = "Cannot assess deviation (no target)"
            result_data["message"] = "Analysis successful, but no target found."
            result_data["alert_level"] = "INFO"

        logger.info(f"[Wrapper] Analysis complete. Alert Level: {result_data['alert_level']}")
        return json.dumps(result_data, indent=2)

    except Exception as e:
        logger.error(f"[Wrapper] An unexpected error occurred during utilization analysis: {e}", exc_info=True)
        result_data["message"] = f"Unexpected Error: {e}"
        result_data["alert_level"] = "ERROR"
        return json.dumps(result_data)

# Wrapper for forecast_next_month_utilization (calls the imported DB function)
def forecast_next_month_utilization(num_history_months: int, current_date_str: str, employee_id: Optional[str] = None, forecast_window: int = 3) -> str:
    """ 
    Wrapper: Calls the underlying database forecast function.
    Ensures the function is loaded before calling.
    """
    # Check if the actual DB function was loaded
    if not TOOLS_LOADED or db_forecast_next_month_utilization is None:
         return "Error: Forecast tool function (forecast_next_month_utilization) not loaded."
         
    logger.info(f"[Wrapper] Calling forecast function...")
    try:
        # Call the imported DB function
        result = db_forecast_next_month_utilization(num_history_months, current_date_str, employee_id, forecast_window)
        return result
    except Exception as e:
        logger.error(f"[Wrapper] An unexpected error occurred during forecast call: {e}", exc_info=True)
        return f"Unexpected Error during forecast call: {e}"

# --- Initialize Agents in Session State --- 
def initialize_agents():
    logger.info("Initializing monitoring agent...")
    llm_config = get_llm_config()
    if not llm_config:
        st.error("LLM configuration failed. Cannot initialize agent.")
        return False
    
    try:
        monitoring_agent_llm_config = llm_config.copy()
        monitoring_agent_llm_config["tools"] = [{
            "type": "function",
            "function": {
                "name": "analyze_utilization",
                "description": "Analyzes resource utilization for a given date range and optional employee ID by querying charged hours, capacity hours, and target utilization from the database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "The start date for the analysis period in YYYY-MM-DD format.",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "The end date for the analysis period in YYYY-MM-DD format.",
                        },
                        "employee_id": {
                            "type": "string",
                            "description": "Optional. The specific employee ID to analyze. If omitted, analyzes aggregate utilization.",
                        },
                    },
                    "required": ["start_date", "end_date"],
                },
            },
        }, {
            "type": "function",
            "function": {
                "name": "forecast_next_month_utilization",
                "description": "Forecasts the next calendar month's resource utilization based on the average of a specified number of past months (forecast_window). Requires specifying how many total months of history (num_history_months) to fetch to calculate the average.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "num_history_months": {
                            "type": "integer",
                            "description": "The total number of past months of historical data to retrieve.",
                        },
                        "current_date_str": {
                            "type": "string",
                            "description": "The current date (YYYY-MM-DD) used as the reference point for fetching history (history ends before this date's month).",
                        },
                        "employee_id": {
                            "type": "string",
                            "description": "Optional. The specific employee ID to forecast for. If omitted, forecasts aggregate utilization.",
                        },
                        "forecast_window": {
                            "type": "integer",
                            "description": "Optional. The number of recent historical months (default 3) to average for the forecast.",
                            "default": 3
                        },
                    },
                    "required": ["num_history_months", "current_date_str"],
                },
            },
        }]
        st.session_state.monitoring_agent = autogen.AssistantAgent(
            name="Monitoring_Agent",
            system_message="""You are a monitoring agent specializing in resource utilization analysis and forecasting.

Your tasks are:
1. **Analyze Current Utilization:** Use the `analyze_utilization` tool. It returns a JSON string containing analysis details and an `alert_level` (NONE, INFO, WARNING, CRITICAL, ERROR).
2. **Forecast Future Utilization:** Use the `forecast_next_month_utilization` tool. It returns a string describing the forecast or an error.

**Your Response Rules:**
* When using `analyze_utilization`:
    * Parse the JSON result provided by the tool.
    * If the `alert_level` is `WARNING` or `CRITICAL`, format your response as an **ALERT** message, clearly stating the reason (e.g., 'Significantly Below Target', 'Zero Capacity') and including key details like Period, Employee (if applicable), Calculated Utilization, Target Utilization, and Deviation.
    * If the `alert_level` is `INFO`, `NONE`, or `ERROR`, simply report the main message or status from the JSON result.
* When using `forecast_next_month_utilization`:
    * Report the exact string result provided by the tool.
* Extract required parameters from the user request for the appropriate tool.
* Call the correct tool based on the user's request (analysis vs. forecast).
* If a tool itself fails or the JSON parsing fails, report the error encountered.
* Do not perform calculations or forecasts yourself; rely solely on the tools' outputs.
* After reporting the result/alert or error, conclude the conversation by replying with the word TERMINATE.""",
            llm_config=monitoring_agent_llm_config,
        )

        logger.info("Monitoring agent initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"Error initializing agent: {e}", exc_info=True)
        st.error(f"Failed to initialize agent: {e}")
        return False

# Initialize only if agent is not already in session state
if "monitoring_agent" not in st.session_state:
    agents_initialized = initialize_agents()
else:
    agents_initialized = True

# --- Chat History Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []

def clear_chat_history():
    st.session_state.messages = []
    st.rerun()

# --- Process Agent Response ---
def format_error_message(error_text: str) -> str:
    """Format error messages for better display"""
    return f"""
⚠️ **Error Occurred**
```
{error_text}
```
Please try again or rephrase your request.
"""

def format_tool_request(tool_name: str, tool_args: dict) -> str:
    """Format tool request messages for better display"""
    formatted_args = json.dumps(tool_args, indent=2)
    return f"""
🔧 **Using Tool: `{tool_name}`**
```json
{formatted_args}
```
"""

def process_agent_response(response: dict):
    """Adds the agent's response dictionary to the session state messages."""
    # Ensure the response has the expected keys (content, timestamp) and add role
    if "content" in response and "timestamp" in response:
        st.session_state.messages.append({
            "role": "assistant", # Assume agent responses are 'assistant' role
            "content": response["content"],
            "timestamp": response["timestamp"]
        })
        logger.info(f"Appended agent response to session state: {response['content']}")
    else:
        logger.warning("Attempted to process agent response with missing keys.")

# --- UI Display Logic ---
def display_chat_messages():
    """Displays the chat messages stored in session state."""
    logger.debug(f"Displaying {len(st.session_state.messages)} messages from session state.")
    for message in st.session_state.messages:
        avatar = "👤" if message["role"] == "user" else "🤖"
        if message["role"] == "tool":
            avatar = "🛠️"
        
        # Get timestamp if available
        timestamp = message.get("timestamp", "")
        
        with st.chat_message(message["role"], avatar=avatar):
            try:
                # Check if content looks like JSON (for tool results)
                if isinstance(message["content"], str) and message["content"].strip().startswith("{"):
                    content_data = json.loads(message["content"])
                    if timestamp:
                        st.caption(f"🕒 {timestamp}")
                    st.json(content_data)
                else:
                    # Display as markdown otherwise
                    if timestamp:
                        st.caption(f"🕒 {timestamp}")
                    st.markdown(message["content"])
            except Exception as display_err:
                logger.warning(f"Error displaying message content: {display_err}")
                if timestamp:
                    st.caption(f"🕒 {timestamp}")
                # Fallback to displaying raw content as markdown
                st.markdown(str(message["content"]))

# --- Page Layout ---
# Title and Status Section
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("🤖 Resource Monitoring Agent Dashboard")
    st.caption("Powered by AutoGen and Streamlit")
with col2:
    if not agents_initialized:
        st.error("⚠️ Agent Offline", icon="⚠️")
    elif not TOOLS_LOADED:
        st.warning("⚡ Agent Online (Limited)", icon="⚡")
    else:
        st.success("✅ Agent Online", icon="✅")
with col3:
    if st.button("🗑️ Clear Chat", help="Clear the conversation history"):
        clear_chat_history()

# Sidebar Info
with st.sidebar:
    st.header("📊 Usage Guide")
    
    # Basic Usage
    st.subheader("Basic Usage")
    st.markdown("""
    Type your questions about resource utilization in the chat input box below.
    The agent will help you analyze utilization data and create forecasts.
    """)
    
    # Example Queries
    st.subheader("Example Queries")
    st.markdown("""
    **Utilization Analysis:**
    - Analyze utilization for April 2025
    - What was the utilization between 2025-01-01 and 2025-01-31?
    - Show me the utilization stats for last week
    - Check employee ABC123's utilization for Q1 2025
    
    **Forecasting:**
    - Forecast utilization for next month
    - Predict next month's utilization based on last 6 months
    - What's the expected utilization for employee XYZ789?
    - Generate a 3-month forecast using 12 months of history
    """)
    
    # Tips
    st.subheader("💡 Tips")
    st.markdown("""
    - Use specific dates in YYYY-MM-DD format for best results
    - For employee-specific queries, include the employee ID
    - For forecasts, specify how many months of history to consider
    - The agent will ask for clarification if needed
    """)
    
    if not TOOLS_LOADED:
        st.warning("⚠️ Some features are limited due to database connection issues.")

# Main Chat Interface
if not agents_initialized:
    st.warning("Agent could not be initialized. Please check configuration and logs. UI is disabled.", icon="⚠️")
    st.stop()

# Display Chat History (now calls the function)
display_chat_messages()

# Chat Input
if user_input := st.chat_input("Ask about resource utilization...", disabled=not agents_initialized):
    # Add user message to history with timestamp
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": timestamp
    })
    
    # Get agent's response
    with st.spinner("🤖 Processing your request..."):
        try:
            # Prepare chat history for the agent
            chat_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            
            # Get agent's response content
            response_content = st.session_state.monitoring_agent.generate_reply(chat_history)
            
            # Append agent response to history if valid
            if isinstance(response_content, str):
                response_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response_content,
                    "timestamp": response_timestamp
                })
                logger.info(f"Appended agent response to session state: {response_content}")
            elif response_content is None:
                 logger.info("Agent returned None (likely termination). No message added.")
            else:
                # Handle unexpected response format if necessary
                logger.warning(f"Agent returned unexpected response format: {type(response_content)}")
                error_msg = format_error_message(f"Agent returned unexpected data: {response_content}")
                process_agent_response({"content": error_msg, "timestamp": datetime.datetime.now().strftime("%H:%M:%S")})

            # Force a rerun to update the display
            st.rerun()
            
        except Exception as e:
            logger.error(f"Error during chat: {e}", exc_info=True)
            error_msg = format_error_message(str(e))
            # Still use process_agent_response for error handling pathway
            process_agent_response({"content": error_msg, "timestamp": datetime.datetime.now().strftime("%H:%M:%S")})

# Display initial message if no conversation yet
if not st.session_state.messages:
    st.info("👋 Hello! I can help you analyze resource utilization and create forecasts. What would you like to know?")

st.divider()

def display_error(error_message: str):
    """Display an error message using Streamlit's error component"""
    st.error(error_message)

@contextmanager
def show_processing_spinner():
    """Context manager to show a spinner while processing"""
    with st.spinner('Processing...'):
        yield

def initialize_session_state():
    """Initialize session state variables if they don't exist."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "agent_manager" not in st.session_state:
        # Create function map for the tools
        function_map = {
            "analyze_utilization": analyze_utilization,
            "forecast_next_month_utilization": forecast_next_month_utilization
        }
        st.session_state.agent_manager = AgentCollaborationManager(function_map)

def forecast_next_month_utilization(num_history_months: int, current_date_str: str = None) -> str:
    """
    Forecasts next month's utilization based on historical data from Excel files.
    """
    try:
        # Get historical data
        history_df = get_monthly_utilization_history(num_history_months, current_date_str)
        if history_df is None or len(history_df) < 3:  # Need at least 3 months for reliable forecast
            return "Insufficient historical data. Need at least 3 months of history."
            
        # Calculate average utilization for the forecast window
        recent_utilization = history_df.tail(3)['monthly_utilization_rate'].mean()
        
        # Format the forecast result
        result = {
            "status": "success",
            "forecast": {
                "predicted_utilization": f"{recent_utilization:.2f}%",
                "confidence": "medium",
                "based_on_months": num_history_months,
                "forecast_period": "Next month"
            },
            "alerts": []
        }
        
        # Add alerts based on predictions
        if recent_utilization < 70:
            result["alerts"].append("⚠️ Forecast indicates potential underutilization")
        elif recent_utilization > 90:
            result["alerts"].append("🚨 Forecast indicates potential overutilization")
            
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in forecast_next_month_utilization: {e}")
        return f"Error generating forecast: {e}"

