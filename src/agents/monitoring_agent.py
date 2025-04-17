import sys
import pathlib
# Assuming the script is in src/agents, go up two levels to get the project root
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import os
import autogen
from dotenv import load_dotenv
# Import the new database query function
from src.db.query_functions import get_period_data, forecast_next_month_utilization
from autogen import AssistantAgent, UserProxyAgent
from autogen.agentchat import GroupChat, GroupChatManager
import pandas as pd
import logging
from typing import Optional # Import Optional for type hinting
import json # Import json for structured output

# Load environment variables
load_dotenv()

# --- Azure OpenAI Configuration ---
azure_endpoint = os.getenv("OPENAI_API_BASE")
azure_deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")
azure_api_version = os.getenv("OPENAI_API_VERSION")
azure_api_key = os.getenv("OPENAI_API_KEY")
azure_api_type = os.getenv("OPENAI_API_TYPE", "azure") # Default to azure if not specified

# Basic validation
missing_vars = []
if not azure_endpoint: missing_vars.append("OPENAI_API_BASE")
if not azure_deployment_name: missing_vars.append("OPENAI_DEPLOYMENT_NAME")
if not azure_api_version: missing_vars.append("OPENAI_API_VERSION")
if not azure_api_key: missing_vars.append("OPENAI_API_KEY")

if missing_vars:
    raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing_vars)}")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure logs go to stdout
    ]
)
logger = logging.getLogger(__name__)
logger.info("Azure OpenAI Configuration Loaded:")
logger.info(f"  Endpoint: {azure_endpoint}")
logger.info(f"  Deployment Name: {azure_deployment_name}")
logger.info(f"  API Version: {azure_api_version}")
logger.info(f"  API Type: {azure_api_type}")
logger.info(f"  API Key: {'********' + azure_api_key[-4:] if azure_api_key else 'Not Set'}")


# ------------------ Tool Definition & Function ------------------

# Define the tool schema for the LLM
analyze_utilization_tool = {
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
}

# Define the function that performs the analysis using database data
def analyze_utilization(start_date: str, end_date: str, employee_id: Optional[str] = None) -> str:
    """
    Analyzes utilization, compares to target, classifies deviation, 
    and returns a structured JSON string with analysis details and alert level.
    """
    SIGNIFICANT_DEVIATION_THRESHOLD = 5.0
    ALERT_THRESHOLD = SIGNIFICANT_DEVIATION_THRESHOLD # Alert if deviation exceeds this (absolute)
    
    result_data = {
        "status": "ERROR",
        "message": "Analysis did not complete.",
        "details": {},
        "alert_level": "NONE" # Levels: NONE, INFO, WARNING, CRITICAL
    }
    
    try:
        logger.info(f"Analyzing utilization for period {start_date} to {end_date}, Employee: {employee_id or 'All'}")
        charged_hours, capacity_hours, target_utilization_ratio = get_period_data(start_date, end_date, employee_id)

        result_data["details"]["period_start"] = start_date
        result_data["details"]["period_end"] = end_date
        result_data["details"]["employee_id"] = employee_id or "All"

        if capacity_hours <= 0:
            logger.warning("Capacity hours are zero or negative.")
            result_data["message"] = "Analysis Error: Capacity hours are zero or less, cannot calculate utilization."
            result_data["alert_level"] = "WARNING" 
            return json.dumps(result_data)

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
            elif abs(deviation) <= ALERT_THRESHOLD: # Use ALERT_THRESHOLD here
                deviation_status = "Slightly Below Target"
                result_data["alert_level"] = "WARNING"
            else:
                deviation_status = "Significantly Below Target"
                result_data["alert_level"] = "CRITICAL" # Set critical alert
                
            result_data["details"]["deviation_status"] = deviation_status
            result_data["message"] = f"Analysis successful. Status: {deviation_status}"
        else:
            result_data["details"]["target_utilization_pct"] = "Not found"
            result_data["details"]["deviation_status"] = "Cannot assess deviation (no target)"
            result_data["message"] = "Analysis successful, but no target found."
            result_data["alert_level"] = "INFO" # No target isn't necessarily an alert

        logger.info(f"Analysis complete. Alert Level: {result_data['alert_level']}")
        return json.dumps(result_data, indent=2)

    except Exception as e:
        logger.error(f"An unexpected error occurred during utilization analysis: {e}", exc_info=True)
        result_data["message"] = f"Unexpected Error: {e}"
        result_data["alert_level"] = "ERROR"
        return json.dumps(result_data)

# --- Tool 2: Forecast Utilization (New) ---
forecast_utilization_tool = {
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
}
# Note: The actual implementation `forecast_next_month_utilization` is imported from query_functions

# ------------------ Agent Setup ------------------

# Configure LLM settings for agents and manager
# Note: Define tool for the agent that needs to call it.
config_list = [
    {
        "model": azure_deployment_name,
        "api_key": azure_api_key,
        "base_url": azure_endpoint,
        "api_type": azure_api_type,
        "api_version": azure_api_version,
    }
]

# LLM config for the agent that will use the tool
agent_llm_config = {
    "config_list": config_list,
    "temperature": 0,
    "timeout": 600,
    "cache_seed": None, # Use None for non-deterministic calls
    "tools": [analyze_utilization_tool, forecast_utilization_tool], # Add new tool schema
}

# LLM config for the manager (does not need the tool definition itself)
manager_llm_config = {
    "config_list": config_list,
    "temperature": 0,
    "timeout": 600,
    "cache_seed": None,
}


# Create MonitoringAgent instance
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
    llm_config=agent_llm_config, # Use the config WITH tools
)

# Create UserProxyAgent instance (Updated Function Map)
user_proxy = autogen.UserProxyAgent(
   name="User_Proxy",
   human_input_mode="NEVER", # Agent executes functions without asking
   max_consecutive_auto_reply=10, # Limit consecutive replies
   # Check if the message content indicates termination
   is_termination_msg=lambda x: isinstance(x, dict) and "TERMINATE" in x.get("content", "").upper(),
   code_execution_config=False, # No code execution needed here
   # Register BOTH functions with the User Proxy agent
   function_map={
       "analyze_utilization": analyze_utilization, # Existing function
       "forecast_next_month_utilization": forecast_next_month_utilization # New function
   }
)


# ------------------ Group Chat Setup ------------------
groupchat = autogen.GroupChat(
    agents=[user_proxy, monitoring_agent],
    messages=[],
    max_round=12, # Maximum rounds of conversation
    speaker_selection_method="auto" # Auto-selects the next speaker
)

manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config=manager_llm_config, # Manager uses config without specific tools defined
)

# ------------------ Main Execution ------------------

if __name__ == "__main__":
    # Use a prompt that should trigger analysis, e.g., April 2025 
    # (assuming data exists, otherwise it will show the capacity error)
    initial_prompt = "Analyze the resource utilization between 2025-04-01 and 2025-04-30."

    logger.info(f"Initiating chat with prompt: '{initial_prompt}'")

    try:
        # Initiate the chat using the User Proxy Agent, triggering the group chat flow
        user_proxy.initiate_chat(
            manager,
            message=initial_prompt
        )
        logger.info("Chat finished successfully.")

    except autogen.oai.APIError as api_err:
        logger.error(f"Azure OpenAI API Error: {api_err}")
        logger.error(f"Check your Azure credentials, endpoint, deployment name, and API version in the .env file.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during chat execution: {e}", exc_info=True)

    logger.info("Script finished.")