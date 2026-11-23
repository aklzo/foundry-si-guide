#!/usr/bin/env python3
"""IP がどのサービスタグ(と地域)に入るかを調べる。az network list-service-tags の JSON を入力にする。

    az network list-service-tags --location japaneast -o json > tags.json
    python3 -I tagip.py tags.json <ip> [<ip> ...]

出力は IP ごとに、含むタグを狭いプレフィックス順に並べたもの(region 付きのタグ名・systemService・最長一致のプレフィックス長)。
"""
from __future__ import annotations

import ipaddress
import json
import sys


def main() -> None:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(f"changeNumber={d.get('changeNumber')} cloud={d.get('cloud')} tags={len(d['values'])}")
    nets = []
    for v in d["values"]:
        p = v["properties"]
        for pfx in p.get("addressPrefixes") or []:
            try:
                nets.append((ipaddress.ip_network(pfx), v["name"], p.get("region") or "", p.get("systemService") or ""))
            except ValueError:
                pass
    for ip_s in sys.argv[2:]:
        ip = ipaddress.ip_address(ip_s)
        hits = sorted({(n.prefixlen, name, region, svc) for n, name, region, svc in nets if ip.version == n.version and ip in n},
                      key=lambda x: (-x[0], x[1]))
        print(f"{ip_s}: {len(hits)} tags")
        for plen, name, region, svc in hits[:12]:
            print(f"   /{plen:<3} {name:<45} region={region or '-':<12} systemService={svc or '-'}")


if __name__ == "__main__":
    main()
