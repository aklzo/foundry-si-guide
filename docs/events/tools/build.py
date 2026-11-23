#!/usr/bin/env python3
"""イベント変更まとめ(docs/events/<event>/)のビルド。

    python3 docs/events/tools/build.py docs/events/ignite-2026            # 図 → HTML → PPTX → プレビュー
    python3 docs/events/tools/build.py docs/events/ignite-2026 figures    # 段階を指定(figures / html / pptx)

- figures: <event>/figures/*.html を headless Chrome で PNG 化 → <event>/images/fig-<name>.png
  (各 HTML の <meta name="figure-size" content="1600x900"> が出力サイズ。2 倍解像度)
- html:    <event>/*.md を docs/survey/tools/md2html.py の変換器で <event>/html/*.html に
           (README.md → index.html。画像の alt を figcaption にする)
- pptx:    <event>/slides.py の SLIDES を pptx_kit で <event>/<event>.pptx に。
           プレビュー PNG を <event>/build/preview/ に出す(build/ は .gitignore)

PPTX は uv で python-pptx を使う(`uv run --no-project --with python-pptx==1.0.2`)。この
スクリプト自体は標準ライブラリだけで動き、pptx 段階で uv を呼び出す。
"""
from __future__ import annotations

import glob
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
sys.path.insert(0, str(REPO / "docs" / "survey" / "tools"))
import md2html  # noqa: E402  (同じ Markdown サブセット・CSS を使う)

# events だけのバッジ語(survey 側の md2html は変えない)
_EXTRA_BADGES = [("両論", "split"), ("Frontier", "soon"), ("予定", "soon"), ("限定プレビュー", "private")]
md2html.BADGE_CLASSES = _EXTRA_BADGES + md2html.BADGE_CLASSES
md2html._BADGE_MAP = dict(md2html.BADGE_CLASSES)
md2html._BADGE_RE = re.compile(
    r"^(\s*)(" + "|".join(re.escape(t) for t, _ in md2html.BADGE_CLASSES) + r")(?=$|[\s(（/、,:：。→])")


def chrome() -> str:
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    hits = sorted(glob.glob(os.path.expanduser(
        "~/.cache/puppeteer/chrome-headless-shell/*/chrome-headless-shell-linux64/chrome-headless-shell")))
    if not hits:
        sys.exit("headless Chrome がない: npx -y puppeteer browsers install chrome-headless-shell@stable")
    return hits[-1]


def shoot(html_path: Path, png_path: Path, w: int, h: int, scale: int = 2) -> None:
    subprocess.run([
        chrome(), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
        f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
        f"--screenshot={png_path}", html_path.as_uri(),
    ], check=True, capture_output=True)


# ---------- figures ----------
def build_figures(ev: Path) -> None:
    out = ev / "images"
    out.mkdir(exist_ok=True)
    for f in sorted((ev / "figures").glob("*.html")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r'<meta name="figure-size" content="(\d+)x(\d+)"', text)
        w, h = (int(m.group(1)), int(m.group(2))) if m else (1600, 900)
        png = out / f"fig-{f.stem}.png"
        shoot(f, png, w, h)
        print(f"  figure {f.name} -> images/{png.name} ({w}x{h} @2x)")


# ---------- html ----------
EXTRA_CSS = """
main { max-width: 1180px; }
figure { margin: 1.4rem 0; text-align: center; }
figure img { max-width: 100%; border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,.06); }
figcaption { color: var(--muted); font-size: .85rem; margin-top: .4rem; }
.lead { font-size: 1.05rem; }
.badge.split { color: #8250df; background: #fbefff; }
.badge small { font-weight: 400; margin-left: 2px; }
.badge.soon { color: #57606a; background: #eef1f4; }
"""


_TAG_CLASS = {"GA": "ga", "Preview": "preview", "限定プレビュー": "private", "予定": "soon", "Frontier": "soon",
              "記載なし": "na", "非推奨": "deprecated", "廃止": "retired"}


def _tag(m: re.Match) -> str:
    """[[状態]] または [[状態:出典]] をバッジにする。出典が食い違うときは出典つきのタグを並べて書く。"""
    state, src = m.group(1).strip(), (m.group(2) or "").strip()
    cls = _TAG_CLASS.get(state, "unknown")
    label = f"{state}<small>({src})</small>" if src else state
    return f'<span class="badge {cls}">{label}</span>'


def build_html(ev: Path) -> None:
    out = ev / "html"
    out.mkdir(exist_ok=True)
    mds = sorted(ev.glob("*.md"), key=lambda p: (p.name != "README.md", p.name))
    pages = []
    for p in mds:
        body, title, h2s = md2html.convert(p.read_text(encoding="utf-8"))
        # ステータスのタグ [[GA]] / [[Preview:公式 GA 一覧]] → バッジ(出典つき)
        body = re.sub(r"\[\[([^\]:]+?)(?::([^\]]+))?\]\]", _tag, body)
        # 画像だけの段落 → figure(alt をキャプションに)
        body = re.sub(r'<p><img src="([^"]+)" alt="([^"]*)" loading="lazy"></p>',
                      r'<figure><img src="\1" alt="\2" loading="lazy"><figcaption>\2</figcaption></figure>', body)
        # survey の .md へのリンク(../../survey/<set>/<x>.md)を生成 HTML へ
        body = re.sub(r'href="\.\./\.\./\.\./survey/([\w-]+)/([\w.-]+)\.md(#[^"]*)?"',
                      lambda m: 'href="../../../survey/%s/html/%s.html%s"' % (
                          m.group(1), "index" if m.group(2) == "README" else m.group(2), m.group(3) or ""), body)
        pages.append((p, "index.html" if p.name == "README.md" else p.stem + ".html", title or p.stem, body, h2s))
    for p, name, title, body, h2s in pages:
        nav = "".join(f'<a href="{n}"{" class=\"current\"" if n == name else ""}>{md2html.short(t)}</a>'
                      for _, n, t, _, _ in pages)
        nav += '<a class="xset" href="../../README.md">→ events</a>'
        if len(h2s) >= 3:
            items = "".join(f'<li><a href="#{i}">{t}</a></li>' for t, i in h2s)
            body = body.replace("</h1>", f'</h1><div class="toc"><strong>このページの内容</strong><ul>{items}</ul></div>', 1)
        rel = p.relative_to(REPO)
        doc = ("<!DOCTYPE html>\n<html lang=\"ja\"><head><meta charset=\"utf-8\">\n"
               '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f"<title>{title}</title>\n<style>{md2html.CSS}{EXTRA_CSS}</style></head>\n"
               f'<body><nav class="site">{nav}</nav>\n<main>\n{body}\n</main>\n'
               f"<footer>この HTML は {rel} から docs/events/tools/build.py で自動生成。編集は Markdown 側で。</footer>"
               "</body></html>\n")
        (out / name).write_text(doc, encoding="utf-8")
        print(f"  html {p.name} -> html/{name}")


# ---------- pptx ----------
def build_pptx(ev: Path) -> None:
    if importlib.util.find_spec("pptx") is None and not os.environ.get("EVENTS_IN_UV"):
        env = dict(os.environ, EVENTS_IN_UV="1")
        subprocess.run(["uv", "run", "--no-project", "--with", "python-pptx==1.0.2", "python",
                        str(Path(__file__)), str(ev), "pptx"], check=True, env=env)
        return
    sys.path.insert(0, str(TOOLS))
    import pptx_kit  # noqa: E402
    spec = importlib.util.spec_from_file_location("slides", ev / "slides.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = ev / f"{ev.name}.pptx"
    pptx_kit.build(mod.SLIDES, ev, out, getattr(mod, "META", {}))
    print(f"  pptx slides.py -> {out.name} ({len(mod.SLIDES)} slides)")
    prev = ev / "build" / "preview"
    pptx_kit.preview(mod.SLIDES, ev, prev, getattr(mod, "META", {}), shoot)
    print(f"  preview -> build/preview/ (slide-NN.png, contact.png)")


STAGES = {"figures": build_figures, "html": build_html, "pptx": build_pptx}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    ev = Path(argv[1]).resolve()
    stages = argv[2:] or list(STAGES)
    for s in stages:
        print(f"[{s}] {ev.relative_to(REPO)}")
        STAGES[s](ev)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
