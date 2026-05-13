"""
Test suite per i motori AI: Anomaly Detection, Forecasting.
Testa con dati mock per validare la logica senza dipendere dal DB.
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from uuid import uuid4

from app.core.ai.anomaly_detection import AnomalyDetector
from app.core.ai.forecasting import ForecastEngine
from app.core.pms_sync import SyncResult


class TestAnomalyDetector:
    def test_empty_dataframe_returns_empty(self):
        detector = AnomalyDetector()
        df = pd.DataFrame()
        results = detector.detect_anomalies(df=df, feature_cols=["a", "b"], id_col="id")
        assert results == []

    def test_small_dataset_returns_empty(self):
        detector = AnomalyDetector()
        df = pd.DataFrame({"a": [1.0] * 10, "b": [2.0] * 10})
        results = detector.detect_anomalies(df=df, feature_cols=["a", "b"], id_col="id")
        assert results == []

    def test_zero_variance_returns_empty(self):
        detector = AnomalyDetector()
        df = pd.DataFrame({"costo_lavoro": [5.0], "ore": [10.0], "volume_output": [20.0]})
        results = detector.detect_anomalies(
            df=df, feature_cols=["costo_lavoro", "ore", "volume_output"], id_col="id"
        )
        assert results == []

    def test_result_structure(self):
        """Con contamination > 0 e dati sufficienti, rileva anomalie."""
        detector = AnomalyDetector(contamination=0.2)
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            "periodo_id": [f"P-{i}" for i in range(n + 2)],
            "costo_lavoro": list(np.random.normal(10000, 500, n)) + [25000, 5000],
            "ore": list(np.random.normal(500, 20, n)) + [1200, 50],
            "volume_output": list(np.random.normal(2000, 100, n)) + [6000, 100],
        })
        results = detector.detect_anomalies(
            df=df,
            feature_cols=["costo_lavoro", "ore", "volume_output"],
            id_col="periodo_id",
        )
        for r in results:
            assert "record_id" in r
            assert "anomaly_score" in r
            assert "root_cause_driver" in r
            assert "explanation" in r


class TestForecastEngine:
    def test_forecast_returns_correct_columns(self):
        engine = ForecastEngine()
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=24, freq="ME")
        df = pd.DataFrame({
            "ds": dates,
            "notti_vendute": np.abs(np.random.normal(100, 10, 24)),
        })
        results = engine.forecast_metric(df, "ds", "notti_vendute", periods=3, freq="ME")
        assert len(results) == 3
        for r in results:
            assert "date" in r
            assert "predicted_value" in r
            assert r["predicted_value"] >= 0

    def test_empty_dataframe_uses_fallback(self):
        engine = ForecastEngine()
        df = pd.DataFrame()
        results = engine.forecast_metric(df, "ds", "y", periods=3, freq="ME")
        assert len(results) == 3

    def test_forecast_no_negative_values(self):
        engine = ForecastEngine()
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=36, freq="ME")
        df = pd.DataFrame({
            "ds": dates,
            "notti_vendute": np.abs(np.random.normal(50, 5, 36)),
        })
        results = engine.forecast_metric(df, "ds", "notti_vendute", periods=6, freq="ME")
        for r in results:
            assert r["predicted_value"] >= 0


class TestSyncResult:
    def test_initial_state(self):
        r = SyncResult("success", uuid4(), uuid4(), records_imported=5)
        assert r.status == "success"
        assert r.records_imported == 5

    def test_status_with_errors(self):
        r = SyncResult("error", uuid4(), uuid4(), errors=["fail"])
        assert r.status == "error"

    def test_summary(self):
        r = SyncResult("success", uuid4(), uuid4(), records_imported=10)
        r.records_read = 100
        s = r.summary()
        assert "100" in s
        assert "10" in s

    def test_is_success_true(self):
        assert SyncResult("success", uuid4(), uuid4()).is_success is True

    def test_is_success_false(self):
        assert SyncResult("error", uuid4(), uuid4()).is_success is False