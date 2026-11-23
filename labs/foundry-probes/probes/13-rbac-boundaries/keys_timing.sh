#!/usr/bin/env bash
# B2: API キーで届く範囲と、disableLocalAuth=true にしてから古いキーが拒否されるまでの時間(公開側のアカウント)。
# 閉域側のキーの届く範囲は VM 内の `vmprobe.py keys`(13 の probe.sh)。こちらは数時間かかりうる待ちを
# 時間課金のない公開側で行う(閉域側は AI Search Basic などが課金され続けるため)。
#   ./keys_timing.sh reach              # キーでの到達範囲(無効化前)
#   ./keys_timing.sh disable [max_min]  # disableLocalAuth=true → 旧キーが 401 になるまで 1 分おきに確認
# キーはシェル変数にだけ置き、表示・保存しない。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../12-closed-network/lib.sh"
LOG="$HERE/logs/keys-timing.log"
ACCT="${ACCT:-$(az deployment group show -g "$RG" -n p13-public --query properties.outputs.foundryName.value -o tsv)}"
PROJ="https://${ACCT}.services.ai.azure.com/api/projects/pub"
OAI="https://${ACCT}.openai.azure.com/openai/v1"
FEAT='A2AAgents=V1Preview,WorkflowAgents=V1Preview,DraftAgents=V1Preview,VoiceAgents=V1Preview,DigitalWorker=V1Preview,GitHubCopilot=V1Preview,Skills=V1Preview,MicrosoftCopilot=V1Preview,ModelRouterControls=V1Preview'
KEY="$(az cognitiveservices account keys list -g "$RG" -n "$ACCT" --query key1 -o tsv)"

kcall() {  # kcall <label> <method> <url> [body] [extra-header]
  local label="$1" m="$2" u="$3" b="${4:-}" xh="${5:-X-Probe: 1}" o code
  o=$(mktemp)
  if [ -n "$b" ]; then
    code=$(curl -sS -m 60 -o "$o" -w '%{http_code}' -X "$m" "$u" -H "api-key: $KEY" -H "$xh" -H 'Content-Type: application/json' --data "$b" || echo err)
  else
    code=$(curl -sS -m 60 -o "$o" -w '%{http_code}' -X "$m" "$u" -H "api-key: $KEY" -H "$xh" || echo err)
  fi
  echo "[$(ts)] [$label] $m ${u/$PROJ/\{pubproj\}} -> HTTP $code $(head -c 400 "$o" | tr '\n' ' ')" | mask | tee -a "$LOG"
  rm -f "$o"
  LAST="$code"
}

ecall() {  # Entra(az login のユーザー)で同じアカウントを呼ぶ対照
  local tok code o
  tok=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)
  o=$(mktemp)
  code=$(curl -sS -m 60 -o "$o" -w '%{http_code}' -X POST "$OAI/responses" -H "Authorization: Bearer $tok" \
    -H 'Content-Type: application/json' --data '{"model":"gpt-5.4-mini","input":"Reply PONG","store":false}' || echo err)
  echo "[$(ts)] [entra] POST {acct-oai}/responses -> HTTP $code" | tee -a "$LOG"
  rm -f "$o"
}

reach() {
  echo "### [$(ts)] キーでの到達範囲(その時点の disableLocalAuth の設定で)" | tee -a "$LOG"
  local r='{"model":"gpt-5.4-mini","input":"Reply PONG","store":false}'
  kcall "key (a) account /openai/v1/responses" POST "$OAI/responses" "$r"
  kcall "key (b) project /openai/v1/responses" POST "$PROJ/openai/v1/responses" "$r"
  kcall "key (c) project responses + agent_reference" POST "$PROJ/openai/v1/responses" '{"input":"ping","agent_reference":{"type":"agent_reference","name":"a14-opt"}}'
  kcall "key (d) agent endpoint" POST "$PROJ/agents/a14-opt/endpoint/protocols/openai/responses?api-version=v1" '{"input":"ping"}' "Foundry-Features: $FEAT"
  kcall "key (e) list agents" GET "$PROJ/agents?api-version=v1&limit=1"
  kcall "key (f) list memory stores" GET "$PROJ/memory_stores?api-version=v1" "" "Foundry-Features: MemoryStores=V1Preview"
  kcall "key (g) list optimization jobs" GET "$PROJ/agent_optimization_jobs?api-version=v1"
  kcall "key (h) list files (project)" GET "$PROJ/openai/v1/files"
}

disable() {
  local max="${1:-180}"
  local aid; aid=$(az cognitiveservices account show -g "$RG" -n "$ACCT" --query id -o tsv)
  echo "### [$(ts)] disableLocalAuth=true(PATCH)→ 旧キーで account /openai/v1/responses を 1 分おきに最大 ${max} 分" | tee -a "$LOG"
  kcall "before" POST "$OAI/responses" '{"model":"gpt-5.4-mini","input":"Reply PONG","store":false}'
  arm PATCH "https://management.azure.com${aid}?api-version=2026-11-01" '{"properties":{"disableLocalAuth":true}}' | tee -a "$LOG"
  local t0; t0=$(date +%s)
  local n401=0
  for i in $(seq 1 "$max"); do
    kcall "t+$(( ($(date +%s)-t0)/60 ))m" POST "$OAI/responses" '{"model":"gpt-5.4-mini","input":"Reply PONG","store":false}'
    if [ "$LAST" = 401 ] || [ "$LAST" = 403 ]; then n401=$((n401+1)); else n401=0; fi
    [ $((i % 10)) -eq 1 ] && ecall
    if [ "$n401" -ge 3 ]; then
      echo "[$(ts)] 3 回連続で拒否。反映まで約 $(( ($(date +%s)-t0)/60 )) 分" | tee -a "$LOG"
      ecall
      reach
      break
    fi
    sleep 60
  done
}

"${1:?reach|disable}" "${@:2}"
