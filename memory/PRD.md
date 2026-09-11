# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google.

## Persona
Consulente italiano - uso personale singolo (enrluc@gmail.com).

## Implementation Status (2026-02)

### Core
- [x] Emergent Google Auth (modalità cloud)
- [x] LOCAL_MODE bypass auth per build desktop (single-user)
- [x] Clients CRUD + geocoding
- [x] Contracts CRUD (numero_preventivo, max_per_month)
- [x] Planning generator con cursore per-contratto + skipped[]
- [x] Manual events con slot mattina/pomeriggio/intera
- [x] Vista Calendario mensile con pannello dettagli
- [x] Vista Mappa (Leaflet + OSM)
- [x] Dashboard con stats + upcoming

### Interventi
- [x] Fasce orarie configurabili (mattina/pomeriggio/intera)
- [x] Status: planned → confirmed → accepted → done
- [x] Bottone Conferma+email + reminder 24h automatico
- [x] **Auto-accept via email reply webhook** (2026-02)

### AI
- [x] Claude Haiku 4.5 - Analyze contract testo + PDF
- [x] Planning chat con contesto
- [x] Draft email/note
- [x] **Support chiave Anthropic personale** (usa Emergent LLM key come fallback)

### Email (Resend)
- [x] Conferma immediata + reminder 24h
- [x] **Support chiave Resend personale** (Emergent Resend come fallback)
- [x] From-email personalizzato (dominio verificato)

### Google Calendar
- [x] Sync iCal privato (cron 08:00)
- [x] Export ICS con orari precisi per slot

### Fatturazione + Invoicex PLUS
- [x] FatturaPA XML v1.2.2 export
- [x] Import CSV clienti + preventivi
- [x] Import massivo XML FatturaPA da Aruba
- [x] Fattura PDF (reportlab)

### 🖥️ Desktop Edition (Opzione 1) — 2026-02
- [x] LOCAL_MODE env flag → bypass OAuth, utente locale singolo
- [x] Backend serve build React statica in LOCAL_MODE
- [x] Frontend AuthContext rileva REACT_APP_LOCAL_MODE=true e salta login
- [x] `backend/launcher.py` + `planop_backend.spec` — bundle PyInstaller onedir
- [x] `electron/main.js` — spawn MongoDB portable + backend .exe + BrowserWindow
- [x] `electron/package.json` — electron-builder NSIS installer Windows x64
- [x] MongoDB Community 7.0.14 portable scaricato dal workflow
- [x] `.github/workflows/build-desktop-windows.yml` — CI Windows on workflow_dispatch + tag v*
- [x] `DESKTOP_BUILD.md` — guida completa

### 🔧 Impostazioni Personali (2026-02)
- [x] `GET/PUT /api/settings/api-keys` - Anthropic + Resend + from-email (masked read)
- [x] UI Settings: card "Chiavi API personali" con show/hide, clear, link doc
- [x] `_get_personal_keys(user_id)` helper - fallback trasparente da personale a Emergent
- [x] `_DirectAnthropicChat` wrapper compatibile con LlmChat interface

### 📨 Webhook Auto-Accept (2026-02)
- [x] `POST /api/webhooks/email-reply` accetta payload da Resend inbound
- [x] Matching: sender email → client → most recent confirmed intervention
- [x] Parole chiave italiane: "ok", "confermo", "va bene", "accetto", ecc.
- [x] Guard-rail rifiuto: "annulla", "sposta", "impegnato", ecc.
- [x] Log inbound in `db.inbound_email_log`
- [x] Protezione opzionale con `WEBHOOK_INBOUND_SECRET`

### 💾 Backup Domenicale (2026-02)
- [x] `POST /api/cron/weekly-backup` (protetto WEBHOOK_CRON_SECRET)
- [x] ZIP con clients.csv, contracts.csv, interventions.csv (UTF-8 BOM)
- [x] Invio email domenica 22:00 Europe/Rome (cron in `.emergent/crons.yml`)
- [x] `GET /api/reports/weekly-backup.zip` per download on-demand da UI Settings

## Verified Endpoints (curl smoke test 2026-02)
- `GET /api/settings/api-keys` → 401 senza auth ✓
- `POST /api/webhooks/email-reply` (empty from) → 400 ✓
- `POST /api/webhooks/email-reply` (valid) → 200 no_action se email non trovata ✓
- `POST /api/cron/weekly-backup` senza token → 401 ✓
- `POST /api/cron/weekly-backup` con token → 200 ✓

## Deployment
- Cloud (Emergent): PASS
- Desktop (Windows installer): pipeline pronta → push to GitHub → Actions → download artifact

## Prioritized Backlog
- P2: Firma digitale Aruba integrata su fatture PDF
- P2: Export Danea Easyfatt-XML / TeamSystem FATSEQ
- P2: Notifiche push mobile / PWA
- P2: Aruba REST API (richiede AuthToken enterprise)
- P3: Test auto-accept end-to-end con Resend inbound reale (richiede dominio + tunnel)
