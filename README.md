# 🚀 MASTODONITTECH (WA Bulk Message Shooter)

A powerful, human-mimicking WhatsApp bulk messaging tool built with FastAPI and WhatsApp-Web.js.

## ✨ Features
- **CSV Support**: Upload numbers with separate country codes.
- **Human Mimicry**: Randomized messaging speeds to avoid bans.
- **Node Bridge**: Uses a headless WhatsApp-Web.js client for stability.
- **QR Streaming**: View the WhatsApp QR code directly in the dashboard.
- **Image Support**: Send captions with image attachments.
- **Automatic Resume**: Saves your login session locally.

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-link>
   cd BulkWATItoll
   ```

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js Dependencies**:
   Navigate to the bridge folder and install required packages.
   ```bash
   cd bridge
   npm install
   ```

## 🚀 How to Run

1. **Start the Server**:
   ```bash
   python main.py
   ```

2. **Open the Dashboard**:
   Go to **[http://localhost:8000](http://localhost:8000)** in your browser.

3. **Send Messages**:
   - Upload your CSV (use the template provided in the app).
   - Type your message.
   - Click **Start Bulk Send**.
   - **Scan the QR Code** that appears on the dashboard (only required the first time).

## 🛡️ Anti-Ban Best Practices
WhatsApp is very strict about bulk messaging. To keep your account safe:
- **Warm up your account**: Don't use a brand-new WhatsApp account for bulk messaging. Use an account that has been active for at least a few weeks with regular personal chat history.
- **Start Small**: Begin with 10-20 messages per day and gradually increase.
- **Use High Delays**: We recommend a minimum delay of **45-60 seconds**.
- **Message Variation**: Use the built-in "Unique Padding" feature. Avoid sending the exact same text to hundreds of people.
- **Avoid Cold Contacts**: Sending messages to people who haven't saved your number increases the chance of being reported as spam.

## 📁 File Structure
- `main.py`: The FastAPI backend with "Smart Pause" logic.
- `bridge/`: Node.js WhatsApp logic with "Typing Simulation".
- `bridge/.wwebjs_auth/`: Stores your login session.
- `frontend/`: HTML, CSS, and JS for the dashboard.
- `uploads/`: Temporary storage for uploaded images.

## ⚠️ Important Notes
- **Do not touch the browser**: Once the automated Chrome window opens, let it do its work. Interacting with it manually might break the sequence.
- **Safety**: The engine now includes **Smart Pauses** (every 10 messages) and **Typing Simulation** to mimic human behavior.
- **Logout**: Use the button in the dashboard to clear your session and switch accounts.

---
Built with ❤️ for Bulk Messaging.
