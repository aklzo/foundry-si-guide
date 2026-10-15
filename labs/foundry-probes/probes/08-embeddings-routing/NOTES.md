# 埋め込みのエンドポイントルーティング — 挙動発見メモ(2026-08-04 実測)

環境: text-embedding-3-small v1 / gpt-5.4-mini / japaneast

## 発見(挙動)

- **survey 08 の注記は実測どおり**。埋め込みには明確な非対称性がある:
  - アカウント `https://aif-fprobes.openai.azure.com/openai/v1` → `embeddings.create` **成功**(1536 次元、model 名も正しく返る)
  - プロジェクト `https://aif-fprobes.services.ai.azure.com/api/projects/probes/openai/v1/` → `embeddings.create` **404 NotFoundError**
- 一方 responses/chat は**両エンドポイントで成功**(アカウント経由 responses も OK)。つまり非対称なのは embeddings だけ。
- text-embedding-3-small は自前デプロイ(このラボで追加)すれば 1536 次元で普通に使える。File Search 内蔵の 3-large@256 とは別。

## つまりどころ

- **1 つのクライアント(プロジェクト経由)で chat も embeddings も、と書くと embeddings だけ 404 で落ちる。** RAG を自前実装(埋め込み+chat)するとき、embeddings 呼び出しだけアカウント `openai.azure.com/openai/v1` に向けるルーティング分岐が要る。~~maf-ports/corrective-rag / db-routing-iq は AI Search 側の埋め込みを使ったのでこの罠を踏まなかったが~~(**※2026-10-06 訂正**: Port 4 corrective-rag はクライアント側で**アカウントの `/openai/v1` 経由**で埋め込みを呼んでいた〈2026-10-06 から MAF の `OpenAIEmbeddingClient`〉のでこの罠を踏まなかった。Port 10 db-routing-iq はベクトルを使わない)、「Foundry の埋め込みモデルをプロジェクト経由で直接呼ぶ」構成では踏む。
- エラーが 404 なので「モデル未デプロイ」と誤診しやすい(実際はデプロイ済みでもエンドポイント違いで 404)。切り分けにはアカウント側で叩き直す。

## SI 判断メモ

- プロジェクトエンドポイント単一で全部済ませたい設計は embeddings で破綻する。接続情報を「プロジェクト(agent/responses 用)」と「アカウント(embeddings 用)」の 2 本持つのを標準にする。共有 .env に両方出力する構成(このラボの main.bicep がそうしている)が安全。

## 2026-10-06 追記(最新化チェック・ライブ未検証)

- **agent-framework-foundry 1.14.0 の「Foundry project embeddings」は、この 404 を SDK 側で回避している。**`FoundryEmbeddingClient(project_endpoint=...)` はプロジェクトの OpenAI クライアントを作った後、base_url を `https://<res>.services.ai.azure.com/api/projects/<p>/openai/v1` から `https://<res>.openai.azure.com/openai/v1/`(コード中の表現は "documented resource-scoped OpenAI model URL")へ**書き換えて** embeddings を呼ぶ(installed package の `_embedding_client.py` `_get_openai_model_base_url`。maf-ports の最新化担当がモック HTTP で「導出したアカウント URL を `https://ai.azure.com/.default` スコープのトークンで呼ぶ」ことを確認)。つまり「プロジェクトのエンドポイントで embeddings が通るようになった」のではなく、「プロジェクトの設定だけ渡せば SDK がアカウントへ振り替える」。上の「接続情報 2 本持ち」は、MAF を使う場合は SDK が肩代わりする形になった。
- その際のトークンはプロジェクト用のスコープ `https://ai.azure.com/.default`(`get_openai_client()` の既定)のまま。アカウントの `openai/v1` がこのスコープのトークンを受け付けるかは本 probe で未確認だったので、**観点 D を追加**した(プロジェクトの資格情報+アカウントの base_url)。A と同じく成功すれば MAF 1.14 の方式が成り立つ、失敗すれば A のように `cognitiveservices` スコープのトークンが要る。
- この SDK の実装は本 probe の観察(プロジェクト経由は 404・アカウント経由は成功)と整合する。再実測で見ること: **B が今も 404 か**(プロジェクト経由の embeddings がルーティングされるようになったか — SDK が振り替えるようになった今も、REST を直接叩く実装や他言語 SDK には効く)と D の成否(ai.azure.com スコープのトークンがアカウントの `openai/v1` で実サービスに通るか。モック HTTP では認可までは確かめられない)。期待(未実測): B = 404 のまま、D = 成功。

## 2026-10-06 再実測(ライブ)

環境: japaneast・rg-foundry-probes(aif-fprobes1006)・text-embedding-3-small v1・openai 3.24.0 / azure-ai-projects 2.8.0。

- **B(プロジェクト経由の embeddings)は今も `NotFoundError 404`**(base_url `…/api/projects/probes/openai/v1/`)。A(アカウント)と C(アカウント経由の responses)は成功で、08-04 と同じ。
- **D(プロジェクトの資格情報+アカウントの base_url)は成功**(1536 次元)。`https://ai.azure.com/.default` スコープのトークンがアカウントの `openai/v1` でも通る → agent-framework-foundry 1.14 の `FoundryEmbeddingClient(project_endpoint=...)` の振り替え方式は実サービスで成り立つ。
- まとめ: プロジェクトのエンドポイントは embeddings を提供しない(SDK が振り替えるだけ)。REST を直接叩く実装や、振り替えのない他言語 SDK では今も「アカウントの URL を別に持つ」が要る。トークンのスコープは `ai.azure.com` でもよいので、資格情報は 1 つで足りる。
