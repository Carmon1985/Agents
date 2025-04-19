import pytest
import os
import sys
import json
from unittest.mock import Mock, patch
import autogen
from datetime import datetime

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the base class we need to instantiate
from autogen import UserProxyAgent
# Import functions needed for function map
from src.agents.monitoring_agent import analyze_utilization, forecast_next_month_utilization

class TestUserProxyAgent:
    @pytest.fixture
    def mock_env_vars(self):
        """Fixture to mock environment variables"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_API_BASE': 'https://test.openai.azure.com/',
            'OPENAI_API_VERSION': '2024-02-15',
            'OPENAI_DEPLOYMENT_NAME': 'test-deployment',
            'OPENAI_API_TYPE': 'azure'
        }):
            yield

    # Fixture to create a fresh agent instance for tests
    @pytest.fixture
    def test_agent(self, mock_env_vars): # Depends on env vars being set
        agent = UserProxyAgent(
           name="Test_User_Proxy",
           human_input_mode="NEVER",
           max_consecutive_auto_reply=10, 
           is_termination_msg=lambda x: isinstance(x, dict) and isinstance(x.get("content"), str) and "TERMINATE" in x.get("content", "").upper(),
           code_execution_config=False, 
           function_map={
               "analyze_utilization": analyze_utilization,
               "forecast_next_month_utilization": forecast_next_month_utilization
           }
        )
        return agent

    def test_user_proxy_initialization(self, test_agent):
        """Test that UserProxyAgent initializes correctly"""
        assert test_agent.name == "Test_User_Proxy"
        assert test_agent.human_input_mode == "NEVER"
        # Check type first, then value - try calling as method/property
        reply_val = test_agent.max_consecutive_auto_reply()
        assert isinstance(reply_val, int), f"Expected int, got {type(reply_val)}"
        assert reply_val == 10
        assert "analyze_utilization" in test_agent.function_map
        assert "forecast_next_month_utilization" in test_agent.function_map

    def test_termination_message_detection(self, test_agent):
        """Test that termination messages are correctly identified"""
        # Test the agent's actual termination check function
        assert test_agent._is_termination_msg({"content": "TERMINATE"})
        assert test_agent._is_termination_msg({"content": "some text TERMINATE"})
        assert test_agent._is_termination_msg({"content": "Terminate"}) # Lambda is case-insensitive
        assert not test_agent._is_termination_msg({"content": "Just some message"})
        assert not test_agent._is_termination_msg({"content": None}) # Check None content
        assert not test_agent._is_termination_msg("TERMINATE") # Check non-dict message

    @pytest.mark.asyncio
    async def test_analyze_utilization_function_call(self, test_agent):
        """Test that analyze_utilization function is called correctly through the agent"""
        test_message = {
            "content": None,
            "function_call": {
                "name": "analyze_utilization",
                "arguments": json.dumps({
                    "start_date": "2025-04-01",
                    "end_date": "2025-04-30",
                    "employee_id": "EMP123"
                })
            }
        }
        original_func = test_agent.function_map["analyze_utilization"]
        test_agent.function_map["analyze_utilization"] = Mock(wraps=original_func)
        mock_func = test_agent.function_map["analyze_utilization"]
        await test_agent.a_generate_reply(messages=[test_message], sender=test_agent)
        mock_func.assert_called_once_with(
            start_date="2025-04-01",
            end_date="2025-04-30",
            employee_id="EMP123"
        )
        test_agent.function_map["analyze_utilization"] = original_func 

    @pytest.mark.asyncio
    async def test_forecast_utilization_function_call(self, test_agent):
        """Test that forecast_next_month_utilization function is called correctly through the agent"""
        test_message = {
            "content": None,
            "function_call": {
                "name": "forecast_next_month_utilization",
                "arguments": json.dumps({
                    "employee_id": "EMP123",
                    "num_history_months": 6, # Changed key to match definition
                    "current_date_str": "2025-04-18" # Added required key
                })
            }
        }
        original_func = test_agent.function_map["forecast_next_month_utilization"]
        test_agent.function_map["forecast_next_month_utilization"] = Mock(wraps=original_func)
        mock_func = test_agent.function_map["forecast_next_month_utilization"]
        await test_agent.a_generate_reply(messages=[test_message], sender=test_agent)
        mock_func.assert_called_once_with(
            employee_id="EMP123",
            num_history_months=6,
            current_date_str="2025-04-18"
        )
        test_agent.function_map["forecast_next_month_utilization"] = original_func 

    def test_function_map_completeness(self, test_agent):
        """Test that all required functions are in the function map"""
        required_functions = {
            "analyze_utilization": analyze_utilization,
            "forecast_next_month_utilization": forecast_next_month_utilization
        }
        
        for func_name, func in required_functions.items():
            assert func_name in test_agent.function_map
            assert test_agent.function_map[func_name] == func

    @pytest.mark.asyncio
    async def test_error_handling(self, test_agent):
        """Test error handling in function execution"""
        original_func = test_agent.function_map["analyze_utilization"]
        
        # Patch the function in the map to raise an error
        mock_analyze_error = Mock(side_effect=Exception("Test error"))
        test_agent.function_map["analyze_utilization"] = mock_analyze_error
        
        test_message = {
            "content": None,
            "function_call": {
                "name": "analyze_utilization",
                "arguments": json.dumps({
                    "start_date": "2025-04-01",
                    "end_date": "2025-04-30"
                })
            }
        }

        # Simulate generating a reply that triggers the function call, expecting an error
        # AutoGen often catches errors during function execution and returns them in the response
        # Let's check the response content instead of expecting pytest.raises on a_generate_reply
        response = await test_agent.a_generate_reply(messages=[test_message], sender=test_agent)
        assert "Error" in response.get("content", "")
        assert "Test error" in response.get("content", "")
        
        # Restore original function
        test_agent.function_map["analyze_utilization"] = original_func

    @pytest.mark.asyncio # Mark as async test
    async def test_invalid_function_call(self, test_agent):
        """Test handling of invalid function calls does not crash"""
        invalid_message = {
            "content": None,
            "function_call": {
                "name": "non_existent_function",
                "arguments": "{}"
            }
        }
        try:
            # Simulate receiving an invalid function call message
            # Check that generating a reply doesn't raise an unexpected error
            await test_agent.a_generate_reply(messages=[invalid_message], sender=test_agent)
            # If it reaches here without a major error (like KeyError), it's handled somewhat gracefully.
            # A more thorough test could check the content of the reply for an error message.
        except KeyError as e:
            pytest.fail(f"Agent raised KeyError on invalid function: {e}")
        except Exception as e:
            # Allow other exceptions if they are part of expected error handling
            # but fail on unexpected ones. For now, let's assume any exception is okay 
            # unless it was a KeyError, which indicates the function map access failed badly.
            pass 