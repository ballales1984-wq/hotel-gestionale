# Hotel ABC Platform

Activity-Based Costing (ABC/ABS) platform for hospitality management.

## Stack
- **Backend**: FastAPI (Python 3.12)
- **Database**: PostgreSQL 16
- **Analytics**: DuckDB + Polars
- **ETL**: Prefect
- **Frontend**: React + Material UI
- **BI**: Apache Superset
- **Cache**: Redis
- **Auth**: Keycloak (planned)

## Services
- PostgreSQL (port 5432)
- Redis (port 6379)
- Backend API (port 8000)
- Frontend (port 3000)
- Superset BI (port 8088)
- Nginx reverse proxy (port 80/443)

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d

# Initialize database
docker-compose exec backend alembic upgrade head
```

## Documentation
- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)
- [ABC Methodology](docs/abc-methodology.md)
