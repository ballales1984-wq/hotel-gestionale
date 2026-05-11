"""
Hotel ABC Platform — Motore ABC Core
Implementa l'algoritmo Activity-Based Costing a 3 livelli:
  1. Costi (centri di costo) → Attività
  2. Attività di supporto → Attività primarie (ribaltamento)
  3. Attività → Servizi

Supporta driver dinamici, ribaltamenti multi-livello
e iterazioni convergenti per allocazioni circolari.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import polars as pl

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES (input al motore)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CostRecord:
    """Una voce di costo proveniente dalla contabilità."""
    cost_item_id: UUID
    cost_center_id: Optional[UUID]
    cost_type: str
    amount: Decimal


@dataclass
class LaborRecord:
    """Ore e costi personale per attività."""
    employee_id: UUID
    activity_id: UUID
    hours: Decimal
    hourly_cost: Decimal
    allocation_pct: Decimal

    @property
    def total_cost(self) -> Decimal:
        return (self.hours * self.hourly_cost).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass
class AllocationRuleRecord:
    """Regola di allocazione ABC."""
    rule_id: UUID
    level: str
    source_cost_center_id: Optional[UUID]
    source_activity_id: Optional[UUID]
    target_activity_id: Optional[UUID]
    target_service_id: Optional[UUID]
    driver_values: Dict[UUID, Decimal]   # entity_id → valore driver
    allocation_pct: Optional[Decimal]    # % fissa (se nessun driver)
    priority: int


@dataclass
class DriverData:
    """Valori di un driver per il periodo."""
    driver_id: UUID
    driver_type: str
    values: Dict[UUID, Decimal]          # entity_id → valore


@dataclass
class ServiceRevenueRecord:
    """Ricavi per servizio nel periodo."""
    service_id: UUID
    revenue: Decimal
    output_volume: Optional[Decimal]


# ─────────────────────────────────────────────────────────────────────────────
# RISULTATI
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ActivityCost:
    """Costo totale di un'attività dopo allocazione."""
    activity_id: UUID
    direct_cost: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    overhead_cost: Decimal = Decimal("0")
    inbound_allocated: Decimal = Decimal("0")  # ricevuti da altre attività

    @property
    def total_cost(self) -> Decimal:
        return self.direct_cost + self.labor_cost + self.overhead_cost + self.inbound_allocated


@dataclass
class ServiceResult:
    """Risultato finale ABC per un servizio."""
    service_id: UUID
    direct_cost: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    overhead_cost: Decimal = Decimal("0")
    total_allocated_cost: Decimal = Decimal("0")
    revenue: Decimal = Decimal("0")
    output_volume: Optional[Decimal] = None
    activity_breakdown: Dict[UUID, Decimal] = field(default_factory=dict)

    @property
    def total_cost(self) -> Decimal:
        return self.direct_cost + self.labor_cost + self.overhead_cost + self.total_allocated_cost

    @property
    def gross_margin(self) -> Decimal:
        return self.revenue - self.total_cost

    @property
    def margin_pct(self) -> Optional[Decimal]:
        if self.revenue == 0:
            return None
        return (self.gross_margin / self.revenue * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def cost_per_unit(self) -> Optional[Decimal]:
        if not self.output_volume or self.output_volume == 0:
            return None
        return (self.total_cost / self.output_volume).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )


@dataclass
class ABCEngineResult:
    """Risultato completo del calcolo ABC per un periodo."""
    period_id: UUID
    activity_costs: Dict[UUID, ActivityCost]
    service_results: Dict[UUID, ServiceResult]
    unallocated_amount: Decimal = Decimal("0")
    iterations_used: int = 1
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_cost(self) -> Decimal:
        return sum(v.total_cost for v in self.service_results.values())

    @property
    def total_revenue(self) -> Decimal:
        return sum(v.revenue for v in self.service_results.values())

    @property
    def total_margin(self) -> Decimal:
        return self.total_revenue - self.total_cost


# ─────────────────────────────────────────────────────────────────────────────
# MOTORE ABC
# ─────────────────────────────────────────────────────────────────────────────

class ABCEngine:
    """
    Motore principale Activity-Based Costing.

    Algoritmo:
    1. Accumula costi diretti sulle attività (da centri di costo + allocazioni personale)
    2. Ribalta i costi delle attività di supporto sulle attività primarie (iterativo)
    3. Alloca i costi delle attività primarie ai servizi tramite driver
    4. Calcola margini per servizio
    """

    def __init__(
        self,
        max_iterations: int = 10,
        convergence_threshold: float = 0.001,
    ):
        self.max_iterations = max_iterations
        self.convergence_threshold = Decimal(str(convergence_threshold))

    def calculate(
        self,
        period_id: UUID,
        cost_records: List[CostRecord],
        labor_records: List[LaborRecord],
        allocation_rules: List[AllocationRuleRecord],
        service_revenues: List[ServiceRevenueRecord],
        activity_ids: List[UUID],
        service_ids: List[UUID],
        support_activity_ids: List[UUID],
    ) -> ABCEngineResult:
        """
        Esegue il calcolo ABC completo.
        Restituisce ABCEngineResult con tutti i dettagli.
        """
        result = ABCEngineResult(
            period_id=period_id,
            activity_costs={aid: ActivityCost(activity_id=aid) for aid in activity_ids},
            service_results={
                sid: ServiceResult(service_id=sid) for sid in service_ids
            },
        )

        # ── FASE 1: Popola costi sulle attività ───────────────────────────
        self._phase1_direct_costs(cost_records, allocation_rules, result)
        self._phase1_labor_costs(labor_records, result)

        logger.info(
            "Fase 1 completata — costi attività: %s",
            {str(k): str(v.total_cost) for k, v in result.activity_costs.items()},
        )

        # ── FASE 2: Ribaltamento attività di supporto ─────────────────────
        iterations = self._phase2_support_activities(
            support_activity_ids, allocation_rules, result
        )
        result.iterations_used = iterations

        logger.info("Fase 2 completata in %d iterazioni", iterations)

        # ── FASE 3: Allocazione attività → servizi ────────────────────────
        self._phase3_allocate_to_services(allocation_rules, result)

        logger.info("Fase 3 completata — servizi calcolati: %d", len(service_ids))

        # ── FASE 4: Aggiunge ricavi e calcola margini ─────────────────────
        self._phase4_revenues(service_revenues, result)

        # ── Calcola non-allocato ──────────────────────────────────────────
        total_activity_cost = sum(
            v.total_cost for v in result.activity_costs.values()
        )
        total_service_cost = sum(
            v.total_cost for v in result.service_results.values()
        )
        result.unallocated_amount = total_activity_cost - total_service_cost

        if result.unallocated_amount > Decimal("0.01"):
            result.warnings.append(
                f"Costo non allocato ai servizi: €{result.unallocated_amount:.2f}. "
                "Verificare le regole di allocazione."
            )

        return result

    # ──────────────────────────────────────────────────────────────────────
    # FASE 1a: Costi diretti (contabilità → attività)
    # ──────────────────────────────────────────────────────────────────────

    def _phase1_direct_costs(
        self,
        cost_records: List[CostRecord],
        rules: List[AllocationRuleRecord],
        result: ABCEngineResult,
    ) -> None:
        """Alloca i costi contabili (per centro di costo) alle attività."""
        # Raggruppa regole per source cost center
        rules_by_cc: Dict[UUID, List[AllocationRuleRecord]] = {}
        for rule in rules:
            if (
                rule.level == "costo_ad_attivita"
                and rule.source_cost_center_id
                and rule.target_activity_id
            ):
                cc_id = rule.source_cost_center_id
                rules_by_cc.setdefault(cc_id, []).append(rule)

        # Raggruppa costi per centro di costo
        costs_by_cc: Dict[Optional[UUID], List[CostRecord]] = {}
        for c in cost_records:
            costs_by_cc.setdefault(c.cost_center_id, []).append(c)

        for cc_id, cc_costs in costs_by_cc.items():
            cc_rules = rules_by_cc.get(cc_id, [])
            if not cc_rules:
                result.warnings.append(
                    f"Nessuna regola di allocazione per centro di costo {cc_id}. "
                    "Costi non distribuiti."
                )
                continue

            # Calcola percentuali normalizzate per le regole di questo CC
            allocated_pcts = self._compute_allocation_pcts(cc_rules)

            for cost in cc_costs:
                for rule, pct in allocated_pcts:
                    activity_id = rule.target_activity_id
                    if activity_id not in result.activity_costs:
                        result.activity_costs[activity_id] = ActivityCost(
                            activity_id=activity_id
                        )

                    allocated = (cost.amount * pct).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

                    activity = result.activity_costs[activity_id]
                    if cost.cost_type == "personale":
                        activity.labor_cost += allocated
                    elif cost.cost_type in ("struttura", "ammortamento", "utilities"):
                        activity.overhead_cost += allocated
                    else:
                        activity.direct_cost += allocated

    # ──────────────────────────────────────────────────────────────────────
    # FASE 1b: Costi personale (timesheet/stime → attività)
    # ──────────────────────────────────────────────────────────────────────

    def _phase1_labor_costs(
        self,
        labor_records: List[LaborRecord],
        result: ABCEngineResult,
    ) -> None:
        """Accumula i costi del personale direttamente sulle attività."""
        for lr in labor_records:
            activity_id = lr.activity_id
            if activity_id not in result.activity_costs:
                result.activity_costs[activity_id] = ActivityCost(
                    activity_id=activity_id
                )
            result.activity_costs[activity_id].labor_cost += lr.total_cost

    # ──────────────────────────────────────────────────────────────────────
    # FASE 2: Ribaltamento attività di supporto → attività primarie
    # ──────────────────────────────────────────────────────────────────────

    def _phase2_support_activities(
        self,
        support_ids: List[UUID],
        rules: List[AllocationRuleRecord],
        result: ABCEngineResult,
    ) -> int:
        """
        Itera il ribaltamento delle attività di supporto fino a convergenza.
        Gestisce allocazioni circolari con algoritmo iterativo.
        """
        if not support_ids:
            return 0

        activity_rules = [
            r for r in rules
            if r.level == "attivita_ad_attivita"
            and r.source_activity_id in support_ids
        ]

        if not activity_rules:
            return 0

        for iteration in range(self.max_iterations):
            prev_totals = {
                aid: ac.total_cost
                for aid, ac in result.activity_costs.items()
            }

            for support_id in support_ids:
                support_activity = result.activity_costs.get(support_id)
                if not support_activity or support_activity.total_cost == 0:
                    continue

                relevant_rules = [
                    r for r in activity_rules
                    if r.source_activity_id == support_id
                ]
                if not relevant_rules:
                    continue

                pct_map = self._compute_allocation_pcts(relevant_rules)
                cost_to_distribute = support_activity.total_cost

                for rule, pct in pct_map:
                    target_id = rule.target_activity_id
                    if not target_id:
                        continue
                    if target_id not in result.activity_costs:
                        result.activity_costs[target_id] = ActivityCost(
                            activity_id=target_id
                        )
                    allocated = (cost_to_distribute * pct).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    result.activity_costs[target_id].inbound_allocated += allocated

                # Azzera l'attività di supporto dopo il ribaltamento
                support_activity.inbound_allocated -= cost_to_distribute

            # Verifica convergenza
            max_delta = max(
                abs(result.activity_costs[aid].total_cost - prev_totals.get(aid, Decimal("0")))
                for aid in result.activity_costs
            )
            if max_delta < self.convergence_threshold:
                logger.debug("Convergenza raggiunta all'iterazione %d", iteration + 1)
                return iteration + 1

        result.warnings.append(
            f"Ribaltamento attività di supporto non converge in {self.max_iterations} iterazioni. "
            "Verificare regole circolari."
        )
        return self.max_iterations

    # ──────────────────────────────────────────────────────────────────────
    # FASE 3: Allocazione attività → servizi
    # ──────────────────────────────────────────────────────────────────────

    def _phase3_allocate_to_services(
        self,
        rules: List[AllocationRuleRecord],
        result: ABCEngineResult,
    ) -> None:
        """Distribuisce i costi delle attività ai servizi finali."""
        service_rules = [
            r for r in rules
            if r.level == "attivita_a_servizio"
            and r.source_activity_id
            and r.target_service_id
        ]

        # Raggruppa per attività sorgente
        rules_by_activity: Dict[UUID, List[AllocationRuleRecord]] = {}
        for r in service_rules:
            rules_by_activity.setdefault(r.source_activity_id, []).append(r)

        for activity_id, activity_rules in rules_by_activity.items():
            activity = result.activity_costs.get(activity_id)
            if not activity or activity.total_cost == 0:
                continue

            pct_map = self._compute_allocation_pcts(activity_rules)
            total_cost = activity.total_cost

            for rule, pct in pct_map:
                service_id = rule.target_service_id
                if service_id not in result.service_results:
                    result.service_results[service_id] = ServiceResult(
                        service_id=service_id
                    )

                allocated = (total_cost * pct).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                svc = result.service_results[service_id]
                svc.total_allocated_cost += allocated
                svc.activity_breakdown[activity_id] = (
                    svc.activity_breakdown.get(activity_id, Decimal("0")) + allocated
                )

                # Distribuisce per categoria di costo
                if total_cost > 0:
                    labor_share = (activity.labor_cost / total_cost * allocated).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    overhead_share = (activity.overhead_cost / total_cost * allocated).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    direct_share = allocated - labor_share - overhead_share
                else:
                    # Se il costo totale dell'attività è zero, distribuisce equamente
                    labor_share = allocated
                    overhead_share = Decimal("0")
                    direct_share = Decimal("0")
                    svc.labor_cost += labor_share
                    svc.overhead_cost += overhead_share
                    svc.direct_cost += direct_share

    # ──────────────────────────────────────────────────────────────────────
    # FASE 4: Ricavi e margini
    # ──────────────────────────────────────────────────────────────────────

    def _phase4_revenues(
        self,
        revenues: List[ServiceRevenueRecord],
        result: ABCEngineResult,
    ) -> None:
        for rev in revenues:
            svc = result.service_results.get(rev.service_id)
            if svc:
                svc.revenue = rev.revenue
                svc.output_volume = rev.output_volume

    # ──────────────────────────────────────────────────────────────────────
    # UTILITÀ
    # ──────────────────────────────────────────────────────────────────────

    def _compute_allocation_pcts(
        self,
        rules: List[AllocationRuleRecord],
    ) -> List[Tuple[AllocationRuleRecord, Decimal]]:
        """
        Calcola le percentuali di allocazione da una lista di regole.
        Supporta:
        - % fissa (allocation_pct nella regola)
        - % calcolata da driver (sum driver_values → pct proporzionale)
        Normalizza a 100% se necessario.
        """
        result: List[Tuple[AllocationRuleRecord, Decimal]] = []

        # Distinguiamo regole con % fissa da quelle con driver
        fixed_rules = [r for r in rules if r.allocation_pct is not None]
        driver_rules = [r for r in rules if r.allocation_pct is None and r.driver_values]

        # Regole fisse: usa le percentuali così come sono
        for rule in fixed_rules:
            result.append((rule, rule.allocation_pct))

        # Regole con driver: calcola proporzioni dai valori del driver
        if driver_rules:
            # Somma i valori del driver per le entità target
            total_driver_value = Decimal("0")
            driver_vals: Dict[UUID, Decimal] = {}

            for rule in driver_rules:
                target_id = rule.target_activity_id or rule.target_service_id
                if target_id and target_id in rule.driver_values:
                    val = rule.driver_values[target_id]
                    driver_vals[target_id] = val
                    total_driver_value += val

            if total_driver_value > 0:
                remaining_pct = Decimal("1") - sum(pct for _, pct in result)
                for rule in driver_rules:
                    target_id = rule.target_activity_id or rule.target_service_id
                    if target_id and target_id in driver_vals:
                        pct = (
                            driver_vals[target_id] / total_driver_value * remaining_pct
                        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                        result.append((rule, pct))

        # Normalizza se somma ≠ 1 (sicurezza anti-arrotondamento)
        total_pct = sum(pct for _, pct in result)
        if total_pct > 0 and abs(total_pct - Decimal("1")) > Decimal("0.001"):
            result = [
                (rule, (pct / total_pct).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
                for rule, pct in result
            ]

        return result
