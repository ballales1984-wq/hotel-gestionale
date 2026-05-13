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
from app.models.models import Hotel, User, UserRole
import asyncio
from passlib.context import CryptContext


@pytest.fixture(scope="module")
def client():
    async def reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset_db())

    async def seed_data():
        from app.db.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            hotel = Hotel(code="DEMO", name="Hotel Demo", is_active=True)
            db.add(hotel)
            await db.flush()

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            user = User(
                email="test@example.com",
                full_name="Test User",
                hashed_password=pwd_context.hash("testpassword123"),
                role=UserRole.ADMIN,
                hotel_id=hotel.id,
                is_active=True,
            )
            db.add(user)
            await db.commit()
    asyncio.run(seed_data())

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/v1/auth/login", data={
        "username": "test@example.com",
        "password": "testpassword123",
    })
    assert r.status_code == 200
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


class TestCostDriversCRUD:
    """CRUD operations for Cost Drivers (richiede auth)."""

    def test_create_driver(self, client, auth_headers, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "Ore Lavorate",
            "code": "DRV-ORE",
            "driver_type": "time",
            "unit": "ore",
            "description": "Totale ore lavorate",
        }
        r = client.post("/api/v1/cost-drivers/", json=payload, headers=auth_headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "DRV-ORE"
        assert data["driver_type"] == "time"

    def test_list_drivers(self, client, auth_headers, demo_hotel_id):
        r = client.get("/api/v1/cost-drivers/", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()
        assert all(item["hotel_id"] == str(demo_hotel_id) for item in items)

    def test_update_driver(self, client, auth_headers, demo_hotel_id):
        create = client.post("/api/v1/cost-drivers/", json={
            "hotel_id": str(demo_hotel_id),
            "name": "Notti Vendute",
            "code": "DRV-NOTTI",
            "driver_type": "volume",
            "unit": "notti",
        }, headers=auth_headers)
        assert create.status_code == 201
        driver_id = create.json()["id"]

        update = client.put(f"/api/v1/cost-drivers/{driver_id}", json={"name": "Notti Vendute Updated"}, headers=auth_headers)
        assert update.status_code == 200
        assert update.json()["name"] == "Notti Vendute Updated"

    def test_delete_driver_soft(self, client, auth_headers, demo_hotel_id):
        create = client.post("/api/v1/cost-drivers/", json={
            "hotel_id": str(demo_hotel_id),
            "name": "Coperti",
            "code": "DRV-COPERTI",
            "driver_type": "volume",
            "unit": "coperti",
        }, headers=auth_headers)
        assert create.status_code == 201
        driver_id = create.json()["id"]

        delete = client.delete(f"/api/v1/cost-drivers/{driver_id}", headers=auth_headers)
        assert delete.status_code == 204

        get = client.get(f"/api/v1/cost-drivers/{driver_id}", headers=auth_headers)
        assert get.status_code == 200
        assert get.json()["is_active"] is False

    def test_unauthorized_access(self, client):
        r = client.get("/api/v1/cost-drivers/")
        assert r.status_code == 401
