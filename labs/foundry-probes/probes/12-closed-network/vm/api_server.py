#!/usr/bin/env python3
"""VM 内に立てる検証用サーバー(標準ライブラリだけ。VM は B1s・パブリック IP なし)。

- :8080 簡単な HTTP API(OpenAPI ツールの呼び出し先)。/openapi.json に仕様を置く
- :8081 最小の MCP サーバー(Streamable HTTP の JSON 応答のみ。initialize / tools/list / tools/call)

どちらも要求元の IP・User-Agent・パスを /opt/probe/logs/server.log に 1 行 JSON で残す。
エージェントがサブネット経由で届いたなら、要求元はエージェントサブネット(10.40.0.0/24)の IP になる。
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_PATH = "/opt/probe/logs/server.log"
VM_IP = "10.40.2.10"
API_SECRET = 4217  # OpenAPI ツールが VM に届いた証拠(モデルが知りえない値)
MCP_SECRET = 7391  # MCP ツールが VM に届いた証拠
_lock = threading.Lock()

OPENAPI_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "vm-probe-api", "version": "1.0"},
    "servers": [{"url": f"http://{VM_IP}:8080"}],
    "paths": {
        "/whoami": {
            "get": {
                "operationId": "whoami",
                "summary": "Return the caller IP address as seen by the VM and a secret number",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "client_ip": {"type": "string"},
                                        "secret_number": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}


def _log(kind: str, handler: BaseHTTPRequestHandler, extra: dict | None = None) -> None:
    rec = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": kind,
        "client_ip": handler.client_address[0],
        "method": handler.command,
        "path": handler.path,
        "ua": handler.headers.get("User-Agent", ""),
    }
    if extra:
        rec.update(extra)
    with _lock, open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 標準の stderr ログは使わない
        pass

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        _log("api", self)
        if self.path.startswith("/openapi.json"):
            self._send(200, OPENAPI_SPEC)
        elif self.path.startswith("/whoami"):
            self._send(200, {"client_ip": self.client_address[0], "secret_number": API_SECRET})
        elif self.path.startswith("/health"):
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})


class McpHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, obj: dict | None) -> None:
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        if obj is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Mcp-Session-Id", "probe-session")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        _log("mcp", self)
        self._send(405, {"error": "SSE stream not supported"})

    def do_DELETE(self):
        _log("mcp", self)
        self._send(200, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            msg = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            _log("mcp", self, {"rpc": "parse-error"})
            self._send(400, {"error": "bad json"})
            return
        msgs = msg if isinstance(msg, list) else [msg]
        replies = []
        for m in msgs:
            method = m.get("method")
            _log("mcp", self, {"rpc": method, "id": m.get("id")})
            if "id" not in m:  # 通知(notifications/initialized など)
                continue
            if method == "initialize":
                result = {
                    "protocolVersion": (m.get("params") or {}).get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "vm-probe-mcp", "version": "1.0"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "get_vm_secret",
                            "description": "Return a secret number that only this VM knows, plus the caller IP.",
                            "inputSchema": {"type": "object", "properties": {}},
                        }
                    ]
                }
            elif method == "tools/call":
                text = f"VM secret is {MCP_SECRET}. caller_ip={self.client_address[0]}"
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            elif method == "ping":
                result = {}
            else:
                replies.append({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32601, "message": "method not found"}})
                continue
            replies.append({"jsonrpc": "2.0", "id": m.get("id"), "result": result})
        if not replies:
            self._send(202, None)
        else:
            self._send(200, replies if isinstance(msg, list) else replies[0])


def main() -> None:
    api = ThreadingHTTPServer(("0.0.0.0", 8080), ApiHandler)
    mcp = ThreadingHTTPServer(("0.0.0.0", 8081), McpHandler)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    mcp.serve_forever()


if __name__ == "__main__":
    main()
