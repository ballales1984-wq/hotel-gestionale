"""CRUD Costs, Periods, Employees, Allocations."""
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import CostItem, CostType

router = APIRouter()

class CostItemSchema(BaseModel):
    id: UUID
    period_id: UUID
    account_code: Optional[str]
    account_name: Optional[str]
    cost_type: str
    amount: Decimal
    class Config: from_attributes = True

@router.get("/{period_id}", response_model=List[CostItemSchema])
async def list_costs(period_id: UUID, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(CostItem).where(CostItem.period_id == period_id))
    return q.scalars().all()
