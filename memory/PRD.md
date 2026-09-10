# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google. Il planning deve tenere conto di altri contratti e relative date stabilite e da stabilire, della località delle sedi dei clienti in modo da generare gli interventi per ottimizzare gli spostamenti ed altre esigenze future.
> Aggiunta: appuntamenti extra + riprogrammazione, fattura fine lavori, integrazione InvoicexPLUS.

## Persona
Consulente/freelance italiano che gestisce interventi presso più clienti, con contratti a giorni, sedi geograficamente sparse, scadenze e imprevisti. Deploy: web app su Emergent, uso personale.

## Implementation Status (2026-02)
### Core planning
- [x] Emergent Google Auth (session cookie + Bearer)
- [x] Clients CRUD + geocoding OSM (con `codice_cliente`, CAP, prov, P.IVA, C.F., Cod.Dest SdI, PEC)
- [x] Contracts CRUD (con `numero_preventivo`) + status lifecycle (active → planned → completed → invoiced)
- [x] Planning generator (haversine + priority + workdays only + blocks)
- [x] Manual events + reschedule-all
- [x] Vista Calendario mensile con eventi extra + click su cella per aggiungere
- [x] ICS export + subscribe URL (https)
- [x] Dashboard con stats + upcoming

### AI (Claude Haiku 4.5)
- [x] /api/ai/analyze-contract da testo → JSON strutturato
- [x] /api/ai/analyze-contract-pdf upload PDF firmato → estrazione automatica
- [x] /api/ai/planning-chat con contesto reale + history persistente
- [x] /api/ai/draft email/note contestuali
- [x] Pagina AI Assistant con 2 tab (Chat + Analizza)
- [x] Bottoni "Importa da PDF" in Clienti e Contratti

### Google Calendar
- [x] Sync via URL iCal privato (settings + endpoint POST /gcal/sync)
- [x] Cron giornaliero 08:00 Europe/Rome → /api/cron/gcal-sync
- [x] Eventi Google bloccano date nel planning

### Email Reminder (Resend gestito Emergent)
- [x] /api/cron/reminders → invia 24h prima ai clienti
- [x] Cron giornaliero 09:00 Europe/Rome
- [x] Preferenze utente (attivo, dest cliente, copia owner)
- [x] Email di test + log invii

### Fatturazione + Invoicex PLUS
- [x] Dati emittente in Settings (P.IVA, C.F., regime fiscale RF01/RF19, ATECO, sede)
- [x] Fattura PDF (reportlab)
- [x] Export FatturaPA XML v1.2.2 (FPR12) importabile in Invoicex/SdI
- [x] Export CSV clienti formato Invoicex (BOM UTF-8, separatore `;`)
- [x] Import CSV clienti con matching per codice_cliente > P.IVA > nome
- [x] Import CSV preventivi con matching cliente per P.IVA > nome
- [x] Modelli CSV scaricabili con esempi

## Verified Backend Endpoints
- Auth: POST /api/auth/session, GET /api/auth/me, POST /api/auth/logout
- Clients: /api/clients (GET/POST/PUT/DELETE)
- Contracts: /api/contracts (GET/POST/PUT/DELETE, /complete)
- Planning: /api/planning/generate, /api/planning/reschedule
- Manual events: /api/manual-events (GET/POST/DELETE)
- Interventions: /api/interventions (GET/DELETE)
- Calendar: /api/calendar/subscribe-url, /api/calendar/export.ics
- Invoices: /api/invoices/generate
- Dashboard: /api/dashboard/stats
- AI: /api/ai/analyze-contract, /analyze-contract-pdf, /planning-chat, /chat-history, /draft
- Reminders: /api/reminders/prefs, /reminders/test, /reminders/log, /cron/reminders
- GCal: /api/gcal/settings, /gcal/sync, /cron/gcal-sync
- Issuer: /api/settings/issuer
- Export: /api/export/invoicex/clients.csv, /api/export/fatturapa/{contract_id}
- Import: /api/import/clients-template.csv, /api/import/contracts-template.csv, /api/import/clients, /api/import/contracts

## Deployment
- Deployment agent: PASS (2026-02)
- Cron: 2 scheduled tasks in /app/.emergent/crons.yml (reminder 09:00, gcal-sync 08:00 Europe/Rome)
- Pronto per Deploy Emergent tier_0 (~$12-15/mese stimato)

## Prioritized Backlog
- P1: Real-time map view of clients + interventions
- P1: Manual event with time slot UI
- P1: Fattura elettronica XML SDI: validatore inline prima del download
- P2: Notifiche push mobile
- P2: Export Danea Easyfatt-XML alternativo a FatturaPA
- P2: Export TeamSystem FATSEQ per commercialisti
- P2: Firma digitale integrata su fatture PDF
