import autogen
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class UIAgent(autogen.AssistantAgent):
    """UI Agent specializing in user interaction and delegation to Tool Agent."""
    
    def __init__(self, name: str = "UI Assistant"):
        system_message = """You are a helpful UI agent that:
1. Understands user requests and maintains conversation context
2. **Immediately delegates** tool execution to the Tool Agent when needed
3. Formats final responses in a user-friendly way

**Delegation Rules (Strict):**
- **IF** the user asks about resource utilization (e.g., "show utilization", "what is the utilization?"), **YOU MUST** respond by asking the Tool Agent to run `analyze_utilization`. Extract the number of months if provided (default to 1 if not specified).
- **IF** the user asks about forecasts (e.g., "forecast utilization", "what is the prediction?"), **YOU MUST** respond by asking the Tool Agent to run `forecast_next_month_utilization`. Extract the number of history months if provided (default to 3 if not specified).
- **DO NOT** ask the user for clarification on parameters like dates. The Tool Agent handles the specifics.
- **ALWAYS** format your delegation request starting with `@Tool Agent, please run ...`

**Example Delegation Responses:**
User: "Show me last month's utilization"
You: "@Tool Agent, please run `analyze_utilization` with num_history_months=1"

User: "What's the forecast based on 6 months history?"
You: "@Tool Agent, please run `forecast_next_month_utilization` with num_history_months=6"

User: "Analyze resource usage."
You: "@Tool Agent, please run `analyze_utilization` with num_history_months=1"

After receiving the result from the Tool Agent, format it clearly for the user, including any alerts provided.
Always maintain a helpful and professional tone."""

        super().__init__(
            name=name,
            system_message=system_message,
            llm_config={
                "temperature": 0.7,
                "request_timeout": 300,
                "functions": None  # Explicitly disable function calling capability
            }
        )

class ToolAgent(autogen.AssistantAgent):
    """Tool Agent specializing in executing tools and handling technical details."""
    
    def __init__(self, name: str = "Tool Agent", function_map: Optional[Dict] = None):
        system_message = """You are a technical Tool Agent that:
1. Validates and executes tool requests from the UI Agent
2. Understands all tool parameters and constraints
3. Returns well-formatted results
4. Can suggest corrections to the UI Agent if requests are invalid

Available Tools:
1. analyze_utilization(num_history_months: int) -> str
   - Analyzes resource utilization for the specified number of months
   - num_history_months must be a positive integer
   - Returns JSON string with utilization metrics

2. forecast_next_month_utilization(num_history_months: int, current_date_str: str = None) -> str
   - Forecasts next month's utilization based on historical data
   - num_history_months must be a positive integer
   - current_date_str is optional, format: "YYYY-MM-DD"
   - Returns JSON string with forecast metrics

When executing tools:
1. Validate all parameters before execution
2. Format results clearly with appropriate alerts
3. If there are errors, explain them clearly to the UI Agent

Response Format:
{
    "status": "success" | "error",
    "tool": "tool_name",
    "result": {...} | "error message",
    "alerts": ["alert1", "alert2"] | []
}

Example interaction:
UI Agent: "Please analyze utilization for the last month"
You: *Executes analyze_utilization(num_history_months=1) and formats response*

UI Agent: "Run forecast with invalid parameter"
You: "Error: num_history_months must be a positive integer. Please provide a valid value."

Always validate inputs and provide clear error messages when needed."""

        super().__init__(
            name=name,
            system_message=system_message,
            llm_config={
                "temperature": 0.7,
                "request_timeout": 300,
                "functions": [
                    {
                        "name": "analyze_utilization",
                        "description": "Analyze resource utilization for specified months",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "num_history_months": {
                                    "type": "integer",
                                    "description": "Number of months of history to analyze"
                                }
                            },
                            "required": ["num_history_months"]
                        }
                    },
                    {
                        "name": "forecast_next_month_utilization",
                        "description": "Forecast next month utilization based on history",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "num_history_months": {
                                    "type": "integer",
                                    "description": "Number of months of history to use"
                                },
                                "current_date_str": {
                                    "type": "string",
                                    "description": "Current date in YYYY-MM-DD format"
                                }
                            },
                            "required": ["num_history_months"]
                        }
                    }
                ]
            }
        )
        # Set the function map if provided
        if function_map:
            self.function_map = function_map

class AgentCollaborationManager:
    """Manages collaboration between UI and Tool agents."""
    
    def __init__(self, function_map: Dict[str, Any]):
        # Create the agents
        self.ui_agent = UIAgent()
        self.tool_agent = ToolAgent()
        self.executor_agent = autogen.UserProxyAgent(
            name="ExecutorAgent",
            human_input_mode="NEVER",
            code_execution_config=False,
            function_map=function_map
        )

        # Configure the group chat
        self.group_chat = autogen.GroupChat(
            agents=[self.ui_agent, self.tool_agent, self.executor_agent],
            messages=[],
            max_round=5
        )
        
        # Create the group chat manager
        self.manager = autogen.GroupChatManager(
            groupchat=self.group_chat,
            llm_config={"temperature": 0.7, "request_timeout": 300}
        )
        
    async def process_user_message(self, messages: List[Dict[str, str]]) -> str:
        """
        Process a user message through the agent collaboration system.
        Args: messages: List of message dictionaries with 'role' and 'content'
        Returns: str: Final response to show to the user
        """
        last_user_message = messages[-1]["content"]
        logger.info(f"Processing user message: {last_user_message}")
        
        try:
            # Reset the group chat messages
            self.group_chat.messages = []
            
            # Start the group chat with the user's message
            # The UI Agent will speak first (due to being first in the agents list)
            await self.executor_agent.a_initiate_chat(
                self.manager,
                message=last_user_message,
                clear_history=True
            )
            
            # Get the final response from the chat history
            chat_messages = self.group_chat.messages
            if not chat_messages:
                return "I apologize, but no response was generated."
            
            # Find the last message from any agent (preferably UI Agent)
            final_message = None
            for msg in reversed(chat_messages):
                if msg.get("role") == "assistant":
                    if msg.get("name") == self.ui_agent.name:
                        # Prefer UI Agent's message
                        final_message = msg.get("content")
                        break
                    elif final_message is None:
                        # Take any agent's message if UI Agent's not found
                        final_message = msg.get("content")
            
            if final_message:
                logger.info(f"Final response from group chat: {final_message}")
                return final_message
            else:
                return "I apologize, but I couldn't generate a proper response."
            
        except Exception as e:
            logger.error(f"Error in agent collaboration: {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error during processing: {str(e)}" 