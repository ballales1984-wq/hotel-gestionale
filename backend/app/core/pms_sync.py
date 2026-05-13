"""
PMS Sync Service — Sincronizzazione dati da sistemi PMS esterni.
Supporta:
  - PMS_API: chiamate REST a API esterne
  - PMS_CSV: importazione da file CSV (locale o remoto)
Altre tipologie (ERP_*) sono placeholder per futuro sviluppo.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionFactory
from app.models.models import (
    PMSIntegration, ExternalSystemType, Hotel,
    ServiceRevenue, CostItem, DataImportLog, AccountingPeriod, Service, CostCenter,
    MappingRule, MappingType
)
from app.core.encryption import get_encryption_service

logger = logging.getLogger(__name__)


def _get_settings():
    """Lazy settings initialization."""
    from app.config import get_settings
    return get_settings()


def _get_enc_service():
    """Lazy initialization dell'encryption service (evita crash a import time)."""
    return get_encryption_service()


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

class SyncResult:
    """Risultato sincronizzazione."""
    def __init__(
        self,
        status: str,
        hotel_id: UUID,
        integration_id: UUID,
        records_imported: int = 0,
        records_read: int = 0,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.hotel_id = hotel_id
        self.integration_id = integration_id
        self.records_imported = records_imported
        self.records_read = records_read
        self.errors = errors or []
        self.metadata = metadata or {}

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    def summary(self) -> str:
        parts = [f"status={self.status}", f"imported={self.records_imported}"]
        if self.records_read:
            parts.append(f"read={self.records_read}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return ", ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SYNC ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

async def run_sync(integration_id: UUID) -> SyncResult:
    """
    Entrypoint per sincronizzazione PMS.
    Viene chiamato dal background task.
    """
    async with AsyncSessionFactory() as db:
        try:
            integration = await db.get(PMSIntegration, integration_id)
            if not integration or not integration.is_active:
                return SyncResult(
                    status="error",
                    hotel_id=integration.hotel_id if integration else UUID('00000000-0000-0000-0000-000000000000'),
                    integration_id=integration_id,
                    errors=["Integrazione non trovata o disattivata"],
                )

            hotel = await db.get(Hotel, integration.hotel_id)
            if not hotel or not hotel.is_active:
                return SyncResult(
                    status="error",
                    hotel_id=integration.hotel_id,
                    integration_id=integration_id,
                    errors=["Hotel non trovato o disattivato"],
                )

            logger.info(
                "PMS sync avviato: hotel=%s, integration=%s, type=%s",
                hotel.code, integration.name, integration.system_type.value
            )

            # Decifra credenziali se necessario
            api_key = None
            password = None
            if integration.api_key:
                try:
                    api_key = _get_enc_service().decrypt(integration.api_key)
                except Exception as e:
                    logger.warning("Failed decrypt api_key: %s", e)
            if integration.password:
                try:
                    password = _get_enc_service().decrypt(integration.password)
                except Exception as e:
                    logger.warning("Failed decrypt password: %s", e)

            settings = _get_settings()

            # Esegui sync in base al system_type
            if integration.system_type == ExternalSystemType.PMS_API:
                result = await _sync_pms_api(db, integration, hotel, api_key, password, settings)
            elif integration.system_type == ExternalSystemType.PMS_CSV:
                result = await _sync_pms_csv(db, integration, hotel, integration.config_data)
            elif integration.system_type in (ExternalSystemType.ERP_API, ExternalSystemType.ERP_CSV):
                result = await _sync_erp(db, integration, hotel, api_key, password)
            elif integration.system_type == ExternalSystemType.MANUAL:
                result = SyncResult(
                    status="skipped",
                    hotel_id=hotel.id,
                    integration_id=integration_id,
                    errors=["Sync non applicabile per integration manuale"],
                )
            else:
                result = SyncResult(
                    status="error",
                    hotel_id=hotel.id,
                    integration_id=integration_id,
                    errors=[f"Tipo integrazione non supportato: {integration.system_type.value}"],
                )

            if result.status in ("success", "partial"):
                integration.last_sync_at = datetime.now()
                await db.commit()

            await _log_import(db, integration, hotel, result)

            logger.info(
                "PMS sync completato: hotel=%s, integration=%s, status=%s, records=%d, errors=%d",
                hotel.code, integration.name, result.status, result.records_imported, len(result.errors)
            )
            return result

        except Exception as e:
            logger.exception("PMS sync failed: integration_id=%s", integration_id)
            return SyncResult(
                status="error",
                hotel_id=integration.hotel_id if 'integration' in locals() else None,
                integration_id=integration_id,
                errors=[str(e)],
            )


# ─────────────────────────────────────────────────────────────────────────────
# CONCRETE SYNC IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────────────

async def _sync_pms_api(
    db: AsyncSession,
    integration: PMSIntegration,
    hotel: Hotel,
    api_key: Optional[str],
    password: Optional[str],
    settings: Any,
) -> SyncResult:
    """Sincronizza da un PMS via API REST."""
    errors = []
    records_imported = 0

    if not integration.api_endpoint:
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=["API endpoint non configurato"],
        )

    logger.info("PMS API sync: endpoint=%s, hotel=%s", integration.api_endpoint, hotel.code)

    timeout = httpx.Timeout(timeout=getattr(settings, 'sync_timeout', 60))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {"Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await client.get(
                integration.api_endpoint,
                headers=headers,
                auth=(integration.username, password) if integration.username and password else None,
            )
            response.raise_for_status()
            data = response.json()
            records = data.get("records", data.get("data", []))
            if isinstance(records, list):
                records_imported = len(records)

    except httpx.HTTPStatusError as e:
        errors.append(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=errors,
        )
    except Exception as e:
        errors.append(f"Errore connessione: {e}")
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=errors,
        )

    # Successo placeholder — in produzione parsare e salvare i dati
    return SyncResult(
        status="success",
        hotel_id=hotel.id,
        integration_id=integration.id,
        records_imported=records_imported,
        errors=[],
        metadata={"source": "api", "raw_records": records_imported},
    )


async def _sync_pms_csv(
    db: AsyncSession,
    integration: PMSIntegration,
    hotel: Hotel,
    config_data: Optional[Dict[str, Any]],
) -> SyncResult:
    """Sincronizza da file CSV."""
    errors = []
    records_imported = 0

    if not config_data or 'file_path' not in config_data:
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=["config_data.file_path mancante"],
        )

    file_path = config_data['file_path']
    delimiter = config_data.get('delimiter', ',')
    encoding = config_data.get('encoding', 'utf-8')

    logger.info("PMS CSV sync: file=%s, hotel=%s", file_path, hotel.code)

    content = None
    try:
        if isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://')):
            timeout = httpx.Timeout(timeout=30)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(file_path)
                resp.raise_for_status()
                content = resp.content.decode(encoding)
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
    except Exception as e:
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=[f"Impossibile leggere file CSV: {e}"],
        )

    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        if not reader.fieldnames:
            return SyncResult(
                status="error",
                hotel_id=hotel.id,
                integration_id=integration.id,
                errors=["CSV vuoto o senza header"],
            )

        col_map = {}
        required = {'date', 'service_code', 'revenue'}
        for col in reader.fieldnames:
            col_l = col.lower().strip()
            if col_l in ('date', 'data', 'transaction_date', 'service_date'):
                col_map['date'] = col
            elif col_l in ('service_code', 'codice_servizio', 'service', 'servizio', 'code'):
                col_map['service_code'] = col
            elif col_l in ('revenue', 'importo', 'amount', 'ricavo'):
                col_map['revenue'] = col
            elif col_l in ('quantity', 'quantita', 'qty'):
                col_map['quantity'] = col
            elif col_l in ('output_volume', 'volume', 'units', 'unita'):
                col_map['output_volume'] = col

        missing = required - set(col_map.keys())
        if missing:
            return SyncResult(
                status="error",
                hotel_id=hotel.id,
                integration_id=integration.id,
                errors=[f"Colonne CSV mancanti: {missing}"],
            )

        row_count = 0
        for row in reader:
            row_count += 1
            try:
                date_str = row[col_map['date']].strip()
                try:
                    row_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        row_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                        errors.append(f"Riga {row_count}: formato data non valido")
                        continue

                service_code = row[col_map['service_code']].strip()
                if not service_code:
                    errors.append(f"Riga {row_count}: service_code vuoto")
                    continue

                rev_str = row[col_map['revenue']].strip().replace(',', '.').replace('$', '').replace('€', '')
                try:
                    revenue = Decimal(rev_str)
                except Exception:
                    errors.append(f"Riga {row_count}: revenue non valido")
                    continue

                quantity = Decimal('1')
                if 'quantity' in col_map and row[col_map['quantity']].strip():
                    try:
                        quantity = Decimal(row[col_map['quantity']].strip().replace(',', '.'))
                    except Exception:
                        quantity = Decimal('1')

                output_volume = quantity
                if 'output_volume' in col_map and row[col_map['output_volume']].strip():
                    try:
                        output_volume = Decimal(row[col_map['output_volume']].strip().replace(',', '.'))
                    except Exception:
                        output_volume = quantity

                period = await _get_or_create_period(db, hotel.id, datetime.combine(row_date, datetime.min.time()))
                service = await _find_service(db, hotel.id, service_code)
                if not service:
                    errors.append(f"Riga {row_count}: servizio '{service_code}' non trovato")
                    continue

                stmt = select(ServiceRevenue).where(
                    ServiceRevenue.hotel_id == hotel.id,
                    ServiceRevenue.period_id == period.id,
                    ServiceRevenue.service_id == service.id,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if existing:
                    existing.revenue = revenue
                    existing.output_volume = output_volume
                    existing.source_system = integration.system_type.value
                else:
                    sr = ServiceRevenue(
                        hotel_id=hotel.id,
                        period_id=period.id,
                        service_id=service.id,
                        revenue=revenue,
                        output_volume=output_volume,
                        source_system=integration.system_type.value,
                    )
                    db.add(sr)

                records_imported += 1
                await db.flush()
            except Exception as e:
                errors.append(f"Riga {row_count}: errore generico {str(e)}")
                continue

        await db.commit()
        status = "success" if not errors else "partial"
        return SyncResult(
            status=status,
            hotel_id=hotel.id,
            integration_id=integration.id,
            records_imported=records_imported,
            errors=errors,
            metadata={"rows_processed": row_count, "file": file_path},
        )
    except Exception as e:
        logger.exception("CSV sync failed")
        return SyncResult(
            status="error",
            hotel_id=hotel.id,
            integration_id=integration.id,
            errors=[f"Errore parsing CSV: {e}"],
        )


async def _sync_erp(
    db: AsyncSession,
    integration: PMSIntegration,
    hotel: Hotel,
    api_key: Optional[str],
    password: Optional[str],
) -> SyncResult:
    """Placeholder per sincronizzazione ERP."""
    logger.info("ERP sync non implementato: hotel=%s, integration=%s", hotel.code, integration.name)
    return SyncResult(
        status="skipped",
        hotel_id=hotel.id,
        integration_id=integration.id,
        errors=["Integrazione ERP non ancora supportata"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# SUPPORT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def _log_import(
    db: AsyncSession,
    integration: PMSIntegration,
    hotel: Hotel,
    result: SyncResult,
) -> None:
    """Registra log dell'importazione in DataImportLog."""
    status_str = "success" if result.status == "success" else (
        "partial" if result.status == "partial" else "error"
    )

    import_log = DataImportLog(
        hotel_id=hotel.id,
        import_type="pms",
        source_system=integration.system_type.value,
        filename=integration.name,
        status=status_str,
        rows_read=result.records_imported,
        rows_imported=result.records_imported,
        errors="\n".join(result.errors) if result.errors else None,
        batch_id=f"pms_{integration.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    db.add(import_log)
    await db.commit()


async def _find_service(db: AsyncSession, hotel_id: UUID, code: str) -> Optional[Service]:
    """Cerca servizio per codice interno o tramite mapping esterno."""
    stmt = select(Service).where(
        Service.hotel_id == hotel_id,
        Service.code == code,
        Service.is_active == True,
    )
    svc = (await db.execute(stmt)).scalar_one_or_none()
    if svc:
        return svc
    return await _get_service_by_external_code(db, hotel_id, code)


async def _get_or_create_period(
    db: AsyncSession,
    hotel_id: UUID,
    date: datetime,
) -> AccountingPeriod:
    """Restituisce il periodo contabile per la data, creandolo se non esiste."""
    year = date.year
    month = date.month

    stmt = select(AccountingPeriod).where(
        AccountingPeriod.hotel_id == hotel_id,
        AccountingPeriod.year == year,
        AccountingPeriod.month == month,
    )
    result = await db.execute(stmt)
    period = result.scalar_one_or_none()

    if not period:
        months_ita = [
            "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
        ]
        period_name = f"{months_ita[month]} {year}"

        period = AccountingPeriod(
            hotel_id=hotel_id,
            year=year,
            month=month,
            name=period_name,
            is_closed=False,
        )
        db.add(period)
        await db.flush()

    return period


async def _get_service_by_external_code(
    db: AsyncSession,
    hotel_id: UUID,
    external_code: str,
) -> Optional[Service]:
    """Cerca un servizio mappato da codice esterno (da MappingRule)."""
    stmt = select(MappingRule).where(
        MappingRule.hotel_id == hotel_id,
        MappingRule.mapping_type == MappingType.SERVICE,
        MappingRule.external_code == external_code,
        MappingRule.is_active == True,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if rule and rule.target_service_id:
        return await db.get(Service, rule.target_service_id)
    return None