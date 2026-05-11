"""
API Imports — Import dati da CSV/Excel (payroll, contabilità, PMS, mapping rules).
Versione 2.0 — con supporto MappingRule e DataImportLog.
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import polars as pl
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import (
    AccountingPeriod, CostCenter, CostItem, CostType,
    Employee, LaborAllocation, Department, Service, ServiceRevenue,
    MappingRule, MappingType, DataImportLog, Hotel, CostDriver,
)
from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    filename: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    errors: list[str]
    warnings: list[str]
    import_batch_id: str


class MappingRow(BaseModel):
    tipo_mapping: str
    codice_esterno: str
    descrizione_esterna: Optional[str] = None
    codice_interno: str
    attendibilita: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def _create_import_log(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    import_type: str,
    source_system: str,
    filename: str,
    status: str,
    rows_read: int,
    rows_imported: int,
    errors: list[str],
    user_id: Optional[uuid.UUID] = None,
) -> str:
    """Crea un DataImportLog per tracciare l'importazione."""
    batch_id = str(uuid.uuid4())
    log = DataImportLog(
        hotel_id=hotel_id,
        import_type=import_type,
        source_system=source_system,
        filename=filename,
        status=status,
        rows_read=rows_read,
        rows_imported=rows_imported,
        errors="; ".join(errors) if errors else None,
        batch_id=batch_id,
        user_id=user_id,
    )
    db.add(log)
    await db.commit()
    return batch_id


async def _load_mapping_rules(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    mapping_type: Optional[MappingType] = None,
) -> dict[str, uuid.UUID]:
    """
    Carica le regole di mapping per un hotel.
    Restituisce {external_code: target_entity_id}.
    """
    q = select(MappingRule).where(
        MappingRule.hotel_id == hotel_id,
        MappingRule.is_active == True,
    )
    if mapping_type:
        q = q.where(MappingRule.mapping_type == mapping_type)

    result = await db.execute(q)
    rules = result.scalars().all()

    mapping: dict[str, uuid.UUID] = {}
    for rule in rules:
        target_id = (
            rule.target_cost_center_id
            or rule.target_activity_id
            or rule.target_service_id
        )
        if target_id:
            mapping[rule.external_code] = target_id
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# FILE PARSING UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

async def _validate_file(file: UploadFile) -> None:
    """Valida estensione e dimensione del file."""
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato: {ext}. Usare: {settings.allowed_extensions}",
        )


def _read_file(content: bytes, filename: str) -> pl.DataFrame:
    """Legge CSV o Excel e restituisce un DataFrame Polars."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return pl.read_csv(
            io.BytesIO(content),
            separator=None,   # auto-detect ; o ,
            infer_schema_length=1000,
            ignore_errors=True,
            null_values=["", "N/A", "n/a", "NULL", "null"],
        )
    elif ext in ("xlsx", "xls"):
        import pandas as pd
        pdf = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        return pl.from_pandas(pdf)
    else:
        raise ValueError(f"Formato non supportato: {ext}")


def _normalize_columns(df: pl.DataFrame, col_map: dict[str, list[str]]) -> pl.DataFrame:
    """
    Rinomina le colonne del DataFrame usando un dizionario di alias.
    col_map: {nome_standard: [alias1, alias2, ...]}
    """
    rename = {}
    existing_cols = [c.lower().strip() for c in df.columns]

    for standard_name, aliases in col_map.items():
        for alias in aliases:
            if alias.lower() in existing_cols:
                original = df.columns[existing_cols.index(alias.lower())]
                rename[original] = standard_name
                break

    if rename:
        df = df.rename(rename)

    # Lowercase tutti i nomi colonne non rinominati
    df = df.rename({c: c.lower().strip() for c in df.columns if c not in rename.values()})

    return df


def _map_cost_type(raw: str) -> CostType:
    """Mappa una stringa libera a un CostType enum."""
    mapping = {
        "personale": CostType.LABOR,
        "labor": CostType.LABOR,
        "stipendi": CostType.LABOR,
        "diretto": CostType.DIRECT,
        "direct": CostType.DIRECT,
        "materie prime": CostType.DIRECT,
        "struttura": CostType.OVERHEAD,
        "overhead": CostType.OVERHEAD,
        "fisso": CostType.OVERHEAD,
        "ammortamento": CostType.DEPRECIATION,
        "depreciation": CostType.DEPRECIATION,
        "utilities": CostType.UTILITIES,
        "energia": CostType.UTILITIES,
    }
    for key, val in mapping.items():
        if key in raw.lower():
            return val
    return CostType.OTHER


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT CONTABILITÀ (Costi)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/accounting",
    response_model=ImportResult,
    summary="Import voci di costo da CSV/Excel",
    description=(
        "Importa le voci di costo dalla contabilità analitica. "
        "Supporta mapping automatico tramite MappingRule (codice esterno → centro di costo ABC). "
        "Colonne attese: conto, descrizione, centro_di_costo, tipo_costo, importo"
    ),
)
async def import_accounting(
    file: UploadFile = File(..., description="File CSV o Excel"),
    period_id: uuid.UUID = Form(..., description="ID periodo contabile"),
    db: AsyncSession = Depends(get_db),
):
    """Importa voci di costo da CSV o Excel."""
    await _validate_file(file)

    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    hotel_id = period.hotel_id
    batch_id = str(uuid.uuid4())
    content = await file.read()

    try:
        df = _read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {e}")

    # Normalizza colonne
    df = _normalize_columns(df, {
        "conto": ["conto", "account", "codice_conto", "cod_conto"],
        "descrizione": ["descrizione", "description", "desc", "nome_conto"],
        "centro_di_costo": ["centro_di_costo", "cdc", "cost_center", "reparto"],
        "tipo_costo": ["tipo_costo", "tipo", "cost_type", "categoria"],
        "importo": ["importo", "amount", "valore", "totale"],
    })

    required_cols = {"importo"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonne mancanti nel file: {missing}. "
                   "Attese: conto, descrizione, centro_di_costo, tipo_costo, importo",
        )

    errors = []
    warnings = []
    imported = 0
    skipped = 0

    # Carica mappa centri di costo esistenti
    cc_map = await _load_cost_center_map(db, hotel_id)
    # Carica mapping rules per contabilità (esterno → centro di costo)
    mapping_map = await _load_mapping_rules(db, hotel_id, MappingType.COST_CENTER)
    account_mapping = await _load_mapping_rules(db, hotel_id, MappingType.ACCOUNT)

    for i, row in enumerate(df.iter_rows(named=True)):
        try:
            amount = Decimal(str(row.get("importo", 0) or 0))
            if amount == 0:
                warnings.append(f"Riga {i+2}: importo zero, saltata")
                skipped += 1
                continue

            cc_id = None
            cc_raw = str(row.get("centro_di_costo", "") or "").strip()

            # 1. Prova mappa diretta CDC
            if cc_raw and cc_raw in cc_map:
                cc_id = cc_map[cc_raw]
            # 2. Prova mapping rules (codice esterno → CDC)
            elif cc_raw and cc_raw in mapping_map:
                cc_id = mapping_map[cc_raw]
            # 3. Prova mapping tramite account code
            elif cc_raw:
                account_map_key = str(row.get("conto", "") or "").strip()
                if account_map_key in account_mapping:
                    cc_id = account_mapping[account_map_key]
                else:
                    warnings.append(
                        f"Riga {i+2}: centro di costo '{cc_raw}' non trovato direttamente né tramite mapping"
                    )

            # Risolvi account_code dal mapping se disponibile
            account_code_raw = str(row.get("conto", "") or "").strip()

            cost_type_raw = str(row.get("tipo_costo", "") or "").lower().strip()
            cost_type = _map_cost_type(cost_type_raw)

            cost_item = CostItem(
                period_id=period_id,
                hotel_id=hotel_id,
                cost_center_id=cc_id,
                account_code=account_code_raw[:50] or None,
                account_name=str(row.get("descrizione", "") or "")[:200] or None,
                cost_type=cost_type,
                amount=amount,
                source_system="import_csv",
                import_batch_id=batch_id,
            )
            db.add(cost_item)
            imported += 1

        except Exception as e:
            errors.append(f"Riga {i+2}: {e}")
            skipped += 1

    await db.commit()

    # Crea DataImportLog
    status = "success" if not errors else "partial" if imported > 0 else "error"
    await _create_import_log(
        db, hotel_id, "accounting", "erp_csv", file.filename,
        status, len(df), imported, errors
    )

    logger.info("Import contabilità: %d righe importate, %d saltate", imported, skipped)

    return ImportResult(
        filename=file.filename,
        rows_read=len(df),
        rows_imported=imported,
        rows_skipped=skipped,
        errors=errors,
        warnings=warnings,
        import_batch_id=batch_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT PAYROLL (Ore personale per attività)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/payroll",
    response_model=ImportResult,
    summary="Import ore personale da CSV/Excel",
    description=(
        "Importa le ore lavorate per dipendente e attività. "
        "Supporta mapping automatico tramite MappingRule (codice esterno → attività ABC). "
        "Colonne attese: matricola, nome, attività, ore, costo_orario, percentuale"
    ),
)
async def import_payroll(
    file: UploadFile = File(...),
    period_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await _validate_file(file)
    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    hotel_id = period.hotel_id
    batch_id = str(uuid.uuid4())
    content = await file.read()

    try:
        df = _read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {e}")

    df = _normalize_columns(df, {
        "matricola": ["matricola", "employee_code", "codice_dipendente", "id"],
        "nome": ["nome", "full_name", "dipendente", "name"],
        "attivita": ["attivita", "attività", "activity", "activity_code"],
        "ore": ["ore", "hours", "h"],
        "costo_orario": ["costo_orario", "hourly_cost", "costo_ora", "tariffa"],
        "percentuale": ["percentuale", "pct", "percent", "quota", "alloc_pct"],
    })

    # Carica mappa dipendenti
    employees_q = await db.execute(select(Employee).where(Employee.hotel_id == hotel_id))
    emp_map = {e.employee_code: e for e in employees_q.scalars().all()}

    # Carica mappa attività esistenti
    activities_q = await db.execute(select(Activity).where(Activity.hotel_id == hotel_id))
    act_map = {a.code: a for a in activities_q.scalars().all()}

    # Carica mapping rules per attività
    activity_mapping = await _load_mapping_rules(db, hotel_id, MappingType.ACTIVITY)

    errors = []
    warnings = []
    imported = 0
    skipped = 0

    for i, row in enumerate(df.iter_rows(named=True)):
        try:
            matricola = str(row.get("matricola", "") or "").strip()
            act_code = str(row.get("attivita", "") or "").strip()
            ore = Decimal(str(row.get("ore", 0) or 0))
            costo_orario = Decimal(str(row.get("costo_orario", 0) or 0))
            pct_raw = row.get("percentuale")
            pct = Decimal(str(pct_raw or 1))
            if pct > 1:
                pct = pct / 100  # converte da % a decimale

            if ore <= 0:
                skipped += 1
                continue

            # Trova dipendente (solo esistenti, non crea automaticamente per sicurezza multi-tenancy)
            emp = emp_map.get(matricola)
            if not emp:
                warnings.append(f"Riga {i+2}: dipendente '{matricola}' non trovato per hotel {hotel_id}")
                skipped += 1
                continue

            # Trova attività: 1° mappa diretta, 2° mapping rules
            act = act_map.get(act_code)
            if not act and act_code in activity_mapping:
                act_id = activity_mapping[act_code]
                act = next((a for a in act_map.values() if a.id == act_id), None)

            if not act:
                # Prova a cercare l'ID direttamente dal mapping
                if act_code in activity_mapping:
                    act_lookup = await db.get(Activity, activity_mapping[act_code])
                    if act_lookup and act_lookup.hotel_id == hotel_id:
                        act = act_lookup
                        act_map[act_code] = act
                    else:
                        errors.append(f"Riga {i+2}: attività mappata '{act_code}' non trovata o non appartiene a questo hotel")
                        skipped += 1
                        continue
                else:
                    errors.append(f"Riga {i+2}: attività '{act_code}' non trovata e nessun mapping disponibile")
                    skipped += 1
                    continue

            labor = LaborAllocation(
                period_id=period_id,
                hotel_id=hotel_id,
                employee_id=emp.id,
                activity_id=act.id,
                hours=ore,
                hourly_cost=costo_orario if costo_orario > 0 else (emp.hourly_cost or Decimal("0")),
                allocation_pct=pct,
                source="import_csv",
            )
            db.add(labor)
            imported += 1

        except Exception as e:
            errors.append(f"Riga {i+2}: {e}")
            skipped += 1

    await db.commit()

    # Crea DataImportLog
    status = "success" if not errors else "partial" if imported > 0 else "error"
    await _create_import_log(
        db, hotel_id, "payroll", "hr_import", file.filename,
        status, len(df), imported, errors
    )

    logger.info("Import payroll: %d righe importate, %d saltate", imported, skipped)

    return ImportResult(
        filename=file.filename,
        rows_read=len(df),
        rows_imported=imported,
        rows_skipped=skipped,
        errors=errors,
        warnings=warnings,
        import_batch_id=batch_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT RICAVI (da PMS o manuale)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/revenues",
    response_model=ImportResult,
    summary="Import ricavi per servizio",
    description=(
        "Importa i ricavi per servizio dal PMS o manualmente. "
        "Supporta mapping automatico tramite MappingRule (codice PMS → servizio ABC). "
        "Upsert: se esistono già ricavi per lo stesso periodo/servizio, vengono sostituiti."
    ),
)
async def import_revenues(
    file: UploadFile = File(...),
    period_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await _validate_file(file)
    period = await db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo non trovato")

    hotel_id = period.hotel_id
    batch_id = str(uuid.uuid4())
    content = await file.read()

    try:
        df = _read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {e}")

    df = _normalize_columns(df, {
        "servizio": ["servizio", "service", "service_code", "codice_servizio"],
        "ricavo": ["ricavo", "revenue", "fatturato", "totale"],
        "volume": ["volume", "quantita", "quantity", "pezzi", "notti", "coperti"],
    })

    # Carica mappa servizi esistenti
    services_q = await db.execute(select(Service).where(Service.hotel_id == hotel_id))
    svc_map = {s.code: s for s in services_q.scalars().all()}

    # Carica mapping rules per servizi
    service_mapping = await _load_mapping_rules(db, hotel_id, MappingType.SERVICE)

    errors = []
    warnings = []
    imported = 0
    skipped = 0

    for i, row in enumerate(df.iter_rows(named=True)):
        try:
            svc_code = str(row.get("servizio", "") or "").strip()
            revenue = Decimal(str(row.get("ricavo", 0) or 0))
            volume = row.get("volume")

            svc = svc_map.get(svc_code)
            if not svc and svc_code in service_mapping:
                svc_id = service_mapping[svc_code]
                svc = next((s for s in svc_map.values() if s.id == svc_id), None)

            if not svc:
                errors.append(f"Riga {i+2}: servizio '{svc_code}' non trovato e nessun mapping disponibile")
                skipped += 1
                continue

            # Upsert: cancella ricavi precedenti per lo stesso periodo/servizio
            from sqlalchemy import delete
            await db.execute(
                delete(ServiceRevenue).where(
                    ServiceRevenue.period_id == period_id,
                    ServiceRevenue.service_id == svc.id,
                )
            )

            rev = ServiceRevenue(
                period_id=period_id,
                hotel_id=hotel_id,
                service_id=svc.id,
                revenue=revenue,
                output_volume=Decimal(str(volume)) if volume else None,
                source_system="import_csv",
            )
            db.add(rev)
            imported += 1

        except Exception as e:
            errors.append(f"Riga {i+2}: {e}")
            skipped += 1

    await db.commit()

    # Crea DataImportLog
    status = "success" if not errors else "partial" if imported > 0 else "error"
    await _create_import_log(
        db, hotel_id, "revenues", "pms_csv", file.filename,
        status, len(df), imported, errors
    )

    logger.info("Import ricavi: %d righe importate, %d saltate", imported, skipped)

    return ImportResult(
        filename=file.filename,
        rows_read=len(df),
        rows_imported=imported,
        rows_skipped=skipped,
        errors=errors,
        warnings=warnings,
        import_batch_id=batch_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT MAPPING RULES (da CSV)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/mappings",
    response_model=ImportResult,
    summary="Import mapping rules da CSV",
    description=(
        "Importa in blocco regole di mapping tra codici esterni (PMS/ERP) e entità ABC. "
        "Colonne: tipo_mapping, codice_esterno, descrizione_esterna, codice_interno, attendibilita"
    ),
)
async def import_mapping_rules(
    file: UploadFile = File(...),
    hotel_id: uuid.UUID = Form(..., description="ID dell'hotel per il quale importare i mapping"),
    db: AsyncSession = Depends(get_db),
):
    """Importa regole di mapping da CSV/Excel per automatizzare la risoluzione dei codici."""
    await _validate_file(file)

    # Verifica che l'hotel esista
    hotel = await db.get(Hotel, hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel non trovato")

    batch_id = str(uuid.uuid4())
    content = await file.read()

    try:
        df = _read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {e}")

    df = _normalize_columns(df, {
        "tipo_mapping": ["tipo_mapping", "mapping_type", "tipo"],
        "codice_esterno": ["codice_esterno", "external_code", "codice_est"],
        "descrizione_esterna": ["descrizione_esterna", "descrizione_esterno", "external_desc", "external_description"],
        "codice_interno": ["codice_interno", "internal_code", "codice_int"],
        "attendibilita": ["attendibilita", "confidence", "attendibilita_score"],
    })

    required_cols = {"tipo_mapping", "codice_esterno", "codice_interno"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonne mancanti nel file: {missing}. "
                   "Attese: tipo_mapping, codice_esterno, codice_interno",
        )

    errors = []
    warnings = []
    imported = 0
    skipped = 0

    # Mappa interna: tipo_mapping stringa → MappingType enum
    mapping_type_map = {
        "centro_di_costo": MappingType.COST_CENTER,
        "attivita": MappingType.ACTIVITY,
        "servizio": MappingType.SERVICE,
        "driver": MappingType.DRIVER,
        "conto_contabile": MappingType.ACCOUNT,
    }

    # Carica ID mappabili per tipo
    cc_map_internal = await _load_cost_center_map(db, hotel_id)
    services_q = await db.execute(select(Service).where(Service.hotel_id == hotel_id))
    svc_map_internal = {s.code: s.id for s in services_q.scalars().all()}
    drivers_q = await db.execute(select(CostDriver).where(CostDriver.hotel_id == hotel_id))
    driver_map_internal = {d.code: d.id for d in drivers_q.scalars().all()}
    activities_q = await db.execute(select(Activity).where(Activity.hotel_id == hotel_id))
    activity_map_internal = {a.code: a.id for a in activities_q.scalars().all()}

    for i, row in enumerate(df.iter_rows(named=True)):
        try:
            tipo_raw = str(row.get("tipo_mapping", "") or "").strip().lower()
            codice_esterno = str(row.get("codice_esterno", "") or "").strip()
            codice_interno = str(row.get("codice_interno", "") or "").strip()
            desc_esterna = str(row.get("descrizione_esterna", "") or "") or None
            attendibilita_raw = row.get("attendibilita")
            attendibilita = float(attendibilita_raw) if attendibilita_raw else None

            if not tipo_raw or not codice_esterno or not codice_interno:
                warnings.append(f"Riga {i+2}: riga incompleta, saltata")
                skipped += 1
                continue

            # Risolvi MappingType
            if tipo_raw not in mapping_type_map:
                errors.append(f"Riga {i+2}: tipo_mapping '{tipo_raw}' non valido (usa: {', '.join(mapping_type_map.keys())})")
                skipped += 1
                continue
            mapping_type = mapping_type_map[tipo_raw]

            # Risolvi target_id in base al tipo
            target_cost_center_id = None
            target_activity_id = None
            target_service_id = None

            if mapping_type == MappingType.COST_CENTER:
                if codice_interno not in cc_map_internal:
                    errors.append(f"Riga {i+2}: centro di costo '{codice_interno}' non esistente")
                    skipped += 1
                    continue
                target_cost_center_id = cc_map_internal[codice_interno]

            elif mapping_type == MappingType.ACTIVITY:
                if codice_interno not in activity_map_internal:
                    errors.append(f"Riga {i+2}: attività '{codice_interno}' non esistente")
                    skipped += 1
                    continue
                target_activity_id = activity_map_internal[codice_interno]

            elif mapping_type == MappingType.SERVICE:
                if codice_interno not in svc_map_internal:
                    errors.append(f"Riga {i+2}: servizio '{codice_interno}' non esistente")
                    skipped += 1
                    continue
                target_service_id = svc_map_internal[codice_interno]

            elif mapping_type == MappingType.DRIVER:
                if codice_interno not in driver_map_internal:
                    errors.append(f"Riga {i+2}: driver '{codice_interno}' non esistente")
                    skipped += 1
                    continue
                target_activity_id = driver_map_internal[codice_interno]  # Riuso campo per semplicità

            elif mapping_type == MappingType.ACCOUNT:
                # Per i conti contabili, usiamo cost_center come target
                if codice_interno not in cc_map_internal:
                    errors.append(f"Riga {i+2}: centro di costo '{codice_interno}' non esistente per mapping conto")
                    skipped += 1
                    continue
                target_cost_center_id = cc_map_internal[codice_interno]

            # Upsert: disattiva mappa precedente per lo stesso external_code e tipo
            existing_map = await db.execute(
                select(MappingRule).where(
                    MappingRule.hotel_id == hotel_id,
                    MappingRule.mapping_type == mapping_type,
                    MappingRule.external_code == codice_esterno,
                )
            )
            existing = existing_map.scalar_one_or_none()
            if existing:
                existing.is_active = False

            rule = MappingRule(
                hotel_id=hotel_id,
                mapping_type=mapping_type,
                external_code=codice_esterno,
                external_description=desc_esterna,
                target_cost_center_id=target_cost_center_id,
                target_activity_id=target_activity_id,
                target_service_id=target_service_id,
                is_active=True,
                confidence_score=attendibilita,
            )
            db.add(rule)
            imported += 1

        except Exception as e:
            errors.append(f"Riga {i+2}: {e}")
            skipped += 1

    await db.commit()

    # Crea DataImportLog
    status = "success" if not errors else "partial" if imported > 0 else "error"
    await _create_import_log(
        db, hotel_id, "mapping", "mapping_csv", file.filename,
        status, len(df), imported, errors
    )

    logger.info("Import mapping rules: %d regole importate, %d saltate", imported, skipped)

    return ImportResult(
        filename=file.filename,
        rows_read=len(df),
        rows_imported=imported,
        rows_skipped=skipped,
        errors=errors,
        warnings=warnings,
        import_batch_id=batch_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION (Pre-flight)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/validate",
    summary="Valida file prima dell'importazione",
)
async def validate_import_file(
    import_type: str = Form(..., description="accounting | payroll | revenues | mappings"),
    file: UploadFile = File(...),
    hotel_id: Optional[uuid.UUID] = Form(None, description="ID hotel per validazione contestuale"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analizza il file e restituisce errori/avvisi senza salvare nulla.
    """
    content = await file.read()
    try:
        df = _read_file(content, file.filename)
    except Exception as e:
        return {"valid": False, "errors": [f"Errore lettura file: {e}"], "warnings": []}

    warnings = []
    errors = []

    if import_type == "accounting":
        df = _normalize_columns(df, {
            "centro_di_costo": ["centro_di_costo", "cdc", "cost_center", "reparto"],
            "importo": ["importo", "amount", "valore"],
        })
        cc_map = await _load_cost_center_map(db, hotel_id) if hotel_id else await _load_cost_center_map(db)
        for i, row in enumerate(df.iter_rows(named=True)):
            cc_raw = str(row.get("centro_di_costo", "") or "").strip()
            if cc_raw and cc_raw not in cc_map:
                warnings.append(f"Riga {i+2}: Centro di costo '{cc_raw}' non censito. Verrà ignorato.")
            if not row.get("importo"):
                warnings.append(f"Riga {i+2}: Importo mancante o zero.")

    elif import_type == "payroll":
        df = _normalize_columns(df, {
            "matricola": ["matricola", "id"],
            "attivita": ["attivita", "attività", "activity"],
        })
        query = select(Activity)
        if hotel_id:
            query = query.where(Activity.hotel_id == hotel_id)
        act_q = await db.execute(query)
        act_map = {a.code for a in act_q.scalars().all()}

        for i, row in enumerate(df.iter_rows(named=True)):
            act_code = str(row.get("attivita", "") or "").strip()
            if act_code and act_code not in act_map:
                errors.append(f"Riga {i+2}: Attività '{act_code}' non trovata a sistema. Errore critico.")
            if not row.get("matricola"):
                warnings.append(f"Riga {i+2}: Matricola dipendente mancante.")

    elif import_type == "revenues":
        df = _normalize_columns(df, {
            "servizio": ["servizio", "service"],
        })
        query = select(Service)
        if hotel_id:
            query = query.where(Service.hotel_id == hotel_id)
        svc_q = await db.execute(query)
        svc_map = {s.code for s in svc_q.scalars().all()}
        for i, row in enumerate(df.iter_rows(named=True)):
            svc_code = str(row.get("servizio", "") or "").strip()
            if svc_code and svc_code not in svc_map:
                errors.append(f"Riga {i+2}: Servizio '{svc_code}' non censito.")

    elif import_type == "mappings":
        df = _normalize_columns(df, {
            "tipo_mapping": ["tipo_mapping", "mapping_type", "tipo"],
            "codice_esterno": ["codice_esterno", "external_code"],
            "codice_interno": ["codice_interno", "internal_code"],
        })
        valid_types = {"centro_di_costo", "attivita", "servizio", "driver", "conto_contabile"}
        for i, row in enumerate(df.iter_rows(named=True)):
            t = str(row.get("tipo_mapping", "") or "").strip().lower()
            if t and t not in valid_types:
                errors.append(f"Riga {i+2}: tipo_mapping '{t}' non valido")
            if not str(row.get("codice_esterno", "") or "").strip():
                warnings.append(f"Riga {i+2}: codice_esterno mancante")

    else:
        return {"valid": False, "errors": [f"Tipo import '{import_type}' non riconosciuto"], "warnings": []}

    return {
        "valid": len(errors) == 0,
        "filename": file.filename,
        "rows_count": len(df),
        "errors": errors,
        "warnings": warnings,
        "summary": f"Analizzate {len(df)} righe. {len(errors)} errori, {len(warnings)} avvisi."
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _load_cost_center_map(
    db: AsyncSession,
    hotel_id: Optional[uuid.UUID] = None,
) -> dict[str, uuid.UUID]:
    """Carica la mappa codice_cc → id per lookup veloce."""
    from sqlalchemy import select
    q = select(CostCenter)
    if hotel_id:
        q = q.where(CostCenter.hotel_id == hotel_id)
    result = await db.execute(q)
    return {cc.code: cc.id for cc in result.scalars().all()}