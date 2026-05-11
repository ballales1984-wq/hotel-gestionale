import asyncio
from sqlalchemy import select, func
from app.db.database import AsyncSessionFactory

async def check():
    async with AsyncSessionFactory() as db:
        # Lista tabelle principali
        from app.models.models import (
            AccountingPeriod, ABCResult, CostItem, Employee,
            LaborAllocation, DriverValue, ServiceRevenue
        )
        tables = [
            ("AccountingPeriod", AccountingPeriod),
            ("ABCResult", ABCResult),
            ("CostItem", CostItem),
            ("Employee", Employee),
            ("LaborAllocation", LaborAllocation),
            ("DriverValue", DriverValue),
            ("ServiceRevenue", ServiceRevenue),
        ]
        print("--- CONTEGGIO TABELLE ---")
        for name, model in tables:
            result = await db.execute(select(func.count(model.id)))
            count = result.scalar()
            print(f"{name}: {count}")

if __name__ == "__main__":
    asyncio.run(check())
