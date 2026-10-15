"""デプロイスクリプトの本番リリース手順(2026-10-06 追加)をフェイクの SDK で固定する。

公式(manage-hosted-agent「Release a version without changing production」):
本番を具体版にピン留め → 候補を作成 → 候補に固定したセッションで試す → セレクタを切り替える。
``hosting/deploy_hosted_agent.py`` の分岐(ピン留めが要るか・候補で本番を動かさないか・
切り替えでほかの設定を保つか)を、``AIProjectClient`` の代わりのフェイクで確かめる。
SDK の型(``AgentEndpointConfig`` / ``VersionRefIndicator``)は本物を使い、
フェイクが受け取るメソッドのキーワードは実 SDK(azure-ai-projects 2.7)のシグネチャと突き合わせる。
"""

from __future__ import annotations

import importlib.util
import inspect
from argparse import Namespace
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("azure.ai.projects")

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentEndpointConfig
from azure.ai.projects.operations import AgentsOperations
from azure.core.exceptions import ResourceNotFoundError

from hn_briefing_maf.hosting_setup import fixed_version_selector, pinned_version

PORT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = PORT_ROOT / "hosting" / "deploy_hosted_agent.py"
AGENT = "hn-briefing-agent"


def load_deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_hosted_agent", DEPLOY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeAgents:
    def __init__(self, *, exists: bool, endpoint: dict | None, versions: dict[str, str]) -> None:
        self.exists = exists
        self.endpoint = endpoint
        self.versions = dict(versions)  # version -> status
        self.routed: list[str] = []
        self.sessions: list[str] = []
        self.same_content_as: str | None = None

    def get(self, *, agent_name: str):
        if not self.exists:
            raise ResourceNotFoundError("not found")
        latest = max(self.versions, key=int)
        return SimpleNamespace(
            agent_endpoint=AgentEndpointConfig(self.endpoint) if self.endpoint else None,
            versions=SimpleNamespace(latest=SimpleNamespace(version=latest)),
        )

    def get_version(self, *, agent_name: str, agent_version: str):
        return {"status": self.versions.get(str(agent_version), "missing")}

    def create_version_from_code(self, *, agent_name, definition, code, description):
        if self.same_content_as is not None:
            # 2026-10-06 ライブ: 内容が同じなら新しい版を作らず既存の版を返す
            return SimpleNamespace(version=self.same_content_as)
        version = str(max((int(v) for v in self.versions), default=0) + 1)
        self.versions[version] = "active"
        self.exists = True
        return SimpleNamespace(version=version)

    def update_details(self, *, agent_name: str, agent_endpoint: AgentEndpointConfig):
        self.endpoint = agent_endpoint.as_dict()
        self.routed.append(pinned_version(self.endpoint))

    def create_session(self, *, agent_name: str, version_indicator):
        indicator = version_indicator.as_dict()
        assert indicator["type"] == "version_ref"
        session_id = f"session-v{indicator['agent_version']}"
        self.sessions.append(session_id)
        return SimpleNamespace(agent_session_id=session_id)


class FakeProject:
    def __init__(self, agents: FakeAgents) -> None:
        self.agents = agents
        self.invocations: list[dict[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_openai_client(self, *, agent_name: str):
        invocations = self.invocations

        def create(*, input, extra_body):
            invocations.append({"input": input, "extra_body": extra_body})
            return SimpleNamespace(status="completed", output_text="brief")

        return nullcontext(SimpleNamespace(responses=SimpleNamespace(create=create)))


@pytest.fixture
def deploy(monkeypatch):
    module = load_deploy_module()
    monkeypatch.setattr(module, "POLL_INTERVAL_SECONDS", 0)
    return module


def run_deploy(module, monkeypatch, project: FakeProject, tmp_path: Path, **flags) -> None:
    monkeypatch.setattr(module, "_project", lambda settings: (nullcontext(), project))
    zip_path = tmp_path / "agent.zip"
    zip_path.write_bytes(b"zip")
    args = Namespace(**{"candidate": False, "invoke": None, "timeout": 5.0, **flags})
    kwargs = {
        "cpu": "0.5",
        "memory": "1Gi",
        "runtime": "python_3_13",
        "entry_point": ["python", "main.py"],
        "environment_variables": {},
        "protocols": [("responses", "2.0.0")],
    }
    module._deploy(SimpleNamespace(project_endpoint="https://x"), AGENT, kwargs, zip_path, args)


def test_sdk_signatures_match_what_the_script_calls() -> None:
    """フェイクに合わせたキーワードが実 SDK にあること(SDK の改名をオフラインで検知する)。"""
    expected = {
        "get": {"agent_name"},
        "get_version": {"agent_name", "agent_version"},
        "update_details": {"agent_name", "agent_endpoint"},
        "create_session": {"agent_name", "version_indicator"},
        "create_version_from_code": {"agent_name", "definition", "code", "description"},
    }
    for name, params in expected.items():
        assert params <= set(inspect.signature(getattr(AgentsOperations, name)).parameters), name
    assert "agent_name" in inspect.signature(AIProjectClient.get_openai_client).parameters


def test_candidate_pins_latest_production_first_and_tests_in_a_pinned_session(
    deploy, monkeypatch, tmp_path
) -> None:
    # セレクタ未設定(既定 = 最新版に追従)で v1 だけがある本番
    agents = FakeAgents(exists=True, endpoint=None, versions={"1": "active"})
    project = FakeProject(agents)

    run_deploy(deploy, monkeypatch, project, tmp_path, candidate=True, invoke="brief please")

    assert agents.routed == ["1"]  # 候補を作る前に v1 へピン留め。候補へは切り替えない
    assert pinned_version(agents.endpoint) == "1"
    assert agents.versions["2"] == "active"
    assert agents.sessions == ["session-v2"]
    assert project.invocations == [
        {"input": "brief please", "extra_body": {"agent_session_id": "session-v2"}}
    ]


def test_candidate_leaves_an_already_pinned_production_untouched(
    deploy, monkeypatch, tmp_path
) -> None:
    endpoint = {
        "version_selector": fixed_version_selector("1"),
        "protocol_configuration": {"responses": {}},
    }
    agents = FakeAgents(exists=True, endpoint=endpoint, versions={"1": "active", "2": "active"})

    run_deploy(deploy, monkeypatch, FakeProject(agents), tmp_path, candidate=True)

    assert agents.routed == []
    assert pinned_version(agents.endpoint) == "1"
    assert "3" in agents.versions


def test_candidate_with_unchanged_content_stops_without_testing(
    deploy, monkeypatch, tmp_path
) -> None:
    """同じ zip・定義の再デプロイはサービスが既存の版を返す(2026-10-06 ライブで確認)。
    候補が本番と同じ版なら、候補として試さずに止める。"""
    endpoint = {"version_selector": fixed_version_selector("1")}
    agents = FakeAgents(exists=True, endpoint=endpoint, versions={"1": "active"})
    agents.same_content_as = "1"
    project = FakeProject(agents)

    with pytest.raises(SystemExit):
        run_deploy(deploy, monkeypatch, project, tmp_path, candidate=True, invoke="hi")

    assert agents.sessions == [] and project.invocations == []
    assert agents.routed == []


def test_candidate_requires_an_existing_production(deploy, monkeypatch, tmp_path) -> None:
    agents = FakeAgents(exists=False, endpoint=None, versions={})
    with pytest.raises(SystemExit):
        run_deploy(deploy, monkeypatch, FakeProject(agents), tmp_path, candidate=True)
    assert agents.versions == {}  # 何も作らない


def test_default_deploy_routes_to_the_new_version_and_keeps_other_settings(
    deploy, monkeypatch, tmp_path
) -> None:
    endpoint = {
        "version_selector": fixed_version_selector("1"),
        "protocol_configuration": {"responses": {}},
        "authorization_schemes": [{"type": "Entra"}],
    }
    agents = FakeAgents(exists=True, endpoint=endpoint, versions={"1": "active"})
    project = FakeProject(agents)

    run_deploy(deploy, monkeypatch, project, tmp_path, invoke="hi")

    assert agents.routed == ["2"]
    assert agents.endpoint["authorization_schemes"] == [{"type": "Entra"}]
    assert project.invocations == [{"input": "hi", "extra_body": None}]  # 本番経路(版指定なし)


def test_promote_switches_only_to_an_active_version(deploy, monkeypatch) -> None:
    agents = FakeAgents(
        exists=True,
        endpoint={"version_selector": fixed_version_selector("1")},
        versions={"1": "active", "2": "active", "3": "failed"},
    )
    monkeypatch.setattr(deploy, "_project", lambda settings: (nullcontext(), FakeProject(agents)))
    settings = SimpleNamespace(project_endpoint="https://x")

    with pytest.raises(SystemExit):
        deploy._promote(settings, AGENT, "3", None)
    assert agents.routed == []

    deploy._promote(settings, AGENT, "2", None)
    deploy._promote(settings, AGENT, "1", None)  # ロールバックも同じ操作
    assert agents.routed == ["2", "1"]
