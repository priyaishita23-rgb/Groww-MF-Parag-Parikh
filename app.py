"""Tiny stdlib-only web server for the FAQ assistant.

    python app.py            # http://127.0.0.1:8000
    python app.py --port 9000

No third-party dependencies, so there is nothing to pip install.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ppfaq.assistant import DISCLAIMER, EXAMPLES, WELCOME, Assistant

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")

ASSISTANT = Assistant()


class Handler(BaseHTTPRequestHandler):
    server_version = "PPFAQ/1.0"

    # -- helpers -----------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, fmt, *args):  # quieter console
        return

    # -- routes ------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            with open(os.path.join(WEB, "index.html"), "rb") as fh:
                self._send(200, fh.read(), "text/html; charset=utf-8")
        elif self.path == "/api/meta":
            self._json(200, {
                "welcome": WELCOME,
                "examples": EXAMPLES,
                "disclaimer": DISCLAIMER,
                "schemes": ASSISTANT.scheme_names(),
                "corpus_last_updated": ASSISTANT.meta.get("corpus_last_updated"),
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/api/ask":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return
        # The question is answered and discarded - nothing is logged or persisted.
        answer = ASSISTANT.ask(str(payload.get("question", "")))
        self._json(200, answer.to_dict())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the facts-only MF FAQ assistant")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"FAQ assistant on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
