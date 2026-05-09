"""Tests for ABC Engine edge cases and full coverage."""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from app.core.abc_engine import (
    ABCEngine,
    CostRecord,
    LaborRecord,
    AllocationRuleRecord,
    ServiceRevenueRecord,
    ActivityCost,
    ServiceResult,
    ABCEngineResult,
)


class TestActivityCost:
    """Tests for ActivityCost dataclass."""

    def test_default_values(self):
        """Test default values for ActivityCost."""
        aid = uuid4()
        ac = ActivityCost(activity_id=aid)
        assert ac.activity_id == aid
        assert ac.direct_cost == Decimal("0")
        assert ac.labor_cost == Decimal("0")
        assert ac.overhead_cost == Decimal("0")
        assert ac.inbound_allocated == Decimal("0")

    def test_total_cost_calculation(self):
        """Test total_cost property."""
        aid = uuid4()
        ac = ActivityCost(
            activity_id=aid,
            direct_cost=Decimal("100"),
            labor_cost=Decimal("200"),
            overhead_cost=Decimal("50"),
            inbound_allocated=Decimal("25"),
        )
        assert ac.total_cost == Decimal("375")


class TestServiceResult:
    """Tests for ServiceResult dataclass."""

    def test_default_values(self):
        """Test default values for ServiceResult."""
        sid = uuid4()
        sr = ServiceResult(service_id=sid)
        assert sr.service_id == sid
        assert sr.revenue == Decimal("0")
        assert sr.output_volume is None

    def test_margin_calculations(self):
        """Test margin calculations."""
        sid = uuid4()
        sr = ServiceResult(
            service_id=sid,
            revenue=Decimal("1000"),
            direct_cost=Decimal("300"),
            labor_cost=Decimal("200"),
            overhead_cost=Decimal("100"),
            total_allocated_cost=Decimal("50"),
        )
        assert sr.total_cost == Decimal("650")
        assert sr.gross_margin == Decimal("350")
        assert sr.margin_pct == Decimal("35.00")

    def test_margin_pct_with_zero_revenue(self):
        """Test margin_pct returns None with zero revenue."""
        sid = uuid4()
        sr = ServiceResult(service_id=sid, revenue=Decimal("0"))
        assert sr.margin_pct is None

    def test_cost_per_unit(self):
        """Test cost per unit calculation."""
        sid = uuid4()
        sr = ServiceResult(
            service_id=sid,
            total_allocated_cost=Decimal("1000"),
            output_volume=Decimal("50"),
        )
        assert sr.cost_per_unit == Decimal("20.0000")

    def test_cost_per_unit_with_zero_volume(self):
        """Test cost_per_unit with zero volume returns None."""
        sid = uuid4()
        sr = ServiceResult(
            service_id=sid,
            output_volume=Decimal("0"),
        )
        assert sr.cost_per_unit is None


class TestABCEngineResult:
    """Tests for ABCEngineResult dataclass."""

    def test_aggregate_properties(self):
        """Test aggregate properties."""
        period_id = uuid4()
        aid1, aid2 = uuid4(), uuid4()
        sid1 = uuid4()
        
        result = ABCEngineResult(
            period_id=period_id,
            activity_costs={
                aid1: ActivityCost(activity_id=aid1, direct_cost=Decimal("100")),
                aid2: ActivityCost(activity_id=aid2, direct_cost=Decimal("200")),
            },
            service_results={
                sid1: ServiceResult(
                    service_id=sid1,
                    revenue=Decimal("500"),
                    total_allocated_cost=Decimal("150"),
                ),
            },
        )
        
        assert result.total_cost == Decimal("150")
        assert result.total_revenue == Decimal("500")
        assert result.total_margin == Decimal("350")


class TestABCEnginePhase2:
    """Tests for Phase 2 support activity rollback."""

    def test_support_activity_rollback(self, sample_uuids):
        """Test rollback of support activities."""
        engine = ABCEngine(max_iterations=5)
        
        cost_records = [
            CostRecord(
                cost_item_id=uuid4(),
                cost_center_id=sample_uuids[0],
                cost_type="personale",
                amount=Decimal("1000"),
            ),
        ]
        
        rules = [
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
                level="attivita_ad_attivita",
                source_cost_center_id=None,
                source_activity_id=sample_uuids[1],
                target_activity_id=sample_uuids[0],
                target_service_id=None,
                driver_values={},
                allocation_pct=Decimal("1.0"),
                priority=1,
            ),
        ]
        
        revenues = [
            ServiceRevenueRecord(
                service_id=sample_uuids[2],
                revenue=Decimal("5000"),
                output_volume=Decimal("100"),
            ),
        ]
        
        result = engine.calculate(
            period_id=uuid4(),
            cost_records=cost_records,
            labor_records=[],
            allocation_rules=rules,
            service_revenues=revenues,
            activity_ids=[sample_uuids[0], sample_uuids[1]],
            service_ids=[sample_uuids[2]],
            support_activity_ids=[sample_uuids[1]],
        )
        
        assert result.iterations_used > 0


class TestDriverBasedAllocation:
    """Tests for driver-based allocation."""

    def test_driver_based_allocation(self, sample_uuids):
        """Test allocation based on driver values."""
        engine = ABCEngine()
        
        cost_records = [
            CostRecord(
                cost_item_id=uuid4(),
                cost_center_id=sample_uuids[0],
                cost_type="struttura",
                amount=Decimal("300"),
            ),
        ]
        
        rules = [
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
                driver_values={sample_uuids[2]: Decimal("100")},
                allocation_pct=None,
                priority=1,
            ),
        ]
        
        revenues = [
            ServiceRevenueRecord(
                service_id=sample_uuids[2],
                revenue=Decimal("1000"),
                output_volume=Decimal("10"),
            ),
        ]
        
        result = engine.calculate(
            period_id=uuid4(),
            cost_records=cost_records,
            labor_records=[],
            allocation_rules=rules,
            service_revenues=revenues,
            activity_ids=[sample_uuids[0]],
            service_ids=[sample_uuids[2]],
            support_activity_ids=[],
        )
        
        assert len(result.service_results) == 1