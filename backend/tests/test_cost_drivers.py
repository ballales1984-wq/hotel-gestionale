"""Tests for Cost Drivers endpoints."""
import os
from pathlib import Path
import pytest
from uuid import uuid4

TEST_DB = Path(__file__).parent / "test_cost_drivers_temp.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.db.database import engine, Base
from app.main import create_app
from app.models.models import Hotel
import asyncio


@pytest.fixture(scope="module")
def client():
    async def reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset_db())

    async def seed_hotel():
        from app.db.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            hotel = Hotel(code="DEMO", name="Hotel Demo", is_active=True)
            db.add(hotel)
            await db.commit()
    asyncio.run(seed_hotel())

    app = create_app()
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


class TestCostDriversCRUD:
    """CRUD operations for Cost Drivers."""

    def test_create_driver(self, client, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "Ore Lavorate",
            "code": "DRV-ORE",
            "driver_type": "time",
            "unit": "ore",
            "description": "Totale ore lavorate",
        }
        r = client.post("/api/v1/cost-drivers/", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "DRV-ORE"
        assert data["driver_type"] == "time"
        assert data["unit"] == "ore"

    def test_list_drivers(self, client, demo_hotel_id):
        r = client.get("/api/v1/cost-drivers/")
        assert r.status_code == 200
        items = r.json()
        assert all(item["hotel_id"] == str(demo_hotel_id) for item in items)

    def test_update_driver(self, client, demo_hotel_id):
        create = client.post("/api/v1/cost-drivers/", json={
            "hotel_id": str(demo_hotel_id),
            "name": "Notti Vendute",
            "code": "DRV-NOTTI",
            "driver_type": "volume",
            "unit": "notti",
        })
        assert create.status_code == 201
        driver_id = create.json()["id"]

        update = client.put(f"/api/v1/cost-drivers/{driver_id}", json={"name": "Notti Vendute Updated"})
        assert update.status_code == 200
        assert update.json()["name"] == "Notti Vendute Updated"

    def test_delete_driver_soft(self, client, demo_hotel_id):
        create = client.post("/api/v1/cost-drivers/", json={
            "hotel_id": str(demo_hotel_id),
            "name": "Coperti",
            "code": "DRV-COPERTI",
            "driver_type": "volume",
            "unit": "coperti",
        })
        assert create.status_code == 201
        driver_id = create.json()["id"]

        delete = client.delete(f"/api/v1/cost-drivers/{driver_id}")
        assert delete.status_code == 204

        get = client.get(f"/api/v1/cost-drivers/{driver_id}")
        assert get.status_code == 200
        assert get.json()["is_active"] is False

    def test_invalid_driver_type(self, client, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "Invalid",
            "code": "DRV-INV",
            "driver_type": "unknown",
            "unit": "x",
        }
        r = client.post("/api/v1/cost-drivers/", json=payload)
        assert r.status_code == 400
