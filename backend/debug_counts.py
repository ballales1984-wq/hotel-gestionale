import asyncio
from app.db.database import AsyncSessionFactory
from sqlalchemy import select, func
from app.models.models import ServiceRevenue, CostItem, LaborAllocation

async def check():
    async with AsyncSessionFactory() as db:
        sr = (await db.execute(select(func.count(ServiceRevenue.id)))).scalar()
        ci = (await db.execute(select(func.count(CostItem.id)))).scalar()
        la = (await db.execute(select(func.count(LaborAllocation.id)))).scalar()
        print(f"ServiceRevenue: {sr}")
        print(f"CostItem: {ci}")
        print(f"LaborAllocation: {la}")

asyncio.run(check())
