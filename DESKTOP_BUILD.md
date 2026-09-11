# PlanOp — Desktop Build (Windows) 🖥️

Guida per generare l'installer **PlanOp-x.y.z-Setup.exe** (Windows 64-bit) da distribuire su un singolo PC.

L'installer bundle:
- **React frontend** (build statica)
- **FastAPI backend** (PyInstaller, unico eseguibile, no Python richiesto)
- **MongoDB Community** portable (`mongod.exe`, avviato automaticamente)
- **Electron** shell (finestra desktop nativa)

Modalità: `LOCAL_MODE=true` → **nessun login**, singolo utente locale, database in `%APPDATA%/PlanOp/mongo-data/`.

---

## ✅ Modo consigliato — Build via GitHub Actions (opzione "b")

Non serve installare nulla sul PC. La build gira nel cloud gratuitamente.

### Passi

1. **Salva su GitHub**  
   Usa il bottone **"Save to GitHub"** in fondo alla chat Emergent.  
   Verrà creato/aggiornato il tuo repository con l'intero codice, inclusi:
   - `electron/`
   - `backend/planop_backend.spec`, `backend/launcher.py`
   - `.github/workflows/build-desktop-windows.yml`

2. **Build manuale**  
   Sul tuo repository GitHub:
   - Vai su **Actions** → **Build PlanOp Desktop (Windows)**
   - Clicca **"Run workflow"** → **Run workflow**
   - Attendi ~10-15 minuti

3. **Scarica l'installer**
   - Al termine della run, in fondo alla pagina trovi la sezione **Artifacts**
   - Scarica **`PlanOp-Windows-Setup`** (file `.zip`)
   - Estrai → dentro c'è **`PlanOp-1.0.0-Setup.exe`**

4. **Installa su Windows**
   - Doppio-click su `PlanOp-1.0.0-Setup.exe`
   - **Windows SmartScreen**: dirà "Editore sconosciuto" (installer non firmato).  
     Clicca **"Ulteriori informazioni"** → **"Esegui comunque"**
   - L'app viene installata in `C:\Users\<tu>\AppData\Local\Programs\PlanOp`
   - Icona sul desktop + voce nel Menu Start

5. **Prima esecuzione**
   - Apri PlanOp → parte MongoDB in locale, poi il backend, poi la finestra
   - Vai in **Impostazioni** → inserisci le tue chiavi personali (opzionali):
     - **Anthropic** (Claude Haiku 4.5) — per lettura PDF
     - **Resend** — per email reminder
   - I dati sono salvati in `%APPDATA%\PlanOp\mongo-data\`

### Rilascio versionato (opzionale)

Per generare una vera "release" GitHub con l'installer allegato:

```bash
git tag v1.0.0
git push --tags
```

Il workflow parte automaticamente su tag `v*` e attacca l'installer alla release.

---

## 🔧 Modo alternativo — Build locale sul tuo PC (avanzato)

Prerequisiti (installali una tantum):
- **Node.js 20+** ([nodejs.org](https://nodejs.org))
- **Python 3.11** ([python.org](https://www.python.org))
- **Yarn**: `npm install -g yarn`

Poi:

```powershell
# 1) Frontend
cd frontend
yarn install
$env:REACT_APP_BACKEND_URL=""
$env:REACT_APP_LOCAL_MODE="true"
yarn build
cd ..

# 2) Backend
cd backend
pip install -r requirements.txt
pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ emergentintegrations
pip install pyinstaller==6.10.0
pyinstaller planop_backend.spec --noconfirm --clean
cd ..

# 3) MongoDB portable
# Scarica ZIP da https://www.mongodb.com/try/download/community (Windows x64)
# Estrai mongod.exe → electron/vendor/mongo/bin/mongod.exe

# 4) Electron installer
cd electron
yarn install
yarn build:win
# → dist/PlanOp-1.0.0-Setup.exe
```

---

## 📁 Layout runtime (dopo installazione)

```
C:\Users\<tu>\AppData\Local\Programs\PlanOp\
├── PlanOp.exe                     ← launcher Electron
├── resources\
│   ├── frontend\                  ← build React
│   ├── backend\
│   │   ├── planop-backend.exe     ← FastAPI/Uvicorn
│   │   └── ... (DLL/dipendenze)
│   └── mongo\bin\mongod.exe

C:\Users\<tu>\AppData\Roaming\PlanOp\
├── mongo-data\                    ← database
├── mongod.log
└── logs\                          ← log Electron
```

## 🐛 Troubleshooting

- **"mongod.exe non trovato"** → la build non ha scaricato MongoDB. Ricontrolla lo step "Download MongoDB" nella run GitHub Actions.
- **App non si apre** → apri `%APPDATA%\PlanOp\logs\main.log` e cerca errori.
- **Porte 8001/27071 occupate** → chiudi altri programmi che le usano, oppure modifica `electron/main.js` (`BACKEND_PORT`, `MONGO_PORT`).
- **Backup dati** → basta zippare `%APPDATA%\PlanOp\mongo-data\`.
- **Disinstalla** → Impostazioni Windows → App → PlanOp → Disinstalla. I dati in `%APPDATA%\PlanOp\` **restano** (cancellali a mano se vuoi).

## 🔐 Chiavi API personali

In modalità desktop **non usi più** l'`EMERGENT_LLM_KEY` cloud. Puoi impostare le tue chiavi tramite:

- Pagina **Impostazioni** dell'app (consigliato)
- Oppure via variabili d'ambiente all'avvio, es. da PowerShell:
  ```powershell
  $env:ANTHROPIC_API_KEY="sk-ant-..."
  $env:RESEND_API_KEY="re_..."
  & "C:\...\PlanOp.exe"
  ```

Costi indicativi uso personale:
- **Anthropic Claude Haiku 4.5**: ~$0,50 - $2/mese (200-500 PDF)
- **Resend**: gratuito fino a 3.000 email/mese
