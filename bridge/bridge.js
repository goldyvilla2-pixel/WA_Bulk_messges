const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const qr = require('qr-image');

const app = express();
app.use(bodyParser.json());

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '..', 'SESSIONS'),
        clientId: fs.existsSync(path.join(__dirname, '..', 'session_id.txt')) 
                  ? fs.readFileSync(path.join(__dirname, '..', 'session_id.txt'), 'utf8').trim() 
                  : 'default'
    }),
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1018.x.html',
    },
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-background-networking',
            '--disable-default-apps',
            '--disable-sync'
        ],
        env: {
            ...process.env,
            PUPPETEER_DISABLE_HEADLESS_WARNING: 'true'
        },
        executablePath: undefined,
    },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
});
let isReady = false;
let currentQR = null;
let deviceInfo = null;


client.on('qr', (text) => {
    console.log('--- SCAN THIS QR CODE ---');
    qrcode.generate(text, { small: true });
    console.log('-------------------------');

    // Generate base64 image
    const qr_png = qr.imageSync(text, { type: 'png' });
    currentQR = qr_png.toString('base64');
});

// Endpoint to get QR code
app.get('/qr', (req, res) => {
    if (currentQR && !isReady) {
        res.json({ qr: currentQR });
    } else {
        res.json({ qr: null });
    }
});

client.on('ready', () => {
    console.log('✅ WhatsApp Bridge is READY!');
    isReady = true;
    currentQR = null;

    // Capture device info
    try {
        const info = client.info;
        deviceInfo = {
            pushname: info.pushname,
            number: info.wid.user
        };
        console.log(`👤 Connected as: ${deviceInfo.pushname} (${deviceInfo.number})`);
    } catch (e) {
        console.log('Could not fetch device info:', e.message);
    }
});

client.on('authenticated', () => {
    console.log('🔐 Authenticated successfully.');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Authentication failure:', msg);
});

client.on('disconnected', (reason) => {
    console.log('🔌 Disconnected:', reason);
    isReady = false;
    deviceInfo = null;
});

// Endpoint to check status
app.get('/status', (req, res) => {
    res.json({ ready: isReady, deviceInfo: deviceInfo });
});

// Endpoint to logout cleanly
app.get('/logout', async (req, res) => {
    console.log('🚪 Logout requested. Cleaning up...');
    try {
        if (client) {
            await client.logout();
            isReady = false;
            deviceInfo = null;
            currentQR = null;
        }
        res.json({ success: true });
    } catch (e) {
        console.log('Logout error (might be already disconnected):', e.message);
        res.json({ success: true }); // Still return success to allow folder deletion
    }
});

client.on('error', (err) => {
    console.error('💥 WhatsApp Client Error:', err);
    if (err.message.includes('detached Frame')) {
        console.log('🔄 Detached frame detected. Client may need restart.');
    }
});

// Endpoint to send message
app.post('/send', async (req, res) => {
    const { phone, message, image, cta_text, cta_url } = req.body;
    const imagePath = image; 

    if (!isReady) {
        return res.status(503).json({ error: 'Bridge not ready. Please scan QR code.' });
    }

    try {
        const getValidChatId = async (p) => {
            try {
                const id = await client.getNumberId(p);
                return id ? id._serialized : (p.includes('@c.us') ? p : `${p}@c.us`);
            } catch (e) {
                return p.includes('@c.us') ? p : `${p}@c.us`;
            }
        };

        const chatId = await getValidChatId(phone);

        // Anti-Ban measure: Simulate typing
        try {
            console.log(`⏳ Simulating typing for ${phone}...`);
            await client.sendPresenceUpdate('composing', chatId);
            // Random typing duration between 3 to 7 seconds
            await new Promise(r => setTimeout(r, 3000 + Math.random() * 4000));
            await client.sendPresenceUpdate('paused', chatId);
        } catch (presenceErr) {
            console.log('Presence update failed (non-critical):', presenceErr.message);
        }

        const attemptSend = async () => {
            let finalMessage = message;
            
            // Append Smart-CTA Link if present (Safe for Non-API accounts)
            if (cta_text && cta_url) {
                finalMessage += `\n\n_________________________\n🔗 *${cta_text}*\n${cta_url}`;
            }

            if (imagePath && fs.existsSync(imagePath)) {
                const media = MessageMedia.fromFilePath(imagePath);
                await client.sendMessage(chatId, media, { caption: finalMessage });
                console.log(`🖼️ Sent image+caption to ${phone}`);
            } else {
                await client.sendMessage(chatId, finalMessage);
                console.log(`✍️ Sent text to ${phone}`);
            }
        };

        let retries = 1; // User requested: "no need to try again" on error
        let lastError = null;

        while (retries > 0) {
            try {
                await attemptSend();
                return res.json({ status: 'success', success: true });
            } catch (e) {
                lastError = e;
                const errMsg = e.message || "";
                if (errMsg.includes('detached Frame') || 
                    errMsg.includes('Execution context') || 
                    errMsg.includes('Navigating') || 
                    errMsg.includes('getChat') ||
                    errMsg.includes('Protocol error')) {
                    
                    console.log(`⚠️ Browser/Internal glitch (${errMsg}). Retrying send for ${phone}... (${retries - 1} left)`);
                    retries--;
                    if (retries > 0) {
                        await new Promise(r => setTimeout(r, 5000)); // wait 5s for re-attachment
                    }
                } else {
                    throw e;
                }
            }
        }

        // If we get here, all retries failed
        throw lastError;

    } catch (err) {
        console.error('❌ Failed to send:', err);
        let errorMsg = err.message || "Unknown error";
        if (errorMsg.includes('detached Frame') || errorMsg.includes('Execution context') || errorMsg.includes('getChat')) {
            errorMsg = `WhatsApp internal sync error (${errorMsg.includes('getChat') ? 'getChat undefined' : 'Detached Frame'}). Retries exhausted. Please try again or refresh the session.`;
        }
        res.status(500).json({ success: false, error: errorMsg });
    }
});

// Endpoint to simulate typing separately (if needed by main.py)
app.get('/typing', async (req, res) => {
    const { phone, duration } = req.query;
    if (!isReady) return res.status(503).json({ error: 'Bridge not ready' });
    
    try {
        const chatId = phone.includes('@c.us') ? phone : `${phone}@c.us`;
        await client.sendPresenceUpdate('composing', chatId);
        setTimeout(async () => {
            try { await client.sendPresenceUpdate('paused', chatId); } catch(e) {}
        }, (duration || 2) * 1000);
        res.json({ success: true });
    } catch (e) {
        res.json({ success: false, error: e.message });
    }
});


const PORT = 3001;
app.listen(PORT, () => {
    console.log(`🚀 Bridge API listening on http://localhost:${PORT}`);
    client.initialize();
});
