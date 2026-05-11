import asyncio
from app.db.database import AsyncSessionFactory
from app.models.models import ABCResult
from sqlalchemy import select, func

async def main():
    async with AsyncSessionFactory() as db:
        cnt = await db.execute(select(func.count(ABCResult.id)))
        print("ABCResults count:", cnt.scalar())
        # Also check periods
        from app.models.models import AccountingPeriod
        p_cnt = await db.execute(select(func.count(AccountingPeriod.id)))
        print("Periodi:", p_cnt.scalar())

asyncio.run(main())
