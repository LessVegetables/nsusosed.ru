#!/usr/bin/env python3
"""Local dev server for the nsusosed.ru frontend. Python standard library only.

- Serves this folder the way production nginx does: /matches -> matches.html,
  /join -> join.html, unknown paths -> 404.html (see README.md, "nginx").
- Proxies /api/* to the backend (default http://localhost:8000), so the
  browser sees one origin and the session cookie just works.
- Serves /media/* (listing photos) from the backend's MEDIA_DIR
  (default backend/media, i.e. MEDIA_DIR=media in the backend's .env).

    python3 frontend/dev_server.py                 # http://localhost:8080
    python3 frontend/dev_server.py --port 3000 --backend http://localhost:8001

Set the backend's PUBLIC_ORIGIN to this server's address (http://localhost:8080):
the backend rejects POST/PUT/DELETE whose Origin header doesn't match it, and
builds invite links from it.
"""

import argparse
import http.client
import http.server
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Hop-by-hop headers are about one connection and must not be forwarded.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    backend = None  # urllib.parse.SplitResult, set in main()
    media_dir = None  # Path, set in main()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".svg": "image/svg+xml",
        ".json": "application/json",
    }

    # ---- static files, with the same fallbacks as production nginx

    def resolve(self):
        """Return (file path, status) for the request path, like
        `try_files $uri $uri.html $uri/ =404` with error_page 404."""
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith("/media/"):
            media = (self.media_dir / urllib.parse.unquote(path[len("/media/"):])).resolve()
            if media.is_relative_to(self.media_dir) and media.is_file():
                return media, 200
            return ROOT / "404.html", 404
        candidate = Path(self.translate_path(path))
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate / "index.html", 200
        if candidate.is_file():
            return candidate, 200
        html = candidate.with_name(candidate.name + ".html")
        if path != "/" and html.is_file():
            return html, 200
        return ROOT / "404.html", 404

    def serve_static(self, head_only=False):
        file, status = self.resolve()
        in_root = file.is_relative_to(ROOT)
        if file.name.startswith(".") or (in_root and "tools" in file.relative_to(ROOT).parts[:1]) or file.suffix == ".py":
            file, status = ROOT / "404.html", 404
        try:
            body = file.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(status)
        self.send_header("Content-Type", self.guess_type(str(file)))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    # ---- /api proxy

    def is_api(self):
        path = urllib.parse.urlsplit(self.path).path
        return path == "/api" or path.startswith("/api/")

    def proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["Host"] = self.backend.netloc
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "http"

        conn_cls = http.client.HTTPSConnection if self.backend.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(self.backend.hostname, self.backend.port, timeout=30)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError as exc:
            self.log_error("backend unavailable: %s", exc)
            # Like nginx: a plain 502 page, not the API's JSON error format.
            msg = b"502 Bad Gateway: backend is not running\n"
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        finally:
            conn.close()

        self.send_response(resp.status, resp.reason)
        # getheaders() keeps repeated headers (several Set-Cookie) separate.
        # send_response() already wrote Server and Date.
        for key, value in resp.getheaders():
            if key.lower() not in HOP_BY_HOP | {"server", "date"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---- methods

    def do_GET(self):
        if self.is_api():
            self.proxy()
        else:
            self.serve_static()

    def do_HEAD(self):
        if self.is_api():
            self.proxy()
        else:
            self.serve_static(head_only=True)

    def do_POST(self):
        self.api_only()

    def do_PUT(self):
        self.api_only()

    def do_DELETE(self):
        self.api_only()

    def do_PATCH(self):
        self.api_only()

    def api_only(self):
        if self.is_api():
            self.proxy()
        else:
            body = json.dumps({"error": "method not allowed"}).encode()
            self.send_response(405)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost", help="address to listen on (default: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on (default: 8080)")
    parser.add_argument("--backend", default="http://localhost:8000", help="backend URL (default: http://localhost:8000)")
    parser.add_argument("--media-dir", default=str(ROOT.parent / "backend" / "media"),
                        help="the backend's MEDIA_DIR, served as /media/ (default: backend/media)")
    args = parser.parse_args()
    Handler.media_dir = Path(args.media_dir).resolve()

    backend = urllib.parse.urlsplit(args.backend)
    if backend.scheme not in ("http", "https") or not backend.hostname:
        sys.exit(f"--backend must look like http://host:port, got {args.backend!r}")
    Handler.backend = backend

    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    origin = f"http://{args.host}:{args.port}"
    print(f"Frontend:  {origin}")
    print(f"API proxy: {origin}/api/* -> {args.backend}")
    print(f"Backend .env needs PUBLIC_ORIGIN={origin}")
    print(f"No backend? Use the mock API: {origin}/?mock=1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
