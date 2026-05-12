"""
Hotel ABC Platform — Database Models
Tutti i modelli SQLAlchemy per l'ORM.
"""
from __future__ import annotations
import enum
import json
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Numeric, Text, Date, DateTime,
    ForeignKey, Enum as SAEnum, UniqueConstraint, Index,
    CheckConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator

from app.db.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM TYPES
# ─────────────────────────────────────────────────────────────────────────────

class JSONEncodedDict(TypeDecorator):
    """SQLAlchemy type for JSON encoding/decoding Python dicts.
    Compatible with SQLite via aiosqlite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class EncryptedString(TypeDecorator):
    """SQLAlchemy type for encrypting/decrypting string values.
    Uses Fernet symmetric encryption via EncryptionService."""
    impl = String
    cache_ok = True

    def __init__(self, length: int = 255, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.impl = String(length)

    def process_bind_param(self, value, dialect):
        """Encrypt value before sending to database."""
        if value is None:
            return None
        # Lazy import to avoid circular dependency
        from app.core.encryption import get_encryption_service
        try:
            return get_encryption_service().encrypt(value)
        except Exception as e:
            # In production, you might want to log this
            raise ValueError(f"Failed to encrypt value: {e}")

    def process_result_value(self, value, dialect):
        """Decrypt value after fetching from database."""
        if value is None:
            return None
        from app.core.encryption import get_encryption_service
        decrypted = get_encryption_service().decrypt(value)
        if decrypted is None:
            # If decryption fails (wrong key, tampered data), return None or raise
            # For now, return None to avoid breaking the app
            return None
        return decrypted


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class CostType(str, enum.Enum):
    LABOR = "personale"
    DIRECT = "diretto"
    OVERHEAD = "struttura"
    DEPRECIATION = "ammortamento"
    UTILITIES = "utilities"
    OTHER = "altro"


class DriverType(str, enum.Enum):
    VOLUME = "volume"       # n° transazioni, coperti, camere
    TIME = "time"           # ore lavorate, minuti per attività
    AREA = "area"           # mq dedicati
    PERCENTAGE = "percentage"  # % fissa
    COMPOSITE = "composite"   # mix di driver


class AllocationLevel(str, enum.Enum):
    COST_TO_ACTIVITY = "costo_ad_attivita"
    ACTIVITY_TO_SERVICE = "attivita_a_servizio"
    ACTIVITY_TO_ACTIVITY = "attivita_ad_attivita"  # ribaltamenti interni


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DIRECTOR = "direzione"
    MANAGER = "responsabile"
    ANALYST = "analista"
    VIEWER = "viewer"


class Department(str, enum.Enum):
    RECEPTION = "reception"
    HOUSEKEEPING = "housekeeping"
    FNB = "food_beverage"
    MAINTENANCE = "manutenzione"
    COMMERCIAL = "commerciale"
    CONGRESS = "congressi"
    DIRECTION = "direzione"
    ADMIN = "amministrazione"


class ServiceType(str, enum.Enum):
    ACCOMMODATION = "pernottamento"
    BREAKFAST = "colazione"
    RESTAURANT = "ristorazione"
    BAR = "bar"
    CONGRESS = "centro_congressi"
    PARKING = "parcheggio"
    SPA = "spa"
    OTHER = "altro"


class ExternalSystemType(str, enum.Enum):
    PMS_CSV = "pms_csv"
    PMS_API = "pms_api"
    ERP_CSV = "erp_csv"
    ERP_API = "erp_api"
    MANUAL = "manuale"


class MappingType(str, enum.Enum):
    COST_CENTER = "centro_di_costo"
    ACTIVITY = "attivita"
    SERVICE = "servizio"
    DRIVER = "driver"
    ACCOUNT = "conto_contabile"


# ─────────────────────────────────────────────────────────────────────────────
# MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# ─────────────────────────────────────────────────────────────────────────────
# HOTEL (TENANT)
# ─────────────────────────────────────────────────────────────────────────────

class Hotel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hotels"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    vat_number: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONEncodedDict, nullable=True)  # JSON config

    # relationships
    users: Mapped[List["User"]] = relationship(back_populates="hotel")
    periods: Mapped[List["AccountingPeriod"]] = relationship(back_populates="hotel")


# ─────────────────────────────────────────────────────────────────────────────
# UTENTI
# ─────────────────────────────────────────────────────────────────────────────

class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    hotel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), nullable=False, default=UserRole.VIEWER
    )
    department: Mapped[Optional[Department]] = mapped_column(
        SAEnum(Department), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    hotel: Mapped[Optional["Hotel"]] = relationship(back_populates="users")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PERIODO CONTABILE
# ─────────────────────────────────────────────────────────────────────────────

class AccountingPeriod(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "accounting_periods"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # es. "Gennaio 2025"
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # relationships
    cost_items: Mapped[List["CostItem"]] = relationship(back_populates="period")
    abc_results: Mapped[List["ABCResult"]] = relationship(back_populates="period")
    labor_allocations: Mapped[List["LaborAllocation"]] = relationship(
        back_populates="period"
    )
    hotel: Mapped["Hotel"] = relationship(back_populates="periods")

    __table_args__ = (
        UniqueConstraint("hotel_id", "year", "month", name="uq_periods_hotel_year_month"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_periods_month_range"),
        Index("ix_periods_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CENTRI DI COSTO
# ─────────────────────────────────────────────────────────────────────────────

class CostCenter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cost_centers"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[Department] = mapped_column(SAEnum(Department), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # relationships
    children: Mapped[List["CostCenter"]] = relationship("CostCenter")
    activities: Mapped[List["Activity"]] = relationship(back_populates="cost_center")
    cost_items: Mapped[List["CostItem"]] = relationship(back_populates="cost_center")

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_cost_centers_hotel_code"),
        Index("ix_cost_centers_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ATTIVITÀ OPERATIVE
# ─────────────────────────────────────────────────────────────────────────────

class Activity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "activities"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    department: Mapped[Department] = mapped_column(SAEnum(Department), nullable=False)
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    # Attività di supporto: i suoi costi vengono ribaltati su altre attività
    is_support_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Metadati ABC (output dell'analisi di processo)
    avg_duration_minutes: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    volume_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_drivers.id"), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)

    # relationships
    cost_center: Mapped[Optional["CostCenter"]] = relationship(back_populates="activities")
    volume_driver: Mapped[Optional["CostDriver"]] = relationship(
        "CostDriver", foreign_keys=[volume_driver_id]
    )
    labor_allocations: Mapped[List["LaborAllocation"]] = relationship(
        back_populates="activity"
    )
    allocation_rules_source: Mapped[List["AllocationRule"]] = relationship(
        "AllocationRule",
        primaryjoin="Activity.id == AllocationRule.source_activity_id",
    )
    allocation_rules_target: Mapped[List["AllocationRule"]] = relationship(
        "AllocationRule",
        primaryjoin="Activity.id == AllocationRule.target_activity_id",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_activities_hotel_code"),
        Index("ix_activities_department", "department"),
        Index("ix_activities_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SERVIZI OFFERTI
# ─────────────────────────────────────────────────────────────────────────────

class Service(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "services"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Revenue center di riferimento
    revenue_center: Mapped[Optional[str]] = mapped_column(String(100))
    # Unità di misura output (es. "notte", "coperto", "posto auto")
    output_unit: Mapped[Optional[str]] = mapped_column(String(50))

    # relationships
    abc_results: Mapped[List["ABCResult"]] = relationship(back_populates="service")
    allocation_rules_target: Mapped[List["AllocationRule"]] = relationship(
        "AllocationRule",
        primaryjoin="Service.id == AllocationRule.target_service_id",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_services_hotel_code"),
        Index("ix_services_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DRIVER DI ALLOCAZIONE
# ─────────────────────────────────────────────────────────────────────────────

class CostDriver(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cost_drivers"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    driver_type: Mapped[DriverType] = mapped_column(SAEnum(DriverType), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)  # ore, mq, n°, %
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_drivers_hotel_code"),
        Index("ix_drivers_hotel", "hotel_id"),
    )


class DriverValue(Base, UUIDMixin, TimestampMixin):
    """Valori effettivi dei driver per periodo."""
    __tablename__ = "driver_values"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_drivers.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    # Riferimento al soggetto (attività o servizio)
    entity_type: Mapped[str] = mapped_column(String(50))  # 'activity' | 'service'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))  # PMS, HR, manuale

    driver: Mapped["CostDriver"] = relationship()
    period: Mapped["AccountingPeriod"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "hotel_id", "driver_id", "period_id", "entity_type", "entity_id",
            name="uq_driver_values_key"
        ),
        Index("ix_driver_values_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# VOCI DI COSTO
# ─────────────────────────────────────────────────────────────────────────────

class CostItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cost_items"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    # Riferimento contabile
    account_code: Mapped[Optional[str]] = mapped_column(String(50))
    account_name: Mapped[Optional[str]] = mapped_column(String(200))
    cost_type: Mapped[CostType] = mapped_column(SAEnum(CostType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # Origine del dato
    source_system: Mapped[Optional[str]] = mapped_column(String(100))  # PMS, payroll, contabilità
    import_batch_id: Mapped[Optional[str]] = mapped_column(String(100))

    period: Mapped["AccountingPeriod"] = relationship(back_populates="cost_items")
    cost_center: Mapped[Optional["CostCenter"]] = relationship(back_populates="cost_items")

    __table_args__ = (
        Index("ix_cost_items_hotel", "hotel_id"),
        Index("ix_cost_items_period", "period_id"),
        Index("ix_cost_items_cost_center", "cost_center_id"),
        Index("ix_cost_items_cost_type", "cost_type"),
        CheckConstraint("amount != 0", name="ck_cost_items_nonzero"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ALLOCAZIONI PERSONALE
# ─────────────────────────────────────────────────────────────────────────────

class Employee(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "employees"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)  # es. "Receptionist"
    department: Mapped[Department] = mapped_column(SAEnum(Department), nullable=False)
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    contract_type: Mapped[Optional[str]] = mapped_column(String(50))
    hire_date: Mapped[Optional[date]] = mapped_column(Date)
    termination_date: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Costo orario lordo (comprensivo di oneri)
    hourly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    labor_allocations: Mapped[List["LaborAllocation"]] = relationship(
        back_populates="employee"
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "employee_code", name="uq_employees_hotel_code"),
        Index("ix_employees_hotel", "hotel_id"),
    )


class LaborAllocation(Base, UUIDMixin, TimestampMixin):
    """Ore e costi del personale allocati alle attività."""
    __tablename__ = "labor_allocations"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id"), nullable=False
    )
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    allocation_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False
    )  # % delle ore su quell'attività
    source: Mapped[str] = mapped_column(
        String(50), default="estimate"
    )  # estimate | timesheet | import

    period: Mapped["AccountingPeriod"] = relationship(back_populates="labor_allocations")
    employee: Mapped["Employee"] = relationship(back_populates="labor_allocations")
    activity: Mapped["Activity"] = relationship(back_populates="labor_allocations")

    __table_args__ = (
        Index("ix_labor_allocations_hotel", "hotel_id"),
        Index("ix_labor_allocations_period", "period_id"),
        CheckConstraint("hours > 0", name="ck_labor_hours_positive"),
        CheckConstraint(
            "allocation_pct > 0 AND allocation_pct <= 1",
            name="ck_labor_pct_range"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# REGOLE DI ALLOCAZIONE ABC
# ─────────────────────────────────────────────────────────────────────────────

class AllocationRule(Base, UUIDMixin, TimestampMixin):
    """
    Regole che definiscono come i costi fluiscono nel modello ABC.
    Supporta:
      - Costo (centro di costo) → Attività
      - Attività → Servizio
      - Attività → Attività (ribaltamento interno)
    """
    __tablename__ = "allocation_rules"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[AllocationLevel] = mapped_column(
        SAEnum(AllocationLevel), nullable=False
    )

    # Source
    source_cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    source_activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id"), nullable=True
    )

    # Target
    target_activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id"), nullable=True
    )
    target_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_allocation_rules_hotel_name"),
        Index("ix_allocation_rules_hotel", "hotel_id"),
    )

    # Driver
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_drivers.id"), nullable=True
    )
    # Se driver_id è NULL, usa allocation_pct fissa
    allocation_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 6), nullable=True
    )

    priority: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)

    driver: Mapped[Optional["CostDriver"]] = relationship()
    source_cost_center: Mapped[Optional["CostCenter"]] = relationship(
        "CostCenter", foreign_keys=[source_cost_center_id]
    )
    source_activity: Mapped[Optional["Activity"]] = relationship(
        "Activity", foreign_keys=[source_activity_id],
        back_populates="allocation_rules_source",
        overlaps="allocation_rules_target"
    )
    target_activity: Mapped[Optional["Activity"]] = relationship(
        "Activity", foreign_keys=[target_activity_id],
        back_populates="allocation_rules_target",
        overlaps="allocation_rules_source"
    )
    target_service: Mapped[Optional["Service"]] = relationship(
        "Service", foreign_keys=[target_service_id],
        back_populates="allocation_rules_target",
    )


# ─────────────────────────────────────────────────────────────────────────────
# RISULTATI ABC
# ─────────────────────────────────────────────────────────────────────────────

class ABCResult(Base, UUIDMixin, TimestampMixin):
    """Risultati del calcolo ABC per periodo/servizio/attività."""
    __tablename__ = "abc_results"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id"), nullable=True
    )

    # Costi per categoria
    direct_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    # Revenue
    revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    output_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )  # n° notti, coperti, ecc.

    # Margini
    gross_margin: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    margin_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )  # costo per notte, per coperto...

    # Metadata calcolo
    calculation_version: Mapped[int] = mapped_column(Integer, default=1)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    period: Mapped["AccountingPeriod"] = relationship(back_populates="abc_results")
    service: Mapped["Service"] = relationship(back_populates="abc_results")

    __table_args__ = (
        Index("ix_abc_results_hotel", "hotel_id"),
        Index("ix_abc_results_period_service", "period_id", "service_id"),
        UniqueConstraint(
            "hotel_id", "period_id", "service_id", "activity_id", "calculation_version",
            name="uq_abc_results_key"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# RICAVI PER SERVIZIO
# ─────────────────────────────────────────────────────────────────────────────

class ServiceRevenue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "service_revenues"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    output_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    source_system: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("hotel_id", "period_id", "service_id", name="uq_service_revenues_key"),
        Index("ix_service_revenues_hotel", "hotel_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRAZIONI E MAPPING
# ─────────────────────────────────────────────────────────────────────────────

class PMSIntegration(Base, UUIDMixin, TimestampMixin):
    """Configurazione dell'integrazione con i sistemi PMS esterni."""
    __tablename__ = "pms_integrations"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # es. "Zucchetti Hotel", "Mews Cloud"
    system_type: Mapped[ExternalSystemType] = mapped_column(
        SAEnum(ExternalSystemType), nullable=False
    )
    # Configurazione connessione
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(255))  # Per PMS_API
    api_key: Mapped[Optional[str]] = mapped_column(EncryptedString(255))      # Crittografato
    username: Mapped[Optional[str]] = mapped_column(String(100))
    password: Mapped[Optional[str]] = mapped_column(EncryptedString(100))     # Crittografato
    # Impostazioni
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_frequency_hours: Mapped[Optional[int]] = mapped_column(Integer, default=24)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Metadati
    config_data: Mapped[Optional[dict]] = mapped_column(JSONEncodedDict, nullable=True)  # JSON per impostazioni aggiuntive

    # relationships
    hotel: Mapped["Hotel"] = relationship()

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_pms_integrations_hotel_name"),
        Index("ix_pms_integrations_hotel", "hotel_id"),
    )


class DataImportLog(Base, UUIDMixin, TimestampMixin):
    """Log delle importazioni dati da sistemi esterni."""
    __tablename__ = "data_import_logs"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    import_type: Mapped[str] = mapped_column(String(50))  # accounting, payroll, pms
    source_system: Mapped[str] = mapped_column(String(100))
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))  # success, error, partial
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(Text)
    batch_id: Mapped[str] = mapped_column(String(100), unique=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class MappingRule(Base, UUIDMixin, TimestampMixin):
    """Regole per mappare codici esterni (PMS/ERP) verso entità ABC."""
    __tablename__ = "mapping_rules"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    mapping_type: Mapped[MappingType] = mapped_column(SAEnum(MappingType), nullable=False)
    external_code: Mapped[str] = mapped_column(String(100), nullable=False)
    external_description: Mapped[Optional[str]] = mapped_column(String(255))
     
    # Riferimento interno (uno solo di questi sarà popolato in base a mapping_type)
    target_cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_centers.id"))
    target_activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("activities.id"))
    target_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"))
     
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))  # per suggerimenti AI

    __table_args__ = (
        UniqueConstraint("hotel_id", "mapping_type", "external_code", name="uq_mapping_rules_key"),
        Index("ix_mapping_rules_hotel", "hotel_id"),
    )
