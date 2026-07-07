from __future__ import annotations

import argparse
import http.client
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


FRONTEND_DIR = Path(__file__).resolve().parent


class FrontendDevHandler(SimpleHTTPRequestHandler):
    backend_base = "http://127.0.0.1:8000"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy_request()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy_request()
            return
        self.send_error(405, "Method Not Allowed")

    def _proxy_request(self) -> None:
        target = urlsplit(self.backend_base)
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=600)
        try:
            body = None
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 0:
                body = self.rfile.read(content_length)

            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"host", "connection"}
            }
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()

            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() in {"transfer-encoding", "connection"}:
                    continue
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)
        finally:
            connection.close()

    def end_headers(self):
        if self.path.endswith(".js"):
            content_type, _ = mimetypes.guess_type(self.path)
            if content_type:
                self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agent-RAG frontend dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    FrontendDevHandler.backend_base = args.backend
    server = ThreadingHTTPServer((args.host, args.port), FrontendDevHandler)
    print(f"Frontend dev server running at http://{args.host}:{args.port} -> proxy {args.backend}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
