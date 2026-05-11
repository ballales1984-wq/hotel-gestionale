# Installazione e Configurazione

## Requisiti di sistema

| Componente | Versione minima | Consigliata |
|------------|-----------------|-------------|
| Docker | 24.0 | 25.0+ |
| Docker Compose | 2.20 | 2.27+ |
| RAM | 8GB | 16GB |
| Storage | 20GB | 50GB+ |

## Installazione rapida

```bash
# 1. Clona il repository
git clone https://github.com/your-org/hotel-abc-platform.git
cd hotel-abc-platform

# 2. Configura l'ambiente
cp .env.example .env

# 3. Modifica le variabili in .env
nano .env  # o usare il tuo editor preferito

# 4. Avvia i servizi
docker-compose up -d

# 5. Inizializza il database
docker-compose exec backend python -m app.db.seed
```

## Variabili d'ambiente

### File `.env`

```bash
# Database
POSTGRES_PASSWORD=hotel_secure_2025
POSTGRES_USER=hotel_user
POSTGRES_DB=hotel_abc

# Redis
REDIS_PASSWORD=redis_secure_2025

# Security
SECRET_KEY=change_me_in_production_32chars_min
SUPERSET_SECRET_KEY=superset_secret_2025_change_me

# Environment
ENVIRONMENT=development
LOG_LEVEL=info
```

### Variabili obbligatorie

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `POSTGRES_PASSWORD` | Password database | `hotel_secure_2025` |
| `SECRET_KEY` | JWT secret key | da modificare |
| `ENVIRONMENT` | `development` o `production` | `development` |

## Configurazione per ambiente

### Sviluppo

```bash
# docker-compose.yml
FRONTEND_TARGET: development
ENVIRONMENT: development
```

### Produzione

```bash
# docker-compose.yml
FRONTEND_TARGET: production
ENVIRONMENT: production
```

Per la produzione, aggiungi:
- Certificati SSL in `infra/nginx/ssl/`
- Configurazione DNS
- Backup automatici

## Verifica installazione

```bash
# Controlla lo stato dei container
docker-compose ps

# Verifica l'API
curl http://localhost:8000/health

# Verifica il frontend
curl http://localhost:3000
```

## Note per Windows

Usa PowerShell o WSL2 per evitare problemi di permessi con Docker Desktop.

## Troubleshooting installazione

### Porta già in uso

```bash
# Trova il processo che usa la porta
netstat -ano | findstr :3000

# Su Linux/macOS
lsof -i :3000
```

### Problemi di permessi Docker

```bash
# Su Linux
sudo usermod -aG docker $USER
newgrp docker
```

### Volume Docker corrotto

```bash
# Rimuovi i volumi (ATTENZIONE: cancella tutti i dati)
docker-compose down -v
docker volume prune
```