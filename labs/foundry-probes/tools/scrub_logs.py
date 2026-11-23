#!/usr/bin/env python3
"""検証ログから、削除済みのリソースでも残したくない識別子を伏せ字にする。

    python3 -I tools/scrub_logs.py --suffix <リソース名の乱数部分> probes/12-closed-network probes/13-...
    python3 -I tools/scrub_logs.py --check probes/12-closed-network   # 伏せ字漏れの検査だけ(書き換えない)

伏せ字にするもの(同じ値は全ファイルで同じ番号にそろえ、ログ同士の対応は追えるように残す):
- メールアドレス(systemData.createdBy など)→ <email>
- GUID(マネージド ID の principal/client ID、エージェントの GUID、ロール割り当て ID など)→ <guid-N>
  ただし組み込みロールの定義 ID(スクリプト中の定数と roleDefinitions/<id>)と 00000000-… は残す
- リソース名の乱数部分(--suffix)→ <sfx>
- 公開 IPv4(10/8・172.16/12・192.168/16・169.254/16・127/8・168.63.129.16 以外)→ <public-ip-N>
- Foundry のオブジェクト ID(conv_… resp_… file-… など)と 40 文字以上の英数字列(キー・トークン・セッション ID)
- 32 桁の 16 進(ダッシュなしのロール割り当て ID・リクエスト ID・ジョブ ID・memory_id など)→ <hex-N>、isolationKey の値 → <key-N>
- 途中で切れた ID: /subscriptions/・/tenants/ の後ろ → <sub>・<tenant>、GUID の前半(8-4-x 以上)→ <guid-N>
- 絶対パス(/home/<user>/… → <home>/…、/tmp/claude-… → <scratch>)
対象は *.log・*.md・*.json・*.jsonl・*.txt・*.csv(.json は .gitignore 済みのものも含む)。スクリプト(.sh/.py/.bicep)は書き換えない。
同じフォルダに後から足したログを伏せるときは、すでにある <guid-N> などの最大の番号の続きから振る(番号がぶつからない)。
文書の例に使うドメイン(contoso.com・example.com など)のアドレスは残す。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
RE_GUID = re.compile(GUID)
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
RE_IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
RE_OBJ = re.compile(r"\b((?:conv|resp|caresp|lsh|lsho|msg|call|cntr|cfile|vs|ws|fs|ci|mcpl|mcpr|rs|ig|run|step|thread|asst|batch|ftjob|eval|evalrun)_)([A-Za-z0-9]{16,})\b")
RE_DASHOBJ = re.compile(r"\b((?:file|assistant|cfile|vsfile)-)([A-Za-z0-9]{16,})\b")
RE_LONG = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{40,}(?![A-Za-z0-9])")
RE_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
RE_HOME = re.compile(r"/home/[A-Za-z0-9._-]+")
RE_SCRATCH = re.compile(r"/tmp/claude-[0-9]+/[^\s\"'`)]*")
RE_HEX32 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
RE_ISOKEY = re.compile(r"(isolationKey\s+)([A-Za-z0-9_-]{16,})")
# 途中で切れた ID(エラー文を切り詰めて残したログなど)。完全な GUID を伏せた後に当てる。
RE_SCOPEFRAG = re.compile(r"(/(?:subscriptions|tenants)/)([0-9a-fA-F][0-9a-fA-F-]{0,35})(?![0-9a-fA-F-])")
RE_GUIDFRAG = re.compile(r"(?<![0-9a-fA-F-])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{0,4}(?:-[0-9a-fA-F]{0,12})?(?![0-9a-fA-F-])")
RE_PLACEHOLDER = re.compile(r"<(guid|public-ip|id|token|hex|key)-(\d+)>")
DOC_DOMAINS = ("contoso.com", "fabrikam.com", "example.com", "example.org", "example.net", "adventure-works.com")
TARGET_EXT = {".log", ".md", ".json", ".jsonl", ".txt", ".csv"}
SCRIPT_EXT = {".sh", ".py", ".bicep"}


def doc_address(addr: str) -> bool:
    return addr.lower().split("@")[-1] in DOC_DOMAINS


def private_ip(parts: tuple[int, ...]) -> bool:
    a, b = parts[0], parts[1]
    return (a in (0, 10, 127, 255) or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)
            or (a == 169 and b == 254) or parts == (168, 63, 129, 16) or a >= 224)


class Scrubber:
    def __init__(self, keep_guids: set[str], suffixes: list[str], start: dict[str, int] | None = None):
        self.keep = {g.lower() for g in keep_guids}
        self.suffixes = [s for s in suffixes if s]
        self.maps: dict[str, dict[str, str]] = {}
        self.start = start or {}

    def _num(self, kind: str, value: str, fmt: str) -> str:
        m = self.maps.setdefault(kind, {})
        if value not in m:
            m[value] = fmt.format(self.start.get(fmt.split("-{")[0].lstrip("<"), 0) + len(m) + 1)
        return m[value]

    def guid(self, mt: re.Match) -> str:
        g = mt.group(0).lower()
        if g in self.keep or g.startswith("00000000-0000-0000-0000-"):
            return mt.group(0)
        return self._num("guid", g, "<guid-{}>")

    def ip(self, mt: re.Match) -> str:
        parts = tuple(int(x) for x in mt.groups())
        if any(p > 255 for p in parts) or private_ip(parts):
            return mt.group(0)
        return self._num("ip", mt.group(0), "<public-ip-{}>")

    def run(self, text: str) -> str:
        text = RE_SCRATCH.sub("<scratch>", text)
        text = RE_HOME.sub("<home>", text)
        text = RE_EMAIL.sub(lambda m: m.group(0) if doc_address(m.group(0)) else "<email>", text)
        text = RE_JWT.sub("<jwt>", text)
        for s in self.suffixes:
            text = text.replace(s, "<sfx>")
        text = RE_GUID.sub(self.guid, text)
        text = RE_SCOPEFRAG.sub(lambda m: m.group(1) + ("<sub>" if "subscriptions" in m.group(1) else "<tenant>"), text)
        text = RE_GUIDFRAG.sub(lambda m: self._num("guid", m.group(0).lower(), "<guid-{}>"), text)
        text = RE_OBJ.sub(lambda m: m.group(1) + self._num("obj", m.group(2), "<id-{}>"), text)
        text = RE_DASHOBJ.sub(lambda m: m.group(1) + self._num("obj", m.group(2), "<id-{}>"), text)
        text = RE_ISOKEY.sub(lambda m: m.group(1) + self._num("key", m.group(2), "<key-{}>"), text)
        text = RE_LONG.sub(lambda m: self._num("long", m.group(0), "<token-{}>"), text)
        text = RE_HEX32.sub(lambda m: self._num("hex", m.group(0).lower(), "<hex-{}>"), text)
        text = RE_IPV4.sub(self.ip, text)
        return text


def files_under(paths: list[Path], exts: set[str]) -> list[Path]:
    out = []
    for p in paths:
        it = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
        out += [x for x in it if x.suffix in exts and "__pycache__" not in x.parts]
    return out


def keep_list(paths: list[Path]) -> set[str]:
    """組み込みロールの定義 ID: スクリプト中の GUID 定数と、ログ中の roleDefinitions/<id>。"""
    keep: set[str] = set()
    for f in files_under(paths, SCRIPT_EXT):
        keep |= set(RE_GUID.findall(f.read_text(encoding="utf-8", errors="replace")))
    for f in files_under(paths, TARGET_EXT):
        keep |= set(re.findall(r"roleDefinitions/(" + GUID + ")", f.read_text(encoding="utf-8", errors="replace")))
    return keep


def leaks(text: str, keep: set[str]) -> list[str]:
    found = [m for m in RE_EMAIL.findall(text) if not doc_address(m)]
    found += [g for g in RE_GUID.findall(text) if g.lower() not in keep and not g.startswith("00000000-0000-0000-0000-")]
    found += [m.group(0) for m in RE_IPV4.finditer(text)
              if all(int(x) <= 255 for x in m.groups()) and not private_ip(tuple(int(x) for x in m.groups()))]
    found += RE_HOME.findall(text) + RE_SCRATCH.findall(text)
    found += RE_HEX32.findall(text) + [m.group(2) for m in RE_ISOKEY.finditer(text)]
    found += [m.group(2) for m in RE_SCOPEFRAG.finditer(text) if not RE_GUID.fullmatch(m.group(2))]
    found += [m.group(0) for m in RE_GUIDFRAG.finditer(text)]
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--suffix", action="append", default=[], help="リソース名の乱数部分(複数可)")
    ap.add_argument("--check", action="store_true", help="書き換えずに伏せ字漏れだけを報告")
    a = ap.parse_args()
    keep = {g.lower() for g in keep_list(a.paths)}
    targets = files_under(a.paths, TARGET_EXT)
    if a.check:
        bad = 0
        for f in targets:
            hits = leaks(f.read_text(encoding="utf-8", errors="replace"), keep)
            if hits:
                bad += 1
                print(f"{f}: {len(hits)} 件(種類: {', '.join(sorted({h.split('@')[0][:3] + '…' for h in hits}))})")
        print("伏せ字漏れなし" if not bad else f"{bad} ファイルに漏れ")
        return 1 if bad else 0
    start: dict[str, int] = {}
    for f in targets:
        for kind, n in RE_PLACEHOLDER.findall(f.read_text(encoding="utf-8", errors="replace")):
            start[kind] = max(start.get(kind, 0), int(n))
    sc = Scrubber(keep, a.suffix, start)
    changed = 0
    for f in targets:
        old = f.read_text(encoding="utf-8", errors="replace")
        new = sc.run(old)
        if new != old:
            f.write_text(new, encoding="utf-8")
            changed += 1
    counts = ", ".join(f"{k} {len(v)}" for k, v in sc.maps.items())
    print(f"{changed}/{len(targets)} ファイルを書き換え({counts or '置換なし'})。残した組み込みロール ID: {len(keep)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
