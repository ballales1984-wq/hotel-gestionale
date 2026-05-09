import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from app.core.abc_engine import (
    ABCEngine,
    CostRecord,
    LaborRecord,
    AllocationRuleRecord,
    ServiceRevenueRecord,
)


@pytest.fixture
def sample_uuid():
    return uuid4()


@pytest.fixture
def sample_uuids():
    """Return 3 UUIDs for testing: cost_center, activity, service."""
    return [uuid4(), uuid4(), uuid4()]


@pytest.fixture
def engine():
    return ABCEngine()


@pytest.fixture
def sample_cost_records(sample_uuids):
    return [
        CostRecord(
            cost_item_id=uuid4(),
            cost_center_id=sample_uuids[0],
            cost_type="personale",
            amount=Decimal("10000"),
        ),
        CostRecord(
            cost_item_id=uuid4(),
            cost_center_id=sample_uuids[0],
            cost_type="struttura",
            amount=Decimal("5000"),
        ),
    ]


@pytest.fixture
def sample_labor_records(sample_uuids):
    return [
        LaborRecord(
            employee_id=uuid4(),
            activity_id=sample_uuids[0],
            hours=Decimal("160"),
            hourly_cost=Decimal("25.00"),
            allocation_pct=Decimal("1.0"),
        ),
    ]


@pytest.fixture
def sample_allocation_rules(sample_uuids):
    return [
        AllocationRuleRecord(
            rule_id=uuid4(),
            level="costo_ad_attivita",
            source_cost_center_id=sample_uuids[0],
            source_activity_id=None,
            target_activity_id=sample_uuids[0],
            target_service_id=None,
            driver_values={},
            allocation_pct=Decimal("1.0"),
            priority=1,
        ),
        AllocationRuleRecord(
            rule_id=uuid4(),
            level="attivita_a_servizio",
            source_cost_center_id=None,
            source_activity_id=sample_uuids[0],
            target_activity_id=None,
            target_service_id=sample_uuids[2],
            driver_values={},
            allocation_pct=Decimal("1.0"),
            priority=1,
        ),
    ]


@pytest.fixture
def sample_service_revenues(sample_uuids):
    return [
        ServiceRevenueRecord(
            service_id=sample_uuids[2],
            revenue=Decimal("50000"),
            output_volume=Decimal("1000"),
        ),
    ]