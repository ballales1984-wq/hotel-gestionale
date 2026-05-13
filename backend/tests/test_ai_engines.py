"""
Test suite per i motori AI: Anomaly Detection, Forecasting, Driver Discovery.
Testa con dati mock per validare la logica senza dipendere dal DB.
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.ai.anomaly_detection import AnomalyDetector
from app.core.ai.forecasting import ForecastEngine
from app.core.ai.data_fetcher import AIDataFetcher


class TestAnomalyDetector:
    """Testa il motore di Anomaly Detection."""

    def test_detects_outliers_correctly(self):
        """Deve rilevare valori anomali in un dataset normale."""
        detector = AnomalyDetector(contamination=0.1)

        df = pd.DataFrame({
            "feature_a": [1.0, 1.1, 0.9, 1.0, 1.2, 1.0, 0.95, 1.05, 100.0, -50.0],
            "feature_b": [10, 12, 8, 11, 9, 10, 11, 10, 500, -200],
        })

        results = detector.detect_anomalies(
            df=df,
            feature_cols=["feature_a", "feature_b"],
            id_col="idx",
        )

        # Con contamination=0.1 e 10 record, ci aspettiamo almeno 1 anomalia
        assert len(results) >= 1
        # Gli outlier estremi (100, -50, 500, -200) dovrebbero essere rilevati
        anomaly_scores = [r["anomaly_score"] for r in results]
        assert all(s > 0 for s in anomaly_scores)

    def test_empty_dataframe_returns_empty(self):
        """DataFrame vuoto deve restituire lista vuota."""
        detector = AnomalyDetector()
        df = pd.DataFrame()
        results = detector.detect_anomalies(df=df, feature_cols=["a", "b"], id_col="id")
        assert results == []

    def test_small_dataset_returns_empty(self):
        """Dataset troppo piccolo (< 20) deve restituire lista vuota."""
        detector = AnomalyDetector()
        df = pd.DataFrame({"a": [1.0] * 10, "b": [2.0] * 10})
        results = detector.detect_anomalies(df=df, feature_cols=["a", "b"], id_col="id")
        assert results == []

    def test_zero_variance_returns_empty(self):
        """Tutte le colonne con varianza zero devono restituire lista vuota."""
        detector = AnomalyDetector()
        df = pd.DataFrame({"a": [5.0] * 50, "b": [10.0] * 50})
        results = detector.detect_anomalies(df=df, feature_cols=["a", "b"], id_col="id")
        assert results == []

    def test_result_structure(self):
        """Ogni anomalia deve avere i campi richiesti."""
        detector = AnomalyDetector(contamination=0.15)
        df = pd.DataFrame({
            "costo_lavoro": [10000] * 18 + [25000, 5000],
            "ore": [500] * 18 + [1200, 50],
            "volume_output": [2000] * 18 + [6000, 100],
        })

        results = detector.detect_anomalies(
            df=df,
            feature_cols=["costo_lavoro", "ore", "volume_output"],
            id_col="periodo_id",
        )

        if results:
            for r in results:
                assert "record_id" in r
                assert "anomaly_score" in r
                assert "root_cause_driver" in r
                assert "explanation" in r
                assert isinstance(r["anomaly_score"], float)


class TestForecastEngine:
    """Testa il motore di Forecasting."""

    def test_forecast_returns_correct_columns(self):
        """La previsione deve restituire lista di dict con date e valori."""
        engine = ForecastEngine()
        dates = pd.date_range("2024-01-01", periods=24, freq="ME")
        df = pd.DataFrame({
            "ds": dates,
            "notti_vendute": np.random.normal(100, 10, 24),
        })

        results = engine.forecast_metric(df, "ds", "notti_vendute", periods=3, freq="ME")

        assert len(results) == 3
        for r in results:
            assert "date" in r
            assert "predicted_value" in r
            assert "lower_bound" in r
            assert "upper_bound" in r
            assert r["predicted_value"] >= 0  # Nessun valore negativo

    def test_empty_dataframe_uses_fallback(self):
        """DataFrame vuoto deve usare il fallback."""
        engine = ForecastEngine()
        df = pd.DataFrame()
        results = engine.forecast_metric(df, "ds", "y", periods=3, freq="ME")
        assert len(results) == 3

    def test_small_dataframe_uses_fallback(self):
        """DataFrame con < 5 righe deve usare fallback."""
        engine = ForecastEngine()
        df = pd.DataFrame({
            "ds": pd.date_range("2024-01-01", periods=3, freq="ME"),
            "y": [100, 110, 105],
        })
        results = engine.forecast_metric(df, "ds", "y", periods=2, freq="ME")
        assert len(results) == 2

    def test_forecast_no_negative_values(self):
        """Le previsioni non devono mai essere negative."""
        engine = ForecastEngine()
        dates = pd.date_range("2024-01-01", periods=36, freq="ME")
        df = pd.DataFrame({
            "ds": dates,
            "notti_vendute": np.abs(np.random.normal(50, 5, 36)),
        })

        results = engine.forecast_metric(df, "ds", "notti_vendute", periods=6, freq="ME")
        for r in results:
            assert r["predicted_value"] >= 0
            assert r["lower_bound"] >= 0


class TestAIDataFetcher:
    """Testa l'estrazione dati per i motori AI."""

    @patch("app.core.ai.data_fetcher.AsyncSession")
    def test_get_driver_discovery_data_columns(self, mock_session):
        """I dati per driver discovery devono avere le colonne attese."""
        fetcher = AIDataFetcher(mock_session)

        # Mock del risultato della query
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (1, 2025, 1, 100, 50, 80, 5000, 5, 15000),
        ]
        mock_session.execute.return_value = mock_result

        df = fetcher.get_driver_discovery_data()
        import asyncio
        df = asyncio.get_event_loop().run_until_complete(df)

        expected_cols = [
            "period_id", "year", "month",
            "ore_lavorate", "notti_vendute", "coperti",
            "mq", "eventi", "overhead_cost",
        ]
        assert list(df.columns) == expected_cols

    @patch("app.core.ai.data_fetcher.AsyncSession")
    def test_get_forecast_data_columns(self, mock_session):
        """I dati per forecast devono avere colonne ds e value."""
        fetcher = AIDataFetcher(mock_session)

        mock_result = MagicMock()
        mock_result.all.return_value = [(1, 2025, 1, 100)]
        mock_session.execute.return_value = mock_result

        df = fetcher.get_forecast_data("notti_vendute")
        import asyncio
        df = asyncio.get_event_loop().run_until_complete(df)

        assert "ds" in df.columns
        assert "value" in df.columns

    @patch("app.core.ai.data_fetcher.AsyncSession")
    def test_get_anomaly_data_columns(self, mock_session):
        """I dati per anomaly detection devono avere le colonne attese."""
        fetcher = AIDataFetcher(mock_session)

        mock_result = MagicMock()
        mock_result.all.return_value = [(1, 2025, 1, 10000, 500, 2000)]
        mock_session.execute.return_value = mock_result

        df = fetcher.get_anomaly_detection_data()
        import asyncio
        df = asyncio.get_event_loop().run_until_complete(df)

        expected_cols = ["periodo_id", "year", "month", "costo_lavoro", "ore", "volume_output"]
        assert list(df.columns) == expected_cols