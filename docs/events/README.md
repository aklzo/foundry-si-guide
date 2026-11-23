# docs/events — イベント変更まとめ

Microsoft のイベント(Ignite・Build など)ごとに、Microsoft Foundry と Copilot Studio の変更をまとめた資料。図を中心にし(製品の画面は Microsoft Learn の掲載ページへのリンクで示す)、ステータスの判定は [features 調査](../survey/features/README.md) と同じ基準(GA 一覧表を正、食い違いは両論)で書く。

| イベント | 基準日 | 詳細版(HTML) | 要約版(PPTX、Foundry のみ) |
| --- | --- | --- | --- |
| [Microsoft Ignite 2026](ignite-2026/README.md)(2026-11-17〜20) | 2026-11-22 | `ignite-2026/html/index.html` | `ignite-2026/ignite-2026.pptx`(10 枚) |

## 作り方・更新のしかた

```bash
python3 docs/events/tools/build.py docs/events/<event>            # 図 → HTML → PPTX(+プレビュー)
python3 docs/events/tools/build.py docs/events/<event> html       # 段階だけ(figures / html / pptx)
python3 docs/events/tools/collect.py --since <基準日> --out <作業用ディレクトリ> --bon <Book of News の URL>
```

| パス | 役割 |
| --- | --- |
| `<event>/README.md` | 原本(詳細版)。`html/index.html` を生成 |
| `<event>/figures/*.html` | 図の原本。`images/fig-*.png`(1600x675 の 2 倍解像度)を生成 |
| `<event>/slides.py` | PPTX の原本。`<event>.pptx` と `build/preview/`(git 管理外)を生成 |
| `tools/build.py` | ビルド(HTML は `docs/survey/tools/md2html.py` の変換器を流用) |
| `tools/pptx_kit.py` | スライドのレイアウト(title / figure / shots)と PPTX・プレビューの生成 |
| `tools/figure.css` | 図の共通スタイル(配色は survey・slides と同じ) |
| `tools/collect.py` | 発表記事の収集とステータス表現の抜き出し |

- 前提: python3、uv(PPTX 生成で python-pptx を取得)、headless Chrome(`npx -y puppeteer browsers install chrome-headless-shell@stable`)。
- HTML・PNG・PPTX は生成物。編集は README.md・figures・slides.py 側で行う。
