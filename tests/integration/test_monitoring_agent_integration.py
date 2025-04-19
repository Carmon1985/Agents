import pytest
from datetime import datetime, timedelta
import numpy as np
from src.agents.monitoring_agent import MonitoringAgent
from unittest.mock import patch, MagicMock

@pytest.fixture
def monitoring_agent():
    """Create a MonitoringAgent instance for integration testing."""
    return MonitoringAgent(
        name="integration_test_agent",
        llm_config={
            "config_list": [{
                "model": "gpt-4",
                "api_type": "openai"
            }]
        },
        system_message="Integration test monitoring agent",
        deviation_thresholds={
            "critical": 10.0,
            "warning": 5.0,
            "utilization": 5.0,
            "z_score": 2.0,
            "correlation": 0.7,
            "trend": 0.1
        }
    )

class TestMonitoringAgentIntegration:
    """Integration test suite for MonitoringAgent class."""

    @pytest.mark.asyncio
    async def test_end_to_end_analysis_workflow(self, monitoring_agent):
        """Test the complete analysis workflow from metrics to alerts."""
        # Mock the metrics data
        current_metrics = {
            "utilization": 95.0,
            "memory": 80.0,
            "cpu": 85.0,
            "network": 70.0
        }
        
        historical_metrics = {
            "utilization": [80.0, 82.0, 83.0, 81.0, 84.0],
            "memory": [75.0, 76.0, 74.0, 77.0, 75.0],
            "cpu": [80.0, 81.0, 79.0, 82.0, 80.0],
            "network": [65.0, 68.0, 67.0, 66.0, 69.0]
        }
        
        dates = [
            datetime.now() - timedelta(days=5),
            datetime.now() - timedelta(days=4),
            datetime.now() - timedelta(days=3),
            datetime.now() - timedelta(days=2),
            datetime.now() - timedelta(days=1)
        ]
        
        # Mock the metrics fetching methods
        with patch.object(monitoring_agent, '_fetch_metrics', return_value=current_metrics), \
             patch.object(monitoring_agent, '_fetch_historical_metrics', return_value=(historical_metrics, dates)):
            
            # Get current metrics
            current_data = monitoring_agent.get_current_metrics("test_resource")
            assert current_data == current_metrics
            
            # Get historical metrics
            historical_data, historical_dates = monitoring_agent.get_historical_metrics(
                "test_resource",
                dates[0],
                dates[-1]
            )
            assert historical_data == historical_metrics
            assert historical_dates == dates
            
            # Perform analysis
            analysis_results = await monitoring_agent.analyze_deviations(
                "test_resource",
                historical_metrics,
                dates
            )
            
            # Verify analysis results
            assert analysis_results["status"] == "success"
            assert "metric_analyses" in analysis_results
            assert "correlations" in analysis_results
            assert analysis_results["resource_id"] == "test_resource"
            
            # Generate alerts
            alerts = await monitoring_agent.generate_alerts(analysis_results)
            
            # Verify alerts
            assert len(alerts) > 0
            assert any(alert["level"] == "CRITICAL" for alert in alerts)
            assert all("timestamp" in alert for alert in alerts)

    @pytest.mark.asyncio
    async def test_metric_correlation_workflow(self, monitoring_agent):
        """Test the workflow for detecting and alerting on metric correlations."""
        # Create synthetic correlated metrics
        timestamps = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
        base_values = np.linspace(70, 90, 10)  # Increasing trend
        noise = np.random.normal(0, 1, 10)
        
        metrics = {
            "utilization": base_values + noise,
            "cpu": base_values * 1.1 + noise,  # Strongly correlated with utilization
            "memory": base_values * 0.5 + np.random.normal(0, 5, 10),  # Weakly correlated
            "network": np.random.normal(70, 5, 10)  # Uncorrelated
        }
        
        # Convert numpy arrays to lists for JSON serialization
        metrics = {k: v.tolist() for k, v in metrics.items()}
        
        # Analyze correlations
        correlations = monitoring_agent.detect_metric_correlations(metrics)
        
        # Verify correlation detection
        assert len(correlations) > 0
        strong_correlations = [c for c in correlations if c["strength"] == "strong positive"]
        assert len(strong_correlations) > 0
        assert any(c["metrics"] == ("utilization", "cpu") for c in strong_correlations)
        
        # Create analysis results with correlations
        analysis_results = {
            "status": "success",
            "resource_id": "test_resource",
            "metric_analyses": {
                "utilization": {
                    "metric": "utilization",
                    "current_value": metrics["utilization"][-1],
                    "statistical_analysis": {
                        "deviation_detected": True,
                        "reason": "Z-score exceeds threshold"
                    },
                    "trend_analysis": {
                        "trend_detected": True,
                        "reason": "Significant upward trend"
                    },
                    "overall_score": 8.5,
                    "alert_level": "CRITICAL"
                }
            },
            "correlations": correlations
        }
        
        # Generate alerts
        alerts = await monitoring_agent.generate_alerts(analysis_results)
        
        # Verify correlation alerts
        correlation_alerts = [a for a in alerts if "correlation" in a["title"].lower()]
        assert len(correlation_alerts) > 0
        assert any("cpu" in a["message"] and "utilization" in a["message"] for a in correlation_alerts)

    @pytest.mark.asyncio
    async def test_trend_analysis_workflow(self, monitoring_agent):
        """Test the workflow for detecting and alerting on metric trends."""
        # Create synthetic trending data
        timestamps = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
        
        # Strong upward trend
        upward_trend = {
            "utilization": [75.0, 77.0, 80.0, 82.0, 85.0, 87.0, 90.0, 92.0, 95.0, 97.0]
        }
        
        # Analyze trends
        trend_result = monitoring_agent.detect_trend_deviation(
            upward_trend["utilization"],
            timestamps
        )
        
        # Verify trend detection
        assert trend_result["trend_detected"] is True
        assert trend_result["direction"] == "increasing"
        assert trend_result["score"] > 7.0  # High confidence in trend
        
        # Create analysis results with trend
        analysis_results = {
            "status": "success",
            "resource_id": "test_resource",
            "metric_analyses": {
                "utilization": {
                    "metric": "utilization",
                    "current_value": upward_trend["utilization"][-1],
                    "statistical_analysis": {
                        "deviation_detected": True,
                        "reason": "Z-score exceeds threshold"
                    },
                    "trend_analysis": trend_result,
                    "overall_score": 9.0,
                    "alert_level": "CRITICAL"
                }
            },
            "correlations": []
        }
        
        # Generate alerts
        alerts = await monitoring_agent.generate_alerts(analysis_results)
        
        # Verify trend alerts
        assert len(alerts) > 0
        trend_alerts = [a for a in alerts if "trend" in a["message"].lower()]
        assert len(trend_alerts) > 0
        assert any("increasing" in a["message"].lower() for a in trend_alerts)
        assert alerts[0]["level"] == "CRITICAL" 