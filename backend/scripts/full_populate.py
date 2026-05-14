"""
Full database reset and historic data population.
Run: python -m scripts.full_populate
"""
import asyncio
import sys
import uuid
import random
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, delete
import logging

sys.path.insert(0, str(__file__).replace('scripts\\full_populate.py', ''))

from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import (
    AccountingPeriod, CostItem, CostType, CostCenter,
    Employee, LaborAllocation, Activity,
    DriverValue, CostDriver, DriverType,
    ServiceRevenue, Service, ServiceType,
    ABCResult, Hotel, User, UserRole,
    AllocationRule, AllocationLevel,
    PMSIntegration, ExternalSystemType,
    Department, MappingType, MappingRule,
    DataImportLog
)
from app.core.abc_engine import ABCEngine, CostRecord, LaborRecord, AllocationRuleRecord, ServiceRevenueRecord

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Global maps (populated by create_base_data, used by generate_history)
_HOTEL_ID = None
_ACT_MAP = {}
_SVC_MAP = {}
_DRV_MAP = {}
_CC_MAP = {}


async def full_reset():
    """Reset completo del database."""
    async with AsyncSessionFactory() as db:
        logger.info("Pulizia completa database...")
        for table in [
            DataImportLog, MappingRule, PMSIntegration,
            ABCResult, ServiceRevenue, LaborAllocation,
            CostItem, DriverValue, AllocationRule,
            AccountingPeriod, Activity, CostCenter,
            CostDriver, Employee, User, Service, Hotel
        ]:
            try:
                await db.execute(delete(table))
            except:
                pass
        await db.commit()
        logger.info("Database pulito.")


async def create_base_data():
    """Crea struttura base."""
    global _HOTEL_ID, _ACT_MAP, _SVC_MAP, _DRV_MAP, _CC_MAP

    async with AsyncSessionFactory() as db:
        # Hotel
        hotel = Hotel(id=uuid.uuid4(), name="Hotel ABC Demo", code="DEMO", is_active=True)
        db.add(hotel)
        await db.flush()
        _HOTEL_ID = hotel.id
        logger.info(f"Hotel creato: {hotel.name} ({_HOTEL_ID})")

        # Utenti
        from passlib.context import CryptContext
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

        users_data = [
            ("admin@hotel-abc.it", "Admin", UserRole.ADMIN, "HotelABC2025!"),
            ("direzione@hotel-abc.it", "Direttore", UserRole.DIRECTOR, "Direzione2025!"),
            ("manager@hotel-abc.it", "Manager", UserRole.MANAGER, "Manager2025!"),
        ]
        for email, name, role, password in users_data:
            u = User(email=email, full_name=name,
                     hashed_password=pwd.hash(password),
                     role=role, hotel_id=_HOTEL_ID)
            db.add(u)
        await db.flush()
        logger.info("Utenti creati: 3")

        # Centri di Costo
        cc_data = [
            ("CC-REC", "Reception", Department.RECEPTION),
            ("CC-HSK", "Housekeeping", Department.HOUSEKEEPING),
            ("CC-FNB", "Food & Beverage", Department.FNB),
            ("CC-MNT", "Manutenzione", Department.MAINTENANCE),
            ("CC-COM", "Commerciale", Department.COMMERCIAL),
            ("CC-CON", "Centro Congressi", Department.CONGRESS),
            ("CC-DIR", "Direzione", Department.DIRECTION),
            ("CC-ADM", "Amministrazione", Department.ADMIN),
        ]
        for code, name, dept in cc_data:
            cc = CostCenter(hotel_id=_HOTEL_ID, code=code, name=name, department=dept)
            db.add(cc)
            await db.flush()
            _CC_MAP[code] = cc
        logger.info(f"Centri di costo: {len(_CC_MAP)}")

        # Attività
        act_data = [
            ("REC-001", "Check-in/Check-out", Department.RECEPTION, "CC-REC", False),
            ("REC-002", "Prenotazioni", Department.RECEPTION, "CC-REC", False),
            ("REC-003", "Concierge", Department.RECEPTION, "CC-REC", False),
            ("REC-004", "Cassa FO", Department.RECEPTION, "CC-REC", False),
            ("HSK-001", "Pulizia check-out", Department.HOUSEKEEPING, "CC-HSK", False),
            ("HSK-002", "Pulizia stayover", Department.HOUSEKEEPING, "CC-HSK", False),
            ("HSK-003", "Aree comuni", Department.HOUSEKEEPING, "CC-HSK", False),
            ("HSK-004", "Biancheria", Department.HOUSEKEEPING, "CC-HSK", False),
            ("FNB-001", "Colazione", Department.FNB, "CC-FNB", False),
            ("FNB-002", "Ristorante", Department.FNB, "CC-FNB", False),
            ("FNB-003", "Bar", Department.FNB, "CC-FNB", False),
            ("FNB-004", "Room service", Department.FNB, "CC-FNB", False),
            ("FNB-005", "Catering", Department.FNB, "CC-FNB", False),
            ("CON-001", "Setup eventi", Department.CONGRESS, "CC-CON", False),
            ("CON-002", "Gestione evento", Department.CONGRESS, "CC-CON", False),
            ("CON-003", "Teardown", Department.CONGRESS, "CC-CON", False),
            ("MNT-001", "Manutenzione camere", Department.MAINTENANCE, "CC-MNT", False),
            ("MNT-002", "Manutenzione impianti", Department.MAINTENANCE, "CC-MNT", False),
            ("MNT-003", "Parcheggio", Department.MAINTENANCE, "CC-MNT", False),
            ("COM-001", "Sales & marketing", Department.COMMERCIAL, "CC-COM", False),
            ("COM-002", "Revenue mgmt", Department.COMMERCIAL, "CC-COM", False),
            ("ADM-001", "Management", Department.DIRECTION, "CC-DIR", True),
            ("ADM-002", "Contabilita'", Department.ADMIN, "CC-ADM", True),
            ("ADM-003", "HR", Department.ADMIN, "CC-ADM", True),
        ]
        for code, name, dept, cc_code, is_support in act_data:
            act = Activity(hotel_id=_HOTEL_ID, code=code, name=name,
                           department=dept, cost_center_id=_CC_MAP[cc_code].id,
                           is_support_activity=is_support)
            db.add(act)
            await db.flush()
            _ACT_MAP[code] = act
        logger.info(f"Attivita': {len(_ACT_MAP)}")

        # Servizi
        svc_data = [
            ("SVC-PNT", "Pernottamento", ServiceType.ACCOMMODATION, "notte"),
            ("SVC-COL", "Colazione", ServiceType.BREAKFAST, "coperto"),
            ("SVC-RST", "Ristorazione", ServiceType.RESTAURANT, "coperto"),
            ("SVC-BAR", "Bar", ServiceType.BAR, "consumazione"),
            ("SVC-CON", "Congressi", ServiceType.CONGRESS, "evento"),
            ("SVC-PRK", "Parcheggio", ServiceType.PARKING, "posto"),
        ]
        for code, name, stype, unit in svc_data:
            svc = Service(hotel_id=_HOTEL_ID, code=code, name=name,
                          service_type=stype, output_unit=unit)
            db.add(svc)
            await db.flush()
            _SVC_MAP[code] = svc
        logger.info(f"Servizi: {len(_SVC_MAP)}")

        # Driver
        drv_data = [
            ("DRV-ORE", "Ore lavorate", DriverType.TIME, "ore"),
            ("DRV-NOT", "Notti vendute", DriverType.VOLUME, "notti"),
            ("DRV-CAM", "Camere pulite", DriverType.VOLUME, "camere"),
            ("DRV-COP", "Coperti", DriverType.VOLUME, "coperti"),
            ("DRV-MQ", "Metri quadrati", DriverType.AREA, "mq"),
            ("DRV-EVT", "Eventi", DriverType.VOLUME, "eventi"),
        ]
        for code, name, dtype, unit in drv_data:
            drv = CostDriver(hotel_id=_HOTEL_ID, code=code, name=name,
                             driver_type=dtype, unit=unit)
            db.add(drv)
            await db.flush()
            _DRV_MAP[code] = drv
        logger.info(f"Driver: {len(_DRV_MAP)}")

        # Regole di allocazione
        alloc_rules = [
            ("REC-001", "SVC-PNT", Decimal("0.50")),
            ("REC-001", "SVC-COL", Decimal("0.30")),
            ("REC-001", "SVC-CON", Decimal("0.20")),
            ("REC-002", "SVC-PNT", Decimal("0.60")),
            ("REC-002", "SVC-CON", Decimal("0.40")),
            ("HSK-001", "SVC-PNT", Decimal("1.00")),
            ("HSK-002", "SVC-PNT", Decimal("1.00")),
            ("FNB-001", "SVC-COL", Decimal("1.00")),
            ("FNB-002", "SVC-RST", Decimal("1.00")),
            ("FNB-003", "SVC-BAR", Decimal("1.00")),
            ("CON-001", "SVC-CON", Decimal("1.00")),
            ("MNT-001", "SVC-PNT", Decimal("1.00")),
            ("MNT-003", "SVC-PRK", Decimal("1.00")),
        ]
        for act_code, svc_code, pct in alloc_rules:
            rule = AllocationRule(
                hotel_id=_HOTEL_ID, name=f"{act_code}->{svc_code}",
                level=AllocationLevel.ACTIVITY_TO_SERVICE,
                source_activity_id=_ACT_MAP[act_code].id,
                target_service_id=_SVC_MAP[svc_code].id,
                allocation_pct=pct, priority=1, is_active=True
            )
            db.add(rule)
        await db.commit()
        logger.info("Regole di allocazione create")

        # Dipendenti
        emp_data = [
            ("EMP001", "Mario Rossi", "Receptionist", Department.RECEPTION, Decimal("18.50")),
            ("EMP002", "Luigi Verdi", "Receptionist", Department.RECEPTION, Decimal("19.00")),
            ("EMP003", "Anna Neri", "Housekeeper", Department.HOUSEKEEPING, Decimal("16.50")),
            ("EMP004", "Sofia Gialli", "Housekeeper", Department.HOUSEKEEPING, Decimal("16.50")),
            ("EMP005", "Carlo Blu", "Camierato", Department.FNB, Decimal("11.00")),
            ("EMP006", "Elena Viola", "Revenue Mgr", Department.COMMERCIAL, Decimal("25.00")),
            ("EMP007", "Marco Gialli", "Manutentore", Department.MAINTENANCE, Decimal("19.50")),
            ("EMP008", "Giulia Blu", "Contabile", Department.ADMIN, Decimal("22.00")),
        ]
        emp_map = {}
        for code, name, role, dept, hourly in emp_data:
            emp = Employee(hotel_id=_HOTEL_ID, employee_code=code, full_name=name,
                           role=role, department=dept, hourly_cost=hourly)
            db.add(emp)
            await db.flush()
            emp_map[code] = emp.id
        logger.info(f"Dipendenti: {len(emp_map)}")

        # PMS Integration
        pms = PMSIntegration(
            hotel_id=_HOTEL_ID, name="Zucchetti PMS",
            system_type=ExternalSystemType.PMS_CSV,
            config_data={"file_path": "/data/pms_export.csv", "delimiter": ";"}
        )
        db.add(pms)
        await db.commit()
        logger.info("Integrazione PMS creata")


async def generate_history(months=24):
    """Genera dati storici completi."""
    global _HOTEL_ID, _ACT_MAP, _SVC_MAP, _DRV_MAP

    async with AsyncSessionFactory() as db:
        db_acts = (await db.execute(select(Activity))).scalars().all()
        act_ids = [a.id for a in db_acts[:15]]
        support_ids = [a.id for a in db_acts if a.is_support_activity]

        db_svcs = (await db.execute(select(Service))).scalars().all()
        svc_ids = [s.id for s in db_svcs]

        db_emps = (await db.execute(select(Employee))).scalars().all()
        emp_map = {e.id: e for e in db_emps}

        db_drvs = (await db.execute(select(CostDriver))).scalars().all()
        drv_map = {d.id: d for d in db_drvs}

        today = datetime.now().replace(day=1)
        created = 0
        for i in range(1, months + 1):
            dt = today - timedelta(days=30 * i)
            dt = dt.replace(day=1)
            yr, mn = dt.year, dt.month
            existing = await db.execute(
                select(AccountingPeriod).where(
                    AccountingPeriod.year == yr, AccountingPeriod.month == mn,
                    AccountingPeriod.hotel_id == _HOTEL_ID
                )
            )
            if existing.scalar_one_or_none():
                continue

            period = AccountingPeriod(
                hotel_id=_HOTEL_ID, year=yr, month=mn,
                name=f"{mn:02d}/{yr}", is_closed=True, closed_at=datetime.now()
            )
            db.add(period)
            await db.flush()
            pid = period.id
            created += 1

            # Cost items
            for _ in range(random.randint(15, 30)):
                cc_ids = list(_CC_MAP.values())
                cc = random.choice(cc_ids)
                ct = random.choice(list(CostType))
                amts = {CostType.LABOR: (8000, 30000), CostType.OVERHEAD: (2000, 10000),
                        CostType.DIRECT: (500, 5000), CostType.UTILITIES: (1000, 5000),
                        CostType.DEPRECIATION: (500, 3000)}
                lo, hi = amts.get(ct, (500, 5000))
                amt = Decimal(random.uniform(lo, hi)).quantize(Decimal('0.01'))
                item = CostItem(hotel_id=_HOTEL_ID, period_id=pid, cost_center_id=cc.id,
                                account_code=f"60{random.randint(10,99)}",
                                account_name=f"Costo {ct.value}", cost_type=ct, amount=amt,
                                source_system="auto")
                db.add(item)

            # Allocazioni lavoro
            for emp in emp_map.values():
                num_acts = random.randint(2, 4)
                assigned = random.sample(act_ids, k=min(num_acts, len(act_ids)))
                total_hrs = Decimal(random.uniform(140, 200)).quantize(Decimal('0.1'))
                splits = [random.random() for _ in assigned]
                ssum = sum(splits)
                accum = Decimal("0")
                for idx, aid in enumerate(assigned):
                    if idx == len(assigned) - 1:
                        hrs = max(Decimal("1"), total_hrs - accum)
                    else:
                        hrs = max(Decimal("1"), (total_hrs * Decimal(splits[idx] / ssum)).quantize(Decimal('0.1')))
                        accum += hrs
                    la = LaborAllocation(
                        hotel_id=_HOTEL_ID, period_id=pid, employee_id=emp.id,
                        activity_id=aid, hours=hrs, hourly_cost=emp.hourly_cost,
                        allocation_pct=(hrs / total_hrs).quantize(Decimal('0.0001')),
                        source="auto"
                    )
                    db.add(la)

            # Driver values
            total_hrs_for_period = Decimal("0")
            for aid in act_ids:
                hours = (await db.execute(select(func.sum(LaborAllocation.hours)).where(
                    LaborAllocation.period_id == pid, LaborAllocation.activity_id == aid
                ))).scalar() or Decimal("0")
                total_hrs_for_period += hours

            for d in drv_map.values():
                if d.code == "DRV-ORE":
                    val = total_hrs_for_period
                elif d.code == "DRV-NOT":
                    val = Decimal(random.randint(800, 2000))
                elif d.code == "DRV-CAM":
                    val = Decimal(random.randint(900, 2200))
                elif d.code == "DRV-COP":
                    val = Decimal(random.randint(1500, 4000))
                elif d.code == "DRV-MQ":
                    val = Decimal("3500")
                elif d.code == "DRV-EVT":
                    val = Decimal(random.randint(5, 25))
                else:
                    val = Decimal(random.randint(1000, 5000))
                dv = DriverValue(
                    hotel_id=_HOTEL_ID, period_id=pid, driver_id=d.id,
                    entity_type='period', entity_id=pid, value=val
                )
                db.add(dv)

            # Ricavi servizio
            rev_ranges = {
                0: (120000, 250000), 1: (15000, 45000), 2: (40000, 100000),
                3: (8000, 30000), 4: (25000, 70000), 5: (4000, 15000)
            }
            for idx, svc in enumerate(db_svcs):
                lo, hi = rev_ranges.get(idx, (5000, 50000))
                rev = Decimal(random.uniform(lo, hi)).quantize(Decimal('0.01'))
                sr = ServiceRevenue(
                    hotel_id=_HOTEL_ID, period_id=pid, service_id=svc.id,
                    revenue=rev, output_volume=Decimal(random.randint(80, 300)),
                    source_system="auto"
                )
                db.add(sr)

        await db.commit()
        logger.info(f"Storico creato: {created} periodi")


async def run_abc():
    """Esegue il calcolo ABC."""
    global _HOTEL_ID, _ACT_MAP, _SVC_MAP

    async with AsyncSessionFactory() as db:
        hotel = (await db.execute(select(Hotel).where(Hotel.code == "DEMO"))).scalar_one()
        hotel_id = hotel.id

        periods = (await db.execute(
            select(AccountingPeriod).where(AccountingPeriod.hotel_id == hotel_id)
                .order_by(AccountingPeriod.year, AccountingPeriod.month)
        )).scalars().all()

        db_acts = (await db.execute(select(Activity).where(Activity.is_active == True))).scalars().all()
        activity_map = {a.id: a for a in db_acts}
        support_ids = [a.id for a in db_acts if a.is_support_activity]

        services = (await db.execute(select(Service).where(Service.is_active == True))).scalars().all()
        service_map = {s.id: s for s in services}

        engine = ABCEngine()
        calculated = 0

        for period in periods:
            pid = period.id
            costs = (await db.execute(select(CostItem).where(CostItem.period_id == pid))).scalars().all()
            cost_records = [CostRecord(c.id, c.cost_center_id, c.cost_type.value, c.amount) for c in costs]

            labor_rows = (await db.execute(select(LaborAllocation).where(LaborAllocation.period_id == pid))).scalars().all()
            labor_records = [LaborRecord(la.employee_id, la.activity_id, la.hours, la.hourly_cost, la.allocation_pct) for la in labor_rows]

            if not labor_records:
                logger.warning(f"Periodo {period.name}: nessuna allocazione lavoro, skip")
                continue

            rules_raw = (await db.execute(select(AllocationRule).where(AllocationRule.is_active == True))).scalars().all()
            allocation_rules = [
                AllocationRuleRecord(r.id, r.level.value, r.source_cost_center_id,
                                     r.source_activity_id, r.target_activity_id,
                                     r.target_service_id, {}, r.allocation_pct, r.priority)
                for r in rules_raw
            ]

            revenues_raw = (await db.execute(select(ServiceRevenue).where(ServiceRevenue.period_id == pid))).scalars().all()
            service_revenues = [ServiceRevenueRecord(r.service_id, r.revenue, r.output_volume) for r in revenues_raw]

            try:
                result = engine.calculate(
                    period_id=pid, cost_records=cost_records,
                    labor_records=labor_records, allocation_rules=allocation_rules,
                    service_revenues=service_revenues,
                    activity_ids=list(activity_map.keys()),
                    service_ids=list(service_map.keys()),
                    support_activity_ids=support_ids
                )
                from sqlalchemy import delete
                await db.execute(delete(ABCResult).where(ABCResult.period_id == pid))
                for svc_id, svc_res in result.service_results.items():
                    abc = ABCResult(
                        hotel_id=hotel_id, period_id=pid, service_id=svc_id,
                        direct_cost=svc_res.direct_cost, labor_cost=svc_res.labor_cost,
                        overhead_cost=svc_res.overhead_cost, total_cost=svc_res.total_cost,
                        revenue=svc_res.revenue, gross_margin=svc_res.gross_margin,
                        margin_pct=svc_res.margin_pct, cost_per_unit=svc_res.cost_per_unit,
                        output_volume=svc_res.output_volume
                    )
                    db.add(abc)
                await db.commit()
                calculated += 1
            except Exception as e:
                logger.error(f"Errore ABC periodo {period.name}: {e}")

        logger.info(f"Calcoli ABC completati: {calculated}/{len(periods)} periodi")


async def verify():
    """Verifica finale."""
    async with AsyncSessionFactory() as db:
        logger.info("=== VERIFICA FINALE ===")
        for tbl_name, tbl_model in [
            ("Hotels", Hotel), ("Users", User), ("Periods", AccountingPeriod),
            ("Activities", Activity), ("Services", Service), ("CostItems", CostItem),
            ("LaborAllocations", LaborAllocation), ("ServiceRevenues", ServiceRevenue),
            ("ABCResults", ABCResult), ("AllocationRules", AllocationRule),
        ]:
            cnt = (await db.execute(select(func.count(tbl_model.id)))).scalar()
            logger.info(f"  {tbl_name}: {cnt}")
        logger.info("POPOLAMENTO COMPLETATO!")


async def main():
    logger.info("=" * 60)
    logger.info("POPOLAMENTO COMPLETO HOTEL ABC")
    logger.info("=" * 60)

    await full_reset()
    await create_base_data()
    await generate_history(months=24)
    await run_abc()
    await verify()

    logger.info("=" * 60)
    logger.info("Avvia il backend: cd backend && venv\\Scripts\\Activate.ps1 && uvicorn app.main:app --reload --port 8000")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())