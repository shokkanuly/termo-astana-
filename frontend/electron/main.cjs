const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow () {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    title: "Astana Twin: Combined Operator Dashboard",
    backgroundColor: "#0a0c0f"
  });

  // Load from Vite dev server during development, or built files in production
  const startUrl = process.env.ELECTRON_DEV_URL || `file://${path.join(__dirname, '../dist/index.html')}`;
  
  // Set window menu
  win.setMenuBarVisibility(false);
  
  win.loadURL(startUrl);

  // If in development mode, open DevTools
  if (process.env.ELECTRON_DEV_URL) {
    win.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
