"""Tests for AI endpoints (updated for multi-tenancy and auth)."""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID
from sqlalchemy import func, select

from app.main import create_app
from fastapi.testclient import TestClient
from app.db.database import AsyncSessionFactory, engine, Base
from app.models.models import Hotel, User, UserRole
from app.core.encryption import get_encryption_service
import asyncio
from passlib.context import CryptContext


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Crea DB, hotel DEMO e utente di test, restituisce TestClient."""
    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from app.db.seed import seed as run_seed
        async with AsyncSessionFactory() as db:
            await run_seed(db)
            # Assicura che l'utente admin creato dal seed abbia hotel_id
            # Se il seed non crea utente, ne creiamo uno
            user_count = await db.scalar(select(func.count(User.id)))
            if user_count == 0:
                from app.models.models import Department
                hotel = await db.scalar(select(Hotel).where(Hotel.code == "DEMO"))
                pwd = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("admin123")
                user = User(
                    email="admin@hotel-abc.it",
                    full_name="Admin Test",
                    hashed_password=pwd,
                    role=UserRole.ADMIN,
                    hotel_id=hotel.id if hotel else None,
                    is_active=True,
                )
                db.add(user)
                await db.commit()
            else:
                # Assicuriamoci che almeno un utente abbia hotel_id
                user = await db.scalar(select(User).where(User.hotel_id != None))
                if not user:
                    # Trova un hotel
                    hotel = await db.scalar(select(Hotel))
                    if hotel:
                        user = await db.scalar(select(User).limit(1))
                        if user:
                            user.hotel_id = hotel.id
                            await db.commit()
    asyncio.run(setup())

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Restituisce header di autorizzazione per un utente valido."""
    r = client.post("/api/v1/auth/login", data={
        "username": "admin@hotel-abc.it",
        "password": "admin123",
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def demo_hotel_id(client):
    from app.db.database import AsyncSessionFactory
    from sqlalchemy import select
    from app.models.models import Hotel

    async def get():
        async with AsyncSessionFactory() as db:
            hotel = await db.scalar(select(Hotel).where(Hotel.code == "DEMO"))
            return hotel.id if hotel else None
    return asyncio.run(get())


# ── tests ──────────────────────────────────────────────────────────────────────

class TestAIEndpoint:
    """Tests for AI endpoints with multi-tenancy and auth."""

    def test_ai_status_endpoint(self, client):
        """Test AI status endpoint (public)."""
        response = client.get("/api/v1/ai/status")
        assert response.status_code == 200
        data = response.json()
        assert data["overall"] == "operational"

    def test_driver_discovery_requires_hotel_id_and_auth(self, client, auth_headers, demo_hotel_id):
        """Driver discovery richiede hotel_id e auth."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/driver-discovery",
            params={"hotel_id": str(demo_hotel_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    def test_forecast_requires_hotel_id_and_auth(self, client, auth_headers, demo_hotel_id):
        """Forecast richiede hotel_id e auth."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/forecast",
            params={"hotel_id": str(demo_hotel_id), "metric": "notti_vendute", "periods": 6},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6

    def test_anomalies_requires_hotel_id_and_auth(self, client, auth_headers, demo_hotel_id):
        """Anomaly detection richiede hotel_id e auth."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get(
            "/api/v1/ai/anomalies",
            params={"hotel_id": str(demo_hotel_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_driver_discovery_missing_hotel_id(self, client, auth_headers):
        """Senza hotel_id → 422."""
        response = client.get("/api/v1/ai/driver-discovery", headers=auth_headers)
        assert response.status_code == 422

    def test_forecast_missing_hotel_id(self, client, auth_headers):
        """Senza hotel_id → 422."""
        response = client.get("/api/v1/ai/forecast", params={"metric": "notti_vendute"}, headers=auth_headers)
        assert response.status_code == 422

    def test_anomalies_missing_hotel_id(self, client, auth_headers):
        """Senza hotel_id → 422."""
        response = client.get("/api/v1/ai/anomalies", headers=auth_headers)
        assert response.status_code == 422

    def test_driver_discovery_wrong_hotel(self, client, auth_headers, demo_hotel_id):
        """Hotel_id non corrispondente all'utente → 403."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        other_hotel_id = uuid4()
        response = client.get(
            "/api/v1/ai/driver-discovery",
            params={"hotel_id": str(other_hotel_id)},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_forecast_wrong_hotel(self, client, auth_headers, demo_hotel_id):
        """Hotel_id non corrispondente → 403."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        other_hotel_id = uuid4()
        response = client.get(
            "/api/v1/ai/forecast",
            params={"hotel_id": str(other_hotel_id), "metric": "notti_vendute"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_anomalies_wrong_hotel(self, client, auth_headers, demo_hotel_id):
        """Hotel_id non corrispondente → 403."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        other_hotel_id = uuid4()
        response = client.get(
            "/api/v1/ai/anomalies",
            params={"hotel_id": str(other_hotel_id)},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_unauthenticated_access(self, client, demo_hotel_id):
        """Senza auth → 401."""
        if demo_hotel_id is None:
            pytest.skip("No DEMO hotel found")
        response = client.get("/api/v1/ai/driver-discovery", params={"hotel_id": str(demo_hotel_id)})
        assert response.status_code == 401