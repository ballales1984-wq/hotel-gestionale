import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, Service
from sqlalchemy import select
from app.api.v1.endpoints.reports import calculate_abc, _save_abc_results

async def run_calc():
    async with AsyncSessionFactory() as db:
        res = await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()))
        period = res.scalars().first()
        if not period:
            print("Nessun periodo trovato.")
            return
        
        print(f"Eseguo calcolo ABC per: {period.name} ({period.id})")
        
        # Carichiamo i servizi manualmente per passarla al salvataggio
        services_q = await db.execute(select(Service))
        service_map = {s.id: s for s in services_q.scalars().all()}
        
        # Eseguiamo il motore direttamente per avere l'oggetto risultato
        # Invece di chiamare l'endpoint che usa background tasks
        from app.core.abc_engine import ABCEngine
        from app.models.models import Activity, CostItem, LaborAllocation, ServiceRevenue, AllocationRule
        
        activities_q = await db.execute(select(Activity).where(Activity.is_active == True))
        activities = activities_q.scalars().all()
        activity_map = {a.id: a for a in activities}
        support_ids = [a.id for a in activities if a.is_support_activity]
        
        costs_q = await db.execute(select(CostItem).where(CostItem.period_id == period.id))
        cost_items = costs_q.scalars().all()
        
        from app.core.abc_engine import CostRecord, LaborRecord, ServiceRevenueRecord, AllocationRuleRecord
        cost_records = [CostRecord(c.id, c.cost_center_id, c.cost_type.value, c.amount) for c in cost_items]
        
        labor_q = await db.execute(select(LaborAllocation).where(LaborAllocation.period_id == period.id))
        labor_records = [LaborRecord(la.employee_id, la.activity_id, la.hours, la.hourly_cost, la.allocation_pct) for la in labor_q.scalars().all()]
        
        revenues_q = await db.execute(select(ServiceRevenue).where(ServiceRevenue.period_id == period.id))
        service_revenues = [ServiceRevenueRecord(r.service_id, r.revenue, r.output_volume) for r in revenues_q.scalars().all()]
        
        # Regole (semplificate per il test)
        rules_q = await db.execute(select(AllocationRule).where(AllocationRule.is_active == True))
        raw_rules = rules_q.scalars().all()
        allocation_rules = [AllocationRuleRecord(r.id, r.level.value, r.source_cost_center_id, r.source_activity_id, r.target_activity_id, r.target_service_id, {}, r.allocation_pct, r.priority) for r in raw_rules]
        
        engine = ABCEngine()
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
        
        print("Salvataggio risultati...")
        await _save_abc_results(db, period.id, period.hotel_id, abc_result, service_map)
        print("Fatto.")

if __name__ == "__main__":
    asyncio.run(run_calc())
