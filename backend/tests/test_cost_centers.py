"""Tests for Cost Centers endpoints."""
import os
from pathlib import Path
import pytest
from uuid import uuid4

TEST_DB = Path(__file__).parent / "test_cost_centers_temp.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import engine, Base
from app.main import create_app
from app.models.models import Hotel, CostCenter, Department
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


class TestCostCentersCRUD:
    """CRUD operations for Cost Centers."""

    def test_create_cost_center(self, client, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "code": "CC-RECEPTION",
            "name": "Reception",
            "department": Department.RECEPTION.value,
        }
        r = client.post("/api/v1/cost-centers/", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "CC-RECEPTION"
        assert data["name"] == "Reception"
        assert data["department"] == "reception"
        assert data["is_active"] is True

    def test_list_filtered_by_hotel(self, client, demo_hotel_id):
        r = client.get("/api/v1/cost-centers/")
        assert r.status_code == 200
        items = r.json()
        assert all(item["hotel_id"] == str(demo_hotel_id) for item in items)

    def test_update_cost_center(self, client, demo_hotel_id):
        # Create first
        create = client.post("/api/v1/cost-centers/", json={
            "hotel_id": str(demo_hotel_id),
            "code": "CC-HOUSEK",
            "name": "Housekeeping",
            "department": Department.HOUSEKEEPING.value,
        })
        assert create.status_code == 201
        cc_id = create.json()["id"]

        update = client.put(f"/api/v1/cost-centers/{cc_id}", json={"name": "Housekeeping Updated"})
        assert update.status_code == 200
        assert update.json()["name"] == "Housekeeping Updated"

    def test_delete_soft(self, client, demo_hotel_id):
        create = client.post("/api/v1/cost-centers/", json={
            "hotel_id": str(demo_hotel_id),
            "code": "CC-FNB",
            "name": "Food & Beverage",
            "department": Department.FNB.value,
        })
        assert create.status_code == 201
        cc_id = create.json()["id"]

        delete = client.delete(f"/api/v1/cost-centers/{cc_id}")
        assert delete.status_code == 204

        get = client.get(f"/api/v1/cost-centers/{cc_id}")
        assert get.status_code == 200
        assert get.json()["is_active"] is False

    def test_invalid_department(self, client, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "code": "CC-X",
            "name": "Invalid",
            "department": "unknown",
        }
        r = client.post("/api/v1/cost-centers/", json=payload)
        assert r.status_code == 400
