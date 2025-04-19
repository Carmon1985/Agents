"""User proxy agent implementation."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging
from autogen import UserProxyAgent as AutoGenUserProxy

logger = logging.getLogger(__name__)

class UserProxyAgent(AutoGenUserProxy):
    """Agent that acts as a proxy for user interactions."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        """Initialize the user proxy agent."""
        super().__init__(
            name=name,
            llm_config=llm_config,
            system_message=system_message,
            **kwargs
        )
        self.tools = tools or []
        self._registered_tools = {}

    def register_tool(self, tool_name: str, tool_func: callable):
        """Register a tool that can be called by the agent."""
        logger.info(f"Registering tool: {tool_name}")
        self._registered_tools[tool_name] = tool_func

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process incoming messages and handle tool calls."""
        try:
            # Log incoming message
            logger.info(f"Processing message: {message[:100]}...")

            # Check for tool calls in the message
            if "TOOL_CALL:" in message:
                tool_name = message.split("TOOL_CALL:")[1].split()[0]
                if tool_name in self._registered_tools:
                    logger.info(f"Executing tool: {tool_name}")
                    try:
                        result = await self._registered_tools[tool_name](message)
                        return {
                            "status": "success",
                            "message": f"Tool {tool_name} executed successfully",
                            "result": result
                        }
                    except Exception as e:
                        logger.error(f"Tool execution failed: {str(e)}", exc_info=True)
                        return {
                            "status": "error",
                            "message": f"Tool execution failed: {str(e)}",
                            "error": str(e)
                        }
                else:
                    return {
                        "status": "error",
                        "message": f"Tool {tool_name} not found"
                    }

            # Process normal message with LLM
            response = await self._get_llm_response(message)
            return {
                "status": "success",
                "message": "Message processed successfully",
                "response": response
            }

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Message processing failed: {str(e)}",
                "error": str(e)
            }

    async def _get_llm_response(self, message: str) -> str:
        """Get response from LLM."""
        try:
            # TODO: Implement actual LLM call here
            # For now, return a mock response
            return f"Processed message: {message}"
        except Exception as e:
            logger.error(f"LLM response generation failed: {str(e)}", exc_info=True)
            raise

    async def _llm_generate(self, message: str) -> Dict[str, Any]:
        """Generate a response using the LLM."""
        # TODO: Implement actual LLM call
        return {
            "content": "This is a mock response",
            "role": "assistant",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        } 