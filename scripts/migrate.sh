#!/usr/bin/env bash
# End-to-end move of one site (or all) from the old host to Cloudflare, non-interactive.
#
#   scripts/migrate.sh <domain|all> [--force] [--old-ip <ip>]
#
# Per site: zone export (rollback material) -> preview deploy on workers.dev -> parity check of
# the preview against the current site (stops before cutover on any difference unless --force,
# or when the old host is not answering) -> live deploy with Worker routes on apex and www
# (proxied hostnames switch at once) -> a zone Redirect Rule if the old host redirected
# apex->www or www->apex -> apex/www DNS records moved to 192.0.2.1, proxied, so the old host
# is out of the path -> cache purge -> parity check on the real hostname.
# Rollback: delete the two Worker routes and import the zone export from backups/.
#
# Needs Cloudflare credentials (CLOUDFLARE_API_TOKEN, or CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY),
# the files under sites/<domain>/public, and the permissions listed in docs/MIGRATION.md.
# CLOUDFLARE_ACCOUNT_ID is found automatically when the credentials see one account.
# Prints counts and URLs, never content.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sel="${1:-}"
[ -n "$sel" ] || { sed -n '2,14p' "$0"; exit 2; }
shift
force=0; oldip=""
while [ $# -gt 0 ]; do
  case "$1" in
    --force) force=1; shift ;;
    --old-ip) oldip="$2"; shift 2 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done
. "$ROOT/scripts/cf-auth.sh"
# tools: install wrangler if this checkout has never run npm ci
[ -x "$ROOT/node_modules/.bin/wrangler" ] || ( cd "$ROOT" && npm ci --no-audit --no-fund >/dev/null 2>&1 ) \
  || { echo "preflight: npm ci failed"; exit 1; }
head_of() { curl -sS -o /dev/null -I -A "$UA" --max-time 20 -w '%{http_code} %{redirect_url}' "$1" 2>/dev/null || echo "000 "; }
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
mkdir -p "$ROOT/backups"
stamp=$(date -u +%Y%m%dT%H%M%SZ)

# ---- preflight: token, zones, files ------------------------------------------------------
cf_preflight || exit 1
if [ "$sel" = all ]; then sites="$(ls "$ROOT/sites")"; else sites="$sel"; fi
for s in $sites; do
  # site files are not in git (public repo): mirror them from the live site when this checkout has none
  if [ ! -f "$ROOT/sites/$s/public/index.html" ]; then
    echo "preflight: no local files for $s; mirroring the live site"
    "$ROOT/scripts/fetch-site.sh" "$s" | tail -1
  fi
  [ -f "$ROOT/sites/$s/public/index.html" ] || { echo "preflight: no files under sites/$s/public and the live site could not be mirrored"; exit 1; }
  z=$(api "$B/zones?name=$s")
  zid=$(printf '%s' "$z" | jq -r '.result[0].id // empty')
  zacct=$(printf '%s' "$z" | jq -r '.result[0].account.id // empty')
  [ -n "$zid" ] || { echo "preflight: zone $s is not visible to this token"; exit 1; }
  [ "$zacct" = "$CLOUDFLARE_ACCOUNT_ID" ] || { echo "preflight: zone $s belongs to account $zacct, not CLOUDFLARE_ACCOUNT_ID"; exit 1; }
done
# a workers.dev subdomain is needed for the preview step; register one if the account has none
sub=$(api "$B/accounts/$CLOUDFLARE_ACCOUNT_ID/workers/subdomain" | jq -r '.result.subdomain // empty')
if [ -z "$sub" ]; then
  want="sites-$(printf '%s' "$CLOUDFLARE_ACCOUNT_ID" | cut -c1-6)"
  sub=$(api -X PUT "$B/accounts/$CLOUDFLARE_ACCOUNT_ID/workers/subdomain" --data "{\"subdomain\":\"$want\"}" | jq -r '.result.subdomain // empty')
  [ -n "$sub" ] || { echo "preflight: could not register a workers.dev subdomain (token needs Workers Scripts: Edit)"; exit 1; }
  echo "registered workers.dev subdomain: $sub.workers.dev"
fi
echo "preflight ok: credentials accepted, zones found in the account, files present"

for s in $sites; do
  echo; echo "########## $s"
  dir="$ROOT/sites/$s"
  name=$(grep -vE '^[[:space:]]*//' "$dir/wrangler.jsonc" | jq -r .name)
  zid=$(api "$B/zones?name=$s" | jq -r '.result[0].id')

  # 1. rollback material
  api "$B/zones/$zid/dns_records/export" -o "$ROOT/backups/$s-$stamp.zone"
  echo "1. zone exported -> backups/$s-$stamp.zone"

  # what the old host does today, captured before anything changes
  apex=$(head_of "https://$s/"); www=$(head_of "https://www.$s/")
  rule=""
  case "$apex" in 30[1278]\ https://www.$s/*) rule=apex-to-www ;; esac
  case "$www"  in 30[1278]\ https://$s/*)     rule=www-to-apex ;; esac
  case "$rule:$www" in
    apex-to-www:*) canon="https://www.$s" ;;
    www-to-apex:*) canon="https://$s" ;;
    :200*)         canon="https://www.$s" ;;
    *)             canon="https://$s" ;;
  esac
  old_up=0; case "$(head_of "$canon/")" in 200*) old_up=1 ;; esac
  echo "   old host: apex=[$apex] www=[$www]; canonical $canon; answering=$old_up${rule:+; host redirect to recreate: $rule}"

  # 2. preview on workers.dev
  log="$ROOT/backups/deploy-$s-preview.log"
  "$ROOT/scripts/deploy.sh" "$s" --preview >"$log" 2>&1 \
    || { echo "2. preview deploy failed:"; grep -i -E 'error|✘' "$log" | head -5; echo "   (full log: $log)"; exit 1; }
  prev=$(grep -o 'https://[a-z0-9.-]*\.workers\.dev' "$log" | head -1 || true)
  [ -n "$prev" ] || { echo "2. no workers.dev URL in the deploy output (register a workers.dev subdomain once in the dashboard?) - see $log"; exit 1; }
  # a freshly registered workers.dev subdomain can take several minutes to resolve and get its certificate (waits up to 15)
  c=000; for _ in $(seq 1 180); do c=$(curl -s -o /dev/null -A "$UA" --max-time 10 -w '%{http_code}' "$prev/" || true); [ "$c" = 200 ] && break; sleep 5; done
  echo "2. preview deployed: $prev (http $c)"
  [ "$c" = 200 ] || { echo "   preview never answered 200; stopping before cutover"; exit 1; }

  # 3. parity gate: preview vs the current site
  if [ "$old_up" = 1 ]; then
    out=$("$ROOT/scripts/verify.sh" "$s" --new "$prev" --old "$canon" ${oldip:+--old-ip "$oldip"} | sed -n 1p)
    if ! printf '%s' "$out" | grep -q ' differ=0 missing-on-new=0'; then
      sleep 20   # a redeployed preview can 404 a file for a few seconds while assets propagate
      out=$("$ROOT/scripts/verify.sh" "$s" --new "$prev" --old "$canon" ${oldip:+--old-ip "$oldip"} | sed -n 1p)
    fi
    echo "3. preview vs current site: $out"
    if ! printf '%s' "$out" | grep -q ' differ=0 missing-on-new=0'; then
      if [ "$force" = 1 ]; then echo "   differences found; continuing because of --force"
      else echo "   differences found; NOT cutting over. Paths (only) in backups/verify-$s.txt. Re-run with --force to proceed anyway."; exit 1; fi
    fi
  else
    echo "3. old host is not answering; skipping the comparison"
  fi

  # 4. live: Worker routes on apex and www. Proxied hostnames switch to the Worker at once.
  log="$ROOT/backups/deploy-$s-live.log"
  "$ROOT/scripts/deploy.sh" "$s" >"$log" 2>&1 \
    || { echo "4. live deploy failed:"; grep -i -E 'error|✘|code:' "$log" | head -6 || true; echo "   (full log: $log)"; exit 1; }
  routes=$(api "$B/zones/$zid/workers/routes" | jq -r --arg n "$name" '[.result[]? | select(.script == $n) | .pattern] | sort | join(", ")')
  [ -n "$routes" ] || { echo "4. live deploy ran but no route points at $name - see $log"; exit 1; }
  echo "4. worker routes live: $routes"

  # 5. the apex/www redirect the old server did, recreated as a zone rule BEFORE the DNS change
  #    (zone rules run ahead of Workers, and only for proxied hostnames)
  if [ -z "$rule" ]; then echo "5. the old host had no apex/www redirect; none needed"
  else
    case "$rule" in apex-to-www) from="$s"; to="www.$s" ;; *) from="www.$s"; to="$s" ;; esac
    have=$(api "$B/zones/$zid/rulesets/phases/http_request_dynamic_redirect/entrypoint" \
      | jq -r --arg h "$from" '[.result.rules[]? | select(.enabled != false) | select((.expression | contains("\"" + $h + "\"")) or (.expression | contains("://" + $h + "/")))] | length' || echo 0)
    if [ "${have:-0}" -gt 0 ]; then echo "5. a zone rule already redirects $from -> $to; kept"
    else printf '5. '; "$ROOT/scripts/cf-redirect-rule.sh" "$s" "$rule"; fi
  fi

  # 6. DNS: point apex/www away from the old host. 192.0.2.1 is a reserved, never-routed address;
  #    with the record proxied, Cloudflare answers via the Worker routes and never contacts it.
  changed=0
  recs=$(api "$B/zones/$zid/dns_records?per_page=100" | jq -c --arg a "$s" --arg w "www.$s" '[.result[] | select((.name == $a or .name == $w) and (.type == "A" or .type == "AAAA" or .type == "CNAME"))]')
  declare -A dummy=()
  while IFS= read -r r; do dummy["$r"]=1; done < <(printf '%s' "$recs" | jq -r '.[] | select(.type == "A" and .content == "192.0.2.1") | .name')
  while IFS=$'\t' read -r rid rtype rname rcontent rproxied; do
    [ -n "$rid" ] || continue
    case "$rtype" in
      A)
        if [ "$rcontent" = 192.0.2.1 ]; then
          [ "$rproxied" = true ] || { api -X PATCH "$B/zones/$zid/dns_records/$rid" --data '{"proxied":true}' | jq -e .success >/dev/null && changed=$((changed+1)); }
        elif [ -n "${dummy[$rname]:-}" ]; then
          api -X DELETE "$B/zones/$zid/dns_records/$rid" | jq -e .success >/dev/null && changed=$((changed+1))
        else
          api -X PATCH "$B/zones/$zid/dns_records/$rid" --data '{"content":"192.0.2.1","proxied":true}' | jq -e .success >/dev/null \
            && { changed=$((changed+1)); dummy["$rname"]=1; }
        fi ;;
      AAAA)  # no IPv6 at the old host; Cloudflare still serves IPv6 for proxied names
        api -X DELETE "$B/zones/$zid/dns_records/$rid" | jq -e .success >/dev/null && changed=$((changed+1)) ;;
      CNAME)
        [ "$rproxied" = true ] || { api -X PATCH "$B/zones/$zid/dns_records/$rid" --data '{"proxied":true}' | jq -e .success >/dev/null && changed=$((changed+1)); } ;;
    esac
  done < <(printf '%s' "$recs" | jq -r '.[] | [.id, .type, .name, .content, (.proxied|tostring)] | @tsv')
  left=$(api "$B/zones/$zid/dns_records?per_page=100" | jq -r --arg a "$s" --arg w "www.$s" '[.result[] | select((.name == $a or .name == $w) and ((.type == "A" and .content != "192.0.2.1") or .proxied == false) and (.type == "A" or .type == "AAAA" or .type == "CNAME")) | "\(.type) \(.name) \(.content)"] | join("; ")')
  if [ -n "$left" ]; then echo "6. DNS: $changed records changed, but these still bypass the Worker: $left"; exit 1; fi
  echo "6. DNS: apex and www now point only at Cloudflare ($changed records changed)"
  unset dummy

  # 7. drop cached copies of the old origin
  api -X POST "$B/zones/$zid/purge_cache" --data '{"purge_everything":true}' \
    | jq -r 'if .success then "7. zone cache purged" else "7. cache purge failed: \(.errors)" end'

  # 8. the real hostname must now serve the same bytes as the local files. With DNS at 192.0.2.1,
  #    any 200 here can only come from the Worker.
  sleep 5
  out=$("$ROOT/scripts/verify.sh" "$s" --new "$canon" --old local | sed -n 1p)
  echo "8. live hostname vs local files: $out"
  for h in "$s" "www.$s"; do echo "   https://$h/ -> $(head_of "https://$h/")"; done
done

echo; echo "done. Check the sites in a browser. After a few quiet days, cancel the old hosting."
