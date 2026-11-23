"""docs/events の PPTX 生成キット(python-pptx 1.0.2)。build.py から呼ぶ。

slides.py の SLIDES は dict のリスト。layout は 3 種:
  title  : title / subtitle / date
  figure : title / message / image(1 枚の図か画面)/ points(任意、右列)/ source / notes
  shots  : title / message / shots=[{image, caption}](2〜3 枚を横並び)/ points(任意、下段)/ source / notes
points の要素は文字列か (見出し, 補足) のタプル。文字は少なく: 見出し 14 字・補足 30 字が目安。
同じレイアウトの HTML を Chrome で撮ったプレビュー(build/preview/)で、はみ出しを目で確かめる。
"""
from __future__ import annotations

import html
from pathlib import Path

W_IN, H_IN = 13.333, 7.5
PX = 96  # プレビューの 1 インチ
FG, MUTED, ACCENT, BORDER, PANEL = "1C1E21", "57606A", "0F6CBD", "D8DEE4", "F7F9FB"
LATIN, EA = "Segoe UI", "Yu Gothic UI"
PREVIEW_FONT = '"Yu Gothic UI","Noto Sans CJK JP",sans-serif'

# 共通の座標(インチ): 左右余白 0.5、タイトル帯、本文域、フッター
TITLE = (0.5, 0.32, 12.33, 0.62)
MESSAGE = (0.5, 0.98, 12.33, 0.5)
BODY = (0.5, 1.65, 12.33, 5.2)
FOOT_Y = 7.06


def _layout(s: dict) -> list[tuple]:
    """スライドを (kind, x, y, w, h, payload) の箱に分解する。PPTX とプレビューで共用。"""
    boxes: list[tuple] = []
    lay = s.get("layout", "figure")
    if lay == "title":
        boxes.append(("band", 0, 0, W_IN, 0.12, None))
        boxes.append(("text", 0.8, 2.3, 11.7, 1.3, {"text": s["title"], "size": 40, "bold": True}))
        if s.get("subtitle"):
            boxes.append(("text", 0.8, 3.65, 11.7, 1.0, {"text": s["subtitle"], "size": 22, "color": ACCENT}))
        if s.get("date"):
            boxes.append(("text", 0.8, 5.6, 11.7, 0.5, {"text": s["date"], "size": 14, "color": MUTED}))
        return boxes
    boxes.append(("band", 0, 0, W_IN, 0.08, None))
    boxes.append(("text", *TITLE, {"text": s["title"], "size": 28, "bold": True}))
    if s.get("message"):
        boxes.append(("text", *MESSAGE, {"text": s["message"], "size": 17, "color": ACCENT, "bold": True}))
    bx, by, bw, bh = BODY
    pts = s.get("points") or []
    if lay == "figure":
        iw = bw if not pts else bw * 0.66
        boxes.append(("image", bx, by, iw, bh, {"path": s["image"]}))
        if pts:
            boxes.append(("points", bx + iw + 0.3, by + 0.1, bw - iw - 0.3, bh - 0.1, {"items": pts}))
    elif lay == "shots" and s.get("arrange") == "stack":
        # 横長の画面を左列に縦積み、要点は右列(横長のスクリーンショット向け)
        shots = s["shots"]
        lw = bw * 0.7
        cap = 0.36
        sh_h = (bh - cap * len(shots) - 0.15 * (len(shots) - 1)) / len(shots)
        y = by
        for sh in shots:
            if "image" in sh:
                boxes.append(("image", bx, y, lw, sh_h, {"path": sh["image"], "frame": True}))
                cy = y + sh_h + 0.02
            else:
                # 画面を転載しない場合は、掲載ページを示すパネルにする(枠の中央に置く)
                ph = min(sh_h, 1.5)
                py = y + (sh_h - ph) / 2
                boxes.append(("points", bx, py, lw, ph,
                              {"items": [(sh["label"], "画面はこの資料に転載していない。掲載ページ: " + sh["link"])]}))
                cy = py + ph + 0.06
            boxes.append(("text", bx, cy, lw, cap - 0.04,
                          {"text": sh.get("caption", ""), "size": 12, "color": MUTED, "align": "center"}))
            y += sh_h + cap + 0.15
        if pts:
            boxes.append(("points", bx + lw + 0.3, by + 0.1, bw - lw - 0.3, bh - 0.1, {"items": pts}))
    elif lay == "shots":
        shots = s["shots"]
        ph = bh - (1.35 if pts else 0.0)
        gap = 0.25
        sw = (bw - gap * (len(shots) - 1)) / len(shots)
        for i, sh in enumerate(shots):
            x = bx + i * (sw + gap)
            boxes.append(("image", x, by, sw, ph - 0.42, {"path": sh["image"], "frame": True}))
            boxes.append(("text", x, by + ph - 0.38, sw, 0.36,
                          {"text": sh.get("caption", ""), "size": 12, "color": MUTED, "align": "center"}))
        if pts:
            boxes.append(("points_row", bx, by + ph + 0.12, bw, 1.15, {"items": pts}))
    if s.get("source"):
        boxes.append(("text", 0.5, FOOT_Y, 10.8, 0.3, {"text": "出典: " + s["source"], "size": 9, "color": MUTED}))
    return boxes


def _fit(path: Path, w: float, h: float) -> tuple[float, float, float, float]:
    from PIL import Image
    with Image.open(path) as im:
        pw, ph = im.size
    r = min(w / pw, h / ph)
    fw, fh = pw * r, ph * r
    return (w - fw) / 2, (h - fh) / 2, fw, fh


def _split(item) -> tuple[str, str]:
    return (item[0], item[1]) if isinstance(item, (tuple, list)) else (item, "")


# ---------------- PPTX ----------------
def build(slides: list[dict], ev: Path, out: Path, meta: dict) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W_IN), Inches(H_IN)
    blank = prs.slide_layouts[6]

    def font(run, size, bold=False, color=FG):
        f = run.font
        f.size, f.bold, f.name = Pt(size), bold, LATIN
        f.color.rgb = RGBColor.from_string(color)
        rpr = run._r.get_or_add_rPr()
        for tag in ("a:ea", "a:cs"):
            el = rpr.find(qn(tag))
            if el is None:
                el = rpr.makeelement(qn(tag), {})
                rpr.append(el)
            el.set("typeface", EA)

    def textbox(sl, x, y, w, h):
        tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        return tf

    for n, s in enumerate(slides, 1):
        sl = prs.slides.add_slide(blank)
        for kind, x, y, w, h, p in _layout(s):
            if kind == "band":
                r = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
                r.fill.solid()
                r.fill.fore_color.rgb = RGBColor.from_string(ACCENT)
                r.line.fill.background()
            elif kind == "text":
                tf = textbox(sl, x, y, w, h)
                para = tf.paragraphs[0]
                if p.get("align") == "center":
                    para.alignment = PP_ALIGN.CENTER
                r = para.add_run()
                r.text = p["text"]
                font(r, p["size"], p.get("bold", False), p.get("color", FG))
            elif kind == "image":
                path = ev / p["path"]
                dx, dy, fw, fh = _fit(path, w, h)
                pic = sl.shapes.add_picture(str(path), Inches(x + dx), Inches(y + dy), Inches(fw), Inches(fh))
                if p.get("frame"):
                    pic.line.color.rgb = RGBColor.from_string(BORDER)
                    pic.line.width = Pt(0.75)
            elif kind in ("points", "points_row"):
                items = p["items"]
                if kind == "points_row":
                    cw = (w - 0.2 * (len(items) - 1)) / len(items)
                    cells = [(x + i * (cw + 0.2), y, cw, h, [it]) for i, it in enumerate(items)]
                else:
                    cells = [(x, y, w, h, items)]
                for cx, cy, cw, ch, its in cells:
                    bg = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(cy), Inches(cw), Inches(ch))
                    bg.adjustments[0] = 0.06
                    bg.fill.solid()
                    bg.fill.fore_color.rgb = RGBColor.from_string(PANEL)
                    bg.line.color.rgb = RGBColor.from_string(BORDER)
                    tf = bg.text_frame
                    tf.word_wrap = True
                    tf.vertical_anchor = MSO_ANCHOR.TOP
                    tf.margin_left = tf.margin_right = Inches(0.16)
                    tf.margin_top = Inches(0.12)
                    first = True
                    for it in its:
                        head, rest = _split(it)
                        para = tf.paragraphs[0] if first else tf.add_paragraph()
                        first = False
                        para.space_after = Pt(4)
                        r = para.add_run()
                        r.text = head
                        font(r, 16, True, ACCENT)
                        if rest:
                            para2 = tf.add_paragraph()
                            para2.space_after = Pt(12)
                            r2 = para2.add_run()
                            r2.text = rest
                            font(r2, 13, False, FG)
        if s.get("layout") != "title":
            tf = textbox(sl, 11.4, FOOT_Y, 1.43, 0.3)
            para = tf.paragraphs[0]
            para.alignment = PP_ALIGN.RIGHT
            r = para.add_run()
            r.text = f"{meta.get('footer', '')}  {n}"
            font(r, 9, False, MUTED)
        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = s["notes"]
    prs.save(out)


# ---------------- preview(同じ箱を HTML で描いて Chrome で撮る) ----------------
def _px(v: float) -> str:
    return f"{v * PX:.1f}px"


def _preview_html(s: dict, n: int, ev: Path, meta: dict) -> str:
    parts = []
    for kind, x, y, w, h, p in _layout(s):
        pos = f"left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)}"
        if kind == "band":
            parts.append(f'<div style="position:absolute;{pos};background:#{ACCENT}"></div>')
        elif kind == "text":
            st = (f"font-size:{p['size'] * 4 / 3:.1f}px;color:#{p.get('color', FG)};"
                  f"font-weight:{700 if p.get('bold') else 400};text-align:{p.get('align', 'left')}")
            parts.append(f'<div class="t" style="{pos};{st}">{html.escape(p["text"])}</div>')
        elif kind == "image":
            path = ev / p["path"]
            dx, dy, fw, fh = _fit(path, w, h)
            fr = f"border:1px solid #{BORDER};" if p.get("frame") else ""
            parts.append(f'<img style="position:absolute;left:{_px(x + dx)};top:{_px(y + dy)};'
                         f'width:{_px(fw)};height:{_px(fh)};{fr}box-sizing:border-box" src="{path.as_uri()}">')
        elif kind in ("points", "points_row"):
            items = p["items"]
            if kind == "points_row":
                cw = (w - 0.2 * (len(items) - 1)) / len(items)
                cells = [(x + i * (cw + 0.2), y, cw, h, [it]) for i, it in enumerate(items)]
            else:
                cells = [(x, y, w, h, items)]
            for cx, cy, cw, ch, its in cells:
                inner = "".join(
                    f'<div style="color:#{ACCENT};font-weight:700;font-size:21.3px;margin-bottom:5px">{html.escape(a)}</div>'
                    + (f'<div style="font-size:17.3px;margin-bottom:16px">{html.escape(b)}</div>' if b else "")
                    for a, b in map(_split, its))
                parts.append(f'<div class="t" style="left:{_px(cx)};top:{_px(cy)};width:{_px(cw)};height:{_px(ch)};'
                             f'background:#{PANEL};border:1px solid #{BORDER};border-radius:8px;'
                             f'padding:11px 15px;box-sizing:border-box;overflow:visible">{inner}</div>')
    if s.get("layout") != "title":
        parts.append(f'<div class="t" style="left:{_px(11.4)};top:{_px(FOOT_Y)};width:{_px(1.43)};'
                     f'font-size:12px;color:#{MUTED};text-align:right">{html.escape(meta.get("footer", ""))}  {n}</div>')
    return ('<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>'
            f'body{{margin:0;width:{_px(W_IN)};height:{_px(H_IN)};position:relative;overflow:hidden;'
            f'font-family:{PREVIEW_FONT};color:#{FG};background:#fff;line-height:1.25;word-break:auto-phrase}}'
            '.t{position:absolute;white-space:pre-wrap;outline:1px dashed rgba(207,34,46,.0)}'
            '</style></head><body>' + "".join(parts) + "</body></html>")


def preview(slides: list[dict], ev: Path, out: Path, meta: dict, shoot) -> None:
    out.mkdir(parents=True, exist_ok=True)
    W, H = round(W_IN * PX), round(H_IN * PX)
    pngs = []
    for n, s in enumerate(slides, 1):
        f = out / f"slide-{n:02d}.html"
        f.write_text(_preview_html(s, n, ev, meta), encoding="utf-8")
        png = out / f"slide-{n:02d}.png"
        shoot(f, png, W, H, scale=1)
        pngs.append(png)
    cells = "".join(f'<img src="{p.as_uri()}" style="width:640px;height:360px;border:1px solid #ccc">' for p in pngs)
    sheet = out / "contact.html"
    sheet.write_text('<!DOCTYPE html><html><body style="margin:8px;display:flex;flex-wrap:wrap;gap:8px;width:1304px">'
                     + cells + "</body></html>", encoding="utf-8")
    rows = (len(pngs) + 1) // 2
    shoot(sheet, out / "contact.png", 1320, rows * 368 + 16, scale=1)
