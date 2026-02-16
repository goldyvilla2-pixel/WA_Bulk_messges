const bulkForm = document.getElementById('bulkForm');
const statusSection = document.getElementById('statusSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const logsContainer = document.getElementById('logs');
const submitBtn = document.getElementById('submitBtn');
const stopBtn = document.getElementById('stopBtn');
const logoutBtn = document.getElementById('logoutBtn');
const killBtn = document.getElementById('killBtn');
const accountInfo = document.getElementById('accountInfo');
const connectedAccountName = document.getElementById('connectedAccountName');

const qrSection = document.getElementById('qrSection');
const qrImage = document.getElementById('qrImage');

const csvInput = document.getElementById('csv_file');
const removeCsvBtn = document.getElementById('remove-csv');
const csvMsg = document.getElementById('csv-file-msg');

const imageInput = document.getElementById('image');
const removeImageBtn = document.getElementById('remove-image');
const imageMsg = document.getElementById('image-file-msg');

const statTotal = document.getElementById('stat-total');
const statSuccess = document.getElementById('stat-success');
const statFailed = document.getElementById('stat-failed');

let statusInterval;

// File Input Listeners
csvInput.addEventListener('change', function (e) {
    if (e.target.files.length > 0) {
        csvMsg.textContent = e.target.files[0].name;
        removeCsvBtn.classList.remove('hidden');

        const reader = new FileReader();
        reader.onload = function (event) {
            const text = event.target.result;
            const lines = text.split('\n').filter(line => line.trim().length > 0);
            statTotal.textContent = Math.max(0, lines.length - 1);
        };
        reader.readAsText(e.target.files[0]);
    }
});

removeCsvBtn.addEventListener('click', function () {
    csvInput.value = '';
    csvMsg.textContent = "Upload .csv with phone numbers";
    removeCsvBtn.classList.add('hidden');
    statTotal.textContent = '0';
});

imageInput.addEventListener('change', function (e) {
    if (e.target.files.length > 0) {
        imageMsg.textContent = e.target.files[0].name;
        removeImageBtn.classList.remove('hidden');
    }
});

removeImageBtn.addEventListener('click', function () {
    imageInput.value = '';
    imageMsg.textContent = "Choose an image or drag it here";
    removeImageBtn.classList.add('hidden');
});

// Logout Support
logoutBtn.addEventListener('click', async () => {
    if (confirm("Reset WhatsApp session? You will need to re-scan the QR code.")) {
        try {
            await fetch('/logout');
            window.location.reload();
        } catch (error) {
            alert("Error logging out.");
        }
    }
});

// Stop Task Support
stopBtn.addEventListener('click', async () => {
    if (confirm("Are you sure you want to stop the current task?")) {
        try {
            await fetch('/stop-task');
        } catch (error) {
            console.error('Error stopping task:', error);
        }
    }
});

// Kill Switch Support
killBtn.addEventListener('click', async () => {
    if (confirm("💀 WARNING: This will FORCE KILL the browser and reset the system state. Use this if the server feels stuck or busy. Continue?")) {
        try {
            const response = await fetch('/force-kill');
            const data = await response.json();
            alert(data.message);
            window.location.reload();
        } catch (error) {
            alert("Error sending kill signal. If the server is completely frozen, you may need to restart the terminal manually.");
        }
    }
});

// Form Submission
bulkForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(bulkForm);
    submitBtn.disabled = true;
    submitBtn.querySelector('.btn-text').textContent = 'Initializing...';
    statusSection.classList.remove('hidden');
    logsContainer.innerHTML = '<div>⏳ Connecting to WhatsApp...</div>';

    try {
        const response = await fetch('/start-bulk', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        statTotal.textContent = data.total;
        startStatusPolling();

    } catch (error) {
        console.error('Error starting bulk task:', error);
        logsContainer.innerHTML += `<div style="color: #f87171">❌ Connection error. If this persists, use the 💀 Kill Switch in the header.</div>`;
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').textContent = 'Start Bulk Send';
    }
});

function startStatusPolling() {
    if (statusInterval) clearInterval(statusInterval);

    statusInterval = setInterval(async () => {
        try {
            const response = await fetch('/status');
            const status = await response.json();

            updateUI(status);

            if (!status.is_running && status.total > 0 && status.current_index === status.total) {
                // Task finished
                clearInterval(statusInterval);
                submitBtn.disabled = false;
                submitBtn.querySelector('.btn-text').textContent = 'Start Bulk Send';
            }
        } catch (error) {
            console.error('Status polling error:', error);
        }
    }, 2000);
}

function updateUI(status) {
    const { current_index, total, success, failed, logs, qr_code, step, is_running, connected_user } = status;

    // Account Display & Logout Button
    if (connected_user) {
        accountInfo.classList.remove('hidden');
        logoutBtn.classList.remove('hidden');
        connectedAccountName.textContent = `Connected: ${connected_user}`;
    } else {
        accountInfo.classList.add('hidden');
        logoutBtn.classList.add('hidden');
    }

    // QR Code Display
    if (qr_code) {
        qrSection.classList.remove('hidden');
        qrImage.src = `data:image/png;base64,${qr_code}`;
    } else {
        qrSection.classList.add('hidden');
    }

    // Progress Bar
    const percent = total > 0 ? (current_index / total) * 100 : 0;
    progressFill.style.width = `${percent}%`;
    progressText.textContent = `${current_index}/${total} Processed`;

    // Stats
    statTotal.textContent = total;
    statSuccess.textContent = success;
    statFailed.textContent = failed;

    // Logs - Only update if count changes to prevent blinking
    if (logsContainer.dataset.lastLogCount != logs.length) {
        logsContainer.innerHTML = logs.map(log => `<div>${log}</div>`).join('');
        logsContainer.dataset.lastLogCount = logs.length;
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    // Button Visibility
    if (is_running) {
        stopBtn.classList.remove('hidden');
    } else {
        stopBtn.classList.add('hidden');
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').textContent = 'Start Bulk Send';
    }

    // QR Code Display
    if (qr_code && is_running) {
        qrSection.classList.remove('hidden');
        qrImage.src = `data:image/png;base64,${qr_code}`;
    } else {
        qrSection.classList.add('hidden');
    }
}

// Diagnostic Helper
async function refreshScreenshot() {
    const btn = document.querySelector('.refresh-btn');
    const placeholder = document.getElementById('screenshotPlaceholder');
    const img = document.getElementById('debugScreenshot');

    btn.disabled = true;
    btn.textContent = 'Updating...';
    placeholder.textContent = 'Capture in progress...';

    try {
        const response = await fetch('/api/screenshot');
        const data = await response.json();

        if (data.screenshot) {
            img.src = `data:image/png;base64,${data.screenshot}`;
            img.style.display = 'block';
            placeholder.style.display = 'none';
        } else {
            placeholder.textContent = data.error || "Could not capture. Browser might be closed.";
        }
    } catch (e) {
        placeholder.textContent = "Connection error.";
    } finally {
        btn.disabled = false;
        btn.textContent = 'Refresh Snapshot';
    }
}
