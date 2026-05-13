"""CRUD Cost Centers — Gestione centri di costo."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import CostCenter, Department, Hotel

router = APIRouter()


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
):
    q = select(CostCenter)
    if hotel_id:
        q = q.where(CostCenter.hotel_id == hotel_id)
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
async def create_cost_center(data: CostCenterCreate, db: AsyncSession = Depends(get_db)):
    # Verifica hotel esiste
    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel non trovato")

    # Valida department
    try:
        dept = Department(data.department)
    except ValueError:
        valid = [d.value for d in Department]
        raise HTTPException(status_code=400, detail=f"Department non valido: {valid}")

    # Verifica unicità codice per hotel
    existing = await db.execute(
        select(CostCenter).where(
            CostCenter.hotel_id == data.hotel_id,
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
        hotel_id=data.hotel_id,
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
):
    cc = await db.get(CostCenter, center_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro di costo non trovato")

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
async def delete_cost_center(center_id: UUID, db: AsyncSession = Depends(get_db)):
    cc = await db.get(CostCenter, center_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro di costo non trovato")
    cc.is_active = False
    await db.commit()
    return None
