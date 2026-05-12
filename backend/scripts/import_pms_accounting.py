#!/usr/bin/env python
"""
Import dati contabili da file CSV esportato da PMS esterno.
Utilizza le mapping rules configurate per associare i codici esterni ai centri di costo interni.
"""
import asyncio
import logging
import os
import sys
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # aggiunge backend/ a path

from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import (
    AccountingPeriod, CostCenter, MappingRule, MappingType,
    CostItem, CostType, Hotel
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Path del file CSV di esempio (nella directory backend/)
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), "accounting_sample.csv")


def _map_cost_type(raw: str) -> CostType:
    raw_lower = raw.lower()
    if any(k in raw_lower for k in ["personale", "labor", "stipendi"]):
        return CostType.LABOR
    if any(k in raw_lower for k in ["diretto", "direct", "materie prime"]):
        return CostType.DIRECT
    if any(k in raw_lower for k in ["struttura", "overhead", "fisso"]):
        return CostType.OVERHEAD
    if any(k in raw_lower for k in ["ammortamento", "depreciation"]):
        return CostType.DEPRECIATION
    if any(k in raw_lower for k in ["utilities", "energia"]):
        return CostType.UTILITIES
    return CostType.OTHER


async def main(csv_path: str | None = None, hotel_code: str = "DEMO"):
    csv_file = csv_path or DEFAULT_CSV_PATH
    if not os.path.exists(csv_file):
        logger.error(f"File non trovato: {csv_file}")
        sys.exit(1)

    await create_tables()
    async with AsyncSessionFactory() as db:
        # Recupera hotel
        hotel = (await db.execute(select(Hotel).where(Hotel.code == hotel_code))).scalar_one_or_none()
        if not hotel:
            logger.error(f"Hotel '{hotel_code}' non trovato")
            return
        logger.info(f"Hotel: {hotel.id} ({hotel.code})")

        # Periodo corrente (mese in corso)
        today = date.today()
        period = (await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.hotel_id == hotel.id,
                AccountingPeriod.year == today.year,
                AccountingPeriod.month == today.month
            ))).scalar_one_or_none()
        if not period:
            period = AccountingPeriod(
                hotel_id=hotel.id,
                name=f"{today.month:02d}/{today.year}",
                year=today.year,
                month=today.month,
                is_closed=False,
            )
            db.add(period)
            await db.flush()
            logger.info(f"Creato periodo {period.name}")
        else:
            logger.info(f"Periodo esistente: {period.name}")

        # Mappa cost center per codice interno
        cc_list = (await db.execute(select(CostCenter).where(CostCenter.hotel_id == hotel.id))).scalars().all()
        cc_map = {cc.code.upper(): cc.id for cc in cc_list}

        # Mapping rules esterne → CDC
        rules = (await db.execute(select(MappingRule).where(
            MappingRule.hotel_id == hotel.id,
            MappingRule.mapping_type == MappingType.COST_CENTER,
            MappingRule.is_active == True
        ))).scalars().all()
        rule_map = {rule.external_code.upper(): rule.target_cost_center_id for rule in rules}

        # Leggi CSV
        df = pd.read_csv(csv_file, sep=None, engine="python", decimal=",")
        logger.info(f"Lette {len(df)} righe da {csv_file}")

        imported = 0
        skipped = 0
        for idx, row in df.iterrows():
            try:
                # Colonne attese: 'conto', 'descrizione', 'centro_di_costo', 'tipo_costo', 'importo'
                cc_raw = str(row.get("centro_di_costo", "") or "").strip()
                cc_id = cc_map.get(cc_raw.upper()) or rule_map.get(cc_raw.upper())
                if not cc_id:
                    logger.warning(f"Riga {idx+2}: centro di costo '{cc_raw}' non mappato – saltata")
                    skipped += 1
                    continue

                amount = Decimal(str(row.get("importo", 0) or 0))
                if amount <= 0:
                    skipped += 1
                    continue

                cost_type = _map_cost_type(str(row.get("tipo_costo", "altro")))
                account_code = str(row.get("conto", ""))[:20]
                account_name = str(row.get("descrizione", ""))[:200]

                item = CostItem(
                    hotel_id=hotel.id,
                    period_id=period.id,
                    cost_center_id=cc_id,
                    account_code=account_code,
                    account_name=account_name,
                    cost_type=cost_type,
                    amount=amount,
                    source_system="pms_import_csv",
                )
                db.add(item)
                imported += 1
            except Exception as e:
                logger.error(f"Errore riga {idx+2}: {e}")
                skipped += 1

        await db.commit()
        logger.info(f"Import completato: {imported} righe importate, {skipped} saltate")

        # Statistics
        count = await db.scalar(select(func.count(CostItem.id)).where(CostItem.period_id == period.id))
        logger.info(f"Total CostItem nel periodo: {count}")


if __name__ == "__main__":
    from sqlalchemy import func
    asyncio.run(main())
