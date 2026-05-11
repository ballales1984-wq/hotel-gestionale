"""
AI / ML Engine — Anomaly Detection
Usa Isolation Forest per individuare anomalie nei costi o nei volumi.
Fornisce anche uno score di anomalia e il feature contribution (approssimato).
"""
import logging
from typing import Dict, List, Any

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class AnomalyDetector:
    """Rileva anomalie nei dati storici per individuare inefficienze o errori."""
    
    def __init__(self, contamination: float = 0.05):
        """
        Args:
            contamination: La proporzione attesa di outlier nel dataset (es. 5%).
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()

    def detect_anomalies(self, df: pd.DataFrame, feature_cols: List[str], id_col: str) -> List[Dict[str, Any]]:
        """
        Identifica anomalie nel DataFrame.
        
        Args:
            df: DataFrame storico.
            feature_cols: Colonne da usare per la rilevazione (es. 'costo_lavoro', 'ore', 'volume_output').
            id_col: Colonna identificativa per riga (es. 'periodo_id' o 'attivita_id').
            
        Returns:
            Lista di anomalie trovate.
        """
        logger.info(f"Avvio Anomaly Detection su {len(df)} records")
        
        if df.empty or len(df) < 20:
            logger.warning("Dataset troppo piccolo per Anomaly Detection affidabile. Nessuna anomalia ritornata.")
            return []

        # Preparazione dati
        X_raw = df[feature_cols].fillna(0)
        
        # Protezione: verifica che non ci siano righe o colonne tutte zero
        if X_raw.shape[0] == 0:
            logger.warning("Nessun dato valido dopo fillna")
            return []
        
        # Verifica se tutte le colonne hanno varianza zero (stessi valori)
        if (X_raw.std() == 0).all():
            logger.warning("Tutte le features hanno varianza zero, skipping anomaly detection")
            return []
        
        # Scaling è importante per l'Isolation Forest
        X_scaled = self.scaler.fit_transform(X_raw)
        
        # Fit e predict (-1 per anomalia, 1 per normale)
        preds = self.model.fit_predict(X_scaled)
        
        # Score di anomalia (più basso = più anomalo)
        scores = self.model.decision_function(X_scaled)
        
        anomalies = []
        for i, pred in enumerate(preds):
            if pred == -1: # È un'anomalia
                record_id = df.iloc[i][id_col]
                
                # Calcola deviazione dalla media per ogni feature per capire *perché* è anomalo
                # (Semplice Z-score heuristics per explainability)
                z_scores = X_scaled[i]
                max_dev_idx = np.argmax(np.abs(z_scores))
                root_cause_feat = feature_cols[max_dev_idx]
                dev_direction = "molto più alto" if z_scores[max_dev_idx] > 0 else "molto più basso"
                
                anomalies.append({
                    "record_id": str(record_id),
                    "anomaly_score": round(float(-scores[i]), 3), # Invertiamo così > score = > anomalia
                    "root_cause_driver": root_cause_feat,
                    "explanation": f"Valore anomalo rilevato. Il fattore principale è '{root_cause_feat}' che risulta {dev_direction} rispetto alla norma."
                })
                
        # Ordina per score di gravità (decrescente)
        anomalies.sort(key=lambda x: x["anomaly_score"], reverse=True)
        return anomalies
