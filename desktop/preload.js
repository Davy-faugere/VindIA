/**
 * Pont sécurisé entre la page VindIA et le poste de travail.
 *
 * La page n'a JAMAIS accès à Node ni au disque : elle ne peut appeler que les
 * quelques fonctions exposées ici, et seuls les dossiers explicitement choisis par
 * l'utilisateur sont accessibles (vérifié côté processus principal).
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vindiaDesktop', {
  // Indique à la page qu'elle tourne dans l'application (et non dans un navigateur).
  isDesktop: true,
  version: '1.1.0',

  // Dossiers de travail
  pickFolder:   ()            => ipcRenderer.invoke('vindia:pickFolder'),
  folders:      ()            => ipcRenderer.invoke('vindia:folders'),
  removeFolder: (dir)         => ipcRenderer.invoke('vindia:removeFolder', dir),
  openFolder:   (dir)         => ipcRenderer.invoke('vindia:openFolder', dir),

  // Fichiers (contenu transporté en base64 : binaire sûr)
  listFiles: (dir)             => ipcRenderer.invoke('vindia:listFiles', dir),
  readFile:  (dir, rel)        => ipcRenderer.invoke('vindia:readFile', dir, rel),
  writeFile: (dir, rel, b64)   => ipcRenderer.invoke('vindia:writeFile', dir, rel, b64),

  // Menu « Ajouter un dossier de travail… »
  onMenuPickFolder: (cb) => ipcRenderer.on('vindia:menuPickFolder', () => cb()),
});
