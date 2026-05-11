import asyncio
from decimal import Decimal
import uuid
from app.db.database import AsyncSessionFactory
from app.models.models import (
    AccountingPeriod, CostCenter, CostItem, CostType, 
    Activity, AllocationRule, AllocationLevel
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
        cc_res = await db.execute(select(CostCenter))
        ccs = {c.code: c for c in cc_res.scalars().all()}
        
        if not ccs:
            print("[ERR] Nessun centro di costo trovato. Eseguire prima il seed.")
            return

        # 3. Definisci Costi Presunti
        presumed_costs = [
            # Camere
            ("CC-ROOMS", "Lavanderia e biancheria", CostType.DIRECT, 2500.00),
            ("CC-ROOMS", "Set cortesia e cleaning supplies", CostType.DIRECT, 800.00),
            # Ristorante
            ("CC-REST", "Materie prime alimentari", CostType.DIRECT, 4500.00),
            ("CC-REST", "Bevande e cantina", CostType.DIRECT, 1200.00),
            # SPA
            ("CC-SPA", "Prodotti trattamenti e oli", CostType.DIRECT, 600.00),
            # Struttura / Generale
            ("CC-ADMIN", "Energia elettrica", CostType.UTILITIES, 3500.00),
            ("CC-ADMIN", "Acqua e Riscaldamento", CostType.UTILITIES, 1500.00),
            ("CC-ADMIN", "Manutenzione ordinaria", CostType.OVERHEAD, 2000.00),
            ("CC-ADMIN", "Marketing e OTA fees", CostType.DIRECT, 5000.00),
            ("CC-ADMIN", "Ammortamenti immobili e arredi", CostType.DEPRECIATION, 8000.00),
        ]

        # Inserimento CostItems
        for cc_code, name, c_type, amount in presumed_costs:
            cc = ccs.get(cc_code)
            if not cc: continue
            
            cost = CostItem(
                period_id=period.id,
                cost_center_id=cc.id,
                account_name=name,
                cost_type=c_type,
                amount=Decimal(str(amount)),
                source_system="presumed_data"
            )
            db.add(cost)

        # 4. Creazione Regole di Allocazione (Costo -> Attività) se mancano
        # Per semplicità, ogni CC ribalta su un'attività specifica o su un gruppo
        act_res = await db.execute(select(Activity))
        activities = {a.code: a for a in act_res.scalars().all()}
        
        rules_check = await db.execute(select(AllocationRule).where(AllocationRule.level == AllocationLevel.COST_TO_ACTIVITY))
        if not rules_check.scalars().first():
            print("[INFO] Creazione regole di allocazione Costo -> Attivita'...")
            
            # Mappa CC -> Attività prevalente
            cc_to_act = [
                ("CC-ROOMS", "HKP-001", Decimal("1.00")), # 100% costi rooms al Housekeeping
                ("CC-REST", "FB-001", Decimal("1.00")),   # 100% costi rest al Servizio F&B
                ("CC-SPA", "SPA-001", Decimal("1.00")),    # 100% costi spa ai trattamenti
                ("CC-ADMIN", "ADM-001", Decimal("0.50")),  # 50% admin a contabilità
                ("CC-ADMIN", "ADM-003", Decimal("0.50")),  # 50% admin a IT/Sistemi
            ]
            
            for cc_code, act_code, pct in cc_to_act:
                cc = ccs.get(cc_code)
                act = activities.get(act_code)
                if cc and act:
                    rule = AllocationRule(
                        name=f"Allocazione {cc.name} -> {act.name}",
                        level=AllocationLevel.COST_TO_ACTIVITY,
                        source_cost_center_id=cc.id,
                        target_activity_id=act.id,
                        allocation_pct=pct,
                        is_active=True,
                        priority=10
                    )
                    db.add(rule)

        await db.commit()
        print("--- Costi presunti e regole di base creati! ---")

if __name__ == "__main__":
    asyncio.run(create_presumed_costs())
