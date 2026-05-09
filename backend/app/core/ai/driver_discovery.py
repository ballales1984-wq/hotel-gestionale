"""
AI / ML Engine — Driver Discovery
Usa LightGBM e SHAP per identificare i cost driver più rilevanti (feature importance)
spiegando l'impatto di ogni attività sui costi e sui volumi.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Any

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap

logger = logging.getLogger(__name__)

class DriverDiscoveryEngine:
    """
    Analizza i dati storici per identificare quali fattori (driver)
    influenzano maggiormente i costi di un reparto o di un servizio.
    """
    
    def __init__(self):
        self.model = None
        self.explainer = None

    def discover_drivers(self, df: pd.DataFrame, target_col: str, feature_cols: List[str]) -> List[Dict[str, Any]]:
        """
        Allena un modello LightGBM sul dataset storico per prevedere il target (es. costo totale).
        Usa SHAP per estrarre il ranking di importanza delle features (i "driver" candidati).
        
        Args:
            df: DataFrame storico (es. aggregato per settimana/mese)
            target_col: La colonna da prevedere (es. 'overhead_cost')
            feature_cols: Le colonne candidate come driver (es. 'ore_lavorate', 'notti_vendute', 'coperti', 'mq')
            
        Returns:
            Lista di dizionari con il ranking dei driver e il loro SHAP value assoluto medio.
        """
        logger.info(f"Avvio Driver Discovery per target: {target_col}")
        
        # Validazione base
        if df.empty or len(df) < 10:
            logger.warning("Dataset troppo piccolo per discovery affidabile. Restituisco stima base.")
            return self._fallback_discovery(feature_cols)

        # Preparazione dati
        X = df[feature_cols].fillna(0)
        y = df[target_col].fillna(0)
        
        # Train modello
        self.model = lgb.LGBMRegressor(
            n_estimators=100, 
            learning_rate=0.05, 
            max_depth=5, 
            random_state=42,
            verbose=-1
        )
        self.model.fit(X, y)
        
        # Explainability con SHAP
        self.explainer = shap.TreeExplainer(self.model)
        shap_values = self.explainer.shap_values(X)
        
        # Calcola importanza media assoluta (mean |SHAP value|)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        
        # Normalizza in percentuale per UI
        total_shap = mean_abs_shap.sum()
        if total_shap == 0:
            return self._fallback_discovery(feature_cols)
            
        importance_pct = (mean_abs_shap / total_shap) * 100
        
        # Costruisci risultato
        results = []
        for i, feat in enumerate(feature_cols):
            results.append({
                "driver_name": feat,
                "importance_pct": round(float(importance_pct[i]), 2),
                "confidence_score": self._calculate_confidence(len(df), float(importance_pct[i])),
                "explanation": f"Un aumento di {feat} influisce in modo significativo su {target_col}."
            })
            
        # Ordina per importanza decrescente
        results.sort(key=lambda x: x["importance_pct"], reverse=True)
        return results

    def _calculate_confidence(self, sample_size: int, importance: float) -> str:
        """Calcola un livello di confidenza basato sulla dimensione del campione e sull'importanza."""
        if sample_size < 30: return "Bassa"
        if importance > 30 and sample_size >= 50: return "Alta"
        return "Media"

    def _fallback_discovery(self, feature_cols: List[str]) -> List[Dict[str, Any]]:
        """Ritorna pesi equalizzati se i dati non sono sufficienti per il ML."""
        weight = 100.0 / len(feature_cols) if feature_cols else 0
        return [{
            "driver_name": feat,
            "importance_pct": round(weight, 2),
            "confidence_score": "Bassa (Dati insufficienti)",
            "explanation": "Distribuzione base per mancanza di dati storici sufficienti."
        } for feat in feature_cols]
