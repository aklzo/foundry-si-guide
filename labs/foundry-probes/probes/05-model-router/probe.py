"""Model router(GA v2025-11-18)の挙動確認。

観点:
  A. japaneast にデプロイできた事実(survey のリージョン表 5 リージョンに
     japaneast が無い → 表の更新が必要)
  B. 難易度の異なるプロンプトでどのモデルにルーティングされるか(response.model)
  C. 非 OpenAI モデルへのルーティング(プレビュー扱いの既定動作)
  D. usage / 課金単位の見え方(ルーティング先モデルの単価になるはず)
  E. reasoning 系パラメータ(temperature)の受理 — ルーティング先依存で挙動が変わるか
  F. ルーティングの記録(2026-10-06 追加・未実測): Chat Completions に
     ``Foundry-Features: ModelRouterControls=V1Preview``(プレビュー)を付けると、応答に
     ``model_selection_details.model_router_details``(mode / routing_trace)が付くか。
     公式 monitor-model-router(2026-09-15 版)はリソースの Azure OpenAI エンドポイントで
     説明しているので、アカウントの openai/v1 で叩く

ルーターのデプロイ名は環境変数 ``FOUNDRY_ROUTER_DEPLOYMENT``(既定 ``model-router``)。
ルーティング先を絞ったデプロイ(model subset / routing mode)を別名で作れば、同じ probe で
「絞り込みが効くか」を比べられる(runbook §6.5)。
"""

from __future__ import annotations

import os
import sys

from foundry_probes.common import (
    Settings,
    make_openai_client,
    make_project_client,
    section,
    show,
)

PROMPTS = [
    ("易: 挨拶", "こんにちは!"),
    ("易: 単純事実", "日本の首都は?一語で。"),
    ("中: 短い作文", "秋の季語を使って俳句を一句。"),
    ("難: 多段推論", "3 桁の整数のうち、各桁の和が 15 で、桁を逆順にすると元より 396 大きくなるものをすべて挙げ、根拠を段階的に示して。"),
    ("難: コード", "Python で LRU キャッシュをスレッドセーフに実装して。ロック粒度の設計理由も。"),
]


def main() -> int:
    settings = Settings.from_env()
    client = make_project_client(settings).get_openai_client()
    router = os.environ.get("FOUNDRY_ROUTER_DEPLOYMENT", "model-router")
    print(f"  router deployment: {router}")

    section("B/C. プロンプト難易度別のルーティング先")
    for label, prompt in PROMPTS:
        try:
            r = client.responses.create(model=router, input=prompt)
            usage = r.usage.model_dump() if r.usage else {}
            print(f"  [{label}] -> model={r.model} out_tokens={usage.get('output_tokens')}")
        except Exception as exc:
            print(f"  [{label}] !! {type(exc).__name__}: {str(exc)[:150]}")

    section("D. usage の詳細(最後の応答)")
    r = client.responses.create(model=router, input="1+1 は?")
    show("model / usage", {"model": r.model, "usage": r.usage.model_dump() if r.usage else None})

    section("E. temperature の受理(ルーティング先が reasoning 系だと拒否されるか)")
    for temp in (0.2,):
        try:
            r = client.responses.create(model=router, input="サイコロを振った気持ちで 1〜6 の数字を1つ。", temperature=temp)
            print(f"  temperature={temp} -> OK(model={r.model})")
        except Exception as exc:
            print(f"  temperature={temp} -> {type(exc).__name__}: {str(exc)[:180]}")

    section("F. ルーティングの記録(ModelRouterControls=V1Preview・プレビュー)")
    try:
        account = make_openai_client(settings)
        c = account.chat.completions.create(
            model=router,
            messages=[{"role": "user", "content": "量子もつれを中学生向けに 2 文で。"}],
            extra_headers={"Foundry-Features": "ModelRouterControls=V1Preview"},
        )
        details = (c.model_extra or {}).get("model_selection_details")
        show("model / model_selection_details", {"model": c.model, "model_selection_details": details})
        if details is None:
            print("  model_selection_details なし(プレビューのため付かない場合がある)")
    except Exception as exc:
        print(f"!! {type(exc).__name__}: {str(exc)[:250]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
