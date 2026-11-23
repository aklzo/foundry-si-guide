#!/usr/bin/env bash
# probe 15: エージェントの外向き通信の経路と、エージェントサブネット(snet-agent)の NSG / UDR の効き方。
# 環境は 12 の deploy.sh で作る(SKIP_PUBLIC=1 で 13 の公開プロジェクトを省く。手順は NOTES.md)。
#   ./run15.sh push                  # vm/egressprobe.py を VM に置く(12 の vmrun.sh push の後)
#   ./run15.sh run <cmd> <phase> [args]  # VM 内で egressprobe.py <cmd> <phase>(要約を logs/vm-<cmd>.log に追記)
#   ./run15.sh nsg <ip>...           # NSG(priority 100 で指定 IP への送信を拒否)を作って snet-agent に関連付け
#   ./run15.sh nsg-off               # 関連付けを外して NSG を削除
#   ./run15.sh rt <prefix>...        # ルートテーブル(指定プレフィックス → 次ホップ None)を作って snet-agent に関連付け
#   ./run15.sh rt-off                # 関連付けを外してルートテーブルを削除
#   ./run15.sh subnet                # snet-agent の NSG・ルートテーブル・委任の状態
# ログはすべて logs/(サブスクリプション ID・テナント ID は伏せる)。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P12="$HERE/../12-closed-network"
source "$P12/lib.sh"
export LOGDIR="${LOGDIR:-$HERE/logs}"  # 追試(harness)は LOGDIR=…/logs/harness で別フォルダに書く(既定は従来どおり)
VM="${VM:-$(az vm list -g "$RG" --query '[0].name' -o tsv)}"
VNET="$(az network vnet list -g "$RG" --query '[0].name' -o tsv)"
NETLOG="$LOGDIR/net.log"
NSG=nsg-p15-agent
RT=rt-p15-agent

rc() {
  az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "$1" -o json | jq -r '.value[0].message'
}

subnet() {
  az network vnet subnet show -g "$RG" --vnet-name "$VNET" -n snet-agent \
    --query '{nsg:networkSecurityGroup.id, routeTable:routeTable.id, defaultOutboundAccess:defaultOutboundAccess, delegations:delegations[].serviceName, sal:serviceAssociationLinks[].linkedResourceType, state:provisioningState}' -o json \
    | mask | tee -a "$NETLOG"
}

case "${1:-}" in
  push)
    rc "echo $(base64 -w0 "$HERE/vm/egressprobe.py") | base64 -d > /opt/probe/egressprobe.py; python3 -m py_compile /opt/probe/egressprobe.py && echo pushed" \
      | mask | tee -a "$LOGDIR/vm-push.log"
    ;;
  run)
    cmd="$2"; ph="$3"; shift 3; log="$LOGDIR/vm-${cmd}.log"
    echo "### [$(ts)] egressprobe.py $cmd $ph $*" | mask | tee -a "$log"
    rc "timeout 1500 python3 /opt/probe/egressprobe.py $cmd $ph $* 2>&1 | tail -c 4000" | mask | tee -a "$log"
    echo "### [$(ts)] done" | tee -a "$log"
    ;;
  nsg)
    shift
    echo "### [$(ts)] NSG $NSG: deny outbound to $* (priority 100) → snet-agent" | tee -a "$NETLOG"
    az network nsg create -g "$RG" -n "$NSG" -l "$LOC" -o none 2>&1 | mask | tee -a "$NETLOG"
    az network nsg rule create -g "$RG" --nsg-name "$NSG" -n deny-echo --priority 100 --direction Outbound --access Deny \
      --protocol '*' --source-address-prefixes '*' --source-port-ranges '*' --destination-address-prefixes "$@" \
      --destination-port-ranges '*' --query '{name:name,access:access,direction:direction,priority:priority,dst:destinationAddressPrefixes,state:provisioningState}' -o json \
      2>&1 | mask | tee -a "$NETLOG"
    az network vnet subnet update -g "$RG" --vnet-name "$VNET" -n snet-agent --network-security-group "$NSG" -o none 2>&1 | mask | tee -a "$NETLOG"
    echo "[$(ts)] associated" | tee -a "$NETLOG"
    subnet
    ;;
  nsg-off)
    echo "### [$(ts)] NSG off" | tee -a "$NETLOG"
    az network vnet subnet update -g "$RG" --vnet-name "$VNET" -n snet-agent --remove networkSecurityGroup -o none 2>&1 | mask | tee -a "$NETLOG"
    az network nsg delete -g "$RG" -n "$NSG" 2>&1 | mask | tee -a "$NETLOG"
    echo "[$(ts)] NSG removed" | tee -a "$NETLOG"
    subnet
    ;;
  rt)
    shift
    echo "### [$(ts)] route table $RT: $* → next hop None → snet-agent" | tee -a "$NETLOG"
    az network route-table show -g "$RG" -n "$RT" -o none 2>/dev/null || az network route-table create -g "$RG" -n "$RT" -l "$LOC" -o none 2>&1 | mask | tee -a "$NETLOG"
    for r in $(az network route-table route list -g "$RG" --route-table-name "$RT" --query '[].name' -o tsv); do
      az network route-table route delete -g "$RG" --route-table-name "$RT" -n "$r" 2>&1 | mask | tee -a "$NETLOG"
    done
    i=0
    for pfx in "$@"; do
      i=$((i+1))
      az network route-table route create -g "$RG" --route-table-name "$RT" -n "r$i" --address-prefix "$pfx" --next-hop-type None \
        --query '{name:name,prefix:addressPrefix,nextHop:nextHopType,state:provisioningState}' -o json 2>&1 | mask | tee -a "$NETLOG"
    done
    az network vnet subnet update -g "$RG" --vnet-name "$VNET" -n snet-agent --route-table "$RT" -o none 2>&1 | mask | tee -a "$NETLOG"
    echo "[$(ts)] associated" | tee -a "$NETLOG"
    subnet
    ;;
  rt-off)
    echo "### [$(ts)] route table off" | tee -a "$NETLOG"
    az network vnet subnet update -g "$RG" --vnet-name "$VNET" -n snet-agent --remove routeTable -o none 2>&1 | mask | tee -a "$NETLOG"
    az network route-table delete -g "$RG" -n "$RT" 2>&1 | mask | tee -a "$NETLOG"
    echo "[$(ts)] route table removed" | tee -a "$NETLOG"
    subnet
    ;;
  subnet) subnet ;;
  *) echo "usage: $0 push|run <cmd> <phase>|nsg <ip>...|nsg-off|rt <prefix>...|rt-off|subnet" >&2; exit 2 ;;
esac
