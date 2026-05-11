# Manutenzione e Troubleshooting

## Manutenzione periodica

### Backup database

```bash
# Backup completo
docker-compose exec postgres pg_dump -U hotel_user hotel_abc > backup_$(date +%Y%m%d).sql

# Backup solo dati (senza schema)
docker-compose exec postgres pg_dump -U hotel_user --data-only hotel_abc > data_backup_$(date +%Y%m%d).sql

# Ripristino
cat backup.sql | docker-compose exec -T postgres psql -U hotel_user hotel_abc
```

### Pulizia log

```bash
# Visualizza log recenti
docker-compose logs --tail=100 backend

# Pulisci log container
docker-compose exec backend sh -c 'truncate -s 0 /var/log/*.log'
```

### Aggiornamento dipendenze

```bash
# Backend
cd backend
pip-compile requirements.in -o requirements.txt

# Frontend
cd frontend
npm update
```

## Troubleshooting

### Container non si avvia

```bash
# Visualizza log di errore
docker-compose logs <service_name>

# Ricostruisci immagine
docker-compose build --no-cache <service_name>
docker-compose up -d <service_name>
```

### Problemi di connessione database

```bash
# Verifica connessione
docker-compose exec backend python -c "from app.db.database import async_session; print('OK')"

# Controlla healthcheck
docker-compose ps postgres

# Riavvia database
docker-compose restart postgres
```

### Errori di autenticazione

1. Verifica che `SECRET_KEY` sia impostato correttamente
2. Cancella cookie del browser
3. Rigenera token con login

### Performance lenta

```bash
# Controlla risorse sistema
docker stats

# Analizza query lente
docker-compose exec postgres psql -U hotel_user -c "
SELECT query, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;"
```

### Problemi di allocazione ABC

Segnali di warning:
- "Costo non allocato ai servizi" → Verifica regole di allocazione
- "Ribaltamento non converge" → Controlla presenza di cicli

## Log e debugging

### Livelli di log

| Livello | Quando usarlo |
|---------|---------------|
| DEBUG | Sviluppo |
| INFO | Produzione normale |
| WARNING | Attenzione richiesta |
| ERROR | Errore da risolvere |

### Abilita log debug

```bash
# Nel file .env
LOG_LEVEL=debug

# Riavvia backend
docker-compose restart backend
```

## Pulizia dati

### Rimuovi dati di test

```bash
# Nel container backend
docker-compose exec backend python -c "
from app.db.database import async_session
from app.models.models import *
from sqlalchemy import delete

async def cleanup():
    async with async_session() as session:
        await session.execute(delete(Period).where(Period.name.like('%TEST%')))
        await session.commit()
"
```

### Reset completo database

```bash
# ATTENZIONE: Cancella tutti i dati
docker-compose down -v
docker volume rm hotel-gestionale_postgres_data
docker-compose up -d
docker-compose exec backend python -m app.db.seed
```

## Aggiornamento applicazione

### Aggiornamento minor version

```bash
git pull origin main
docker-compose pull
docker-compose up -d
```

### Migration database

```bash
# Genera migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Applica migration
docker-compose exec backend alembic upgrade head
```

## Monitoraggio salute

### Health checks critici

```bash
# API
curl http://localhost:8000/health

# Database
docker-compose exec postgres pg_isready

# Redis
docker-compose exec redis redis-cli ping
```

### Alert prerequisiti

Controlla che:
- Spazio disco > 20% libero
- Memoria disponibile > 2GB
- CPU load < 80%
- Database connection pool non esaurito