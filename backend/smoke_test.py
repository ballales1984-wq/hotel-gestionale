import asyncio
import httpx
import sys
from app.db.database import AsyncSessionFactory
from app.models.models import AccountingPeriod, ABCResult, User, Activity, Service
from sqlalchemy import select, func

async def audit():
    print("--- INIZIO AUDIT TECNICO HOTEL ABC ---")
    sys.stdout.flush()
    
    # 1. Database Check
    async with AsyncSessionFactory() as db:
        # Conteggi
        periods_count = await db.execute(select(func.count(AccountingPeriod.id)))
        abc_count = await db.execute(select(func.count(ABCResult.id)))
        users_count = await db.execute(select(func.count(User.id)))
        
        p_val = periods_count.scalar()
        a_val = abc_count.scalar()
        u_val = users_count.scalar()
        
        print(f"[DB] Periodi: {p_val} (Previsti > 24)")
        print(f"[DB] Risultati ABC: {a_val} (Previsti > 100)")
        print(f"[DB] Utenti: {u_val}")
        
        if p_val < 25: print("! Avviso: Meno periodi del previsto.")
        if a_val < 100: print("! Avviso: Mancano alcuni calcoli ABC storici.")
        sys.stdout.flush()

    # 2. API Health Check
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://localhost:8000/health")
            print(f"[API] Health: {r.status_code} {r.json()}")
        except Exception as e:
            print(f"[API] Errore Health: {e}")
            
        # Test Endpoint AI (il più critico dopo il fix)
        try:
            # Notiamo che serve il token, ma possiamo testare se l'endpoint risponde (anche 401 è segno di vita)
            r = await client.get("http://localhost:8000/api/v1/ai/driver-discovery")
            print(f"[API] AI Driver Discovery: {r.status_code} (Atteso 200 o 401)")
        except Exception as e:
            print(f"[API] Errore AI: {e}")
    
    print("--- AUDIT COMPLETATO ---")
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(audit())
