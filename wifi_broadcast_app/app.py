from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "0.0.0.0"
PORT = 5000

HOST_PAGE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>WiFi Broadcast Host</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 700px; margin: 2rem auto; padding: 1rem; }
    textarea { width: 100%; min-height: 120px; margin-bottom: 1rem; }
    button { padding: 0.7rem 1.1rem; font-size: 1rem; }
    .status { margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Host Broadcast Console</h1>
  <p>Broadcast text to all devices on the same WiFi.</p>
  <textarea id=\"message\" placeholder=\"Enter message...\"></textarea>
  <br />
  <button id=\"sendBtn\">Send to all devices</button>
  <div class=\"status\" id=\"status\"></div>
  <p>Receivers should open: <code>http://HOST_IP:5000/receiver</code></p>

  <script>
    const statusEl = document.getElementById('status');
    document.getElementById('sendBtn').addEventListener('click', async () => {
      const text = document.getElementById('message').value.trim();
      if (!text) {
        statusEl.style.color = '#c00';
        statusEl.textContent = 'Enter a message first.';
        return;
      }
      const resp = await fetch('/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ text })
      });
      const data = await resp.json();
      if (!resp.ok) {
        statusEl.style.color = '#c00';
        statusEl.textContent = data.error || 'Failed to send.';
        return;
      }
      statusEl.style.color = '#0a0';
      statusEl.textContent = `Sent! total messages: ${data.total_messages}`;
      document.getElementById('message').value = '';
    });
  </script>
</body>
</html>
"""

RECEIVER_PAGE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>WiFi Broadcast Receiver</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 700px; margin: 2rem auto; padding: 1rem; }
    .status { margin-bottom: 1rem; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 0.8rem; margin-bottom: 0.6rem; background: #fafafa; }
    .meta { color: #666; font-size: 0.85rem; margin-bottom: 0.25rem; }
  </style>
</head>
<body>
  <h1>Receiver Screen</h1>
  <div class=\"status\" id=\"status\">Connected. Waiting for messages...</div>
  <div id=\"messages\"></div>

  <script>
    let lastId = 0;
    const statusEl = document.getElementById('status');
    const messagesEl = document.getElementById('messages');

    async function poll() {
      try {
        const resp = await fetch(`/messages?since=${lastId}`);
        const data = await resp.json();
        for (const msg of data.messages) {
          lastId = Math.max(lastId, msg.id);
          const card = document.createElement('div');
          card.className = 'card';

          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = new Date(msg.sent_at * 1000).toLocaleTimeString();

          const body = document.createElement('div');
          body.textContent = msg.text;

          card.appendChild(meta);
          card.appendChild(body);
          messagesEl.prepend(card);
        }
        statusEl.style.color = '#0a0';
        statusEl.textContent = 'Connected. Waiting for messages...';
      } catch (error) {
        statusEl.style.color = '#c00';
        statusEl.textContent = 'Connection issue. Retrying...';
      }
    }

    setInterval(poll, 1200);
    poll();
  </script>
</body>
</html>
"""


class MessageStore:
    def __init__(self) -> None:
        self._messages = []
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, text: str) -> dict:
        with self._lock:
            message = {"id": self._next_id, "text": text, "sent_at": time.time()}
            self._next_id += 1
            self._messages.append(message)
            return message

    def since(self, message_id: int) -> list[dict]:
        with self._lock:
            return [m for m in self._messages if m["id"] > message_id]

    def count(self) -> int:
        with self._lock:
            return len(self._messages)


store = MessageStore()


class BroadcastHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(HOST_PAGE)
            return

        if parsed.path == "/receiver":
            self._send_html(RECEIVER_PAGE)
            return

        if parsed.path == "/messages":
            query = parse_qs(parsed.query)
            since = int(query.get("since", ["0"])[0])
            self._send_json({"messages": store.since(since)})
            return

        if parsed.path == "/health":
            self._send_json({"ok": True, "messages": store.count()})
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/send":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        text = str(payload.get("text", "")).strip()

        if not text:
            self._send_json({"ok": False, "error": "Text message cannot be empty."}, status=400)
            return

        message = store.add(text)
        self._send_json({"ok": True, "message": message, "total_messages": store.count()})

    def log_message(self, format: str, *args) -> None:
        return


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BroadcastHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
