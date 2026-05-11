import asyncio
import uuid
from decimal import Decimal
from sqlalchemy import select
from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, DriverValue, CostDriver, Service, Activity,
    Employee, LaborAllocation, Hotel, ServiceRevenue
)

async def populate_driver_values():
    """
    Popola driver_values storici per i driver principali.
    - DRV-NOT: numero notti per servizio pernottamento (da revenue output_volume)
    - DRV-COP: coperti per servizi ristorazione/colazione
    - DRV-ORE: ore lavorate per attività (da LaborAllocation)
    - DRV-CAM: camere pulite per housekeeping (simulato)
    """
    async with AsyncSessionFactory() as db:
        # Prendi hotel default
        hotel_res = await db.execute(select(Hotel).where(Hotel.code == "DEMO"))
        hotel = hotel_res.scalar_one_or_none()
        if not hotel:
            print("Nessun hotel Demo trovato.")
            return
        print("Hotel Demo: %s" % hotel.id)

        # Prendi tutti i periodi
        periods_q = await db.execute(
            select(AccountingPeriod).where(AccountingPeriod.hotel_id == hotel.id).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
        )
        periods = periods_q.scalars().all()
        print("Periodi trovati: %d" % len(periods))

        # Prendi driver
        drivers_q = await db.execute(select(CostDriver).where(CostDriver.hotel_id == hotel.id))
        drivers = {d.code: d for d in drivers_q.scalars().all()}
        print("Driver disponibili: %s" % list(drivers.keys()))

        # Prendi servizi e attività
        services_q = await db.execute(select(Service).where(Service.hotel_id == hotel.id))
        services = services_q.scalars().all()
        activities_q = await db.execute(select(Activity).where(Activity.hotel_id == hotel.id))
        activities = activities_q.scalars().all()

        # Contatore
        created = 0

        for period in periods:
            print("\n Periodo: %s" % period.name)

            # 1. DRV-NOT per servizio Pernottamento (da ServiceRevenue output_volume)
            drv_not = drivers.get("DRV-NOT")
            if drv_not:
                revenues_q = await db.execute(
                    select(ServiceRevenue).where(ServiceRevenue.period_id == period.id)
                )
                revenues = revenues_q.scalars().all()
                for rev in revenues:
                    svc = next((s for s in services if s.id == rev.service_id), None)
                    if svc and svc.service_type.value == "pernottamento":
                        val = rev.output_volume or Decimal("100")
                        dv = DriverValue(
                            hotel_id=hotel.id,
                            driver_id=drv_not.id,
                            period_id=period.id,
                            entity_type="service",
                            entity_id=rev.service_id,
                            value=val,
                            source="derived_from_revenue"
                        )
                        db.add(dv)
                        created += 1

            # 2. DRV-COP per servizi Ristorazione/Colazione
            drv_cop = drivers.get("DRV-COP")
            if drv_cop:
                for rev in revenues:
                    svc = next((s for s in services if s.id == rev.service_id), None)
                    if svc and svc.service_type.value in ["ristorazione", "colazione"]:
                        val = rev.output_volume or Decimal("100")
                        dv = DriverValue(
                            hotel_id=hotel.id,
                            driver_id=drv_cop.id,
                            period_id=period.id,
                            entity_type="service",
                            entity_id=rev.service_id,
                            value=val,
                            source="derived_from_revenue"
                        )
                        db.add(dv)
                        created += 1

            # 3. DRV-ORE per attività (da LaborAllocation)
            drv_ore = drivers.get("DRV-ORE")
            if drv_ore:
                labor_q = await db.execute(
                    select(LaborAllocation).where(LaborAllocation.period_id == period.id)
                )
                labor_allocations = labor_q.scalars().all()
                # Raggruppa per activity
                activity_hours = {}
                for la in labor_allocations:
                    activity_hours[la.activity_id] = activity_hours.get(la.activity_id, Decimal("0")) + la.hours
                for act_id, total_hours in activity_hours.items():
                    dv = DriverValue(
                        hotel_id=hotel.id,
                        driver_id=drv_ore.id,
                        period_id=period.id,
                        entity_type="activity",
                        entity_id=act_id,
                        value=total_hours,
                        source="derived_from_labor"
                    )
                    db.add(dv)
                    created += 1

            # 4. DRV-CAM per Housekeeping (simulato: 0.5 ore per notte di pulizia)
            drv_cam = drivers.get("DRV-CAM")
            if drv_cam:
                # Trova attività housekeeping
                hsk_activities = [a for a in activities if a.department.value == "housekeeping"]
                if hsk_activities:
                    # Prendi notti totali da DRV-NOT
                    notti = Decimal("0")
                    if drv_not:
                        dv_not_q = await db.execute(
                            select(DriverValue).where(
                                DriverValue.period_id == period.id,
                                DriverValue.driver_id == drv_not.id,
                                DriverValue.entity_type == "service"
                            )
                        )
                        notti_vals = dv_not_q.scalars().all()
                        notti = sum(v.value for v in notti_vals)
                    # Simula camere pulite = notti (ogni stanza check-out)
                    camere = notti
                    for act in hsk_activities:
                        dv = DriverValue(
                            hotel_id=hotel.id,
                            driver_id=drv_cam.id,
                            period_id=period.id,
                            entity_type="activity",
                            entity_id=act.id,
                            value=camere,
                            source="simulated_from_occupancy"
                        )
                        db.add(dv)
                        created += 1

        await db.commit()
        print("\n[OK] DriverValues creati: %d" % created)

if __name__ == "__main__":
    asyncio.run(populate_driver_values())
