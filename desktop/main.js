/**
 * VindIA — application de bureau (Windows).
 *
 * Rôle : afficher VindIA dans une vraie fenêtre, et surtout faire le pont avec les
 * FICHIERS LOCAUX du poste — ce que le navigateur seul ne permet pas.
 *
 * Rappel d'architecture : le moteur de VindIA (LLM) tourne sur le serveur. Pour qu'il
 * puisse lire un fichier du poste, son contenu doit remonter au serveur. L'application
 * assure cette synchronisation de façon intégrée et silencieuse — c'est ce qui remplace
 * Syncthing : une seule app, aucune configuration.
 */

const { app, BrowserWindow, dialog, ipcMain, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

const APP_URL = process.env.VINDIA_URL || 'https://vindia.faugere-davy.fr';
const CONFIG_FILE = path.join(app.getPath('userData'), 'vindia-config.json');

let win = null;

// ── Configuration locale (dossiers de travail choisis par l'utilisateur) ──────
function readConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')); }
  catch (e) { return { folders: [] }; }
}
function writeConfig(cfg) {
  try { fs.mkdirSync(path.dirname(CONFIG_FILE), { recursive: true }); } catch (e) {}
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2), 'utf8');
}

// ── Lecture d'un dossier local ───────────────────────────────────────────────
// Extensions exploitables par VindIA (mêmes que le serveur) : inutile d'envoyer
// des binaires qu'elle ne sait pas lire.
const OK_EXT = new Set([
  '.txt', '.md', '.markdown', '.csv', '.tsv', '.log', '.json', '.yaml', '.yml',
  '.html', '.htm', '.docx', '.xlsx', '.pptx', '.pdf',
  '.mp3', '.wav', '.m4a', '.mp4', '.mov', '.mkv', '.webm',
]);
const MAX_FILE = 10 * 1024 * 1024;   // 10 Mo, aligné sur la limite serveur

function listFolder(dir, base = dir, out = []) {
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return out; }
  for (const e of entries) {
    if (e.name.startsWith('.')) continue;              // fichiers cachés ignorés
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { listFolder(full, base, out); continue; }
    const ext = path.extname(e.name).toLowerCase();
    if (!OK_EXT.has(ext)) continue;
    let st; try { st = fs.statSync(full); } catch (e) { continue; }
    if (st.size === 0 || st.size > MAX_FILE) continue;
    out.push({ rel: path.relative(base, full).split(path.sep).join('/'), size: st.size, mtime: st.mtimeMs });
  }
  return out;
}

// ── Pont exposé à la page (via preload) ──────────────────────────────────────
ipcMain.handle('vindia:pickFolder', async () => {
  const r = await dialog.showOpenDialog(win, {
    title: 'Choisir un dossier de travail pour VindIA',
    properties: ['openDirectory'],
  });
  if (r.canceled || !r.filePaths.length) return null;
  const dir = r.filePaths[0];
  const cfg = readConfig();
  if (!cfg.folders.includes(dir)) { cfg.folders.push(dir); writeConfig(cfg); }
  return dir;
});

ipcMain.handle('vindia:folders', () => readConfig().folders);

ipcMain.handle('vindia:removeFolder', (_e, dir) => {
  const cfg = readConfig();
  cfg.folders = cfg.folders.filter(f => f !== dir);
  writeConfig(cfg);
  return cfg.folders;
});

ipcMain.handle('vindia:listFiles', (_e, dir) => {
  if (!readConfig().folders.includes(dir)) return [];   // seulement les dossiers autorisés
  return listFolder(dir);
});

ipcMain.handle('vindia:readFile', (_e, dir, rel) => {
  if (!readConfig().folders.includes(dir)) return null;
  const full = path.resolve(dir, rel);
  if (!full.startsWith(path.resolve(dir))) return null;  // anti-traversée de dossier
  try { return fs.readFileSync(full).toString('base64'); } catch (e) { return null; }
});

ipcMain.handle('vindia:writeFile', (_e, dir, rel, base64) => {
  if (!readConfig().folders.includes(dir)) return false;
  const full = path.resolve(dir, rel);
  if (!full.startsWith(path.resolve(dir))) return false;
  try {
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, Buffer.from(base64, 'base64'));
    return true;
  } catch (e) { return false; }
});

ipcMain.handle('vindia:openFolder', (_e, dir) => { shell.openPath(dir); });

// ── Fenêtre ──────────────────────────────────────────────────────────────────
function createWindow() {
  win = new BrowserWindow({
    width: 1100, height: 820, minWidth: 420, minHeight: 560,
    title: 'VindIA',
    backgroundColor: '#fafafe',
    icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,      // la page n'accède jamais directement à Node
      nodeIntegration: false,
      spellcheck: true,
    },
  });

  win.loadURL(APP_URL);

  // Le micro est indispensable (dictée vocale) : on l'autorise pour notre domaine.
  win.webContents.session.setPermissionRequestHandler((wc, permission, callback) => {
    const url = wc.getURL() || '';
    const ours = url.startsWith(APP_URL);
    callback(ours && ['media', 'audioCapture', 'clipboard-read', 'notifications'].includes(permission));
  });

  // Les liens externes s'ouvrent dans le navigateur, pas dans l'application.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(APP_URL)) { shell.openExternal(url); return { action: 'deny' }; }
    return { action: 'allow' };
  });

  // Page inaccessible (serveur down, pas de réseau) → message clair plutôt qu'un écran blanc.
  win.webContents.on('did-fail-load', (_e, code, desc) => {
    if (code === -3) return;   // navigation annulée : sans conséquence
    win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
      <body style="font-family:system-ui;padding:40px;color:#1B1E2B;background:#fafafe">
        <h2>VindIA n'est pas joignable</h2>
        <p style="color:#6b7280">Vérifie ta connexion internet, puis relance l'application.</p>
        <p style="color:#9ca3af;font-size:13px">Détail technique : ${desc}</p>
      </body>`));
  });

  const template = [
    { label: 'Fichier', submenu: [
      { label: 'Ajouter un dossier de travail…', click: () => win.webContents.send('vindia:menuPickFolder') },
      { type: 'separator' },
      { role: 'quit', label: 'Quitter' },
    ]},
    { label: 'Édition', submenu: [
      { role: 'undo', label: 'Annuler' }, { role: 'redo', label: 'Rétablir' }, { type: 'separator' },
      { role: 'cut', label: 'Couper' }, { role: 'copy', label: 'Copier' }, { role: 'paste', label: 'Coller' },
      { role: 'selectAll', label: 'Tout sélectionner' },
    ]},
    { label: 'Affichage', submenu: [
      { role: 'reload', label: 'Recharger' }, { role: 'resetZoom', label: 'Taille normale' },
      { role: 'zoomIn', label: 'Agrandir' }, { role: 'zoomOut', label: 'Réduire' },
      { type: 'separator' }, { role: 'togglefullscreen', label: 'Plein écran' },
    ]},
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// Une seule instance : relancer l'app ramène la fenêtre existante au premier plan.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(createWindow);
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
}
