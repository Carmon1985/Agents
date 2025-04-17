import sys
import pathlib
# Assuming the script is in src/agents, go up two levels to get the project root
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import os
import autogen
from dotenv import load_dotenv
# Import the new database query function
from src.db.query_functions import get_period_data
from autogen import AssistantAgent, UserProxyAgent
from autogen.agentchat import GroupChat, GroupChatManager
import pandas as pd
import logging
from typing import Optional # Import Optional for type hinting

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
    Analyzes utilization by fetching data from the database for a given period
    and optional employee, calculating the rate, and comparing it to the target.
    """
    try:
        logger.info(f"Analyzing utilization for period {start_date} to {end_date}, Employee: {employee_id or 'All'}")

        # Fetch data from the database
        charged_hours, capacity_hours, target_utilization_ratio = get_period_data(start_date, end_date, employee_id)

        # Perform calculations and comparisons
        if capacity_hours <= 0:
            logger.warning("Capacity hours are zero or negative. Cannot calculate utilization.")
            return "Analysis Error: Capacity hours are zero or less, cannot calculate utilization."

        utilization_rate = (charged_hours / capacity_hours) * 100
        result_str = f"Analysis Period: {start_date} to {end_date}"
        if employee_id:
            result_str += f" | Employee: {employee_id}"
        else:
            result_str += " | Employee: All"
        result_str += f"\nCharged Hours: {charged_hours:.2f}"
        result_str += f"\nCapacity Hours: {capacity_hours:.2f}"
        result_str += f"\nCalculated Utilization: {utilization_rate:.2f}%"

        if target_utilization_ratio is not None:
            target_percentage = target_utilization_ratio * 100
            result_str += f"\nTarget Utilization: {target_percentage:.2f}%"
            deviation = utilization_rate - target_percentage
            deviation_status = "Met/Exceeded" if deviation >= 0 else "Below Target"
            result_str += f"\nDeviation from Target: {deviation:.2f}% ({deviation_status})"
        else:
            result_str += "\nTarget Utilization: Not found"

        logger.info(f"Analysis complete. Result: {result_str}")
        return result_str

    except Exception as e:
        logger.error(f"An unexpected error occurred during utilization analysis: {e}", exc_info=True)
        return f"An unexpected error occurred during analysis: {e}"


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
    "tools": [analyze_utilization_tool], # Provide the tool schema here
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
    system_message="""You are a monitoring agent specializing in resource utilization analysis.
Your task is to analyze utilization based on provided date ranges (start_date, end_date) and an optional employee_id.
You must use the `analyze_utilization` tool to perform the analysis, which involves querying a database, calculating the utilization rate (charged hours / capacity hours), and comparing it to the target utilization.
Extract the required parameters (start_date, end_date, employee_id [optional]) from the user request.
Call the `analyze_utilization` tool with these parameters.
Report the full analysis result provided by the tool, including charged hours, capacity hours, calculated utilization, target utilization (if found), and deviation.
If the tool returns an error, report the error message.
Do not perform calculations yourself or make assumptions; rely solely on the tool's output.
After reporting the result or error, conclude the conversation by replying with the word TERMINATE.""",
    llm_config=agent_llm_config, # <<< Use the config WITH tools for this agent >>>
)

# Create UserProxyAgent instance (to execute the function)
user_proxy = autogen.UserProxyAgent(
   name="User_Proxy",
   human_input_mode="NEVER", # Agent executes functions without asking
   max_consecutive_auto_reply=10, # Limit consecutive replies
   # Check if the message content indicates termination
   is_termination_msg=lambda x: isinstance(x, dict) and "TERMINATE" in x.get("content", "").upper(),
   code_execution_config=False, # No code execution needed here
   # Register the *actual Python function* with the User Proxy agent
   # The key MUST match the function name defined in the tool schema
   function_map={
       "analyze_utilization": analyze_utilization
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
    # Example initial prompt asking for analysis within a date range
    initial_prompt = "Analyze the resource utilization between 2024-01-01 and 2024-01-31 for employee EMP001."
    # Alt prompt (all employees): "Analyze the resource utilization between 2024-02-01 and 2024-02-29."

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