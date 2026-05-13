"""Tests for PMS Sync Service (pms_sync.py)."""
import os
from pathlib import Path
import pytest
import csv
import io
import asyncio
from decimal import Decimal
from uuid import uuid4, UUID
from datetime import datetime, date

from app.core.pms_sync import (
    run_sync,
    _sync_pms_csv,
    _find_service,
    _get_or_create_period,
    SyncResult
)
from app.models.models import (
    Hotel, Service, AccountingPeriod, PMSIntegration,
    ExternalSystemType, ServiceType, DataImportLog, ServiceRevenue,
    MappingRule, MappingType
)
from app.db.database import AsyncSessionFactory, engine, Base

# ── Isolamento DB: usa SQLite file temporaneo per questo modulo ──────────────
TEST_DB = Path(__file__).parent / "test_pms_sync_temp.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
from decimal import Decimal
from uuid import uuid4, UUID
from datetime import datetime, date
from pathlib import Path

from app.core.pms_sync import (
    run_sync,
    _sync_pms_csv,
    _find_service,
    _get_or_create_period,
    SyncResult
)
from app.models.models import (
    Hotel, Service, AccountingPeriod, PMSIntegration,
    ExternalSystemType, ServiceType, DataImportLog, ServiceRevenue,
    MappingRule, MappingType
)
from app.db.database import AsyncSessionFactory, engine, Base


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for the module."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def setup_db():
    """Crea tutte le tabelle e le mantiene per il modulo."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Non droppa alla fine per velocità; pulizia manuale in test se necessario


@pytest.fixture
async def db_session(setup_db):
    """Fornisce una sessione DB pulita per ogni test, con rollback."""
    async with AsyncSessionFactory() as session:
        # Inizia transazione
        await session.begin()
        yield session
        await session.rollback()


@pytest.fixture
async def demo_hotel(db_session):
    """Crea un hotel di test."""
    hotel = Hotel(
        code="TEST-HOTEL",
        name="Hotel di Test Sync",
        is_active=True,
    )
    db_session.add(hotel)
    await db_session.flush()
    return hotel


@pytest.fixture
async def second_hotel(db_session):
    """Crea un secondo hotel per test di isolamento multi-tenant."""
    hotel = Hotel(
        code="TEST-HOTEL-2",
        name="Secondo Hotel",
        is_active=True,
    )
    db_session.add(hotel)
    await db_session.flush()
    return hotel


@pytest.fixture
async def demo_service(db_session, demo_hotel):
    """Crea un servizio di test per l'hotel principale."""
    service = Service(
        hotel_id=demo_hotel.id,
        code="ACCOMM-001",
        name="Pernottamento Standard",
        service_type=ServiceType.ACCOMMODATION,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    return service


@pytest.fixture
async def demo_service2(db_session, second_hotel):
    """Crea un servizio per il secondo hotel (usato in test multi-tenant)."""
    service = Service(
        hotel_id=second_hotel.id,
        code="ACCOMM-002",
        name="Pernottamento Hotel2",
        service_type=ServiceType.ACCOMMODATION,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    return service


@pytest.fixture
async def demo_period(db_session, demo_hotel):
    """Crea periodo contabile Maggio 2025."""
    period = AccountingPeriod(
        hotel_id=demo_hotel.id,
        year=2025,
        month=5,
        name="Maggio 2025",
        is_closed=False,
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest.fixture
async def demo_period_june(db_session, demo_hotel):
    """Crea periodo Giugno 2025."""
    period = AccountingPeriod(
        hotel_id=demo_hotel.id,
        year=2025,
        month=6,
        name="Giugno 2025",
        is_closed=False,
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest.fixture
async def pms_integration(db_session, demo_hotel):
    """Crea integrazione PMS CSV attiva."""
    integration = PMSIntegration(
        hotel_id=demo_hotel.id,
        name="Test CSV Integration",
        system_type=ExternalSystemType.PMS_CSV,
        is_active=True,
        sync_frequency_hours=24,
        config_data={"delimiter": ","},
    )
    db_session.add(integration)
    await db_session.flush()
    return integration


@pytest.fixture
async def pms_integration_hotel2(db_session, second_hotel):
    """Crea integrazione per il secondo hotel (test multi-tenant)."""
    integration = PMSIntegration(
        hotel_id=second_hotel.id,
        name="Hotel2 CSV Integration",
        system_type=ExternalSystemType.PMS_CSV,
        is_active=True,
        sync_frequency_hours=24,
        config_data={"delimiter": ","},
    )
    db_session.add(integration)
    await db_session.flush()
    return integration


# ── unit tests ─────────────────────────────────────────────────────────────────

class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_create_success(self):
        result = SyncResult(
            status="success",
            hotel_id=uuid4(),
            integration_id=uuid4(),
            records_imported=10,
            errors=[],
        )
        assert result.status == "success"
        assert result.records_imported == 10
        assert result.errors == []

    def test_create_partial(self):
        result = SyncResult(
            status="partial",
            hotel_id=uuid4(),
            integration_id=uuid4(),
            records_imported=5,
            errors=["Errore riga 3", "Errore riga 7"],
        )
        assert result.status == "partial"
        assert len(result.errors) == 2

    def test_create_error(self):
        result = SyncResult(
            status="error",
            hotel_id=uuid4(),
            integration_id=uuid4(),
            records_imported=0,
            errors=["File non trovato"],
        )
        assert result.status == "error"
        assert result.records_imported == 0


class TestHelperFindService:
    """Test _find_service helper."""

    async def test_find_by_code_success(self, db_session, demo_hotel, demo_service):
        """Trova servizio per codice interno."""
        svc = await _find_service(db_session, demo_hotel.id, "ACCOMM-001")
        assert svc is not None
        assert svc.id == demo_service.id

    async def test_find_by_code_not_found(self, db_session, demo_hotel):
        """Codice inesistente → None."""
        svc = await _find_service(db_session, demo_hotel.id, "NON-EXISTENT")
        assert svc is None

    async def test_find_via_mapping_rule(self, db_session, demo_hotel, demo_service):
        """Cerca servizio tramite MappingRule (external_code → service)."""
        external_code = "EXT-CODE-123"
        rule = MappingRule(
            hotel_id=demo_hotel.id,
            mapping_type=MappingType.SERVICE,
            external_code=external_code,
            target_service_id=demo_service.id,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.flush()

        svc = await _find_service(db_session, demo_hotel.id, external_code)
        assert svc is not None
        assert svc.id == demo_service.id


class TestHelperGetOrCreatePeriod:
    """Test _get_or_create_period helper."""

    async def test_creates_new_period(self, db_session, demo_hotel):
        """Crea periodo se non esiste."""
        test_date = datetime(2025, 8, 1)
        period = await _get_or_create_period(db_session, demo_hotel.id, test_date)
        assert period is not None
        assert period.year == 2025
        assert period.month == 8
        assert period.name == "Agosto 2025"

    async def test_returns_existing_period(self, db_session, demo_hotel, demo_period):
        """Restituisce periodo esistente."""
        test_date = datetime(2025, 5, 15)
        period = await _get_or_create_period(db_session, demo_hotel.id, test_date)
        assert period.id == demo_period.id


# ── integration tests: CSV sync ────────────────────────────────────────────────

class TestCSVSync:
    """Test per sincronizzazione CSV (locale)."""

    def create_csv_bytes(self, rows: list, delimiter=",") -> bytes:
        """Helper per generare CSV in memoria."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerow(["date", "service_code", "revenue", "output_volume"])
        for row in rows:
            writer.writerow(row)
        return output.getvalue().encode("utf-8")

    async def test_sync_csv_valid_rows(
        self, db_session, demo_hotel, pms_integration, demo_service, demo_period, tmp_path
    ):
        """Import CSV con righe valide → record ServiceRevenue creati."""
        # Prepara CSV file
        csv_rows = [
            ["2025-05-01", "ACCOMM-001", "15000", "100"],
            ["2025-05-02", "ACCOMM-001", "16000", "105"],
            ["2025-05-03", "ACCOMM-001", "15500", "98"],
        ]
        csv_bytes = self.create_csv_bytes(csv_rows)

        # Salva file temporaneo
        csv_file = tmp_path / "revenue.csv"
        csv_file.write_bytes(csv_bytes)

        # Modifica config per puntare al file
        pms_integration.config_data = {"file_path": str(csv_file), "delimiter": ","}

        # Esegui sync
        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )

        assert result.status == "success"
        assert result.records_imported == 3
        assert result.errors == []

        # Verifica dati importati
        await db_session.flush()
        stmt = select(ServiceRevenue).where(
            ServiceRevenue.hotel_id == demo_hotel.id,
            ServiceRevenue.period_id == demo_period.id,
            ServiceRevenue.service_id == demo_service.id,
        )
        revenues = (await db_session.execute(stmt)).scalars().all()
        assert len(revenues) == 1
        sr = revenues[0]
        assert sr.revenue == Decimal("46500")  # 15000+16000+15500
        assert sr.output_volume == Decimal("303")  # 100+105+98

    async def test_sync_csv_invalid_dates(
        self, db_session, demo_hotel, pms_integration, demo_service, demo_period, tmp_path
    ):
        """Righe con date non valide → errori, righe valide comunque importate."""
        csv_rows = [
            ["2025-05-01", "ACCOMM-001", "15000", "100"],  # valida
            ["invalid-date", "ACCOMM-001", "16000", "105"],  # data non valida
            ["2025-05-03", "ACCOMM-001", "15500", "98"],  # valida
        ]
        csv_bytes = self.create_csv_bytes(csv_rows)
        csv_file = tmp_path / "revenue_bad.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )

        assert result.status == "partial"
        assert result.records_imported == 2  # solo valide
        assert len(result.errors) == 1
        assert "data non valido" in result.errors[0].lower()

    async def test_sync_csv_missing_required_columns(self, db_session, demo_hotel, pms_integration, tmp_path):
        """CSV senza colonna 'revenue' → errore."""
        csv_bytes = self.create_csv_bytes([["2025-05-01", "ACCOMM-001", "15000"]])  # manca output_volume (opzionale OK)
        # Modifichiamo per mancare revenue
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "service_code"])  # niente revenue
        writer.writerow(["2025-05-01", "ACCOMM-001"])
        csv_bytes = output.getvalue().encode("utf-8")

        csv_file = tmp_path / "bad.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )
        assert result.status == "error"
        assert result.records_imported == 0
        assert any("mancanti" in e.lower() for e in result.errors)

    async def test_sync_csv_service_not_found(self, db_session, demo_hotel, pms_integration, demo_period, tmp_path):
        """Codice servizio non mappato → errore e skip."""
        csv_bytes = self.create_csv_bytes([["2025-05-01", "UNKNOWN-SVC", "15000", "100"]])
        csv_file = tmp_path / "unknown.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )

        assert result.status == "partial"  # 0 imported ma non error fatale
        assert result.records_imported == 0
        assert any("servizio" in e.lower() and "non trovato" in e.lower() for e in result.errors)

    async def test_sync_csv_mixed_success_partial(
        self, db_session, demo_hotel, pms_integration, demo_service, demo_period, tmp_path
    ):
        """Mix righe valide e non → status 'partial'."""
        csv_rows = [
            ["2025-05-01", "ACCOMM-001", "15000", "100"],  # ok
            ["2025-05-02", "ACCOMM-001", "16000", "105"],  # ok
            ["2025-05-03", "UNKNOWN", "15500", "98"],     # servizio non trovato → skip
            ["2025-05-04", "ACCOMM-001", "not-a-number", "100"],  # revenue non valida
        ]
        csv_bytes = self.create_csv_bytes(csv_rows)
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )

        assert result.status == "partial"
        assert result.records_imported == 2  # prime due righe valide
        assert len(result.errors) >= 2  # almeno 2 errori (servizio + numero)

    async def test_sync_csv_creates_period_if_missing(
        self, db_session, demo_hotel, pms_integration, demo_service, tmp_path
    ):
        """Se il periodo non esiste, viene creato automaticamente."""
        # Usiamo data Giugno 2025 → periodo non ancora presente
        csv_rows = [
            ["2025-06-01", "ACCOMM-001", "17000", "110"],
        ]
        csv_bytes = self.create_csv_bytes(csv_rows)
        csv_file = tmp_path / "june.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        result = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )

        assert result.status == "success"
        assert result.records_imported == 1

        # Verifica periodo creato
        period_stmt = select(AccountingPeriod).where(
            AccountingPeriod.hotel_id == demo_hotel.id,
            AccountingPeriod.year == 2025,
            AccountingPeriod.month == 6,
        )
        period = (await db_session.execute(period_stmt)).scalar_one_or_none()
        assert period is not None

    async def test_sync_csv_multi_tenant_isolation(
        self, db_session, demo_hotel, second_hotel, pms_integration, pms_integration_hotel2,
        demo_service, demo_service2, tmp_path
    ):
        """
        Verifica che i dati dell'hotel2 non vengano importati nell'hotel1
        anche se service_code uguale o diverso.
        """
        # CSV per hotel1 (service_code ACCOMM-001)
        csv1 = self.create_csv_bytes([["2025-05-01", "ACCOMM-001", "10000", "50"]])
        file1 = tmp_path / "hotel1.csv"
        file1.write_bytes(csv1)
        pms_integration.config_data = {"file_path": str(file1)}

        result1 = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration,
            hotel=demo_hotel,
            config_data=pms_integration.config_data,
        )
        assert result1.status == "success"
        assert result1.records_imported == 1

        # CSV per hotel2 (service_code ACCOMM-002)
        csv2 = self.create_csv_bytes([["2025-05-01", "ACCOMM-002", "20000", "80"]])
        file2 = tmp_path / "hotel2.csv"
        file2.write_bytes(csv2)
        pms_integration_hotel2.config_data = {"file_path": str(file2)}

        result2 = await _sync_pms_csv(
            db=db_session,
            integration=pms_integration_hotel2,
            hotel=second_hotel,
            config_data=pms_integration_hotel2.config_data,
        )
        assert result2.status == "success"
        assert result2.records_imported == 1

        # Verifica isolamento: servizi revenue separati
        revenues_h1 = (await db_session.execute(
            select(ServiceRevenue).where(ServiceRevenue.hotel_id == demo_hotel.id)
        )).scalars().all()
        revenues_h2 = (await db_session.execute(
            select(ServiceRevenue).where(ServiceRevenue.hotel_id == second_hotel.id)
        )).scalars().all()

        assert len(revenues_h1) == 1
        assert len(revenues_h2) == 1
        assert revenues_h1[0].service_id == demo_service.id
        assert revenues_h2[0].service_id == demo_service2.id
        assert revenues_h1[0].revenue == Decimal("10000")
        assert revenues_h2[0].revenue == Decimal("20000")


# ── run_sync end-to-end tests ─────────────────────────────────────────────────

class TestRunSync:
    """Test per la funzione run_sync (background task entrypoint)."""

    async def test_run_sync_success_csv(
        self, db_session, demo_hotel, pms_integration, demo_service, demo_period, tmp_path
    ):
        """run_sync esegue full pipeline: decript, sync, log."""
        # Prepara CSV
        csv_bytes = b"date,service_code,revenue,output_volume\n2025-05-01,ACCOMM-001,12345,67\n"
        csv_file = tmp_path / "revenue.csv"
        csv_file.write_bytes(csv_bytes)
        pms_integration.config_data = {"file_path": str(csv_file)}

        # Rendi persistenti le entità (integrazione, hotel, service, period) per la nuova sessione
        await db_session.commit()

        # Esegui
        result = await run_sync(pms_integration.id)

        assert result.status == "success"
        assert result.records_imported == 1
        assert result.integration_id == pms_integration.id

        # Verifica log import (nella nuova sessione, usa AsyncSessionFactory)
        async with AsyncSessionFactory() as verify_db:
            log_stmt = select(DataImportLog).where(
                DataImportLog.hotel_id == demo_hotel.id,
                DataImportLog.import_type == "pms",
            )
            log = (await verify_db.execute(log_stmt)).scalar_one_or_none()
            assert log is not None
            assert log.status == "success"
            assert "pms_" in log.batch_id

    async def test_run_sync_inactive_integration(self, db_session, demo_hotel):
        """Integration disattivata → errore."""
        # Creiamo integration tramite db_session e committiamo
        integration = PMSIntegration(
            hotel_id=demo_hotel.id,
            name="Inactive Sync",
            system_type=ExternalSystemType.PMS_CSV,
            is_active=False,
        )
        db_session.add(integration)
        await db_session.commit()

        result = await run_sync(integration.id)
        assert result.status == "error"
        assert "disattivata" in result.errors[0].lower()

    async def test_run_sync_missing_config(
        self, db_session, demo_hotel, pms_integration
    ):
        """Configurazione incompleta (no file_path) → errore."""
        pms_integration.config_data = {}  # nessun file_path
        await db_session.commit()

        result = await run_sync(pms_integration.id)
        assert result.status == "error"
        assert any("file_path" in e.lower() for e in result.errors)


# ── API endpoint tests (HTTP) ─────────────────────────────────────────────────

class TestPMSSyncAPI:
    """Test per endpoint REST /sync."""

    @pytest.fixture
    def client(self, setup_db):
        """FastAPI TestClient (sincrono)."""
        from fastapi.testclient import TestClient
        from app.main import create_app
        # Seed minimale per avere hotel DEMO
        async def seed_mini():
            from app.db.seed import seed as run_seed
            async with AsyncSessionFactory() as db:
                await run_seed(db)
                await db.commit()
        asyncio.run(seed_mini())
        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_sync_endpoint_returns_queued(self, client, demo_hotel_id):
        """POST /pms-integrations/{id}/sync restituisce status queued."""
        # Prima crea un'integrazione
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "API Test Sync",
            "system_type": "pms_csv",
            "config_data": {"file_path": "/tmp/dummy.csv"},
        }
        r = client.post("/api/v1/pms-integrations/", json=payload)
        assert r.status_code == 201
        integration_id = r.json()["id"]

        # Ora chiama sync
        r_sync = client.post(f"/api/v1/pms-integrations/{integration_id}/sync")
        assert r_sync.status_code == 200
        data = r_sync.json()
        assert data["status"] == "queued"
        assert data["integration_id"] == integration_id

    def test_sync_endpoint_404(self, client):
        """Integration ID inesistente → 404."""
        r = client.post(f"/api/v1/pms-integrations/{uuid4()}/sync")
        assert r.status_code == 404

    def test_sync_inactive_integration(self, client, demo_hotel_id):
        """Integration disattivata → 400."""
        payload = {
            "hotel_id": str(demo_hotel_id),
            "name": "Inactive Sync",
            "system_type": "pms_csv",
            "is_active": False,
        }
        r = client.post("/api/v1/pms-integrations/", json=payload)
        assert r.status_code == 201
        integration_id = r.json()["id"]

        r_sync = client.post(f"/api/v1/pms-integrations/{integration_id}/sync")
        assert r_sync.status_code == 400
        assert "disattivata" in r_sync.json()["detail"].lower()
