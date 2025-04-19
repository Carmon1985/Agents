import pytest
from unittest.mock import Mock, patch
import json
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import from the correct path within src
from src.agents.user_proxy_agent import UserProxyAgent

class TestUserProxyAgent:
    @pytest.fixture
    def mock_llm_config(self):
        """Mock LLM configuration"""
        return {
            "config_list": [{
                "model": "test-deployment",
                "api_key": "test-key",
                "base_url": "https://test.openai.azure.com/",
                "api_type": "azure",
                "api_version": "2024-02-15",
            }],
            "temperature": 0,
            "timeout": 600,
            "cache_seed": None
        }

    @pytest.fixture
    def user_proxy_agent(self, mock_llm_config):
        """Create a UserProxyAgent instance for testing"""
        return UserProxyAgent(
            name="test_user_proxy",
            llm_config=mock_llm_config,
            system_message="You are a test agent"
        )

    def test_agent_initialization(self, user_proxy_agent, mock_llm_config):
        """Test agent initialization"""
        assert user_proxy_agent.name == "test_user_proxy"
        assert user_proxy_agent.llm_config == mock_llm_config
        assert "You are a test agent" in user_proxy_agent.system_message

    @pytest.mark.asyncio
    async def test_message_processing(self, user_proxy_agent):
        """Test message processing"""
        test_message = "Test user message"
        
        # Mock the LLM response
        mock_response = {
            "content": "Test response",
            "role": "assistant"
        }
        
        with patch.object(user_proxy_agent, '_llm_generate') as mock_generate:
            mock_generate.return_value = mock_response
            response = await user_proxy_agent.process_message(test_message)
            
            assert response["content"] == "Test response"
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_execution(self, user_proxy_agent):
        """Test tool execution handling"""
        # Mock a tool call response from LLM
        tool_response = {
            "tool_calls": [{
                "function": {
                    "name": "test_tool",
                    "arguments": json.dumps({
                        "param1": "value1",
                        "param2": "value2"
                    })
                }
            }]
        }
        
        # Mock the tool execution
        mock_tool = Mock(return_value={"result": "success"})
        user_proxy_agent.register_tool("test_tool", mock_tool)
        
        with patch.object(user_proxy_agent, '_llm_generate') as mock_generate:
            mock_generate.return_value = tool_response
            response = await user_proxy_agent.process_message("Execute test tool")
            
            mock_tool.assert_called_once_with(param1="value1", param2="value2")

    @pytest.mark.asyncio
    async def test_error_handling(self, user_proxy_agent):
        """Test error handling during message processing"""
        with patch.object(user_proxy_agent, '_llm_generate') as mock_generate:
            mock_generate.side_effect = Exception("Test error")
            
            with pytest.raises(Exception) as exc_info:
                await user_proxy_agent.process_message("This will fail")
            
            assert "Test error" in str(exc_info.value)

    def test_tool_registration(self, user_proxy_agent):
        """Test tool registration"""
        mock_tool = Mock()
        user_proxy_agent.register_tool("test_tool", mock_tool)
        
        assert "test_tool" in user_proxy_agent.available_tools
        assert user_proxy_agent.available_tools["test_tool"] == mock_tool 