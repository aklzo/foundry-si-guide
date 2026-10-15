"""hosted agent デプロイの純関数部(zip ステージング+バージョン定義)。

HTTP/SDK を貼るのは hosting/deploy_hosted_agent.py のみ(db-routing-iq の
kb_setup.py と同じ「ペイロード組み立ては純関数・オフラインテストで固定」方針)。

実装前調査の要点(quickstart-hosted-agent / concepts/hosted-agents、2026-07):

- コードデプロイは **zip のルートに main.py と requirements.txt が必須**
  (quickstart の Troubleshooting に明記)。パッケージ本体
  (``hn_briefing_maf/``)も zip ルートへ同梱して import 可能にする
- ``create_version_from_code`` の定義は HostedAgentDefinition(cpu/memory +
  CodeConfiguration(runtime, entry_point, dependency_resolution=REMOTE_BUILD)
  + environment_variables + protocol_versions)。**コンテナプロトコルは
  responses 2.0.0**(1.0.0 はサポート終了・ブロック済み。2026-09-29 に
  quickstart / deploy-hosted-agent-code で 2.0.0 が現行のままと再確認)
- 環境変数がコンテナへの唯一の構成手段(バージョンごとに不変)。
  App Insights 接続文字列はプラットフォームが自動注入するため渡さない
- サンドボックスは 0.5vCPU/1GiB で十分(HN GET 1 本+モデル呼び出しのみ)
- idle timeout(``session_configuration.idle_timeout_seconds``、120〜3600 秒)は
  指定しない = サービス既定 900 秒(15 分)。日次 1 回の起動では既定で足りる

本番リリース手順(2026-10-06 追加。Learn manage-hosted-agent「Release a version without
changing production」2026-09-16 版): エンドポイントの既定ルーティングは**最新版に追従**するため、
版を作る前に本番を具体版へ FixedRatio 100% で**ピン留め**し、候補版は版指定のセッション
(``version_indicator`` = ``version_ref``)で試してから、セレクタだけを候補へ切り替える。
セレクタの組み立てと「今どの版にピン留めされているか」の読み取りは下の純関数で行い、
エンドポイント設定のほかの項目(プロトコル・認可方式)は保ったまま差し替える。
"""

from __future__ import annotations

import shutil
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: ポートのルート(src/hn_briefing_maf/ の 2 つ上)
PORT_ROOT = Path(__file__).resolve().parents[2]

#: zip ルートに置くファイル(hosted agent コードデプロイの必須規約)
REQUIRED_ZIP_ROOT_FILES = ("main.py", "requirements.txt")

#: コンテナプロトコル(2.0.0 必須 — 1.0.0 はサポート終了)
RESPONSES_PROTOCOL_VERSION = "2.0.0"


def stage_hosted_agent_dir(dest: Path, *, port_root: Path = PORT_ROOT) -> Path:
    """デプロイ zip の中身を dest に組み立てる。

    - hosting/main.py / hosting/requirements.txt → zip ルート
    - src/hn_briefing_maf/ → zip ルート直下の hn_briefing_maf/
      (main.py の ``import hn_briefing_maf`` を成立させる)
    """
    dest.mkdir(parents=True, exist_ok=True)
    hosting_dir = port_root / "hosting"
    for name in REQUIRED_ZIP_ROOT_FILES:
        source = hosting_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"hosting/{name} が見つからない: {source}")
        shutil.copy2(source, dest / name)
    shutil.copytree(
        port_root / "src" / "hn_briefing_maf",
        dest / "hn_briefing_maf",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        dirs_exist_ok=True,
    )
    return dest


def create_code_zip(staged_dir: Path, zip_path: Path) -> Path:
    """ステージ済みディレクトリを zip 化する(相対パス保存)。"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(staged_dir.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(staged_dir))
    return zip_path


def hosted_agent_definition_kwargs(
    *,
    project_endpoint: str,
    model: str,
    cpu: str = "0.5",
    memory: str = "1Gi",
    runtime: str = "python_3_13",
) -> dict[str, Any]:
    """HostedAgentDefinition に渡す値(SDK 型に依存しない素の dict)。

    deploy スクリプトが azure-ai-projects の型へ写像する。環境変数は
    hosting/main.py が読む 2 点のみ — API キーは渡さない(hosted 実行は
    agent identity + FoundryChatClient。README の学び参照)。
    """
    return {
        "cpu": cpu,
        "memory": memory,
        "runtime": runtime,
        "entry_point": ["python", "main.py"],
        "environment_variables": {
            "FOUNDRY_PROJECT_ENDPOINT": project_endpoint,
            "FOUNDRY_MODEL_NAME": model,
        },
        "protocols": [("responses", RESPONSES_PROTOCOL_VERSION)],
    }


# --- エンドポイントのルーティング(本番リリース手順)---

#: エンドポイント設定のうちサーバーが埋める読み取り専用の項目(送り返さない)
READ_ONLY_ENDPOINT_FIELDS = ("publish_approval_status",)


def fixed_version_selector(version: str) -> dict[str, Any]:
    """具体版 1 つに 100% を向けるセレクタ(hosted agent はトラフィック分割不可)。"""
    return {
        "version_selection_rules": [
            {"type": "FixedRatio", "agent_version": str(version), "traffic_percentage": 100}
        ]
    }


def pinned_version(endpoint: Mapping[str, Any] | None) -> str | None:
    """エンドポイントが具体版 1 つに 100% 固定されていればその版、そうでなければ ``None``。

    ``None`` = セレクタ未設定(既定の「最新版に追従」)か、想定外の形。この状態で版を作ると
    利用者に届く版が変わりうるので、候補をデプロイする前にピン留めが要る。
    """
    selector = (endpoint or {}).get("version_selector") or {}
    rules = selector.get("version_selection_rules") or []
    if len(rules) != 1:
        return None
    rule = rules[0]
    if rule.get("type") != "FixedRatio" or rule.get("traffic_percentage") != 100:
        return None
    version = rule.get("agent_version")
    return str(version) if version else None


def endpoint_with_version(endpoint: Mapping[str, Any] | None, version: str) -> dict[str, Any]:
    """既存のエンドポイント設定を保ったまま、セレクタだけを ``version`` 100% に差し替える。

    公式手順の「プロトコルや認可の設定は保ったままセレクタを更新する」。未設定なら
    Responses プロトコルの既定構成を補う(初回デプロイ)。
    """
    updated = {
        key: value
        for key, value in dict(endpoint or {}).items()
        if key not in READ_ONLY_ENDPOINT_FIELDS
    }
    updated["version_selector"] = fixed_version_selector(version)
    updated.setdefault("protocol_configuration", {"responses": {}})
    return updated
