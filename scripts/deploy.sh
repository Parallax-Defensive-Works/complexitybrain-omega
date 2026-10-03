#!/usr/bin/env bash
# Deploy one site (or all) to Cloudflare Workers static assets.
#
#   scripts/deploy.sh <domain|all> [--preview] [--dry-run] [extra wrangler args...]
#
#   (no flag)   deploys sites/<domain>/wrangler.jsonc as is. That config lists the site's custom
#               domains, so the FIRST such deploy is the cutover: wrangler asks, in the terminal,
#               before replacing the DNS records that still point at the old host. Answer y.
#               Without a terminal (CI, or output piped through tee) it replaces them WITHOUT asking.
#   --preview   deploys the same files to <name>.<account>.workers.dev only. The custom domains are
#               stripped from a temporary copy of the config, so the live site is untouched.
#   --dry-run   validates and bundles without contacting Cloudflare (no auth needed).
#
# Auth: export CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID, or run `npx wrangler login` once.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sel="${1:-}"
[ -n "$sel" ] || { sed -n '2,15p' "$0"; exit 2; }
shift
preview=0; args=()
for a in "$@"; do
  case "$a" in --preview) preview=1 ;; *) args+=("$a") ;; esac
done

if [ "$sel" = all ]; then sites="$(ls "$ROOT/sites")"; else sites="$sel"; fi

for s in $sites; do
  dir="$ROOT/sites/$s"; cfg="$dir/wrangler.jsonc"
  [ -f "$cfg" ] || { echo "no config: $cfg"; exit 1; }
  [ -f "$dir/public/index.html" ] || echo "warning: sites/$s/public has no index.html (run fetch or import first)"
  if [ "$preview" = 1 ]; then
    # temporary config next to the real one (paths stay relative): drop the custom domains,
    # turn on the workers.dev hostname. Only full-line // comments are used in wrangler.jsonc.
    cfg="$dir/.wrangler-preview.json"
    grep -vE '^[[:space:]]*//' "$dir/wrangler.jsonc" | jq 'del(.routes) | .workers_dev = true' > "$cfg"
    echo "== $s  (preview: workers.dev only, custom domains untouched)"
  else
    echo "== $s"
    if grep -qE '^[[:space:]]*\{[[:space:]]*"pattern"' "$cfg"; then
      echo "   attaches the custom domains in wrangler.jsonc: wrangler asks before replacing existing DNS records (no prompt in CI)"
    fi
  fi
  ( cd "$ROOT" && npx wrangler deploy --config "$cfg" ${args[@]+"${args[@]}"} )
done
