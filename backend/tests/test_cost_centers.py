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
from app.models.models import Hotel, CostCenter, Department, User, UserRole
import asyncio


@pytest.fixture(scope="module")
def client():
    async def reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset_db())

    async def seed_data():
        from app.db.database import AsyncSessionFactory
        from app.core.encryption import get_encryption_service
        async with AsyncSessionFactory() as db:
            # Hotel DEMO
            hotel = Hotel(code="DEMO", name="Hotel Demo", is_active=True)
            db.add(hotel)
            await db.flush()

            # Utente di test
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed = pwd_context.hash("testpassword123")
            user = User(
                email="test@example.com",
                full_name="Test User",
                hashed_password=hashed,
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
    """Restituisce header di autorizzazione per un utente admin."""
    # Login per ottenere token
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


class TestCostCentersCRUD:
    """CRUD operations for Cost Centers (richiede auth)."""

    def test_create_cost_center(self, client, auth_headers, demo_hotel_id):
        payload = {
            "hotel_id": str(demo_hotel_id),
            "code": "CC-RECEPTION",
            "name": "Reception",
            "department": Department.RECEPTION.value,
        }
        r = client.post("/api/v1/cost-centers/", json=payload, headers=auth_headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "CC-RECEPTION"
        assert data["name"] == "Reception"

    def test_list_filtered_by_hotel(self, client, auth_headers, demo_hotel_id):
        r = client.get("/api/v1/cost-centers/", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()
        assert all(item["hotel_id"] == str(demo_hotel_id) for item in items)

    def test_update_cost_center(self, client, auth_headers, demo_hotel_id):
        create = client.post("/api/v1/cost-centers/", json={
            "hotel_id": str(demo_hotel_id),
            "code": "CC-HOUSEK",
            "name": "Housekeeping",
            "department": Department.HOUSEKEEPING.value,
        }, headers=auth_headers)
        assert create.status_code == 201
        cc_id = create.json()["id"]

        update = client.put(f"/api/v1/cost-centers/{cc_id}", json={"name": "Housekeeping Updated"}, headers=auth_headers)
        assert update.status_code == 200
        assert update.json()["name"] == "Housekeeping Updated"

    def test_delete_soft(self, client, auth_headers, demo_hotel_id):
        create = client.post("/api/v1/cost-centers/", json={
            "hotel_id": str(demo_hotel_id),
            "code": "CC-FNB",
            "name": "Food & Beverage",
            "department": Department.FNB.value,
        }, headers=auth_headers)
        assert create.status_code == 201
        cc_id = create.json()["id"]

        delete = client.delete(f"/api/v1/cost-centers/{cc_id}", headers=auth_headers)
        assert delete.status_code == 204

        get = client.get(f"/api/v1/cost-centers/{cc_id}", headers=auth_headers)
        assert get.status_code == 200
        assert get.json()["is_active"] is False

    def test_unauthorized_access(self, client, demo_hotel_id):
        """Senza auth → 401."""
        r = client.get("/api/v1/cost-centers/")
        assert r.status_code == 401
