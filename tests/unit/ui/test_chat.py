import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock, ANY
import json
import datetime
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the app module (this will be mocked)
with patch('streamlit.set_page_config'):
    import app

class TestChatFunctionality:
    @pytest.fixture
    def mock_session_state(self):
        """Fixture to mock Streamlit session state"""
        with patch('streamlit.session_state') as mock_state:
            # Assign a MagicMock to messages
            mock_messages_list = MagicMock(spec=list)
            mock_state.messages = mock_messages_list # Assign the mock list
            mock_state.monitoring_agent = Mock()
            yield mock_state # Yield only the main state mock

    @pytest.fixture
    def mock_agent_response(self):
        """Fixture to mock agent response"""
        return {
            "content": "Test response from agent",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }

    def test_message_formatting(self):
        """Test message formatting functions"""
        # Test error message formatting
        error_msg = app.format_error_message("Test error")
        assert "Test error" in error_msg
        assert "⚠️" in error_msg

        # Test tool request formatting
        tool_args = {"param1": "value1", "param2": "value2"}
        tool_msg = app.format_tool_request("test_tool", tool_args)
        assert "test_tool" in tool_msg
        assert "value1" in tool_msg
        assert "value2" in tool_msg

    @patch('streamlit.rerun')
    def test_chat_message_processing(self, mock_rerun, mock_session_state):
        """Test chat message processing flow"""
        
        # Process the message. This should call st.session_state.messages.append, 
        # which is mocked by the mock_session_state fixture.
        app.process_agent_response({
            "content": "Agent response",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S") 
        })

        # Verify message was added to the *mocked* session state via append
        # Access messages attribute directly on the mock_session_state object
        mock_session_state.messages.append.assert_called_once_with({
            "role": "assistant", 
            "content": "Agent response",
            "timestamp": ANY # Use ANY to avoid exact timestamp matching issues
        })
            
    def test_message_display(self, mock_session_state):
        """Test that message display function runs without error"""
        # Define test messages
        test_messages = [
            {"role": "user", "content": "User message", "timestamp": "12:00:00"},
            {"role": "assistant", "content": "Assistant message", "timestamp": "12:00:01"},
            {"role": "tool", "content": json.dumps({"result": "Tool result"}), "timestamp": "12:00:02"}
        ]
        # Assign the real list directly to the mocked attribute
        mock_session_state.messages = test_messages
        
        # Patch app.st locally to avoid errors if display_chat_messages uses st internally
        with patch('app.st', new_callable=MagicMock) as mock_st:
            try:
                # Call the actual display function from the app
                app.display_chat_messages()
                # If the function completes without error, the test implicitly passes
            except Exception as e:
                pytest.fail(f"app.display_chat_messages raised an exception: {e}")

    @patch('streamlit.rerun')
    def test_clear_chat_functionality(self, mock_rerun, mock_session_state):
        """Test clear chat functionality"""
        # Add some messages - assign directly to the messages attribute of the mock state
        mock_session_state.messages = [
            {"role": "user", "content": "Test message", "timestamp": "12:00:00"}
        ]
        
        # Clear chat
        app.clear_chat_history()
        
        # Verify messages were cleared
        assert len(mock_session_state.messages) == 0
        mock_rerun.assert_called_once() 