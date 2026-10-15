"""リトリーバのオフラインテスト。

PORTING.md §4 に従い、azure-search-documents への実接続はライブスモークに
限定し、ここでは protocol(SupportsVectorSearch / MAF の
SupportsGetEmbeddings)への fake 注入で AzureSearchRetriever のマッピング
ロジックを検証する。埋め込みは 2026-10-06 に MAF の OpenAIEmbeddingClient に
置き換えたため、その配線(送信先・送信 JSON・応答の復元)も HTTP 層だけを
差し替えたモック(httpx2.MockTransport)で固定する。
"""

import json
from collections.abc import Sequence
from typing import Any

import httpx2
from agent_framework import Embedding, GeneratedEmbeddings, SupportsGetEmbeddings

from corrective_rag_maf.config import CorrectiveRagSettings
from corrective_rag_maf.retrieval import (
    DEFAULT_TOP_K,
    AzureSearchRetriever,
    build_embedding_client,
)


class FakeEmbeddingClient:
    """MAF の SupportsGetEmbeddings を満たす scripted fake。"""

    def __init__(self) -> None:
        self.additional_properties: dict[str, Any] = {}
        self.calls: list[list[str]] = []

    async def get_embeddings(
        self, values: Sequence[str], *, options: Any = None
    ) -> GeneratedEmbeddings[list[float], Any]:
        self.calls.append(list(values))
        return GeneratedEmbeddings([Embedding(vector=[0.1, 0.2, 0.3]) for _ in values])


class FakeSearcher:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[list[float], int]] = []

    async def search(self, vector: list[float], top: int) -> list[dict[str, Any]]:
        self.calls.append((vector, top))
        return self.rows


async def test_retriever_embeds_question_and_maps_rows() -> None:
    searcher = FakeSearcher(
        [
            {
                "content": "Free tier: 3 indexes, 50MB storage.",
                "source": "azure-ai-search-vector-tiers.md",
                "title": "Azure AI Search",
                "@search.score": 0.83,
            },
            {"content": "chunk without metadata"},
        ]
    )
    embedder = FakeEmbeddingClient()
    retriever = AzureSearchRetriever(searcher, embedder)

    docs = await retriever.retrieve("What are the free tier limits?")

    # 質問 1 件を 1 回の get_embeddings で埋め込む
    assert embedder.calls == [["What are the free tier limits?"]]
    assert searcher.calls == [([0.1, 0.2, 0.3], DEFAULT_TOP_K)]

    assert docs[0].content == "Free tier: 3 indexes, 50MB storage."
    assert docs[0].source == "azure-ai-search-vector-tiers.md"
    assert docs[0].title == "Azure AI Search"
    assert docs[0].score == 0.83
    # メタデータ欠落は既定値に落ちる(元 langchain Document の metadata.get 相当)
    assert docs[1].source == "Unknown"
    assert docs[1].title == ""
    assert docs[1].score is None


async def test_retriever_respects_top_k_and_clamps_to_one() -> None:
    searcher = FakeSearcher([])
    retriever = AzureSearchRetriever(searcher, FakeEmbeddingClient(), top_k=7)
    await retriever.retrieve("q")
    assert searcher.calls[0][1] == 7

    clamped = AzureSearchRetriever(FakeSearcher([]), FakeEmbeddingClient(), top_k=0)
    assert clamped._top_k == 1  # 内部値の下限クランプ確認


async def test_retriever_returns_empty_for_no_rows() -> None:
    retriever = AzureSearchRetriever(FakeSearcher([]), FakeEmbeddingClient())
    assert await retriever.retrieve("q") == []


def make_settings() -> CorrectiveRagSettings:
    return CorrectiveRagSettings(
        openai_v1_endpoint="https://example.openai.azure.com/openai/v1",
        model="gpt-5.4-mini",
        api_key="dummy-key",
        embedding_model="text-embedding-3-small",
        search_endpoint="https://example.search.windows.net",
        search_api_key="dummy",
        search_index="corrective-rag",
        app_insights_connection_string=None,
    )


def test_build_embedding_client_uses_same_connection_as_chat() -> None:
    """埋め込みはチャットと同じ OpenAI v1 エンドポイント+API キーで、MAF の
    埋め込みプロトコル(SupportsGetEmbeddings)を満たす。"""
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    client = build_embedding_client(make_settings())

    assert isinstance(client, SupportsGetEmbeddings)
    assert client.model == "text-embedding-3-small"
    # /openai/v1 は OpenAI 互換面なので AsyncAzureOpenAI(パス書き換えあり)ではなく
    # AsyncOpenAI がそのまま使われる(書き換わると /deployments/... で 404 になる)
    assert isinstance(client.client, AsyncOpenAI)
    assert not isinstance(client.client, AsyncAzureOpenAI)
    assert str(client.client.base_url) == "https://example.openai.azure.com/openai/v1/"


async def test_embedding_client_wire_format_through_retriever() -> None:
    """実 OpenAIEmbeddingClient → openai SDK の HTTP 層だけを差し替え、
    POST /openai/v1/embeddings の送信内容と応答ベクトルの復元を固定する。"""
    from openai import AsyncOpenAI

    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.5, -0.25, 1.0]}],
                "usage": {"prompt_tokens": 7, "total_tokens": 7},
            },
        )

    settings = make_settings()
    client = build_embedding_client(settings)
    client.client = AsyncOpenAI(
        base_url=settings.openai_v1_endpoint,
        api_key=settings.api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    searcher = FakeSearcher([{"content": "c", "source": "s.md", "title": "t"}])

    docs = await AzureSearchRetriever(searcher, client).retrieve("Free tier limits?")

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://example.openai.azure.com/openai/v1/embeddings"
    assert request.headers["authorization"] == "Bearer dummy-key"
    body = json.loads(request.content)
    assert body["model"] == "text-embedding-3-small"
    assert body["input"] == ["Free tier limits?"]
    # 応答のベクトルがそのまま AI Search のベクトルクエリに渡る
    assert searcher.calls == [([0.5, -0.25, 1.0], DEFAULT_TOP_K)]
    assert docs[0].source == "s.md"


async def test_embedding_call_emits_maf_otel_span() -> None:
    """埋め込み呼び出しが MAF の OTel 計装に乗る(``embeddings <model>`` スパン+
    入力トークン数)。旧実装(openai SDK 直呼び)ではスパンが出なかった点の
    回帰検知。グローバル TracerProvider はこのテストだけが設定する。"""
    from openai import AsyncOpenAI
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    settings = make_settings()
    client = build_embedding_client(settings)
    client.client = AsyncOpenAI(
        base_url=settings.openai_v1_endpoint,
        api_key=settings.api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )

    await client.get_embeddings(["q"])

    spans = [s for s in exporter.get_finished_spans() if s.name.startswith("embeddings")]
    assert [s.name for s in spans] == ["embeddings text-embedding-3-small"]
    assert spans[0].attributes["gen_ai.operation.name"] == "embeddings"
    assert spans[0].attributes["gen_ai.usage.input_tokens"] == 5
