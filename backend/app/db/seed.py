"""
Seed data — Popola il database con dati di esempio realistici per un hotel.
Eseguire: python -m app.db.seed
"""
import asyncio
import logging
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import (
    Activity, AllocationRule, AllocationLevel, CostCenter, CostDriver,
    Department, DriverType, Service, ServiceType, User, UserRole,
    AccountingPeriod, ABCResult, CostItem, Employee, LaborAllocation,
    DriverValue, ServiceRevenue, Hotel
)

logger = logging.getLogger(__name__)

COST_CENTERS = [
    {"code": "CC-REC", "name": "Reception", "department": Department.RECEPTION},
    {"code": "CC-HSK", "name": "Housekeeping", "department": Department.HOUSEKEEPING},
    {"code": "CC-FNB", "name": "Food & Beverage", "department": Department.FNB},
    {"code": "CC-MNT", "name": "Manutenzione", "department": Department.MAINTENANCE},
    {"code": "CC-COM", "name": "Commerciale", "department": Department.COMMERCIAL},
    {"code": "CC-CON", "name": "Centro Congressi", "department": Department.CONGRESS},
    {"code": "CC-DIR", "name": "Direzione", "department": Department.DIRECTION},
    {"code": "CC-ADM", "name": "Amministrazione", "department": Department.ADMIN},
]

ACTIVITIES = [
    # Reception
    {"code": "REC-001", "name": "Check-in / Check-out", "department": Department.RECEPTION, "cc": "CC-REC"},
    {"code": "REC-002", "name": "Gestione prenotazioni", "department": Department.RECEPTION, "cc": "CC-REC"},
    {"code": "REC-003", "name": "Concierge e informazioni", "department": Department.RECEPTION, "cc": "CC-REC"},
    {"code": "REC-004", "name": "Cassa e amministrazione FO", "department": Department.RECEPTION, "cc": "CC-REC"},
    # Housekeeping
    {"code": "HSK-001", "name": "Pulizia camere check-out", "department": Department.HOUSEKEEPING, "cc": "CC-HSK"},
    {"code": "HSK-002", "name": "Pulizia camere stayover", "department": Department.HOUSEKEEPING, "cc": "CC-HSK"},
    {"code": "HSK-003", "name": "Pulizia aree comuni", "department": Department.HOUSEKEEPING, "cc": "CC-HSK"},
    {"code": "HSK-004", "name": "Gestione biancheria", "department": Department.HOUSEKEEPING, "cc": "CC-HSK"},
    # F&B
    {"code": "FNB-001", "name": "Servizio colazione", "department": Department.FNB, "cc": "CC-FNB"},
    {"code": "FNB-002", "name": "Servizio pranzo/cena ristorante", "department": Department.FNB, "cc": "CC-FNB"},
    {"code": "FNB-003", "name": "Servizio bar e beverage", "department": Department.FNB, "cc": "CC-FNB"},
    {"code": "FNB-004", "name": "Room service", "department": Department.FNB, "cc": "CC-FNB"},
    {"code": "FNB-005", "name": "Catering eventi", "department": Department.FNB, "cc": "CC-FNB"},
    # Centro Congressi
    {"code": "CON-001", "name": "Setup sala eventi", "department": Department.CONGRESS, "cc": "CC-CON"},
    {"code": "CON-002", "name": "Gestione evento in corso", "department": Department.CONGRESS, "cc": "CC-CON"},
    {"code": "CON-003", "name": "Teardown e pulizia post-evento", "department": Department.CONGRESS, "cc": "CC-CON"},
    # Manutenzione
    {"code": "MNT-001", "name": "Manutenzione ordinaria camere", "department": Department.MAINTENANCE, "cc": "CC-MNT"},
    {"code": "MNT-002", "name": "Manutenzione impianti", "department": Department.MAINTENANCE, "cc": "CC-MNT"},
    {"code": "MNT-003", "name": "Gestione parcheggio", "department": Department.MAINTENANCE, "cc": "CC-MNT"},
    # Commerciale
    {"code": "COM-001", "name": "Sales e marketing", "department": Department.COMMERCIAL, "cc": "CC-COM"},
    {"code": "COM-002", "name": "Revenue management", "department": Department.COMMERCIAL, "cc": "CC-COM"},
    # Direzione / Admin (attività di supporto)
    {"code": "DIR-001", "name": "Management e coordinamento", "department": Department.DIRECTION, "cc": "CC-DIR", "is_support": True},
    {"code": "ADM-001", "name": "Contabilità e amministrazione", "department": Department.ADMIN, "cc": "CC-ADM", "is_support": True},
    {"code": "ADM-002", "name": "Gestione HR e personale", "department": Department.ADMIN, "cc": "CC-ADM", "is_support": True},
]

SERVICES = [
    {"code": "SVC-PNT", "name": "Pernottamento", "type": ServiceType.ACCOMMODATION, "unit": "notte"},
    {"code": "SVC-COL", "name": "Colazione", "type": ServiceType.BREAKFAST, "unit": "coperto"},
    {"code": "SVC-RST", "name": "Ristorazione", "type": ServiceType.RESTAURANT, "unit": "coperto"},
    {"code": "SVC-BAR", "name": "Bar e Beverage", "type": ServiceType.BAR, "unit": "consumazione"},
    {"code": "SVC-CON", "name": "Centro Congressi", "type": ServiceType.CONGRESS, "unit": "evento"},
    {"code": "SVC-PRK", "name": "Parcheggio", "type": ServiceType.PARKING, "unit": "sosta"},
]

DRIVERS = [
    {"code": "DRV-ORE", "name": "Ore lavorate", "type": DriverType.TIME, "unit": "ore"},
    {"code": "DRV-NOT", "name": "Numero notti", "type": DriverType.VOLUME, "unit": "notti"},
    {"code": "DRV-CAM", "name": "Camere pulite", "type": DriverType.VOLUME, "unit": "camere"},
    {"code": "DRV-COP", "name": "Coperti serviti", "type": DriverType.VOLUME, "unit": "coperti"},
    {"code": "DRV-MQ", "name": "Metri quadrati", "type": DriverType.AREA, "unit": "mq"},
    {"code": "DRV-EVT", "name": "Numero eventi", "type": DriverType.VOLUME, "unit": "eventi"},
    {"code": "DRV-PRK", "name": "Soste parcheggio", "type": DriverType.VOLUME, "unit": "soste"},
    {"code": "DRV-TRX", "name": "Transazioni", "type": DriverType.VOLUME, "unit": "transazioni"},
]


async def seed(db: AsyncSession):
    logger.info("Avvio seed database...")

    # ── Ottieni o crea Hotel di default ─────────────────────────────────────
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
        logger.info(f"Creato Hotel Demo: {hotel.id}")
    else:
        logger.info(f"Hotel Demo esistente: {hotel.id}")

    # ── Utente admin ──────────────────────────────────────────────────────
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    for user_data in [
        {"email": "admin@hotel-abc.it", "name": "Amministratore Sistema", "role": UserRole.ADMIN, "pass": "HotelABC2025!"},
        {"email": "direzione@hotel-abc.it", "name": "Direttore Generale", "role": UserRole.DIRECTOR, "pass": "Direzione2025!"}
    ]:
        res = await db.execute(select(User).where(User.email == user_data["email"]))
        if not res.scalar_one_or_none():
            u = User(
                email=user_data["email"],
                full_name=user_data["name"],
                hashed_password=pwd.hash(user_data["pass"]),
                role=user_data["role"],
                hotel_id=hotel.id,
            )
            db.add(u)
            logger.info(f"Creato utente: {user_data['email']}")
        else:
            logger.info(f"Utente già esistente: {user_data['email']}")
    pass

    # ── Centri di costo ───────────────────────────────────────────────────
    cc_map = {}
    for cc_data in COST_CENTERS:
        res = await db.execute(select(CostCenter).where(CostCenter.code == cc_data["code"], CostCenter.hotel_id == hotel.id))
        cc = res.scalar_one_or_none()
        if not cc:
            cc = CostCenter(
                hotel_id=hotel.id,
                code=cc_data["code"],
                name=cc_data["name"],
                department=cc_data["department"],
            )
            db.add(cc)
            await db.flush()
            logger.info(f"Creato centro di costo: {cc_data['code']}")
        cc_map[cc_data["code"]] = cc

    # ── Attività ──────────────────────────────────────────────────────────
    act_map = {}
    for act_data in ACTIVITIES:
        res = await db.execute(select(Activity).where(Activity.code == act_data["code"], Activity.hotel_id == hotel.id))
        act = res.scalar_one_or_none()
        if not act:
            act = Activity(
                hotel_id=hotel.id,
                code=act_data["code"],
                name=act_data["name"],
                department=act_data["department"],
                cost_center_id=cc_map[act_data["cc"]].id,
                is_support_activity=act_data.get("is_support", False),
            )
            db.add(act)
            await db.flush()
            logger.info(f"Creata attività: {act_data['code']}")
        act_map[act_data["code"]] = act

    # ── Servizi ───────────────────────────────────────────────────────────
    svc_map = {}
    for svc_data in SERVICES:
        res = await db.execute(select(Service).where(Service.code == svc_data["code"], Service.hotel_id == hotel.id))
        svc = res.scalar_one_or_none()
        if not svc:
            svc = Service(
                hotel_id=hotel.id,
                code=svc_data["code"],
                name=svc_data["name"],
                service_type=svc_data["type"],
                output_unit=svc_data["unit"],
            )
            db.add(svc)
            await db.flush()
            logger.info(f"Creato servizio: {svc_data['code']}")
        svc_map[svc_data["code"]] = svc

    # ── Driver ────────────────────────────────────────────────────────────
    drv_map = {}
    for drv_data in DRIVERS:
        res = await db.execute(select(CostDriver).where(CostDriver.code == drv_data["code"], CostDriver.hotel_id == hotel.id))
        drv = res.scalar_one_or_none()
        if not drv:
            drv = CostDriver(
                hotel_id=hotel.id,
                code=drv_data["code"],
                name=drv_data["name"],
                driver_type=drv_data["type"],
                unit=drv_data["unit"],
            )
            db.add(drv)
            await db.flush()
            logger.info(f"Creato driver: {drv_data['code']}")
        drv_map[drv_data["code"]] = drv

    # ── Regole di allocazione esempio ────────────────────────────────────
    # Reception → Pernottamento 70%, Colazione 15%, Congressi 15%
    for act_code, svc_code, pct in [
        ("REC-001", "SVC-PNT", Decimal("0.70")),
        ("REC-001", "SVC-COL", Decimal("0.15")),
        ("REC-001", "SVC-CON", Decimal("0.15")),
        ("REC-002", "SVC-PNT", Decimal("0.60")),
        ("REC-002", "SVC-CON", Decimal("0.40")),
        ("HSK-001", "SVC-PNT", Decimal("1.00")),
        ("HSK-002", "SVC-PNT", Decimal("1.00")),
        ("HSK-003", "SVC-PNT", Decimal("0.50")),
        ("HSK-003", "SVC-CON", Decimal("0.50")),
        ("FNB-001", "SVC-COL", Decimal("1.00")),
        ("FNB-002", "SVC-RST", Decimal("1.00")),
        ("FNB-003", "SVC-BAR", Decimal("1.00")),
        ("FNB-005", "SVC-CON", Decimal("1.00")),
        ("CON-001", "SVC-CON", Decimal("1.00")),
        ("CON-002", "SVC-CON", Decimal("1.00")),
        ("MNT-001", "SVC-PNT", Decimal("1.00")),
        ("MNT-003", "SVC-PRK", Decimal("1.00")),
        ("COM-001", "SVC-PNT", Decimal("0.60")),
        ("COM-001", "SVC-CON", Decimal("0.40")),
        ("COM-002", "SVC-PNT", Decimal("1.00")),
    ]:
        # Controlla se regola esiste già per questo hotel
        existing_rule = await db.execute(select(AllocationRule).where(
            AllocationRule.hotel_id == hotel.id,
            AllocationRule.source_activity_id == act_map[act_code].id,
            AllocationRule.target_service_id == svc_map[svc_code].id
        ))
        if not existing_rule.scalar_one_or_none():
            rule = AllocationRule(
                hotel_id=hotel.id,
                name=f"{act_code} → {svc_code} ({int(pct*100)}%)",
                level=AllocationLevel.ACTIVITY_TO_SERVICE,
                source_activity_id=act_map[act_code].id,
                target_service_id=svc_map[svc_code].id,
                allocation_pct=pct,
                priority=1,
                is_active=True,
            )
            db.add(rule)

    await db.commit()
    logger.info("✅ Seed completato: %d attività, %d servizi, %d driver",
                len(ACTIVITIES), len(SERVICES), len(DRIVERS))


async def main():
    logging.basicConfig(level=logging.INFO)
    await create_tables()
    async with AsyncSessionFactory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
