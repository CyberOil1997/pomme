const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pomme', {
  platform: process.platform,
  setTrayTitle: (t) => ipcRenderer.send('tray-title', t),
  notify: (title, body) => ipcRenderer.send('notify', { title, body }),
  onToggle: (fn) => ipcRenderer.on('toggle', fn),
});
