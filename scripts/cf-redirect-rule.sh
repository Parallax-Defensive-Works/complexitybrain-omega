#!/usr/bin/env bash
# Add a zone-level Single Redirect. It runs at Cloudflare's edge, before the Worker,
# so it costs nothing and does not depend on the hosting.
#
#   scripts/cf-redirect-rule.sh <domain> apex-to-www   # https://<domain>/x     -> https://www.<domain>/x  (301)
#   scripts/cf-redirect-rule.sh <domain> www-to-apex   # https://www.<domain>/x -> https://<domain>/x      (301)
#
# Needs Cloudflare credentials (see scripts/cf-auth.sh) with Zone: Read and Dynamic Redirect: Edit.
# Does nothing if a rule for that host already exists.
set -euo pipefail

domain="${1:-}"; mode="${2:-}"
case "$mode" in
  apex-to-www) from="$domain";     to="www.$domain" ;;
  www-to-apex) from="www.$domain"; to="$domain" ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/cf-auth.sh"
cf_require_auth || exit 1

zid=$(api "$B/zones?name=$domain" | jq -r '.result[0].id // empty')
[ -n "$zid" ] || { echo "zone $domain not found in this account"; exit 1; }

expr="(http.host eq \"$from\")"
rule=$(jq -n --arg from "$from" --arg to "$to" --arg expr "$expr" '{
  description: ("redirect " + $from + " -> " + $to),
  expression: $expr,
  action: "redirect",
  enabled: true,
  action_parameters: { from_value: {
    status_code: 301,
    preserve_query_string: true,
    target_url: { expression: ("concat(\"https://" + $to + "\", http.request.uri.path)") }
  } }
}')

ep=$(api "$B/zones/$zid/rulesets/phases/http_request_dynamic_redirect/entrypoint")
if [ "$(printf '%s' "$ep" | jq -r .success)" = true ]; then
  if printf '%s' "$ep" | jq -e --arg e "$expr" '.result.rules[]? | select(.expression == $e)' >/dev/null; then
    echo "a redirect rule for $from already exists - nothing to do"; exit 0
  fi
  rid=$(printf '%s' "$ep" | jq -r .result.id)
  res=$(api -X POST "$B/zones/$zid/rulesets/$rid/rules" --data "$rule")
else
  body=$(jq -n --argjson r "$rule" '{name: "redirects", kind: "zone", phase: "http_request_dynamic_redirect", rules: [$r]}')
  res=$(api -X POST "$B/zones/$zid/rulesets" --data "$body")
fi
printf '%s' "$res" | jq -r --arg from "$from" --arg to "$to" 'if .success then "ok: 301 \($from) -> \($to) is live" else "error: \(.errors)" end'
