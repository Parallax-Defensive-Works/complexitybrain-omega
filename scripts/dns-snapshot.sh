#!/usr/bin/env bash
# Snapshot DNS for every site under sites/ into backups/ (gitignored).
#   public view via DNS-over-HTTPS:                      backups/dns-public-<date>.txt
#   full zone export when CLOUDFLARE_API_TOKEN is set:   backups/<domain>-<date>.zone
# Run it BEFORE cutover: proxied records hide their real targets from public DNS, and the
# zone export is what you restore from if you ever need to roll back.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
date=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$ROOT/backups"
out="$ROOT/backups/dns-public-$date.txt"

doh() {
  curl -sS --max-time 15 -H 'accept: application/dns-json' "https://cloudflare-dns.com/dns-query?name=$1&type=$2" \
    | jq -r '[.Answer[]?.data] | join("  |  ") | if . == "" then "(none)" else . end'
}

for d in $(ls "$ROOT/sites"); do
  echo "=== $d"
  for t in NS A AAAA MX TXT; do printf '%-6s @       %s\n' "$t" "$(doh "$d" "$t")"; done
  printf '%-6s www     %s\n' A     "$(doh "www.$d" A)"
  printf '%-6s www     %s\n' CNAME "$(doh "www.$d" CNAME)"
  printf '%-6s _dmarc  %s\n' TXT   "$(doh "_dmarc.$d" TXT)"
  for s in mail cpanel webmail ftp; do printf '%-6s %-7s %s\n' A "$s" "$(doh "$s.$d" A)"; done
done | tee "$out"
echo "saved $out"

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  for d in $(ls "$ROOT/sites"); do
    zid=$(curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones?name=$d" | jq -r '.result[0].id // empty')
    [ -n "$zid" ] || { echo "zone $d: not found in this account (token scope?)"; continue; }
    curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones/$zid/dns_records/export" -o "$ROOT/backups/$d-$date.zone"
    echo "exported zone $d -> backups/$d-$date.zone ($(grep -cv '^;' "$ROOT/backups/$d-$date.zone") records)"
  done
else
  echo "CLOUDFLARE_API_TOKEN not set: skipped the full zone export (set it and re-run before cutover)"
fi
