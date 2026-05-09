"""Employees endpoint."""
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.models import Employee

router = APIRouter()

class EmployeeSchema(BaseModel):
    id: UUID
    employee_code: str
    full_name: str
    role: str
    department: str
    hourly_cost: Optional[Decimal]
    is_active: bool
    class Config: from_attributes = True

@router.get("/", response_model=List[EmployeeSchema])
async def list_employees(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Employee).where(Employee.is_active == True))
    return q.scalars().all()
