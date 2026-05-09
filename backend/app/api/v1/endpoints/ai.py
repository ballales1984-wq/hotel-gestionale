from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import pandas as pd
from datetime import datetime, timedelta

# Import AI Engines
from app.core.ai.driver_discovery import DriverDiscoveryEngine
from app.core.ai.forecasting import ForecastEngine
from app.core.ai.anomaly_detection import AnomalyDetector

router = APIRouter()

# Inizializza i motori
discovery_engine = DriverDiscoveryEngine()
forecast_engine = ForecastEngine()
anomaly_detector = AnomalyDetector()

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
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/driver-discovery", response_model=List[AIDriverResult])
async def discover_drivers():
    """Analizza dati storici per identificare l'importanza dei driver sui costi."""
    df = _get_mock_data_for_discovery()
    # Immaginiamo di voler prevedere l'overhead_cost in base a ore, notti e coperti
    features = ['ore_lavorate', 'notti_vendute', 'coperti']
    
    # Aggiungiamo un po' di correlazione finta per far lavorare il modello
    df['overhead_cost'] = df['ore_lavorate'] * 10 + df['notti_vendute'] * 5 + np.random.normal(0, 500, 60)
    
    results = discovery_engine.discover_drivers(df, 'overhead_cost', features)
    return results

@router.get("/forecast", response_model=List[AIForecastResult])
async def get_forecast(metric: str = 'notti_vendute', periods: int = 6):
    """Prevede i valori futuri di una determinata metrica (notti, coperti, ecc.)."""
    df = _get_mock_data_for_forecast()
    
    results = forecast_engine.forecast_metric(
        df=df,
        date_col='ds',
        metric_col='notti_vendute',
        periods=periods,
        freq='M'
    )
    return results

@router.get("/anomalies", response_model=List[AIAnomalyResult])
async def get_anomalies():
    """Rileva anomalie nei costi rispetto ai volumi."""
    df = _get_mock_data_for_anomalies()
    features = ['costo_lavoro', 'ore', 'volume_output']
    
    results = anomaly_detector.detect_anomalies(
        df=df,
        feature_cols=features,
        id_col='periodo_id'
    )
    return results
