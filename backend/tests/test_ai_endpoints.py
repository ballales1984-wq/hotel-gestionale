"""Tests for AI endpoints (updated for multi-tenancy)."""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from app.main import create_app
from fastapi.testclient import TestClient
from app.db.database import AsyncSessionFactory, engine, Base
from app.models.models import Hotel
import asyncio


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Crea DB e hotel DEMO, restituisce TestClient."""
    # Crea tabelle
    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed minimale (crea hotel DEMO)
        from app.db.seed import seed as run_seed
        async with AsyncSessionFactory() as db:
            await run_seed(db)
            await db.commit()
    asyncio.run(setup())

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_hotel_id(client):
    """Recupera hotel_id di DEMO dalla tabella hotels."""
    async def get():
        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            result = await db.execute(select(Hotel).where(Hotel.code == "DEMO"))
            hotel = result.scalar_one_or_none()
            return hotel.id if hotel else None
    return asyncio.run(get())


# ── tests ──────────────────────────────────────────────────────────────────────

class TestAIEndpoint:
    """Tests for AI endpoints with multi-tenancy."""

    def test_ai_status_endpoint(self, client):
        """Test AI status endpoint."""
        response = client.get("/api/v1/ai/status")
        assert response.status_code == 200
        data = response.json()
        assert data["overall"] == "operational"

    def test_driver_discovery_requires_hotel_id(self, client, demo_hotel_id):
        """Driver discovery richiede hotel_id."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/driver-discovery",
            params={"hotel_id": str(demo_hotel_id)}
        )
        assert response.status_code == 200
        data = response.json()
        # Result può essere lista (fallback) o driver discoveries
        assert isinstance(data, list)
        # Se ci sono dati reali, ci sono 5 driver; altrimenti fallback con 5 elementi fittizi
        assert len(data) == 5

    def test_forecast_requires_hotel_id(self, client, demo_hotel_id):
        """Forecast richiede hotel_id e metric."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/forecast",
            params={"hotel_id": str(demo_hotel_id), "metric": "notti_vendute", "periods": 6}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6  # periods=6
        # Ogni elemento: date, predicted_value, lower_bound, upper_bound
        for item in data:
            assert "date" in item
            assert "predicted_value" in item

    def test_anomalies_requires_hotel_id(self, client, demo_hotel_id):
        """Anomaly detection richiede hotel_id."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/anomalies",
            params={"hotel_id": str(demo_hotel_id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Se dati insufficienti, lista vuota; altrimenti anomalie
        # Non verifichiamo lunghezza perché dipende da dati seed

    def test_driver_discovery_missing_hotel_id(self, client):
        """Senza hotel_id → 422 Unprocessable Entity (missing required query param)."""
        response = client.get("/api/v1/ai/driver-discovery")
        assert response.status_code == 422

    def test_forecast_missing_hotel_id(self, client):
        """Senza hotel_id → 422."""
        response = client.get("/api/v1/ai/forecast", params={"metric": "notti_vendute"})
        assert response.status_code == 422

    def test_anomalies_missing_hotel_id(self, client):
        """Senza hotel_id → 422."""
        response = client.get("/api/v1/ai/anomalies")
        assert response.status_code == 422