#!/usr/bin/env bash
# probe 12〜14 の環境の作成と撤去(RG rg-ignite26-verify の中だけに作る)。
#   ./deploy.sh up        # RG → infra.bicep(閉域)→ ../13-rbac-boundaries/infra.bicep(公開 basic)
#   ./deploy.sh caphost   # capability host をアカウント → プロジェクトの順に az rest(curl)で作り、結果を記録
#   ./deploy.sh vmconfig  # VM に置く config.json(エンドポイントと MI の client_id。資格情報なし)を作る
#   ./deploy.sh down      # capability host → アカウント削除 → purge → RG 削除 → az group exists=false を確認
# 時間課金(AI Search Basic・PE 4 本・VM)は約 ¥29.65 / 時。終わったらすぐ down する(COST.md)。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib.sh"
LOG="${LOGDIR:-$HERE/logs}/deploy.log"  # LOGDIR で別 probe のログ置き場に変えられる(既定は従来どおり)
OUTS_FILE="${OUTS_FILE:-$HERE/infra.outputs.json}"
SP="${SCRATCH:-$HERE/.work}"  # 鍵と vm-config.json の置き場(.gitignore 済み)
API=2026-11-01

outs() { az deployment group show -g "$RG" -n p12-infra --query properties.outputs -o json; }

up() {
  local uoid; uoid=$(az ad signed-in-user show --query id -o tsv)
  [ -f "$SP/keys/vm_ed25519.pub" ] || { mkdir -p "$SP/keys"; ssh-keygen -q -t ed25519 -N '' -C probe-vm -f "$SP/keys/vm_ed25519"; }
  echo "[$(ts)] az group create $RG" | tee -a "$LOG"
  az group create -n "$RG" -l "$LOC" -o none
  echo "[$(ts)] deployment p12-infra" | tee -a "$LOG"
  az deployment group create -g "$RG" -n p12-infra -f "$HERE/infra.bicep" \
    -p userObjectId="$uoid" sshPublicKey="$(cat "$SP/keys/vm_ed25519.pub")" -o none
  local base; base=$(outs | jq -r .baseName.value)
  echo "[$(ts)] deployment p13-public (baseName=$base)${SKIP_PUBLIC:+ — SKIP_PUBLIC のため省略}" | tee -a "$LOG"
  [ -n "${SKIP_PUBLIC:-}" ] || az deployment group create -g "$RG" -n p13-public -f "$HERE/../13-rbac-boundaries/infra.bicep" \
    -p userObjectId="$uoid" baseName="$base" -o none
  outs | mask > "$OUTS_FILE"
}

wait_caphost() {  # wait_caphost <url> — provisioningState が終わるまで 30 秒おきに GET
  local url="$1" st nf=0
  for _ in $(seq 1 80); do
    st=$(az rest --method get --url "$url" --query properties.provisioningState -o tsv 2>/dev/null || echo "GET-failed")
    echo "[$(ts)]   provisioningState=$st" | tee -a "$LOG"
    case "$st" in Succeeded|Failed|Canceled) break ;; GET-failed) nf=$((nf+1)); [ "$nf" -ge 3 ] && break ;; esac
    sleep 30
  done
  arm GET "$url" | tee -a "$LOG"
}

caphost() {
  local acct; acct=$(outs | jq -r .foundryId.value)
  local subnet; subnet=$(outs | jq -r .vnetId.value)/subnets/snet-agent
  local a="https://management.azure.com${acct}/capabilityHosts/caphost-acct?api-version=$API"
  local p="https://management.azure.com${acct}/projects/proj/capabilityHosts/caphost-proj?api-version=$API"
  echo "### [$(ts)] account capability host" | tee -a "$LOG"
  # 1 回目(2026-11-22)は customerSubnet なしで 400「The customerSubnet property must match the subnet
  # recorded on the CapabilityHost parent resource.」→ networkInjections と同じサブネットを入れる
  arm PUT "$a" "{\"properties\":{\"capabilityHostKind\":\"Agents\",\"customerSubnet\":\"$subnet\"}}" | tee -a "$LOG"
  wait_caphost "$a"
  echo "### [$(ts)] project capability host" | tee -a "$LOG"
  arm PUT "$p" '{"properties":{"capabilityHostKind":"Agents","vectorStoreConnections":["conn-search"],"storageConnections":["conn-storage"],"threadStorageConnections":["conn-cosmos"]}}' | tee -a "$LOG"
  wait_caphost "$p"
}

vmconfig() {
  local o; o=$(outs)
  local pub; pub=$(az deployment group show -g "$RG" -n p13-public --query properties.outputs -o json 2>/dev/null || echo '{}')
  local base; base=$(jq -r .baseName.value <<<"$o")
  jq -n --argjson o "$o" --argjson pub "$pub" --arg base "$base" '{
      projectEndpoint: $o.projectEndpoint.value, openaiV1Endpoint: $o.openaiV1Endpoint.value,
      model: $o.modelDeploymentName.value, vmPrivateIp: $o.vmPrivateIp.value,
      foundryId: $o.foundryId.value, projectId: $o.projectId.value,
      publicProjectEndpoint: ($pub.projectEndpoint.value // "#"), publicOpenaiV1Endpoint: $pub.openaiV1Endpoint.value,
      publicFoundryId: $pub.foundryId.value, publicProjectId: $pub.projectId.value,
      depHosts: [("cos-" + $base + ".documents.azure.com"), ("srch-" + $base + ".search.windows.net"), ("st" + $base + ".blob.core.windows.net")],
      ids: ($o.identities.value | map({key: (.name | sub("^id-"; "")), value: .clientId}) | from_entries),
      principals: ($o.identities.value | map({key: (.name | sub("^id-"; "")), value: .principalId}) | from_entries)
    }' > "$SP/vm-config.json"
  echo "wrote $SP/vm-config.json"
}

down() {
  local acct pubacct
  acct=$(outs | jq -r .foundryId.value 2>/dev/null || true)
  pubacct=$(az deployment group show -g "$RG" -n p13-public --query properties.outputs.foundryId.value -o tsv 2>/dev/null || true)
  echo "### [$(ts)] down: capability host → アカウント → purge → RG" | tee -a "$LOG"
  if [ -n "$acct" ]; then
    arm DELETE "https://management.azure.com${acct}/projects/proj/capabilityHosts/caphost-proj?api-version=$API" | tee -a "$LOG" || true
    sleep 60
    arm DELETE "https://management.azure.com${acct}/capabilityHosts/caphost-acct?api-version=$API" | tee -a "$LOG" || true
    sleep 60
  fi
  # 2026-11-22: プロジェクトが残っているとアカウントの削除は CannotDeleteResource。先にプロジェクトを消す。
  # また RG 削除はアカウントが論理削除のままだと委任サブネットの legionservicelink で VNet を消せず
  # ResourceGroupDeletionBlocked になるので、purge の完了(閉域側は約 22 分かかった)を待ってから RG を消す。
  [ -n "$acct" ] && arm DELETE "https://management.azure.com${acct}/projects/proj?api-version=$API" | tee -a "$LOG" || true
  [ -n "$pubacct" ] && arm DELETE "https://management.azure.com${pubacct}/projects/pub?api-version=$API" | tee -a "$LOG" || true
  sleep 60
  for id in $acct $pubacct; do
    local name; name=$(basename "$id")
    echo "[$(ts)] delete + purge $name" | tee -a "$LOG"
    az cognitiveservices account delete -g "$RG" -n "$name" 2>&1 | mask | tee -a "$LOG" || true
    az cognitiveservices account purge -g "$RG" -n "$name" -l "$LOC" 2>&1 | mask | tee -a "$LOG" || true
  done
  echo "[$(ts)] az group delete -n $RG --yes" | tee -a "$LOG"
  az group delete -n "$RG" --yes 2>&1 | mask | tee -a "$LOG" || true
  for _ in $(seq 1 60); do
    local e; e=$(az group exists -n "$RG")
    echo "[$(ts)] az group exists -n $RG -> $e" | tee -a "$LOG"
    [ "$e" = false ] && break
    sleep 30
  done
}

"${1:?up|caphost|vmconfig|down}"
