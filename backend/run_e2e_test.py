"""
End-to-End Test: Seed → Storia → Calcolo ABC → AI Forecast
Esegue tutto in memoria (SQLite) per isolamento.
"""
import asyncio
import logging
import os

# Forza DB in memoria per test isolato
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import Hotel
from app.db.seed import seed
from app.core.ai.forecasting import ForecastEngine
from app.core.ai.anomaly_detection import AnomalyDetectionEngine
from app.core.ai.driver_discovery import DriverDiscoveryEngine
from scripts.generate_history import generate_periods, run_abc_calculations
import polars as pl

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


async def main():
    logger.info("=== E2E TEST START ===")

    # 1. Crea tabelle
    logger.info("Step 1 — Creazione tabelle...")
    await create_tables()

    # 2. Seed dati (Hotel, CC, Attività, Servizi, Driver, Regole)
    logger.info("Step 2 — Seed dati...")
    async with AsyncSessionFactory() as db:
        await seed(db)
        await db.commit()
        from sqlalchemy import select
        hotel = (await db.execute(select(Hotel).where(Hotel.code == "DEMO"))).scalar_one()
        logger.info(f"Hotel seed: {hotel.id} ({hotel.code})")

    # 3. Genera periodi storici (24 mesi)
    logger.info("Step 3 — Generazione periodi storici...")
    async with AsyncSessionFactory() as db:
        periods = await generate_periods(db, hotel_id=hotel.id, months_back=24)
        logger.info(f"Periodi generati: {len(periods)}")

    # 4. Esegui calcolo ABC su tutti i periodi
    logger.info("Step 4 — Calcolo ABC...")
    async with AsyncSessionFactory() as db:
        results = await run_abc_calculations(db, periods)
        logger.info(f"Risultati ABC: {len(results)} periodi calcolati")
        for r in results[-3:]:
            logger.info(f"  Periodo {r['period']} — {r['services_calculated']} servizi, unallocated: €{r.get('unallocated', 0):.2f}")

    # 5. Forecasting (Prophet) su ServiceRevenue esistente
    logger.info("Step 5 — Forecasting AI (Prophet)...")
    forecast_engine = ForecastEngine()
    async with AsyncSessionFactory() as db:
        from sqlalchemy import select
        from app.models.models import ServiceRevenue, Service

        svc_res = await db.execute(select(Service).where(Service.code == "SVC-PNT"))
        pernotto = svc_res.scalar_one_or_none()
        if pernotto:
            revs = (await db.execute(select(ServiceRevenue).where(ServiceRevenue.service_id == pernotto.id).order_by(ServiceRevenue.created_at))).scalars().all()
            if revs:
                import pandas as pd
                from datetime import date
                df = pd.DataFrame([
                    {"ds": date(r.created_at.year, r.created_at.month, 1), "y": float(r.output_volume or 0)}
                    for r in revs
                ])
                forecast = forecast_engine.forecast_metric(df, "ds", "y", periods=3, freq='ME')
                logger.info(f"Forecast: {len(forecast)} valori previsti")
                if forecast:
                    logger.info(f"  Prossimo: {forecast[0]['date']} → {forecast[0]['predicted_value']:.0f} unità (bounds: {forecast[0]['lower_bound']:.0f} - {forecast[0]['upper_bound']:.0f})")
            else:
                logger.warning("Nessun ServiceRevenue per SVC-PNT")
        else:
            logger.warning("Servizio SVC-PNT non trovato")

    # 6. Driver Discovery (LightGBM + SHAP)
    logger.info("Step 6 — Driver Discovery AI...")
    driver_engine = DriverDiscoveryEngine()
    async with AsyncSessionFactory() as db:
        from sqlalchemy import select
        from app.models.models import DriverValue, Activity, CostItem, AccountingPeriod
        import pandas as pd

        last_period = (await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()).limit(1))).scalar_one()
        driver_vals = (await db.execute(select(DriverValue).where(DriverValue.period_id == last_period.id))).scalars().all()

        if driver_vals:
            dv_map = {}
            for dv in driver_vals:
                key = (dv.entity_type, dv.entity_id)
                dv_map.setdefault(key, {})[dv.driver_id] = float(dv.value)

            activities = (await db.execute(select(Activity))).scalars().all()
            rows = []
            for act in activities:
                key = ('activity', act.id)
                if key in dv_map:
                    # Overhead cost: sum di costi indiretti nel periodo per l'attività (tramite centro di costo)
                    overhead_items = (await db.execute(select(CostItem).where(CostItem.cost_center_id == act.cost_center_id, CostItem.period_id == last_period.id, CostItem.cost_type.in_(["struttura", "utilities", "altro"])))).scalars().all()
                    overhead = sum(float(i.amount) for i in overhead_items)
                    row = {"activity_id": str(act.id), "overhead": overhead}
                    row.update({f"drv_{str(k)}": v for k, v in dv_map[key].items()})
                    rows.append(row)

            if rows:
                df = pd.DataFrame(rows)
                feature_cols = [c for c in df.columns if c.startswith("drv_")]
                if feature_cols:
                    importance = driver_engine.discover_drivers(df, feature_cols, "overhead")
                    logger.info(f"Driver discovery: top 5 -> {importance[:5]}")
            else:
                logger.warning("Nessuna riga di dati per driver discovery")
        else:
            logger.warning("Nessun driver value per periodo corrente")

    # 7. Anomaly Detection
    logger.info("Step 7 — Anomaly Detection AI...")
    anomaly_engine = AnomalyDetectionEngine()
    async with AsyncSessionFactory() as db:
        from sqlalchemy import select
        from app.models.models import CostItem, AccountingPeriod, ServiceRevenue
        import pandas as pd

        last_period = (await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()).limit(1))).scalar_one()
        cost_items = (await db.execute(select(CostItem).where(CostItem.period_id == last_period.id))).scalars().all()
        revenues = (await db.execute(select(ServiceRevenue).where(ServiceRevenue.period_id == last_period.id))).scalars().all()

        if cost_items:
            df_cost = pd.DataFrame([
                {"cost_center_id": str(ci.cost_center_id), "amount": float(ci.amount), "type": ci.cost_type}
                for ci in cost_items
            ])
            volumes = {str(r.service_id): float(r.output_volume or 0) for r in revenues}
            anomalies = anomaly_engine.detect_anomalies(df_cost, volumes)
            logger.info(f"Anomalie rilevate: {len(anomalies)}")
            if anomalies:
                logger.info(f"  Primo: {anomalies[0]['explanation']}")
        else:
            logger.warning("Nessun CostItem per anomaly detection")

    logger.info("=== E2E TEST COMPLETATO CON SUCCESSO ===")


if __name__ == "__main__":
    asyncio.run(main())
