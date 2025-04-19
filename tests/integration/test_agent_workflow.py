import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import with explicit paths
from src.agents.user_proxy_agent import UserProxyAgent
from src.agents.monitoring_agent import MonitoringAgent
from src.db.models import ResourceMetric, Alert
from src.db.database import get_db_session_context

# Mock data and configurations
TEST_LLM_CONFIG = {"config_list": [{"model": "gpt-4", "api_type": "openai"}]}
TEST_DB_URL = "sqlite+aiosqlite:///./test_integration.db"

@pytest.fixture(scope="module")
def event_loop():
    """Overrides pytest-asyncio default event loop scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

class TestAgentWorkflow:
    @pytest.fixture
    def setup_agents(self, mock_llm_config):
        """Set up agents for testing"""
        user_proxy = UserProxyAgent(
            name="test_user_proxy",
            llm_config=mock_llm_config,
            system_message="You are a test user proxy agent"
        )
        
        monitoring_agent = MonitoringAgent(
            name="test_monitoring",
            llm_config=mock_llm_config,
            system_message="You are a test monitoring agent",
            deviation_thresholds={
                "critical": 10.0,
                "warning": 5.0,
                "utilization": 5.0,
                "z_score": 2.0,
                "correlation": 0.7
            }
        )
        
        return user_proxy, monitoring_agent

    @pytest.fixture
    def sample_metrics(self):
        """Create sample metrics for testing"""
        now = datetime.now()
        metrics = []
        
        # Generate CPU metrics for the last hour
        for i in range(6):  # Every 10 minutes
            metrics.append(
                ResourceMetric(
                    resource_id="test-server",
                    metric_name="cpu_utilization",
                    value=50 + (i * 5),  # Increasing utilization
                    timestamp=now - timedelta(minutes=i*10),
                    unit="percent"
                )
            )
        
        return metrics

    @pytest.mark.asyncio
    async def test_complete_monitoring_workflow(self, setup_agents, sample_metrics):
        """Test the complete monitoring workflow"""
        user_proxy, monitoring_agent = setup_agents
        
        # 1. Register metrics in the database
        for metric in sample_metrics:
            await metric.save()
        
        # 2. User requests analysis
        user_message = "Analyze CPU utilization for test-server"
        response = await user_proxy.process_message(user_message)
        
        # Verify response contains analysis
        assert "CPU utilization" in response["content"]
        assert "test-server" in response["content"]
        
        # 3. Check if alerts were generated
        alerts = await Alert.find(
            {"resource_id": "test-server", "alert_type": "high_utilization"}
        ).to_list()
        
        assert len(alerts) > 0
        assert any(alert.severity == "warning" for alert in alerts)

    @pytest.mark.asyncio
    async def test_metric_threshold_alerts(self, setup_agents):
        """Test alert generation for threshold violations"""
        user_proxy, monitoring_agent = setup_agents
        
        # Create a high utilization metric
        high_metric = ResourceMetric(
            resource_id="test-server",
            metric_name="cpu_utilization",
            value=95.0,  # Very high utilization
            timestamp=datetime.now(),
            unit="percent"
        )
        await high_metric.save()
        
        # Request analysis
        response = await user_proxy.process_message(
            "Check for any critical alerts on test-server"
        )
        
        # Verify critical alert was generated
        alerts = await Alert.find(
            {
                "resource_id": "test-server",
                "severity": "critical"
            }
        ).to_list()
        
        assert len(alerts) > 0
        assert "Critical CPU utilization" in alerts[0].message

    @pytest.mark.asyncio
    async def test_trend_analysis(self, setup_agents, sample_metrics):
        """Test trend analysis functionality"""
        user_proxy, monitoring_agent = setup_agents
        
        # Save metrics
        for metric in sample_metrics:
            await metric.save()
        
        # Request trend analysis
        response = await user_proxy.process_message(
            "Analyze CPU utilization trends for test-server"
        )
        
        # Verify trend analysis
        assert "increasing trend" in response["content"].lower()
        assert "recommendation" in response["content"].lower()

    @pytest.mark.asyncio
    async def test_multi_resource_analysis(self, setup_agents):
        """Test analysis across multiple resources"""
        user_proxy, monitoring_agent = setup_agents
        
        # Create metrics for multiple servers
        resources = ["server-1", "server-2", "server-3"]
        for resource_id in resources:
            metric = ResourceMetric(
                resource_id=resource_id,
                metric_name="cpu_utilization",
                value=85.0,
                timestamp=datetime.now(),
                unit="percent"
            )
            await metric.save()
        
        # Request multi-resource analysis
        response = await user_proxy.process_message(
            "Show me all servers with high CPU utilization"
        )
        
        # Verify all resources are mentioned
        for resource_id in resources:
            assert resource_id in response["content"] 