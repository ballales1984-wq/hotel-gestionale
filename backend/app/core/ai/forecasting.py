"""
AI / ML Engine — Forecasting
Usa Prophet per la previsione di volumi (notti, coperti) e costi futuri,
supportando la stagionalità tipica del settore alberghiero.
"""
import logging
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd
from prophet import Prophet

logger = logging.getLogger(__name__)

class ForecastEngine:
    """Motore di previsione basato su Prophet."""

    def __init__(self):
        self.model = None

    def forecast_metric(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        metric_col: str, 
        periods: int = 3, 
        freq: str = 'M'
    ) -> List[Dict[str, Any]]:
        """
        Allena un modello Prophet e prevede i valori futuri della metrica.
        
        Args:
            df: DataFrame storico con date e valori.
            date_col: Nome colonna data (deve essere convertibile in datetime).
            metric_col: Nome colonna della metrica da prevedere (es. 'notti_vendute').
            periods: Quanti periodi prevedere nel futuro.
            freq: Frequenza ('M' per mese, 'W' per settimana, 'D' per giorno).
            
        Returns:
            Lista di previsioni con ds (data), yhat (valore predetto), e intervalli di confidenza.
        """
        logger.info(f"Avvio Forecasting per {metric_col} su {periods} periodi ({freq})")
        
        if df.empty or len(df) < 5:
            logger.warning("Dataset troppo piccolo per Prophet. Restituisco flat forecast.")
            return self._fallback_forecast(df, metric_col, periods, freq)

        # Prophet richiede colonne 'ds' (datestamp) e 'y' (valore)
        prophet_df = pd.DataFrame({
            'ds': pd.to_datetime(df[date_col]),
            'y': df[metric_col].fillna(method='ffill') # Semplice fill per NaN
        })

        # Inizializza e allena Prophet
        # (abilitiamo stagionalità annuale per gli hotel)
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.80 # 80% confidence interval
        )
        self.model.fit(prophet_df)

        # Crea dataframe per il futuro
        future = self.model.make_future_dataframe(periods=periods, freq=freq)
        
        # Effettua la previsione
        forecast = self.model.predict(future)
        
        # Filtra solo i periodi futuri (quelli non presenti nel df originale)
        last_date = prophet_df['ds'].max()
        future_forecast = forecast[forecast['ds'] > last_date]

        results = []
        for _, row in future_forecast.iterrows():
            # Evita previsioni negative per volumi o costi
            yhat = max(0, float(row['yhat']))
            yhat_lower = max(0, float(row['yhat_lower']))
            
            results.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "predicted_value": round(yhat, 2),
                "lower_bound": round(yhat_lower, 2),
                "upper_bound": round(float(row['yhat_upper']), 2)
            })

        return results

    def _fallback_forecast(self, df: pd.DataFrame, metric_col: str, periods: int, freq: str) -> List[Dict[str, Any]]:
        """Previsione naive basata sull'ultima media mobile se mancano dati storici."""
        last_val = 0
        if not df.empty:
            last_val = df[metric_col].mean() # Media per smussare

        results = []
        # Genera date fittizie per l'output (semplificazione per PoC)
        import datetime
        from dateutil.relativedelta import relativedelta
        current_date = datetime.date.today()
        
        for i in range(periods):
            if freq == 'M':
                current_date = current_date + relativedelta(months=1)
            elif freq == 'W':
                current_date = current_date + relativedelta(weeks=1)
                
            results.append({
                "date": current_date.strftime('%Y-%m-%d'),
                "predicted_value": round(float(last_val), 2),
                "lower_bound": round(float(last_val) * 0.9, 2),
                "upper_bound": round(float(last_val) * 1.1, 2)
            })
        return results
