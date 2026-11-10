const { app, BrowserWindow, Tray, nativeImage, ipcMain, Notification, Menu } = require('electron');
const path = require('path');

let win;
let tray;

function createWindow() {
  win = new BrowserWindow({
    width: 380,
    height: 640,
    minWidth: 340,
    minHeight: 580,
    resizable: true,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: '#f7efeb',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.once('ready-to-show', () => win.show());
  // dev: POMME_SHOT=/path.png captures the window and quits
  if (process.env.POMME_SHOT) {
    win.webContents.on('console-message', (e) => console.log('[renderer]', e.message));
    win.webContents.once('did-finish-load', () => setTimeout(async () => {
      if (process.env.POMME_JS) await win.webContents.executeJavaScript(process.env.POMME_JS).catch((e) => console.error(e));
      setTimeout(async () => {
        const img = await win.webContents.capturePage();
        require('fs').writeFileSync(process.env.POMME_SHOT, img.toPNG());
        app.exit(0);
      }, +(process.env.POMME_WAIT || 800));
    }, 2500));
  }
  win.on('closed', () => { win = null; });
}

function createTray() {
  tray = new Tray(nativeImage.createEmpty());
  tray.setTitle('🍎');
  tray.setToolTip('Pomme');
  tray.on('click', () => {
    if (!win) createWindow();
    else { win.show(); win.focus(); }
  });
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Pomme', click: () => (win ? win.show() : createWindow()) },
    { label: 'Start / Pause', click: () => win && win.webContents.send('toggle') },
    { type: 'separator' },
    { label: 'Quit', role: 'quit' },
  ]));
}

ipcMain.on('tray-title', (_e, title) => tray && tray.setTitle(title));
ipcMain.on('notify', (_e, { title, body }) => {
  if (Notification.isSupported()) new Notification({ title, body, silent: true }).show();
});

app.whenReady().then(() => {
  createWindow();
  createTray();
  app.on('activate', () => { if (!win) createWindow(); else win.show(); });
});

// Keep running in the menu bar when the window closes, like most timers.
app.on('window-all-closed', () => {});
