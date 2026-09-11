# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google.

## Persona
Consulente italiano - uso personale singolo (enrluc@gmail.com).

## Implementation Status (2026-02)
### Core
- [x] Emergent Google Auth (modalità cloud)
- [x] **LOCAL_MODE bypass auth** per build desktop (single-user)
- [x] Clients CRUD + geocoding (codice_cliente, CAP, prov, P.IVA, C.F., Cod.Dest SdI, PEC)
- [x] Contracts CRUD (numero_preventivo, max_per_month)
- [x] Planning generator con cursore per-contratto [start_date, deadline] + skipped[] output
- [x] Manual events con slot mattina/pomeriggio/intera
- [x] Vista Calendario mensile con pannello dettagli click
- [x] Vista Mappa (Leaflet + OSM) con toggle percorso interventi
- [x] Dashboard con stats + upcoming

### Interventi
- [x] Fasce orarie configurabili (mattina/pomeriggio/intera)
- [x] Status: planned → confirmed → accepted → done
- [x] Bottone Conferma+email + reminder 24h automatico

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

### 🖥️ Desktop Edition (2026-02, Opzione 1)
- [x] `LOCAL_MODE` env flag → bypass OAuth, auto-crea utente locale singolo
- [x] Backend serve build React statica in LOCAL_MODE (`/` + SPA fallback)
- [x] Frontend `AuthContext` rileva `REACT_APP_LOCAL_MODE=true` a build-time e salta login
- [x] `backend/launcher.py` + `backend/planop_backend.spec` — bundle PyInstaller onedir
- [x] `electron/main.js` — spawn MongoDB portable + backend .exe, apre BrowserWindow su localhost:8001
- [x] `electron/package.json` — electron-builder NSIS installer Windows x64
- [x] MongoDB Community 7.0.14 portable scaricato dal workflow (bundle in installer)
- [x] `.github/workflows/build-desktop-windows.yml` — CI build automatica su tag `v*` o workflow_dispatch
- [x] `DESKTOP_BUILD.md` — guida completa build via GitHub Actions
- [x] Regression cloud verificata: `/api/auth/me → 401` senza LOCAL_MODE

## Verified Bug Fixes
- Planning ignorava start_date/deadline contratto → risolto (iter2: 8/8 PASS)
- Lint blockers CalendarPage (`FileSpreadsheet`, `monthlyAgendaUrl` non importati) → risolti

## Deployment
- Cloud (Emergent): PASS
- Desktop (Windows installer): pipeline pronta, richiede push su GitHub → Actions → download artifact

## Prioritized Backlog
- P1: Webhook Resend per auto-accettazione clienti via email
- P2: Backup CSV settimanale (cron domenica notte)
- P2: Firma digitale Aruba integrata su fatture PDF
- P2: Notifiche push mobile / PWA
- P2: Export Danea Easyfatt-XML / TeamSystem FATSEQ
- P2: UI Impostazioni per chiavi personali (Anthropic + Resend) in modalità desktop
