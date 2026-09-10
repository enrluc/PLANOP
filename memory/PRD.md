# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google.

## Persona
Consulente italiano - uso personale singolo (enrluc@gmail.com).

## Implementation Status (2026-02)
### Core
- [x] Emergent Google Auth
- [x] Clients CRUD + geocoding (codice_cliente, CAP, prov, P.IVA, C.F., Cod.Dest SdI, PEC)
- [x] Contracts CRUD (numero_preventivo, max_per_month)
- [x] Planning generator con **cursore per-contratto [start_date, deadline]** + `skipped[]` output
- [x] Manual events con **slot mattina/pomeriggio/intera**
- [x] Vista Calendario mensile con **pannello dettagli** click su intervento/evento
- [x] Vista Mappa (Leaflet + OSM) con toggle percorso interventi
- [x] Dashboard con stats + upcoming

### Interventi
- [x] Fasce orarie configurabili per singolo intervento (mattina/pomeriggio/intera)
- [x] Status: planned → confirmed → done
- [x] Bottone Conferma+email (immediata + reminder 24h automatico solo per confermati)
- [x] Modifica slot da tabella Planning E da pannello dettagli Calendario

### AI (Claude Haiku 4.5)
- [x] Analyze contract testo + PDF upload
- [x] Planning chat con contesto
- [x] Draft email/note

### Email (Resend gestito Emergent)
- [x] Conferma immediata + reminder 24h (cron 09:00 Europe/Rome)

### Google Calendar
- [x] Sync iCal privato (cron 08:00 Europe/Rome)
- [x] Export ICS con orari precisi per slot (Europe/Rome TZ)

### Fatturazione + Invoicex PLUS
- [x] FatturaPA XML v1.2.2 export
- [x] Import CSV clienti + preventivi con template scaricabili
- [x] Import massivo XML FatturaPA da Aruba
- [x] Fattura PDF (reportlab)

## Verified Bug Fixes
- Planning ignorava start_date/deadline contratto → risolto (testing_agent iter2: 8/8 PASS)

## Deployment
- Deployment agent: PASS
- Cron: 2 tasks in /app/.emergent/crons.yml
- Pronto per Deploy Emergent

## Prioritized Backlog
- P2: Notifiche push mobile / PWA
- P2: Firma digitale Aruba integrata su fatture
- P2: Export Danea Easyfatt-XML / TeamSystem FATSEQ
- P2: Aruba REST API (richiede AuthToken enterprise)
- P2: Backup automatico settimanale (cron domenica notte)
