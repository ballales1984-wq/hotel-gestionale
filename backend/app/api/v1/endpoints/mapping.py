"""
API Mapping & Logs — Gestione Mapping Rules e Import Logs.
Endpoint per CRUD mapping rules e consultazione storico importazioni.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import (
    MappingRule, MappingType, DataImportLog, Hotel,
    CostCenter, Activity, Service, CostDriver,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class MappingRuleSchema(BaseModel):
    id: UUID
    hotel_id: UUID
    mapping_type: str
    external_code: str
    external_description: Optional[str]
    target_cost_center_id: Optional[UUID]
    target_activity_id: Optional[UUID]
    target_service_id: Optional[UUID]
    is_active: bool
    confidence_score: Optional[float]

    class Config:
        from_attributes = True


class MappingRuleCreate(BaseModel):
    mapping_type: str
    external_code: str
    external_description: Optional[str] = None
    target_cost_center_id: Optional[UUID] = None
    target_activity_id: Optional[UUID] = None
    target_service_id: Optional[UUID] = None
    confidence_score: Optional[float] = None


class MappingRuleUpdate(BaseModel):
    external_code: Optional[str] = None
    external_description: Optional[str] = None
    target_cost_center_id: Optional[UUID] = None
    target_activity_id: Optional[UUID] = None
    target_service_id: Optional[UUID] = None
    confidence_score: Optional[float] = None
    is_active: Optional[bool] = None


class DataImportLogSchema(BaseModel):
    id: UUID
    hotel_id: UUID
    import_type: str
    source_system: str
    filename: str
    status: str
    rows_read: int
    rows_imported: int
    errors: Optional[str]
    batch_id: str
    user_id: Optional[UUID]
    created_at: str

    class Config:
        from_attributes = True


class MappingTarget(BaseModel):
    """Rappresenta un target di mapping disponibile (CDC, Attività, Servizio)."""
    id: UUID
    code: str
    name: str
    type: str  # "cost_center", "activity", "service", "driver"


# ─────────────────────────────────────────────────────────────────────────────
# MAPPING RULES CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[MappingRuleSchema],
    summary="Lista regole di mapping",
)
async def list_mapping_rules(
    hotel_id: Optional[UUID] = None,
    mapping_type: Optional[str] = None,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Elenca le regole di mapping. Filtrabile per hotel, tipo e stato."""
    q = select(MappingRule)
    if hotel_id:
        q = q.where(MappingRule.hotel_id == hotel_id)
    if mapping_type:
        q = q.where(MappingRule.mapping_type == MappingType(mapping_type))
    q = q.where(MappingRule.is_active == is_active)
    result = await db.execute(q)
    return result.scalars().all()


@router.get(
    "/{rule_id}",
    response_model=MappingRuleSchema,
    summary="Dettaglio regola di mapping",
)
async def get_mapping_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restituisce una singola regola di mapping."""
    rule = await db.get(MappingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regola di mapping non trovata")
    return rule


@router.post(
    "/",
    response_model=MappingRuleSchema,
    status_code=201,
    summary="Crea regola di mapping",
)
async def create_mapping_rule(
    data: MappingRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea una nuova regola di mapping tra codice esterno e entità ABC."""
    # Convalida mapping_type
    try:
        mtype = MappingType(data.mapping_type)
    except ValueError:
        valid_types = [t.value for t in MappingType]
        raise HTTPException(
            status_code=400,
            detail=f"Tipo di mapping non valido. Valori ammessi: {valid_types}",
        )

    # Verifica target in base al tipo
    target_field = _get_target_field(mtype)
    target_id = getattr(data, target_field, None)
    if not target_id:
        raise HTTPException(
            status_code=400,
            detail=f"Per mapping_type '{mtype.value}' è richiesto '{target_field}'",
        )

    # Verifica che l'entità target esista
    await _verify_target_exists(db, mtype, target_id)

    # Verifica unicità
    existing = await db.execute(
        select(MappingRule).where(
            MappingRule.mapping_type == mtype,
            MappingRule.external_code == data.external_code,
            MappingRule.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Esiste già un mapping attivo per '{data.external_code}' di tipo '{mtype.value}'",
        )

    rule = MappingRule(
        mapping_type=mtype,
        external_code=data.external_code,
        external_description=data.external_description,
        **{target_field: target_id},
        confidence_score=data.confidence_score,
        is_active=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put(
    "/{rule_id}",
    response_model=MappingRuleSchema,
    summary="Aggiorna regola di mapping",
)
async def update_mapping_rule(
    rule_id: UUID,
    data: MappingRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Aggiorna una regola di mapping esistente."""
    rule = await db.get(MappingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regola di mapping non trovata")

    update_data = data.model_dump(exclude_unset=True)

    # Se si cambia mapping_type, converte in enum
    if "mapping_type" in update_data:
        try:
            update_data["mapping_type"] = MappingType(update_data["mapping_type"])
        except ValueError:
            valid_types = [t.value for t in MappingType]
            raise HTTPException(
                status_code=400,
                detail=f"Tipo di mapping non valido. Valori ammessi: {valid_types}",
            )

    # Verifica target se specificato
    if any(k in update_data for k in ("target_cost_center_id", "target_activity_id", "target_service_id")):
        mtype = update_data.get("mapping_type", rule.mapping_type)
        target_field = _get_target_field(mtype)
        target_id = update_data.get(target_field)
        if target_id:
            await _verify_target_exists(db, mtype, target_id)

    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete(
    "/{rule_id}",
    status_code=204,
    summary="Elimina regola di mapping",
)
async def delete_mapping_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Elimina (soft delete) una regola di mapping."""
    rule = await db.get(MappingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regola di mapping non trovata")
    rule.is_active = False
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# DATA IMPORT LOGS
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/import-logs",
    response_model=List[DataImportLogSchema],
    summary="Storico importazioni",
)
async def list_import_logs(
    hotel_id: Optional[UUID] = None,
    import_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Elenca i log delle importazioni, filtrabile per hotel, tipo e stato."""
    q = select(DataImportLog).order_by(DataImportLog.created_at.desc()).limit(limit)
    if hotel_id:
        q = q.where(DataImportLog.hotel_id == hotel_id)
    if import_type:
        q = q.where(DataImportLog.import_type == import_type)
    if status:
        q = q.where(DataImportLog.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get(
    "/import-logs/{log_id}",
    response_model=DataImportLogSchema,
    summary="Dettaglio log importazione",
)
async def get_import_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restituisce il dettaglio di un singolo log di importazione."""
    log = await db.get(DataImportLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log di importazione non trovato")
    return log


# ─────────────────────────────────────────────────────────────────────────────
# TARGET DISPONIBILI PER MAPPING
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/targets/{mapping_type}",
    response_model=List[MappingTarget],
    summary="Target disponibili per mapping",
)
async def list_mapping_targets(
    mapping_type: str,
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restituisce le entità disponibili come target per un dato tipo di mapping."""
    try:
        mtype = MappingType(mapping_type)
    except ValueError:
        valid_types = [t.value for t in MappingType]
        raise HTTPException(
            status_code=400,
            detail=f"Tipo di mapping non valido. Valori ammessi: {valid_types}",
        )

    results = []

    if mtype == MappingType.COST_CENTER:
        q = select(CostCenter).where(CostCenter.hotel_id == hotel_id, CostCenter.is_active == True)
        rows = (await db.execute(q)).scalars().all()
        results = [MappingTarget(id=r.id, code=r.code, name=r.name, type="cost_center") for r in rows]

    elif mtype == MappingType.ACTIVITY:
        q = select(Activity).where(Activity.hotel_id == hotel_id, Activity.is_active == True)
        rows = (await db.execute(q)).scalars().all()
        results = [MappingTarget(id=r.id, code=r.code, name=r.name, type="activity") for r in rows]

    elif mtype == MappingType.SERVICE:
        q = select(Service).where(Service.hotel_id == hotel_id, Service.is_active == True)
        rows = (await db.execute(q)).scalars().all()
        results = [MappingTarget(id=r.id, code=r.code, name=r.name, type="service") for r in rows]

    elif mtype == MappingType.DRIVER:
        q = select(CostDriver).where(CostDriver.hotel_id == hotel_id, CostDriver.is_active == True)
        rows = (await db.execute(q)).scalars().all()
        results = [MappingTarget(id=r.id, code=r.code, name=r.name, type="driver") for r in rows]

    elif mtype == MappingType.ACCOUNT:
        # Per i conti contabili, target = centri di costo
        q = select(CostCenter).where(CostCenter.hotel_id == hotel_id, CostCenter.is_active == True)
        rows = (await db.execute(q)).scalars().all()
        results = [MappingTarget(id=r.id, code=r.code, name=r.name, type="cost_center") for r in rows]

    return results


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_target_field(mapping_type: MappingType) -> str:
    """Restituisce il nome del campo target per un dato tipo di mapping."""
    _map = {
        MappingType.COST_CENTER: "target_cost_center_id",
        MappingType.ACTIVITY: "target_activity_id",
        MappingType.SERVICE: "target_service_id",
        MappingType.DRIVER: "target_activity_id",  # Driver mappati su Activity
        MappingType.ACCOUNT: "target_cost_center_id",  # Conti mappati su CDC
    }
    return _map.get(mapping_type, "target_cost_center_id")


async def _verify_target_exists(db: AsyncSession, mapping_type: MappingType, target_id: UUID):
    """Verifica che l'entità target esista nel database."""
    from sqlalchemy import select

    model_map = {
        MappingType.COST_CENTER: CostCenter,
        MappingType.ACTIVITY: Activity,
        MappingType.SERVICE: Service,
        MappingType.DRIVER: CostDriver,
    }

    model = model_map.get(mapping_type)
    if model:
        result = await db.execute(select(model).where(model.id == target_id))
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail=f"Entità target '{model.__tablename__}' con ID {target_id} non trovata",
            )