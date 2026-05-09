"""Tests for AI ML modules."""
import pytest
import pandas as pd
import numpy as np

from app.core.ai.driver_discovery import DriverDiscoveryEngine


class TestDriverDiscovery:
    """Tests for Driver Discovery engine."""

    @pytest.fixture
    def engine(self):
        return DriverDiscoveryEngine()

    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        return pd.DataFrame({
            "ore_lavorate": np.random.randint(100, 500, 50),
            "notti_vendute": np.random.randint(50, 200, 50),
            "coperti": np.random.randint(200, 800, 50),
            "overhead_cost": np.random.uniform(1000, 5000, 50),
        })

    def test_fallback_discovery_small_dataset(self, engine):
        """Test fallback when dataset is too small."""
        small_df = pd.DataFrame({"a": [1], "b": [2]})
        result = engine.discover_drivers(
            small_df, "a", ["a", "b"]
        )
        assert len(result) == 2
        assert all("driver_name" in r for r in result)
        assert all("importance_pct" in r for r in result)
        assert all("confidence_score" in r for r in result)

    def test_discover_drivers_with_valid_data(self, engine, sample_data):
        """Test driver discovery with valid sample data."""
        result = engine.discover_drivers(
            sample_data,
            target_col="overhead_cost",
            feature_cols=["ore_lavorate", "notti_vendute", "coperti"]
        )
        assert len(result) == 3
        assert all(r["importance_pct"] >= 0 for r in result)
        total_pct = sum(r["importance_pct"] for r in result)
        assert 99 <= total_pct <= 101

    def test_confidence_calculation(self, engine):
        """Test confidence score calculation."""
        assert engine._calculate_confidence(20, 25.0) == "Bassa"
        assert engine._calculate_confidence(60, 35.0) == "Alta"
        assert engine._calculate_confidence(50, 20.0) == "Media"

    def test_empty_dataframe_returns_fallback(self, engine):
        """Test that empty dataframe triggers fallback."""
        empty_df = pd.DataFrame()
        result = engine.discover_drivers(
            empty_df, "target", ["feature1"]
        )
        assert len(result) == 1
        assert result[0]["driver_name"] == "feature1"
        assert "confidence_score" in result[0]