# Sourced by the scripts that call the Cloudflare API. Accepts either
#   CLOUDFLARE_API_TOKEN                     a scoped API token (preferred), or
#   CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY    the account's login email + Global API Key
# (wrangler understands the same variables). Provides api(), cf_require_auth and cf_preflight;
# cf_preflight also fills CLOUDFLARE_ACCOUNT_ID when the credentials see exactly one account.
if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  AUTH=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"); CF_AUTH_KIND=token
elif [ -n "${CLOUDFLARE_API_KEY:-}" ] && [ -n "${CLOUDFLARE_EMAIL:-}" ]; then
  AUTH=(-H "X-Auth-Email: $CLOUDFLARE_EMAIL" -H "X-Auth-Key: $CLOUDFLARE_API_KEY"); CF_AUTH_KIND=key
else
  AUTH=(); CF_AUTH_KIND=none
fi
B=https://api.cloudflare.com/client/v4
api() { curl -sS ${AUTH[@]+"${AUTH[@]}"} -H 'content-type: application/json' "$@"; }
cf_require_auth() {
  [ "$CF_AUTH_KIND" != none ] && return 0
  echo "auth: set CLOUDFLARE_API_TOKEN, or CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY" >&2; return 1
}
cf_preflight() {
  cf_require_auth || return 1
  if [ "$CF_AUTH_KIND" = token ]; then
    api "$B/user/tokens/verify" | jq -e '.success and .result.status == "active"' >/dev/null \
      || { echo "preflight: CLOUDFLARE_API_TOKEN is invalid or inactive" >&2; return 1; }
  else
    api "$B/user" | jq -e '.success' >/dev/null \
      || { echo "preflight: CLOUDFLARE_EMAIL / CLOUDFLARE_API_KEY were rejected" >&2; return 1; }
  fi
  if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
    local accts; accts=$(api "$B/accounts?per_page=50" | jq -r '.result[]? | "\(.id) \(.name)"')
    case "$(printf '%s\n' "$accts" | grep -c .)" in
      1) CLOUDFLARE_ACCOUNT_ID=${accts%% *}; export CLOUDFLARE_ACCOUNT_ID; echo "account: ${accts#* } ($CLOUDFLARE_ACCOUNT_ID)" ;;
      0) echo "preflight: no Cloudflare account is visible to these credentials" >&2; return 1 ;;
      *) echo "preflight: several accounts; set CLOUDFLARE_ACCOUNT_ID to one of:" >&2; printf '  %s\n' $accts >&2; return 1 ;;
    esac
  fi
}
