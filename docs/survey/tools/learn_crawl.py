#!/usr/bin/env python3
"""Learn の TOC を巡回して、差分更新の対象ページを洗い出す。

MicrosoftDocs/azure-ai-docs(公開ミラー)が 2026-10-14 時点で 404 になり、
「git diff で期間の変更を追う」手順が使えなくなったための代替。

- 各 TOC(Foundry / Foundry classic / Speech / Content Safety / Content Understanding /
  Language / AI Search / Agent Framework)の全ページを取得し、meta の updated_at / ms.date と
  本文テキストのハッシュを記録する。
- `--since` 以降に updated_at / ms.date が更新されたページの生 HTML を `--out` に保存する。
- `--snapshot` に前回の記録(TSV)を渡すと、updated_at が変わっていないのに本文ハッシュが
  変わったページ(= include ファイルだけの変更。Learn の updated_at には反映されない)と、
  新設・削除されたページを報告する。巡回後は同じパスに今回の記録を書き戻す。

使い方(リポジトリルートで):
    python3 docs/survey/tools/learn_crawl.py --since 2026-10-06 \
        --out <scratchpad>/crawl --snapshot docs/survey/tools/learn-snapshot.tsv

出力: <out>/index.json(全ページ)、<out>/pages/*.html(更新ページ)、<out>/report.txt
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TOCS = {
    'foundry': 'https://learn.microsoft.com/en-us/azure/foundry/',
    'foundry-classic': 'https://learn.microsoft.com/en-us/azure/foundry-classic/',
    'speech': 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/',
    'content-safety': 'https://learn.microsoft.com/en-us/azure/ai-services/content-safety/',
    'content-understanding': 'https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/',
    'language': 'https://learn.microsoft.com/en-us/azure/ai-services/language-service/',
    'search': 'https://learn.microsoft.com/en-us/azure/search/',
    'agent-framework': 'https://learn.microsoft.com/en-us/agent-framework/',
}
SKIP = ('/rest/', '/python/api', '/dotnet/api', '/javascript/api', '/java/api', '/cli/')
UA = {'User-Agent': 'foundry-si-guide-learn-crawl/1.0 (+https://github.com/aklzo/foundry-si-guide)'}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.geturl(), r.read().decode('utf-8', 'replace')


class MainText(HTMLParser):
    """<main> 内のテキストだけを集める(ナビ・スクリプトは除く)。"""

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.inmain = [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.inmain = True
        if tag in ('script', 'style', 'nav'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav'):
            self.skip -= 1

    def handle_data(self, data):
        if self.inmain and self.skip <= 0:
            self.out.append(data)


def body_hash(html):
    p = MainText()
    p.feed(html)
    text = re.sub(r'\s+', ' ', ''.join(p.out)).strip()
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def meta(html, name):
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else ''


def toc_urls():
    urls = {}
    for name, base in TOCS.items():
        try:
            _, text = get(base + 'toc.json')
        except Exception as e:  # noqa: BLE001 — TOC が消えても他は続ける
            print('toc fail', name, e, file=sys.stderr)
            continue

        def walk(items):
            for it in items:
                h = it.get('href')
                if h and not h.startswith('http'):
                    u = urllib.parse.urljoin(base, h).split('?')[0].split('#')[0]
                    if u.startswith('https://learn.microsoft.com/en-us/') and not any(s in u for s in SKIP):
                        urls.setdefault(u, name)
                walk(it.get('children', []))

        walk(json.loads(text).get('items', []))
    return urls


def load_snapshot(path):
    snap = {}
    if path and os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.startswith('#') or not line.strip():
                continue
            url, updated, ms_date, sha = line.rstrip('\n').split('\t')[:4]
            snap[url] = (updated, ms_date, sha)
    return snap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', required=True, help='YYYY-MM-DD(この日以降の更新ページを保存)')
    ap.add_argument('--out', required=True, help='出力ディレクトリ(リポジトリ外を推奨)')
    ap.add_argument('--snapshot', help='前回の記録 TSV(比較後に今回の記録で上書き)')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()

    urls = toc_urls()
    print('pages', len(urls), file=sys.stderr)
    os.makedirs(os.path.join(a.out, 'pages'), exist_ok=True)

    def one(u):
        try:
            final, h = get(u)
        except Exception as e:  # noqa: BLE001
            return {'url': u, 'toc': urls[u], 'err': str(e)[:80]}
        rec = {
            'url': u, 'final': final, 'toc': urls[u],
            'title': (re.search(r'<title>(.*?)</title>', h, re.S) or [None, ''])[1].strip(),
            'ms_date': meta(h, 'ms.date')[:10], 'updated_at': meta(h, 'updated_at'),
            'src': meta(h, 'original_content_git_url').split('/blob/live/')[-1],
            'sha': body_hash(h),
        }
        if rec['updated_at'][:10] >= a.since or rec['ms_date'] >= a.since:
            fn = re.sub(r'[^A-Za-z0-9]+', '_', final.split('/en-us/')[-1])[:150] + '.html'
            with open(os.path.join(a.out, 'pages', fn), 'w', encoding='utf-8') as f:
                f.write(h)
            rec['file'] = fn
        return rec

    with cf.ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(one, sorted(urls)))
    with open(os.path.join(a.out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)

    ok = [r for r in recs if 'err' not in r]
    lines = ['# updated since %s' % a.since]
    for r in sorted((r for r in ok if r.get('file')), key=lambda r: r['updated_at'], reverse=True):
        lines.append('%s  ms.date=%s  %s' % (r['updated_at'][:16], r['ms_date'], r['final']))

    snap = load_snapshot(a.snapshot)
    if snap:
        cur = {r['url']: r for r in ok}
        inc = [r for u, r in cur.items() if u in snap and snap[u][0] == r['updated_at'] and snap[u][2] != r['sha']]
        lines.append('\n# body changed without updated_at change (include-only edits?): %d' % len(inc))
        lines += ['%s  %s' % (r['updated_at'][:16], r['final']) for r in inc]
        lines.append('\n# new pages vs snapshot: %d' % len(set(cur) - set(snap)))
        lines += sorted(set(cur) - set(snap))
        lines.append('\n# removed pages vs snapshot: %d' % len(set(snap) - set(cur)))
        lines += sorted(set(snap) - set(cur))
    report = '\n'.join(lines) + '\n'
    with open(os.path.join(a.out, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write(report)

    if a.snapshot:
        with open(a.snapshot, 'w', encoding='utf-8') as f:
            f.write('# url\tupdated_at\tms.date\tbody_sha1_12 — learn_crawl.py が上書きする(手で編集しない)\n')
            for r in sorted(ok, key=lambda r: r['url']):
                f.write('%s\t%s\t%s\t%s\n' % (r['url'], r['updated_at'], r['ms_date'], r['sha']))
    print('errors', len(recs) - len(ok), 'updated', sum(1 for r in ok if r.get('file')),
          '-> %s/report.txt' % a.out, file=sys.stderr)


if __name__ == '__main__':
    main()
