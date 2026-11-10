const { app, BrowserWindow, Tray, nativeImage, ipcMain, Notification, Menu } = require('electron');
const path = require('path');

const isMac = process.platform === 'darwin';
let win;
let tray;

// Mac: traffic lights inset into the page. Windows: hide the title bar and
// let Windows draw its own min/max/close buttons over the top-right corner.
const chrome = isMac
  ? { titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 16, y: 16 } }
  : { titleBarStyle: 'hidden', titleBarOverlay: { color: '#00000000', symbolColor: '#6b4a42', height: 44 } };

function createWindow() {
  win = new BrowserWindow({
    width: 380,
    height: 640,
    minWidth: 340,
    minHeight: 580,
    resizable: true,
    ...chrome,
    icon: path.join(__dirname, 'assets', 'icon.png'),
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
  if (isMac) {
    tray = new Tray(nativeImage.createEmpty());
    tray.setTitle('🍎');
  } else {
    // Windows trays need a real icon; the time goes in the hover tooltip
    const img = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png')).resize({ width: 32, height: 32 });
    tray = new Tray(img);
  }
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

ipcMain.on('tray-title', (_e, title) => {
  if (!tray) return;
  if (isMac) tray.setTitle(title);
  else tray.setToolTip(title.replace('🍎', 'Pomme').trim() || 'Pomme');
});
ipcMain.on('notify', (_e, { title, body }) => {
  if (Notification.isSupported()) new Notification({ title, body, silent: true }).show();
});

app.whenReady().then(() => {
  createWindow();
  createTray();
  app.on('activate', () => { if (!win) createWindow(); else win.show(); });
});

// Keep running in the menu bar (or tray on Windows) when the window closes.
app.on('window-all-closed', () => {});
