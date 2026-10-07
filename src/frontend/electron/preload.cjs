const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    isElectron: true,
    platform: process.platform,
    version: '1.0.0',

    // High performance IPC request proxy (bypasses browser connection limits)
    request: (config) => ipcRenderer.invoke('api:request', config),

    // Background streaming listeners
    onBackgroundUpdate: (callback) => {
        const handler = (_event, data) => callback(data);
        ipcRenderer.on('bg:update', handler);
        return () => ipcRenderer.removeListener('bg:update', handler);
    },

    // Native notifications
    notify: (title, body) => ipcRenderer.invoke('app:notify', { title, body }),

    // Window controls
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
});
