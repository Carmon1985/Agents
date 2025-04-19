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
from typing import Optional, Dict, Any, List, Tuple
import json # Import json for structured output
from datetime import datetime, timedelta
import numpy as np
from scipy import stats

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
   # Updated lambda to safely handle None content
   is_termination_msg=lambda x: isinstance(x, dict) and isinstance(x.get("content"), str) and "TERMINATE" in x.get("content", "").upper(),
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

class MonitoringAgent(autogen.AssistantAgent):
    """Agent that monitors system resources and generates alerts."""

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        deviation_thresholds: Optional[Dict[str, float]] = None,
        name: str = "MonitoringAgent",
        system_message: Optional[str] = None,
        **kwargs
    ):
        """Initialize the MonitoringAgent with configuration and thresholds.

        Args:
            llm_config (Optional[Dict[str, Any]]): Configuration for the LLM. Must contain 'config_list'.
            deviation_thresholds (Optional[Dict[str, float]]): Thresholds for deviation alerts.
                Must include 'critical' and 'warning' keys with positive float values.
            name (str): Name of the agent. Defaults to "MonitoringAgent".
            system_message (Optional[str]): System message for the agent.
            **kwargs: Additional arguments passed to the parent class.
        
        Raises:
            ValueError: If llm_config or deviation_thresholds are invalid.
        """
        # Initialize metrics cache
        self.metrics_cache = {}

        # Validate llm_config
        if not isinstance(llm_config, dict):
            raise ValueError("llm_config must be a dictionary containing 'config_list'")
        if 'config_list' not in llm_config:
            raise ValueError("llm_config must be a dictionary containing 'config_list'")
        if not llm_config['config_list']:
            raise ValueError("llm_config must be a dictionary containing 'config_list'")

        # Set default thresholds
        default_thresholds = {
            "critical": 10.0,
            "warning": 5.0,
            "z_score": 2.0,
            "trend": 0.1,
            "correlation": 0.7
        }

        # Validate deviation_thresholds if provided
        if deviation_thresholds is not None:
            if not isinstance(deviation_thresholds, dict):
                raise ValueError("deviation_thresholds must be a dictionary")
            
            # Check for required keys
            for key in ["critical", "warning"]:
                if key not in deviation_thresholds:
                    raise ValueError(f"Missing required threshold key: {key}")
                
                # Validate threshold values
                if not isinstance(deviation_thresholds[key], (int, float)):
                    raise ValueError(f"Invalid value for {key} threshold: must be a positive number")
                if deviation_thresholds[key] <= 0:
                    raise ValueError(f"Invalid value for {key} threshold: must be a positive number")
            
            # Update default thresholds with provided values
            default_thresholds.update(deviation_thresholds)

        self.deviation_thresholds = default_thresholds

        # Initialize parent class with validated config
        super().__init__(
            name=name,
            llm_config=llm_config,
            system_message=system_message or "I am a monitoring agent that analyzes resource utilization and generates alerts.",
            **kwargs
        )

    def detect_statistical_deviation(
        self,
        current_value: float,
        historical_values: List[float]
    ) -> Dict[str, Any]:
        """
        Detect statistical deviations using z-score and historical context.
        
        Args:
            current_value: The current metric value
            historical_values: List of historical values for the metric
            
        Returns:
            Dictionary containing deviation analysis results
        """
        if not historical_values:
            return {
                "deviation_detected": False,
                "reason": "Insufficient historical data",
                "score": 0.0
            }
            
        # Calculate basic statistics
        mean = np.mean(historical_values)
        std = np.std(historical_values)
        
        if std == 0:
            return {
                "deviation_detected": False,
                "reason": "No variation in historical data",
                "score": 0.0
            }
            
        # Calculate z-score
        z_score = (current_value - mean) / std
        
        # Determine if this is a significant deviation
        is_significant = bool(abs(z_score) > self.deviation_thresholds["z_score"])
        
        # Calculate deviation score (0-10 scale)
        score = min(10.0, abs(z_score) * (10.0 / self.deviation_thresholds["z_score"]))
        
        return {
            "deviation_detected": is_significant,
            "z_score": z_score,
            "score": score,
            "mean": mean,
            "std": std,
            "reason": f"Z-score of {z_score:.2f} {'exceeds' if is_significant else 'within'} threshold"
        }
        
    def detect_trend_deviation(
        self,
        values: List[float],
        dates: List[datetime]
    ) -> Dict[str, Any]:
        """
        Detect deviations in trend using linear regression.
        
        Args:
            values: List of metric values
            dates: List of corresponding dates
            
        Returns:
            Dictionary containing trend analysis results
        """
        if len(values) < 3:  # Need at least 3 points for meaningful trend
            return {
                "trend_detected": False,
                "reason": "Insufficient data points",
                "score": 0.0
            }
            
        # Validate dates are in chronological order
        for i in range(1, len(dates)):
            if dates[i] <= dates[i-1]:
                raise ValueError("Dates must be in chronological order")
            
        # Convert dates to numeric values (days since first date)
        days = [(d - dates[0]).days for d in dates]
        
        # Perform linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(days, values)
        
        # Calculate trend score based on slope significance and R² value
        r_squared = r_value ** 2
        trend_score = min(10.0, abs(slope) * 100 * r_squared)
        
        # Determine if trend is significant
        is_significant = bool(
            abs(slope) > self.deviation_thresholds["trend"] and
            p_value < 0.05 and
            r_squared > 0.6
        )
        
        return {
            "trend_detected": is_significant,
            "slope": slope,
            "r_squared": r_squared,
            "p_value": p_value,
            "score": trend_score,
            "direction": "increasing" if slope > 0 else "decreasing",
            "reason": f"{'Significant' if is_significant else 'No significant'} trend detected (slope: {slope:.4f}, R²: {r_squared:.2f})"
        }
        
    def detect_metric_correlations(
        self,
        metric_data: Dict[str, List[float]]
    ) -> List[Dict[str, Any]]:
        """
        Detect correlations between different metrics.
        
        Args:
            metric_data: Dictionary of metric names to their values
            
        Returns:
            List of significant correlations found
        """
        correlations = []
        metrics = list(metric_data.keys())
        
        if not metrics:
            return correlations
            
        # Validate all metrics have the same number of values
        first_metric_len = len(metric_data[metrics[0]])
        for metric in metrics[1:]:
            if len(metric_data[metric]) != first_metric_len:
                raise ValueError("All metrics must have the same number of values")
        
        for i in range(len(metrics)):
            for j in range(i + 1, len(metrics)):
                metric1, metric2 = metrics[i], metrics[j]
                values1, values2 = metric_data[metric1], metric_data[metric2]
                
                # Calculate correlation coefficient
                correlation = np.corrcoef(values1, values2)[0, 1]
                
                # Check if correlation is significant
                if abs(correlation) >= self.deviation_thresholds["correlation"]:
                    correlations.append({
                        "metrics": (metric1, metric2),
                        "correlation": correlation,
                        "strength": "strong positive" if correlation > 0 else "strong negative",
                        "score": abs(correlation) * 10  # Scale to 0-10
                    })
                    
        return correlations
        
    def _determine_alert_level(self, statistical_analysis: Dict[str, Any], trend_analysis: Dict[str, Any]) -> str:
        """
        Determine alert level based on statistical and trend analyses.
        
        Args:
            statistical_analysis: Results from statistical deviation analysis
            trend_analysis: Results from trend deviation analysis
            
        Returns:
            Alert level ("CRITICAL", "WARNING", or None)
        """
        # Check scores from both analyses
        stat_score = statistical_analysis.get("score", 0.0)
        trend_score = trend_analysis.get("score", 0.0)
        max_score = max(stat_score, trend_score)
        
        # Determine alert level based on thresholds
        if max_score >= self.deviation_thresholds["critical"]:
            return "CRITICAL"
        elif max_score >= self.deviation_thresholds["warning"]:
            return "WARNING"
        
        return None
        
    async def analyze_deviations(self, resource_id: str, current_metrics: dict, historical_metrics: dict, dates: list) -> dict:
        """
        Analyze deviations in metrics for a given resource.
        
        Args:
            resource_id (str): Identifier for the resource being analyzed
            current_metrics (dict): Current metric values
            historical_metrics (dict): Historical metric values
            dates (list): List of dates corresponding to historical metrics
            
        Returns:
            dict: Analysis results including statistical deviations, trends, and correlations
        """
        try:
            # Validate input
            if not resource_id or not isinstance(resource_id, str):
                return {
                    "status": "error",
                    "message": "Missing required metrics or resource ID",
                    "resource_id": resource_id
                }
                
            required_metrics = ["utilization", "charged_hours", "capacity_hours", "target_utilization"]
            if not all(metric in current_metrics for metric in required_metrics):
                return {
                    "status": "error",
                    "message": "Missing required metrics in current data",
                    "resource_id": resource_id
                }
            
            if not all(metric in historical_metrics for metric in required_metrics):
                return {
                    "status": "error",
                    "message": "Missing required metrics in historical data",
                    "resource_id": resource_id
                }
                
            # Check for empty historical data
            if not any(historical_metrics.values()):
                return {
                    "status": "error",
                    "message": "Insufficient historical data for analysis",
                    "resource_id": resource_id
                }
            
            # Initialize result structure
            result = {
                "status": "success",
                "resource_id": resource_id,
                "metric_analyses": {},
                "correlations": [],
                "alert_level": "normal"
            }
            
            overall_max_score = 0.0
            
            # Analyze each metric
            for metric in required_metrics:
                current_value = current_metrics[metric]
                historical_values = historical_metrics[metric]
                
                # Skip analysis if insufficient data
                if len(historical_values) < 2:
                    continue
                
                # Perform statistical analysis
                stat_analysis = self.detect_statistical_deviation(current_value, historical_values)
                
                # Perform trend analysis
                trend_analysis = self.detect_trend_deviation(historical_values + [current_value], dates + [datetime.now()])
                
                # Determine alert level for this metric
                alert_level = self._determine_alert_level(stat_analysis, trend_analysis)
                
                # Update overall max score
                stat_score = stat_analysis.get("score", 0.0)
                trend_score = trend_analysis.get("score", 0.0)
                metric_max_score = max(stat_score, trend_score)
                overall_max_score = max(overall_max_score, metric_max_score)
                
                # Store analysis results for this metric
                result["metric_analyses"][metric] = {
                    "statistical": stat_analysis,
                    "trend": trend_analysis,
                    "alert_level": alert_level,
                    "statistical_analysis": {
                        "reason": stat_analysis.get("reason", "Statistical analysis completed")
                    }
                }
            
            # Perform correlation analysis if sufficient data points
            if len(dates) >= 5:
                metric_data = {metric: historical_metrics[metric] + [current_metrics[metric]] 
                             for metric in required_metrics}
                correlations = self.detect_metric_correlations(metric_data)
                result["correlations"] = correlations
            
            # Set overall alert level based on max score
            if overall_max_score >= self.deviation_thresholds["critical"]:
                result["alert_level"] = "critical"
            elif overall_max_score >= self.deviation_thresholds["warning"]:
                result["alert_level"] = "warning"
            else:
                result["alert_level"] = "normal"
            
            return result
            
        except Exception as e:
            logging.error(f"Error in analyze_deviations: {str(e)}")
            return {
                "status": "error",
                "message": f"Error analyzing deviations: {str(e)}",
                "resource_id": resource_id
            }

    async def generate_alerts(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate alerts based on analysis results.

        Args:
            analysis_results: Dictionary containing analysis results

        Returns:
            List of alert dictionaries sorted by priority (CRITICAL > WARNING > INFO)
        """
        alerts = []
        
        # Return empty list if analysis failed or has no results
        if not analysis_results or analysis_results.get("status") != "success":
            return alerts
            
        # Process metric deviations
        metric_analyses = analysis_results.get("metric_analyses", {})
        for metric_name, analysis in metric_analyses.items():
            alert_level = analysis.get("alert_level")
            if alert_level in ["CRITICAL", "WARNING"]:
                reason = analysis.get('statistical_analysis', {}).get('reason', 'Significant deviation detected')
                alerts.append({
                    "level": alert_level,
                    "metric": metric_name,
                    "message": f"{alert_level} alert for {metric_name}: {reason}",
                    "details": analysis
                })
                
        # Process correlations
        correlations = analysis_results.get("correlations", [])
        for correlation in correlations:
            if correlation.get("score", 0) >= 7.0:  # High correlation threshold
                metric1, metric2 = correlation.get("metrics", ("", ""))
                correlation_value = correlation.get('correlation', 0)
                alerts.append({
                    "level": "INFO",
                    "metric": f"{metric1}-{metric2}",
                    "message": f"Strong correlation detected between {metric1} and {metric2} (correlation: {correlation_value:.2f})",
                    "details": correlation
                })
                
        # Sort alerts by priority (CRITICAL > WARNING > INFO)
        priority_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        alerts.sort(key=lambda x: priority_order[x["level"]])
        
        return alerts

    async def get_current_metrics(self, resource_id: str) -> Dict[str, float]:
        """Get current metrics for a given resource."""
        try:
            # For testing purposes, if no data is available, return empty dict
            if not resource_id:
                return {}
                
            # Get period data
            charged_hours, capacity_hours, target_ratio = get_period_data(
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                resource_id if resource_id != "all" else None
            )
            
            # If any of the values are None, return empty dict
            if any(v is None for v in [charged_hours, capacity_hours, target_ratio]):
                return {}
            
            # Calculate utilization
            utilization = (charged_hours / capacity_hours) * 100 if capacity_hours > 0 else 0
            target_utilization = target_ratio * 100 if target_ratio else 0
            
            return {
                "utilization": utilization,
                "charged_hours": charged_hours,
                "capacity_hours": capacity_hours,
                "target_utilization": target_utilization
            }
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {}

    async def _fetch_metrics(self) -> Dict[str, float]:
        """Fetch current metrics from the monitoring system."""
        # Mock implementation for testing
        return {}

    async def _fetch_historical_metrics(self, resource_id: str, start_date: datetime, end_date: datetime) -> Tuple[Dict[str, List[float]], List[datetime]]:
        """Fetch historical metrics from the monitoring system."""
        # Mock implementation for testing
        return {}, []

    async def get_historical_metrics(
        self,
        resource_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[Dict[str, List[float]], List[datetime]]:
        """
        Get historical metric values for a resource.
        
        Args:
            resource_id: Identifier for the resource (employee_id)
            start_date: Start date for historical data
            end_date: End date for historical data
            
        Returns:
            Tuple containing a dictionary of metrics and a list of dates
        """
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")
            
        try:
            historical_metrics = {}
            dates = []
            
            # Collect monthly data points
            current_date = start_date
            while current_date <= end_date:
                month_end = min(
                    (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                    end_date
                )
                
                # Format dates for query
                start_str = current_date.strftime("%Y-%m-%d")
                end_str = month_end.strftime("%Y-%m-%d")
                
                # Query utilization data for this month
                charged_hours, capacity_hours, target_ratio = get_period_data(
                    start_str,
                    end_str,
                    resource_id if resource_id != "all" else None
                )
                
                # Calculate utilization for this month
                if capacity_hours and capacity_hours > 0:
                    utilization = (charged_hours / capacity_hours) * 100
                    
                    # Initialize metric lists if not already done
                    if "utilization" not in historical_metrics:
                        historical_metrics["utilization"] = []
                    if "charged_hours" not in historical_metrics:
                        historical_metrics["charged_hours"] = []
                    if "capacity_hours" not in historical_metrics:
                        historical_metrics["capacity_hours"] = []
                    if "target_utilization" not in historical_metrics:
                        historical_metrics["target_utilization"] = []
                    
                    # Add values to respective lists
                    historical_metrics["utilization"].append(utilization)
                    historical_metrics["charged_hours"].append(charged_hours)
                    historical_metrics["capacity_hours"].append(capacity_hours)
                    historical_metrics["target_utilization"].append(target_ratio * 100 if target_ratio else 0)
                    dates.append(current_date)
                
                # Move to next month
                current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            
            return historical_metrics, dates
            
        except Exception as e:
            logger.error(f"Error getting historical metrics for resource {resource_id}: {str(e)}")
            raise

    async def forecast_performance(
        self,
        resource_id: str,
        num_history_months: int = 6,
        forecast_window: int = 3
    ) -> Dict[str, Any]:
        """
        Forecast future performance metrics using historical data.
        
        Args:
            resource_id: Identifier for the resource to forecast for
            num_history_months: Number of months of historical data to use
            forecast_window: Number of recent months to use for the forecast calculation
            
        Returns:
            Dictionary containing forecast results and confidence metrics
        """
        try:
            # Calculate date ranges
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30 * num_history_months)
            
            # Get historical metrics
            historical_metrics, dates = await self.get_historical_metrics(resource_id, start_date, end_date)
            
            if not historical_metrics or not dates:
                return {
                    "status": "error",
                    "error": "No historical data available for forecasting"
                }
            
            # Get utilization data for forecasting
            if "utilization" not in historical_metrics:
                return {
                    "status": "error",
                    "error": "Utilization data not available for forecasting"
                }
                
            utilization_data = historical_metrics["utilization"]
            
            if len(utilization_data) < forecast_window:
                return {
                    "status": "error",
                    "error": f"Insufficient data for forecasting. Need at least {forecast_window} months of history."
                }
            
            # Calculate trend using linear regression
            x = np.array(range(len(dates))).reshape(-1, 1)
            y = np.array(utilization_data)
            model = stats.linregress(x.flatten(), y)
            
            # Extract model parameters
            slope = model.slope
            intercept = model.intercept
            r_value = model.rvalue
            p_value = model.pvalue
            std_error = model.stderr
            
            # Calculate forecast
            next_month_index = len(dates)
            forecast_value = slope * next_month_index + intercept
            
            # Calculate confidence metrics
            r_squared = r_value ** 2
            
            # Calculate prediction interval (95% confidence)
            confidence_interval = 1.96 * std_error
            
            # Determine forecast reliability
            reliability = "high" if r_squared > 0.7 else "medium" if r_squared > 0.5 else "low"
            
            # Format forecast date range
            next_month_start = (end_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            next_month_end = (next_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            return {
                "status": "success",
                "resource_id": resource_id,
                "forecast_period": {
                    "start": next_month_start.strftime("%Y-%m-%d"),
                    "end": next_month_end.strftime("%Y-%m-%d")
                },
                "forecast": {
                    "value": round(forecast_value, 2),
                    "confidence_interval": round(confidence_interval, 2),
                    "lower_bound": round(max(0, forecast_value - confidence_interval), 2),
                    "upper_bound": round(min(100, forecast_value + confidence_interval), 2)
                },
                "reliability": {
                    "level": reliability,
                    "r_squared": round(r_squared, 3),
                    "std_error": round(std_error, 3)
                },
                "trend": {
                    "slope": round(slope, 3),
                    "direction": "increasing" if slope > 0 else "decreasing",
                    "significance": "significant" if abs(slope) > self.deviation_thresholds["trend"] and p_value < 0.05 else "not significant"
                },
                "historical_data_points": len(utilization_data)
            }
        except Exception as e:
            logger.error(f"Error forecasting performance for resource {resource_id}: {str(e)}")
            return {
                "status": "error",
                "error": f"Error forecasting performance: {str(e)}"
            }