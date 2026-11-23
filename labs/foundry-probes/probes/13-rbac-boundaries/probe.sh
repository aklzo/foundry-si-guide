#!/usr/bin/env bash
# probe 13: 権限の境界(ユーザー割り当て MI × ロール × スコープ)。12 と同じ RG・同じ VM を使う。
# ロールは GUID で付ける。付けた後は伝播を待つ(403 が続く間は 1 分おきに再試行し、最大 15 分)。
#   ./probe.sh roles-agent   # エージェントスコープの Agent Consumer(閉域: a13-target・a13-share、公開: a13-mem)
#   ./probe.sh b1            # 推論の経路 × ロール(vmprobe rbac)
#   ./probe.sh b2            # API キー(閉域: vmprobe keys / 公開: keys_timing.sh)
#   ./probe.sh b3            # Agent Consumer 2 人の間の共有(vmprobe share)
#   ./probe.sh b4            # 接続の作成・仕様にない名前(vmprobe conn / authz と、操作者の ARM 呼び出し)
#   ./probe.sh roles-b5      # id-fu に Foundry Project Manager @アカウント、id-rt に Foundry Account Owner @アカウントを足す
#   ./probe.sh b5            # ロール割り当ての条件と metrics read(vmprobe roleassign)
#   ./probe.sh b6            # Memory の x-memory-user-id(公開側。vmprobe memory)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P12="$HERE/../12-closed-network"
source "$P12/lib.sh"
LOG="$HERE/logs/roles.log"
export LOGDIR="$HERE/logs"
CFG="${CONFIG:-${SCRATCH:-$P12/.work}/vm-config.json}"

R_AGENT_CONSUMER=eed3b665-ab3a-47b6-8f48-c9382fb1dad6
R_PROJECT_MANAGER=eadc314b-1a2d-4efa-be10-5d325db5065e
R_ACCOUNT_OWNER=e47c6f54-e4a2-4754-9501-8e0985b135e1

pid() { jq -r ".principals.$1" "$CFG"; }

assign() {  # assign <who> <roleGuid> <scope>
  echo "[$(ts)] role assignment create who=$1 role=$2 scope=${3##*/providers/}" | mask | tee -a "$LOG"
  az role assignment create --assignee-object-id "$(pid "$1")" --assignee-principal-type ServicePrincipal \
    --role "$2" --scope "$3" -o json 2>&1 | jq -c '{id: .id, role: .roleDefinitionId, scope: .scope}' 2>/dev/null | mask | tee -a "$LOG" || true
}

roles-agent() {
  local proj pub
  proj=$(jq -r .projectId "$CFG"); pub=$(jq -r .publicProjectId "$CFG")
  "$P12/vmrun.sh" run setup13
  assign ac1 $R_AGENT_CONSUMER "$proj/agents/a13-target"
  assign ac1 $R_AGENT_CONSUMER "$proj/agents/a13-share"
  assign rd  $R_AGENT_CONSUMER "$proj/agents/a13-share"
  assign ac1 $R_AGENT_CONSUMER "$pub/agents/a13-mem"
  assign rd  $R_AGENT_CONSUMER "$pub/agents/a13-mem"
}

roles-b5() {
  local acct; acct=$(jq -r .foundryId "$CFG")
  assign fu $R_PROJECT_MANAGER "$acct"
  assign rt $R_ACCOUNT_OWNER "$acct"
}

b1() { "$P12/vmrun.sh" run rbac; }
b2() { "$P12/vmrun.sh" run keys; "$HERE/keys_timing.sh" reach; }
b3() { "$P12/vmrun.sh" run share; "$P12/vmrun.sh" run share2; "$P12/vmrun.sh" run share3; }
b4() {
  "$P12/vmrun.sh" run conn
  "$P12/vmrun.sh" run authz
  # 操作者(サブスクリプションの所有者)で、仕様にない authType を ARM に投げる
  local proj; proj=$(jq -r .projectId "$CFG")
  {
    echo "### [$(ts)] 操作者で接続の authType を試す"
    for at in AgentOnBehalfOfUser AgentUserImpersonation UserEntraToken; do
      arm PUT "https://management.azure.com${proj}/connections/c13-${at,,}?api-version=2026-11-01" \
        "{\"properties\":{\"category\":\"RemoteTool\",\"target\":\"http://10.40.2.10:8081/mcp\",\"authType\":\"$at\",\"metadata\":{\"type\":\"custom_MCP\"}}}"
      arm GET "https://management.azure.com${proj}/connections/c13-${at,,}?api-version=2026-11-01"
    done
  } 2>&1 | tee -a "$HERE/logs/b4-operator.log"
}
b5() { "$P12/vmrun.sh" run roleassign; }
b6() {
  "$P12/vmrun.sh" run memory write
  echo "[$(ts)] 記憶の抽出を待つ(update_delay=1 秒。抽出は非同期なので 90 秒置く)" | tee -a "$HERE/logs/vm-memory.log"
  sleep 90
  "$P12/vmrun.sh" run memory read
  "$P12/vmrun.sh" run memory2 find      # ac1 の scope の探索と、プロジェクトの経路で ops が user-bob に書く
  sleep 90
  "$P12/vmrun.sh" run memory2 read
  crossuser                             # 実行者(別の ID)が user-bob を読む
}

crossuser() {  # 実行者(az login のユーザー。Foundry User @公開アカウント)で x-memory-user-id: user-bob を付けて読む
  local P T F U B code r
  P=$(jq -r .publicProjectEndpoint "$CFG")
  T=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
  F='A2AAgents=V1Preview,WorkflowAgents=V1Preview,DraftAgents=V1Preview,VoiceAgents=V1Preview,DigitalWorker=V1Preview,GitHubCopilot=V1Preview,Skills=V1Preview,MicrosoftCopilot=V1Preview,ModelRouterControls=V1Preview'
  r=$(mktemp)
  {
    echo "### [$(ts)] B6: 実行者(ops とは別の ID)が x-memory-user-id: user-bob(ops が書いた scope)を付けて読む"
    for route in project agent; do
      for hdr in "x-memory-user-id: user-bob" "X-Probe: none"; do
        if [ "$route" = project ]; then U="$P/openai/v1/responses"; B='{"input":"私の好きな色は? 記憶から答えて。","agent_reference":{"type":"agent_reference","name":"a13-mem"}}'
        else U="$P/agents/a13-mem/endpoint/protocols/openai/responses?api-version=v1"; B='{"input":"私の好きな色は? 記憶から答えて。"}'; fi
        code=$(curl -sS -o "$r" -w '%{http_code}' -H "Authorization: Bearer $T" -H "Foundry-Features: $F" -H "$hdr" -H 'Content-Type: application/json' "$U" --data "$B")
        echo "[$route] [$hdr] HTTP $code text=$(jq -r '[.output[]?|select(.type=="message")|.content[]?.text]|join(" ")' "$r" 2>/dev/null | head -c 300)"
      done
    done
  } 2>&1 | mask | tee -a "$HERE/logs/memory-crossuser.log"
  rm -f "$r"
}

"${1:?roles-agent|b1|b2|b3|b4|roles-b5|b5|b6}"
