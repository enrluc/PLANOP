# PlanOp - Product Requirements Doc

## Original Problem Statement
> Vorrei creare una app che a partire dal contratto firmato per una attività che prevede un certo numero di giorni di lavoro mi crei un planning da inserire a calendario Google. Il planning deve tenere conto di altri contratti e relative date stabilite e da stabilire, della località delle sedi dei clienti in modo da generare gli interventi per ottimizzare gli spostamenti ed altre esigenze future.
> Aggiunta: possibilità di inserire appuntamenti non previsti e riprogrammare tutto.
> Potrebbe generare fattura a fine lavori.

## Persona
Consulente/freelance italiano che gestisce interventi presso più clienti, con contratti a giorni di lavoro, sedi geograficamente sparse, scadenze e imprevisti.

## Core Requirements (Static)
- Login personale via Emergent Google Auth (single-user)
- Anagrafica clienti con indirizzo + geocoding OSM (Nominatim)
- Contratti (cliente, giorni, tariffa, priorità, scadenza, tipologia, note)
- Planning automatico ottimizzato per prossimità geografica + priorità/scadenze
- Appuntamenti extra manuali che bloccano date
- Riprogrammazione completa
- Vista Calendario mensile con extra events + interventi
- Sincronizzazione Google Calendar via URL .ics (subscribe)
- Fattura PDF finale (regime forfettario, IVA, ritenuta d'acconto, marca da bollo)

## Implementation Status (2026-02)
- [x] Emergent Google Auth (session cookie + Bearer)
- [x] Clients CRUD + geocoding OSM
- [x] Contracts CRUD + status lifecycle (active → planned → completed → invoiced)
- [x] Planning generator (haversine + priority + workdays only + blocks)
- [x] Manual events + reschedule-all
- [x] Calendar view mensile con extra events
- [x] ICS export + subscribe URL (https via X-Forwarded-Proto)
- [x] Invoice PDF con reportlab (forfettario/ordinario)
- [x] Dashboard con stats + upcoming

## Verified Backend Endpoints (Testing agent iter1 + fix)
- POST /api/auth/session, GET /api/auth/me, POST /api/auth/logout
- /api/clients (GET/POST/PUT/DELETE)
- /api/contracts (GET/POST/PUT/DELETE, /complete)
- /api/planning/generate, /api/planning/reschedule
- /api/manual-events (GET/POST/DELETE)
- /api/interventions (GET/DELETE)
- /api/calendar/subscribe-url, /api/calendar/export.ics
- /api/invoices/generate
- /api/dashboard/stats

## Known Limitations
- Geocoding: Nominatim may return 403 from server IP → lat/lng null → planning fallback ordering. Non blocking. Consider caching or paid provider.
- Google Calendar: read-only subscribe (utente incolla URL). Nessuna scrittura diretta OAuth (Emergent Auth non fornisce scope Calendar).

## Prioritized Backlog
- P1: Real-time map view of clients + interventions
- P1: Manual event with time slot (start_time/end_time già nel modello, mancano UI)
- P1: Export interventi filtrati per periodo/cliente
- P2: Fattura elettronica XML (SDI)
- P2: Multi-lingua
- P2: Notifiche email 24h prima intervento (Resend)
