"""
Setup completo Hotel ABC Platform – dati e calcoli.

Esegue in ordine:
1. Migrazione multi-tenancy (schema hotels)
2. Seed dati master (CDC, attività, servizi, driver, regole base)
3. Popolazione storico contabile (12 mesi)
4. Aggiunta costi presunti e regole Costo→Attività per ultimo periodo
5. Generazione driver values per AI (notti, coperti, ore, camere)
6. Calcolo ABC per tutti i periodi

Uso: python -m scripts.setup_all
"""
import asyncio
import sys
from pathlib import Path

# Aggiunge backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionFactory, create_tables
from app.models.models import Hotel
from sqlalchemy import select

# Import script
from scripts.migrate_to_multitenancy import migrate
from app.db.seed import seed as seed_data
from scripts.populate_min_history import populate_minimal_history
from scripts.populate_presumed_costs import create_presumed_costs
from scripts.populate_driver_values import populate_driver_values as populate_driver_vals
from scripts.calculate_all_periods import calculate_all_periods

async def main():
    print("=" * 50)
    print("Hotel ABC Platform – Setup Completo")
    print("=" * 50)

    # 0. Crea tabelle (se non esistono)
    print("\n[1/6] Creazione tabelle DB...")
    await create_tables()
    print("      Tabelle create/verificate.")

    # 1. Migrazione multi-tenancy
    print("\n[2/6] Migrazione multi-tenancy...")
    await migrate()

    # 2. Seed dati master
    print("\n[3/6] Seed dati master (CDC, attività, servizi, driver, regole)...")
    async with AsyncSessionFactory() as db:
        await seed_data(db)

    # 3. Storico contabile (12 mesi)
    print("\n[4/6] Popolamento storico contabile (12 mesi)...")
    await populate_minimal_history()

    # 4. Costi presunti e regole Costo→Attività per ultimo periodo
    print("\n[5/6] Aggiunta costi presunti e regole base per ultimo periodo...")
    await create_presumed_costs()

    # 5. Ricalcolo ABC per includere nuovi costi
    print("\n[6/6] Ricalcolo ABC per tutti i periodi...")
    await calculate_all_periods()

    # 6. Driver values per AI
    print("\n[7/7] Generazione driver values per AI...")
    await populate_driver_vals()

    print("\n" + "=" * 50)
    print("✅ Setup completato con successo!")
    print("=" * 50)
    
    # Stampa riepilogo
    async with AsyncSessionFactory() as db:
        from app.models.models import AccountingPeriod, ABCResult, DriverValue
        from sqlalchemy import func
        p = await db.execute(select(func.count(AccountingPeriod.id)))
        a = await db.execute(select(func.count(ABCResult.id)))
        d = await db.execute(select(func.count(DriverValue.id)))
        print("   Periodi contabili: %d" % p.scalar())
        print("   Risultati ABC: %d" % a.scalar())
        print("   DriverValues (AI): %d" % d.scalar())
        
        # Hotel
        h = await db.execute(select(Hotel))
        hotels = h.scalars().all()
        print("   Hotel configurati: %d" % len(hotels))
        for hp in hotels:
            print(f"      - {hp.code}: {hp.name}")

if __name__ == "__main__":
    asyncio.run(main())
