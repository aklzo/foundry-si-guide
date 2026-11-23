#!/usr/bin/env bash
# probe 12: 閉域(PNA Disabled + BYO VNet 注入 + standard setup)の動作確認。
# 前提: deploy.sh up 済み(infra.bicep → capability host)。テストは VM 内から(vmrun.sh)。
#   ./probe.sh outside     # A2: この端末(VNet の外)から閉域のエンドポイントを呼ぶ
#   ./probe.sh inside      # A2〜A4: VM 内から(dns / reach / agent / filesearch / codeinterp / websearch / openapi / mcp)
#   ./probe.sh harness     # A5: Copilot harness の prompt agent
# 結果は logs/ に残る(サブスクリプション ID・テナント ID は伏せる)。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib.sh"
OUTS="$HERE/infra.outputs.json"  # deploy.sh が保存する Bicep の出力(ID は含むが資格情報は含まない)

outside() {
  local log="$HERE/logs/outside.log"
  local proj acct
  proj=$(jq -r '.projectEndpoint.value' "$OUTS")
  acct=$(jq -r '.foundryName.value' "$OUTS")
  {
    echo "### [$(ts)] A2: VNet の外(WSL)から呼ぶ。呼び出し元ユーザーには閉域アカウントの Foundry User を付けてある"
    for h in "$acct.services.ai.azure.com" "$acct.openai.azure.com" "$acct.cognitiveservices.azure.com"; do
      echo "[dns] $h -> $(getent ahosts "$h" | awk '{print $1}' | sort -u | tr '\n' ' ')"
      echo "[alias] $(python3 -c 'import socket,sys; print(socket.gethostbyname_ex(sys.argv[1]))' "$h" 2>&1)"
    done
    local tai tcog
    tai=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
    tcog=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)
    for spec in \
      "GET|$proj/agents?api-version=v1|$tai" \
      "POST|$proj/openai/v1/responses|$tai" \
      "POST|https://$acct.openai.azure.com/openai/v1/responses|$tcog" \
      "POST|https://$acct.cognitiveservices.azure.com/openai/v1/responses|$tcog"; do
      IFS='|' read -r m u t <<<"$spec"
      local body=''
      [ "$m" = POST ] && body='{"model":"gpt-5.4-mini","input":"Say OK.","store":false}'
      local o; o=$(mktemp)
      local code
      if [ -n "$body" ]; then
        code=$(curl -sS -m 30 -o "$o" -w '%{http_code}' -X "$m" "$u" -H "Authorization: Bearer $t" -H 'Content-Type: application/json' --data "$body" || echo "curl-error")
      else
        code=$(curl -sS -m 30 -o "$o" -w '%{http_code}' -X "$m" "$u" -H "Authorization: Bearer $t" || echo "curl-error")
      fi
      echo "[outside] $m $u -> HTTP $code $(head -c 600 "$o")"
      rm -f "$o"
    done
  } 2>&1 | mask | tee -a "$log"
}

inside() {
  for c in dns reach agent filesearch codeinterp websearch openapi mcp; do
    "$HERE/vmrun.sh" run "$c"
  done
  "$HERE/vmrun.sh" run serverlog 40
}

harness() {
  "$HERE/vmrun.sh" run harness
  "$HERE/vmrun.sh" run serverlog 10
}

"${1:?outside|inside|harness}"
