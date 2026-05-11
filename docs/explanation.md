# Spiegazione del Progetto Hotel ABC Platform

## Cos'è?
Hotel ABC Platform è un software che aiuta gli hotel a capire esattamente quanto costa offrire ogni servizio (come una camera, un pasto al ristorante o un servizio di lavanderia). Invece di indovinare, il sistema calcola i costi reali guardando tutte le attività che accadono dietro le quinte.

## A cosa serve?
Immagina di gestire un hotel e di voler sapere:
- Quanto costa davvero pulire una camera?
- Il ristorante sta guadagnando o perdendo soldi sui pasti?
- Quanto devo chiedere per un servizio di spa per coprire i costi e fare profitto?

Questo strumento risponde a queste domande mostrando:
- Dove vanno davvero i soldi (quali attività consumano più risorse)
- Quanto ogni servizio dell'hotel costa da fornire
- Quali servizi sono più redditizi e quali potrebbere essere migliorati

## Come funziona? (in termini semplici)
1. **Inserisci i dati**: Carichi semplici fogli Excel (CSV) con:
   - Cosa hai speso (stipendi, bollette, ecc.)
   - Quanto tempo i dipendenti hanno dedicato a ogni attività
   - Quanto hai guadagnato da ogni servizio (camere, ristorante, ecc.)

2. **Il sistema elabora**: 
   - Prima, divide i costi generali (come l'affitto dell'edificio) tra le attività che li hanno causati (pulizia, reception, cucina)
   - Poi, ridistribuisce i costi delle attività di supporto (come la contabilità o le pulizie generali) alle attività principali (come pulire le camere o servire i pasti)
   - Infine, assegna i costi di ogni attività ai servizi finali che li utilizzano (una camera usa pulizia, biancheria, energia, ecc.)

3. **Ottieni i risultati**: Vedi chiaramente:
   - Quanto costa fornire ogni servizio
   - Quali attività costano di più
   - Quali servizi fanno guadagnare o perdere soldi

## Chi lo usa?
- **Direttori hotel**: Per prendere decisioni sui prezzi e su cosa migliorare
- **Controller finanziari**: Per capire i veri costi e controllare gli sprechi
- **Responsabili di reparto**: Per vedere quanto costa il loro lavoro e giustificare budget
- **Consulenti**: Per analizzare hotel e suggerire miglioramenti

## Tecnologie utilizzate (spiegato semplicemente)
- **Backend (il cervello)**: È fatto con Python (un linguaggio di programmazione) e usa FastAPI per comunicare con il resto del sistema
- **Database**: PostgreSQL, che è come un archivio elettronico molto organizzato per tenere tutti i dati al sicuro
- **Frontend (ciò che vedi)**: È fatto con React, che crea le pagine web interattive che usi nel browser
- **AI/ML (funzioni intelligenti)**: Usa sistemi di apprendimento automatico per:
  - Scoprire quali attività influenzano di più i costi
  - Prevedere quanto lavoro ci sarà nel futuro (quante camere prenotate, ecc.)
  - Trovare strani schemi nei dati che potrebbero indicare errori o sprechi
- **Docker**: È una tecnologia che impacchetta tutto il programma così funziona allo stesso modo su qualsiasi computer, senza problemi di installazione
- **Superset**: È uno strumento incluso per creare grafici e rapporti avanzati se vuoi analizzare i dati in modo più dettagliato

## Perché è utile?
Senza questo strumento, gli hotel spesso:
- Stabiliscono prezzi basandosi su congetture anziché sui costi reali
- Non si accorgono che alcuni servizi stanno perdendo soldi
- Sprecano risorse in attività che non aggiungono valore
- Prendono decisioni importanti senza dati solidi

Con Hotel ABC Platform, invece:
- Puoi fissare prezzi che coprono davvero i costi e generano profitto
- Identifichi quali servizi promuovere e quali migliorare o eliminare
- Ottimizzi l'uso del personale e delle forniture
- Prendi decisioni basate su fatti, non su intuizioni

## Iniziare è semplice
1. Installa Docker (un programma che permette di eseguire il sistema senza complicazioni)
2. Copia il progetto sul tuo computer
3. Avvia il sistema con un comando semplice
4. Carica i tuoi dati nei formati CSV forniti
5. Guarda i risultati in una interfaccia web facile da usare

Non serve essere esperti di tecnologia: il sistema guida passo passo e l'interfaccia è pensata per chi lavora in hotel, non per programmatori.