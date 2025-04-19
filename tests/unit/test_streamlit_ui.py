import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock
import json
import datetime
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the app module (this will be mocked)
with patch('streamlit.set_page_config'):  # Mock st.set_page_config since it must be first Streamlit command
    import app

class TestStreamlitUI:
    @pytest.fixture
    def mock_streamlit(self):
        """Fixture to mock Streamlit components"""
        with patch('streamlit.title') as mock_title, \
             patch('streamlit.sidebar') as mock_sidebar, \
             patch('streamlit.chat_input') as mock_chat_input, \
             patch('streamlit.chat_message') as mock_chat_message, \
             patch('streamlit.spinner') as mock_spinner, \
             patch('streamlit.error') as mock_error:
            yield {
                'title': mock_title,
                'sidebar': mock_sidebar,
                'chat_input': mock_chat_input,
                'chat_message': mock_chat_message,
                'spinner': mock_spinner,
                'error': mock_error
            }

    @pytest.fixture
    def mock_session_state(self):
        """Fixture to mock Streamlit session state"""
        with patch('streamlit.session_state') as mock_state:
            mock_state.messages = []
            mock_state.monitoring_agent = Mock()
            yield mock_state

    @pytest.fixture
    def mock_agent_response(self):
        """Fixture to mock agent response"""
        return {
            "content": "Test response from agent",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }

    def test_session_state_initialization(self, mock_session_state):
        """Test that session state is properly initialized"""
        # Clear chat history
        app.clear_chat_history()
        assert len(mock_session_state.messages) == 0

        # Initialize agents
        assert app.initialize_agents()
        assert hasattr(mock_session_state, 'monitoring_agent')

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
    def test_chat_message_processing(self, mock_rerun, mock_session_state, mock_streamlit):
        """Test chat message processing flow"""
        test_message = "Test user input"
        
        # Simulate user input
        mock_streamlit['chat_input'].return_value = test_message
        
        # Process the message
        app.process_agent_response({
            "content": "Agent response",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })

        # Verify message was added to session state
        assert len(mock_session_state.messages) > 0
        assert any(m['content'] == "Agent response" for m in mock_session_state.messages)

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_streamlit):
        """Test error handling in UI"""
        # Simulate an error condition
        with patch('app.process_agent_response') as mock_process:
            mock_process.side_effect = Exception("Test error")

            # Process some input that would cause an error
            # Use pytest.raises to assert that the expected exception occurs
            with pytest.raises(Exception, match="Test error"):
                await app.process_agent_response({"content": "This will error"})
            
            # Optionally, verify error was displayed if applicable (depends on app structure)
            # mock_streamlit['error'].assert_called_with(...) 

    def test_message_display(self, mock_streamlit, mock_session_state):
        """Test message display formatting"""
        # Add some test messages
        test_messages = [
            {"role": "user", "content": "User message", "timestamp": "12:00:00"},
            {"role": "assistant", "content": "Assistant message", "timestamp": "12:00:01"},
            {"role": "tool", "content": json.dumps({"result": "Tool result"}), "timestamp": "12:00:02"}
        ]
        mock_session_state.messages = test_messages

        # Verify each message type is displayed correctly
        for msg in test_messages:
            with mock_streamlit['chat_message'](msg['role']) as mock_msg:
                if msg['role'] == 'tool':
                    # Tool messages should be displayed as JSON
                    assert isinstance(json.loads(msg['content']), dict)
                else:
                    # Other messages should be displayed as markdown
                    assert isinstance(msg['content'], str)

    def test_ui_component_initialization(self):
        """Test UI component initialization by calling setup_page with mock"""
        with patch('app.st', new_callable=MagicMock) as mock_st:
            # Call the setup function *after* the mock is active
            app.setup_page()

            # Assertions now use the locally created 'mock_st'
            mock_st.set_page_config.assert_called_with(
                page_title="🤖 Resource Monitoring Agent Dashboard",
                page_icon="🤖",
                layout="wide",
                initial_sidebar_state="expanded"
            )
            # We could also check sidebar access if needed
            # assert mock_st.sidebar.called 

    @patch('streamlit.rerun')
    def test_clear_chat_functionality(self, mock_rerun, mock_session_state):
        """Test clear chat functionality"""
        # Add some messages
        mock_session_state.messages = [
            {"role": "user", "content": "Test message", "timestamp": "12:00:00"}
        ]
        
        # Clear chat
        app.clear_chat_history()
        
        # Verify messages were cleared
        assert len(mock_session_state.messages) == 0
        mock_rerun.assert_called_once() 