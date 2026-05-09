"""Periods, Employees, Allocations endpoints."""
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import AccountingPeriod

router = APIRouter()

class PeriodSchema(BaseModel):
    id: UUID
    year: int
    month: int
    name: str
    is_closed: bool
    class Config: from_attributes = True

class PeriodCreate(BaseModel):
    year: int
    month: int
    name: str

@router.get("/", response_model=List[PeriodSchema])
async def list_periods(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(AccountingPeriod).order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()))
    return q.scalars().all()

@router.post("/", response_model=PeriodSchema, status_code=201)
async def create_period(data: PeriodCreate, db: AsyncSession = Depends(get_db)):
    period = AccountingPeriod(**data.model_dump())
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period

@router.get("/{period_id}", response_model=PeriodSchema)
async def get_period(period_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await db.get(AccountingPeriod, period_id)
    if not p:
        raise HTTPException(404, "Periodo non trovato")
    return p
