"""CRUD Cost Centers — Gestione centri di costo."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import CostCenter, Department, Hotel, User
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


def enforce_hotel_access(current_user: User, requested_hotel_id: Optional[UUID]) -> UUID:
    """Verifica che l'utente possa accedere all'hotel richiesto."""
    if requested_hotel_id is None:
        if current_user.hotel_id is None:
            raise HTTPException(status_code=403, detail="Utente non associato ad alcun hotel")
        return current_user.hotel_id
    if current_user.hotel_id != requested_hotel_id:
        raise HTTPException(status_code=403, detail="Accesso non consentito a questo hotel")
    return requested_hotel_id


class CostCenterSchema(BaseModel):
    id: UUID
    hotel_id: UUID
    code: str
    name: str
    department: str
    parent_id: Optional[UUID] = None
    is_active: bool
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CostCenterCreate(BaseModel):
    hotel_id: UUID
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    department: str
    parent_id: Optional[UUID] = None
    description: Optional[str] = None


class CostCenterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    department: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


@router.get("/", response_model=List[CostCenterSchema])
async def list_cost_centers(
    hotel_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_hotel_id = enforce_hotel_access(current_user, hotel_id)
    q = select(CostCenter).where(CostCenter.hotel_id == effective_hotel_id)
    if is_active is not None:
        q = q.where(CostCenter.is_active == is_active)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{center_id}", response_model=CostCenterSchema)
async def get_cost_center(center_id: UUID, db: AsyncSession = Depends(get_db)):
    cc = await db.get(CostCenter, center_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro di costo non trovato")
    return cc


@router.post("/", response_model=CostCenterSchema, status_code=201)
async def create_cost_center(
    data: CostCenterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Forza hotel_id dall'utente (non consentito specificare hotel diverso)
    effective_hotel_id = enforce_hotel_access(current_user, data.hotel_id)

    # Valida department
    try:
        dept = Department(data.department)
    except ValueError:
        valid = [d.value for d in Department]
        raise HTTPException(status_code=400, detail=f"Department non valido: {valid}")

    # Verifica unicità codice per hotel
    existing = await db.execute(
        select(CostCenter).where(
            CostCenter.hotel_id == effective_hotel_id,
            CostCenter.code == data.code,
            CostCenter.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Esiste già un centro di costo attivo con codice '{data.code}' per questo hotel",
        )

    cc = CostCenter(
        hotel_id=effective_hotel_id,
        code=data.code,
        name=data.name,
        department=dept,
        parent_id=data.parent_id,
        description=data.description,
        is_active=True,
    )
    db.add(cc)
    await db.commit()
    await db.refresh(cc)
    return cc


@router.put("/{center_id}", response_model=CostCenterSchema)
async def update_cost_center(
    center_id: UUID,
    data: CostCenterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cc = await db.get(CostCenter, center_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro di costo non trovato")

    # Verifica accesso
    if cc.hotel_id != current_user.hotel_id:
        raise HTTPException(status_code=403, detail="Accesso non consentito a questo hotel")

    update_data = data.model_dump(exclude_unset=True)

    if 'department' in update_data:
        try:
            update_data['department'] = Department(update_data['department'])
        except ValueError:
            valid = [d.value for d in Department]
            raise HTTPException(status_code=400, detail=f"Department non valido: {valid}")

    for key, value in update_data.items():
        setattr(cc, key, value)

    await db.commit()
    await db.refresh(cc)
    return cc


@router.delete("/{center_id}", status_code=204)
async def delete_cost_center(
    center_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cc = await db.get(CostCenter, center_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro di costo non trovato")
    if cc.hotel_id != current_user.hotel_id:
        raise HTTPException(status_code=403, detail="Accesso non consentito a questo hotel")
    cc.is_active = False
    await db.commit()
    return None
