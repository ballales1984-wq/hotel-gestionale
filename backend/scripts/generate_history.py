"""
Script: Genera dati storici (24 mesi) per testare l'intera pipeline ABC e AI.
Esegue: python -m scripts.generate_history
"""
import asyncio
import random
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID
import logging
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, CostItem, CostType, CostCenter,
    Employee, LaborAllocation, Activity,
    DriverValue, CostDriver,
    ServiceRevenue, Service,
    ABCResult
)
from app.core.abc_engine import ABCEngine

logger = logging.getLogger(__name__)


async def generate_periods(db: AsyncSession, months_back: int = 24):
    """Crea periodi contabili mensili retroattivi."""
    logger.info(f"Generazione {months_back} periodi contabili...")
    today = date.today()
    created = []
    for i in range(months_back):
        year = today.year - (i // 12)
        month = 12 - (i % 12)
        if month == 0:
            month = 12
            year -= 1
        period_name = f"{month:02d}/{year}"
        # Check esistente per year+month
        existing = await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.year == year,
                AccountingPeriod.month == month
            )
        )
        if existing.scalar_one_or_none():
            continue
        period = AccountingPeriod(
            name=period_name,
            year=year,
            month=month,
            is_closed=(i > 3),
        )
        db.add(period)
        created.append(period)
    await db.commit()
    logger.info(f"Creati {len(created)} periodi")
    return created


async def generate_cost_items(db: AsyncSession, periods):
    """Genera CostItem per ogni periodo, distribuite sui centri di costo."""
    cost_centers = (await db.execute(select(CostCenter))).scalars().all()
    cost_types = list(CostType)
    created = 0
    for period in periods:
        for cc in cost_centers:
            num_items = random.randint(3, 8)
            for _ in range(num_items):
                cost_type = random.choice(cost_types)
                base_amounts = {
                    CostType.LABOR: Decimal(random.uniform(8000, 25000)),
                    CostType.OVERHEAD: Decimal(random.uniform(2000, 8000)),
                    CostType.DIRECT: Decimal(random.uniform(500, 3000)),
                    CostType.UTILITIES: Decimal(random.uniform(1000, 4000)),
                    CostType.DEPRECIATION: Decimal(random.uniform(500, 2000)),
                }
                amount = base_amounts.get(cost_type, Decimal(random.uniform(500, 5000)))
                amount = amount * Decimal(random.uniform(0.9, 1.1))
                item = CostItem(
                    period_id=period.id,
                    cost_center_id=cc.id,
                    account_code=f"60{random.randint(10,99)}",
                    account_name=f"Spesa {cost_type.value} - {cc.code}",
                    cost_type=cost_type,
                    amount=amount.quantize(Decimal('0.01')),
                    source_system="seed_history",
                )
                db.add(item)
                created += 1
    await db.commit()
    logger.info(f"Creati {created} CostItem")


async def generate_employees_and_labor(db: AsyncSession, periods):
    """Crea dipendenti e loro allocazioni ore per attività."""
    employees = [
        {"code": "001", "name": "Mario Rossi",   "hourly": Decimal("18.50"), "dept": "RECEPTION",    "role": "Receptionist"},
        {"code": "002", "name": "Luigi Verdi",   "hourly": Decimal("19.00"), "dept": "RECEPTION",    "role": "Receptionist"},
        {"code": "003", "name": "Anna Neri",     "hourly": Decimal("16.50"), "dept": "HOUSEKEEPING", "role": "Housekeeper"},
        {"code": "004", "name": "Sofia Gialli",  "hourly": Decimal("16.50"), "dept": "HOUSEKEEPING", "role": "Housekeeper"},
        {"code": "005", "name": "Carlo Blu",     "hourly": Decimal("22.00"), "dept": "FNB",          "role": "Waiter"},
        {"code": "006", "name": "Elena Bianchi", "hourly": Decimal("21.50"), "dept": "FNB",          "role": "Waiter"},
        {"code": "007", "name": "Marco Viola",   "hourly": Decimal("20.00"), "dept": "MAINTENANCE",  "role": "Technician"},
        {"code": "008", "name": "Giulia Grigi",  "hourly": Decimal("18.00"), "dept": "COMMERCIAL",   "role": "Sales"},
    ]
    emp_map = {}
    for emp_data in employees:
        exist = await db.execute(select(Employee).where(Employee.employee_code == emp_data["code"]))
        e = exist.scalar_one_or_none()
        if not e:
            from app.models.models import Department
            e = Employee(
                employee_code=emp_data["code"],
                full_name=emp_data["name"],
                role=emp_data["role"],
                department=Department[emp_data["dept"]],
                hourly_cost=emp_data["hourly"],
            )
            db.add(e)
            await db.flush()
        emp_map[emp_data["code"]] = e
    await db.commit()

    activity_assign = {
        "001": ["REC-001", "REC-002"],
        "002": ["REC-003", "REC-004"],
        "003": ["HSK-001", "HSK-002", "HSK-003"],
        "004": ["HSK-001", "HSK-002"],
        "005": ["FNB-001", "FNB-002"],
        "006": ["FNB-003", "FNB-004"],
        "007": ["MNT-001", "MNT-002"],
        "008": ["COM-001", "COM-002"],
    }

    activities = {a.code: a for a in (await db.execute(select(Activity))).scalars().all()}

    created = 0
    for period in periods:
        for emp_code, act_codes in activity_assign.items():
            emp = emp_map[emp_code]
            total_hours = Decimal(random.randint(160, 200))  # ore mensili totali per dipendente
            splits = [random.random() for _ in act_codes]
            total_split = sum(splits)
            # Assegnazione ore con minimo 1 ora per attività
            allocated_hours = []
            for idx, act_code in enumerate(act_codes):
                if idx == len(act_codes) - 1:
                    # Ultima attività prende il resto
                    hours = total_hours - sum(allocated_hours)
                else:
                    hours = max(Decimal(1), (total_hours * Decimal(splits[idx] / total_split)).quantize(Decimal('0.1')))
                    allocated_hours.append(hours)
                # Calcola la percentuale effettiva
                pct = hours / total_hours
                la = LaborAllocation(
                    period_id=period.id,
                    employee_id=emp.id,
                    activity_id=activities[act_code].id,
                    hours=hours,
                    hourly_cost=emp.hourly_cost,
                    allocation_pct=pct,
                    source="seed_history",
                )
                db.add(la)
                created += 1
    await db.commit()
    logger.info(f"Creati {created} LaborAllocation")


async def generate_driver_values(db: AsyncSession, periods):
    """Genera valori driver per ogni periodo."""
    drivers = {d.code: d for d in (await db.execute(select(CostDriver))).scalars().all()}
    created = 0
    for period in periods:
        total_labor_hours = sum(
            la.hours for la in (await db.execute(
                select(LaborAllocation).where(LaborAllocation.period_id == period.id)
            )).scalars().all()
        )
        dv1 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-ORE"].id,
            entity_type='period',
            entity_id=period.id,
            value=total_labor_hours,
        )
        db.add(dv1)

        dv2 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-NOT"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal(random.randint(800, 1800)),
        )
        db.add(dv2)

        dv3 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-CAM"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal(random.randint(900, 2000)),
        )
        db.add(dv3)

        dv4 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-COP"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal(random.randint(1500, 3500)),
        )
        db.add(dv4)

        dv5 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-MQ"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal("3500.00"),
        )
        db.add(dv5)

        dv6 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-EVT"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal(random.randint(5, 20)),
        )
        db.add(dv6)

        dv7 = DriverValue(
            period_id=period.id,
            driver_id=drivers["DRV-TRX"].id,
            entity_type='period',
            entity_id=period.id,
            value=Decimal(random.randint(2000, 5000)),
        )
        db.add(dv7)
        created += 7
    await db.commit()
    logger.info(f"Creati {created} DriverValue")


async def generate_service_revenues(db: AsyncSession, periods):
    """Genera ricavi per servizio per ogni periodo."""
    services = {s.code: s for s in (await db.execute(select(Service))).scalars().all()}
    created = 0
    revenue_ranges = {
        "SVC-PNT": (150000, 250000),
        "SVC-COL": (20000, 40000),
        "SVC-RST": (50000, 90000),
        "SVC-BAR": (10000, 25000),
        "SVC-CON": (30000, 60000),
        "SVC-PRK": (5000, 12000),
    }
    for period in periods:
        for svc_code, (min_rev, max_rev) in revenue_ranges.items():
            svc = services[svc_code]
            if svc_code == "SVC-PNT":
                volume = Decimal(random.randint(1200, 1800))
            elif svc_code in ("SVC-COL", "SVC-RST"):
                volume = Decimal(random.randint(1500, 3000))
            elif svc_code == "SVC-BAR":
                volume = Decimal(random.randint(800, 1500))
            elif svc_code == "SVC-CON":
                volume = Decimal(random.randint(8, 20))
            elif svc_code == "SVC-PRK":
                volume = Decimal(random.randint(400, 800))
            else:
                volume = None
            revenue = Decimal(random.uniform(min_rev, max_rev))
            sr = ServiceRevenue(
                period_id=period.id,
                service_id=svc.id,
                revenue=revenue.quantize(Decimal('0.01')),
                output_volume=volume,
                source_system="seed_history",
            )
            db.add(sr)
            created += 1
    await db.commit()
    logger.info(f"Creati {created} ServiceRevenue")


async def run_abc_calculations(db: AsyncSession, periods):
    """Esegue il calcolo ABC per tutti i periodi chiamando l'API FastAPI."""
    logger.info("Esecuzione calcoli ABC per tutti i periodi...")
    created = 0
    # Usa httpx per chiamare l'API locale (backend deve essere in esecuzione)
    async with httpx.AsyncClient(timeout=30.0) as client:
        for period in periods:
            try:
                # Chiama endpoint di calcolo ABC (salva automaticamente)
                resp = await client.post(
                    f"http://127.0.0.1:8000/api/v1/reports/abc/calculate/{period}",
                    params={"save_results": "true"}
                )
                if resp.status_code == 200:
                    created += 1
                    logger.info(f"Periodo {period.name}: calcolo ABC completato via API")
                else:
                    logger.error(f"Errore ABC periodo {period.name}: HTTP {resp.status_code} - {resp.text}")
            except Exception as e:
                logger.error(f"Errore chiamata API per periodo {period.name}: {e}")
    logger.info(f"Completati {created} calcoli ABC")


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    async with AsyncSessionFactory() as db:
        periods = await generate_periods(db, months_back=24)
        if not periods:
            # Se già esistono, recupera i 12 più recenti (ordine cronologico crescente)
            stmt = select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()).limit(12)
            periods = (await db.execute(stmt)).scalars().all()
            # Inverti per avere ordine cronologico (dal più vecchio al più recente)
            periods = list(reversed(periods))
            logger.info(f"Usati {len(periods)} periodi esistenti")

        await generate_cost_items(db, periods)
        await generate_employees_and_labor(db, periods)
        await generate_driver_values(db, periods)
        await generate_service_revenues(db, periods)

        await run_abc_calculations(db, periods)

        logger.info("✅ Generazione dati storici completata!")


if __name__ == "__main__":
    asyncio.run(main())
