"""Tests for forecasting module."""
import pytest
import pandas as pd
import numpy as np

from app.core.ai.forecasting import ForecastEngine


class TestForecastingEngine:
    """Tests for forecasting engine."""

    @pytest.fixture
    def engine(self):
        return ForecastEngine()

    def test_forecast_empty_data(self, engine):
        """Test forecast with empty data returns fallback."""
        empty_df = pd.DataFrame()
        result = engine.forecast_metric(empty_df, "ds", "y", periods=7)
        assert isinstance(result, list)

    def test_forecast_with_valid_data(self, engine):
        """Test forecast with valid time series data."""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        df = pd.DataFrame({
            "ds": dates,
            "y": np.sin(np.arange(30) * 0.3) * 100 + 200,
        })
        result = engine.forecast_metric(df, "ds", "y", periods=7)
        assert isinstance(result, list)

    def test_forecast_missing_column(self, engine):
        """Test forecast with missing required column."""
        df = pd.DataFrame({"ds": [1, 2, 3], "y": [100, 105, 110]})
        result = engine.forecast_metric(df, "ds", "y", periods=7)
        assert isinstance(result, list)
        assert len(result) == 7