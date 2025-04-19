import pytest
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from src.agents.monitoring_agent import MonitoringAgent
from unittest.mock import patch, MagicMock

@pytest.fixture
def monitoring_agent():
    """Create a MonitoringAgent instance for testing."""
    return MonitoringAgent(
        llm_config={
            "config_list": [{
                "model": "gpt-4",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
                "api_type": "openai"
            }]
        },
        deviation_thresholds={
            "critical": 10.0,
            "warning": 5.0
        }
    )

class TestMonitoringAgent:
    """Test suite for MonitoringAgent class."""
    
    def test_detect_statistical_deviation_significant(self, monitoring_agent):
        """Test statistical deviation detection with significant deviation."""
        current_value = 95.0
        historical_values = [80.0, 82.0, 78.0, 81.0, 79.0]  # Mean = 80, std ≈ 1.58
        
        result = monitoring_agent.detect_statistical_deviation(current_value, historical_values)
        
        assert result["deviation_detected"] is True
        assert result["z_score"] > monitoring_agent.deviation_thresholds["z_score"]
        assert result["score"] > 0.0
        assert "exceeds threshold" in result["reason"]
        
    def test_detect_statistical_deviation_normal(self, monitoring_agent):
        """Test statistical deviation detection with normal values."""
        current_value = 81.0
        historical_values = [80.0, 82.0, 78.0, 81.0, 79.0]
        
        result = monitoring_agent.detect_statistical_deviation(current_value, historical_values)
        
        assert result["deviation_detected"] is False
        assert abs(result["z_score"]) <= monitoring_agent.deviation_thresholds["z_score"]
        assert "within threshold" in result["reason"]
        
    def test_detect_trend_deviation_significant(self, monitoring_agent):
        """Test trend deviation detection with significant trend."""
        values = [75.0, 80.0, 85.0, 90.0, 95.0]  # Clear upward trend
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 2, 1),
            datetime(2024, 3, 1),
            datetime(2024, 4, 1),
            datetime(2024, 5, 1)
        ]
        
        result = monitoring_agent.detect_trend_deviation(values, dates)
        
        assert result["trend_detected"] is True
        assert result["slope"] > 0
        assert result["r_squared"] > 0.6
        assert result["direction"] == "increasing"
        assert "Significant trend detected" in result["reason"]
        
    def test_detect_trend_deviation_no_trend(self, monitoring_agent):
        """Test trend deviation detection with no significant trend."""
        values = [80.0, 79.0, 81.0, 78.0, 80.0]  # Random fluctuation
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 2, 1),
            datetime(2024, 3, 1),
            datetime(2024, 4, 1),
            datetime(2024, 5, 1)
        ]
        
        result = monitoring_agent.detect_trend_deviation(values, dates)
        
        assert result["trend_detected"] is False
        assert "No significant trend detected" in result["reason"]
        
    def test_detect_metric_correlations(self, monitoring_agent):
        """Test correlation detection between metrics."""
        metric_data = {
            "utilization": [75.0, 80.0, 85.0, 90.0, 95.0],
            "charged_hours": [30.0, 32.0, 34.0, 36.0, 38.0],  # Perfectly correlated
            "capacity_hours": [40.0, 40.0, 40.0, 40.0, 40.0]  # No correlation
        }
        
        correlations = monitoring_agent.detect_metric_correlations(metric_data)
        
        assert len(correlations) >= 1
        assert any(c["correlation"] > monitoring_agent.deviation_thresholds["correlation"] 
                  for c in correlations)
        
    @pytest.mark.asyncio
    async def test_analyze_deviations(self, monitoring_agent):
        """Test comprehensive deviation analysis."""
        metric_name = "test_resource"
        current_value = {
            "utilization": 90.0,
            "charged_hours": 45.0,
            "capacity_hours": 50.0,
            "target_utilization": 80.0
        }
        historical_data = {
            "utilization": [80.0, 82.0, 78.0, 81.0, 79.0],
            "charged_hours": [40.0, 41.0, 39.0, 40.5, 39.5],
            "capacity_hours": [50.0, 50.0, 50.0, 50.0, 50.0],
            "target_utilization": [80.0, 80.0, 80.0, 80.0, 80.0]
        }
        # Create dates in chronological order (oldest to newest)
        dates = [datetime.now() - timedelta(days=5-i) for i in range(5)]
        
        result = await monitoring_agent.analyze_deviations(metric_name, current_value, historical_data, dates)
        
        assert result["status"] == "success"
        assert result["resource_id"] == metric_name
        assert "metric_analyses" in result
        assert "correlations" in result
        assert isinstance(result["metric_analyses"], dict)
        assert isinstance(result["correlations"], list)
        assert all(key in result["metric_analyses"] for key in ["utilization", "charged_hours", "capacity_hours"])
        assert all(analysis.get("statistical") and analysis.get("trend") for analysis in result["metric_analyses"].values())
        
    @pytest.mark.asyncio
    async def test_analyze_deviations_with_significant_deviation(self, monitoring_agent):
        """Test deviation analysis with significant statistical deviation."""
        metric_name = "test_resource"
        current_value = {
            "utilization": 95.0,  # Significantly higher than historical values
            "charged_hours": 47.5,
            "capacity_hours": 50.0,
            "target_utilization": 80.0
        }
        historical_data = {
            "utilization": [80.0, 81.0, 79.0, 80.5, 80.2],
            "charged_hours": [40.0, 40.5, 39.5, 40.25, 40.1],
            "capacity_hours": [50.0, 50.0, 50.0, 50.0, 50.0],
            "target_utilization": [80.0, 80.0, 80.0, 80.0, 80.0]
        }
        # Create dates in chronological order
        dates = [datetime.now() - timedelta(days=5-i) for i in range(5)]
        
        result = await monitoring_agent.analyze_deviations(metric_name, current_value, historical_data, dates)
        
        assert result["status"] == "success"
        assert result["metric_analyses"]["utilization"]["statistical"]["deviation_detected"] is True
        assert result["metric_analyses"]["utilization"]["statistical"]["z_score"] > monitoring_agent.deviation_thresholds["z_score"]
        assert "exceeds threshold" in result["metric_analyses"]["utilization"]["statistical"]["reason"]
        
    @pytest.mark.asyncio
    async def test_analyze_deviations_with_trend(self, monitoring_agent):
        """Test deviation analysis with significant trend."""
        metric_name = "test_resource"
        current_value = {
            "utilization": 90.0,
            "charged_hours": 45.0,
            "capacity_hours": 50.0,
            "target_utilization": 80.0
        }
        historical_data = {
            "utilization": [75.0, 80.0, 85.0, 87.0, 89.0],  # Clear upward trend
            "charged_hours": [37.5, 40.0, 42.5, 43.5, 44.5],
            "capacity_hours": [50.0, 50.0, 50.0, 50.0, 50.0],
            "target_utilization": [80.0, 80.0, 80.0, 80.0, 80.0]
        }
        # Create dates in chronological order
        dates = [datetime.now() - timedelta(days=5-i) for i in range(5)]
        
        result = await monitoring_agent.analyze_deviations(metric_name, current_value, historical_data, dates)
        
        assert result["status"] == "success"
        assert result["metric_analyses"]["utilization"]["trend"]["trend_detected"] is True
        assert result["metric_analyses"]["utilization"]["trend"]["direction"] == "increasing"
        assert result["metric_analyses"]["utilization"]["trend"]["r_squared"] > 0.6
        
    @pytest.mark.asyncio
    async def test_analyze_deviations_with_correlation(self, monitoring_agent):
        """Test deviation analysis with metric correlations."""
        metric_name = "test_resource"
        current_value = {
            "utilization": 90.0,
            "charged_hours": 45.0,
            "capacity_hours": 50.0,
            "target_utilization": 80.0
        }
        historical_data = {
            "utilization": [75.0, 80.0, 85.0, 87.0, 89.0],
            "charged_hours": [37.5, 40.0, 42.5, 43.5, 44.5],  # Perfectly correlated with utilization
            "capacity_hours": [50.0, 50.0, 50.0, 50.0, 50.0],
            "target_utilization": [80.0, 80.0, 80.0, 80.0, 80.0]
        }
        # Create dates in chronological order
        dates = [datetime.now() - timedelta(days=5-i) for i in range(5)]
        
        result = await monitoring_agent.analyze_deviations(metric_name, current_value, historical_data, dates)
        
        assert result["status"] == "success"
        assert len(result["correlations"]) > 0
        assert any(c["correlation"] > monitoring_agent.deviation_thresholds["correlation"] for c in result["correlations"])
        assert any(c["metrics"] == ("utilization", "charged_hours") for c in result["correlations"])

    @pytest.mark.asyncio
    async def test_get_current_metrics(self, monitoring_agent):
        """Test getting current metrics."""
        with patch('src.agents.monitoring_agent.get_period_data') as mock_get_data:
            mock_get_data.return_value = (40.0, 50.0, 0.8)  # charged_hours, capacity_hours, target_ratio
            
            result = await monitoring_agent.get_current_metrics("test_resource")
            
            assert "utilization" in result
            assert abs(result["utilization"] - 80.0) < 0.01  # Should be (40/50) * 100
            assert result["charged_hours"] == 40.0
            assert result["capacity_hours"] == 50.0
            assert abs(result["target_utilization"] - 80.0) < 0.01
            
    @pytest.mark.asyncio
    async def test_get_historical_metrics(self, monitoring_agent):
        """Test getting historical metrics."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        with patch('src.agents.monitoring_agent.get_period_data') as mock_get_data:
            mock_get_data.return_value = (40.0, 50.0, 0.8)
            
            metrics, dates = await monitoring_agent.get_historical_metrics("test_resource", start_date, end_date)
            
            assert isinstance(metrics, dict)
            assert isinstance(dates, list)

    @pytest.mark.asyncio
    async def test_forecast_performance(self, monitoring_agent):
        """Test performance forecasting functionality."""
        # Mock historical data with increasing trend
        historical_metrics = {
            "utilization": [75.0, 78.0, 80.0, 82.0, 85.0, 87.0]  # Increasing trend
        }
        dates = [
            datetime.now() - timedelta(days=150),
            datetime.now() - timedelta(days=120),
            datetime.now() - timedelta(days=90),
            datetime.now() - timedelta(days=60),
            datetime.now() - timedelta(days=30),
            datetime.now()
        ]
        
        # Mock get_historical_metrics
        with patch.object(monitoring_agent, 'get_historical_metrics', 
                         return_value=(historical_metrics, dates)):
            
            # Test successful forecast
            result = await monitoring_agent.forecast_performance("test_resource")
            
            assert result["status"] == "success"
            assert "forecast" in result
            assert "reliability" in result
            assert "trend" in result
            assert result["trend"]["direction"] == "increasing"
            assert result["reliability"]["level"] in ["low", "medium", "high"]
            assert 0 <= result["forecast"]["value"] <= 100
            assert result["forecast"]["lower_bound"] <= result["forecast"]["value"] <= result["forecast"]["upper_bound"]
            
            # Test insufficient data
            with patch.object(monitoring_agent, 'get_historical_metrics',
                            return_value=({"utilization": [75.0]}, [datetime.now()])):
                result = await monitoring_agent.forecast_performance("test_resource")
                assert result["status"] == "error"
                assert "Insufficient data" in result["error"]
            
            # Test no data
            with patch.object(monitoring_agent, 'get_historical_metrics', return_value=({}, [])):
                result = await monitoring_agent.forecast_performance("test_resource")
                assert result["status"] == "error"
                assert "No historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_alerts(self, monitoring_agent):
        """Test alert generation from analysis results."""
        analysis_results = {
            "status": "success",
            "metric_analyses": {
                "utilization": {
                    "alert_level": "CRITICAL",
                    "statistical_analysis": {
                        "reason": "Significant deviation detected"
                    }
                },
                "charged_hours": {
                    "alert_level": "WARNING",
                    "statistical_analysis": {
                        "reason": "Minor deviation detected"
                    }
                }
            },
            "correlations": [
                {
                    "metrics": ("utilization", "charged_hours"),
                    "correlation": 0.95,
                    "score": 8.0
                }
            ]
        }
        
        alerts = await monitoring_agent.generate_alerts(analysis_results)
        
        # Verify alerts are generated and sorted by priority
        assert len(alerts) == 3  # Should have CRITICAL, WARNING, and INFO alerts
        assert alerts[0]["level"] == "CRITICAL"
        assert alerts[1]["level"] == "WARNING"
        assert alerts[2]["level"] == "INFO"
        
        # Verify alert messages
        assert "Significant deviation detected" in alerts[0]["message"]
        assert "Minor deviation detected" in alerts[1]["message"]
        assert "Strong correlation" in alerts[2]["message"]

    @pytest.mark.asyncio
    async def test_generate_alerts_empty_analysis(self, monitoring_agent):
        """Test alert generation with empty analysis results."""
        empty_results = {}
        alerts = await monitoring_agent.generate_alerts(empty_results)
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_generate_alerts_failed_analysis(self, monitoring_agent):
        """Test alert generation with failed analysis results."""
        failed_results = {
            "status": "error",
            "message": "Analysis failed"
        }
        alerts = await monitoring_agent.generate_alerts(failed_results)
        assert len(alerts) == 0

    def test_initialization_with_custom_thresholds(self):
        """Test agent initialization with custom thresholds."""
        custom_thresholds = {
            "critical": 15.0,
            "warning": 7.5
        }
        
        agent = MonitoringAgent(
            llm_config={"config_list": [{"model": "gpt-4", "api_type": "openai"}]},
            deviation_thresholds=custom_thresholds
        )
        
        assert agent.deviation_thresholds["critical"] == 15.0
        assert agent.deviation_thresholds["warning"] == 7.5
        
    def test_initialization_with_default_thresholds(self):
        """Test agent initialization with default thresholds."""
        agent = MonitoringAgent(
            llm_config={"config_list": [{"model": "gpt-4", "api_type": "openai"}]}
        )
        
        assert agent.deviation_thresholds["critical"] == 10.0
        assert agent.deviation_thresholds["warning"] == 5.0
        
    def test_initialization_with_invalid_thresholds(self):
        """Test agent initialization with invalid threshold values."""
        invalid_thresholds = {
            "critical": "invalid",  # Invalid type
            "warning": 5.0
        }
        
        with pytest.raises(ValueError) as exc_info:
            MonitoringAgent(
                llm_config={"config_list": [{"model": "gpt-4", "api_type": "openai"}]},
                deviation_thresholds=invalid_thresholds
            )
        assert "Invalid value for critical threshold" in str(exc_info.value)
        
    def test_initialization_with_missing_thresholds(self):
        """Test agent initialization with missing threshold keys."""
        incomplete_thresholds = {
            "warning": 5.0  # Missing critical threshold
        }
        
        with pytest.raises(ValueError) as exc_info:
            MonitoringAgent(
                llm_config={"config_list": [{"model": "gpt-4", "api_type": "openai"}]},
                deviation_thresholds=incomplete_thresholds
            )
        assert "Missing required threshold key: critical" in str(exc_info.value)
        
    def test_initialization_with_invalid_llm_config(self):
        """Test agent initialization with invalid LLM configuration."""
        invalid_configs = [
            {},  # Empty config
            {"config_list": []},  # Empty config list
            {"wrong_key": []},  # Missing config_list
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(ValueError) as exc_info:
                MonitoringAgent(llm_config=invalid_config)
            assert "llm_config must be a dictionary containing 'config_list'" in str(exc_info.value)

    def test_detect_statistical_deviation_empty_data(self, monitoring_agent):
        """Test statistical deviation detection with empty historical data."""
        current_value = 95.0
        historical_values = []

        result = monitoring_agent.detect_statistical_deviation(current_value, historical_values)
        
        assert result["deviation_detected"] is False
        assert "Insufficient historical data" in result["reason"]
        assert result["score"] == 0.0

    def test_detect_statistical_deviation_constant_data(self, monitoring_agent):
        """Test statistical deviation detection with constant historical values."""
        current_value = 95.0
        historical_values = [80.0, 80.0, 80.0, 80.0, 80.0]  # All same value

        result = monitoring_agent.detect_statistical_deviation(current_value, historical_values)
        
        assert result["deviation_detected"] is False
        assert "No variation in historical data" in result["reason"]
        assert result["score"] == 0.0

    def test_detect_trend_deviation_insufficient_data(self, monitoring_agent):
        """Test trend deviation detection with insufficient data points."""
        values = [75.0, 80.0]  # Only 2 points
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 2, 1)
        ]

        result = monitoring_agent.detect_trend_deviation(values, dates)
        
        assert result["trend_detected"] is False
        assert "Insufficient data points" in result["reason"]
        assert result["score"] == 0.0

    def test_detect_trend_deviation_invalid_dates(self, monitoring_agent):
        """Test trend deviation detection with invalid date order."""
        values = [75.0, 80.0, 85.0]
        dates = [
            datetime(2024, 3, 1),  # Out of order
            datetime(2024, 1, 1),
            datetime(2024, 2, 1)
        ]

        with pytest.raises(ValueError) as exc_info:
            monitoring_agent.detect_trend_deviation(values, dates)
        
        assert "Dates must be in chronological order" in str(exc_info.value)

    def test_detect_metric_correlations_insufficient_data(self, monitoring_agent):
        """Test correlation detection with insufficient data."""
        metrics = {
            "metric1": [1.0],  # Only one data point
            "metric2": [2.0]
        }
        
        result = monitoring_agent.detect_metric_correlations(metrics)
        
        assert len(result) == 0

    def test_detect_metric_correlations_invalid_data(self, monitoring_agent):
        """Test correlation detection with invalid/mismatched data."""
        metrics = {
            "metric1": [1.0, 2.0, 3.0],
            "metric2": [1.0, 2.0]  # Different length
        }
        
        with pytest.raises(ValueError) as exc_info:
            monitoring_agent.detect_metric_correlations(metrics)
        
        assert "All metrics must have the same number of values" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_deviations_missing_metrics(self, monitoring_agent):
        """Test deviation analysis with missing required metrics."""
        dates = [datetime.now() - timedelta(days=i) for i in range(3)]
        result = await monitoring_agent.analyze_deviations("test_resource", {"cpu": 70.0}, {"cpu": [60.0, 65.0, 70.0]}, dates)
        assert result["status"] == "error"
        assert "Missing required metrics" in result["message"]

    @pytest.mark.asyncio
    async def test_analyze_deviations_invalid_resource(self, monitoring_agent):
        """Test deviation analysis with invalid resource ID."""
        dates = [datetime.now() - timedelta(days=i) for i in range(3)]
        result = await monitoring_agent.analyze_deviations("", {}, {}, dates)
        assert result["status"] == "error"
        assert "Missing required metrics or resource ID" in result["message"]

    @pytest.mark.asyncio
    async def test_get_current_metrics_empty_data(self, monitoring_agent):
        """Test current metrics retrieval with empty data."""
        with patch('src.agents.monitoring_agent.get_period_data', return_value=(None, None, None)):
            result = await monitoring_agent.get_current_metrics("test_resource")
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_historical_metrics_invalid_range(self, monitoring_agent):
        """Test historical metrics retrieval with invalid date range."""
        end_date = datetime.now()
        start_date = end_date + timedelta(days=1)
        
        with pytest.raises(ValueError, match="Start date must be before end date"):
            await monitoring_agent.get_historical_metrics("test_resource", start_date, end_date)

    @pytest.mark.asyncio
    async def test_get_historical_metrics_valid_range(self, monitoring_agent):
        """Test historical metrics retrieval with valid date range."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        metrics, dates = await monitoring_agent.get_historical_metrics("test_resource", start_date, end_date)
        assert isinstance(metrics, dict)
        assert isinstance(dates, list) 

    @pytest.mark.asyncio
    async def test_analyze_deviations_with_empty_data(self, monitoring_agent):
        """Test deviation analysis with empty historical data."""
        metric_name = "test_resource"
        current_value = {
            "utilization": 90.0,
            "charged_hours": 45.0,
            "capacity_hours": 50.0,
            "target_utilization": 80.0
        }
        historical_data = {
            "utilization": [],
            "charged_hours": [],
            "capacity_hours": [],
            "target_utilization": []
        }
        dates = []
        
        result = await monitoring_agent.analyze_deviations(metric_name, current_value, historical_data, dates)
        
        assert result["status"] == "error"
        assert "insufficient historical data" in result["message"].lower()

    def test_invalid_deviation_thresholds(self, monitoring_agent):
        """Test initialization with invalid deviation thresholds."""
        with pytest.raises(ValueError, match="deviation_thresholds must be a dictionary"):
            MonitoringAgent(
                name="test",
                llm_config={"config_list": [{"model": "gpt-4", "api_type": "openai"}]},
                system_message="test",
                deviation_thresholds="invalid"
            )

    def test_invalid_llm_config(self, monitoring_agent):
        """Test initialization with invalid LLM config."""
        with pytest.raises(ValueError, match="llm_config must be a dictionary containing 'config_list'"):
            MonitoringAgent(
                name="test",
                llm_config="invalid",
                system_message="test"
            )

        with pytest.raises(ValueError, match="llm_config must be a dictionary containing 'config_list'"):
            MonitoringAgent(
                name="test",
                llm_config={},
                system_message="test"
            )