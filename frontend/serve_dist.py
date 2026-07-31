#!/usr/bin/env python3
"""Serve frontend dist/ and proxy /api to backend :8000 (no file watchers)."""

from __future__ import annotations

import http.client
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent / "dist"
API_HOST = "127.0.0.1"
API_PORT = 8000
PORT = 5173


class Handler(BaseHTTPRequestHandler):
    def _proxy(self) -> None:
        conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=300)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        conn.request(self.command, self.path, body=body, headers=headers)
        resp = conn.getresponse()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in {"transfer-encoding", "connection"}:
                continue
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp.read())
        conn.close()

    def _static(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        file_path = (ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(ROOT)) or not file_path.is_file():
            file_path = ROOT / "index.html"
        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api"):
            self._proxy()
        else:
            self._static()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api"):
            self._proxy()
        else:
            self.send_error(404)

    def do_PUT(self) -> None:  # noqa: N802
        self.do_POST()

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    if not ROOT.exists():
        raise SystemExit("dist/ missing — run npm run build first")
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving {ROOT} on http://127.0.0.1:{PORT} (API -> {API_HOST}:{API_PORT})")
    httpd.serve_forever()
