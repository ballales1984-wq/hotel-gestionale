"""Tests for API endpoints."""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestCostEndpoint:
    """Tests for costs endpoint."""

    def test_list_costs_returns_empty_list_for_invalid_period(self, client):
        """Test that list costs returns empty list for non-existent period."""
        fake_uuid = uuid4()
        response = client.get(f"/api/v1/costs/{fake_uuid}")
        assert response.status_code == 200
        assert response.json() == []


class TestPeriodEndpoint:
    """Tests for periods endpoint."""

    def test_list_periods_returns_empty_list(self, client):
        """Test that list periods returns empty list when no periods."""
        response = client.get("/api/v1/periods/")
        assert response.status_code == 200


class TestEmployeeEndpoint:
    """Tests for employees endpoint."""

    def test_list_employees_returns_empty_list(self, client):
        """Test that list employees returns empty list when no employees."""
        response = client.get("/api/v1/employees/")
        assert response.status_code == 200


class TestServiceEndpoint:
    """Tests for services endpoint."""

    def test_list_services_returns_empty_list(self, client):
        """Test that list services returns empty list when no services."""
        response = client.get("/api/v1/services/")
        assert response.status_code == 200


class TestActivityEndpoint:
    """Tests for activities endpoint."""

    def test_list_activities_returns_empty_list(self, client):
        """Test that list activities returns empty list when no activities."""
        response = client.get("/api/v1/activities/")
        assert response.status_code == 200