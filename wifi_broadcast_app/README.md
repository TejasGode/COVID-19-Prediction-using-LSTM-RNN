# WiFi One-Way Text Broadcast App

This mini app lets one **host** device broadcast text messages to all **receiver** devices connected to the same WiFi network.

## Features
- One-way communication (host ➜ all receivers)
- Real-time style updates via lightweight polling
- No external dependencies (Python standard library only)

## Setup
```bash
cd wifi_broadcast_app
python app.py
```

The app runs on `http://0.0.0.0:5000`.

## Usage
1. Open host page on host device:
   - `http://HOST_IP:5000/`
2. Open receiver page on every other device:
   - `http://HOST_IP:5000/receiver`
3. Type a message on host page and click **Send to all devices**.

## Notes
- All devices must be on the same WiFi network.
- Keep receiver page open to receive new messages.
- Current implementation stores messages in memory only.
