import asyncio
from app.db.database import AsyncSessionFactory
from sqlalchemy import select
from app.models.models import ABCResult

async def check_abc():
    async with AsyncSessionFactory() as db:
        results = (await db.execute(select(ABCResult))).scalars().all()
        print("ABC Results breakdown:")
        for r in results:
            print(f"  Service {r.service_id[:8]}... Total: {r.total_cost}, Labor: {r.labor_cost}, Overhead: {r.overhead_cost}, Gross Margin: {r.gross_margin}")

asyncio.run(check_abc())
