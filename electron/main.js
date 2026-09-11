// PlanOp — Electron main process
// Boots:
//   1. Local MongoDB (bundled) on a fixed port, storing data under userData/mongo-data
//   2. FastAPI backend (PyInstaller bundle) on 127.0.0.1:8001 with LOCAL_MODE=true
//   3. BrowserWindow pointing at http://127.0.0.1:8001 (backend also serves the React build)

const { app, BrowserWindow, dialog, Menu, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const waitOn = require('wait-on');
const log = require('electron-log');

log.transports.file.level = 'info';
log.transports.console.level = 'info';

const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT = 8001;
const MONGO_HOST = '127.0.0.1';
const MONGO_PORT = 27071; // avoid clashing with any user-installed MongoDB
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let mainWindow = null;
let mongoProc = null;
let backendProc = null;

function isPackaged() {
  return app.isPackaged;
}

function resourcePath(...p) {
  // In dev: files are read from repo. In prod: from process.resourcesPath (extraResources).
  return isPackaged()
    ? path.join(process.resourcesPath, ...p)
    : path.join(__dirname, ...p);
}

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
  return p;
}

function killChildren() {
  try { if (backendProc && !backendProc.killed) backendProc.kill(); } catch (e) { log.warn(e); }
  try { if (mongoProc && !mongoProc.killed) mongoProc.kill(); } catch (e) { log.warn(e); }
}

function startMongo() {
  const userData = app.getPath('userData');
  const dbPath = ensureDir(path.join(userData, 'mongo-data'));
  const logPath = path.join(userData, 'mongod.log');

  const mongodBinary = process.platform === 'win32' ? 'mongod.exe' : 'mongod';
  const mongodPath = resourcePath('mongo', 'bin', mongodBinary);

  if (!fs.existsSync(mongodPath)) {
    const msg = `MongoDB binary non trovato: ${mongodPath}\n\nEsegui gli step di setup descritti in DESKTOP_BUILD.md.`;
    log.error(msg);
    dialog.showErrorBox('PlanOp — errore di avvio', msg);
    return Promise.reject(new Error('mongod not found'));
  }

  const args = [
    '--port', String(MONGO_PORT),
    '--bind_ip', MONGO_HOST,
    '--dbpath', dbPath,
    '--logpath', logPath,
    '--logappend',
    '--quiet',
  ];

  log.info(`Starting mongod: ${mongodPath} ${args.join(' ')}`);
  mongoProc = spawn(mongodPath, args, { windowsHide: true });
  mongoProc.on('exit', (code, sig) => log.info(`mongod exited: code=${code} sig=${sig}`));
  mongoProc.on('error', (e) => log.error('mongod error:', e));

  return waitOn({
    resources: [`tcp:${MONGO_HOST}:${MONGO_PORT}`],
    timeout: 30000,
    interval: 500,
  });
}

function startBackend() {
  const binaryName = process.platform === 'win32' ? 'planop-backend.exe' : 'planop-backend';
  const backendBinary = resourcePath('backend', binaryName);
  const frontendDir = resourcePath('frontend');

  if (!fs.existsSync(backendBinary)) {
    const msg = `Backend eseguibile non trovato: ${backendBinary}\n\nEsegui prima la build PyInstaller (vedi DESKTOP_BUILD.md).`;
    log.error(msg);
    dialog.showErrorBox('PlanOp — errore di avvio', msg);
    return Promise.reject(new Error('backend not found'));
  }

  const env = {
    ...process.env,
    LOCAL_MODE: 'true',
    MONGO_URL: `mongodb://${MONGO_HOST}:${MONGO_PORT}`,
    DB_NAME: 'planop_local',
    STATIC_FRONTEND_DIR: frontendDir,
    CORS_ORIGINS: '*',
    HOST: BACKEND_HOST,
    PORT: String(BACKEND_PORT),
    // Personal API keys (opzionali) — impostati tramite Settings o config esterno
    EMERGENT_LLM_KEY: process.env.EMERGENT_LLM_KEY || '',
    ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || '',
    RESEND_API_KEY: process.env.RESEND_API_KEY || '',
  };

  log.info(`Starting backend: ${backendBinary}`);
  backendProc = spawn(backendBinary, [], { env, windowsHide: true });
  backendProc.stdout?.on('data', (d) => log.info(`[backend] ${d.toString().trim()}`));
  backendProc.stderr?.on('data', (d) => log.info(`[backend-err] ${d.toString().trim()}`));
  backendProc.on('exit', (code, sig) => log.info(`backend exited: code=${code} sig=${sig}`));
  backendProc.on('error', (e) => log.error('backend error:', e));

  return waitOn({
    resources: [`http-get://${BACKEND_HOST}:${BACKEND_PORT}/api/auth/me`],
    timeout: 60000,
    interval: 500,
    validateStatus: (s) => s >= 200 && s < 500, // any non-crash is fine
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'PlanOp',
    backgroundColor: '#0f172a',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Route external target=_blank links to the OS default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(BACKEND_URL)) return { action: 'allow' };
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.loadURL(BACKEND_URL);

  mainWindow.on('closed', () => { mainWindow = null; });
}

async function boot() {
  try {
    await startMongo();
    log.info('MongoDB ready');
    await startBackend();
    log.info('Backend ready');
    createWindow();
  } catch (e) {
    log.error('Boot failed:', e);
    dialog.showErrorBox('PlanOp — avvio fallito', `${e.message}\n\nControlla il file di log:\n${log.transports.file.getFile().path}`);
    app.quit();
  }
}

app.on('ready', boot);

app.on('window-all-closed', () => {
  killChildren();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', killChildren);
app.on('will-quit', killChildren);
process.on('exit', killChildren);
