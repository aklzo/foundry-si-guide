"""hosted agent のデプロイ(SDK 経路・ライブ専用)。

    uv sync --extra dev --extra hosting
    az login   # Foundry Project Manager 以上のロールが必要
    uv run python hosting/deploy_hosted_agent.py                 # デプロイ+100% ルーティング
    uv run python hosting/deploy_hosted_agent.py --invoke "Give me today's brief."
    uv run python hosting/deploy_hosted_agent.py --dry-run       # zip 内容と定義の確認のみ

    # 本番を変えずに候補を出す(2026-10-06 追加。公式の「Release a version without changing
    # production」): 本番をピン留め → 候補を作成 → 候補に固定したセッションで試す → 切り替え
    uv run python hosting/deploy_hosted_agent.py --candidate --invoke "Give me today's brief."
    uv run python hosting/deploy_hosted_agent.py --promote <候補の版> --invoke "..."
    uv run python hosting/deploy_hosted_agent.py --promote <前の版>   # ロールバックも同じ操作

経路(実装前調査 quickstart-hosted-agent の Python SDK パス):
``AIProjectClient.agents.create_version_from_code`` に zip(ルートに main.py /
requirements.txt / hn_briefing_maf/)+ HostedAgentDefinition を渡す →
provisioning をポーリング → ``update_details`` でエンドポイントを新バージョン
100% に向ける(hosted agent はトラフィック分割不可・常に 1 バージョン 100%)。
quickstart は検証後にバージョンを削除するが、本ポートは **Routine が呼ぶ
常設エージェント**なので残す。

ルーティングの更新はエンドポイント設定のほかの項目(プロトコル・認可方式)を保ち、
セレクタだけを差し替える(``hosting_setup.endpoint_with_version``)。``--candidate`` は
エンドポイントが具体版にピン留めされていなければ、まず現在の最新版にピン留めしてから
候補を作る(既定のルーティングは最新版に追従するため、ピンなしで版を作ると Routine が
次に呼ぶ版が変わる)。候補の試験は ``create_session(version_indicator=version_ref)`` で
作った候補専用セッションに ``agent_session_id`` を付けて呼ぶ。既存のセッションは作成時の版に
束縛され、セレクタを変えても移らない(公式。2026-10-06 のライブでは停止後・アイドル明けの再開も
作成時の版だった。foundry-probes probe 10〈2026-09-30〉の「休止明けは現行ルーティング先」とは逆)。
どの版が答えたかは応答の ``agent_reference.version``(その時点のセレクタ)ではなく、セッションの
``version_indicator`` かコンテナ側スパンの ``gen_ai.agent.version`` で見る。

azd 代替: `azd ai agent init` → `azd provision` → `azd deploy`(azure.yaml
一式を azd が管理)。既存の共有基盤へ載せる本ラボの流儀では SDK 経路の方が
Bicep + スクリプトの 2 段デプロイ規約に馴染む(README 参照)。

Bicep との関係: エージェント本体/バージョンはデータプレーンのオブジェクトで
ARM では作れない(infra/main.bicep のコメント参照)。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))

from hn_briefing_maf.config import ConfigError, FoundrySettings
from hn_briefing_maf.hosting_setup import (
    create_code_zip,
    endpoint_with_version,
    hosted_agent_definition_kwargs,
    pinned_version,
    stage_hosted_agent_dir,
)

POLL_INTERVAL_SECONDS = 10.0


def main() -> None:
    parser = argparse.ArgumentParser(description="hn-briefing hosted agent のデプロイ")
    parser.add_argument("--agent-name", default=None, help="hosted agent 名(既定は設定値)")
    parser.add_argument("--cpu", default="0.5", help="サンドボックス vCPU(0.5/1/2)")
    parser.add_argument("--memory", default="1Gi", help="サンドボックスメモリ(1Gi/2Gi/4Gi)")
    parser.add_argument("--invoke", default=None, help="デプロイ後にこのプロンプトで 1 回呼ぶ")
    parser.add_argument("--timeout", type=float, default=600.0, help="provisioning 待ち上限秒")
    parser.add_argument(
        "--dry-run", action="store_true", help="zip 内容と定義を表示するだけ(送信しない)"
    )
    release = parser.add_mutually_exclusive_group()
    release.add_argument(
        "--candidate",
        action="store_true",
        help="本番のルーティングを変えずに候補版を作る(--invoke は候補専用セッションで呼ぶ)",
    )
    release.add_argument(
        "--promote",
        metavar="VERSION",
        default=None,
        help="作成済みの版へ 100%% を切り替える(デプロイしない。ロールバックにも使う)",
    )
    args = parser.parse_args()

    try:
        settings = FoundrySettings.from_env()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    if not settings.project_endpoint:
        print(
            "error: FOUNDRY_PROJECT_ENDPOINT が未設定(hosted agent のデプロイは"
            "プロジェクトエンドポイント+Entra ID が必要。labs/maf-ports/.env を確認)",
            file=sys.stderr,
        )
        sys.exit(2)
    agent_name = args.agent_name or settings.agent_name
    if args.promote:
        if args.dry_run:
            print(json.dumps({"agent_name": agent_name, "promote": args.promote}, indent=2))
            return
        _promote(settings, agent_name, args.promote, args.invoke)
        return
    definition_kwargs = hosted_agent_definition_kwargs(
        project_endpoint=settings.project_endpoint,
        model=settings.model,
        cpu=args.cpu,
        memory=args.memory,
    )

    with tempfile.TemporaryDirectory(prefix="hn-briefing-hosted-") as tmp:
        staged = stage_hosted_agent_dir(Path(tmp) / "staged")
        zip_path = create_code_zip(staged, Path(tmp) / f"{agent_name}.zip")
        files = sorted(str(p.relative_to(staged)) for p in staged.rglob("*") if p.is_file())
        print(f"zip: {len(files)} files — {', '.join(files[:6])} ...", file=sys.stderr)

        if args.dry_run:
            release = {"candidate": True} if args.candidate else {}
            print(json.dumps({"agent_name": agent_name, **release, **definition_kwargs}, indent=2))
            return
        _deploy(settings, agent_name, definition_kwargs, zip_path, args)


def _project(settings):
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return credential, AIProjectClient(endpoint=settings.project_endpoint, credential=credential)


def _current_endpoint(project, agent_name: str):
    """(エージェント, エンドポイント設定の dict)。エージェントが無ければ (None, None)。"""
    from azure.core.exceptions import ResourceNotFoundError

    try:
        agent = project.agents.get(agent_name=agent_name)
    except ResourceNotFoundError:
        return None, None
    endpoint = agent.agent_endpoint
    return agent, (endpoint.as_dict() if endpoint is not None else None)


def _route(project, agent_name: str, version: str, endpoint: dict | None) -> None:
    """セレクタだけを ``version`` 100% に差し替える(ほかのエンドポイント設定は保つ)。"""
    from azure.ai.projects.models import AgentEndpointConfig

    project.agents.update_details(
        agent_name=agent_name,
        agent_endpoint=AgentEndpointConfig(endpoint_with_version(endpoint, version)),
    )
    print(f"routed 100% -> version {version}", file=sys.stderr)


def _wait_active(project, agent_name: str, version: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        details = project.agents.get_version(agent_name=agent_name, agent_version=version)
        status = details["status"]
        print(f"  status={status}", file=sys.stderr)
        if status == "active":
            return
        if status == "failed":
            raise RuntimeError(f"provisioning failed: {dict(details)}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"provisioning timeout({timeout:.0f}s)")
        time.sleep(POLL_INTERVAL_SECONDS)


def _invoke(project, agent_name: str, text: str, *, pinned_to: str | None = None) -> None:
    """1 回呼ぶ。``pinned_to`` を渡すとその版に固定した新しいセッションで呼ぶ(候補の試験)。"""
    extra_body = None
    if pinned_to is not None:
        from azure.ai.projects.models import VersionRefIndicator

        session = project.agents.create_session(
            agent_name=agent_name,
            version_indicator=VersionRefIndicator(agent_version=pinned_to),
        )
        extra_body = {"agent_session_id": session.agent_session_id}
        print(
            f"candidate session {session.agent_session_id} (version {pinned_to})",
            file=sys.stderr,
        )
    with project.get_openai_client(agent_name=agent_name) as openai_client:
        response = openai_client.responses.create(input=text, extra_body=extra_body)
    if response.status != "completed":
        raise RuntimeError(f"invoke did not complete: status={response.status}")
    print(response.output_text)


def _deploy(settings, agent_name: str, definition_kwargs: dict, zip_path: Path, args) -> None:
    from azure.ai.projects.models import (
        CodeConfiguration,
        CodeDependencyResolution,
        HostedAgentDefinition,
        ProtocolVersionRecord,
    )

    definition = HostedAgentDefinition(
        cpu=definition_kwargs["cpu"],
        memory=definition_kwargs["memory"],
        code_configuration=CodeConfiguration(
            runtime=definition_kwargs["runtime"],
            entry_point=definition_kwargs["entry_point"],
            dependency_resolution=CodeDependencyResolution.REMOTE_BUILD,
        ),
        environment_variables=definition_kwargs["environment_variables"],
        protocol_versions=[
            ProtocolVersionRecord(protocol=protocol, version=version)
            for protocol, version in definition_kwargs["protocols"]
        ],
    )

    credential, project = _project(settings)
    with credential, project, zip_path.open("rb") as code_stream:
        agent, endpoint = _current_endpoint(project, agent_name)
        if args.candidate:
            if agent is None:
                raise SystemExit(
                    f"error: {agent_name} がまだ無い(本番が無いので候補にできない)。"
                    "初回は --candidate なしでデプロイする"
                )
            production = pinned_version(endpoint)
            if production is None:
                # 既定は最新版に追従 → 候補を作った瞬間に本番が変わる。先に今の最新版へ固定する
                production = str(agent.versions.latest.version)
                _route(project, agent_name, production, endpoint)
                agent, endpoint = _current_endpoint(project, agent_name)
            print(f"production pinned to version {production}", file=sys.stderr)

        created = project.agents.create_version_from_code(
            agent_name=agent_name,
            description=(
                "Always-on HN briefing agent (MAF port of always_on_hn_briefing_agent)."
            ),
            definition=definition,
            code=code_stream,
        )
        print(f"created version {created.version} — provisioning...", file=sys.stderr)
        _wait_active(project, agent_name, created.version, args.timeout)

        if args.candidate and str(created.version) == production:
            # 2026-10-06 ライブ: zip と定義が本番と同じだと、サービスは新しい版を作らず既存の版を返す
            raise SystemExit(
                f"error: 本番(version {production})と同じ内容なので新しい版は作られなかった。"
                "コードか定義(--cpu / --memory 等)を変えてから候補を作る"
            )
        if args.candidate:
            # 本番が動いていないことを確かめ、候補は候補専用セッションで試す
            _, after = _current_endpoint(project, agent_name)
            if pinned_version(after) != production:
                raise RuntimeError(
                    f"production selector changed while deploying: {after} — reconcile first"
                )
            if args.invoke:
                _invoke(project, agent_name, args.invoke, pinned_to=str(created.version))
            print(
                f"candidate version {created.version} is active; production stays on "
                f"{production}. promote: --promote {created.version}",
                file=sys.stderr,
            )
            return

        # 常設運用: エンドポイントを新バージョン 100% に向けたまま残す
        # (hosted agent は 1 バージョン 100% のみ・分割不可)
        _route(project, agent_name, str(created.version), endpoint)
        print(f"agent endpoint: {project.agents.get(agent_name=agent_name).agent_endpoint}")
        if args.invoke:
            _invoke(project, agent_name, args.invoke)


def _promote(settings, agent_name: str, version: str, invoke: str | None) -> None:
    """作成済みの版へ切り替える(ロールバックも同じ)。新しいセッションで応答を確かめる。"""
    credential, project = _project(settings)
    with credential, project:
        agent, endpoint = _current_endpoint(project, agent_name)
        if agent is None:
            raise SystemExit(f"error: {agent_name} が見つからない")
        status = project.agents.get_version(agent_name=agent_name, agent_version=version)[
            "status"
        ]
        if status != "active":
            raise SystemExit(f"error: version {version} is {status}(active の版だけ切り替える)")
        print(f"production was {pinned_version(endpoint) or 'latest(未ピン)'}", file=sys.stderr)
        _route(project, agent_name, version, endpoint)
        if invoke:
            _invoke(project, agent_name, invoke)


if __name__ == "__main__":
    main()
