import asyncio
from decimal import Decimal
import uuid
from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, CostCenter, CostItem, CostType, 
    Activity, AllocationRule, AllocationLevel, Hotel
)
from sqlalchemy import select

async def create_presumed_costs():
    async with AsyncSessionFactory() as db:
        # 1. Trova ultimo periodo
        p_res = await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()))
        period = p_res.scalars().first()
        if not period:
            print("[ERR] Nessun periodo trovato. Creane uno prima.")
            return
        
        print(f"[INFO] Popolamento costi per: {period.name}")

        # 2. Carica Centri di Costo
        cc_res = await db.execute(select(CostCenter).where(CostCenter.hotel_id == period.hotel_id))
        ccs = {c.code: c for c in cc_res.scalars().all()}
        
        if not ccs:
            print("[ERR] Nessun centro di costo trovato. Eseguire prima il seed.")
            return

        # 3. Definisci Costi Presunti (adattati ai CDC esistenti)
        presumed_costs = [
            # Housekeeping (pulizie camere) – CC-HSK
            ("CC-HSK", "Lavanderia e biancheria", CostType.DIRECT, 2500.00),
            ("CC-HSK", "Set cortesia e cleaning supplies", CostType.DIRECT, 800.00),
            # Food & Beverage – CC-FNB
            ("CC-FNB", "Materie prime alimentari", CostType.DIRECT, 4500.00),
            ("CC-FNB", "Bevande e cantina", CostType.DIRECT, 1200.00),
            # Manutenzione – CC-MNT
            ("CC-MNT", "Manutenzione ordinaria", CostType.OVERHEAD, 2000.00),
            # Amministrazione / Struttura – CC-ADM
            ("CC-ADM", "Energia elettrica", CostType.UTILITIES, 3500.00),
            ("CC-ADM", "Acqua e Riscaldamento", CostType.UTILITIES, 1500.00),
            ("CC-ADM", "Marketing e OTA fees", CostType.DIRECT, 5000.00),
            ("CC-ADM", "Ammortamenti immobili e arredi", CostType.DEPRECIATION, 8000.00),
            # Reception – CC-REC
            ("CC-REC", "Materiale ufficio reception", CostType.DIRECT, 300.00),
            # Congressi – CC-CON
            ("CC-CON", "Allestimento eventi", CostType.DIRECT, 1200.00),
        ]

        # Inserimento CostItems
        for cc_code, name, c_type, amount in presumed_costs:
            cc = ccs.get(cc_code)
            if not cc: 
                print(f"[WARN] CDC {cc_code} non trovato, skip.")
                continue
            
            cost = CostItem(
                period_id=period.id,
                hotel_id=period.hotel_id,
                cost_center_id=cc.id,
                account_name=name,
                cost_type=c_type,
                amount=Decimal(str(amount)),
                source_system="presumed_data"
            )
            db.add(cost)

        # 4. Creazione Regole di Allocazione (Costo -> Attività) se mancano
        act_res = await db.execute(select(Activity).where(Activity.hotel_id == period.hotel_id))
        activities = {a.code: a for a in act_res.scalars().all()}
        
        rules_check = await db.execute(select(AllocationRule).where(
            AllocationRule.hotel_id == period.hotel_id,
            AllocationRule.level == AllocationLevel.COST_TO_ACTIVITY
        ))
        if not rules_check.scalars().first():
            print("[INFO] Creazione regole di allocazione Costo -> Attivita'...")
            
            # Mappa CDC -> Attività prevista (usando codici esistenti)
            cc_to_act = [
                ("CC-HSK", "HSK-001", Decimal("0.60")),   # 60% pulizia camere check-out
                ("CC-HSK", "HSK-002", Decimal("0.40")),   # 40% pulizia stayover
                ("CC-FNB", "FNB-001", Decimal("0.40")),   # colazione
                ("CC-FNB", "FNB-002", Decimal("0.60")),   # ristorazione
                ("CC-MNT", "MNT-001", Decimal("0.70")),   # manutenzione camere
                ("CC-MNT", "MNT-002", Decimal("0.30")),   # manutenzione impianti
                ("CC-ADM", "ADM-001", Decimal("0.60")),   # amministrazione/contabilità
                ("CC-ADM", "ADM-002", Decimal("0.40")),   # HR
                ("CC-REC", "REC-001", Decimal("0.80")),   # check-in/out
                ("CC-REC", "REC-002", Decimal("0.20")),   # gestione prenotazioni
                ("CC-CON", "CON-001", Decimal("0.50")),   # setup eventi
                ("CC-CON", "CON-002", Decimal("0.50")),   # gestione evento
            ]
            
            for cc_code, act_code, pct in cc_to_act:
                cc = ccs.get(cc_code)
                act = activities.get(act_code)
                if cc and act:
                    rule = AllocationRule(
                        hotel_id=period.hotel_id,
                        name=f"Allocazione {cc.name} -> {act.name} ({int(pct*100)}%)",
                        level=AllocationLevel.COST_TO_ACTIVITY,
                        source_cost_center_id=cc.id,
                        target_activity_id=act.id,
                        allocation_pct=pct,
                        is_active=True,
                        priority=10
                    )
                    db.add(rule)

        await db.commit()
        print("[OK] Costi presunti e regole di base creati per %s" % period.name)

if __name__ == "__main__":
    asyncio.run(create_presumed_costs())
