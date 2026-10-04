#!/usr/bin/env python3
"""Check that every same-site file a site's pages reference actually loads.

  scripts/check-refs.py <domain> <base-url> [--root <dir>] [--local-missing]

Collects references from the HTML and CSS under sites/<domain>/public (or --root): src, href,
srcset and <source srcset> candidates, poster, data-src/data-srcset, inline style url() and CSS
url(). Default: requests each one from <base-url>, prints "<domain>: N referenced same-site
files, M not loading" plus the failing paths, and exits 1 if any fail.
--local-missing: no network; prints, one per line, the referenced paths with no local file
(used by fetch-site.sh to fetch what the crawler skipped). Never prints page text.
"""
import sys, os, re, html.parser, urllib.parse, subprocess

args = sys.argv[1:]
if len(args) < 2: sys.exit(__doc__)
domain, base = args[0], args[1].rstrip('/')
root = args[args.index('--root') + 1] if '--root' in args else f"sites/{domain}/public"
local_only = '--local-missing' in args
hosts = {domain, "www." + domain}
refs = set()
URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)")

def add(u, page):
    u = (u or "").strip()
    if not u or u.startswith(("data:", "mailto:", "tel:", "javascript:", "#")): return
    p = urllib.parse.urlparse(urllib.parse.urljoin(base + page, u))
    if p.scheme not in ("http", "https") or (p.netloc and p.netloc not in hosts): return
    refs.add(urllib.parse.unquote(p.path) or "/")

class Parser(html.parser.HTMLParser):
    def __init__(self, page): super().__init__(); self.page = page
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for k in ("src", "poster", "data-src", "data-original"): add(d.get(k), self.page)
        if tag in ("link", "a", "area"): add(d.get("href"), self.page)
        for k in ("srcset", "data-srcset", "imagesrcset"):
            for part in (d.get(k) or "").split(","):
                if part.strip(): add(part.split()[0], self.page)
        for m in URL_RE.findall(d.get("style") or ""): add(m, self.page)

for dirpath, _, files in os.walk(root):
    for f in files:
        fp = os.path.join(dirpath, f)
        page = ("/" + os.path.relpath(fp, root)).rsplit("/", 1)[0] + "/"
        if f.endswith((".html", ".htm")):
            txt = open(fp, encoding="utf-8", errors="replace").read()
            Parser(page).feed(txt)
            for block in re.findall(r"<style[^>]*>(.*?)</style>", txt, re.S):
                for m in URL_RE.findall(block): add(m, page)
        elif f.endswith(".css"):
            for m in URL_RE.findall(open(fp, encoding="utf-8", errors="replace").read()): add(m, page)

def has_local(r):
    return any(os.path.isfile(root + c) for c in (r, r.rstrip("/") + "/index.html", r + ".html"))

if local_only:
    for r in sorted(refs):
        if not has_local(r) and not r.endswith("/"): print(r)
    sys.exit(0)

failing = []
for r in sorted(refs):
    code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-L", "--max-time", "30", "-w", "%{http_code}",
                           base + urllib.parse.quote(r)], capture_output=True, text=True).stdout or "000"
    if code != "200": failing.append(f"   {code}  local={'yes' if has_local(r) else 'NO '}  {r}")
print(f"{domain}: {len(refs)} referenced same-site files, {len(failing)} not loading")
if failing: print("\n".join(failing)); sys.exit(1)
