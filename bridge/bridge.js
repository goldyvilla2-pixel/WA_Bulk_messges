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
        dataPath: path.join(__dirname, '.wwebjs_auth')
    }),
    puppeteer: {
        headless: true, // Run in background
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
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

// Endpoint to send message
app.post('/send', async (req, res) => {
    const { phone, message, imagePath } = req.body;

    if (!isReady) {
        return res.status(503).json({ error: 'Bridge not ready. Please scan QR code.' });
    }

    try {
        const chatId = phone.includes('@c.us') ? phone : `${phone}@c.us`;

        if (imagePath && fs.existsSync(imagePath)) {
            const media = MessageMedia.fromFilePath(imagePath);
            await client.sendMessage(chatId, media, { caption: message });
            console.log(`🖼️ Sent image+caption to ${phone}`);
        } else {
            await client.sendMessage(chatId, message);
            console.log(`✍️ Sent text to ${phone}`);
        }

        res.json({ success: true });
    } catch (err) {
        console.error('Failed to send:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

const PORT = 3001;
app.listen(PORT, () => {
    console.log(`🚀 Bridge API listening on http://localhost:${PORT}`);
    client.initialize();
});
