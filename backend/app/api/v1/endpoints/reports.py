"""
API Reports — Calcoli ABC e dashboard KPI.
Endpoint principale per il calcolo e la lettura dei risultati ABC.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import (
    AccountingPeriod, Activity, Service, CostItem, LaborAllocation,
    AllocationRule, DriverValue, ServiceRevenue, ABCResult, Employee,
)
from app.core.abc_engine import (
    ABCEngine, CostRecord, LaborRecord, AllocationRuleRecord,
    ServiceRevenueRecord, DriverData,
)
from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ServiceResultSchema(BaseModel):
    service_id: UUID
    service_name: str
    service_type: str
    direct_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    total_cost: Decimal
    revenue: Decimal
    gross_margin: Decimal
    margin_pct: Optional[Decimal]
    cost_per_unit: Optional[Decimal]
    output_volume: Optional[Decimal]
    output_unit: Optional[str]

    class Config:
        from_attributes = True


class ABCReportSchema(BaseModel):
    period_id: UUID
    period_name: str
    total_cost: Decimal
    total_revenue: Decimal
    total_margin: Decimal
    unallocated_amount: Decimal
    iterations_used: int
    services: list[ServiceResultSchema]
    warnings: list[str]
    errors: list[str]


class ActivityCostSchema(BaseModel):
    activity_id: UUID
    activity_name: str
    activity_code: str
    department: str
    labor_cost: Decimal
    direct_cost: Decimal
    overhead_cost: Decimal
    inbound_allocated: Decimal
    total_cost: Decimal


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/abc/calculate/{period_id}",
    response_model=ABCReportSchema,
    summary="Calcola ABC per un periodo",
    description=(
        "Esegue il calcolo Activity-Based Costing completo per il periodo specificato. "
        "Usa tutti i costi, le allocazioni personale e le regole di allocazione attive."
    ),
)
async def calculate_abc(
    period_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    save_results: bool = Query(True, description="Salva i risultati nel DB"),
):
    """
    Endpoint principale: esegue il calcolo ABC e restituisce i risultati.
    """
    # ── Verifica periodo ────────────────────────────────────────────────────
    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    # ── Carica attività ─────────────────────────────────────────────────────
    activities_q = await db.execute(
        select(Activity).where(Activity.is_active == True)
    )
    activities = activities_q.scalars().all()
    activity_map = {a.id: a for a in activities}

    support_ids = [a.id for a in activities if a.is_support_activity]

    # ── Carica servizi ───────────────────────────────────────────────────────
    services_q = await db.execute(
        select(Service).where(Service.is_active == True)
    )
    services = services_q.scalars().all()
    service_map = {s.id: s for s in services}

    # ── Carica voci di costo ─────────────────────────────────────────────────
    costs_q = await db.execute(
        select(CostItem).where(CostItem.period_id == period_id)
    )
    cost_items = costs_q.scalars().all()
    cost_records = [
        CostRecord(
            cost_item_id=c.id,
            cost_center_id=c.cost_center_id,
            cost_type=c.cost_type.value,
            amount=c.amount,
        )
        for c in cost_items
    ]

    # ── Carica allocazioni personale ─────────────────────────────────────────
    labor_q = await db.execute(
        select(LaborAllocation, Employee)
        .join(Employee, LaborAllocation.employee_id == Employee.id)
        .where(LaborAllocation.period_id == period_id)
    )
    labor_rows = labor_q.all()
    labor_records = [
        LaborRecord(
            employee_id=la.employee_id,
            activity_id=la.activity_id,
            hours=la.hours,
            hourly_cost=la.hourly_cost,
            allocation_pct=la.allocation_pct,
        )
        for la, _ in labor_rows
    ]

    # ── Carica regole di allocazione ─────────────────────────────────────────
    rules_q = await db.execute(
        select(AllocationRule).where(AllocationRule.is_active == True)
    )
    raw_rules = rules_q.scalars().all()

    # Carica valori driver per il periodo
    driver_values_q = await db.execute(
        select(DriverValue).where(DriverValue.period_id == period_id)
    )
    driver_value_rows = driver_values_q.scalars().all()

    # Raggruppa driver values per driver_id
    driver_map: dict[UUID, dict[UUID, Decimal]] = {}
    for dv in driver_value_rows:
        driver_map.setdefault(dv.driver_id, {})[dv.entity_id] = dv.value

    allocation_rules = [
        AllocationRuleRecord(
            rule_id=r.id,
            level=r.level.value,
            source_cost_center_id=r.source_cost_center_id,
            source_activity_id=r.source_activity_id,
            target_activity_id=r.target_activity_id,
            target_service_id=r.target_service_id,
            driver_values=driver_map.get(r.driver_id, {}) if r.driver_id else {},
            allocation_pct=r.allocation_pct,
            priority=r.priority,
        )
        for r in raw_rules
    ]

    # ── Carica ricavi per servizio ───────────────────────────────────────────
    revenue_q = await db.execute(
        select(ServiceRevenue).where(ServiceRevenue.period_id == period_id)
    )
    revenues = revenue_q.scalars().all()
    service_revenues = [
        ServiceRevenueRecord(
            service_id=r.service_id,
            revenue=r.revenue,
            output_volume=r.output_volume,
        )
        for r in revenues
    ]

    # ── Esegui motore ABC ────────────────────────────────────────────────────
    engine = ABCEngine(
        max_iterations=settings.abc_max_iterations,
        convergence_threshold=settings.abc_convergence_threshold,
    )

    try:
        abc_result = engine.calculate(
            period_id=period_id,
            cost_records=cost_records,
            labor_records=labor_records,
            allocation_rules=allocation_rules,
            service_revenues=service_revenues,
            activity_ids=list(activity_map.keys()),
            service_ids=list(service_map.keys()),
            support_activity_ids=support_ids,
        )
    except Exception as e:
        logger.exception("Errore nel calcolo ABC per periodo %s", period_id)
        raise HTTPException(status_code=500, detail=f"Errore calcolo ABC: {str(e)}")

    # ── Salva risultati in background ────────────────────────────────────────
    if save_results:
        background_tasks.add_task(
            _save_abc_results, db, period_id, period.hotel_id, abc_result, service_map
        )

    # ── Costruisci risposta ──────────────────────────────────────────────────
    service_results = []
    for svc_id, svc_result in abc_result.service_results.items():
        svc = service_map.get(svc_id)
        if not svc:
            continue
        service_results.append(
            ServiceResultSchema(
                service_id=svc_id,
                service_name=svc.name,
                service_type=svc.service_type.value,
                direct_cost=svc_result.direct_cost,
                labor_cost=svc_result.labor_cost,
                overhead_cost=svc_result.overhead_cost,
                total_cost=svc_result.total_cost,
                revenue=svc_result.revenue,
                gross_margin=svc_result.gross_margin,
                margin_pct=svc_result.margin_pct,
                cost_per_unit=svc_result.cost_per_unit,
                output_volume=svc_result.output_volume,
                output_unit=svc.output_unit,
            )
        )

    # Ordina per margine crescente (peggiori prima)
    service_results.sort(key=lambda x: x.gross_margin)

    return ABCReportSchema(
        period_id=period_id,
        period_name=period.name,
        total_cost=abc_result.total_cost,
        total_revenue=abc_result.total_revenue,
        total_margin=abc_result.total_margin,
        unallocated_amount=abc_result.unallocated_amount,
        iterations_used=abc_result.iterations_used,
        services=service_results,
        warnings=abc_result.warnings,
        errors=abc_result.errors,
    )


@router.get(
    "/abc/{period_id}",
    response_model=ABCReportSchema,
    summary="Leggi risultati ABC salvati",
)
async def get_abc_results(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Legge i risultati ABC già calcolati e salvati per il periodo."""
    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    results_q = await db.execute(
        select(ABCResult, Service)
        .join(Service, ABCResult.service_id == Service.id)
        .where(ABCResult.period_id == period_id)
        .where(ABCResult.activity_id == None)  # risultati aggregati per servizio
    )
    rows = results_q.all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Nessun risultato ABC trovato. Eseguire prima il calcolo.",
        )

    services = []
    total_cost = Decimal("0")
    total_revenue = Decimal("0")

    for result, svc in rows:
        margin_pct = None
        if result.revenue and result.revenue != 0:
            margin_pct = (result.gross_margin / result.revenue * 100).quantize(
                Decimal("0.01")
            )

        services.append(
            ServiceResultSchema(
                service_id=result.service_id,
                service_name=svc.name,
                service_type=svc.service_type.value,
                direct_cost=result.direct_cost,
                labor_cost=result.labor_cost,
                overhead_cost=result.overhead_cost,
                total_cost=result.total_cost,
                revenue=result.revenue,
                gross_margin=result.gross_margin,
                margin_pct=margin_pct,
                cost_per_unit=result.cost_per_unit,
                output_volume=result.output_volume,
                output_unit=svc.output_unit,
            )
        )
        total_cost += result.total_cost
        total_revenue += result.revenue

    services.sort(key=lambda x: x.gross_margin)

    return ABCReportSchema(
        period_id=period_id,
        period_name=period.name,
        total_cost=total_cost,
        total_revenue=total_revenue,
        total_margin=total_revenue - total_cost,
        unallocated_amount=Decimal("0"),
        iterations_used=0,
        services=services,
        warnings=[],
        errors=[],
    )


@router.get(
    "/kpi/summary",
    summary="KPI direzionali sintetici",
)
async def get_kpi_summary(
    period_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Restituisce i KPI principali per la dashboard direzionale:
    - margine totale per servizio
    - incidenza costo personale
    - top 3 attività per costo
    """
    query = select(ABCResult, Service).join(Service, ABCResult.service_id == Service.id)
    if period_id:
        query = query.where(ABCResult.period_id == period_id)

    results_q = await db.execute(query)
    rows = results_q.all()

    total_revenue = sum(r.revenue for r, _ in rows)
    total_cost = sum(r.total_cost for r, _ in rows)
    total_labor = sum(r.labor_cost for r, _ in rows)

    services_kpi = [
        {
            "service": svc.name,
            "service_type": svc.service_type.value,
            "revenue": float(r.revenue),
            "total_cost": float(r.total_cost),
            "gross_margin": float(r.gross_margin),
            "margin_pct": float(r.margin_pct) if r.margin_pct else None,
        }
        for r, svc in rows
    ]

    return {
        "total_revenue": float(total_revenue),
        "total_cost": float(total_cost),
        "total_margin": float(total_revenue - total_cost),
        "overall_margin_pct": (
            float((total_revenue - total_cost) / total_revenue * 100)
            if total_revenue > 0
            else None
        ),
        "labor_cost_incidence_pct": (
            float(total_labor / total_cost * 100) if total_cost > 0 else None
        ),
        "services": sorted(services_kpi, key=lambda x: x["gross_margin"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────────────────────

async def _save_abc_results(db, period_id, hotel_id, abc_result, service_map):
    """Salva i risultati ABC nel DB (eseguito in background)."""
    from sqlalchemy import delete
    try:
        # Cancella risultati precedenti per il periodo
        await db.execute(
            delete(ABCResult).where(ABCResult.period_id == period_id)
        )

        # Inserisce nuovi risultati
        for svc_id, svc_result in abc_result.service_results.items():
            if svc_id not in service_map:
                continue

            margin_pct = svc_result.margin_pct
            cost_per_unit = svc_result.cost_per_unit

            db_result = ABCResult(
                hotel_id=hotel_id,
                period_id=period_id,
                service_id=svc_id,
                activity_id=None,  # risultato aggregato
                direct_cost=svc_result.direct_cost,
                labor_cost=svc_result.labor_cost,
                overhead_cost=svc_result.overhead_cost,
                total_cost=svc_result.total_cost,
                revenue=svc_result.revenue,
                gross_margin=svc_result.gross_margin,
                margin_pct=margin_pct,
                cost_per_unit=cost_per_unit,
                output_volume=svc_result.output_volume,
            )
            db.add(db_result)

        await db.commit()
        logger.info("Risultati ABC salvati per periodo %s", period_id)
    except Exception as e:
        logger.exception("Errore nel salvataggio risultati ABC: %s", e)
        await db.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT EXCEL
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/export/{period_id}",
    summary="Esporta risultati ABC in Excel",
)
async def export_abc_to_excel(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Genera un file Excel con i risultati del calcolo ABC."""
    import io
    import pandas as pd
    from datetime import datetime
    from fastapi.responses import StreamingResponse

    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    # 1. Carica Risultati Aggregati (Servizi)
    query_svc = (
        select(ABCResult, Service)
        .join(Service, ABCResult.service_id == Service.id)
        .where(ABCResult.period_id == period_id)
        .where(ABCResult.activity_id == None)
    )
    res_svc = await db.execute(query_svc)
    svc_data = []
    for r, s in res_svc.all():
        svc_data.append({
            "Servizio": s.name,
            "Tipo": s.service_type.value,
            "Ricavo": float(r.revenue),
            "Costo Totale": float(r.total_cost),
            "Costo Personale": float(r.labor_cost),
            "Costo Diretto": float(r.direct_cost),
            "Overhead": float(r.overhead_cost),
            "Margine Lordo": float(r.gross_margin),
            "Margine %": float(r.margin_pct) if r.margin_pct else 0,
            "Volume": float(r.output_volume) if r.output_volume else 0,
            "Costo Unitario": float(r.cost_per_unit) if r.cost_per_unit else 0,
        })

    # 2. Carica Dettaglio Attività (solo record con activity_id non null)
    from app.models.models import Activity
    query_act = (
        select(ABCResult, Service, Activity)
        .join(Service, ABCResult.service_id == Service.id)
        .outerjoin(Activity, ABCResult.activity_id == Activity.id)  # outerjoin per gestire activity_id null
        .where(ABCResult.period_id == period_id)
        .where(ABCResult.activity_id != None)  # solo dettaglio attività, non aggregati
    )
    res_act = await db.execute(query_act)
    act_data = []
    for r, s, a in res_act.all():
        act_name = a.name if a else "N/A"
        dept = a.department.value if a else "N/A"
        act_data.append({
            "Servizio": s.name,
            "Attività": act_name,
            "Reparto": dept,
            "Costo Allocato": float(r.total_cost),
            "di cui Personale": float(r.labor_cost),
        })

    # Crea Excel in memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if svc_data:
            pd.DataFrame(svc_data).to_excel(writer, sheet_name="Sintesi Servizi", index=False)
        if act_data:
            pd.DataFrame(act_data).to_excel(writer, sheet_name="Dettaglio Attività", index=False)
        
        # Aggiungi Info Periodo
        pd.DataFrame([{"Periodo": period.name, "Data Export": datetime.now()}]).to_excel(writer, sheet_name="Info", index=False)

    output.seek(0)
    filename = f"Report_ABC_{period.name.replace(' ', '_')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
