import autogen
import logging
import sys
import os
import datetime
from dotenv import load_dotenv

# --- Load Environment Variables ---
# Load variables from .env file into environment
load_dotenv()

# --- Path Setup ---
# Add project root to the Python path
# This allows us to import modules like src.db.tools
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.db import tools as db_tools
except ImportError as e:
    logging.error(f"Error importing db_tools: {e}. Ensure the project structure is correct and dependencies are installed.")
    # Handle the error appropriately, maybe exit or raise
    raise

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Agent Configuration ---

MONITORING_AGENT_SYSTEM_PROMPT = """You are the Performance Monitoring Agent.
Your primary responsibilities are:
1.  **Query Data:** Use the provided database tool functions (`get_performance_data`, `get_targets`, `get_employee_data`, `get_project_data`, `calculate_utilization`) to retrieve relevant performance metrics, targets, and contextual data based on user requests or scheduled checks.
2.  **Analyze & Compare:** Analyze the retrieved data. Compare current performance against targets and historical data (e.g., previous month, same period last year). Calculate key metrics like utilization and month-over-month changes.
3.  **Identify Deviations:** Identify significant deviations from targets or historical norms based on predefined or adaptable thresholds. Correlate segment performance issues with potentially impacted projects or employees using available data.
4.  **Forecast Trends:** Perform simple trend analysis or forecasting based on historical performance data.
5.  **Generate Alerts:** Generate clear, structured alerts summarizing significant findings, deviations, potential risks, or trends. Include relevant context and data points in your alerts.
6.  **Leverage History:** You MUST actively use the conversation history and your memory of past analyses to provide context, track trends over time, and avoid redundant calculations or questions. Refer to previous results when relevant (e.g., "Last month's utilization was X, this month it is Y"). Ask clarifying questions if the request is ambiguous or lacks necessary parameters (like date ranges).

You have access to the following database tool functions:
- `get_performance_data(start_date: str, end_date: str, employee_id: str | None = None, project_id: str | None = None)`
- `get_targets(year: int | None = None, month: int | None = None, employee_id: str | None = None)`
- `get_employee_data(employee_id: str | None = None, segment: str | None = None)`
- `get_project_data(project_id: str | None = None, manager_id: str | None = None)`
- `calculate_utilization(start_date: str, end_date: str, employee_id: str | None = None)`

Execute queries precisely as requested. When performing comparisons or analyses, clearly state the period you are analyzing. Always check if you have sufficient historical context from the conversation before asking for it or re-querying extensively. Structure your findings logically.
"""

# TODO: Load LLM Config from a central place (e.g., OAI_CONFIG_LIST)
# For now, using a placeholder. Replace with your actual config loading.
# config_list = autogen.config_list_from_json(
#     "OAI_CONFIG_LIST",
#     filter_dict={
#         "model": ["gpt-4", "gpt-3.5-turbo"], # Example models
#     },
# )

# Placeholder config - replace with actual OpenAI or other LLM config
llm_config = {
    "config_list": [{"model": "gpt-4", "api_key": os.environ.get("OPENAI_API_KEY")}],
    "temperature": 0.7,
    # Add other relevant LLM parameters like timeout, cache_seed, etc.
}


# --- Agent Definition ---
monitoring_agent = autogen.AssistantAgent(
    name="Monitoring_Agent",
    system_message=MONITORING_AGENT_SYSTEM_PROMPT,
    llm_config=llm_config,
    # Ensure agent can execute function calls
    # function_map is deprecated, use register_function instead
)

# --- Register Database Tools ---
# Make the db tool functions available to the agent
monitoring_agent.register_function(
    function_map={
        "get_performance_data": db_tools.get_performance_data,
        "get_targets": db_tools.get_targets,
        "get_employee_data": db_tools.get_employee_data,
        "get_project_data": db_tools.get_project_data,
        "calculate_utilization": db_tools.calculate_utilization,
    }
)

# --- Agent Usage and Interaction Setup ---
if __name__ == "__main__":
    logger.info("Setting up agent interaction...")

    # Create a UserProxyAgent to interact with the MonitoringAgent
    # This agent can execute function calls made by the assistant
    user_proxy = autogen.UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER", # Don't require human input during this automated test
        max_consecutive_auto_reply=10,
        is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
        # The UserProxyAgent needs to be able to execute the functions
        # called by the MonitoringAgent. We register them here too.
        function_map={
            "get_performance_data": db_tools.get_performance_data,
            "get_targets": db_tools.get_targets,
            "get_employee_data": db_tools.get_employee_data,
            "get_project_data": db_tools.get_project_data,
            "calculate_utilization": db_tools.calculate_utilization,
        },
        # Alternatively, configure code execution if functions require it
        # code_execution_config={"work_dir": "_agent_output"}, 
        llm_config=llm_config # Can optionally have its own LLM config
    )

    logger.info("Initiating chat...")
    # Example Chat: Ask the monitoring agent to perform a calculation
    initial_message = "Calculate utilization for employee 'emp1' between 2024-01-01 and 2024-01-31."

    user_proxy.initiate_chat(
        monitoring_agent,
        message=initial_message
    )

    logger.info("Chat finished.") 