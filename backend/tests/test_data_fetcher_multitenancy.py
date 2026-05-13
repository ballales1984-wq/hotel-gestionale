"""Tests for AI Data Fetcher multi-tenancy enforcement.

Verifica che tutti i metodi di estrazione dati filtri per hotel_id.
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.ai.data_fetcher import AIDataFetcher
from app.models.models import (
    Hotel, AccountingPeriod, Service, ServiceType, CostCenter, CostItem,
    CostType, LaborAllocation, Employee, DriverValue, CostDriver, ABCResult,
    Department, Activity
)
from app.db.database import AsyncSessionFactory, engine, Base
import asyncio


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    pass  # no cleanup


@pytest.fixture
async def db_session(setup_db):
    async with AsyncSessionFactory() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest.fixture
async def hotel1(db_session):
    """Primo hotel con dati completi."""
    hotel = Hotel(code="HOTEL1", name="Hotel One", is_active=True)
    db_session.add(hotel)
    await db_session.flush()
    return hotel


@pytest.fixture
async def hotel2(db_session):
    """Secondo hotel (isolamento)."""
    hotel = Hotel(code="HOTEL2", name="Hotel Two", is_active=True)
    db_session.add(hotel)
    await db_session.flush()
    return hotel


@pytest.fixture
async def periods_h1(db_session, hotel1):
    """Crea 3 periodi per hotel1 (2025-01, 02, 03)."""
    periods = []
    for m in (1, 2, 3):
        p = AccountingPeriod(
            hotel_id=hotel1.id,
            year=2025,
            month=m,
            name=f"Gennaio {2025}" if m == 1 else f"Febbraio {2025}" if m == 2 else f"Marzo {2025}",
            is_closed=False,
        )
        db_session.add(p)
        await db_session.flush()
        periods.append(p)
    return periods


@pytest.fixture
async def periods_h2(db_session, hotel2):
    """Crea 3 periodi per hotel2 (2025-01, 02, 03)."""
    periods = []
    for m in (1, 2, 3):
        p = AccountingPeriod(
            hotel_id=hotel2.id,
            year=2025,
            month=m,
            name=f"Gennaio {2025}" if m == 1 else f"Febbraio {2025}" if m == 2 else f"Marzo {2025}",
            is_closed=False,
        )
        db_session.add(p)
        await db_session.flush()
        periods.append(p)
    return periods


@pytest.fixture
async def services_h1(db_session, hotel1):
    """Servizi per hotel1: accommodation, restaurant, congress."""
    services = {}
    for code, stype in [("ACCOMM", ServiceType.ACCOMMODATION), ("REST", ServiceType.RESTAURANT), ("CONG", ServiceType.CONGRESS)]:
        svc = Service(
            hotel_id=hotel1.id,
            code=code,
            name=f"Servizio {code}",
            service_type=stype,
            is_active=True,
        )
        db_session.add(svc)
        await db_session.flush()
        services[code] = svc
    return services


@pytest.fixture
async def services_h2(db_session, hotel2):
    """Servizi per hotel2 (stessi tipi)."""
    services = {}
    for code, stype in [("ACCOMM", ServiceType.ACCOMMODATION), ("REST", ServiceType.RESTAURANT)]:
        svc = Service(
            hotel_id=hotel2.id,
            code=f"{code}-H2",
            name=f"Servizio {code} Hotel2",
            service_type=stype,
            is_active=True,
        )
        db_session.add(svc)
        await db_session.flush()
        services[code] = svc
    return services


@pytest.fixture
async def cost_centers_h1(db_session, hotel1):
    """Centri di costo per hotel1."""
    cc = CostCenter(
        hotel_id=hotel1.id,
        code="CC-RECEPTION",
        name="Reception",
        department=Department.RECEPTION,
        is_active=True,
    )
    db_session.add(cc)
    await db_session.flush()
    return cc


@pytest.fixture
async def cost_items_h1(db_session, hotel1, periods_h1, cost_centers_h1):
    """Voci di costo per hotel1."""
    items = []
    for i, period in enumerate(periods_h1):
        # costo lavoro, overhead vari
        ci1 = CostItem(
            hotel_id=hotel1.id,
            period_id=period.id,
            cost_center_id=cost_centers_h1.id,
            account_code="4000",
            account_name="Personale",
            cost_type=CostType.LABOR,
            description="Stipendi reception",
            amount=Decimal(str(10000 + i * 1000)),
            currency="EUR",
            source_system="test",
        )
        ci2 = CostItem(
            hotel_id=hotel1.id,
            period_id=period.id,
            cost_center_id=cost_centers_h1.id,
            account_code="5000",
            account_name="Utilitie",
            cost_type=CostType.UTILITIES,
            description="Bollette",
            amount=Decimal(str(2000 + i * 100)),
            currency="EUR",
            source_system="test",
        )
        db_session.add_all([ci1, ci2])
        await db_session.flush()
        items.extend([ci1, ci2])
    return items


@pytest.fixture
async def employees_h1(db_session, hotel1, cost_centers_h1):
    """Dipendenti per hotel1."""
    emp = Employee(
        hotel_id=hotel1.id,
        employee_code="EMP001",
        full_name="Mario Rossi",
        role="Receptionist",
        department=Department.RECEPTION,
        cost_center_id=cost_centers_h1.id,
        hourly_cost=Decimal("15.00"),
        is_active=True,
    )
    db_session.add(emp)
    await db_session.flush()
    return emp


@pytest.fixture
async def activity_h1(db_session, hotel1, cost_centers_h1):
    """Attività operativa per hotel1 (es. reception)."""
    act = Activity(
        hotel_id=hotel1.id,
        code="ACT-RECEPT",
        name="Attività Reception",
        department=Department.RECEPTION,
        cost_center_id=cost_centers_h1.id,
        is_active=True,
    )
    db_session.add(act)
    await db_session.flush()
    return act


@pytest.fixture
async def labor_allocations_h1(db_session, hotel1, periods_h1, employees_h1, activity_h1):
    """Allocazioni personale per hotel1: ore su attività."""
    allocations = []
    for period in periods_h1:
        la = LaborAllocation(
            hotel_id=hotel1.id,
            period_id=period.id,
            employee_id=employees_h1.id,
            activity_id=activity_h1.id,
            hours=Decimal("160"),
            hourly_cost=Decimal("15.00"),
            allocation_pct=Decimal("1.0"),
            source="test",
        )
        db_session.add(la)
        await db_session.flush()
        allocations.append(la)
    return allocations


@pytest.fixture
async def driver_ore_h1(db_session, hotel1, periods_h1, services_h1):
    """Driver DVR-ORE per hotel1 (collegato al servizio accommodation)."""
    driver = CostDriver(
        hotel_id=hotel1.id,
        code="DRV-ORE",
        name="Ore Lavorate",
        driver_type=DriverType.TIME,
        unit="ore",
        is_active=True,
    )
    db_session.add(driver)
    await db_session.flush()

    # valori per ogni periodo, entity_type='service', entity_id=accommodation
    values = []
    for period in periods_h1:
        dv = DriverValue(
            hotel_id=hotel1.id,
            driver_id=driver.id,
            period_id=period.id,
            entity_type="service",
            entity_id=services_h1["ACCOMM"].id,
            value=Decimal("160"),  # ore totali
            source="test",
        )
        db_session.add(dv)
        await db_session.flush()
        values.append(dv)
    return driver, values


@pytest.fixture
async def abc_results_h1(db_session, hotel1, periods_h1, services_h1):
    """Risultati ABC per hotel1: revenue e output volume."""
    results = []
    for period in periods_h1:
        # Pernottamento
        ar = ABCResult(
            hotel_id=hotel1.id,
            period_id=period.id,
            service_id=services_h1["ACCOMM"].id,
            activity_id=None,
            direct_cost=Decimal("5000"),
            labor_cost=Decimal("8000"),
            overhead_cost=Decimal("2000"),
            total_cost=Decimal("15000"),
            revenue=Decimal("30000"),
            output_volume=Decimal("100"),  # notti
            gross_margin=Decimal("15000"),
            margin_pct=Decimal("50.00"),
            cost_per_unit=Decimal("150.00"),
            calculation_version=1,
            is_validated=False,
        )
        # Ristorazione
        ar2 = ABCResult(
            hotel_id=hotel1.id,
            period_id=period.id,
            service_id=services_h1["REST"].id,
            activity_id=None,
            direct_cost=Decimal("3000"),
            labor_cost=Decimal("5000"),
            overhead_cost=Decimal("1500"),
            total_cost=Decimal("9500"),
            revenue=Decimal("25000"),
            output_volume=Decimal("500"),  # coperti
            gross_margin=Decimal("15500"),
            margin_pct=Decimal("62.00"),
            cost_per_unit=Decimal("19.00"),
            calculation_version=1,
            is_validated=False,
        )
        db_session.add_all([ar, ar2])
        await db_session.flush()
        results.extend([ar, ar2])
    return results


@pytest.fixture
async def data_fetcher(db_session):
    """Fetcher iniettato con sessione DB."""
    return AIDataFetcher(db_session)


# ── tests ──────────────────────────────────────────────────────────────────────

class TestDriverDiscoveryTenancy:
    """Test che get_driver_discovery_data filtri per hotel_id."""

    async def test_returns_only_hotel1_data(
        self, data_fetcher, hotel1, hotel2,
        periods_h1, periods_h2,
        services_h1, services_h2,
        driver_ore_h1,  # solo hotel1 ha driver DVR-ORE
        abc_results_h1
    ):
        """
        hotel1 ha dati completi, hotel2 ha solo periodi.
        Verifica che driver discovery per hotel1 restituisca solo dati hotel1.
        """
        df = await data_fetcher.get_driver_discovery_data(hotel1.id)

        assert not df.empty
        # Tutti i periodi devono essere di hotel1 (i periodi di hotel2 non appaiono)
        # Non abbiamo colonna hotel_id diretta, ma i dati aggregati devono corrispondere a hotel1
        # Verifichiamo che i valori siano quelli di hotel1 (ore_lavorate=160, notti_vendute=100, coperti=500)
        assert len(df) == len(periods_h1)  # solo 3 periodi
        assert all(df["ore_lavorate"] == 160)
        assert all(df["notti_vendute"] == 100)
        assert all(df["coperti"] == 500)

    async def test_hotel2_no_accidental_data(
        self, data_fetcher, hotel2, periods_h2, services_h2
    ):
        """Hotel2 senza alcun dato → DataFrame vuoto."""
        df = await data_fetcher.get_driver_discovery_data(hotel2.id)
        assert df.empty


class TestForecastTenancy:
    """Test multi-tenancy per get_forecast_data."""

    async def test_forecast_filters_hotel(
        self, data_fetcher, hotel1, hotel2,
        periods_h1, periods_h2,
        services_h1, services_h2,
        abc_results_h1
    ):
        """
        Hotel1 ha dati notti_vendute per 3 periodi, hotel2 nessuno.
        Forecast per hotel1 deve restituire 3 record.
        """
        df = await data_fetcher.get_forecast_data(hotel1.id, metric="notti_vendute")

        assert not df.empty
        assert len(df) == len(periods_h1)
        # Verifica valori: ogni periodo ha output_volume 100
        assert all(df["value"] == 100)

    async def test_forecast_hotel2_empty(self, data_fetcher, hotel2):
        df = await data_fetcher.get_forecast_data(hotel2.id, metric="notti_vendute")
        assert df.empty


class TestAnomalyDetectionTenancy:
    """Test multi-tenancy per get_anomaly_detection_data."""

    async def test_anomaly_filters_hotel(
        self, data_fetcher, hotel1, hotel2,
        periods_h1, periods_h2,
        cost_items_h1, labor_allocations_h1, abc_results_h1
    ):
        """
        Dati costo_lavoro, ore, volume_output solo per hotel1.
        Verifica che risultato contenga solo hotel1.
        """
        df = await data_fetcher.get_anomaly_detection_data(hotel1.id)

        assert not df.empty
        assert len(df) == len(periods_h1)
        # costo_lavoro per ogni periodo = sum(cost_item LABOR) = ~10000+...
        # Non verifichiamo valori precisi, solo presenza.
        assert "costo_lavoro" in df.columns
        assert "ore" in df.columns
        assert "volume_output" in df.columns

    async def test_anomaly_hotel2_empty(self, data_fetcher, hotel2):
        df = await data_fetcher.get_anomaly_detection_data(hotel2.id)
        assert df.empty
