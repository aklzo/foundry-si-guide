#!/usr/bin/env python3
"""probe 15: エージェントの外向き通信の経路と、エージェントサブネットの NSG / UDR で止まるか(VM 内で実行)。

実行: ../run15.sh が az vm run-command invoke で `python3 /opt/probe/egressprobe.py <command> <phase>` を呼ぶ。
- 12 の vmprobe.py(/opt/probe/vmprobe.py)の設定・MI のトークン取得を使う(トークンは表示・保存しない)
- 標準出力は 1 テスト 1〜3 行の要約(run-command は末尾 4,096 バイトしか返らない)。
  詳細(応答の非メッセージ項目・シェルの出力)は /opt/probe/logs/p15-<command>.log
- テスト: t1 Copilot harness の shell / t2 OpenAPI(公開の IP エコー)/ t3 MCP(Microsoft Learn MCP)/
  t4 Code Interpreter / t5 Web search / t6 VM 自身の送信元 IP / basic 素の prompt agent
"""

from __future__ import annotations

import calendar
import json
import socket
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/probe")
import vmprobe as V  # noqa: E402

# 13 の公開プロジェクトを省いたので publicProjectEndpoint は null。vmprobe.short() の replace(None) を避ける
V.CFG["publicProjectEndpoint"] = V.CFG.get("publicProjectEndpoint") or "#"

P = V.P
MODEL = V.MODEL
VM_IP = V.VM_IP
ECHO = ["https://api.ipify.org?format=json", "https://ifconfig.me/ip"]
ECHO_HOSTS = ["api.ipify.org", "ifconfig.me"]
TCP_HOST = "github.com"
LEARN_MCP = "https://learn.microsoft.com/api/mcp"
PH = "P?"
_LOG = None

SHELL_CMD = (
    "for u in https://api.ipify.org?format=json https://ifconfig.me/ip; do echo \"== $u\"; "
    "curl -sS -m 10 -w ' | http=%{http_code} rip=%{remote_ip} t=%{time_total}' \"$u\" 2>&1; echo; done; "
    f"echo '== vm'; curl -sS -m 10 -w ' | http=%{{http_code}} t=%{{time_total}}' http://{VM_IP}:8080/whoami 2>&1; echo; "
    "echo '== hostname'; hostname -I; "
    "echo '== dns'; getent ahostsv4 api.ipify.org ifconfig.me github.com | awk '{print $1}' | sort -u | tr '\\n' ' '; echo; "
    f"echo '== tcp22'; timeout 8 bash -c 'exec 3<>/dev/tcp/{TCP_HOST}/22 && head -c 20 <&3' 2>&1; echo \" rc=$?\"; "
    "echo '== all.json'; curl -sS -m 10 https://ifconfig.me/all.json 2>&1 | head -c 400; echo; "
    "echo '== proxy env'; env | grep -i _proxy | sed 's/=.*@/=<cred>@/' ; echo"
)


def log(s: str) -> None:
    _LOG.write(s + "\n")
    _LOG.flush()


def say(s: str) -> None:
    line = f"[{PH}]{s}"
    print(line, flush=True)
    log(line)


def req(method, url, body=None, who="ops", headers=None, label="", timeout=240):
    """harness のエージェントのエンドポイントが 403「Traffic is not from an approved private endpoint.」を返すあいだは
    8 秒おきに最大 5 回まで呼び直す(作成直後の PE の承認が一部のゲートウェイに伝わっていない。2026-11-22 18:0x に実測)。"""
    for i in range(5):
        r = _req(method, url, body, who, headers, label + (f" (retry {i})" if i else ""), timeout)
        # harness 以外はすぐにプロジェクトの Responses へ切り替える(agent_call)ので、呼び直すのは harness だけ
        if not (r[0] == 403 and "approved private endpoint" in r[2] and "/endpoint/" in url and "harness" in url):
            return r
        time.sleep(8)
    return r


def _req(method, url, body=None, who="ops", headers=None, label="", timeout=240):
    h = {"Authorization": "Bearer " + V.token(who, V.AI)}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            status, text = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        status, text = -1, f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    try:
        j = json.loads(text)
    except Exception:  # noqa: BLE001
        j = None
    log(f"[{PH}][{label}] {method} {V.short(url)} -> {status} ({dt:.1f}s)\n   body: {text[:6000]}")
    return status, j, text, dt


ROUTE = {"last": "agent-endpoint"}


def agent_call(name, payload, label):
    """エージェントのエンドポイントで呼ぶ。403(PE の承認が伝わっていない)のときは harness 以外をプロジェクトの Responses
    +agent_reference で呼び直し、どちらの経路だったかを ROUTE に残す(会話を使わない呼び出しだけ)。"""
    h = {"Foundry-Features": V.AGENT_FEATURES}
    r = req("POST", f"{P}/agents/{name}/endpoint/protocols/openai/responses?api-version=v1", payload, headers=h, label=label)
    ROUTE["last"] = "agent-endpoint"
    if r[0] == 403 and "harness" not in name and "conversation" not in payload:
        body = dict(payload, agent_reference={"type": "agent_reference", "name": name})
        r = req("POST", f"{P}/openai/v1/responses", body, label=label + " (fallback: project responses+agent_reference)")
        ROUTE["last"] = "project+agent_reference(agent endpoint 403)"
    return r


def items(j):
    """非メッセージの出力項目を ID なしで返す。"""
    if not isinstance(j, dict):
        return []
    res = []
    for it in j.get("output") or []:
        if it.get("type") == "message":
            continue
        res.append({k: v for k, v in it.items() if k not in ("id", "call_id", "response_id", "agent_reference", "environment")})
    return res


def err_of(s, j, text):
    if s == 200:
        return ""
    if isinstance(j, dict) and isinstance(j.get("error"), dict):
        e = j["error"]
        return f"{e.get('code')}: {str(e.get('message'))[:220]}"
    return text[:220]


# ------------------------------------------------------------------ setup

def cmd_setup(_a):
    defs = {
        "a15-harness": ({"kind": "prompt", "model": MODEL, "instructions": "You are a network test agent. Use the shell tool. Run commands exactly as given.",
                         "harness": {"type": "microsoft_copilot_preview"}}, "MicrosoftCopilot=V1Preview"),
        "a15-oapi": ({"kind": "prompt", "model": MODEL,
                      "instructions": "Always call the ipecho getEgressIp operation with format=json and report the exact ip value.",
                      "tools": [{"type": "openapi", "openapi": {"name": "ipecho", "description": "Public IP echo service",
                                                                "spec": OAPI_SPEC, "auth": {"type": "anonymous"}}}]}, None),
        "a15-mcp": ({"kind": "prompt", "model": MODEL,
                     "instructions": "Always call the microsoft_docs_search tool of mslearn first, then answer with one document title.",
                     "tools": [{"type": "mcp", "server_label": "mslearn", "server_url": LEARN_MCP, "require_approval": "never"}]}, None),
        "a15-ci": ({"kind": "prompt", "model": MODEL, "instructions": "Use the python tool. Report exact outputs and errors.",
                    "tools": [{"type": "code_interpreter", "container": {"type": "auto"}}]}, None),
        "a15-web": ({"kind": "prompt", "model": MODEL, "instructions": "Use web search. Answer briefly.", "tools": [{"type": "web_search"}]}, None),
        "a15-basic": ({"kind": "prompt", "model": MODEL, "instructions": "Reply with exactly: PONG"}, None),
    }
    for name, (d, feat) in defs.items():
        h = {"Foundry-Features": feat} if feat else None
        s, j, text, dt = req("POST", f"{P}/agents/{name}/versions?api-version=v1", {"definition": d, "description": f"probe {name}"},
                             headers=h, label=f"create {name}")
        say(f"[setup] {name} -> {s} ({dt:.1f}s) {err_of(s, j, text)}")


def cmd_setup_eg(a):
    """任意(a): RAI ポリシーの egress 制御(プレビュー)を付けた harness エージェントを新しく作る。a[0] = ポリシーの ARM ID。"""
    d = {"kind": "prompt", "model": MODEL, "instructions": "You are a network test agent. Use the shell tool. Run commands exactly as given.",
         "harness": {"type": "microsoft_copilot_preview"}, "rai_config": {"rai_policy_name": a[0]}}
    s, j, text, dt = req("POST", f"{P}/agents/a15-harness-eg/versions?api-version=v1", {"definition": d, "description": "probe a15-harness-eg"},
                         headers={"Foundry-Features": "MicrosoftCopilot=V1Preview"}, label="create a15-harness-eg")
    rc = (j or {}).get("definition", {}).get("rai_config") if isinstance(j, dict) else None
    say(f"[setup_eg] a15-harness-eg -> {s} ({dt:.1f}s) {err_of(s, j, text)} rai_config={json.dumps(rc)[:200] if rc else None}")


OAPI_SPEC2 = {
    "openapi": "3.0.1",
    "info": {"title": "ipecho2", "version": "1.0"},
    "servers": [{"url": "https://ifconfig.me"}],
    "paths": {"/all.json": {"get": {
        "operationId": "getAllHeaders", "summary": "Return the caller IP as seen by the server and the X-Forwarded-For header",
        "responses": {"200": {"description": "ok", "content": {"application/json": {
            "schema": {"type": "object", "properties": {"ip_addr": {"type": "string"}, "forwarded": {"type": "string"}}}}}}}}}},
}


def cmd_setup2(_a):
    """a15-oapi の 2 版: ipify(XFF を優先して返す)に加え、TCP の送信元と X-Forwarded-For を分けて返す ifconfig.me/all.json。"""
    d = {"kind": "prompt", "model": MODEL,
         "instructions": "Always call BOTH tools: ipecho getEgressIp (format=json) and ipecho2 getAllHeaders. Report the raw outputs.",
         "tools": [{"type": "openapi", "openapi": {"name": "ipecho", "description": "Public IP echo service", "spec": OAPI_SPEC, "auth": {"type": "anonymous"}}},
                   {"type": "openapi", "openapi": {"name": "ipecho2", "description": "Public IP and header echo", "spec": OAPI_SPEC2, "auth": {"type": "anonymous"}}}]}
    s, j, text, dt = req("POST", f"{P}/agents/a15-oapi/versions?api-version=v1", {"definition": d, "description": "probe a15-oapi v2"}, label="create a15-oapi v2")
    say(f"[setup2] a15-oapi v2 -> {s} ({dt:.1f}s) {err_of(s, j, text)}")


OAPI_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "ipecho", "version": "1.0"},
    "servers": [{"url": "https://api.ipify.org"}],
    "paths": {"/": {"get": {
        "operationId": "getEgressIp", "summary": "Return the caller's public IP address",
        "parameters": [{"name": "format", "in": "query", "required": True, "schema": {"type": "string", "enum": ["json"]}}],
        "responses": {"200": {"description": "ok", "content": {"application/json": {
            "schema": {"type": "object", "properties": {"ip": {"type": "string"}}}}}}}}}},
}


# ------------------------------------------------------------------ tests

def server_log_since(t0: float):
    try:
        lines = open("/opt/probe/logs/server.log", encoding="utf-8").read().splitlines()[-30:]
    except FileNotFoundError:
        return []
    res = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if calendar.timegm(time.strptime(r["t"], "%Y-%m-%dT%H:%M:%SZ")) >= t0 - 5:
            res.append(f"{r['t'][11:19]} {r['client_ip']} {r['method']} {r['path']}")
    return res


def cmd_t1(a):
    agent = a[0] if a else "a15-harness"
    t0 = time.time()
    h = {"Foundry-Features": V.AGENT_FEATURES}
    s, c, _, _ = req("POST", f"{P}/agents/{agent}/endpoint/protocols/openai/conversations?api-version=v1", {}, headers=h,
                     label=f"t1 conversation ({agent})")
    cid = c.get("id") if isinstance(c, dict) else None
    ask = ("Run exactly this one shell command (do not modify it, do not split it) and paste the raw output:\n" + SHELL_CMD)
    payload = {"input": ask}
    if cid:
        payload["conversation"] = cid
    s, j, text, dt = agent_call(agent, payload, f"t1 harness shell ({agent})")
    outs = []
    for it in items(j):
        if it.get("type") == "shell_call_output":
            for o in it.get("output") or []:
                outs.append((o.get("stdout") or "") + (o.get("stderr") or ""))
        elif it.get("type") == "shell_call":
            log(f"   shell_call: {json.dumps(it.get('action'), ensure_ascii=False)[:1500]}")
    log("   shell outputs: " + json.dumps(outs, ensure_ascii=False)[:6000])
    say(f"[T1 {agent}] HTTP {s} ({dt:.1f}s) {err_of(s, j, text)} shell_outputs={len(outs)}")
    body = " || ".join(o.replace("\n", " ¶ ") for o in outs)
    print(f"[{PH}][T1 out] {body[:1300]}", flush=True)
    sl = server_log_since(t0)
    say(f"[T1 vm-log] {sl[-4:]}")


def summarize_tool(j, keys=("type", "status", "error", "output", "server_label", "name", "queries", "action", "outputs", "code")):
    acc = []
    for it in items(j):
        acc.append({k: it[k] for k in keys if k in it and it[k] not in (None, "", [])})
    return json.dumps(acc, ensure_ascii=False)


def cmd_t2(_a):
    s, j, text, dt = agent_call("a15-oapi", {"input": "Call both getEgressIp and getAllHeaders and report the raw outputs.", "tool_choice": "required"}, "t2 openapi public")
    say(f"[T2 openapi→ipify] HTTP {s} ({dt:.1f}s) route={ROUTE['last']} {err_of(s, j, text)}")
    print(f"[{PH}][T2 items] {summarize_tool(j)[:900]} | text={V.text_of(j)[:200]!r}", flush=True)


def cmd_t3(_a):
    s, j, text, dt = agent_call("a15-mcp", {"input": "Search Microsoft Learn for 'Foundry Agent Service virtual network' and give one title.",
                                            "tool_choice": "required"}, "t3 mcp learn")
    say(f"[T3 mcp→learn] HTTP {s} ({dt:.1f}s) route={ROUTE['last']} {err_of(s, j, text)}")
    print(f"[{PH}][T3 items] {summarize_tool(j, keys=('type', 'status', 'error', 'server_label', 'name'))[:500]} | text={V.text_of(j)[:160]!r}", flush=True)


def cmd_t4(_a):
    code = ("import urllib.request\n"
            "for u in ['https://api.ipify.org?format=json', 'http://%s:8080/whoami']:\n"
            "    try:\n        print(u, urllib.request.urlopen(u, timeout=8).read()[:80])\n"
            "    except Exception as e:\n        print(u, 'ERR', type(e).__name__, e)\n") % VM_IP
    s, j, text, dt = agent_call("a15-ci", {"input": "Run this python code exactly and paste the raw output:\n" + code, "tool_choice": "required"},
                                "t4 code interpreter")
    say(f"[T4 code_interp] HTTP {s} ({dt:.1f}s) route={ROUTE['last']} {err_of(s, j, text)}")
    print(f"[{PH}][T4 out] {summarize_tool(j, keys=('type', 'status', 'outputs'))[:500]} | text={V.text_of(j)[:300]!r}", flush=True)


def cmd_t5(_a):
    s, j, text, dt = agent_call("a15-web", {"input": "Microsoft Ignite 2026 の開催都市は? 一言で。", "tool_choice": "required"}, "t5 web search")
    say(f"[T5 web_search] HTTP {s} ({dt:.1f}s) route={ROUTE['last']} {err_of(s, j, text)}")
    print(f"[{PH}][T5 items] {summarize_tool(j, keys=('type', 'status', 'action'))[:300]} | text={V.text_of(j)[:160]!r}", flush=True)


def cmd_t6(_a):
    for h in ECHO_HOSTS + [TCP_HOST]:
        try:
            ips = sorted({a[4][0] for a in socket.getaddrinfo(h, 443, socket.AF_INET)})
        except Exception as e:  # noqa: BLE001
            ips = [f"ERR {e}"]
        say(f"[T6 dns] {h} -> {ips}")
    for u in ECHO:
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "curl/8"}), timeout=10) as r:
                say(f"[T6 vm-egress] {u} -> {r.status} ({time.time() - t0:.1f}s) {r.read()[:80]!r}")
        except Exception as e:  # noqa: BLE001
            say(f"[T6 vm-egress] {u} -> ERR {type(e).__name__}: {e}")


def cmd_basic(_a):
    s, j, text, dt = agent_call("a15-basic", {"input": "ping"}, "basic prompt agent")
    say(f"[basic] HTTP {s} ({dt:.1f}s) route={ROUTE['last']} {err_of(s, j, text)} text={V.text_of(j)[:40]!r}")


def cmd_route(a):
    """エージェントのエンドポイントとプロジェクトの Responses(+agent_reference)の両方で a15-basic を呼ぶ(403 の切り分け)。"""
    s, j, text, dt = agent_call("a15-basic", {"input": "ping"}, "route agent-endpoint")
    say(f"[route] agent endpoint HTTP {s} ({dt:.1f}s) {err_of(s, j, text)} text={V.text_of(j)[:30]!r}")
    s, j, text, dt = req("POST", f"{P}/openai/v1/responses", {"input": "ping", "agent_reference": {"type": "agent_reference", "name": "a15-basic"}},
                         label="route project responses + agent_reference")
    say(f"[route] project responses+agent_reference HTTP {s} ({dt:.1f}s) {err_of(s, j, text)} text={V.text_of(j)[:30]!r}")
    s, j, text, dt = req("GET", f"{P}/agents/a15-basic?api-version=v1", label="route GET agent")
    ep = (j or {}).get("agent_endpoint") if isinstance(j, dict) else None
    say(f"[route] GET agent HTTP {s} agent_endpoint={json.dumps(ep)[:300] if ep else None}")


def cmd_all(a):
    for f in (cmd_t6, cmd_basic, cmd_t1, cmd_t2, cmd_t3, cmd_t4, cmd_t5):
        try:
            f(a)
        except Exception as e:  # noqa: BLE001
            say(f"[{f.__name__}] EXC {type(e).__name__}: {e}")


COMMANDS = {k[4:]: v for k, v in globals().items() if k.startswith("cmd_")}


def main() -> None:
    global _LOG, PH
    cmd = sys.argv[1]
    PH = sys.argv[2] if len(sys.argv) > 2 else "P?"
    _LOG = open(f"/opt/probe/logs/p15-{cmd}.log", "a", encoding="utf-8")
    V._LOG = _LOG
    log(f"===== {cmd} {PH} @ {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"===== {cmd} {PH} @ {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
    COMMANDS[cmd](sys.argv[3:])


if __name__ == "__main__":
    main()
