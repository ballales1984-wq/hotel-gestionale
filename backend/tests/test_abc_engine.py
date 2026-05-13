"""
Test suite per il motore Activity-Based Costing (ABC).
Testa le 4 fasi del calcolo ABC con dati mock realistici.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from uuid import uuid4

from app.core.abc_engine import (
    ABCEngine, CostRecord, LaborRecord, AllocationRuleRecord,
    ServiceRevenueRecord,
)


def _rule(level, scc=None, sa=None, ta=None, ts=None,
          driver_values=None, pct=None, priority=10, rid=None):
    """Helper per costruire AllocationRuleRecord."""
    return AllocationRuleRecord(
        rule_id=rid or uuid4(),
        level=level,
        source_cost_center_id=scc,
        source_activity_id=sa,
        target_activity_id=ta,
        target_service_id=ts,
        driver_values=driver_values or {},
        allocation_pct=pct,
        priority=priority,
    )


class TestABCEngineInitialization:
    def test_default_parameters(self):
        e = ABCEngine()
        assert e.max_iterations == 10
        assert e.convergence_threshold == Decimal("0.001")

    def test_custom_parameters(self):
        e = ABCEngine(max_iterations=20, convergence_threshold=0.01)
        assert e.max_iterations == 20
        assert e.convergence_threshold == Decimal("0.01")


class TestABCEngineDirectCosts:
    def test_single_cost_single_rule(self):
        cc_id, act_id = uuid4(), uuid4()
        cost_records = [CostRecord(uuid4(), cc_id, "diretto", Decimal("1000"))]
        rules = [_rule("costo_ad_attivita", scc=cc_id, ta=act_id, pct=Decimal("1"))]
        result = ABCEngine().calculate(uuid4(), cost_records, [], rules, [], [act_id], [uuid4()], [])
        assert result.activity_costs[act_id].direct_cost == Decimal("1000.00")

    def test_multiple_costs_split_by_percentage(self):
        cc_id, act_a, act_b = uuid4(), uuid4(), uuid4()
        cost_records = [
            CostRecord(uuid4(), cc_id, "diretto", Decimal("1000")),
            CostRecord(uuid4(), cc_id, "diretto", Decimal("500")),
        ]
        rules = [
            _rule("costo_ad_attivita", scc=cc_id, ta=act_a, pct=Decimal("0.6")),
            _rule("costo_ad_attivita", scc=cc_id, ta=act_b, pct=Decimal("0.4")),
        ]
        result = ABCEngine().calculate(uuid4(), cost_records, [], rules, [], [act_a, act_b], [uuid4()], [])
        assert result.activity_costs[act_a].direct_cost == Decimal("900.00")
        assert result.activity_costs[act_b].direct_cost == Decimal("600.00")

    def test_no_allocation_rules_warning(self):
        cost_records = [CostRecord(uuid4(), uuid4(), "diretto", Decimal("1000"))]
        result = ABCEngine().calculate(uuid4(), cost_records, [], [], [], [uuid4()], [uuid4()], [])
        assert any("Nessuna regola" in w for w in result.warnings)

    def test_labor_cost_accumulation(self):
        act_id = uuid4()
        labor = [
            LaborRecord(uuid4(), act_id, Decimal("160"), Decimal("25"), Decimal("1")),
            LaborRecord(uuid4(), act_id, Decimal("80"), Decimal("30"), Decimal("1")),
        ]
        result = ABCEngine().calculate(uuid4(), [], labor, [], [], [act_id], [uuid4()], [])
        assert result.activity_costs[act_id].labor_cost == Decimal("6400.00")


class TestABCEngineSupportAllocation:
    def test_simple_support_allocation(self):
        support, primary, cc_id = uuid4(), uuid4(), uuid4()
        cost_records = [CostRecord(uuid4(), cc_id, "diretto", Decimal("1000"))]
        labor = [LaborRecord(uuid4(), support, Decimal("10"), Decimal("20"), Decimal("1"))]
        rules = [
            _rule("costo_ad_attivita", scc=cc_id, ta=support, pct=Decimal("1")),
            _rule("attivita_ad_attivita", sa=support, ta=primary, pct=Decimal("1"), priority=1),
        ]
        result = ABCEngine(max_iterations=10, convergence_threshold=0.001).calculate(
            uuid4(), cost_records, labor, rules, [], [support, primary], [uuid4()], [support],
        )
        assert result.activity_costs[primary].inbound_allocated == Decimal("1200.00")

    def test_no_support_activities(self):
        result = ABCEngine().calculate(uuid4(), [], [], [], [], [uuid4()], [uuid4()], [])
        assert result.iterations_used == 0


class TestABCEngineServiceAllocation:
    def test_activity_to_service(self):
        act, svc_a, svc_b = uuid4(), uuid4(), uuid4()
        labor = [LaborRecord(uuid4(), act, Decimal("40"), Decimal("25"), Decimal("1"))]
        rules = [
            _rule("attivita_a_servizio", sa=act, ts=svc_a, pct=Decimal("0.7"), priority=1),
            _rule("attivita_a_servizio", sa=act, ts=svc_b, pct=Decimal("0.3"), priority=1),
        ]
        result = ABCEngine().calculate(
            uuid4(), [], labor, rules, [], [act], [svc_a, svc_b], [],
        )
        assert float(result.service_results[svc_a].total_allocated_cost) == 700.0
        assert float(result.service_results[svc_b].total_allocated_cost) == 300.0


class TestABCEngineRevenues:
    def test_margin_calculation(self):
        svc, act = uuid4(), uuid4()
        labor = [LaborRecord(uuid4(), act, Decimal("40"), Decimal("25"), Decimal("1"))]
        rules = [_rule("attivita_a_servizio", sa=act, ts=svc, pct=Decimal("1"), priority=1)]
        revenues = [ServiceRevenueRecord(svc, Decimal("2000"), Decimal("100"))]
        result = ABCEngine().calculate(
            uuid4(), [], labor, rules, revenues, [act], [svc], [],
        )
        svc_r = result.service_results[svc]
        assert svc_r.revenue == Decimal("2000")
        assert svc_r.total_allocated_cost == Decimal("1000")
        assert svc_r.cost_per_unit == Decimal("20.0000")

    def test_zero_revenue_no_crash(self):
        svc, act = uuid4(), uuid4()
        revenues = [ServiceRevenueRecord(svc, Decimal("0"), Decimal("50"))]
        rules = [_rule("attivita_a_servizio", sa=act, ts=svc, pct=Decimal("1"), priority=1)]
        result = ABCEngine().calculate(
            uuid4(), [], [], rules, revenues, [act], [svc], [],
        )
        assert result.service_results[svc].margin_pct is None
        assert result.service_results[svc].cost_per_unit == Decimal("0.0000")


class TestABCEngineEdgeCases:
    def test_empty_inputs(self):
        result = ABCEngine().calculate(uuid4(), [], [], [], [], [], [], [])
        assert len(result.activity_costs) == 0
        assert len(result.service_results) == 0

    def test_partial_allocation_normalized(self):
        cc, act_a, act_b = uuid4(), uuid4(), uuid4()
        cost_records = [CostRecord(uuid4(), cc, "diretto", Decimal("1000"))]
        rules = [
            _rule("costo_ad_attivita", scc=cc, ta=act_a, pct=Decimal("0.5")),
            _rule("costo_ad_attivita", scc=cc, ta=act_b, pct=Decimal("0.3")),
        ]
        result = ABCEngine().calculate(uuid4(), cost_records, [], rules, [], [act_a, act_b], [uuid4()], [])
        assert result.activity_costs[act_a].direct_cost == Decimal("625.00")
        assert result.activity_costs[act_b].direct_cost == Decimal("375.00")

    def test_unallocated_cost_warning(self):
        cc, act, svc_a, svc_b = uuid4(), uuid4(), uuid4(), uuid4()
        cost_records = [CostRecord(uuid4(), cc, "diretto", Decimal("1000"))]
        rules = [_rule("costo_ad_attivita", scc=cc, ta=act, pct=Decimal("1"))]
        revenues = [
            ServiceRevenueRecord(svc_a, Decimal("5000"), Decimal("50")),
            ServiceRevenueRecord(svc_b, Decimal("5000"), Decimal("50")),
        ]
        result = ABCEngine().calculate(
            uuid4(), cost_records, [], rules, revenues, [act], [svc_a, svc_b], [],
        )
        assert any("non allocato" in w.lower() for w in result.warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])