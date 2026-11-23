#!/usr/bin/env bash
# WSL 側から VM 内の probe を動かす(Bastion なし・パブリック IP なし → az vm run-command invoke)。
#   ./vmrun.sh push                 # vm/*.py と config.json を VM に置き、検証用サーバーを起動
#   ./vmrun.sh run <command> [args] # VM 内で vmprobe.py <command> を実行し、標準出力を logs/vm-<command>.log に追記
#   ./vmrun.sh fetch <command>      # VM 内の詳細ログ /opt/probe/logs/<command>.log を分割取得して logs/vmfull-<command>.log に保存
#   ./vmrun.sh sh '<shell>'         # 任意のシェル(診断用)
# run-command の標準出力は末尾 4,096 バイトまでしか返らない。詳細は fetch で取る。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib.sh"
VM="${VM:-$(az vm list -g "$RG" --query '[0].name' -o tsv)}"
CONFIG="${CONFIG:-${SCRATCH:-$HERE/.work}/vm-config.json}"

rc() {  # rc <script> → 標準出力と標準エラー(run-command の message)を表示
  local script="$1"
  az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "$script" -o json \
    | jq -r '.value[0].message'
}

case "${1:-}" in
  push)
    b64() { base64 -w0 "$1"; }
    script="set -e; mkdir -p /opt/probe/logs
echo $(b64 "$HERE/vm/vmprobe.py") | base64 -d > /opt/probe/vmprobe.py
echo $(b64 "$HERE/vm/api_server.py") | base64 -d > /opt/probe/api_server.py
echo $(b64 "$CONFIG") | base64 -d > /opt/probe/config.json
systemctl stop probe-api 2>/dev/null || true; systemctl reset-failed probe-api 2>/dev/null || true
systemd-run --unit=probe-api --property=Restart=always /usr/bin/python3 /opt/probe/api_server.py
sleep 2; curl -s -m 5 http://10.40.2.10:8080/health; echo; python3 --version"
    rc "$script" | mask | tee -a "${LOGDIR:-$HERE/logs}/vm-push.log"
    ;;
  run)
    shift
    cmd="$1"; shift || true
    log="${LOGDIR:-$HERE/logs}/vm-${cmd}.log"
    echo "### [$(ts)] vmprobe.py $cmd $*" | tee -a "$log"
    rc "timeout 1500 python3 /opt/probe/vmprobe.py $cmd $* 2>&1 | tail -c 4000" | mask | tee -a "$log"
    ;;
  fetch)
    cmd="$2"
    log="${LOGDIR:-$HERE/logs}/vmfull-${cmd}.log"
    tmp="$(mktemp)"
    n=$(rc "gzip -c /opt/probe/logs/${cmd}.log | base64 -w0 | wc -c" | sed -n '/\[stdout\]/{n;p}')
    off=0; : > "$tmp"
    while [ "$off" -lt "$n" ]; do
      rc "gzip -c /opt/probe/logs/${cmd}.log | base64 -w0 | cut -c$((off+1))-$((off+3800))" | sed -n '/\[stdout\]/{n;p}' | tr -d '\n' >> "$tmp"
      off=$((off+3800))
    done
    base64 -d "$tmp" | gunzip | mask > "$log"
    rm -f "$tmp"
    echo "saved $log ($(wc -l < "$log") lines)"
    ;;
  sh)
    rc "$2" | mask
    ;;
  *)
    echo "usage: $0 push|run <cmd>|fetch <cmd>|sh '<shell>'" >&2; exit 2
    ;;
esac
