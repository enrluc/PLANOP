// Currently unused: the app runs as a plain SPA against the local backend.
// Placeholder for future native bridges (file dialogs, native notifications, etc.).
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('planop', {
  isDesktop: true,
  platform: process.platform,
});
