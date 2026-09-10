# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google. Il planning deve tenere conto di altri contratti e relative date stabilite e da stabilire, della località delle sedi dei clienti in modo da generare gli interventi per ottimizzare gli spostamenti ed altre esigenze future.

## Persona
Consulente/freelance italiano che gestisce interventi presso più clienti. Deploy: web app su Emergent, uso personale singolo (enrluc@gmail.com).

## Implementation Status (2026-02)
### Core planning
- [x] Emergent Google Auth
- [x] Clients CRUD + geocoding OSM (codice_cliente, CAP, prov, P.IVA, C.F., Cod.Dest SdI, PEC)
- [x] Contracts CRUD (numero_preventivo, intervention_slot, max_per_month) + status
- [x] Planning generator (haversine + priority + workdays + blocks + slot + max/mese)
- [x] Manual events + reschedule-all + Google Calendar iCal sync
- [x] Vista Calendario mensile con click cella
- [x] Vista Mappa con Leaflet + OpenStreetMap + toggle percorso interventi
- [x] Dashboard con stats + upcoming

### AI (Claude Haiku 4.5)
- [x] Analyze contract (testo + PDF upload)
- [x] Planning chat con contesto reale + history
- [x] Draft email/note contestuali

### Appuntamenti - Nuovo workflow
- [x] Fasce orarie: mattina (09:00-13:30), pomeriggio (14:30-18:00), giornata intera (09:00-18:00)
- [x] Status intervento: pianificato → confermato → done
- [x] Bottone "Conferma + email" in Planning: cambia stato E invia email di conferma al cliente
- [x] Reminder 24h prima (cron 09:00 Europe/Rome) SOLO per interventi confermati
- [x] Icons e color coding nel Calendario per stato

### Email (Resend gestito Emergent)
- [x] Email di conferma appuntamento (istantanea alla conferma)
- [x] Email di reminder 24h prima (cron giornaliero)
- [x] Preferenze utente + log invii + email di test

### Google Calendar
- [x] Sync via URL iCal privato (cron 08:00 Europe/Rome)
- [x] Eventi Google bloccano date nel planning
- [x] Export ICS con orari VEVENT precisi per slot

### Fatturazione + Invoicex PLUS
- [x] Dati emittente (P.IVA, C.F., regime fiscale, ATECO, sede)
- [x] Fattura PDF (reportlab)
- [x] Export FatturaPA XML v1.2.2 (FPR12) importabile Invoicex/SdI
- [x] Export CSV clienti formato Invoicex
- [x] Import CSV clienti (matching per codice_cliente > P.IVA > nome)
- [x] Import CSV preventivi (matching cliente per P.IVA > nome)
- [x] **Import massivo FatturaPA XML da Aruba** → estrae automaticamente Cedente + Cessionario in anagrafica

## Verified Backend Endpoints
- Auth: /api/auth/* 
- Clients: /api/clients/*
- Contracts: /api/contracts/*
- Planning: /api/planning/generate, /reschedule
- Interventions: /api/interventions/*, /api/interventions/{id}/confirm, /api/interventions/{id}/unconfirm
- Manual events: /api/manual-events/*
- Calendar: /api/calendar/*
- Invoices: /api/invoices/generate
- Dashboard: /api/dashboard/stats
- AI: /api/ai/analyze-contract, /analyze-contract-pdf, /planning-chat, /draft
- Reminders: /api/reminders/*, /api/cron/reminders
- GCal: /api/gcal/*, /api/cron/gcal-sync
- Issuer: /api/settings/issuer
- Export: /api/export/invoicex/clients.csv, /api/export/fatturapa/{contract_id}
- Import: /api/import/clients-template.csv, /contracts-template.csv, /clients, /contracts, /fatturapa-xml

## Deployment
- Deployment agent: PASS
- Cron: 2 tasks in /app/.emergent/crons.yml (reminder 09:00, gcal-sync 08:00 Europe/Rome)
- Pronto per Deploy Emergent

## Prioritized Backlog
- P1: Manual event con slot orario UI (mezze giornate manuali)
- P1: Visualizzazione dettagli intervento con click su cella calendario
- P2: Notifiche push mobile / PWA
- P2: Export Danea Easyfatt-XML / TeamSystem FATSEQ
- P2: Aruba REST API integration (richiede AuthToken enterprise)
- P2: Firma digitale integrata su fatture PDF
