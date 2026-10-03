#!/usr/bin/env bash
# Import a site from a cPanel / File Manager archive (zip or tar.gz of public_html)
# into sites/<domain>/public. Prints counts only, never file contents.
#
#   scripts/import-cpanel-archive.sh <domain> <archive.zip|.tar.gz|.tgz|.tar>
#
# The web root is detected automatically (a public_html/ folder, else the top-most
# folder holding index.html). .htaccess is copied to sites/<domain>/htaccess.orig
# (gitignored) so its redirect rules can be translated into public/_redirects by hand.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
domain="${1:-}"; archive="${2:-}"
{ [ -n "$domain" ] && [ -f "$archive" ]; } || { sed -n '2,9p' "$0"; exit 2; }

site="$ROOT/sites/$domain"; pub="$site/public"
mkdir -p "$site" "$ROOT/backups"
tmp="$(mktemp -d "$ROOT/backups/import-XXXXXX")"

case "$archive" in
  *.zip)          unzip -q "$archive" -d "$tmp" ;;
  *.tar.gz|*.tgz) tar -xzf "$archive" -C "$tmp" ;;
  *.tar)          tar -xf "$archive" -C "$tmp" ;;
  *) echo "unsupported archive type: $archive"; rm -rf "$tmp"; exit 2 ;;
esac

root="$(find "$tmp" -type d -name public_html | head -1)"
if [ -z "$root" ]; then
  root="$(find "$tmp" -type f \( -name index.html -o -name index.htm \) -printf '%d %h\n' | sort -n | head -1 | cut -d' ' -f2-)"
fi
[ -n "$root" ] || { echo "could not find a web root (public_html/ or index.html) in the archive"; rm -rf "$tmp"; exit 1; }

if [ -f "$root/.htaccess" ]; then
  cp "$root/.htaccess" "$site/htaccess.orig"
  echo "saved .htaccess -> sites/$domain/htaccess.orig (translate its redirect rules into public/_redirects)"
fi
# server-side config and credentials have no place in a static deployment
rm -f "$root/.htaccess" "$root/.htpasswd"
php=$(find "$root" -type f \( -name '*.php' -o -name '*.phtml' \) | wc -l)
[ "$php" -eq 0 ] || echo "warning: $php PHP files found - they cannot run on static hosting and are excluded by .assetsignore"

for f in _redirects _headers .assetsignore; do
  [ -f "$pub/$f" ] && cp "$pub/$f" "$root/$f"
done
[ -f "$root/.assetsignore" ] || cp "$ROOT/scripts/assetsignore.default" "$root/.assetsignore"

rm -rf "$pub"; mv "$root" "$pub"; rm -rf "$tmp"
printf 'done: %s files, %s -> %s\n' "$(find "$pub" -type f | wc -l)" "$(du -sh "$pub" | cut -f1)" "$pub"
