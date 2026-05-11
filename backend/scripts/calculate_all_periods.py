import asyncio
from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, Service, Activity, CostItem, LaborAllocation,
    ServiceRevenue, AllocationRule, ABCResult
)
from sqlalchemy import select, delete
from app.core.abc_engine import (
    ABCEngine, CostRecord, LaborRecord, ServiceRevenueRecord, AllocationRuleRecord
)
from app.api.v1.endpoints.reports import _save_abc_results

async def calculate_all_periods():
    async with AsyncSessionFactory() as db:
        # Prendi tutti i periodi ordinati (più recente prima)
        periods_q = await db.execute(
            select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
        )
        periods = periods_q.scalars().all()
        print("Trovati %d periodi da processare." % len(periods))

        # Carica dati comuni (una volta)
        services_q = await db.execute(select(Service))
        service_map = {s.id: s for s in services_q.scalars().all()}

        activities_q = await db.execute(select(Activity).where(Activity.is_active == True))
        activities = activities_q.scalars().all()
        activity_map = {a.id: a for a in activities}
        support_ids = [a.id for a in activities if a.is_support_activity]

        rules_q = await db.execute(select(AllocationRule).where(AllocationRule.is_active == True))
        raw_rules = rules_q.scalars().all()
        allocation_rules = [
            AllocationRuleRecord(
                rule_id=r.id,
                level=r.level.value,
                source_cost_center_id=r.source_cost_center_id,
                source_activity_id=r.source_activity_id,
                target_activity_id=r.target_activity_id,
                target_service_id=r.target_service_id,
                driver_values={},
                allocation_pct=r.allocation_pct,
                priority=r.priority,
            )
            for r in raw_rules
        ]

        engine = ABCEngine()

        for period in periods:
            print("\n=== Calcolo ABC per: %s ===" % period.name)

            # Carica dati specifici del periodo
            costs_q = await db.execute(select(CostItem).where(CostItem.period_id == period.id))
            cost_items = costs_q.scalars().all()
            cost_records = [
                CostRecord(c.id, c.cost_center_id, c.cost_type.value, c.amount)
                for c in cost_items
            ]

            labor_q = await db.execute(
                select(LaborAllocation).where(LaborAllocation.period_id == period.id)
            )
            labor_records = [
                LaborRecord(la.employee_id, la.activity_id, la.hours, la.hourly_cost, la.allocation_pct)
                for la in labor_q.scalars().all()
            ]

            revenues_q = await db.execute(
                select(ServiceRevenue).where(ServiceRevenue.period_id == period.id)
            )
            service_revenues = [
                ServiceRevenueRecord(r.service_id, r.revenue, r.output_volume)
                for r in revenues_q.scalars().all()
            ]

            # Esegui calcolo
            try:
                abc_result = engine.calculate(
                    period_id=period.id,
                    cost_records=cost_records,
                    labor_records=labor_records,
                    allocation_rules=allocation_rules,
                    service_revenues=service_revenues,
                    activity_ids=list(activity_map.keys()),
                    service_ids=list(service_map.keys()),
                    support_activity_ids=support_ids,
                )
                print("   Calcolo completato. Salvataggio...")

                # Pulisci risultati precedenti
                await db.execute(delete(ABCResult).where(ABCResult.period_id == period.id))
                # Salva nuovi (passiamo hotel_id)
                await _save_abc_results(db, period.id, period.hotel_id, abc_result, service_map)
                print("   [OK] Risultati salvati per %s" % period.name)
            except Exception as e:
                print("   [ERR] Errore per %s: %s" % (period.name, e))
                import traceback; traceback.print_exc()

        print("\n[OK] Calcoli ABC completati per tutti i periodi.")

if __name__ == "__main__":
    asyncio.run(calculate_all_periods())
