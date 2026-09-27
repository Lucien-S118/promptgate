"""One-shot loopback credential entry for the fixed 100-row MVP evaluation.

No shell execution, credential storage, remote binding, or request-body logging.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs

from .evaluate import evaluate

HOST, PORT = "127.0.0.1", 8789


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new output directory.")
    token = secrets.token_urlsafe(32)
    state = {"status": "awaiting_key", "planned_calls": 100}

    def run(key):
        try:
            summary = evaluate(Path("data/processed/v1/mvp_100.jsonl"), args.output, "llm", key, 100)
            state.update(status="completed", summary=summary)
        except Exception:
            state.update(status="failed", detail="Inspect the sanitized run evidence; no credentials were saved.")
        finally:
            key = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body, content_type="text/html; charset=utf-8"):
            payload = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.headers.get("Host") != f"{HOST}:{PORT}":
                return self.reply(403, "Host rejected")
            if self.path == "/status":
                return self.reply(200, json.dumps(state), "application/json")
            if self.path != "/":
                return self.reply(404, "Not found")
            if state["status"] != "awaiting_key":
                return self.reply(200, f"<h1>PromptGate</h1><p>{state['status']}</p><p>Key was not saved.</p>")
            self.reply(200, f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>PromptGate 本机密钥输入</title>
<body style="font:18px system-ui;max-width:680px;margin:80px auto;line-height:1.8">
<h1>PromptGate 真实评估</h1><p>固定100条公开样本，每条最多一次GPT-4o-mini调用。</p>
<p>密钥仅用于此次运行，不保存到文件；页面仅监听本机。</p>
<form action="/start" method="post" autocomplete="off">
<input type="hidden" name="nonce" value="{token}">
<label>OpenRouter API key <input type="password" name="key" autocomplete="off" required style="width:100%;font-size:18px"></label>
<button type="submit" style="margin-top:20px;padding:12px">开始100条真实评估</button></form></body></html>''')

        def do_POST(self):
            if self.path != "/start" or self.headers.get("Host") != f"{HOST}:{PORT}":
                return self.reply(403, "Rejected")
            origin = self.headers.get("Origin")
            if origin not in (None, f"http://{HOST}:{PORT}"):
                return self.reply(403, "Origin rejected")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    raise ValueError()
                values = parse_qs(self.rfile.read(size).decode(), strict_parsing=True)
                if values.get("nonce") != [token] or state["status"] != "awaiting_key":
                    return self.reply(403, "One-shot token rejected")
                key = values.get("key", [""])[0].strip()
                if not key.startswith("sk-or-") or len(key) > 200:
                    return self.reply(400, "Invalid key format")
                state["status"] = "running"
                threading.Thread(target=run, args=(key,), daemon=True).start()
                values.clear()
                key = None
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            except (ValueError, UnicodeError):
                self.reply(400, "Invalid request")

    print(f"Local-only one-shot entry: http://{HOST}:{PORT}", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
