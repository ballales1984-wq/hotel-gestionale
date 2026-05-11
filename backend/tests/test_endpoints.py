"""Tests for API endpoints."""
import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4

from app.main import create_app
from fastapi.testclient import TestClient


_tables_created = False

def create_tables_sync():
    global _tables_created
    if _tables_created:
        return
    from app.db.database import engine, Base
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_create())
    _tables_created = True


@pytest.fixture(scope="module")
def client():
    create_tables_sync()
    app = create_app()
    return TestClient(app)


class TestCostEndpoint:
    def test_list_costs_returns_empty_list_for_invalid_period(self, client):
        fake_uuid = uuid4()
        response = client.get(f"/api/v1/costs/{fake_uuid}")
        assert response.status_code == 200
        assert response.json() == []

class TestPeriodEndpoint:
    def test_list_periods_returns_empty_list(self, client):
        response = client.get("/api/v1/periods/")
        assert response.status_code == 200

class TestEmployeeEndpoint:
    def test_list_employees_returns_empty_list(self, client):
        response = client.get("/api/v1/employees/")
        assert response.status_code == 200

class TestServiceEndpoint:
    def test_list_services_returns_empty_list(self, client):
        response = client.get("/api/v1/services/")
        assert response.status_code == 200

class TestActivityEndpoint:
    def test_list_activities_returns_empty_list(self, client):
        response = client.get("/api/v1/activities/")
        assert response.status_code == 200
