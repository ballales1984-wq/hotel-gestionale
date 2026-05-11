import asyncio
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, ABCResult, User, Activity, Service
from sqlalchemy import select, func

async def check():
    async with AsyncSessionFactory() as db:
        res = await db.execute(select(AccountingPeriod.name, AccountingPeriod.year, AccountingPeriod.month).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()))
        periods = res.all()
        print(f"Totale periodi: {len(periods)}")
        print("Ultimi 5 periodi:")
        for p in periods[:5]:
            print(f" - {p.name} ({p.year}/{p.month})")
        
        res_abc = await db.execute(select(func.count(ABCResult.id)))
        print(f"Calcoli ABC salvati: {res_abc.scalar()}")
        
        res_services = await db.execute(select(func.count(Service.id)))
        print(f"Servizi configurati: {res_services.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
