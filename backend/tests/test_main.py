"""Tests for FastAPI main application."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_ok(self, client):
        """Test that health check returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data