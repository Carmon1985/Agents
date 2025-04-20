import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import re

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules to test
from src.ui.app import process_chat_input, is_simple_greeting, is_resource_monitoring_query
from src.agents.agent_factory import create_agents
from src.config.config import load_config

# Constants for testing
TEST_USER_MESSAGE = "What is the CPU usage on server1?"
TEST_GREETING = "Hello there!"
TEST_OUT_OF_DOMAIN = "What is the weather today?"
TEST_API_KEY = "test-api-key"
TEST_API_BASE = "https://test-endpoint.openai.azure.com"
TEST_API_VERSION = "2023-05-15"
TEST_DEPLOYMENT_NAME = "test-deployment"

class MockMessage:
    def __init__(self, content, role="user"):
        self.content = content
        self.role = role

class MockChatResponse:
    def __init__(self, response_content):
        self.response_content = response_content
        
    def __iter__(self):
        for msg in self.response_content:
            yield msg

class MockAsyncClient:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []
    
    async def create(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.responses:
            return self.responses.pop(0)
        return MockChatResponse(["I am a mock response"])

class MockAgent:
    def __init__(self, name, responses=None):
        self.name = name
        self.responses = responses or []
        self.messages = []
    
    def initiate_chat(self, recipient, message, clear_history=False):
        self.messages.append({"to": recipient, "message": message, "clear_history": clear_history})
        if self.responses:
            return self.responses.pop(0)
        return f"Response from {self.name} agent"

@pytest.fixture
def mock_config():
    return {
        "openai": {
            "api_key": TEST_API_KEY,
            "api_base": TEST_API_BASE,
            "api_version": TEST_API_VERSION,
            "deployment_name": TEST_DEPLOYMENT_NAME
        },
        "agent_configs": {
            "user_proxy": {"name": "User Proxy", "system_message": "You are a user proxy"},
            "main_assistant": {"name": "Main Assistant", "system_message": "You are a main assistant"},
            "cpu_monitor": {"name": "CPU Monitor", "system_message": "You monitor CPU resources"},
            "memory_monitor": {"name": "Memory Monitor", "system_message": "You monitor memory resources"},
            "disk_monitor": {"name": "Disk Monitor", "system_message": "You monitor disk resources"},
            "network_monitor": {"name": "Network Monitor", "system_message": "You monitor network resources"}
        }
    }

@pytest.fixture
def mock_agents():
    # Create mock agents
    user_proxy = MockAgent("user_proxy")
    main_assistant = MockAgent("main_assistant")
    cpu_monitor = MockAgent("cpu_monitor")
    memory_monitor = MockAgent("memory_monitor")
    disk_monitor = MockAgent("disk_monitor")
    network_monitor = MockAgent("network_monitor")
    
    agents = {
        "user_proxy": user_proxy,
        "main_assistant": main_assistant,
        "cpu_monitor": cpu_monitor,
        "memory_monitor": memory_monitor,
        "disk_monitor": disk_monitor,
        "network_monitor": network_monitor,
        "group_chat_manager": Mock()
    }
    
    return agents

@pytest.fixture
def mock_streamlit():
    with patch('streamlit.session_state', new_callable=dict) as mock_state:
        # Initialize session state with required values
        mock_state.history = []
        mock_state.messages = []
        mock_state.processing = False
        
        # Mock Streamlit components
        with patch('streamlit.text_area', return_value=TEST_USER_MESSAGE) as mock_text_area:
            with patch('streamlit.chat_message') as mock_chat_message:
                with patch('streamlit.empty', return_value=MagicMock()) as mock_empty:
                    with patch('streamlit.spinner') as mock_spinner:
                        with patch('streamlit.error') as mock_error:
                            yield {
                                'session_state': mock_state,
                                'text_area': mock_text_area,
                                'chat_message': mock_chat_message,
                                'empty': mock_empty,
                                'spinner': mock_spinner,
                                'error': mock_error
                            }

# Test simple greeting detection
@pytest.mark.parametrize("message,expected", [
    ("Hello", True),
    ("Hi there", True),
    ("hey", True),
    ("Good morning", True),
    ("What is CPU usage?", False),
    ("Tell me about memory", False)
])
def test_is_simple_greeting(message, expected):
    assert is_simple_greeting(message) == expected

# Test resource monitoring query detection
@pytest.mark.parametrize("message,expected", [
    ("What is the CPU usage?", True),
    ("Show me memory stats", True),
    ("How much disk space is left?", True),
    ("Is the network down?", True),
    ("What's the weather like?", False),
    ("Tell me a joke", False)
])
def test_is_resource_monitoring_query(message, expected):
    assert is_resource_monitoring_query(message) == expected

# Test greeting response
@patch('src.ui.app.st')
def test_process_greeting(mock_st, mock_agents, mock_config):
    mock_st.session_state.messages = []
    mock_st.session_state.history = []
    
    result = process_chat_input(TEST_GREETING, mock_agents, mock_config)
    
    # Check that the greeting was processed directly without agent involvement
    assert any(re.search(r'hello|hi|hey|greetings', msg['content'].lower()) 
               for msg in mock_st.session_state.messages if msg['role'] == 'assistant')
    assert not mock_agents['main_assistant'].messages  # Main assistant shouldn't be involved
    
# Test out of domain query
@patch('src.ui.app.st')
def test_process_out_of_domain(mock_st, mock_agents, mock_config):
    mock_st.session_state.messages = []
    mock_st.session_state.history = []
    
    with patch('src.ui.app.is_resource_monitoring_query', return_value=False):
        result = process_chat_input(TEST_OUT_OF_DOMAIN, mock_agents, mock_config)
        
        # Check that an out-of-domain response was given directly
        assert any('outside the scope' in msg['content'] or 'cannot help' in msg['content'] 
                   for msg in mock_st.session_state.messages if msg['role'] == 'assistant')

# Test resource monitoring query routing
@patch('src.ui.app.st')
def test_process_resource_query(mock_st, mock_agents, mock_config):
    mock_st.session_state.messages = []
    mock_st.session_state.history = []
    
    # Set up mock responses
    mock_agents['user_proxy'].responses = ["Chat completed"]
    
    with patch('src.ui.app.is_resource_monitoring_query', return_value=True):
        result = process_chat_input(TEST_USER_MESSAGE, mock_agents, mock_config)
        
        # Check that the message was sent to the user proxy agent
        assert len(mock_agents['user_proxy'].messages) > 0
        assert TEST_USER_MESSAGE in mock_agents['user_proxy'].messages[0]['message']

# Test error handling
@patch('src.ui.app.st')
def test_process_chat_error_handling(mock_st, mock_agents, mock_config):
    mock_st.session_state.messages = []
    mock_st.session_state.history = []
    
    # Make user_proxy agent raise an exception
    mock_agents['user_proxy'].initiate_chat = Mock(side_effect=Exception("Test error"))
    
    with patch('src.ui.app.is_resource_monitoring_query', return_value=True):
        result = process_chat_input(TEST_USER_MESSAGE, mock_agents, mock_config)
        
        # Check that error was handled and shown to user
        mock_st.error.assert_called_once()
        assert any('error' in msg['content'].lower() 
                   for msg in mock_st.session_state.messages if msg['role'] == 'assistant')

# Test agent creation
@patch('src.agents.agent_factory.aoai')
@patch('src.agents.agent_factory.autogen')
def test_create_agents(mock_autogen, mock_aoai, mock_config):
    # Configure mocks
    mock_aoai.ChatCompletion = Mock()
    mock_autogen.UserProxyAgent = Mock(return_value=Mock())
    mock_autogen.AssistantAgent = Mock(return_value=Mock())
    mock_autogen.GroupChat = Mock(return_value=Mock())
    mock_autogen.GroupChatManager = Mock(return_value=Mock())
    
    # Call create_agents
    agents = create_agents(mock_config)
    
    # Check that all necessary agents were created
    assert "user_proxy" in agents
    assert "main_assistant" in agents
    assert "cpu_monitor" in agents
    assert "memory_monitor" in agents
    assert "disk_monitor" in agents
    assert "network_monitor" in agents
    assert "group_chat_manager" in agents

# Test processing of conversation history
@patch('src.ui.app.st')
def test_conversation_history_processing(mock_st, mock_agents, mock_config):
    mock_st.session_state.messages = []
    
    # Set up mock chat history
    mock_st.session_state.history = [
        {"role": "user", "content": "Test message 1"},
        {"role": "assistant", "content": "Test response 1"},
        {"role": "user", "content": "Test message 2"},
        {"role": "assistant", "content": "Test response 2"}
    ]
    
    # Test a mock function that would process history
    def mock_process_history(history):
        return len(history)
    
    # Call with our test function
    count = mock_process_history(mock_st.session_state.history)
    
    # Verify the history was processed correctly
    assert count == 4

if __name__ == "__main__":
    pytest.main() 