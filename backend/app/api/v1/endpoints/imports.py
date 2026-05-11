"""
API Imports — Import dati da CSV/Excel (payroll, contabilità, PMS).
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import (
    AccountingPeriod, CostCenter, CostItem, CostType,
    Employee, LaborAllocation, Department, Service, ServiceRevenue,
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


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT CONTABILITÀ (Costi)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/accounting",
    response_model=ImportResult,
    summary="Import voci di costo da CSV/Excel",
    description=(
        "Importa le voci di costo dalla contabilità analitica. "
        "Il file deve avere le colonne: conto, descrizione, centro_di_costo, tipo_costo, importo"
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

    # Mappa centri di costo
    cc_map = await _load_cost_center_map(db)

        for i, row in enumerate(df.iter_rows(named=True)):
            try:
                amount = Decimal(str(row.get("importo", 0) or 0))
                if amount == 0:
                    warnings.append(f"Riga {i+2}: importo zero, saltata")
                    skipped += 1
                    continue

                cc_id = None
                cc_raw = str(row.get("centro_di_costo", "") or "").strip()
                if cc_raw and cc_raw in cc_map:
                    cc_id = cc_map[cc_raw]
                elif cc_raw:
                    warnings.append(
                        f"Riga {i+2}: centro di costo '{cc_raw}' non trovato"
                    )

                cost_type_raw = str(row.get("tipo_costo", "") or "").lower().strip()
                cost_type = _map_cost_type(cost_type_raw)

                cost_item = CostItem(
                    period_id=period_id,
                    hotel_id=period.hotel_id,
                    cost_center_id=cc_id,
                    account_code=str(row.get("conto", "") or "")[:50] or None,
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

    # Carica mappa dipendenti e attività
    from sqlalchemy import select
    from app.models.models import Activity

    employees_q = await db.execute(select(Employee))
    emp_map = {e.employee_code: e for e in employees_q.scalars().all()}

    activities_q = await db.execute(select(Activity))
    act_map = {a.code: a for a in activities_q.scalars().all()}

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

            # Trova o crea dipendente
            emp = emp_map.get(matricola)
            if not emp:
                nome = str(row.get("nome", f"Dipendente {matricola}") or "")
                emp = Employee(
                    employee_code=matricola,
                    full_name=nome[:255],
                    role="N/D",
                    department=Department.ADMIN,
                    hourly_cost=costo_orario,
                )
                db.add(emp)
                await db.flush()
                emp_map[matricola] = emp
                warnings.append(f"Riga {i+2}: dipendente '{matricola}' creato automaticamente")

            # Trova attività
            act = act_map.get(act_code)
            if not act:
                errors.append(f"Riga {i+2}: attività '{act_code}' non trovata")
                skipped += 1
                continue

            labor = LaborAllocation(
                period_id=period_id,
                hotel_id=period.hotel_id,
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
    description="Importa i ricavi per servizio dal PMS o manualmente.",
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

    from sqlalchemy import select
    services_q = await db.execute(select(Service))
    svc_map = {s.code: s for s in services_q.scalars().all()}

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
            if not svc:
                errors.append(f"Riga {i+2}: servizio '{svc_code}' non trovato")
                skipped += 1
                continue

            # Upsert
            from sqlalchemy import delete
            await db.execute(
                delete(ServiceRevenue).where(
                    ServiceRevenue.period_id == period_id,
                    ServiceRevenue.service_id == svc.id,
                )
            )

            rev = ServiceRevenue(
                period_id=period_id,
                hotel_id=period.hotel_id,
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
# UTILITY FUNCTIONS
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
        if key in raw:
            return val
    return CostType.OTHER


async def _load_cost_center_map(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Carica la mappa codice_cc → id per lookup veloce."""
    from sqlalchemy import select
    q = await db.execute(select(CostCenter))
    return {cc.code: cc.id for cc in q.scalars().all()}


# ─────────────────────────────────────────────────────────────────────────────
# PRE-FLIGHT VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/validate",
    summary="Valida file prima dell'importazione",
)
async def validate_import_file(
    import_type: str = Form(..., description="accounting | payroll | revenues"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Analizza il file e restituisce errori/avvisi senza salvare nulla.
    Utile per verificare se i codici (CDC, Attività) sono censiti nel sistema.
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
        cc_map = await _load_cost_center_map(db)
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
        from sqlalchemy import select
        from app.models.models import Activity
        act_q = await db.execute(select(Activity))
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
        from sqlalchemy import select
        from app.models.models import Service
        svc_q = await db.execute(select(Service))
        svc_map = {s.code for s in svc_q.scalars().all()}
        for i, row in enumerate(df.iter_rows(named=True)):
            svc_code = str(row.get("servizio", "") or "").strip()
            if svc_code and svc_code not in svc_map:
                errors.append(f"Riga {i+2}: Servizio '{svc_code}' non censito.")

    return {
        "valid": len(errors) == 0,
        "filename": file.filename,
        "rows_count": len(df),
        "errors": errors,
        "warnings": warnings,
        "summary": f"Analizzate {len(df)} righe. {len(errors)} errori, {len(warnings)} avvisi."
    }
