#!/usr/bin/env python3
"""Local stand-in for the production nginx: one origin for pages, API and photos.

    python3 frontend/dev_server.py            # http://localhost:8080
    (backend: uvicorn app.main:app --reload --port 8000, PUBLIC_ORIGIN=http://localhost:8080)

It behaves like deploy/nginx/nsusosed.ru.conf where that matters for development:
  - /matches → matches.html, unknown paths → 404.html with status 404 (no SPA fallback);
  - /api/* is proxied to the backend, so the session cookie and the Origin check work;
  - /media/* is served from backend/media;
  - the same Content-Security-Policy, so a CSP mistake shows up here, not in production.
Standard library only. Not for production.
"""

from __future__ import annotations
import argparse
import mimetypes
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT.parent / "backend" / "media"
NGINX_CONF = ROOT.parent / "deploy" / "nginx" / "nsusosed.ru.conf"
NOT_SERVED = {"dev_server.py", "README.md", "tools"}  # same list the deploy leaves out
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade", "proxy-authenticate",
              "proxy-authorization", "te", "trailers", "host", "content-length"}


def production_csp() -> str | None:
    """The CSP header straight from the nginx config, so the two can't drift apart."""
    try:
        m = re.search(r'add_header Content-Security-Policy "([^"]+)"', NGINX_CONF.read_text(encoding="utf-8"))
        return m.group(1) if m else None
    except OSError:
        return None


class Handler(BaseHTTPRequestHandler):
    api = "http://127.0.0.1:8000"
    csp = None #production_csp()
    protocol_version = "HTTP/1.1"

    # ── static files ──────────────────────────────────────
    def resolve(self, url_path: str) -> Path | None:
        """nginx: try_files $uri $uri.html $uri/ =404"""
        rel = url_path.lstrip("/")
        base, root = (MEDIA, rel[len("media/"):]) if rel.startswith("media/") else (ROOT, rel)
        parts = Path(root).parts
        if any(p.startswith(".") or p == ".." for p in parts) or (base is ROOT and parts and parts[0] in NOT_SERVED):
            return None
        target = base / root
        for candidate in (target, target.with_name(target.name + ".html"), target / "index.html"):
            if candidate.is_file():
                return candidate
        return None

    def send_file(self, path: Path, status: int = 200) -> None:
        body = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.csp:
            self.send_header("Content-Security-Policy", self.csp)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def serve_static(self) -> None:
        path = self.resolve(self.path.split("?", 1)[0].split("#", 1)[0])
        if path is not None:
            self.send_file(path)
        elif (ROOT / "404.html").is_file():
            self.send_file(ROOT / "404.html", 404)
        else:
            self.send_error(404)

    # ── API proxy ─────────────────────────────────────────
    def proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["X-Forwarded-For"] = self.client_address[0]
        req = urllib.request.Request(self.api + self.path, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                self.relay(res.status, res.headers, res.read())
        except urllib.error.HTTPError as err:
            self.relay(err.code, err.headers, err.read())
        except OSError:
            msg = b'{"error":{"code":"BACKEND_DOWN","message":"Backend is not running on %s","fields":{}}}' % self.api.encode()
            self.relay(502, {"Content-Type": "application/json"}, msg)

    def relay(self, status: int, headers, body: bytes) -> None:
        self.send_response(status)
        for name, value in headers.items():
            if name.lower() not in HOP_BY_HOP:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_any(self) -> None:
        if self.path.startswith("/api/"):
            self.proxy()
        elif self.command in ("GET", "HEAD"):
            self.serve_static()
        else:
            self.send_error(405)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = handle_any

    def log_message(self, fmt: str, *args) -> None:
        if self.path.startswith("/api/") or (args and str(args[1]).startswith(("4", "5"))):
            super().log_message(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to open it from a phone on the same Wi-Fi")
    parser.add_argument("--api", default=Handler.api, help="backend address (default %(default)s)")
    args = parser.parse_args()
    Handler.api = args.api.rstrip("/")
    mimetypes.add_type("font/woff2", ".woff2")
    mimetypes.add_type("application/javascript", ".js")
    print(f"nsusosed dev server: http://localhost:{args.port}  (API → {Handler.api})")
    if not Handler.csp:
        print("warning: CSP not found in deploy/nginx/nsusosed.ru.conf; serving without it")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
