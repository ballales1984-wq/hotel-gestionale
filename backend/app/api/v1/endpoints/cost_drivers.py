"""CRUD Cost Drivers — Gestione driver di allocazione (es. ore, mq, coperti)."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import CostDriver, DriverType, Hotel

router = APIRouter()


class CostDriverSchema(BaseModel):
    id: UUID
    hotel_id: UUID
    name: str
    code: str
    driver_type: str
    unit: str
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class CostDriverCreate(BaseModel):
    hotel_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=30)
    driver_type: str
    unit: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class CostDriverUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = Field(None, min_length=1, max_length=30)
    driver_type: Optional[str] = None
    unit: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[CostDriverSchema])
async def list_cost_drivers(
    hotel_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
):
    q = select(CostDriver)
    if hotel_id:
        q = q.where(CostDriver.hotel_id == hotel_id)
    if is_active is not None:
        q = q.where(CostDriver.is_active == is_active)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{driver_id}", response_model=CostDriverSchema)
async def get_cost_driver(driver_id: UUID, db: AsyncSession = Depends(get_db)):
    driver = await db.get(CostDriver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver non trovato")
    return driver


@router.post("/", response_model=CostDriverSchema, status_code=201)
async def create_cost_driver(data: CostDriverCreate, db: AsyncSession = Depends(get_db)):
    # Verifica hotel
    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel non trovato")

    # Valida driver_type
    try:
        dtype = DriverType(data.driver_type)
    except ValueError:
        valid = [d.value for d in DriverType]
        raise HTTPException(status_code=400, detail=f"Tipo driver non valido: {valid}")

    # Verifica unicità codice per hotel
    existing = await db.execute(
        select(CostDriver).where(
            CostDriver.hotel_id == data.hotel_id,
            CostDriver.code == data.code,
            CostDriver.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Esiste già un driver attivo con codice '{data.code}' per questo hotel",
        )

    driver = CostDriver(
        hotel_id=data.hotel_id,
        name=data.name,
        code=data.code,
        driver_type=dtype,
        unit=data.unit,
        description=data.description,
        is_active=True,
    )
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.put("/{driver_id}", response_model=CostDriverSchema)
async def update_cost_driver(
    driver_id: UUID,
    data: CostDriverUpdate,
    db: AsyncSession = Depends(get_db),
):
    driver = await db.get(CostDriver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver non trovato")

    update_data = data.model_dump(exclude_unset=True)

    if 'driver_type' in update_data:
        try:
            update_data['driver_type'] = DriverType(update_data['driver_type'])
        except ValueError:
            valid = [d.value for d in DriverType]
            raise HTTPException(status_code=400, detail=f"Tipo driver non valido: {valid}")

    for key, value in update_data.items():
        setattr(driver, key, value)

    await db.commit()
    await db.refresh(driver)
    return driver


@router.delete("/{driver_id}", status_code=204)
async def delete_cost_driver(driver_id: UUID, db: AsyncSession = Depends(get_db)):
    driver = await db.get(CostDriver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver non trovato")
    driver.is_active = False
    await db.commit()
    return None
