#!/usr/bin/env bash
# Content-blind mirror of a live site into sites/<domain>/public.
#
#   scripts/fetch-site.sh <domain> [--keep-existing]
#
# Crawls https://<domain>/ (following its canonical apex/www redirect), seeded with
# robots.txt and every URL in sitemap.xml, plus all page requisites (css/js/images).
# Nothing from the pages is printed: wget's output goes to backups/<domain>.mirror.log.
# Only file counts and sizes are reported. public/ is replaced unless --keep-existing.
#
# Limits of a crawl (use scripts/import-cpanel-archive.sh for a pristine copy):
#   - files not linked from any page and not in the sitemap are missed
#   - .htaccess rules are not captured, only their visible effects
#   - pages are captured as Cloudflare serves them (its injected scripts included, if any)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
domain="${1:-}"
[ -n "$domain" ] || { sed -n '2,15p' "$0"; exit 2; }
shift
keep=0; for a in "$@"; do [ "$a" = --keep-existing ] && keep=1; done

site="$ROOT/sites/$domain"
pub="$site/public"
tmp="$ROOT/backups/mirror-tmp/$domain"
log="$ROOT/backups/$domain.mirror.log"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

mkdir -p "$site" "$ROOT/backups"
rm -rf "$tmp"; mkdir -p "$tmp"
: > "$log"

canon=$(curl -sS -o /dev/null -L -A "$UA" --max-time 20 -w '%{url_effective}' "https://$domain/" 2>>"$log" || true)
host=$(printf '%s' "$canon" | sed -E 's#^https?://([^/]+).*#\1#')
case "$host" in "$domain"|"www.$domain") ;; *) host="$domain" ;; esac
echo "mirroring https://$host/ (canonical host)"

seeds="$tmp.seeds"
{
  echo "https://$host/"
  for f in robots.txt sitemap.xml sitemap_index.xml favicon.ico; do echo "https://$host/$f"; done
  for sm in sitemap.xml sitemap_index.xml; do
    curl -sS -A "$UA" --max-time 30 "https://$host/$sm" 2>/dev/null | grep -o '<loc>[^<]*</loc>' | sed 's/<loc>//;s#</loc>##' || true
  done
} | sort -u > "$seeds"
# one level of nested sitemaps
grep -E 'sitemap[^/]*\.xml$' "$seeds" | while read -r u; do
  curl -sS -A "$UA" --max-time 30 "$u" 2>/dev/null | grep -o '<loc>[^<]*</loc>' | sed 's/<loc>//;s#</loc>##' || true
done >> "$seeds"
sort -u -o "$seeds" "$seeds"

set +e
wget --mirror --page-requisites --adjust-extension --no-parent \
     --span-hosts --domains="$domain,www.$domain" \
     --no-host-directories --directory-prefix="$tmp" \
     --exclude-directories=/cdn-cgi \
     -e robots=off --user-agent="$UA" --wait=0.2 --timeout=30 --tries=3 \
     --input-file="$seeds" >>"$log" 2>&1
rc=$?
set -e
rm -f "$seeds"
# wget exit 8 = "server issued an error response" (a 404 among the seeds, typically) - not fatal
[ $rc -eq 0 ] || [ $rc -eq 8 ] || { echo "wget failed (exit $rc) - see $log"; exit 1; }

# files saved as "name?query" -> "name" (first one wins)
find "$tmp" -type f -name '*\?*' -print0 | while IFS= read -r -d '' f; do
  b="${f%%\?*}"
  if [ -e "$b" ]; then rm -f "$f"; else mv "$f" "$b"; fi
done

# --adjust-extension appends .html to anything the server labelled text/html, even robots.txt
# or a sitemap sent with the wrong content type: give those files their real names back
find "$tmp" -type f -regextype posix-extended -iregex '.*\.(txt|xml|pdf|jpe?g|png|webp|gif|svg|css|js|json|ico|woff2?)\.html$' -print0 \
  | while IFS= read -r -d '' f; do b="${f%.html}"; [ -e "$b" ] || mv "$f" "$b"; done

n=$(find "$tmp" -type f | wc -l)
[ "$n" -gt 0 ] || { echo "nothing fetched - see $log"; exit 1; }

# keep the hand-written control files from the previous public/
for f in _redirects _headers .assetsignore; do
  [ -f "$pub/$f" ] && cp "$pub/$f" "$tmp/$f"
done
[ -f "$tmp/.assetsignore" ] || cp "$ROOT/scripts/assetsignore.default" "$tmp/.assetsignore"

if [ "$keep" = 1 ] && [ -d "$pub" ]; then
  cp -a "$tmp/." "$pub/"
else
  rm -rf "$pub"; mv "$tmp" "$pub"
fi
rm -rf "$tmp"

printf 'done: %s files, %s, %s html pages, 403s=%s 404s=%s -> %s\n' \
  "$(find "$pub" -type f | wc -l)" "$(du -sh "$pub" | cut -f1)" \
  "$(find "$pub" -type f \( -name '*.html' -o -name '*.htm' \) | wc -l)" \
  "$(grep -c 'ERROR 403' "$log" || true)" "$(grep -c 'ERROR 404' "$log" || true)" "$pub"
