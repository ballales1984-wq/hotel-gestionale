import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, delete, func
from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, CostItem, CostType, Service, ServiceRevenue,
    LaborAllocation, Activity, Employee, Hotel, Department, DriverValue, ABCResult
)

async def populate_minimal_history():
    async with AsyncSessionFactory() as db:
        # Get or create default hotel
        hotel_res = await db.execute(select(Hotel).where(Hotel.code == "DEMO"))
        hotel = hotel_res.scalar_one_or_none()
        if not hotel:
            hotel = Hotel(
                id=uuid.uuid4(),
                name="Hotel Demo",
                code="DEMO",
                is_active=True,
            )
            db.add(hotel)
            await db.flush()
            print("[OK] Creato Hotel Demo: %s" % hotel.id)
        else:
            print("[OK] Hotel Demo esistente: %s" % hotel.id)

        print("[CLEANUP] Pulizia dati storici per questo hotel...")

        # Cancellazione CASCADE manuale
        await db.execute(delete(ServiceRevenue).where(ServiceRevenue.hotel_id == hotel.id))
        await db.execute(delete(LaborAllocation).where(LaborAllocation.hotel_id == hotel.id))
        await db.execute(delete(CostItem).where(CostItem.hotel_id == hotel.id))
        await db.execute(delete(DriverValue).where(DriverValue.hotel_id == hotel.id))
        await db.execute(delete(ABCResult).where(ABCResult.hotel_id == hotel.id))
        await db.execute(delete(AccountingPeriod).where(AccountingPeriod.hotel_id == hotel.id))
        await db.flush()

        # Verifica cancellazione
        cnt = await db.execute(select(func.count(AccountingPeriod.id)).where(AccountingPeriod.hotel_id == hotel.id))
        print("   Periodi residui dopo cleanup: %d" % cnt.scalar())

        print("[INFO] Creazione periodi storici (ultimi 12 mesi)...")

        # Get reference data
        activities_res = await db.execute(select(Activity).where(Activity.is_active == True, Activity.hotel_id == hotel.id))
        activities = activities_res.scalars().all()
        if not activities:
            print("[ERR] Nessuna attivita trovata. Eseguire seed prima.")
            return

        services_res = await db.execute(select(Service).where(Service.hotel_id == hotel.id))
        services = services_res.scalars().all()
        if not services:
            print("[ERR] Nessun servizio trovato. Eseguire seed prima.")
            return

        employees_res = await db.execute(select(Employee).where(Employee.hotel_id == hotel.id))
        employees = employees_res.scalars().all()
        if not employees:
            emp = Employee(
                hotel_id=hotel.id,
                employee_code="EMP001",
                full_name="Mario Rossi",
                role="Receptionist",
                department=Department.RECEPTION,
                hourly_cost=Decimal("20.00")
            )
            db.add(emp)
            await db.flush()
            employees = [emp]
            print("   Creato dipendente dummy EMP001")

        today = datetime.now().replace(day=1)
        created_periods = 0
        created_months = set()
        
        # Genera ultimi 12 mesi
        for i in range(1, 13):
            first_day_of_month = today - timedelta(days=30 * i)
            first_day_of_month = first_day_of_month.replace(day=1)
            month = first_day_of_month.month
            year = first_day_of_month.year

            key = (year, month)
            if key in created_months:
                print("   [WARN] Periodo %d-%02d gia creato in questo run, skip." % (year, month))
                continue
            created_months.add(key)

            # Controlla se esiste gia (per debug)
            existing = await db.execute(select(AccountingPeriod).where(
                AccountingPeriod.hotel_id == hotel.id,
                AccountingPeriod.year == year,
                AccountingPeriod.month == month
            ))
            if existing.scalar_one_or_none():
                print("   [WARN] Periodo %d-%02d gia esistente nel DB, skip." % (year, month))
                continue

            period = AccountingPeriod(
                id=uuid.uuid4(),
                hotel_id=hotel.id,
                year=year,
                month=month,
                name=first_day_of_month.strftime('%B %Y'),
                is_closed=True,
                closed_at=datetime.now()
            )
            db.add(period)
            try:
                await db.flush()
                created_periods += 1
                print("   [OK] Creato periodo: %d-%02d (ID: %s)" % (year, month, period.id))
            except Exception as e:
                print("   [ERR] Errore creando periodo %d-%02d: %s" % (year, month, e))
                await db.rollback()
                return

            # Add some costs per attivita (prime 5)
            for act in activities[:5]:
                cost = CostItem(
                    period_id=period.id,
                    hotel_id=hotel.id,
                    cost_center_id=act.cost_center_id,
                    account_name="Costo operativo %s" % act.name,
                    cost_type=CostType.DIRECT,
                    amount=Decimal(str(2000 + i * 100)),
                    source_system="manual"
                )
                db.add(cost)

            # Add some labor allocations per dipendente e prime 2 attivita
            for emp in employees:
                for act in activities[:2]:
                    labor = LaborAllocation(
                        period_id=period.id,
                        hotel_id=hotel.id,
                        employee_id=emp.id,
                        activity_id=act.id,
                        hours=Decimal("80.00"),
                        hourly_cost=emp.hourly_cost,
                        allocation_pct=Decimal("0.50"),
                        source="manual"
                    )
                    db.add(labor)

            # Add some revenues per servizio
            for svc in services:
                rev = ServiceRevenue(
                    period_id=period.id,
                    hotel_id=hotel.id,
                    service_id=svc.id,
                    revenue=Decimal(str(10000 + i * 500)),
                    output_volume=Decimal("100"),
                    source_system="manual"
                )
                db.add(rev)

        try:
            await db.commit()
            print("[OK] Storico minimo creato: %d periodi, %d attivita, %d servizi." % (created_periods, len(activities), len(services)))
        except Exception as e:
            print("[ERR] Errore commit: %s" % e)
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(populate_minimal_history())
