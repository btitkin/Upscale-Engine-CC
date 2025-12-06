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

        // mainWindow.webContents.openDevTools();
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
        const [cpu, mem, graphics, currentLoad, cpuTemp, battery] = await Promise.all([
            si.cpu(),
            si.mem(),
            si.graphics(),
            si.currentLoad(),
            si.cpuTemperature(),
            si.battery()
        ]);

        // Fetch real VRAM usage from backend if available
        let vramUsed = '0';
        let vramTotal = 12;

        try {
            const backendStats = await axios.get(`${BACKEND_URL}/system/stats`, { timeout: 500 });
            if (backendStats.data && backendStats.data.vram_usage) {
                vramUsed = backendStats.data.vram_usage.allocated_gb;
                // Use reserved as total or keep static 12? 
                // Better to show allocated/reserved or allocated/total_capacity
                // Let's use reserved as the "active" total, or just keep 12 as the card limit.
                // Actually, let's use the backend's reported reserved as "used" for a more conservative view,
                // or allocated. User complained about 12/12.
                // Let's use allocated for "Used" and 12 (or detected) for "Total".
            }
        } catch (e) {
            // Backend offline, ignore
        }

        const gpuController = graphics.controllers[0] || {};
        // If backend provided data, use it. Otherwise fallback to SI (which is often wrong on Windows)
        if (vramUsed === '0' && gpuController.vram) {
            vramUsed = (gpuController.vram / 1024).toFixed(1);
            vramTotal = (gpuController.vram / 1024).toFixed(0);
        }

        return {
            cpu: {
                load: Math.round(currentLoad.currentLoad),
                temp: cpuTemp.main || cpuTemp.cores?.[0] || null
            },
            memory: {
                used: (mem.used / 1024 / 1024 / 1024).toFixed(1),
                total: (mem.total / 1024 / 1024 / 1024).toFixed(0)
            },
            gpu: {
                name: gpuController.model || 'Unknown GPU',
                vramUsed: vramUsed.toString(),
                vramTotal: vramTotal,
                load: gpuController.utilizationGpu || null,
                temp: gpuController.temperatureGpu || null
            },
            psu: {
                watts: null
            }
        };
    } catch (error) {
        console.error('[SystemInfo] Error:', error);
        return {
            cpu: { load: 0, temp: null },
            memory: { used: 0, total: 64 },
            gpu: { name: 'Unknown', vramUsed: '0', vramTotal: 12, load: null, temp: null },
            psu: { watts: null }
        };
    }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('[App] Uncaught exception:', error);
});

console.log('[App] Electron main process loaded');
