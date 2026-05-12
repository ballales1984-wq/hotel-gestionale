"""Tests for PMS Integration endpoints."""
import os
from pathlib import Path
import pytest
from uuid import uuid4

# Usa un DB SQLite file-based isolato per questo modulo di test
TEST_DB = Path(__file__).parent / "test_pms_temp.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import engine, Base
from app.main import create_app
from app.models.models import Hotel, PMSIntegration, ExternalSystemType
import asyncio


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Crea tabelle + seed hotel DEMO (DB in-memory isolato)."""
    # Reset DB: drop & create per assicurare pulizia
    async def reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset_db())

    async def seed_minimal():
        from app.db.database import AsyncSessionFactory
        from app.db.seed import seed as run_seed
        async with AsyncSessionFactory() as db:
            await run_seed(db)
            await db.commit()
    asyncio.run(seed_minimal())

    app = create_app()
    # Debug: print registered routes
    print("\n=== Registered routes ===")
    for route in app.routes:
        print(route.path, route.methods)
    print("========================\n")
    with TestClient(app) as c:
        yield c


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


# ── tests ─────────────────────────────────────────────────────────────────────

class TestPMSIntegrationCRUD:
    """CRUD operations for PMS integrations."""

    def test_create_pms_integration_success(self, client, demo_hotel_id):
        """Crea una nuova integrazione PMS."""
        unique_name = f"Mews-{uuid4().hex[:8]}"
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": unique_name,
            "system_type": ExternalSystemType.PMS_API.value,
            "api_endpoint": "https://api.mews.com/connector",
            "api_key": "secret-key-123",
            "username": "user@hotel.it",
            "password": "pwd123",
            "sync_frequency_hours": 12,
            "config_data": {"property_id": "DEMO123"},
        }
        r = client.post("/api/v1/pms-integrations/", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["name"] == unique_name
        assert data["system_type"] == "pms_api"
        assert data["is_active"] is True
        assert "id" in data

    def test_create_duplicate_name_fails(self, client, demo_hotel_id):
        """Nome duplicato per stesso hotel → 409 Conflict."""
        unique_name = f"DupTest-{uuid4().hex[:8]}"
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": unique_name,
            "system_type": ExternalSystemType.ERP_API.value,
            "sync_frequency_hours": 24,
        }
        r1 = client.post("/api/v1/pms-integrations/", json=payload)
        assert r1.status_code == 201

        r2 = client.post("/api/v1/pms-integrations/", json=payload)
        assert r2.status_code == 409

    def test_list_filtered_by_hotel(self, client, demo_hotel_id):
        """Lista filtrata per hotel_id restituisce solo le integrazioni di quel hotel."""
        from app.db.database import AsyncSessionFactory
        from app.models.models import Hotel, PMSIntegration as PMSInt

        async def create_other_hotel():
            async with AsyncSessionFactory() as db:
                other = Hotel(code="OTHER", name="Altro Hotel", is_active=True)
                db.add(other)
                await db.flush()
                other_int = PMSIntegration(
                    hotel_id=other.id,
                    name="Opera PMS",
                    system_type=ExternalSystemType.PMS_API,
                    is_active=True,
                )
                db.add(other_int)
                await db.commit()
                return other.id

        other_hotel_id = asyncio.run(create_other_hotel())

        r = client.get(f"/api/v1/pms-integrations/?hotel_id={demo_hotel_id}")
        assert r.status_code == 200
        items = r.json()
        assert all(item["hotel_id"] == str(demo_hotel_id) for item in items)

        r2 = client.get(f"/api/v1/pms-integrations/?hotel_id={other_hotel_id}")
        assert r2.status_code == 200
        items2 = r2.json()
        assert all(item["hotel_id"] == str(other_hotel_id) for item in items2)

    def test_update_pms_integration(self, client, demo_hotel_id):
        """Aggiorna integrazione (cambio endpoint, frequency)."""
        unique_name = f"UpdTest-{uuid4().hex[:8]}"
        create_payload = {
            "hotel_id": str(demo_hotel_id),
            "name": unique_name,
            "system_type": ExternalSystemType.PMS_API.value,
            "sync_frequency_hours": 24,
        }
        r = client.post("/api/v1/pms-integrations/", json=create_payload)
        assert r.status_code == 201
        integration_id = r.json()["id"]

        update_payload = {
            "api_endpoint": "https://new-endpoint.example.com",
            "sync_frequency_hours": 48,
            "is_active": False,
        }
        r2 = client.put(f"/api/v1/pms-integrations/{integration_id}", json=update_payload)
        assert r2.status_code == 200, r2.text
        updated = r2.json()
        assert updated["api_endpoint"] == update_payload["api_endpoint"]
        assert updated["sync_frequency_hours"] == 48
        assert updated["is_active"] is False

    def test_delete_soft(self, client, demo_hotel_id):
        """Delete imposta is_active=False (soft delete)."""
        unique_name = f"DelTest-{uuid4().hex[:8]}"
        create_payload = {
            "hotel_id": str(demo_hotel_id),
            "name": unique_name,
            "system_type": ExternalSystemType.PMS_CSV.value,
        }
        r = client.post("/api/v1/pms-integrations/", json=create_payload)
        assert r.status_code == 201
        integration_id = r.json()["id"]

        r_del = client.delete(f"/api/v1/pms-integrations/{integration_id}")
        assert r_del.status_code == 204

        r_get = client.get(f"/api/v1/pms-integrations/{integration_id}")
        assert r_get.status_code == 200
        assert r_get.json()["is_active"] is False

    def test_invalid_system_type(self, client, demo_hotel_id):
        """Tipo system_type non valido → 400."""
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "Invalid Type",
            "system_type": "unknown_pms",
        }
        r = client.post("/api/v1/pms-integrations/", json=payload)
        assert r.status_code == 400


class TestPMSIntegrationIntegration:
    """Integrazione con imports endpoint."""

    def test_pms_integration_lifecycle(self, client, demo_hotel_id):
        """Scenario completo: create → list → update → delete."""
        unique_name = f"LifeCycle-{uuid4().hex[:8]}"
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": unique_name,
            "system_type": ExternalSystemType.ERP_CSV.value,
            "api_endpoint": "https://zucchetti.example.com/api",
            "sync_frequency_hours": 12,
        }
        r = client.post("/api/v1/pms-integrations/", json=payload)
        assert r.status_code == 201
        integration_id = r.json()["id"]

        r_list = client.get("/api/v1/pms-integrations/")
        assert r_list.status_code == 200
        ids = [i["id"] for i in r_list.json()]
        assert integration_id in ids

        r_up = client.put(f"/api/v1/pms-integrations/{integration_id}", json={"sync_frequency_hours": 6})
        assert r_up.status_code == 200
        assert r_up.json()["sync_frequency_hours"] == 6

        r_del = client.delete(f"/api/v1/pms-integrations/{integration_id}")
        assert r_del.status_code == 204
