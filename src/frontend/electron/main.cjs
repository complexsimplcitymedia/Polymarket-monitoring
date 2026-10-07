const { app, BrowserWindow, ipcMain, Notification, shell, Menu } = require('electron');
const path = require('path');
const http = require('http');
const https = require('https');
const url = require('url');

// Environment & Configuration
const BACKEND_URL = process.env.POLYMARKET_BACKEND_URL || 'http://100.110.82.54:8001';
const IS_DEV = process.env.NODE_ENV === 'development' || !app.isPackaged;
const VITE_PORT = process.env.VITE_PORT || 5173;

// High-performance HTTP agent: No connection pool bottleneck, persistent keep-alive
const httpAgent = new http.Agent({
    keepAlive: true,
    maxSockets: Infinity,
    maxFreeSockets: 128,
    timeout: 30000,
});
const httpsAgent = new https.Agent({
    keepAlive: true,
    maxSockets: Infinity,
    maxFreeSockets: 128,
    timeout: 30000,
});

let mainWindow = null;
let bgPollingInterval = null;

// Support Linux display environments
if (process.env.XDG_SESSION_TYPE === 'wayland') {
    app.commandLine.appendSwitch('enable-features', 'UseOzonePlatform');
    app.commandLine.appendSwitch('ozone-platform', 'wayland');
}

// Disable GPU crashes in virtualized/headless environments if needed
app.commandLine.appendSwitch('disable-gpu-compositing');
app.commandLine.appendSwitch('ignore-certificate-errors');

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1600,
        height: 1000,
        minWidth: 1280,
        minHeight: 768,
        title: 'Wolf of PolyMarket | Powered by Wolf Logic',
        backgroundColor: '#020617',
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            contextIsolation: true,
            nodeIntegration: false,
            // CRITICAL: Disable background throttling so real-time ticks never freeze
            backgroundThrottling: false,
        },
    });

    const devServerUrl = process.env.VITE_DEV_SERVER_URL || `http://localhost:${VITE_PORT}`;

    if (IS_DEV && process.env.VITE_DEV_SERVER_URL) {
        mainWindow.loadURL(devServerUrl).catch(() => {
            mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
        });
    } else {
        const distIndex = path.join(__dirname, '../dist/index.html');
        mainWindow.loadFile(distIndex).catch((err) => {
            console.warn('Could not load dist, falling back to URL:', err);
            mainWindow.loadURL(devServerUrl);
        });
    }

    // External links open in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url: targetUrl }) => {
        if (!targetUrl.startsWith('http://localhost') && !targetUrl.startsWith('http://100.110.82.54')) {
            shell.openExternal(targetUrl);
            return { action: 'deny' };
        }
        return { action: 'allow' };
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    startBackgroundTicker();
}

/**
 * Unthrottled Node.js background ticker loop.
 * Runs independently of renderer UI thread, delivering market updates at high cadence.
 */
function startBackgroundTicker() {
    if (bgPollingInterval) clearInterval(bgPollingInterval);

    const tick = async () => {
        if (!mainWindow || mainWindow.isDestroyed()) return;
        try {
            const statusRes = await nodeRequest({
                url: `${BACKEND_URL}/api/trading/status`,
                method: 'GET',
            });
            mainWindow.webContents.send('bg:update', {
                type: 'TRADING_STATUS',
                timestamp: Date.now(),
                data: statusRes.data,
            });
        } catch (e) {
            // Heartbeat fails silently if backend temporarily down
        }
    };

    bgPollingInterval = setInterval(tick, 3000);
}

/**
 * Native Node.js request router.
 * Routes directly to FastAPI backend without browser 6-connection limits.
 */
function nodeRequest(options) {
    return new Promise((resolve, reject) => {
        let reqUrl = options.url || '';
        if (reqUrl.startsWith('/api')) {
            reqUrl = `${BACKEND_URL}${reqUrl}`;
        }

        // Handle query params
        if (options.params && typeof options.params === 'object') {
            const searchParams = new URLSearchParams();
            for (const [k, v] of Object.entries(options.params)) {
                if (v !== undefined && v !== null) searchParams.append(k, String(v));
            }
            const qs = searchParams.toString();
            if (qs) {
                reqUrl += (reqUrl.includes('?') ? '&' : '?') + qs;
            }
        }

        const parsed = url.parse(reqUrl);
        const isHttps = parsed.protocol === 'https:';
        const client = isHttps ? https : http;

        const headers = Object.assign(
            {
                'User-Agent': 'WolfOfPolyMarket-Desktop/1.0.0',
                'Accept': 'application/json, text/plain, */*',
            },
            options.headers || {}
        );

        let bodyData = null;
        if (options.data !== undefined && options.data !== null) {
            bodyData = typeof options.data === 'string' ? options.data : JSON.stringify(options.data);
            if (!headers['Content-Type']) {
                headers['Content-Type'] = 'application/json';
            }
            headers['Content-Length'] = Buffer.byteLength(bodyData);
        }

        const reqOptions = {
            hostname: parsed.hostname,
            port: parsed.port || (isHttps ? 443 : 80),
            path: parsed.path,
            method: (options.method || 'GET').toUpperCase(),
            headers: headers,
            agent: isHttps ? httpsAgent : httpAgent,
            timeout: options.timeout || 30000,
        };

        const req = client.request(reqOptions, (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => {
                const rawBuffer = Buffer.concat(chunks);
                const rawString = rawBuffer.toString('utf8');
                let parsedData = rawString;
                const contentType = res.headers['content-type'] || '';
                if (contentType.includes('application/json')) {
                    try {
                        parsedData = JSON.parse(rawString);
                    } catch (_) {}
                }

                resolve({
                    status: res.statusCode,
                    statusText: res.statusMessage,
                    headers: res.headers,
                    data: parsedData,
                });
            });
        });

        req.on('timeout', () => {
            req.destroy();
            reject(new Error(`Request timed out after ${reqOptions.timeout}ms`));
        });

        req.on('error', (err) => {
            reject(err);
        });

        if (bodyData) {
            req.write(bodyData);
        }
        req.end();
    });
}

// IPC Handlers
ipcMain.handle('api:request', async (_event, config) => {
    try {
        return await nodeRequest(config);
    } catch (err) {
        return {
            status: 500,
            statusText: err.message,
            headers: {},
            data: { error: err.message, isNodeError: true },
        };
    }
});

ipcMain.handle('app:notify', (_event, { title, body }) => {
    if (Notification.isSupported()) {
        new Notification({
            title: title || 'Wolf of PolyMarket',
            body: body || '',
            silent: false,
        }).show();
        return true;
    }
    return false;
});

// App lifecycle
app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (bgPollingInterval) clearInterval(bgPollingInterval);
    if (process.platform !== 'darwin') app.quit();
});
