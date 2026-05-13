"""
Test suite per il motore Activity-Based Costing (ABC).
Testa le 4 fasi del calcolo ABC con dati mock realistici.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from uuid import uuid4

from app.core.abc_engine import (
    ABCEngine,
    CostRecord,
    LaborRecord,
    AllocationRuleRecord,
    ServiceRevenueRecord,
    ABCEngineResult,
)


class TestABCEngineInitialization:
    """Testa l'inizializzazione del motore ABC."""

    def test_default_parameters(self):
        engine = ABCEngine()
        assert engine.max_iterations == 10
        assert engine.convergence_threshold == Decimal("0.001")

    def test_custom_parameters(self):
        engine = ABCEngine(max_iterations=20, convergence_threshold=0.01)
        assert engine.max_iterations == 20
        assert engine.convergence_threshold == Decimal("0.01")


class TestABCEngineDirectCosts:
    """Testa la Fase 1: allocazione costi diretti."""

    def test_single_cost_single_rule(self):
        cc_id = uuid4()
        act_id = uuid4()
        engine = ABCEngine()
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("1000")),
        ]
        allocation_rules = [
            AllocationRuleRecord(
                rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_id,
                driver_values={}, allocation_pct=Decimal("1"), priority=10,
            )
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=[], allocation_rules=allocation_rules,
            service_revenues=[], activity_ids=[act_id],
            service_ids=[uuid4()], support_activity_ids=[],
        )
        assert result.activity_costs[act_id].direct_cost == Decimal("1000.00")

    def test_multiple_costs_split_by_percentage(self):
        cc_id = uuid4()
        act_a, act_b = uuid4(), uuid4()
        engine = ABCEngine()
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("1000")),
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("500")),
        ]
        allocation_rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_a,
                driver_values={}, allocation_pct=Decimal("0.6"), priority=10),
            AllocationRuleRecord(rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_b,
                driver_values={}, allocation_pct=Decimal("0.4"), priority=10),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=[], allocation_rules=allocation_rules,
            service_revenues=[], activity_ids=[act_a, act_b],
            service_ids=[uuid4()], support_activity_ids=[],
        )
        assert result.activity_costs[act_a].direct_cost == Decimal("900.00")
        assert result.activity_costs[act_b].direct_cost == Decimal("600.00")

    def test_no_allocation_rules_warning(self):
        engine = ABCEngine()
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=uuid4(),
                       cost_type="diretto", amount=Decimal("1000")),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=[], allocation_rules=[],
            service_revenues=[], activity_ids=[uuid4()],
            service_ids=[uuid4()], support_activity_ids=[],
        )
        assert any("Nessuna regola" in w for w in result.warnings)

    def test_labor_cost_accumulation(self):
        act_id = uuid4()
        engine = ABCEngine()
        labor_records = [
            LaborRecord(employee_id=uuid4(), activity_id=act_id,
                        hours=Decimal("160"), hourly_cost=Decimal("25"),
                        allocation_pct=Decimal("1")),
            LaborRecord(employee_id=uuid4(), activity_id=act_id,
                        hours=Decimal("80"), hourly_cost=Decimal("30"),
                        allocation_pct=Decimal("1")),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=[],
            labor_records=labor_records, allocation_rules=[],
            service_revenues=[], activity_ids=[act_id],
            service_ids=[uuid4()], support_activity_ids=[],
        )
        # 160*25 + 80*30 = 4000 + 2400 = 6400
        assert result.activity_costs[act_id].labor_cost == Decimal("6400.00")


class TestABCEngineSupportAllocation:
    """Testa la Fase 2: ribaltamento attività di supporto."""

    def test_simple_support_allocation(self):
        """Support activity cost viene ribaltato su primaria."""
        support_act = uuid4()
        primary_act = uuid4()
        cc_id = uuid4()
        engine = ABCEngine(max_iterations=10, convergence_threshold=0.001)

        # Costo diretto su CC → support activity (Fase 1)
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("1000")),
        ]
        labor_records = [
            LaborRecord(employee_id=uuid4(), activity_id=support_act,
                        hours=Decimal("10"), hourly_cost=Decimal("20"),
                        allocation_pct=Decimal("1")),
        ]
        # Regola CC → support (Fase 1a)
        cc_to_support = AllocationRuleRecord(
            rule_id=uuid4(), level="costo_ad_attivita",
            source_cost_center_id=cc_id, target_activity_id=support_act,
            driver_values={}, allocation_pct=Decimal("1"), priority=10,
        )
        # Regola support → primary (Fase 2)
        support_to_primary = AllocationRuleRecord(
            rule_id=uuid4(), level="attivita_ad_attivita",
            source_activity_id=support_act, target_activity_id=primary_act,
            driver_values={}, allocation_pct=Decimal("1"), priority=1,
        )

        result = engine.calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=labor_records,
            allocation_rules=[cc_to_support, support_to_primary],
            service_revenues=[],
            activity_ids=[support_act, primary_act],
            service_ids=[uuid4()],
            support_activity_ids=[support_act],
        )

        # Support cost: 1000 (diretto) + 200 (labor) = 1200 → ribaltato
        assert result.activity_costs[primary_act].inbound_allocated == Decimal("1200.00")

    def test_no_support_activities(self):
        engine = ABCEngine()
        result = engine.calculate(
            period_id=uuid4(), cost_records=[], labor_records=[],
            allocation_rules=[], service_revenues=[],
            activity_ids=[uuid4()], service_ids=[uuid4()],
            support_activity_ids=[],
        )
        assert result.iterations_used == 0


class TestABCEngineServiceAllocation:
    """Testa la Fase 3: allocazione attività ai servizi."""

    def test_activity_to_service(self):
        act_id = uuid4()
        svc_a, svc_b = uuid4(), uuid4()
        engine = ABCEngine()
        labor_records = [
            LaborRecord(employee_id=uuid4(), activity_id=act_id,
                        hours=Decimal("40"), hourly_cost=Decimal("25"),
                        allocation_pct=Decimal("1")),
        ]
        rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="attivita_a_servizio",
                source_activity_id=act_id, target_service_id=svc_a,
                driver_values={}, allocation_pct=Decimal("0.7"), priority=1),
            AllocationRuleRecord(rule_id=uuid4(), level="attivita_a_servizio",
                source_activity_id=act_id, target_service_id=svc_b,
                driver_values={}, allocation_pct=Decimal("0.3"), priority=1),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=[],
            labor_records=labor_records, allocation_rules=rules,
            service_revenues=[], activity_ids=[act_id],
            service_ids=[svc_a, svc_b], support_activity_ids=[],
        )
        assert float(result.service_results[svc_a].total_allocated_cost) == 700.0
        assert float(result.service_results[svc_b].total_allocated_cost) == 300.0


class TestABCEngineRevenues:
    """Testa la Fase 4: ricavi e margini."""

    def test_margin_calculation(self):
        svc_id = uuid4()
        act_id = uuid4()
        engine = ABCEngine()
        labor_records = [
            LaborRecord(employee_id=uuid4(), activity_id=act_id,
                        hours=Decimal("40"), hourly_cost=Decimal("25"),
                        allocation_pct=Decimal("1")),
        ]
        rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="attivita_a_servizio",
                source_activity_id=act_id, target_service_id=svc_id,
                driver_values={}, allocation_pct=Decimal("1"), priority=1),
        ]
        service_revenues = [
            ServiceRevenueRecord(service_id=svc_id, revenue=Decimal("2000"),
                                  output_volume=Decimal("100")),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=[],
            labor_records=labor_records, allocation_rules=rules,
            service_revenues=service_revenues, activity_ids=[act_id],
            service_ids=[svc_id], support_activity_ids=[],
        )
        svc = result.service_results[svc_id]
        assert svc.revenue == Decimal("2000")
        # activity cost 1000, distributed 100% to service
        assert svc.total_allocated_cost == Decimal("1000")
        # margin = 2000 - (0 + 1000 + 0 + 1000) = 0  (allocated already includes labor)
        assert svc.gross_margin == Decimal("0")
        assert svc.cost_per_unit == Decimal("20.0000")

    def test_zero_revenue_no_crash(self):
        svc_id = uuid4()
        act_id = uuid4()
        engine = ABCEngine()
        service_revenues = [
            ServiceRevenueRecord(service_id=svc_id, revenue=Decimal("0"),
                                  output_volume=Decimal("50")),
        ]
        rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="attivita_a_servizio",
                source_activity_id=act_id, target_service_id=svc_id,
                driver_values={}, allocation_pct=Decimal("1"), priority=1),
        ]
        result = engine.calculate(
            period_id=uuid4(), cost_records=[],
            labor_records=[], allocation_rules=rules,
            service_revenues=service_revenues, activity_ids=[act_id],
            service_ids=[svc_id], support_activity_ids=[],
        )
        assert result.service_results[svc_id].margin_pct is None


class TestABCEngineEdgeCases:
    """Testa casi limite."""

    def test_empty_inputs(self):
        result = ABCEngine().calculate(
            period_id=uuid4(), cost_records=[], labor_records=[],
            allocation_rules=[], service_revenues=[],
            activity_ids=[], service_ids=[], support_activity_ids=[],
        )
        assert len(result.activity_costs) == 0
        assert len(result.service_results) == 0

    def test_partial_allocation_normalized(self):
        """Regole con % che non sommano a 1 vengono normalizzate."""
        cc_id = uuid4()
        act_a, act_b = uuid4(), uuid4()
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("1000")),
        ]
        rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_a,
                driver_values={}, allocation_pct=Decimal("0.5"), priority=10),
            AllocationRuleRecord(rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_b,
                driver_values={}, allocation_pct=Decimal("0.3"), priority=10),
        ]
        result = ABCEngine().calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=[], allocation_rules=rules,
            service_revenues=[], activity_ids=[act_a, act_b],
            service_ids=[uuid4()], support_activity_ids=[],
        )
        # Normalizzato: 0.5/0.8=0.625 → 625, 0.3/0.8=0.375 → 375
        assert result.activity_costs[act_a].direct_cost == Decimal("625.00")
        assert result.activity_costs[act_b].direct_cost == Decimal("375.00")

    def test_unallocated_cost_warning(self):
        """Costo non allocato ai servizi → warning."""
        cc_id = uuid4()
        act_id = uuid4()
        svc_a, svc_b = uuid4(), uuid4()
        cost_records = [
            CostRecord(cost_item_id=uuid4(), cost_center_id=cc_id,
                       cost_type="diretto", amount=Decimal("1000")),
        ]
        rules = [
            AllocationRuleRecord(rule_id=uuid4(), level="costo_ad_attivita",
                source_cost_center_id=cc_id, target_activity_id=act_id,
                driver_values={}, allocation_pct=Decimal("1"), priority=10),
        ]
        result = ABCEngine().calculate(
            period_id=uuid4(), cost_records=cost_records,
            labor_records=[], allocation_rules=rules,
            service_revenues=[
                ServiceRevenueRecord(service_id=svc_a, revenue=Decimal("5000"), output_volume=Decimal("50")),
                ServiceRevenueRecord(service_id=svc_b, revenue=Decimal("5000"), output_volume=Decimal("50")),
            ],
            activity_ids=[act_id], service_ids=[svc_a, svc_b],
            support_activity_ids=[],
        )
        assert any("non allocato" in w.lower() for w in result.warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])