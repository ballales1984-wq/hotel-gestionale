import asyncio
import uuid
from sqlalchemy import text
from app.db.database import AsyncSessionFactory, engine
from app.models.models import Base

async def migrate():
    print("--- Inizio Migrazione Multi-Tenancy ---")
    
    async with engine.begin() as conn:
        # 1. Creazione nuove tabelle (hotels, mapping_rules, data_import_logs)
        # Usiamo Base.metadata.create_all tramite un approccio asincrono
        await conn.run_sync(Base.metadata.create_all)
        print("Tabelle create/aggiornate.")

    async with AsyncSessionFactory() as db:
        # 2. Crea Hotel di default se non esiste
        hotel_id = uuid.uuid4()
        res = await db.execute(text("SELECT id FROM hotels WHERE code = 'DEMO'"))
        row = res.fetchone()
        if not row:
            await db.execute(text(
                "INSERT INTO hotels (id, name, code, is_active, created_at, updated_at) "
                "VALUES (:id, 'Hotel Demo', 'DEMO', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ), {"id": str(hotel_id)})
            print(f"Hotel Demo creato: {hotel_id}")
        else:
            hotel_id = row[0]
            print(f"Hotel Demo esistente: {hotel_id}")

        # 3. Aggiorna hotel_id su tutte le tabelle esistenti
        tables = [
            "users", "accounting_periods", "cost_centers", "activities", "services",
            "cost_drivers", "driver_values", "cost_items", "employees",
            "labor_allocations", "allocation_rules", "abc_results", "service_revenues"
        ]
        
        for table in tables:
            # SQLite: aggiungiamo la colonna se non esiste (create_all l'ha già fatto se non c'era)
            # Ma dobbiamo assicurarci che i dati esistenti abbiano l'hotel_id
            print(f"Aggiornamento tabella: {table}")
            await db.execute(text(f"UPDATE {table} SET hotel_id = :h_id WHERE hotel_id IS NULL"), {"h_id": str(hotel_id)})

        await db.commit()
    
    print("--- Migrazione Completata con Successo ---")

if __name__ == "__main__":
    asyncio.run(migrate())
