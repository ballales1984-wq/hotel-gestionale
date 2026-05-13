"""
API PMS Integrations — Configurazione connessioni a sistemi PMS/ERP esterni.
Consente di definire credenziali, endpoint e sync schedule.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import PMSIntegration, ExternalSystemType, Hotel
from app.config import get_settings
from app.core.encryption import get_encryption_service
from app.core.pms_sync import SyncResult, run_sync

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class PMSIntegrationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hotel_id: UUID
    name: str
    system_type: str
    api_endpoint: Optional[str] = None
    username: Optional[str] = None
    is_active: bool
    sync_frequency_hours: int
    config_data: Optional[dict] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PMSIntegrationCreate(BaseModel):
    hotel_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    system_type: str = Field(..., description="Tipo PMS: 'mews', 'zucchetti', 'operah', 'custom_api'")
    api_endpoint: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=255, description="Chiave API (sarà cifrata)")
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=100, description="Password (sarà cifrata)")
    sync_frequency_hours: int = Field(24, ge=1, le=168)
    config_data: Optional[dict] = None


class PMSIntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_endpoint: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=255)
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=100)
    sync_frequency_hours: Optional[int] = Field(None, ge=1, le=168)
    is_active: Optional[bool] = None
    config_data: Optional[dict] = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/", response_model=PMSIntegrationSchema, status_code=201, summary="Crea configurazione PMS")
async def create_pms_integration(
    data: PMSIntegrationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea una nuova configurazione integrazione PMS per un hotel."""
    # Verifica hotel esiste
    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel non trovato")

    # Valida system_type
    try:
        system_type = ExternalSystemType(data.system_type)
    except ValueError:
        valid = [e.value for e in ExternalSystemType]
        raise HTTPException(status_code=400, detail=f"Tipo PMS non valido. Valori: {valid}")

    # Verifica unicità nome per hotel
    existing = await db.execute(
        select(PMSIntegration).where(
            PMSIntegration.hotel_id == data.hotel_id,
            PMSIntegration.name == data.name,
            PMSIntegration.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Esiste già un'integrazione attiva con nome '{data.name}' per questo hotel",
        )

    # Cifra credenziali se presenti
    enc = get_encryption_service()
    api_key_enc = enc.encrypt(data.api_key) if data.api_key else None
    password_enc = enc.encrypt(data.password) if data.password else None

    integration = PMSIntegration(
        hotel_id=data.hotel_id,
        name=data.name,
        system_type=system_type,
        api_endpoint=data.api_endpoint,
        api_key=api_key_enc,
        username=data.username,
        password=password_enc,
        sync_frequency_hours=data.sync_frequency_hours,
        config_data=data.config_data,
        is_active=True,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return integration


@router.get("/", response_model=List[PMSIntegrationSchema], summary="Lista integrazioni PMS")
async def list_pms_integrations(
    hotel_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
):
    """Elenca le integrazioni PMS, filtrabili per hotel e stato."""
    q = select(PMSIntegration)
    if hotel_id:
        q = q.where(PMSIntegration.hotel_id == hotel_id)
    if is_active is not None:
        q = q.where(PMSIntegration.is_active == is_active)
    q = q.order_by(PMSIntegration.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{integration_id}", response_model=PMSIntegrationSchema, summary="Dettaglio integrazione PMS")
async def get_pms_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restituisce i dettagli di una configurazione PMS."""
    integration = await db.get(PMSIntegration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integrazione PMS non trovata")
    return integration


@router.put("/{integration_id}", response_model=PMSIntegrationSchema, summary="Aggiorna integrazione PMS")
async def update_pms_integration(
    integration_id: UUID,
    data: PMSIntegrationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Aggiorna una configurazione PMS esistente."""
    integration = await db.get(PMSIntegration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integrazione PMS non trovata")

    update_data = data.model_dump(exclude_unset=True)

    # Cifra credenziali se presenti
    if 'api_key' in update_data and update_data['api_key'] is not None:
        enc = get_encryption_service()
        update_data['api_key'] = enc.encrypt(update_data['api_key'])
    if 'password' in update_data and update_data['password'] is not None:
        enc = get_encryption_service()
        update_data['password'] = enc.encrypt(update_data['password'])

    # If system_type change, validate
    if "system_type" in update_data:
        try:
            update_data["system_type"] = ExternalSystemType(update_data["system_type"])
        except ValueError:
            valid = [e.value for e in ExternalSystemType]
            raise HTTPException(status_code=400, detail=f"Tipo PMS non valido: {valid}")

    for key, value in update_data.items():
        setattr(integration, key, value)

    await db.commit()
    await db.refresh(integration)
    return integration


@router.delete("/{integration_id}", status_code=204, summary="Elimina integrazione PMS")
async def delete_pms_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Elimina (soft) una configurazione PMS. Imposta is_active=False."""
    integration = await db.get(PMSIntegration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integrazione PMS non trovata")

    integration.is_active = False
    await db.commit()
    return None


@router.post("/{integration_id}/sync", summary="Avvia sincronizzazione manuale")
async def sync_pms_integration(
    integration_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Avvia una sincronizzazione manuale dati dal PMS configurato.
    Esegue il sync in background e restituisce immediatamente un job_id."""
    integration = await db.get(PMSIntegration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integrazione PMS non trovata")
    if not integration.is_active:
        raise HTTPException(status_code=400, detail="Integrazione disattivata")

    # Esegui sync in background
    background_tasks.add_task(_run_sync_task, integration_id)

    return {
        "status": "queued",
        "integration_id": str(integration_id),
        "message": "Sync job avviato in background",
        "system_type": integration.system_type.value,
    }


async def _run_sync_task(integration_id: UUID):
    """Task in background per eseguire il sync PMS."""
    logger.info("Task sync PMS avviato per integration_id=%s", integration_id)
    result = await run_sync(integration_id)
    logger.info(
        "Task sync PMS completato: status=%s, imported=%d, errors=%d",
        result.status,
        result.records_imported,
        len(result.errors),
    )
