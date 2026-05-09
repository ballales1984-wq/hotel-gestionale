"""Tests for ABCEngine core functionality."""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from app.core.abc_engine import ABCEngine, ABCEngineResult


class TestABCEngineBasic:
    """Basic functionality tests for ABCEngine."""

    def test_engine_initialization(self):
        """Test that engine initializes with default parameters."""
        engine = ABCEngine()
        assert engine.max_iterations == 10
        assert engine.convergence_threshold == Decimal("0.001")

    def test_engine_custom_params(self):
        """Test engine with custom parameters."""
        engine = ABCEngine(max_iterations=5, convergence_threshold=0.01)
        assert engine.max_iterations == 5
        assert engine.convergence_threshold == Decimal("0.01")


class TestCostAllocation:
    """Tests for cost allocation functionality."""

    @pytest.mark.asyncio
    async def test_simple_allocation(
        self, engine, sample_cost_records, sample_allocation_rules, sample_service_revenues, sample_uuids
    ):
        """Test basic cost allocation flow."""
        activity_ids = [sample_uuids[0]]
        service_ids = [sample_uuids[2]]
        support_ids = []

        result = engine.calculate(
            period_id=sample_uuids[1],
            cost_records=sample_cost_records,
            labor_records=[],
            allocation_rules=sample_allocation_rules,
            service_revenues=sample_service_revenues,
            activity_ids=activity_ids,
            service_ids=service_ids,
            support_activity_ids=support_ids,
        )

        assert isinstance(result, ABCEngineResult)
        assert len(result.activity_costs) == 1
        assert len(result.service_results) == 1
        assert result.iterations_used == 0

    def test_labor_cost_calculation(self, engine, sample_uuids):
        """Test that labor costs are correctly calculated."""
        from app.core.abc_engine import LaborRecord

        labor = LaborRecord(
            employee_id=uuid4(),
            activity_id=sample_uuids[0],
            hours=Decimal("40"),
            hourly_cost=Decimal("30.00"),
            allocation_pct=Decimal("1.0"),
        )

        assert labor.total_cost == Decimal("1200.00")