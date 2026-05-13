"""Tests for accounting import endpoint (/imports/accounting)."""
import os
from pathlib import Path
import io
import csv
import pytest
from uuid import uuid4
from datetime import datetime

# Usa un DB SQLite file-based isolato per questo modulo di test
TEST_DB = Path(__file__).parent / "test_imports_accounting.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.db.database import engine, Base
from app.main import create_app
from app.models.models import CostItem, AccountingPeriod, Hotel, CostCenter, Department
import asyncio


@pytest.fixture(scope="module")
def client():
    """Crea DB pulito + seed minimale."""
    async def reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset_db())

    async def seed_minimal():
        from app.db.database import AsyncSessionFactory
        from app.models.models import Hotel, CostCenter, AccountingPeriod, Department
        from datetime import datetime
        async with AsyncSessionFactory() as db:
            hotel = Hotel(id=uuid4(), name="Hotel Demo", code="DEMO", is_active=True)
            db.add(hotel)
            await db.flush()
            cc_admin = CostCenter(hotel_id=hotel.id, code="CC-ADMIN", name="Amministrazione", department=Department.ADMIN, is_active=True)
            cc_rec = CostCenter(hotel_id=hotel.id, code="CC-RECEPTION", name="Reception", department=Department.RECEPTION, is_active=True)
            db.add_all([cc_admin, cc_rec])
            today = datetime.now()
            period = AccountingPeriod(
                id=uuid4(),
                hotel_id=hotel.id,
                year=today.year,
                month=today.month,
                name=f"{today.month:02d}/{today.year}",
                is_closed=False,
            )
            db.add(period)
            await db.commit()
    asyncio.run(seed_minimal())

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_import_accounting_csv_success(client):
    """Import CSV contabilità crea CostItem con hotel_id corretto."""
    # CSV con codici cost center corrispondenti a quelli nel seed
    csv_content = """conto,descrizione,centro_di_costo,tipo_costo,importo
60001,Affitto annuale,CC-ADMIN,struttura,2500.00
60002,Stipendi reception,CC-RECEPTION,personale,12000.00
"""
    # Recupera periodo e hotel
    async def get_period_hotel():
        from app.db.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            period = await db.scalar(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()).limit(1))
            hotel = await db.scalar(select(Hotel).where(Hotel.code == "DEMO"))
            return period, hotel
    period, hotel = asyncio.run(get_period_hotel())
    assert period is not None, "Periodo non trovato"
    assert hotel is not None, "Hotel DEMO non trovato"

    files = {'file': ('accounting.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
    data = {'period_id': str(period.id)}
    r = client.post("/api/v1/imports/accounting", files=files, data=data)
    assert r.status_code == 201, r.text
    result = r.json()
    assert result['rows_read'] == 2
    assert result['rows_imported'] == 2
    assert result['rows_skipped'] == 0

    # Verifica CostItem creati con hotel_id e period_id corretti
    async def verify():
        from app.db.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            count = await db.scalar(select(func.count(CostItem.id)).where(
                CostItem.hotel_id == hotel.id,
                CostItem.period_id == period.id
            ))
            return count
    count = asyncio.run(verify())
    assert count == 2
