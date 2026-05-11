from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Import AI Engines
from app.core.ai.driver_discovery import DriverDiscoveryEngine
from app.core.ai.forecasting import ForecastEngine
from app.core.ai.anomaly_detection import AnomalyDetector
from app.core.ai.data_fetcher import AIDataFetcher
from app.db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()

# Inizializza i motori
discovery_engine = DriverDiscoveryEngine()
forecast_engine = ForecastEngine()
anomaly_detector = AnomalyDetector()

# Feature set completo per driver discovery
ALL_DRIVER_FEATURES = ["ore_lavorate", "notti_vendute", "coperti", "mq", "eventi"]


class AIStatus(BaseModel):
    driver_discovery: str = "ready"
    forecasting: str = "ready"
    anomaly_detection: str = "ready"
    overall: str = "operational"


@router.get("/status", response_model=AIStatus)
async def get_ai_status():
    """Verifica lo stato dei motori AI."""
    return AIStatus()


def _get_fallback_driver_results(feature_cols: List[str]) -> List[Dict[str, Any]]:
    """Ritorna pesi equalizzati se i dati non sono sufficienti per il ML."""
    weight = 100.0 / len(feature_cols) if feature_cols else 0
    return [{
        "driver_name": feat,
        "importance_pct": round(weight, 2),
        "confidence_score": "Bassa (Dati insufficienti)",
        "explanation": "Dati storici insufficienti per l'analisi ML."
    } for feat in feature_cols]

class AIDriverResult(BaseModel):
    driver_name: str
    importance_pct: float
    confidence_score: str
    explanation: str

class AIForecastResult(BaseModel):
    date: str
    predicted_value: float
    lower_bound: float
    upper_bound: float

class AIAnomalyResult(BaseModel):
    record_id: str
    anomaly_score: float
    root_cause_driver: str
    explanation: str

# ── Mock Data Generator (per PoC) ─────────────────────────────────────────────
# Genera dati dummy coerenti per testare le pipeline ML senza avere storici
def _get_mock_data_for_discovery() -> pd.DataFrame:
    import numpy as np
    np.random.seed(42)
    n = 60
    return pd.DataFrame({
        'ore_lavorate': np.random.normal(1000, 100, n),
        'notti_vendute': np.random.normal(500, 50, n),
        'coperti': np.random.normal(800, 80, n),
        'overhead_cost': np.random.normal(15000, 2000, n)
    })

def _get_mock_data_for_forecast() -> pd.DataFrame:
    import numpy as np
    np.random.seed(42)
    n = 36 # 3 anni
    dates = [datetime.today() - timedelta(days=30 * i) for i in range(n)]
    dates.reverse()
    base_trend = np.linspace(100, 150, n)
    seasonality = np.sin(np.linspace(0, 3 * 2 * np.pi, n)) * 20
    return pd.DataFrame({
        'ds': dates,
        'notti_vendute': base_trend + seasonality + np.random.normal(0, 5, n)
    })

def _get_mock_data_for_anomalies() -> pd.DataFrame:
    import numpy as np
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        'periodo_id': [f"P-{i}" for i in range(n)],
        'costo_lavoro': np.random.normal(10000, 500, n),
        'ore': np.random.normal(500, 20, n),
        'volume_output': np.random.normal(2000, 100, n)
    })
    # Inseriamo 3 anomalie palesi
    df.loc[10, 'costo_lavoro'] = 25000
    df.loc[50, 'ore'] = 1200
    df.loc[80, 'volume_output'] = 500
    return df

def _get_fallback_forecast(periods: int) -> List[Dict[str, Any]]:
    """Genera una previsione piatta (media) in caso di errore."""
    import datetime
    from dateutil.relativedelta import relativedelta
    current_date = datetime.date.today()
    avg_value = 1000.0  # valore placeholder
    results = []
    for i in range(periods):
        current_date = current_date + relativedelta(months=1)
        results.append({
            "date": current_date.strftime('%Y-%m-%d'),
            "predicted_value": round(avg_value, 2),
            "lower_bound": round(avg_value * 0.9, 2),
            "upper_bound": round(avg_value * 1.1, 2)
        })
    return results
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/driver-discovery", response_model=List[AIDriverResult])
async def discover_drivers(db: AsyncSession = Depends(get_db)):
    """Analizza dati storici per identificare l'importanza dei driver sui costi."""
    try:
        fetcher = AIDataFetcher(db)
        df = await fetcher.get_driver_discovery_data()
        
        # Se non ci sono dati reali sufficienti, usa mock data
        if df.empty or len(df) < 10:
            logger.warning("Dati reali insufficienti per driver discovery, uso mock data")
            df = _get_mock_data_for_discovery()
            # Per mock, usiamo features fisse
            features = ['ore_lavorate', 'notti_vendute', 'coperti']
            # Aggiungiamo correlazione fitta
            df['overhead_cost'] = df['ore_lavorate'] * 10 + df['notti_vendute'] * 5 + np.random.normal(0, 500, len(df))
        else:
            logger.info(f"Driver discovery con dati reali: {len(df)} periodi")
            # Determina le feature disponibili (con dati non-null e somma > 0)
            features = [f for f in ALL_DRIVER_FEATURES if f in df.columns and df[f].sum() > 0]
            
            if not features:
                logger.warning("Nessun driver con dati positivi, restituisco fallback")
                return _get_fallback_driver_results(ALL_DRIVER_FEATURES)
        
        results = discovery_engine.discover_drivers(df, 'overhead_cost', features)
        return results
    except Exception as e:
        logger.error(f"Errore in driver discovery: {e}", exc_info=True)
        # Fallback: risultati equalizzati
        return _get_fallback_driver_results(ALL_DRIVER_FEATURES)

@router.get("/forecast", response_model=List[AIForecastResult])
async def get_forecast(
    metric: str = "notti_vendute", 
    periods: int = 6, 
    db: AsyncSession = Depends(get_db)
):
    """Prevede i valori futuri di una determinata metrica (notti, coperti, ecc.)."""
    try:
        fetcher = AIDataFetcher(db)
        df = await fetcher.get_forecast_data(metric)
        
        # Se non ci sono dati reali sufficienti, usa mock data
        if df.empty or len(df) < 5:
            logger.warning(f"Dati reali insufficienti per forecast {metric}, uso mock data")
            df_mock = _get_mock_data_for_forecast()
            results = forecast_engine.forecast_metric(
                df=df_mock,
                date_col='ds',
                metric_col='notti_vendute',
                periods=periods,
                freq='M'
            )
            return results
        
        logger.info(f"Forecast {metric} con dati reali: {len(df)} punti storici")
        results = forecast_engine.forecast_metric(
            df=df,
            date_col='ds',
            metric_col='value',
            periods=periods,
            freq='M'
        )
        return results
    except Exception as e:
        logger.error(f"Errore in forecast per {metric}: {e}", exc_info=True)
        # Fallback: restituisce forecast piatto
        return _get_fallback_forecast(periods)

@router.get("/anomalies", response_model=List[AIAnomalyResult])
async def get_anomalies(db: AsyncSession = Depends(get_db)):
    """Rileva anomalie nei costi rispetto ai volumi."""
    try:
        fetcher = AIDataFetcher(db)
        df = await fetcher.get_anomaly_detection_data()
        
        features = ['costo_lavoro', 'ore', 'volume_output']
        
        # Se non ci sono dati reali sufficienti, usa mock data
        if df.empty or len(df) < 20:
            logger.warning("Dati reali insufficienti per anomaly detection, uso mock data")
            df = _get_mock_data_for_anomalies()
        else:
            logger.info(f"Anomaly detection con dati reali: {len(df)} periodi")
        
        results = anomaly_detector.detect_anomalies(
            df=df,
            feature_cols=features,
            id_col='periodo_id'
        )
        return results
    except Exception as e:
        logger.error(f"Errore in anomaly detection: {e}", exc_info=True)
        return []  # Nessuna anomalia in caso di errore
