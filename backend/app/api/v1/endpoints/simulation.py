"""
API Simulation — Simulatore What-If per scenari decisionali.
Risponde a: "Cosa succede se...?"
- riduciamo il personale del X%?
- aumentiamo i prezzi del Y%?
- outsourciang di un'attività?
- modifica del mix di servizi?
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import ABCResult, Service, AccountingPeriod

router = APIRouter()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS INPUT
# ─────────────────────────────────────────────────────────────────────────────

class LaborReductionScenario(BaseModel):
    """Scenario: riduzione costo personale."""
    reduction_pct: Decimal = Field(
        ..., ge=0, le=100,
        description="Percentuale di riduzione del costo personale (0-100)"
    )
    department: Optional[str] = Field(
        None,
        description="Reparto specifico (lasciare vuoto per tutti)"
    )


class PriceChangeScenario(BaseModel):
    """Scenario: variazione prezzi / ricavi."""
    service_id: UUID
    revenue_change_pct: Decimal = Field(
        ...,
        description="Variazione % ricavi (+10 = +10%, -5 = -5%)"
    )


class OutsourcingScenario(BaseModel):
    """Scenario: outsourcing di un'attività (rimozione costi interni)."""
    activity_id: UUID
    outsourcing_cost: Decimal = Field(
        ..., ge=0,
        description="Costo fisso dell'outsourcing (sostituisce il costo interno)"
    )


class CombinedScenario(BaseModel):
    """Scenario combinato (più leve contemporaneamente)."""
    name: str = Field(default="Scenario personalizzato")
    labor_reduction_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    overhead_reduction_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    revenue_changes: list[PriceChangeScenario] = Field(default_factory=list)
    outsourcing: list[OutsourcingScenario] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

class ServiceComparison(BaseModel):
    service_id: UUID
    service_name: str
    baseline_cost: Decimal
    scenario_cost: Decimal
    cost_delta: Decimal
    cost_delta_pct: Optional[Decimal]
    baseline_margin: Decimal
    scenario_margin: Decimal
    margin_delta: Decimal
    margin_delta_pct: Optional[Decimal]
    baseline_margin_pct: Optional[Decimal]
    scenario_margin_pct: Optional[Decimal]


class SimulationResult(BaseModel):
    scenario_name: str
    period_id: UUID
    period_name: str
    baseline_total_cost: Decimal
    scenario_total_cost: Decimal
    total_cost_saving: Decimal
    baseline_total_margin: Decimal
    scenario_total_margin: Decimal
    margin_improvement: Decimal
    services: list[ServiceComparison]
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/combined/{period_id}",
    response_model=SimulationResult,
    summary="Simula scenario combinato What-If",
    description=(
        "Esegue una simulazione multi-leva: riduzione personale, variazione ricavi, "
        "outsourcing. Usa i risultati ABC salvati come baseline."
    ),
)
async def simulate_combined(
    period_id: UUID,
    scenario: CombinedScenario,
    db: AsyncSession = Depends(get_db),
):
    """Simula un scenario combinato rispetto al baseline ABC."""
    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    # Carica baseline
    results_q = await db.execute(
        select(ABCResult, Service)
        .join(Service, ABCResult.service_id == Service.id)
        .where(ABCResult.period_id == period_id)
        .where(ABCResult.activity_id == None)
    )
    baseline_rows = results_q.all()

    if not baseline_rows:
        raise HTTPException(
            status_code=404,
            detail="Nessun risultato ABC baseline. Eseguire prima il calcolo ABC.",
        )

    # Indice modifiche per servizio
    revenue_changes = {s.service_id: s.revenue_change_pct for s in scenario.revenue_changes}

    comparisons = []
    baseline_total_cost = Decimal("0")
    scenario_total_cost = Decimal("0")
    baseline_total_margin = Decimal("0")
    scenario_total_margin = Decimal("0")

    for result, svc in baseline_rows:
        # ── Costo scenario ────────────────────────────────────────────────
        new_labor = result.labor_cost
        new_overhead = result.overhead_cost
        new_direct = result.direct_cost
        new_revenue = result.revenue

        # Applica riduzione personale
        if scenario.labor_reduction_pct:
            factor = 1 - scenario.labor_reduction_pct / 100
            new_labor = result.labor_cost * factor

        # Applica riduzione overhead
        if scenario.overhead_reduction_pct:
            factor = 1 - scenario.overhead_reduction_pct / 100
            new_overhead = result.overhead_cost * factor

        # Applica variazione ricavi
        if svc.id in revenue_changes:
            factor = 1 + revenue_changes[svc.id] / 100
            new_revenue = result.revenue * factor

        scenario_cost = new_labor + new_overhead + new_direct
        baseline_cost = result.total_cost
        baseline_margin = result.gross_margin
        scenario_margin = new_revenue - scenario_cost

        # Delta
        cost_delta = scenario_cost - baseline_cost
        cost_delta_pct = (
            cost_delta / baseline_cost * 100 if baseline_cost != 0 else None
        )
        margin_delta = scenario_margin - baseline_margin
        margin_delta_pct = (
            margin_delta / abs(baseline_margin) * 100
            if baseline_margin != 0
            else None
        )

        comparisons.append(ServiceComparison(
            service_id=svc.id,
            service_name=svc.name,
            baseline_cost=baseline_cost,
            scenario_cost=scenario_cost,
            cost_delta=cost_delta,
            cost_delta_pct=cost_delta_pct,
            baseline_margin=baseline_margin,
            scenario_margin=scenario_margin,
            margin_delta=margin_delta,
            margin_delta_pct=margin_delta_pct,
            baseline_margin_pct=(
                result.margin_pct if hasattr(result, "margin_pct") else None
            ),
            scenario_margin_pct=(
                scenario_margin / new_revenue * 100 if new_revenue != 0 else None
            ),
        ))

        baseline_total_cost += baseline_cost
        scenario_total_cost += scenario_cost
        baseline_total_margin += baseline_margin
        scenario_total_margin += scenario_margin

    total_cost_saving = baseline_total_cost - scenario_total_cost
    margin_improvement = scenario_total_margin - baseline_total_margin

    # Genera summary testuale
    summary_parts = []
    if scenario.labor_reduction_pct:
        summary_parts.append(
            f"Riduzione personale {scenario.labor_reduction_pct}%"
        )
    if scenario.overhead_reduction_pct:
        summary_parts.append(
            f"Riduzione overhead {scenario.overhead_reduction_pct}%"
        )
    if revenue_changes:
        summary_parts.append(f"Variazione ricavi su {len(revenue_changes)} servizi")

    saving_str = f"€{total_cost_saving:,.0f}" if total_cost_saving >= 0 else f"-€{abs(total_cost_saving):,.0f}"
    margin_str = f"€{margin_improvement:,.0f}" if margin_improvement >= 0 else f"-€{abs(margin_improvement):,.0f}"
    summary = (
        f"Scenario '{scenario.name}': "
        f"{', '.join(summary_parts) or 'nessuna modifica'}. "
        f"Risparmio costi: {saving_str}. "
        f"Variazione margine: {margin_str}."
    )

    comparisons.sort(key=lambda x: x.margin_delta)

    return SimulationResult(
        scenario_name=scenario.name,
        period_id=period_id,
        period_name=period.name,
        baseline_total_cost=baseline_total_cost,
        scenario_total_cost=scenario_total_cost,
        total_cost_saving=total_cost_saving,
        baseline_total_margin=baseline_total_margin,
        scenario_total_margin=scenario_total_margin,
        margin_improvement=margin_improvement,
        services=comparisons,
        summary=summary,
    )


@router.get(
    "/scenarios/templates",
    summary="Template scenari predefiniti",
)
async def get_scenario_templates():
    """Restituisce template di scenari comuni per l'hotel."""
    return [
        {
            "name": "Riduzione personale 10%",
            "description": "Impatto di una riduzione del 10% del costo del personale su tutti i reparti",
            "scenario": CombinedScenario(
                name="Riduzione personale 10%",
                labor_reduction_pct=Decimal("10"),
            ).model_dump(),
        },
        {
            "name": "Ottimizzazione overhead 15%",
            "description": "Effetto di una riduzione dei costi fissi (energia, manutenzione) del 15%",
            "scenario": CombinedScenario(
                name="Ottimizzazione overhead 15%",
                overhead_reduction_pct=Decimal("15"),
            ).model_dump(),
        },
        {
            "name": "Aumento RevPAR 8%",
            "description": "Impatto dell'aumento del prezzo medio camera dell'8%",
            "scenario": CombinedScenario(
                name="Aumento RevPAR 8%",
                revenue_changes=[],  # da personalizzare con service_id reale
            ).model_dump(),
        },
    ]
