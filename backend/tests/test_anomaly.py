"""Tests for anomaly detection module."""
import pytest
import pandas as pd
import numpy as np

from app.core.ai.anomaly_detection import AnomalyDetector


class TestAnomalyDetection:
    """Tests for anomaly detection engine."""

    @pytest.fixture
    def detector(self):
        return AnomalyDetector()

    def test_detect_anomalies_empty_data(self, detector):
        """Test anomaly detection with empty data."""
        empty_df = pd.DataFrame()
        result = detector.detect_anomalies(empty_df, ["value"], "id")
        assert len(result) == 0

    def test_detect_anomalies_with_data(self, detector):
        """Test anomaly detection with valid data."""
        df = pd.DataFrame({
            "id": range(30),
            "value": [100, 105, 98, 102, 150, 99, 101, 500, 100, 98, 103, 100, 102, 99, 101, 150, 100, 101, 98, 102, 105, 100, 99, 500, 101, 100, 98, 102, 101, 103],
        })
        result = detector.detect_anomalies(df, ["value"], "id")
        assert isinstance(result, list)

    def test_detector_initialization(self, detector):
        """Test that detector is initialized."""
        assert detector.model is not None
        assert detector.scaler is not None