#!/usr/bin/env python3
"""VM 内で実行する probe(標準ライブラリだけ)。12(閉域)・13(権限)・14(Optimizer の閉域側)で共用。

実行: az vm run-command invoke 経由で `python3 /opt/probe/vmprobe.py <command> [args]`。
- ID はユーザー割り当て MI。IMDS に client_id を付けてトークンを取る(トークンは表示・保存しない)
- 応答は HTTP ステータスと本文の先頭をそのまま出す。全文は /opt/probe/logs/<command>.log
- run-command の標準出力は末尾 4,096 バイトしか返らないので、標準出力は要約、ファイルは詳細
- 設定は /opt/probe/config.json(エンドポイント・MI の client_id。資格情報は入れない)
"""

from __future__ import annotations

import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CFG = json.load(open("/opt/probe/config.json", encoding="utf-8"))
P = CFG["projectEndpoint"]  # https://aif-x.services.ai.azure.com/api/projects/proj
ACC_OAI = CFG["openaiV1Endpoint"]  # https://aif-x.openai.azure.com/openai/v1
MODEL = CFG["model"]
VM_IP = CFG["vmPrivateIp"]
AI = "https://ai.azure.com"
COG = "https://cognitiveservices.azure.com"
ARM = "https://management.azure.com/"
AGENT_FEATURES = (
    "A2AAgents=V1Preview,WorkflowAgents=V1Preview,DraftAgents=V1Preview,VoiceAgents=V1Preview,"
    "DigitalWorker=V1Preview,GitHubCopilot=V1Preview,Skills=V1Preview,MicrosoftCopilot=V1Preview,"
    "ModelRouterControls=V1Preview"
)
STATE_PATH = "/opt/probe/state.json"
_LOG = None
_TOK: dict = {}


def state() -> dict:
    try:
        return json.load(open(STATE_PATH, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_state(**kv) -> None:
    s = state()
    s.update(kv)
    json.dump(s, open(STATE_PATH, "w", encoding="utf-8"), indent=1)


def out(msg: str, detail: str | None = None) -> None:
    print(msg, flush=True)
    _LOG.write(msg + "\n")
    if detail:
        _LOG.write(detail + "\n")
    _LOG.flush()


def short(url: str) -> str:
    return url.replace(P, "{proj}").replace(ACC_OAI, "{acct-oai}").replace(CFG.get("publicProjectEndpoint", "#"), "{pubproj}")


def token(who: str, resource: str) -> str:
    cid = CFG["ids"][who]
    key = (cid, resource)
    if key in _TOK and _TOK[key][1] > time.time() + 120:
        return _TOK[key][0]
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": resource, "client_id": cid})
    req = urllib.request.Request(f"http://169.254.169.254/metadata/identity/oauth2/token?{q}", headers={"Metadata": "true"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    _TOK[key] = (d["access_token"], int(d["expires_on"]))
    return d["access_token"]


def call(method, url, body=None, who=None, resource=AI, headers=None, raw=None, ctype=None, label="", n=600):
    """HTTP 呼び出し。(status, json|None, text) を返し、要約を出力する。"""
    h = {}
    if who:
        h["Authorization"] = "Bearer " + token(who, resource)
    if headers:
        h.update(headers)
    data = None
    if raw is not None:
        data = raw
        h["Content-Type"] = ctype or "application/octet-stream"
    elif body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            status, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        status, text = -1, f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    try:
        j = json.loads(text)
    except Exception:
        j = None
    out(f"[{label}] {method} {short(url)} -> {status} ({dt:.1f}s) {text[:n]!s}".replace("\n", " "),
        detail=f"   full: {text[:8000]}")
    return status, j, text


def multipart(fields: dict, filename: str, content: bytes, ctype: str) -> tuple[bytes, str]:
    b = "----probe" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
        + content + b"\r\n"
    )
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def text_of(j) -> str:
    """Responses の応答から出力テキストを取り出す。"""
    if not isinstance(j, dict):
        return ""
    acc = []
    for item in j.get("output") or []:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text"):
                    acc.append(c.get("text", ""))
    return " ".join(acc)


def tool_items(j) -> list:
    if not isinstance(j, dict):
        return []
    return [{k: v for k, v in it.items() if k in ("type", "status", "name", "server_label", "error", "output", "queries", "action", "code", "results")}
            for it in (j.get("output") or []) if it.get("type") != "message"]


# ------------------------------------------------------------------ helpers (agents)

def create_agent(name, definition, who="ops", features=None, base=None, label="create_version"):
    base = base or P
    h = {"Foundry-Features": features} if features else None
    return call("POST", f"{base}/agents/{name}/versions?api-version=v1",
                {"definition": definition, "description": f"probe {name}"}, who=who, headers=h, label=label)


def agent_responses(name, payload, who="ops", base=None, label="agent-endpoint", extra_headers=None):
    base = base or P
    h = {"Foundry-Features": AGENT_FEATURES}
    if extra_headers:
        h.update(extra_headers)
    return call("POST", f"{base}/agents/{name}/endpoint/protocols/openai/responses?api-version=v1",
                payload, who=who, headers=h, label=label, n=900)


def agent_conversation(name, who="ops", base=None, label="create conversation (agent endpoint)"):
    base = base or P
    s, j, _ = call("POST", f"{base}/agents/{name}/endpoint/protocols/openai/conversations?api-version=v1", {}, who=who,
                   headers={"Foundry-Features": AGENT_FEATURES}, label=label, n=300)
    return j.get("id") if isinstance(j, dict) else None


def project_responses(payload, who="ops", base=None, label="project-responses", extra_headers=None):
    base = base or P
    return call("POST", f"{base}/openai/v1/responses", payload, who=who, label=label, n=900, headers=extra_headers)


# ------------------------------------------------------------------ commands

def cmd_dns(_args):
    """VM から見た名前解決(プライベート IP に解決されるか)と外向き通信の有無。"""
    host = urllib.parse.urlparse(P).hostname
    acct = host.split(".")[0]
    names = [host, f"{acct}.openai.azure.com", f"{acct}.cognitiveservices.azure.com"] + CFG.get("depHosts", [])
    for n in names:
        try:
            ips = sorted({a[4][0] for a in socket.getaddrinfo(n, 443)})
        except Exception as e:
            ips = [f"ERR {e}"]
        out(f"[dns] {n} -> {ips}")
    call("GET", "https://api.ipify.org?format=json", label="vm-egress(public ip echo)")


def cmd_reach(args):
    """閉域のエンドポイントに VM 内から届くか(id-ops = Foundry User @アカウント)。"""
    who = args[0] if args else "ops"
    call("GET", f"{P}/agents?api-version=v1&limit=5", who=who, label="list agents")
    call("GET", f"{P}/connections?api-version=v1", who=who, label="list connections", n=300)
    project_responses({"model": MODEL, "input": "Say OK.", "store": False}, who=who, label="project /openai/v1/responses")
    call("POST", f"{ACC_OAI}/responses", {"model": MODEL, "input": "Say OK.", "store": False}, who=who, resource=COG,
         label="account /openai/v1/responses")


def cmd_agent(_args):
    """prompt agent を作って応答させる(A3)。"""
    create_agent("a12-basic", {"kind": "prompt", "model": MODEL, "instructions": "Answer in one short Japanese sentence."})
    s, j, _ = agent_responses("a12-basic", {"input": "閉域から呼ばれています。挨拶して。"})
    out(f"[agent] output_text: {text_of(j)!r}")
    s, j, _ = project_responses({"input": "1+1 は?", "agent_reference": {"type": "agent_reference", "name": "a12-basic"}},
                                label="project responses + agent_reference")
    out(f"[agent] output_text(agent_reference): {text_of(j)!r}")
    # 会話(Cosmos に保存されるはず)
    s, conv, _ = call("POST", f"{P}/openai/v1/conversations", {}, who="ops", label="create conversation")
    if isinstance(conv, dict) and conv.get("id"):
        agent_responses("a12-basic", {"input": "私の名前は閉域太郎です。", "conversation": conv["id"]}, label="conv turn1")
        s, j, _ = agent_responses("a12-basic", {"input": "私の名前は?", "conversation": conv["id"]}, label="conv turn2")
        out(f"[agent] conv turn2: {text_of(j)!r}")
        save_state(conversation=conv["id"])


def cmd_filesearch(_args):
    """File Search: ファイル登録 → ベクトルストア作成 → 検索(A4)。"""
    doc = ("社内規程 第 12 条: 閉域検証用の合言葉は『あおいろペンギン 4096』である。\n"
           "第 13 条: 検証が終わったらリソースグループを削除すること。\n").encode()
    body, ct = multipart({"purpose": "assistants"}, "rules.txt", doc, "text/plain")
    s, f, _ = call("POST", f"{P}/openai/v1/files", who="ops", raw=body, ctype=ct, label="upload file")
    if not (isinstance(f, dict) and f.get("id")):
        return
    save_state(file_id=f["id"])
    s, vs, _ = call("POST", f"{P}/openai/v1/vector_stores", {"name": "vs-closed", "file_ids": [f["id"]]}, who="ops",
                    label="create vector store")
    if not (isinstance(vs, dict) and vs.get("id")):
        return
    vsid = vs["id"]
    save_state(vector_store_id=vsid)
    for _ in range(30):
        s, v, _ = call("GET", f"{P}/openai/v1/vector_stores/{vsid}", who="ops", label="vector store status", n=400)
        if isinstance(v, dict) and (v.get("file_counts") or {}).get("in_progress", 1) == 0:
            break
        time.sleep(10)
    call("GET", f"{P}/openai/v1/vector_stores/{vsid}/files", who="ops", label="vector store files", n=600)
    call("POST", f"{P}/openai/v1/vector_stores/{vsid}/search", {"query": "合言葉"}, who="ops", label="vector store search", n=600)
    create_agent("a12-fs", {"kind": "prompt", "model": MODEL, "instructions": "Use file_search and answer briefly in Japanese.",
                            "tools": [{"type": "file_search", "vector_store_ids": [vsid]}]})
    s, j, _ = agent_responses("a12-fs", {"input": "閉域検証用の合言葉は?"}, label="agent file_search")
    out(f"[fs] output_text: {text_of(j)!r}")
    out(f"[fs] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:700]}")


def cmd_codeinterp(_args):
    """Code Interpreter のファイル入出力(A4・候補 5)。"""
    csv = b"name,score\nalice,72\nbob,88\ncarol,95\n"
    body, ct = multipart({"purpose": "assistants"}, "scores.csv", csv, "text/csv")
    s, f, _ = call("POST", f"{P}/openai/v1/files", who="ops", raw=body, ctype=ct, label="upload csv")
    fid = f.get("id") if isinstance(f, dict) else None
    ask = ("Load the attached scores.csv with pandas, compute the mean score, and save a file named result.txt "
           "containing only the mean. Reply with the mean.")
    # (1) auto コンテナー+file_ids(ファイル入力あり)
    create_agent("a12-ci", {"kind": "prompt", "model": MODEL, "instructions": "Use the python tool.",
                            "tools": [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [fid] if fid else []}}]})
    s, j, _ = agent_responses("a12-ci", {"input": ask}, label="agent code_interpreter(auto+file_ids)")
    out(f"[ci] output_text: {text_of(j)!r}")
    out(f"[ci] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:600]}")
    cont = None
    if isinstance(j, dict):
        for it in j.get("output") or []:
            if it.get("type") == "code_interpreter_call":
                cont = it.get("container_id")
            for c in it.get("content") or []:
                for a in c.get("annotations") or []:
                    out(f"[ci] annotation: {json.dumps(a, ensure_ascii=False)[:300]}")
    if cont:
        s, lst, _ = call("GET", f"{P}/openai/v1/containers/{cont}/files", who="ops", label="container files", n=800)
        for cf in (lst or {}).get("data", []) if isinstance(lst, dict) else []:
            if str(cf.get("path", "")).endswith("result.txt"):
                call("GET", f"{P}/openai/v1/containers/{cont}/files/{cf['id']}/content", who="ops", label="download result.txt")
    # (2) 回避策: SDK と同じくコンテナーを先に作って container_id を渡す
    s, c2, _ = call("POST", f"{P}/openai/v1/containers", {"name": "probe-ci", "file_ids": [fid] if fid else []}, who="ops",
                    label="create container (workaround)")
    if isinstance(c2, dict) and c2.get("id"):
        create_agent("a12-ci2", {"kind": "prompt", "model": MODEL, "instructions": "Use the python tool.",
                                 "tools": [{"type": "code_interpreter", "container": c2["id"]}]})
        s, j2, _ = agent_responses("a12-ci2", {"input": ask.replace("attached ", "")}, label="agent code_interpreter(container_id)")
        out(f"[ci2] output_text: {text_of(j2)!r}")
        call("GET", f"{P}/openai/v1/containers/{c2['id']}/files", who="ops", label="container files (workaround)", n=800)
    # (3) サンドボックスの外向き通信
    s, j3, _ = agent_responses("a12-ci", {"input": f"Run python: import urllib.request; print(urllib.request.urlopen('http://{VM_IP}:8080/whoami', timeout=5).read()); then also try https://api.ipify.org . Report exact errors."},
                               label="code_interpreter egress")
    out(f"[ci3] output_text: {text_of(j3)!r}")


def cmd_conv(args):
    """会話の作り先(プロジェクト /openai/v1/conversations とエージェントのエンドポイント)と、呼び出し経路の組み合わせ。"""
    base = CFG["publicProjectEndpoint"] if (args and args[0] == "public") else P
    name = "a14-opt" if base != P else "a12-basic"
    s, conv, _ = call("POST", f"{base}/openai/v1/conversations", {}, who="ops", label="project conversation", n=200)
    pc = conv.get("id") if isinstance(conv, dict) else None
    ac = agent_conversation(name, base=base)
    for cid, kind in ((pc, "project-conv"), (ac, "agent-conv")):
        if not cid:
            continue
        s, j, _ = agent_responses(name, {"input": "私の名前は閉域太郎です。", "conversation": cid}, base=base, label=f"{kind} via agent endpoint")
        s, j, _ = project_responses({"input": "私の名前は?", "conversation": cid, "agent_reference": {"type": "agent_reference", "name": name}},
                                    base=base, label=f"{kind} via project responses + agent_reference")
        out(f"[conv] {kind}: {text_of(j)!r}")


def cmd_websearch(_args):
    create_agent("a12-web", {"kind": "prompt", "model": MODEL, "instructions": "Use web search. Answer briefly.",
                             "tools": [{"type": "web_search"}]})
    s, j, _ = agent_responses("a12-web", {"input": "Microsoft Ignite 2026 の開催都市はどこ?", "tool_choice": "required"},
                              label="agent web_search")
    out(f"[web] output_text: {text_of(j)!r}")
    out(f"[web] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:600]}")


def cmd_openapi(_args):
    spec = json.load(urllib.request.urlopen(f"http://{VM_IP}:8080/openapi.json", timeout=10))
    create_agent("a12-openapi", {"kind": "prompt", "model": MODEL,
                                 "instructions": "Always call the vmapi whoami operation and report client_ip and secret_number.",
                                 "tools": [{"type": "openapi", "openapi": {"name": "vmapi", "description": "API on the VNet VM",
                                                                           "spec": spec, "auth": {"type": "anonymous"}}}]})
    s, j, _ = agent_responses("a12-openapi", {"input": "whoami を呼んで結果を教えて。", "tool_choice": "required"}, label="agent openapi")
    out(f"[openapi] output_text: {text_of(j)!r}")
    out(f"[openapi] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:800]}")


def cmd_mcp(_args):
    create_agent("a12-mcp", {"kind": "prompt", "model": MODEL,
                             "instructions": "Always call the get_vm_secret tool and report its exact output.",
                             "tools": [{"type": "mcp", "server_label": "vmmcp", "server_url": f"http://{VM_IP}:8081/mcp",
                                        "require_approval": "never"}]})
    s, j, _ = agent_responses("a12-mcp", {"input": "get_vm_secret を呼んで結果を教えて。", "tool_choice": "required"}, label="agent mcp")
    out(f"[mcp] output_text: {text_of(j)!r}")
    out(f"[mcp] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:800]}")


def cmd_harness(_args):
    """Copilot harness の prompt agent(A5・候補 7)。"""
    s, j, _ = create_agent("a12-harness", {"kind": "prompt", "model": MODEL, "instructions": "You are a network test agent. Use the shell tool.",
                                           "harness": {"type": "microsoft_copilot_preview"}},
                           features="MicrosoftCopilot=V1Preview", label="create harness agent")
    if s not in (200, 201):
        return
    cid = agent_conversation("a12-harness")
    ask = (f"Run these shell commands and paste their raw outputs: "
           f"(1) curl -s -m 10 http://{VM_IP}:8080/whoami ; "
           f"(2) curl -s -m 10 https://api.ipify.org?format=json ; "
           f"(3) hostname -I ; (4) getent hosts {urllib.parse.urlparse(P).hostname}")
    s, j, _ = agent_responses("a12-harness", {"input": ask, "conversation": cid}, label="harness shell egress")
    out(f"[harness] output_text: {text_of(j)[:1500]!r}")
    out(f"[harness] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:800]}")


def cmd_serverlog(args):
    n = int(args[0]) if args else 30
    try:
        lines = open("/opt/probe/logs/server.log", encoding="utf-8").read().splitlines()[-n:]
    except FileNotFoundError:
        lines = ["(no server.log)"]
    for ln in lines:
        out(ln)


# ------------------------------------------------------------------ 13: 権限

WHO_ALL = ["ops", "fu", "rt", "ac1", "rd"]


def cmd_setup13(_args):
    """13 の準備: ロールを付ける対象のエージェントを ops で作る(エージェントスコープの割り当てはエージェントの作成後)。"""
    create_agent("a13-target", {"kind": "prompt", "model": MODEL, "instructions": "Reply with exactly: PONG"})
    create_agent("a13-share", {"kind": "prompt", "model": MODEL, "instructions": "Answer briefly. Quote file contents when asked."})
    save_state(a13_created=True)


def cmd_rbac(args):
    """B1: ロールごとに推論の経路が通るか。a13-target を ops で作ってから各 ID で呼ぶ。"""
    whos = args or WHO_ALL
    if not state().get("a13_created"):
        create_agent("a13-target", {"kind": "prompt", "model": MODEL, "instructions": "Reply with exactly: PONG"})
        save_state(a13_created=True)
    for who in whos:
        out(f"--- who={who}")
        project_responses({"model": MODEL, "input": "Reply with exactly: PONG", "store": False}, who=who,
                          label=f"{who} (a) project responses (no agent)")
        agent_responses("a13-target", {"input": "ping"}, who=who, label=f"{who} (b) agent endpoint")
        project_responses({"input": "ping", "agent_reference": {"type": "agent_reference", "name": "a13-target"}}, who=who,
                          label=f"{who} (c) project responses + agent_reference")
        call("POST", f"{ACC_OAI}/responses", {"model": MODEL, "input": "Reply with exactly: PONG", "store": False}, who=who,
             resource=COG, label=f"{who} (d) account /openai/v1/responses", n=300)
        call("POST", f"{ACC_OAI}/responses", {"model": MODEL, "input": "Reply with exactly: PONG", "store": False}, who=who,
             resource=AI, label=f"{who} (d2) account /openai/v1 with ai.azure.com token", n=300)
        call("GET", f"{P}/agents?api-version=v1&limit=1", who=who, label=f"{who} (e) list agents", n=200)
        create_agent(f"a13-by-{who}", {"kind": "prompt", "model": MODEL, "instructions": "x"}, who=who, label=f"{who} (f) create_version")


def arm(method, path, body=None, who="ops", label=""):
    url = path if path.startswith("https://") else "https://management.azure.com" + path
    return call(method, url, body, who=who, resource=ARM, label=label, n=500)


def cmd_keys(args):
    """B2(閉域側): id-ops が ARM の listKeys でキーを取り、api-key でどこまで届くか。キーは表示しない。"""
    acct_id = CFG["foundryId"]
    s, j, text = call("POST", f"https://management.azure.com{acct_id}/listKeys?api-version=2026-11-01", who="ops", resource=ARM,
                      label="ops listKeys", n=0)
    key = j.get("key1") if isinstance(j, dict) else None
    out(f"[keys] listKeys status={s} key_obtained={bool(key)}")
    for who in ("fu", "rt", "rd"):
        s2, _, _ = call("POST", f"https://management.azure.com{acct_id}/listKeys?api-version=2026-11-01", who=who, resource=ARM,
                        label=f"{who} listKeys", n=300)
    if not key:
        return
    kh = {"api-key": key}
    call("POST", f"{ACC_OAI}/responses", {"model": MODEL, "input": "Reply PONG", "store": False}, headers=kh, label="key (a) account /openai/v1/responses", n=300)
    call("POST", f"{P}/openai/v1/responses", {"model": MODEL, "input": "Reply PONG", "store": False}, headers=kh, label="key (b) project /openai/v1/responses", n=300)
    call("POST", f"{P}/openai/v1/responses", {"input": "ping", "agent_reference": {"type": "agent_reference", "name": "a13-target"}},
         headers=kh, label="key (c) project responses + agent_reference", n=300)
    call("POST", f"{P}/agents/a13-target/endpoint/protocols/openai/responses?api-version=v1", {"input": "ping"},
         headers={**kh, "Foundry-Features": AGENT_FEATURES}, label="key (d) agent endpoint", n=300)
    call("GET", f"{P}/agents?api-version=v1&limit=1", headers=kh, label="key (e) list agents", n=300)
    call("GET", f"{P}/openai/v1/files", headers=kh, label="key (f) list files", n=300)


def cmd_share(_args):
    """B3: 同じエージェントの Agent Consumer 2 人(ac1 / rd)の間で見えるもの。"""
    st = state()
    # 準備(ops): ファイル F
    body, ct = multipart({"purpose": "assistants"}, "secret-ops.txt", b"ops only: the code word is KIWI-5521.", "text/plain")
    s, f, _ = call("POST", f"{P}/openai/v1/files", who="ops", raw=body, ctype=ct, label="ops upload F")
    fid = f.get("id") if isinstance(f, dict) else None
    if not st.get("a13_created"):
        create_agent("a13-target", {"kind": "prompt", "model": MODEL, "instructions": "Reply with exactly: PONG"})
    create_agent("a13-share", {"kind": "prompt", "model": MODEL, "instructions": "Answer briefly. Quote file contents when asked."})
    out("--- ac1")
    body, ct = multipart({"purpose": "assistants"}, "ac1.txt", b"ac1 file", "text/plain")
    call("POST", f"{P}/openai/v1/files", who="ac1", raw=body, ctype=ct, label="ac1 (a) upload file")
    call("GET", f"{P}/openai/v1/files", who="ac1", label="ac1 (b) list files", n=300)
    if fid:
        s, j, _ = agent_responses("a13-share", {"input": [{"role": "user", "content": [
            {"type": "input_text", "text": "What is the code word in the file?"}, {"type": "input_file", "file_id": fid}]}]},
            who="ac1", label="ac1 (c) input_file=F (ops のファイル)")
        out(f"[share] ac1 (c) text: {text_of(j)!r}")
    agent_responses("a12-basic", {"input": "ping"}, who="ac1", label="ac1 (d) ロールのない a12-basic")
    s, r1, _ = agent_responses("a13-share", {"input": "Remember: my lucky number is 31337.", "store": True}, who="ac1", label="ac1 R1 (store)")
    r1id = r1.get("id") if isinstance(r1, dict) else None
    s, c1, _ = call("POST", f"{P}/openai/v1/conversations", {}, who="ac1", label="ac1 create conversation C1")
    c1id = c1.get("id") if isinstance(c1, dict) else None
    if c1id:
        agent_responses("a13-share", {"input": "My pet's name is Mochi.", "conversation": c1id}, who="ac1", label="ac1 C1 turn")
    out("--- rd(2 人目の Agent Consumer)")
    if r1id:
        s, j, _ = agent_responses("a13-share", {"input": "What is my lucky number?", "previous_response_id": r1id}, who="rd",
                                  label="rd (e) previous_response_id=R1")
        out(f"[share] rd (e) text: {text_of(j)!r}")
        call("GET", f"{P}/openai/v1/responses/{r1id}", who="rd", label="rd (f) GET R1 (project)", n=300)
        call("GET", f"{P}/agents/a13-share/endpoint/protocols/openai/responses/{r1id}?api-version=v1", who="rd",
             headers={"Foundry-Features": AGENT_FEATURES}, label="rd (f2) GET R1 (agent endpoint)", n=300)
    if c1id:
        call("GET", f"{P}/openai/v1/conversations/{c1id}/items", who="rd", label="rd (g) list C1 items", n=400)
        s, j, _ = agent_responses("a13-share", {"input": "What is my pet's name?", "conversation": c1id}, who="rd",
                                  label="rd (g2) C1 に続けて質問")
        out(f"[share] rd (g2) text: {text_of(j)!r}")
    if fid:
        s, j, _ = agent_responses("a13-share", {"input": [{"role": "user", "content": [
            {"type": "input_text", "text": "What is the code word in the file?"}, {"type": "input_file", "file_id": fid}]}]},
            who="rd", label="rd (h) input_file=F")
        out(f"[share] rd (h) text: {text_of(j)!r}")


def cmd_share2(_args):
    """B3 の補足: 対照(ops の input_file、ac1 自身の GET)と、エージェントのエンドポイントで作る会話 C1。"""
    AE = f"{P}/agents/a13-share/endpoint/protocols/openai"
    fh = {"Foundry-Features": AGENT_FEATURES}
    body, ct = multipart({"purpose": "assistants"}, "secret-ops2.txt", b"ops only: the code word is KIWI-5521.", "text/plain")
    s, f, _ = call("POST", f"{P}/openai/v1/files", who="ops", raw=body, ctype=ct, label="ops upload F2")
    fid = f.get("id") if isinstance(f, dict) else None
    msg = [{"role": "user", "content": [{"type": "input_text", "text": "What is the code word in the file?"},
                                         {"type": "input_file", "file_id": fid}]}]
    for who in ("ops", "fu", "ac1"):
        s, j, _ = agent_responses("a13-share", {"input": msg}, who=who, label=f"{who} input_file=F2 (agent endpoint)")
        out(f"[share2] {who} input_file text: {text_of(j)!r}")
    s, j, _ = project_responses({"input": msg, "agent_reference": {"type": "agent_reference", "name": "a13-share"}}, who="ops",
                                label="ops input_file=F2 (project responses + agent_reference)")
    out(f"[share2] ops project input_file text: {text_of(j)!r}")
    s, r1, _ = agent_responses("a13-share", {"input": "Remember: my lucky number is 31337.", "store": True}, who="ac1", label="ac1 R1")
    r1id = r1.get("id") if isinstance(r1, dict) else None
    if r1id:
        call("GET", f"{AE}/responses/{r1id}?api-version=v1", who="ac1", headers=fh, label="ac1 GET R1 (agent endpoint・本人)", n=200)
        call("GET", f"{AE}/responses/{r1id}?api-version=v1", who="rd", headers=fh, label="rd GET R1 (agent endpoint)", n=200)
        call("GET", f"{P}/openai/v1/responses/{r1id}", who="ops", label="ops GET R1 (project・Foundry User)", n=200)
    c1 = agent_conversation("a13-share", who="ac1", label="ac1 create C1 (agent endpoint)")
    if c1:
        agent_responses("a13-share", {"input": "My pet's name is Mochi.", "conversation": c1}, who="ac1", label="ac1 C1 turn")
        call("GET", f"{AE}/conversations/{c1}/items?api-version=v1", who="rd", headers=fh, label="rd list C1 items (agent endpoint)", n=400)
        s, j, _ = agent_responses("a13-share", {"input": "What is my pet's name?", "conversation": c1}, who="rd", label="rd C1 に続けて質問")
        out(f"[share2] rd C1 text: {text_of(j)!r}")
        call("GET", f"{AE}/conversations/{c1}/items?api-version=v1", who="ac1", headers=fh, label="ac1 list C1 items (本人・rd の追記が見えるか)", n=600)


def cmd_share3(_args):
    """B3 の再現確認: 他人の previous_response_id で続きが読めるか(ac1 が作り、rd / fu / ops が続ける)。"""
    s, r1, _ = agent_responses("a13-share", {"input": "Remember: my secret color is ultramarine-77.", "store": True}, who="ac1", label="ac1 R (store)")
    rid = r1.get("id") if isinstance(r1, dict) else None
    for who in ("rd", "fu", "ops"):
        s, j, _ = agent_responses("a13-share", {"input": "What is my secret color?", "previous_response_id": rid}, who=who,
                                  label=f"{who} previous_response_id=ac1 の R")
        out(f"[share3] {who}: {text_of(j)!r}")
    s, j, _ = project_responses({"input": "What is my secret color?", "previous_response_id": rid,
                                 "agent_reference": {"type": "agent_reference", "name": "a13-share"}}, who="ops",
                                label="ops previous_response_id=R (project responses)")
    out(f"[share3] ops(project): {text_of(j)!r}")


def cmd_sharepub(args):
    """B3 の補足(公開プロジェクト): 閉域では input_file 自体が 400 なので、公開側で Agent Consumer が他人(実行者)の
    ファイル ID を input_file に入れて中身を読めるかを見る。args[0] = 実行者がアップロードした file ID。"""
    pub = CFG["publicProjectEndpoint"]
    fid = args[0]
    agent = args[1] if len(args) > 1 else "a13-mem"
    if agent != "a13-mem" and len(args) > 2 and args[2] == "create":
        create_agent(agent, {"kind": "prompt", "model": MODEL, "instructions": "Answer briefly. Quote file contents when asked."},
                     who="ops", base=pub, label=f"ops create {agent} (public)")
        return
    msg = [{"role": "user", "content": [{"type": "input_text", "text": "What is the code word in the file?"},
                                         {"type": "input_file", "file_id": fid}]}]
    for who in ("ac1", "rd"):
        s, j, _ = agent_responses(agent, {"input": msg}, who=who, base=pub, label=f"{who} input_file=<実行者のファイル> (public {agent})")
        out(f"[sharepub] {who}: {text_of(j)!r}")
        call("GET", f"{pub}/openai/v1/files/{fid}", who=who, label=f"{who} GET file metadata", n=200)


def cmd_conn(_args):
    """B4: 接続の作成(ARM)。id-fu(FU@プロジェクト)と id-ops(FU@アカウント)。"""
    pid = CFG["projectId"]
    body = {"properties": {"category": "RemoteTool", "target": f"http://{VM_IP}:8081/mcp", "authType": "None",
                           "metadata": {"type": "custom_MCP"}}}
    for who in ("fu", "ops", "rd"):
        arm("PUT", f"{pid}/connections/c13-by-{who}?api-version=2026-11-01", body, who=who, label=f"{who} PUT connection")
    arm("POST", f"{pid}/connections/conn-search/listsecrets?api-version=2026-11-01", {}, who="fu", label="fu listsecrets(conn-search)")
    # データプレーンの接続一覧
    call("GET", f"{P}/connections?api-version=v1", who="fu", label="fu data-plane list connections", n=300)


def cmd_authz(_args):
    """B4: エージェントのエンドポイント認可に仕様にない名前(AzureRbac / AgentBlueprint)を入れる。"""
    s, j, _ = call("GET", f"{P}/agents/a13-target?api-version=v1", who="ops", label="GET agent (before)", n=900)
    for schemes, lab in (([{"type": "AzureRbac"}], "AzureRbac"), ([{"type": "Entra"}], "Entra"),
                         ([{"type": "AzureRbac"}, {"type": "AgentBlueprint"}], "AzureRbac+AgentBlueprint"),
                         ([{"type": "NoSuchScheme"}], "NoSuchScheme(対照)")):
        call("PATCH", f"{P}/agents/a13-target?api-version=v1",
             {"agent_endpoint": {"authorization_schemes": schemes}}, who="ops",
             headers={"Foundry-Features": AGENT_FEATURES}, label=f"PATCH authorization_schemes={lab}", n=900)
        call("GET", f"{P}/agents/a13-target?api-version=v1", who="ops", label=f"GET agent after {lab}", n=900)


def cmd_authz2(_args):
    """authz の続き: 存在しないスキーム(NoSuchScheme)が入ったエンドポイントを呼べるか → 既定(Entra)に戻す。"""
    for who in ("ac1", "ops"):
        agent_responses("a13-target", {"input": "ping"}, who=who, label=f"{who} call with NoSuchScheme", extra_headers=None)
    call("PATCH", f"{P}/agents/a13-target?api-version=v1",
         {"agent_endpoint": {"authorization_schemes": [{"type": "Entra", "isolation_key_source": {"kind": "Entra"}}]}}, who="ops",
         headers={"Foundry-Features": AGENT_FEATURES}, label="PATCH back to Entra(既定)", n=300)
    for who in ("ac1",):
        agent_responses("a13-target", {"input": "ping"}, who=who, label=f"{who} call after restore")


def cmd_roleassign(args):
    """B5: id-fu(+Foundry Project Manager @アカウント)と id-rt(+Foundry Account Owner @アカウント)が誰に何を付けられるか。"""
    acct = CFG["foundryId"]
    tgt = CFG["principals"]["ac1"]
    roles = {"FoundryUser": "53ca6127-db72-4b80-b1b0-d745d6d5456d", "AgentConsumer": "eed3b665-ab3a-47b6-8f48-c9382fb1dad6",
             "Reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7", "LogAnalyticsReader": "73c42c96-874c-492b-b04d-ab87d138a893",
             "MonitoringReader": "43d0d8ad-25c7-4714-9337-8ba259a9fe05"}
    sub = acct.split("/")[2]
    scopes = {"account": acct, "agent": f"{CFG['projectId']}/agents/a13-target"}
    created = []
    for who in (args or ["fu", "rt"]):
        for rname, rid in roles.items():
            for sname, scope in scopes.items():
                if sname == "agent" and rname not in ("AgentConsumer", "FoundryUser", "Reader"):
                    continue
                ra = str(uuid.uuid4())
                body = {"properties": {"roleDefinitionId": f"/subscriptions/{sub}/providers/Microsoft.Authorization/roleDefinitions/{rid}",
                                       "principalId": tgt, "principalType": "ServicePrincipal"}}
                s, j, _ = arm("PUT", f"{scope}/providers/Microsoft.Authorization/roleAssignments/{ra}?api-version=2022-04-01", body,
                              who=who, label=f"{who} assign {rname} @{sname}")
                if s in (200, 201):
                    created.append(f"{scope}/providers/Microsoft.Authorization/roleAssignments/{ra}")
    save_state(created_role_assignments=created)
    # metrics read
    for who in WHO_ALL:
        arm("GET", f"{acct}/providers/Microsoft.Insights/metrics?api-version=2023-10-01&metricnames=ProcessedPromptTokens&timespan=PT6H",
            who=who, label=f"{who} metrics read")


def cmd_roleclean(_args):
    for rid in state().get("created_role_assignments", []):
        arm("DELETE", f"{rid}?api-version=2022-04-01", who="ops", label="delete created role assignment (ops)")


def cmd_memory(args):
    """B6(公開側のプロジェクト): x-memory-user-id で他人の記憶が読めるか。
    ac1 と rd は a13-mem に Agent Consumer(エージェントスコープ)を持つ。ops は Foundry User @アカウント。"""
    pub = CFG["publicProjectEndpoint"]
    mh = {"Foundry-Features": "MemoryStores=V1Preview"}
    phase = args[0] if args else "setup"
    if phase == "setup":
        call("POST", f"{pub}/memory_stores?api-version=v1", {
            "name": "ms13", "description": "probe 13 B6",
            "definition": {"kind": "default", "chat_model": CFG.get("publicModel", MODEL), "embedding_model": "text-embedding-3-small",
                           "options": {"user_profile_enabled": True, "chat_summary_enabled": True}}},
             who="ops", headers=mh, label="ops create memory store", n=500)
        create_agent("a13-mem", {"kind": "prompt", "model": MODEL,
                                 "instructions": "You remember facts about the user. When asked, answer from memory only; say UNKNOWN if not remembered.",
                                 "tools": [{"type": "memory_search_preview", "memory_store_name": "ms13", "scope": "{{$userId}}", "update_delay": 1}]},
                     who="ops", base=pub, features="MemoryStores=V1Preview", label="ops create a13-mem")
        return
    if phase == "write":
        agent_responses("a13-mem", {"input": "覚えておいて: 私の好きな果物はドラゴンフルーツです。"}, who="ac1", base=pub,
                        extra_headers={"x-memory-user-id": "user-alice"}, label="ac1 write (x-memory-user-id: user-alice)")
        agent_responses("a13-mem", {"input": "覚えておいて: 私の飼い猫の名前はモチです。"}, who="ac1", base=pub,
                        label="ac1 write (ヘッダーなし = TID/OID)")
        return
    if phase == "read":
        for who, hdr, lab in (("rd", {"x-memory-user-id": "user-alice"}, "rd + x-memory-user-id: user-alice(他人の値)"),
                              ("rd", None, "rd ヘッダーなし(対照)"),
                              ("ac1", {"x-memory-user-id": "user-alice"}, "ac1 + 自分の値(対照)"),
                              ("ac1", None, "ac1 ヘッダーなし(TID/OID)")):
            s, j, _ = agent_responses("a13-mem", {"input": "私の好きな果物と飼い猫の名前は? 記憶から答えて。"}, who=who, base=pub,
                                      extra_headers=hdr, label=f"read {lab}")
            out(f"[memory] {lab}: {text_of(j)!r}")
            out(f"[memory] tool items: {json.dumps(tool_items(j), ensure_ascii=False)[:500]}")
        for who in ("ops", "rd", "ac1"):
            call("POST", f"{pub}/memory_stores/ms13:search_memories?api-version=v1",
                 {"scope": "user-alice", "items": [{"type": "message", "role": "user", "content": "好きな果物"}]},
                 who=who, headers=mh, label=f"{who} low-level search_memories(scope=user-alice)", n=600)
            call("POST", f"{pub}/memory_stores/ms13/items:list?api-version=v1", {"scope": "user-alice"},
                 who=who, headers=mh, label=f"{who} low-level items:list(scope=user-alice)", n=600)


def cmd_memory2(args):
    """B6 の続き: ac1 の記憶がどの scope に入ったかを ops の low-level API で探し、その値を rd がヘッダーに入れて読む。
    あわせて、プロジェクトの Responses(+agent_reference)経路でヘッダーが効くかを ops で確かめる。"""
    pub = CFG["publicProjectEndpoint"]
    mh = {"Foundry-Features": "MemoryStores=V1Preview"}
    tid = CFG["tenantId"]
    oid = CFG["principals"]["ac1"]
    phase = args[0] if args else "find"
    if phase == "find":
        found = None
        for sc in (oid, f"{tid}_{oid}", f"{tid}:{oid}", f"{tid}/{oid}", f"{oid}@{tid}", f"{tid}.{oid}", f"{tid}-{oid}"):
            s, j, _ = call("POST", f"{pub}/memory_stores/ms13/items:list?api-version=v1", {"scope": sc}, who="ops", headers=mh,
                           label=f"ops items:list scope=<候補 {sc.replace(tid, '<tid>')}>", n=300)
            if isinstance(j, dict) and j.get("data"):
                found = sc
                break
        save_state(ac1_scope=found)
        out(f"[memory2] ac1 scope found: {str(found).replace(tid, '<tid>') if found else None}")
        # プロジェクトの Responses 経路でのヘッダー(ops = Foundry User)
        project_responses({"input": "覚えておいて: 私の好きな色はエメラルドグリーンです。",
                           "agent_reference": {"type": "agent_reference", "name": "a13-mem"}}, who="ops", base=pub,
                          extra_headers={"x-memory-user-id": "user-bob"}, label="ops write via project responses (x-memory-user-id: user-bob)")
        return
    if phase == "read":
        sc = state().get("ac1_scope")
        call("POST", f"{pub}/memory_stores/ms13/items:list?api-version=v1", {"scope": "user-bob"}, who="ops", headers=mh,
             label="ops items:list scope=user-bob(ヘッダーの値で入ったか)", n=500)
        if sc:
            s, j, _ = agent_responses("a13-mem", {"input": "私の好きな果物と飼い猫の名前は? 記憶から答えて。"}, who="rd", base=pub,
                                      extra_headers={"x-memory-user-id": sc}, label="rd + x-memory-user-id=<ac1 の scope>")
            out(f"[memory2] rd with ac1 scope: {text_of(j)!r}")
            s, j, _ = project_responses({"input": "私の好きな果物と飼い猫の名前は? 記憶から答えて。",
                                         "agent_reference": {"type": "agent_reference", "name": "a13-mem"}}, who="ops", base=pub,
                                        extra_headers={"x-memory-user-id": sc}, label="ops(project) + x-memory-user-id=<ac1 の scope>")
            out(f"[memory2] ops(project) with ac1 scope: {text_of(j)!r}")


def cmd_optimizer(args):
    """C(閉域側): 公開側と同じ本文で estimate → 最小ジョブ(候補 1)を 1 回。本文は 14 の probe.py が作ったもの。"""
    body = CFG.get("optimizerEstimateBody")
    if not body:
        out("[opt] no body")
        return
    body = json.loads(json.dumps(body).replace("__AGENT__", "a12-basic").replace("__MODEL__", MODEL))
    call("POST", f"{P}/agent_optimization_jobs:estimate?api-version=v1", body, who="ops", label="closed estimate", n=1500)
    if args and args[0] == "start":
        job = dict(body, display_name="probe14-closed")
        s, j, _ = call("POST", f"{P}/agent_optimization_jobs?api-version=v1", job, who="ops", label="closed create job", n=800)
        jid = j.get("id") if isinstance(j, dict) else None
        for _ in range(24):
            if not jid:
                break
            time.sleep(30)
            s, g, _ = call("GET", f"{P}/agent_optimization_jobs/{jid}?api-version=v1", who="ops", label="closed job status", n=200)
            st = g.get("status") if isinstance(g, dict) else None
            if st in ("succeeded", "failed", "cancelled", "skipped"):
                call("GET", f"{P}/agent_optimization_jobs/{jid}?api-version=v1", who="ops", label="closed job final", n=3000)
                break
        else:
            if jid:
                call("POST", f"{P}/agent_optimization_jobs/{jid}:cancel?api-version=v1", {}, who="ops", label="closed job cancel", n=500)
    call("GET", f"{P}/agent_optimization_jobs?api-version=v1", who="ops", label="closed list jobs", n=300)


COMMANDS = {k[4:]: v for k, v in globals().items() if k.startswith("cmd_")}


def main() -> None:
    global _LOG
    cmd = sys.argv[1]
    _LOG = open(f"/opt/probe/logs/{cmd}.log", "a", encoding="utf-8")
    out(f"===== {cmd} {' '.join(sys.argv[2:])} @ {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
