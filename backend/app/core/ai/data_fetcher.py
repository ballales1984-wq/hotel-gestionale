"""
AI Data Fetcher — Estrae dati storici dal database per i motori AI.
Fornisce dataset pronti per driver discovery, forecasting e anomaly detection.
"""
import logging
from typing import Optional, Dict, List
from uuid import UUID
import pandas as pd
from sqlalchemy import select, func, and_
from sqlalchemy.sql import case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AccountingPeriod, DriverValue, CostDriver, ABCResult,
    CostItem, CostType, LaborAllocation, Service, ServiceType
)

logger = logging.getLogger(__name__)


class AIDataFetcher:
    """Gestisce l'estrazione di dati storici per le analisi AI."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_driver_discovery_data(
        self,
        hotel_id: UUID,
        target: str = "overhead_cost"
    ) -> pd.DataFrame:
        """
        Estrae dati aggregati per periodo per il driver discovery, filtrati per hotel.

        Args:
            hotel_id: UUID dell'hotel per cui estrarre i dati.
            target: metrica target da discovery (default overhead_cost).

        Returns:
            DataFrame con colonne: period_id, year, month,
            ore_lavorate, notti_vendute, coperti, mq, eventi, overhead_cost
        """
        from app.models.models import CostDriver, Service, ServiceType, DriverValue, ABCResult

        # Query con subselect scalari per evitare cross-join, filtrate per hotel_id
        stmt = select(
            AccountingPeriod.id.label("period_id"),
            AccountingPeriod.year,
            AccountingPeriod.month,
            # Ore lavorate: somma driver DVR-ORE per periodo
            select(func.coalesce(func.sum(DriverValue.value), 0)).where(
                and_(
                    DriverValue.period_id == AccountingPeriod.id,
                    CostDriver.id == DriverValue.driver_id,
                    CostDriver.code == "DRV-ORE",
                    DriverValue.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("ore_lavorate"),
            # Notti vendute: somma output_volume per servizi accommodation (filtrato per hotel)
            select(func.coalesce(func.sum(ABCResult.output_volume), 0)).where(
                and_(
                    ABCResult.period_id == AccountingPeriod.id,
                    Service.id == ABCResult.service_id,
                    Service.service_type == ServiceType.ACCOMMODATION,
                    ABCResult.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("notti_vendute"),
            # Coperti: somma output_volume per servizi ristorazione/colazione
            select(func.coalesce(func.sum(ABCResult.output_volume), 0)).where(
                and_(
                    ABCResult.period_id == AccountingPeriod.id,
                    Service.id == ABCResult.service_id,
                    Service.service_type.in_([ServiceType.RESTAURANT, ServiceType.BREAKFAST]),
                    ABCResult.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("coperti"),
            # MQ: somma driver DVR-MQ
            select(func.coalesce(func.sum(DriverValue.value), 0)).where(
                and_(
                    DriverValue.period_id == AccountingPeriod.id,
                    CostDriver.id == DriverValue.driver_id,
                    CostDriver.code == "DRV-MQ",
                    DriverValue.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("mq"),
            # Eventi: somma output_volume per servizi congressi
            select(func.coalesce(func.sum(ABCResult.output_volume), 0)).where(
                and_(
                    ABCResult.period_id == AccountingPeriod.id,
                    Service.id == ABCResult.service_id,
                    Service.service_type == ServiceType.CONGRESS,
                    ABCResult.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("eventi"),
            # Overhead cost: somma overhead_cost da abc_results
            select(func.coalesce(func.sum(ABCResult.overhead_cost), 0)).where(
                and_(
                    ABCResult.period_id == AccountingPeriod.id,
                    ABCResult.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("overhead_cost")
        ).select_from(AccountingPeriod)
        # Filtra AccountingPeriod per hotel_id (tutti i periodi dell'hotel)
        stmt = stmt.where(AccountingPeriod.hotel_id == hotel_id)
        stmt = stmt.order_by(AccountingPeriod.year, AccountingPeriod.month)

        result = await self.db.execute(stmt)
        rows = result.all()
        
        if not rows:
            logger.warning("Nessun dato trovato per driver discovery")
            return pd.DataFrame()
        
        # Converti a DataFrame
        df = pd.DataFrame(rows, columns=[
            "period_id", "year", "month", "ore_lavorate", "notti_vendute",
            "coperti", "mq", "eventi", "overhead_cost"
        ])
        
        # Assicura tipi numerici
        numeric_cols = ["ore_lavorate", "notti_vendute", "coperti", "mq", "eventi", "overhead_cost"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        logger.info(f"Driver discovery: estratti {len(df)} periodi storici")
        return df
    
    async def get_forecast_data(
        self,
        hotel_id: UUID,
        metric: str = "notti_vendute"
    ) -> pd.DataFrame:
        """
        Estrae serie storica per forecasting, filtrata per hotel.

        Args:
            hotel_id: UUID dell'hotel.
            metric: 'notti_vendute', 'coperti', 'ore_lavorate', 'eventi', etc.

        Returns:
            DataFrame con colonne: ds (date), y (valore metric)
        """
        # Mappa metriche a colonne ABCResult o driver_values
        if metric == "notti_vendute":
            # Somma output_volume per servizi accommodation per periodo, filtrato per hotel
            stmt = select(
                AccountingPeriod.id,
                AccountingPeriod.year,
                AccountingPeriod.month,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Service.service_type == ServiceType.ACCOMMODATION,
                                ABCResult.output_volume
                            ),
                            else_=0
                        )
                    ), 0
                ).label("value")
            ).select_from(AccountingPeriod)
            stmt = stmt.join(
                ABCResult, AccountingPeriod.id == ABCResult.period_id, isouter=True
            ).join(
                Service, ABCResult.service_id == Service.id, isouter=True
            )
            stmt = stmt.where(ABCResult.hotel_id == hotel_id)
            stmt = stmt.group_by(AccountingPeriod.id, AccountingPeriod.year, AccountingPeriod.month)

        elif metric == "coperti":
            stmt = select(
                AccountingPeriod.id,
                AccountingPeriod.year,
                AccountingPeriod.month,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Service.service_type.in_([ServiceType.RESTAURANT, ServiceType.BREAKFAST]),
                                ABCResult.output_volume
                            ),
                            else_=0
                        )
                    ), 0
                ).label("value")
            ).select_from(AccountingPeriod)
            stmt = stmt.join(
                ABCResult, AccountingPeriod.id == ABCResult.period_id, isouter=True
            ).join(
                Service, ABCResult.service_id == Service.id, isouter=True
            )
            stmt = stmt.where(ABCResult.hotel_id == hotel_id)
            stmt = stmt.group_by(AccountingPeriod.id, AccountingPeriod.year, AccountingPeriod.month)

        elif metric == "ore_lavorate":
            # Ore da driver_values con driver DVR-ORE su attività, filtrate per hotel
            stmt = select(
                AccountingPeriod.id,
                AccountingPeriod.year,
                AccountingPeriod.month,
                func.coalesce(
                    func.sum(
                        case(
                            (CostDriver.code == "DRV-ORE", DriverValue.value),
                            else_=0
                        )
                    ), 0
                ).label("value")
            ).select_from(AccountingPeriod)
            stmt = stmt.join(
                DriverValue, AccountingPeriod.id == DriverValue.period_id, isouter=True
            ).join(
                CostDriver, DriverValue.driver_id == CostDriver.id, isouter=True
            )
            stmt = stmt.where(DriverValue.hotel_id == hotel_id)
            stmt = stmt.group_by(AccountingPeriod.id, AccountingPeriod.year, AccountingPeriod.month)

        elif metric == "eventi":
            stmt = select(
                AccountingPeriod.id,
                AccountingPeriod.year,
                AccountingPeriod.month,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Service.service_type == ServiceType.CONGRESS,
                                ABCResult.output_volume
                            ),
                            else_=0
                        )
                    ), 0
                ).label("value")
            ).select_from(AccountingPeriod)
            stmt = stmt.join(
                ABCResult, AccountingPeriod.id == ABCResult.period_id, isouter=True
            ).join(
                Service, ABCResult.service_id == Service.id, isouter=True
            )
            stmt = stmt.where(ABCResult.hotel_id == hotel_id)
            stmt = stmt.group_by(AccountingPeriod.id, AccountingPeriod.year, AccountingPeriod.month)
        else:
            raise ValueError(f"Metrica non supportata: {metric}")

        # Filtra per hotel_id nei periodi (tutti i periodi sono già filtrati per hotel nelle join delle tabelle principali,
        # ma per sicurezza aggiungiamo anche il filtro su AccountingPeriod se necessario)
        # Nota: le join con ABCResult/DriverValue già filtrano per hotel. Aggiungiamo anche qui per sicurezza.
        stmt = stmt.where(AccountingPeriod.hotel_id == hotel_id)

        stmt = stmt.order_by(AccountingPeriod.year, AccountingPeriod.month)
        result = await self.db.execute(stmt)
        rows = result.all()
        
        if not rows:
            logger.warning(f"Nessun dato trovato per forecasting metric: {metric}")
            return pd.DataFrame()
        
        # Costruisci DataFrame
        df = pd.DataFrame(rows, columns=["period_id", "year", "month", "value"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
        
        # Crea colonna ds come data (usa primo giorno del mese)
        df["ds"] = pd.to_datetime(
            df[["year", "month"]].assign(day=1)
        )
        
        logger.info(f"Forecast {metric}: estratti {len(df)} punti storici")
        return df[["ds", "value"]]
    
    async def get_anomaly_detection_data(self, hotel_id: UUID) -> pd.DataFrame:
        """
        Estrae features per anomaly detection, filtrate per hotel:
        costi lavoro, ore, volume output per periodo.

        Args:
            hotel_id: UUID dell'hotel.

        Returns:
            DataFrame con colonne: periodo_id, costo_lavoro, ore, volume_output
        """
        from app.models.models import CostType

        # Usa subquery scalari per evitare cross-join multiplication, con filtri per hotel
        stmt = select(
            AccountingPeriod.id.label("periodo_id"),
            AccountingPeriod.year,
            AccountingPeriod.month,
            # Costo del lavoro: somma cost_items con cost_type = LABOR, filtrato per hotel
            select(func.coalesce(func.sum(CostItem.amount), 0)).where(
                and_(
                    CostItem.period_id == AccountingPeriod.id,
                    CostItem.cost_type == CostType.LABOR,
                    CostItem.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("costo_lavoro"),
            # Ore totali: somma ore da labor_allocations, filtrate per hotel
            select(func.coalesce(func.sum(LaborAllocation.hours), 0)).where(
                and_(
                    LaborAllocation.period_id == AccountingPeriod.id,
                    LaborAllocation.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("ore"),
            # Volume output totale: somma output_volume da abc_results, filtrato per hotel
            select(func.coalesce(func.sum(ABCResult.output_volume), 0)).where(
                and_(
                    ABCResult.period_id == AccountingPeriod.id,
                    ABCResult.hotel_id == hotel_id,
                )
            ).scalar_subquery().label("volume_output")
        ).select_from(AccountingPeriod)
        # Filtra AccountingPeriod per hotel_id
        stmt = stmt.where(AccountingPeriod.hotel_id == hotel_id)
        stmt = stmt.order_by(AccountingPeriod.year, AccountingPeriod.month)

        result = await self.db.execute(stmt)
        rows = result.all()
        
        if not rows:
            logger.warning("Nessun dato trovato per anomaly detection")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["periodo_id", "year", "month", "costo_lavoro", "ore", "volume_output"])
        numeric_cols = ["costo_lavoro", "ore", "volume_output"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        logger.info(f"Anomaly detection: estratti {len(df)} periodi")
        return df
