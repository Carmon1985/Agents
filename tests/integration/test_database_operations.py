import pytest
from datetime import datetime, timedelta
import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import with explicit paths
from src.db.models import ChatMessage, ResourceMetric, Alert
from src.db.operations import (
    save_chat_message,
    get_chat_history,
    save_resource_metric,
    get_resource_metrics,
    create_alert,
    get_alerts
)

class TestDatabaseOperations:
    @pytest.fixture
    async def setup_database(self):
        """Set up test database and clean up after tests"""
        # Clean up any existing test data
        await ChatMessage.delete_many({"session_id": {"$regex": "^test-"}})
        await ResourceMetric.delete_many({"resource_id": {"$regex": "^test-"}})
        await Alert.delete_many({"resource_id": {"$regex": "^test-"}})
        
        yield
        
        # Clean up test data after tests
        await ChatMessage.delete_many({"session_id": {"$regex": "^test-"}})
        await ResourceMetric.delete_many({"resource_id": {"$regex": "^test-"}})
        await Alert.delete_many({"resource_id": {"$regex": "^test-"}})

    @pytest.mark.asyncio
    async def test_chat_history_operations(self, setup_database):
        """Test chat history database operations"""
        session_id = "test-session-1"
        
        # Create test messages
        messages = [
            {
                "role": "user",
                "content": "Test message 1",
                "timestamp": datetime.now()
            },
            {
                "role": "assistant",
                "content": "Test response 1",
                "timestamp": datetime.now() + timedelta(seconds=1)
            }
        ]
        
        # Save messages
        for msg in messages:
            await save_chat_message(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                session_id=session_id
            )
        
        # Retrieve chat history
        history = await get_chat_history(session_id)
        
        assert len(history) == 2
        assert history[0]["content"] == "Test message 1"
        assert history[1]["content"] == "Test response 1"

    @pytest.mark.asyncio
    async def test_resource_metric_operations(self, setup_database):
        """Test resource metric database operations"""
        resource_id = "test-server-1"
        now = datetime.now()
        
        # Create test metrics
        metrics = [
            {
                "metric_name": "cpu_utilization",
                "value": 75.5,
                "timestamp": now - timedelta(minutes=10),
                "unit": "percent"
            },
            {
                "metric_name": "memory_utilization",
                "value": 85.0,
                "timestamp": now,
                "unit": "percent"
            }
        ]
        
        # Save metrics
        for metric in metrics:
            await save_resource_metric(
                resource_id=resource_id,
                metric_name=metric["metric_name"],
                value=metric["value"],
                timestamp=metric["timestamp"],
                unit=metric["unit"]
            )
        
        # Retrieve metrics
        saved_metrics = await get_resource_metrics(
            resource_id=resource_id,
            start_time=now - timedelta(minutes=15),
            end_time=now + timedelta(minutes=1)
        )
        
        assert len(saved_metrics) == 2
        assert any(m.metric_name == "cpu_utilization" for m in saved_metrics)
        assert any(m.metric_name == "memory_utilization" for m in saved_metrics)

    @pytest.mark.asyncio
    async def test_alert_operations(self, setup_database):
        """Test alert database operations"""
        resource_id = "test-server-1"
        
        # Create test alerts
        alerts = [
            {
                "alert_type": "high_utilization",
                "severity": "warning",
                "message": "High CPU utilization detected",
                "timestamp": datetime.now()
            },
            {
                "alert_type": "threshold_breach",
                "severity": "critical",
                "message": "Memory threshold exceeded",
                "timestamp": datetime.now()
            }
        ]
        
        # Save alerts
        for alert in alerts:
            await create_alert(
                resource_id=resource_id,
                alert_type=alert["alert_type"],
                severity=alert["severity"],
                message=alert["message"],
                timestamp=alert["timestamp"]
            )
        
        # Retrieve alerts
        saved_alerts = await get_alerts(resource_id=resource_id)
        
        assert len(saved_alerts) == 2
        assert any(a.severity == "warning" for a in saved_alerts)
        assert any(a.severity == "critical" for a in saved_alerts)

    @pytest.mark.asyncio
    async def test_metric_aggregation(self, setup_database):
        """Test metric aggregation operations"""
        resource_id = "test-server-1"
        now = datetime.now()
        
        # Create hourly metrics
        for i in range(24):  # Last 24 hours
            await save_resource_metric(
                resource_id=resource_id,
                metric_name="cpu_utilization",
                value=50 + (i % 10),  # Varying utilization
                timestamp=now - timedelta(hours=i),
                unit="percent"
            )
        
        # Get hourly averages
        hourly_metrics = await ResourceMetric.aggregate([
            {
                "$match": {
                    "resource_id": resource_id,
                    "timestamp": {
                        "$gte": now - timedelta(days=1)
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "hour": {"$hour": "$timestamp"}
                    },
                    "avg_value": {"$avg": "$value"}
                }
            }
        ]).to_list()
        
        assert len(hourly_metrics) > 0
        assert all("avg_value" in m for m in hourly_metrics)

    @pytest.mark.asyncio
    async def test_alert_correlation(self, setup_database):
        """Test alert correlation with metrics"""
        resource_id = "test-server-1"
        now = datetime.now()
        
        # Create high utilization metric
        await save_resource_metric(
            resource_id=resource_id,
            metric_name="cpu_utilization",
            value=95.0,
            timestamp=now,
            unit="percent"
        )
        
        # Create corresponding alert
        await create_alert(
            resource_id=resource_id,
            alert_type="high_utilization",
            severity="critical",
            message="Critical CPU utilization detected",
            timestamp=now
        )
        
        # Get correlated data
        metrics = await get_resource_metrics(
            resource_id=resource_id,
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(minutes=5)
        )
        alerts = await get_alerts(resource_id=resource_id)
        
        # Verify correlation
        assert len(metrics) > 0
        assert len(alerts) > 0
        assert any(m.value >= 95.0 for m in metrics)
        assert any(
            a.alert_type == "high_utilization" and a.severity == "critical"
            for a in alerts
        ) 