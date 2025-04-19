import pytest
import os
from unittest.mock import patch

@pytest.fixture(scope="session")
def mock_env_vars():
    """Session-wide mock environment variables"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_API_BASE': 'https://test.openai.azure.com/',
        'OPENAI_API_VERSION': '2024-02-15',
        'OPENAI_DEPLOYMENT_NAME': 'test-deployment',
        'OPENAI_API_TYPE': 'azure'
    }):
        yield

@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@pytest.fixture(autouse=True)
def add_project_root_to_path(project_root):
    """Automatically add project root to sys.path for all tests"""
    import sys
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    yield

@pytest.fixture
def mock_llm_config():
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
def sample_tool_response():
    """Sample tool response data"""
    return {
        "utilization": 0.75,
        "alert_level": "INFO",
        "message": "Test utilization data",
        "timestamp": "2025-04-01 12:00:00"
    }

@pytest.fixture
def sample_chat_history():
    """Sample chat history data"""
    return [
        {"role": "user", "content": "Analyze utilization for April 2025"},
        {"role": "assistant", "content": "I'll help you analyze that."},
        {"role": "tool", "content": '{"utilization": 0.75, "message": "Test data"}'}
    ] 