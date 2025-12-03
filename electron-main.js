/**
 * LumaScale Electron Main Process - SIMPLIFIED FOR DEBUGGING
 * Skip backend health check temporarily to see if window opens
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const axios = require('axios');
const si = require('systeminformation');

let mainWindow;
const BACKEND_URL = 'http://localhost:5555';

// Create main application window
function createWindow() {
    console.log('[Window] Creating main window...');

    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 700,
        title: 'Upscale Engine CC',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'electron-preload.js')
        },
        backgroundColor: '#0a0a0a',
        show: false,
    });

    console.log('[Window] Window created, loading URL...');

    // Load the app
    if (app.isPackaged) {
        mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
    } else {
        // Development: load from Vite dev server
        console.log('[Window] Loading from http://localhost:5173');
        mainWindow.loadURL('http://localhost:5173')
            .then(() => console.log('[Window] URL loaded successfully'))
            .catch(err => console.error('[Window] Failed to load URL:', err));

        mainWindow.webContents.openDevTools();
    }

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        console.log('[Window] Ready to show, displaying window...');
        mainWindow.show();
    });

    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
        console.error('[Window] Failed to load:', errorCode, errorDescription);
    });

    // Handle window close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// App lifecycle - SIMPLIFIED
app.on('ready', async () => {
    console.log('[App] Electron ready event fired');
    console.log('[App] Creating window immediately (backend already running separately)...');

    try {
        createWindow();
        console.log('[App] Window creation initiated!');
    } catch (error) {
        console.error('[App] Failed to create window:', error);
    }
});

app.on('window-all-closed', () => {
    console.log('[App] All windows closed, quitting...');
    app.quit();
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

// IPC handlers
ipcMain.handle('get-backend-url', () => {
    return BACKEND_URL;
});

ipcMain.handle('backend-status', async () => {
    try {
        const response = await axios.get(`${BACKEND_URL}/status`);
        return { success: true, data: response.data };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// System information handler
ipcMain.handle('get-system-info', async () => {
    try {
        const [cpu, mem, graphics, currentLoad] = await Promise.all([
            si.cpu(),
            si.mem(),
            si.graphics(),
            si.currentLoad()
        ]);

        const gpuController = graphics.controllers[0] || {};

        return {
            cpu: {
                load: Math.round(currentLoad.currentLoad)
            },
            memory: {
                used: (mem.used / 1024 / 1024 / 1024).toFixed(1), // GB
                total: (mem.total / 1024 / 1024 / 1024).toFixed(0) // GB
            },
            gpu: {
                name: gpuController.model || 'Unknown GPU',
                vramUsed: gpuController.vram ? (gpuController.vram * 0.3).toFixed(1) : 0, // Estimate
                vramTotal: gpuController.vram || 12, // MB -> GB conversion or default
                load: gpuController.utilizationGpu || 0,
                temp: gpuController.temperatureGpu || 0
            }
        };
    } catch (error) {
        console.error('[SystemInfo] Error:', error);
        return {
            cpu: { load: 0 },
            memory: { used: 0, total: 64 },
            gpu: { name: 'Unknown', vramUsed: 0, vramTotal: 12, load: 0, temp: 0 }
        };
    }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('[App] Uncaught exception:', error);
});

console.log('[App] Electron main process loaded');
