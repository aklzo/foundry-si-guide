# 12〜14 の共通ヘルパー(source して使う)。
# - ログからサブスクリプション ID・テナント ID を伏せる(mask)
# - ARM / データプレーンを curl で呼び、HTTP ステータスと本文をそのまま残す(arm)
# トークンは環境変数にだけ置き、ファイルやログには書かない。

RG="${RG:-rg-ignite26-verify}"
LOC="${LOC:-japaneast}"
HERE_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUB_ID="$(az account show --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"

mask() {
  sed -e "s/${SUB_ID}/<sub>/g" -e "s/${TENANT_ID}/<tenant>/g"
}

ts() { TZ=Asia/Tokyo date +"%Y-%m-%d %H:%M:%S JST"; }

# arm METHOD PATH_OR_URL [JSON_BODY]  — PATH は /subscriptions/... で始める
arm() {
  local method="$1" url="$2" body="${3:-}"
  [[ "$url" == /* ]] && url="https://management.azure.com${url}"
  local tok
  tok="$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)"
  local out code
  out="$(mktemp)"
  if [ -n "$body" ]; then
    code=$(curl -sS -o "$out" -w '%{http_code}' -X "$method" "$url" \
      -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' --data "$body")
  else
    code=$(curl -sS -o "$out" -w '%{http_code}' -X "$method" "$url" -H "Authorization: Bearer $tok")
  fi
  {
    echo "[$(ts)] $method ${url}"
    [ -n "$body" ] && echo "  request: $body"
    echo "  HTTP $code"
    echo "  body: $(head -c 4000 "$out")"
  } | mask
  rm -f "$out"
}
