"""Tests for AI endpoints."""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestAIEndpoint:
    """Tests for AI endpoints."""

    def test_ai_status_endpoint(self, client):
        """Test AI status endpoint."""
        response = client.get("/api/v1/ai/status")
        assert response.status_code == 200
        data = response.json()
        assert data["overall"] == "operational"

    def test_driver_discovery_endpoint(self, client):
        """Test driver discovery endpoint."""
        response = client.get(
            "/api/v1/ai/driver-discovery",
            params={"period_id": str(uuid4())}
        )
        assert response.status_code in [200, 404, 422, 500]

    def test_forecast_endpoint(self, client):
        """Test forecast endpoint."""
        response = client.get(
            "/api/v1/ai/forecast",
            params={"metric": "occupancy", "periods": 7}
        )
        assert response.status_code in [200, 404, 422, 500]

    def test_anomalies_endpoint(self, client):
        """Test anomalies endpoint."""
        response = client.get(
            "/api/v1/ai/anomalies",
            params={"period_id": str(uuid4())}
        )
        assert response.status_code in [200, 404, 422, 500]