#!/usr/bin/env bash
# Content-blind parity check between the current host and the Cloudflare deployment.
# Every file under sites/<domain>/public is requested from both bases and the response
# bodies are compared by SHA-256. Only counts are printed; the list of differing paths
# is written to backups/verify-<domain>.txt for you to read.
#
#   scripts/verify.sh <domain> --new <base-url> [--old <base-url>] [--old-ip <ip>]
#
#   --new     https://<worker-name>.<account>.workers.dev   (before cutover)
#             https://www.<domain>                            (after cutover)
#   --old     defaults to https://www.<domain> or https://<domain>, whichever is canonical today
#   --old-ip  connect to the old origin's IP directly (bypasses the Cloudflare proxy in front
#             of it). Required after cutover, when the hostname already points at the Worker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
domain="${1:-}"; shift || true
new=""; old=""; oldip=""
while [ $# -gt 0 ]; do
  case "$1" in
    --new) new="$2"; shift 2 ;;
    --old) old="$2"; shift 2 ;;
    --old-ip) oldip="$2"; shift 2 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done
{ [ -n "$domain" ] && [ -n "$new" ]; } || { sed -n '2,14p' "$0"; exit 2; }
pub="$ROOT/sites/$domain/public"
[ -d "$pub" ] || { echo "no $pub"; exit 1; }
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

if [ -z "$old" ]; then
  canon=$(curl -sS -o /dev/null -L -A "$UA" --max-time 20 -w '%{url_effective}' "https://$domain/" || true)
  old=$(printf '%s' "$canon" | sed -E 's#^(https?://[^/]+).*#\1#')
  [ -n "$old" ] || old="https://$domain"
fi
new="${new%/}"; old="${old%/}"
oldhost=$(printf '%s' "$old" | sed -E 's#^https?://([^/]+).*#\1#')
oldopts=()
[ -z "$oldip" ] || oldopts=(--connect-to "$oldhost:443:$oldip:443" --connect-to "$oldhost:80:$oldip:80")

mkdir -p "$ROOT/backups"
report="$ROOT/backups/verify-$domain.txt"; : > "$report"
work=$(mktemp -d)
same=0; differ=0; missing=0; total=0

while IFS= read -r -d '' f; do
  rel="${f#"$pub"/}"
  case "$rel" in _redirects|_headers|.assetsignore|.*|*/.*) continue ;; esac
  path="/$rel"
  case "$path" in */index.html) path="${path%index.html}" ;; esac
  url=$(printf '%s' "$path" | jq -rR 'split("/") | map(@uri) | join("/")')   # spaces etc. in file names
  total=$((total+1))
  oc=$(curl -s -L -A "$UA" --max-time 30 ${oldopts[@]+"${oldopts[@]}"} -o "$work/o" -w '%{http_code}' "$old$url" || echo 000)
  nc=$(curl -s -L -A "$UA" --max-time 30 -o "$work/n" -w '%{http_code}' "$new$url" || echo 000)
  oh=$(sha256sum "$work/o" 2>/dev/null | cut -c1-16 || true)
  nh=$(sha256sum "$work/n" 2>/dev/null | cut -c1-16 || true)
  if [ "$nc" != 200 ]; then
    missing=$((missing+1)); echo "MISSING new=$nc old=$oc $path" >> "$report"   # 000 = connection failed
  elif [ "$oh" = "$nh" ]; then
    same=$((same+1))
  else
    differ=$((differ+1)); echo "DIFFER  new=$nc old=$oc $path" >> "$report"
  fi
  rm -f "$work/o" "$work/n"
done < <(find "$pub" -type f -print0 | sort -z)
rm -rf "$work"

echo "checked $total paths: identical=$same differ=$differ missing-on-new=$missing"
echo "details (paths only): $report"
echo "note: HTML may differ legitimately when the old copy is read through Cloudflare features"
echo "      (Rocket Loader, email obfuscation); re-run with --old-ip <origin ip> to compare against the bare origin."
