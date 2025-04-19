import pytest
from datetime import datetime
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import from the correct path within src
from src.db.models import ChatMessage, ResourceMetric, Alert

class TestDatabaseModels:
    @pytest.fixture
    def sample_chat_message(self):
        """Create a sample chat message for testing"""
        return ChatMessage(
            role="user",
            content="Test message",
            timestamp=datetime.now(),
            session_id="test-session"
        )

    @pytest.fixture
    def sample_resource_metric(self):
        """Create a sample resource metric for testing"""
        return ResourceMetric(
            resource_id="test-resource",
            metric_name="cpu_utilization",
            value=75.5,
            timestamp=datetime.now(),
            unit="percent"
        )

    @pytest.fixture
    def sample_alert(self):
        """Create a sample alert for testing"""
        return Alert(
            resource_id="test-resource",
            alert_type="high_utilization",
            severity="warning",
            message="High CPU utilization detected",
            timestamp=datetime.now()
        )

    def test_chat_message_model(self, sample_chat_message):
        """Test ChatMessage model"""
        assert sample_chat_message.role == "user"
        assert sample_chat_message.content == "Test message"
        assert isinstance(sample_chat_message.timestamp, datetime)
        assert sample_chat_message.session_id == "test-session"

    def test_resource_metric_model(self, sample_resource_metric):
        """Test ResourceMetric model"""
        assert sample_resource_metric.resource_id == "test-resource"
        assert sample_resource_metric.metric_name == "cpu_utilization"
        assert sample_resource_metric.value == 75.5
        assert sample_resource_metric.unit == "percent"
        assert isinstance(sample_resource_metric.timestamp, datetime)

    def test_alert_model(self, sample_alert):
        """Test Alert model"""
        assert sample_alert.resource_id == "test-resource"
        assert sample_alert.alert_type == "high_utilization"
        assert sample_alert.severity == "warning"
        assert sample_alert.message == "High CPU utilization detected"
        assert isinstance(sample_alert.timestamp, datetime)

    def test_chat_message_validation(self):
        """Test ChatMessage validation"""
        with pytest.raises(ValueError):
            ChatMessage(
                role="invalid_role",  # Should be user, assistant, or system
                content="Test message",
                timestamp=datetime.now(),
                session_id="test-session"
            )

    def test_resource_metric_validation(self):
        """Test ResourceMetric validation"""
        with pytest.raises(ValueError):
            ResourceMetric(
                resource_id="test-resource",
                metric_name="cpu_utilization",
                value="invalid_value",  # Should be a number
                timestamp=datetime.now(),
                unit="percent"
            )

    def test_alert_severity_validation(self):
        """Test Alert severity validation"""
        with pytest.raises(ValueError):
            Alert(
                resource_id="test-resource",
                alert_type="high_utilization",
                severity="invalid_severity",  # Should be info, warning, or critical
                message="Test alert",
                timestamp=datetime.now()
            ) 