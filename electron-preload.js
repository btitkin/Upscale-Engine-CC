// Expose system info to renderer
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
    getSystemInfo: () => ipcRenderer.invoke('get-system-info')
});
