import streamlit as st
import os
import sys
import logging
import json
from dotenv import load_dotenv

# --- Page Configuration MUST BE FIRST STREAMLIT COMMAND ---
st.set_page_config(
    page_title="Resource Monitoring Agent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --------------------------------------------------------

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# Add project root to sys.path to allow importing src modules
# Assuming app.py is in the project root
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
logger.info(f"Added {src_path} to sys.path")

# --- Load Environment Variables ---
load_dotenv()
logger.info(".env file loaded.")

# --- Import AutoGen and Project Modules ---
try:
    import autogen
    from src.db.query_functions import get_period_data, forecast_next_month_utilization
    logger.info("AutoGen and query functions imported successfully.")
except ImportError as e:
    logger.error(f"Error importing modules: {e}", exc_info=True)
    # Display error in Streamlit if possible, otherwise it will just be in logs
    st.error(f"Failed to import necessary modules. Check logs. Error: {e}")
    # We might want to stop here if imports fail critically
    # st.stop()
    # For now, let the rest of the UI load partially
    get_period_data = None
    forecast_next_month_utilization = None


# --- Helper Function to Get Config ---
def get_llm_config():
    # Fetch Azure configuration from environment variables
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
        # st.stop() # Stop execution if config is missing
        return None # Return None instead of stopping

    config_list = [{
        "model": azure_deployment_name,
        "api_key": azure_api_key,
        "base_url": azure_endpoint,
        "api_type": azure_api_type,
        "api_version": azure_api_version,
    }]
    # Return the config dict needed by AutoGen agents
    return {"config_list": config_list, "temperature": 0, "timeout": 600, "cache_seed": None}

# --- Define Tool Schemas ---
analyze_utilization_tool = {
    "type": "function", "function": { "name": "analyze_utilization", "description": "Analyzes resource utilization for a given date range and optional employee ID by querying charged hours, capacity hours, and target utilization from the database. Returns structured JSON.", "parameters": { "type": "object", "properties": { "start_date": { "type": "string", "description": "The start date for the analysis period in YYYY-MM-DD format." }, "end_date": { "type": "string", "description": "The end date for the analysis period in YYYY-MM-DD format." }, "employee_id": { "type": "string", "description": "Optional. The specific employee ID to analyze. If omitted, analyzes aggregate utilization." } }, "required": ["start_date", "end_date"] } }
}
forecast_utilization_tool = {
    "type": "function", "function": { "name": "forecast_next_month_utilization", "description": "Forecasts the next calendar month's resource utilization based on the average of a specified number of past months (forecast_window). Requires specifying how many total months of history (num_history_months) to fetch to calculate the average.", "parameters": { "type": "object", "properties": { "num_history_months": { "type": "integer", "description": "The total number of past months of historical data to retrieve." }, "current_date_str": { "type": "string", "description": "The current date (YYYY-MM-DD) used as the reference point for fetching history (history ends before this date's month)." }, "employee_id": { "type": "string", "description": "Optional. The specific employee ID to forecast for. If omitted, forecasts aggregate utilization." }, "forecast_window": { "type": "integer", "description": "Optional. The number of recent historical months (default 3) to average for the forecast.", "default": 3 } }, "required": ["num_history_months", "current_date_str"] } }
}

# --- Page Configuration ---
st.title("🤖 Resource Monitoring Agent Dashboard")
st.caption("Powered by AutoGen and Streamlit")

# --- Agent Initialization and Interaction ---

# Use session state to store conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages on rerun
for message in st.session_state.messages:
    avatar = "👤" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        # Handle potential JSON string in content for display
        try:
             # Basic check if it might be JSON before trying to parse
            if isinstance(message["content"], str) and message["content"].strip().startswith("{") and message["content"].strip().endswith("}"):
                 content_data = json.loads(message["content"])
                 st.json(content_data) # Display JSON nicely
            else:
                 st.markdown(message["content"]) # Display as Markdown
        except json.JSONDecodeError:
            st.markdown(message["content"]) # Display as is if not valid JSON
        except Exception as display_err: # Catch other potential errors during display
             logger.warning(f"Error displaying message content: {display_err}")
             st.markdown(str(message["content"])) # Fallback to string


# --- Sidebar Controls ---
st.sidebar.header("Controls")
user_input = st.sidebar.text_area("Enter your request for the agent:", height=100, key="user_input_area", help="Examples: 'Analyze utilization for April 2025', 'Forecast next month based on last 6 months, today is 2025-05-01'")
submit_button = st.sidebar.button("Submit Request", key="submit_button")


# --- Main Logic ---
if not (get_period_data and forecast_next_month_utilization):
     st.warning("Agent tools could not be loaded due to import errors. Please check logs.", icon="⚠️")
     st.stop()


if submit_button and user_input:
    st.sidebar.info("Initializing agents and processing request...")
    logger.info(f"User submitted request: {user_input}")

    # Add user message to history and display immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    llm_config = get_llm_config()
    if not llm_config:
        # Error displayed by get_llm_config
        st.stop()

    # Create agents for THIS RUN
    try:
        monitoring_agent_llm_config = llm_config.copy()
        monitoring_agent_llm_config["tools"] = [analyze_utilization_tool, forecast_utilization_tool]

        monitoring_agent = autogen.AssistantAgent(
            name="Monitoring_Agent",
            system_message="""You are a monitoring agent specializing in resource utilization analysis and forecasting.
Your tasks are:
1.  **Analyze Current Utilization:** Use the `analyze_utilization` tool. It returns a JSON string containing analysis details and an `alert_level` (NONE, INFO, WARNING, CRITICAL, ERROR).
2.  **Forecast Future Utilization:** Use the `forecast_next_month_utilization` tool. It returns a string describing the forecast or an error.
**Your Response Rules:**
*   When using `analyze_utilization`:
    *   Parse the JSON result provided by the tool.
    *   If the `alert_level` is `WARNING` or `CRITICAL`, format your response as an **ALERT** message, clearly stating the reason (e.g., 'Significantly Below Target', 'Zero Capacity') and including key details like Period, Employee (if applicable), Calculated Utilization, Target Utilization, and Deviation.
    *   If the `alert_level` is `INFO`, `NONE`, or `ERROR`, simply report the main message or status from the JSON result.
*   When using `forecast_next_month_utilization`:
    *   Report the exact string result provided by the tool.
*   Extract required parameters from the user request for the appropriate tool.
*   Call the correct tool based on the user's request (analysis vs. forecast).
*   If a tool itself fails or the JSON parsing fails, report the error encountered.
*   Do not perform calculations or forecasts yourself; rely solely on the tools' outputs.
*   After reporting the result/alert or error, conclude the conversation by replying with the word TERMINATE.""",
            llm_config=monitoring_agent_llm_config,
        )

        ui_user_proxy = autogen.UserProxyAgent(
            name="UI_User_Proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=8,
            is_termination_msg=lambda x: isinstance(x, dict) and "TERMINATE" in x.get("content", "").upper(),
            code_execution_config=False,
            llm_config=llm_config,
            function_map={
                "analyze_utilization": get_period_data,
                "forecast_next_month_utilization": forecast_next_month_utilization
            }
        )

        groupchat = autogen.GroupChat(
            agents=[ui_user_proxy, monitoring_agent],
            messages=[],
            max_round=10 # Reduced rounds slightly for UI responsiveness
        )
        manager = autogen.GroupChatManager(
            groupchat=groupchat,
            llm_config=llm_config
        )

        logger.info("Agents and Manager initialized for this run.")

        # Initiate chat
        with st.spinner("🤖 Thinking..."):
            try:
                ui_user_proxy.initiate_chat(
                    manager,
                    message=user_input,
                    clear_history=True
                )
                logger.info("Chat initiated and completed.")

                # --- Simplified Message Processing ---
                # Get the last message from the chat (usually the final response or termination)
                last_message = groupchat.messages[-1] if groupchat.messages else None
                
                if last_message and last_message.get("role") != "user": # Avoid echoing user input again
                    role_name = last_message.get("name", last_message.get("role"))
                    content = last_message.get("content", "")
                    # Add only the final agent message to the display history
                    st.session_state.messages.append({
                        "role": "assistant", # Label as assistant for display
                        "content": content # Display raw content (might include TERMINATE)
                    })
                elif not last_message: # Handle case where chat might have failed silently
                     st.session_state.messages.append({"role": "assistant", "content": "No response received from agent."})
                # --- End Simplified Message Processing ---
                
                # Clear the input box BEFORE rerun
                st.session_state.user_input_area = ""
                st.rerun()

            except Exception as e:
                 logger.error(f"Error during chat execution: {e}", exc_info=True)
                 st.error(f"An error occurred during agent interaction: {e}")
                 # Add error message to chat display
                 st.session_state.messages.append({"role": "assistant", "content": f"Error during chat: {e}"})
                 # Clear the input box BEFORE rerun
                 st.session_state.user_input_area = ""
                 st.rerun()

    except Exception as e:
        logger.error(f"Error initializing agents: {e}", exc_info=True)
        st.error(f"Failed to initialize agents. Error: {e}")
        # Add error message to chat display
        st.session_state.messages.append({"role": "assistant", "content": f"Error initializing agents: {e}"})
        # Clear the input box BEFORE rerun
        st.session_state.user_input_area = ""
        st.rerun()

elif not st.session_state.messages: # Only show if not processing and no messages displayed yet
     st.info("Enter a request in the sidebar and click Submit.")


# Add a divider at the end
st.divider()