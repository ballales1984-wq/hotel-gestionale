import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, User, CostItem, CostType, Service, ServiceRevenue, LaborAllocation, Activity, Employee

async def populate_minimal_history():
    async with AsyncSessionFactory() as db:
        # Check if periods already exist
        res = await db.execute(select(AccountingPeriod))
        if res.scalars().first():
            print("Periodi già esistenti. Salto popolamento storico.")
            return

        print("Creazione periodi storici (ultimi 6 mesi)...")

        # Get reference data
        activities_res = await db.execute(select(Activity))
        activities = activities_res.scalars().all()

        services_res = await db.execute(select(Service))
        services = services_res.scalars().all()

        employees_res = await db.execute(select(Employee))
        employees = employees_res.scalars().all()
        if not employees:
            # Create a dummy employee if none exist
            emp = Employee(
                employee_code="EMP001",
                full_name="Mario Rossi",
                role="Receptionist",
                department="reception",
                hourly_cost=Decimal("20.00")
            )
            db.add(emp)
            await db.flush()
            employees = [emp]

        today = datetime.now().replace(day=1)
        for i in range(1, 7):
            # Go back i months from the current month
            first_day_of_month = today - timedelta(days=30 * i)
            first_day_of_month = first_day_of_month.replace(day=1)
            month = first_day_of_month.month
            year = first_day_of_month.year

            period = AccountingPeriod(
                id=uuid.uuid4(),
                year=year,
                month=month,
                name=first_day_of_month.strftime('%B %Y'),
                is_closed=True,
                closed_at=datetime.now()
            )
            db.add(period)
            await db.flush()

            # Add some costs
            for act in activities[:5]:
                cost = CostItem(
                    period_id=period.id,
                    cost_center_id=act.cost_center_id,
                    account_name=f"Costo operativo {act.name}",
                    cost_type=CostType.DIRECT,
                    amount=Decimal(str(2000 + i * 100)),
                    source_system="manual"
                )
                db.add(cost)

            # Add some labor
            for emp in employees:
                for act in activities[:2]:
                    labor = LaborAllocation(
                        period_id=period.id,
                        employee_id=emp.id,
                        activity_id=act.id,
                        hours=Decimal("80.00"),
                        hourly_cost=emp.hourly_cost,
                        allocation_pct=Decimal("0.50"),
                        source="manual"
                    )
                    db.add(labor)

            # Add some revenues
            for svc in services:
                rev = ServiceRevenue(
                    period_id=period.id,
                    service_id=svc.id,
                    revenue=Decimal(str(10000 + i * 500)),
                    output_volume=Decimal("100"),
                    source_system="manual"
                )
                db.add(rev)

        await db.commit()
        print("✅ Storico minimo creato con successo!")

if __name__ == "__main__":
    asyncio.run(populate_minimal_history())
