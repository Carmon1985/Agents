import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.agents.recommendation_agent import RecommendationAgent

@pytest.fixture
def llm_config():
    return {
        "config_list": [{"model": "test-model"}]
    }

@pytest.fixture
def recommendation_agent(llm_config):
    return RecommendationAgent(
        name="test_agent",
        llm_config=llm_config
    )

@pytest.fixture
def current_metrics():
    return {
        "utilization": 85.0,
        "target_utilization": 80.0,
        "charged_hours": 42.5,
        "capacity_hours": 50.0
    }

@pytest.fixture
def mock_forecast():
    return {
        "utilization": 105.0,
        "charged_hours": 45.0,
        "capacity_hours": 50.0
    }

@pytest.mark.asyncio
async def test_init_with_invalid_llm_config():
    """Test initialization with invalid llm_config."""
    with pytest.raises(ValueError, match="llm_config must be a dictionary"):
        RecommendationAgent(name="test", llm_config=None)

    with pytest.raises(ValueError, match="llm_config must contain 'config_list' key"):
        RecommendationAgent(name="test", llm_config={})

@pytest.mark.asyncio
async def test_generate_baseline_recommendations(recommendation_agent, current_metrics, mock_forecast):
    """Test generating baseline recommendations with no alerts."""
    with patch("src.agents.recommendation_agent.forecast_next_month_utilization", return_value=mock_forecast):
        recommendations = await recommendation_agent._generate_baseline_recommendations(
            current_metrics=current_metrics,
            resource_id="test_resource"
        )
        
        assert len(recommendations) == 3
        assert any(r["category"] == "resource_optimization" for r in recommendations)
        assert any(r["category"] == "capacity_planning" for r in recommendations)
        
        # Verify forecast-based recommendation
        forecast_rec = next(r for r in recommendations if "Forecasted utilization" in r["context"])
        assert forecast_rec["priority"] == "HIGH"
        assert "105.0%" in forecast_rec["context"]

@pytest.mark.asyncio
async def test_handle_critical_utilization_alert(recommendation_agent, current_metrics):
    """Test handling critical utilization alerts."""
    alert = {
        "level": "CRITICAL",
        "metric": "utilization",
        "details": {
            "deviation": 20.0
        }
    }
    
    recommendations = await recommendation_agent._handle_critical_alert(
        alert=alert,
        current_metrics=current_metrics,
        resource_id="test_resource"
    )
    
    assert len(recommendations) == 2
    assert all(r["priority"] == "HIGH" for r in recommendations)
    assert any(r["category"] == "workload_management" for r in recommendations)
    assert any(r["category"] == "resource_scaling" for r in recommendations)

@pytest.mark.asyncio
async def test_handle_critical_charged_hours_alert(recommendation_agent, current_metrics):
    """Test handling critical charged hours alerts."""
    alert = {
        "level": "CRITICAL",
        "metric": "charged_hours",
        "details": {
            "deviation": 15.0
        }
    }
    
    recommendations = await recommendation_agent._handle_critical_alert(
        alert=alert,
        current_metrics=current_metrics,
        resource_id="test_resource"
    )
    
    assert len(recommendations) == 1
    assert recommendations[0]["priority"] == "HIGH"
    assert recommendations[0]["category"] == "time_management"
    assert "42.5/50.0 hours" in recommendations[0]["context"]

@pytest.mark.asyncio
async def test_handle_warning_alerts(recommendation_agent, current_metrics):
    """Test handling warning alerts."""
    alert = {
        "level": "WARNING",
        "metric": "charged_hours",
        "details": {
            "deviation": 8.0
        }
    }
    
    recommendations = await recommendation_agent._handle_warning_alert(
        alert=alert,
        current_metrics=current_metrics,
        resource_id="test_resource"
    )
    
    assert len(recommendations) == 2
    assert all(r["priority"] == "MEDIUM" for r in recommendations)
    assert any(r["category"] == "time_tracking" for r in recommendations)
    assert any(r["category"] == "process_improvement" for r in recommendations)

@pytest.mark.asyncio
async def test_handle_correlation_alert(recommendation_agent, current_metrics):
    """Test handling correlation alerts."""
    alert = {
        "level": "INFO",
        "details": {
            "correlation": 0.85,
            "metrics": ("utilization", "charged_hours")
        }
    }
    
    recommendations = await recommendation_agent._handle_correlation_alert(
        alert=alert,
        current_metrics=current_metrics,
        resource_id="test_resource"
    )
    
    assert len(recommendations) == 1
    assert recommendations[0]["priority"] == "MEDIUM"
    assert recommendations[0]["category"] == "metric_analysis"
    assert "positive correlation" in recommendations[0]["context"]

@pytest.mark.asyncio
async def test_generate_recommendations_with_multiple_alerts(recommendation_agent, current_metrics):
    """Test generating recommendations with multiple alerts."""
    alerts = [
        {
            "level": "CRITICAL",
            "metric": "utilization",
            "details": {"deviation": 20.0}
        },
        {
            "level": "WARNING",
            "metric": "charged_hours",
            "details": {"deviation": 8.0}
        },
        {
            "level": "INFO",
            "details": {
                "correlation": 0.85,
                "metrics": ("utilization", "charged_hours")
            }
        }
    ]
    
    recommendations = await recommendation_agent.generate_recommendations(
        alerts=alerts,
        current_metrics=current_metrics,
        resource_id="test_resource"
    )
    
    # Verify recommendations are sorted by priority
    priorities = [r["priority"] for r in recommendations]
    assert priorities == sorted(priorities, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x])
    
    # Verify we have recommendations from all alert types
    categories = [r["category"] for r in recommendations]
    assert "workload_management" in categories
    assert "time_tracking" in categories
    assert "metric_analysis" in categories

@pytest.mark.asyncio
async def test_generate_recommendations_with_errors(recommendation_agent, current_metrics):
    """Test error handling in recommendation generation."""
    with patch("src.agents.recommendation_agent.forecast_next_month_utilization", side_effect=Exception("Test error")):
        # Test with no alerts (baseline recommendations)
        recommendations = await recommendation_agent.generate_recommendations(
            alerts=[],
            current_metrics=current_metrics,
            resource_id="test_resource"
        )
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0  # Should still get some recommendations despite forecast error
        
        # Test with invalid alert data
        invalid_alerts = [{"level": "CRITICAL", "metric": None}]
        recommendations = await recommendation_agent.generate_recommendations(
            alerts=invalid_alerts,
            current_metrics=current_metrics,
            resource_id="test_resource"
        )
        assert isinstance(recommendations, list)  # Should handle errors gracefully 