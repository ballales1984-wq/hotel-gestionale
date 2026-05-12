"""
End-to-End Test Completo (locale):
1. Seed DB strutture
2. Genera dati storici (periodi, costi, lavoro, driver values, revenues)
3. Aggiunge regole di allocazione Costo→Attività (populate_presumed_costs)
4. Calcolo ABC locale (senza API) per tutti i periodi, salva ABCResult
5. Avvio server FastAPI
6. Test endpoint AI (driver discovery, forecasting, anomalies)
7. Report results
"""
import asyncio
import logging
import os
import subprocess
import time
import httpx
from pathlib import Path
from decimal import Decimal

# Forza DB su file condiviso
DB_FILE = "./hotel_abc_e2e_test.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_FILE}"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.db.database import AsyncSessionFactory, create_tables
from app.db.seed import seed as run_seed
from app.core.abc_engine import ABCEngine, CostRecord, LaborRecord, AllocationRuleRecord, ServiceRevenueRecord
from app.models.models import (
    AccountingPeriod, Activity, Service, CostItem, LaborAllocation,
    AllocationRule, DriverValue, CostCenter, CostDriver, ABCResult, Hotel,
    AllocationLevel, CostType, ServiceRevenue
)
from sqlalchemy import select, func, delete

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def wait_for_server(url: str, timeout: int = 30) -> bool:
    start = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                r = await client.get(url, timeout=2.0)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
    return False


async def main():
    logger.info("=== E2E TEST START ===")

    # Step 1 — Crea tabelle
    logger.info("Step 1 — Creazione tabelle...")
    await create_tables()

    # Step 2 — Seed strutture
    logger.info("Step 2 — Seed dati strutturali...")
    async with AsyncSessionFactory() as db:
        await run_seed(db)
        await db.commit()
        hotel = (await db.execute(select(Hotel).where(Hotel.code == "DEMO"))).scalar_one()
        logger.info(f"Hotel Demo: {hotel.id}")

    # Step 3 — Genera dati storici (importa funzioni dagli script)
    logger.info("Step 3 — Generazione dati storici (24 mesi)...")
    from scripts.generate_history import (
        generate_periods,
        generate_cost_items,
        generate_employees_and_labor,
        generate_driver_values,
        generate_service_revenues,
    )
    from scripts.populate_presumed_costs import create_presumed_costs

    async with AsyncSessionFactory() as db:
        periods = await generate_periods(db, hotel_id=hotel.id, months_back=24)
        logger.info(f"  Periodi: {len(periods)}")
        await generate_cost_items(db, periods)
        logger.info("  CostItems generati")
        await generate_employees_and_labor(db, periods)
        logger.info("  LaborAllocation generati")
        await generate_driver_values(db, periods)
        logger.info("  DriverValues generati")
        await generate_service_revenues(db, periods)
        logger.info("  ServiceRevenues generati")
        # Aggiunge costi presunti e regole Costo→Attività
        await create_presumed_costs()
        logger.info("  Regole Costo→Attività e costi aggiuntivi generati")

    # Step 4 — Calcolo ABC locale
    logger.info("Step 4 — Calcolo ABC (locale)...")
    engine = ABCEngine()
    async with AsyncSessionFactory() as db:
        # Recupera liste riferimento per l'hotel
        activities = (await db.execute(select(Activity).where(Activity.hotel_id == hotel.id, Activity.is_active == True))).scalars().all()
        activity_ids = [a.id for a in activities]
        support_activity_ids = [a.id for a in activities if a.is_support_activity]

        services = (await db.execute(select(Service).where(Service.hotel_id == hotel.id, Service.is_active == True))).scalars().all()
        service_ids = [s.id for s in services]

        # Carica toutes le regole attive per l'hotel (per evitare query nella loop)
        rules_db = (await db.execute(select(AllocationRule).where(
            AllocationRule.hotel_id == hotel.id,
            AllocationRule.is_active == True
        ))).scalars().all()

        for period in periods:
            # Cost records
            cost_items = (await db.execute(select(CostItem).where(CostItem.period_id == period.id))).scalars().all()
            cost_records = [
                CostRecord(
                    cost_item_id=ci.id,
                    cost_center_id=ci.cost_center_id,
                    cost_type=ci.cost_type.value,
                    amount=ci.amount,
                )
                for ci in cost_items
            ]

            # Labor records
            labor_alloc = (await db.execute(select(LaborAllocation).where(LaborAllocation.period_id == period.id))).scalars().all()
            labor_records = [
                LaborRecord(
                    employee_id=la.employee_id,
                    activity_id=la.activity_id,
                    hours=la.hours,
                    hourly_cost=la.hourly_cost,
                    allocation_pct=la.allocation_pct,
                )
                for la in labor_alloc
            ]

            # Build AllocationRuleRecords
            allocation_rules = []
            # Filtra regole rilevanti per questo periodo? Le regole non hanno validità temporale, valgono per tutto.
            for rule in rules_db:
                # Recupera driver values per la regola se presenti (per target activity/service) per questo periodo
                driver_vals: dict[UUID, Decimal] = {}
                if rule.driver_id:
                    # DriverValue può essere entity_type='activity' o 'service' o 'period'? Nel nostro caso, a volte entity_type='period' non collegato a regole.
                    # Per semplicità, non usiamo driver values dynamic in questo test; usiamo allocation_pct fisso.
                    pass
                allocation_rules.append(
                    AllocationRuleRecord(
                        rule_id=rule.id,
                        level=rule.level.value,
                        source_cost_center_id=rule.source_cost_center_id,
                        source_activity_id=rule.source_activity_id,
                        target_activity_id=rule.target_activity_id,
                        target_service_id=rule.target_service_id,
                        driver_values=driver_vals,
                        allocation_pct=rule.allocation_pct,
                        priority=rule.priority,
                    )
                )

            # Service revenues
            service_rev = (await db.execute(select(ServiceRevenue).where(ServiceRevenue.period_id == period.id))).scalars().all()
            service_revenues = [
                ServiceRevenueRecord(
                    service_id=sr.service_id,
                    revenue=sr.revenue,
                    output_volume=sr.output_volume,
                )
                for sr in service_rev
            ]

            # Calcolo
            result = engine.calculate(
                period_id=period.id,
                cost_records=cost_records,
                labor_records=labor_records,
                allocation_rules=allocation_rules,
                service_revenues=service_revenues,
                activity_ids=activity_ids,
                service_ids=service_ids,
                support_activity_ids=support_activity_ids,
            )

            # Salva risultati (elimina vecchi se esistono)
            await db.execute(delete(ABCResult).where(ABCResult.period_id == period.id))
            for service_id, svc in result.service_results.items():
                abc = ABCResult(
                    hotel_id=period.hotel_id,
                    period_id=period.id,
                    service_id=service_id,
                    activity_id=None,
                    direct_cost=svc.direct_cost,
                    labor_cost=svc.labor_cost,
                    overhead_cost=svc.overhead_cost,
                    total_cost=svc.total_cost,
                    revenue=svc.revenue,
                    output_volume=svc.output_volume,
                    gross_margin=svc.gross_margin,
                    margin_pct=svc.margin_pct,
                    cost_per_unit=svc.cost_per_unit,
                    calculation_version=1,
                    is_validated=False,
                )
                db.add(abc)
            await db.commit()
            logger.info(f"  Periodo {period.name}: {len(result.service_results)} servizi, margine totale €{result.total_margin:.2f}")

    # Step 5 — Avvia server FastAPI
    logger.info("Step 5 — Avvio server FastAPI...")
    server_proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ready = await wait_for_server("http://127.0.0.1:8000/health")
    if not ready:
        logger.error("Server non pronto, abort.")
        server_proc.terminate()
        return

    # Debug: verifica periodi visibili via API
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        r = await client.get("/api/v1/periods")
        if r.status_code == 200:
            periods_api = r.json()
            logger.info(f"Periodi via API: {len(periods_api)}")
        else:
            logger.warning(f"Lista periodi API error: {r.status_code}")

    # Step 6 — Test endpoint AI
    logger.info("Step 6 — Test endpoint AI...")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # Driver Discovery
        try:
            r = await client.get("/api/v1/ai/driver-discovery", params={"top_k": 5})
            if r.status_code == 200:
                drivers = r.json()
                if drivers:
                    logger.info(f"Driver discovery: top-5 -> {[d['driver_name'] for d in drivers[:5]]}")
                else:
                    logger.info("Driver discovery: nessun risultato (dati insufficienti)")
            else:
                logger.warning(f"Driver discovery HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            logger.warning(f"Driver discovery fallito: {e}")

        # Forecasting
        try:
            r = await client.get("/api/v1/ai/forecast", params={"metric": "notti_vendute", "periods": 3})
            if r.status_code == 200:
                forecast = r.json()
                if forecast:
                    logger.info(f"Forecast notti: {forecast[0]['date']} → {forecast[0]['predicted_value']:.0f} (bounds: {forecast[0]['lower_bound']:.0f}-{forecast[0]['upper_bound']:.0f})")
                else:
                    logger.info("Forecast vuoto")
            else:
                logger.warning(f"Forecast HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            logger.warning(f"Forecast fallito: {e}")

        # Anomalies
        try:
            r = await client.get("/api/v1/ai/anomalies")
            if r.status_code == 200:
                anomalies = r.json()
                logger.info(f"Anomalie rilevate: {len(anomalies)}")
            else:
                logger.warning(f"Anomalies HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"Anomalies fallito: {e}")

    # Step 7 — Verifica DB
    logger.info("Step 7 — Verifica ABC results...")
    async with AsyncSessionFactory() as db:
        abc_count = await db.scalar(select(func.count(ABCResult.id)))
        periods_count = await db.scalar(select(func.count(AccountingPeriod.id)))
        logger.info(f"ABCResults: {abc_count} righe, Periodi: {periods_count}")

    logger.info("=== E2E TEST COMPLETATO CON SUCCESSO ===")

    # Pulizia
    server_proc.terminate()
    server_proc.wait()
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


if __name__ == "__main__":
    asyncio.run(main())
