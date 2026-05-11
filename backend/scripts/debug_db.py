import asyncio
from app.db.database import AsyncSessionFactory
from app.models.models import ABCResult, AccountingPeriod
from sqlalchemy import select

async def check():
    async with AsyncSessionFactory() as db:
        p = await db.execute(select(AccountingPeriod))
        periods = p.scalars().all()
        print(f"PERIODS: {len(periods)}")
        for prd in periods:
            print(f" - ID: {prd.id}, Name: {prd.name}")
            
        r = await db.execute(select(ABCResult))
        results = r.scalars().all()
        print(f"ABC RESULTS: {len(results)}")
        for res in results:
            print(f" - Period: {res.period_id}, Service: {res.service_id}, Revenue: {res.revenue}")
            
        rev_q = await db.execute(select(ServiceRevenue))
        revenues = rev_q.scalars().all()
        print(f"SERVICE REVENUES: {len(revenues)}")
        for rev in revenues:
            print(f" - Period: {rev.period_id}, Service: {rev.service_id}, Revenue: {rev.revenue}")

if __name__ == "__main__":
    asyncio.run(check())
