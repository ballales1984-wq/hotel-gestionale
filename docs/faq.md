# FAQ - Domande Frequenti

## Installazione

**Q: Qual è la password di default per il database?**

A: La password predefinita è `hotel_secure_2025`. Modificala in `.env` per la produzione.

**Q: Posso installare l'applicazione senza Docker?**

A: Sì, ma richiede installazione manuale di Python 3.11+, Node.js 20+, PostgreSQL 16 e Redis 7. Segui le istruzioni in `docs/installation.md`.

## Configurazione

**Q: Come modifico le credenziali admin?**

A: Esegui nel container backend:
```bash
docker-compose exec backend python scripts/create_admin.py
```

**Q: Come aggiungo un nuovo hotel/condominio?**

A: L'applicazione supporta un singolo hotel per deploy. Per multi-hotel, usa strategie di multitenancy o installazioni separate.

## Funzionalità ABC

**Q: Cosa significa 'costo non allocato' nei risultati?**

A: Indica che alcune regole di allocazione non sono state definite o i totali non coincidono. Verifica le regole mancanti in **Allocazioni**.

**Q: Come si fa il ribaltamento attività di supporto?**

A: L'algoritmo lo fa automaticamente come Fase 2. Definisci le regole con `level: attivita_ad_attivita`.

**Q: Posso eseguire più calcoli per lo stesso periodo?**

A: Sì. Ogni esecuzione crea un nuovo risultato. Puoi confrontare i risultati nella sezione Report.

## AI & Machine Learning

**Q: I dati devono essere di quanti periodi per le funzioni AI?**

A: Minimo 10 periodi per forecasting, 20 per anomaly detection. Se i dati sono insufficienti, il sistema usa dati di esempio.

**Q: Come funziona il driver discovery?**

A: Usa Random Forest per determinare l'importanza relativa dei driver (ore lavorate, notti, coperti, mq, eventi) sui costi overhead.

**Q: Posso aggiungere nuovi driver?**

A: Sì, modifica `backend/app/api/v1/endpoints/ai.py` nella lista `ALL_DRIVER_FEATURES`.

## Troubleshooting

**Q: L'applicazione è lenta, cosa posso fare?**

A: Controlla `docker stats` per verificare utilizzo risorse. Considera di aumentare RAM o ottimizzare le query.

**Q: Ricevo errore 'relation does not exist' al login**

A: Esegui il seed del database: `docker-compose exec backend python -m app.db.seed`

**Q: Come resetto tutti i dati di sviluppo?**

A: `docker-compose down -v && docker-compose up -d && docker-compose exec backend python -m app.db.seed`

## Produzione

**Q: Quali modifiche fare per la produzione?**

A: 
1. Modifica tutte le password in `.env`
2. Genera nuove chiavi secret (`openssl rand -hex 32`)
3. Configura SSL in `infra/nginx/ssl/`
4. Imposta `ENVIRONMENT=production`
5. Usa `FRONTEND_TARGET=production`

**Q: Come configuro il backup automatico?**

A: Aggiungi a crontab:
```bash
0 2 * * * cd /path/to/app && docker-compose exec postgres pg_dump -U hotel_user hotel_abc > backups/backup_$(date +\%Y\%m\%d).sql
```

## Sviluppo

**Q: Come aggiungo un nuovo endpoint API?**

A: 
1. Crea il file in `backend/app/api/v1/endpoints/`
2. Aggiungi il router in `backend/app/api/v1/__init__.py`
3. Aggiorna i modelli in `backend/app/models/models.py`

**Q: Come testare localmente le modifiche?**

A: I container sono configurati con volume bind. Modificando i file localmente, i cambiamenti sono immediati in `development`.