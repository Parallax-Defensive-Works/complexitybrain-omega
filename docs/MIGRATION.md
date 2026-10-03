# Moving the four sites from Shinjiru to Cloudflare

Scope: `coach-edward-weinhaus.com`, `edward-andrew-weinhaus-disbarment.com`,
`edward-andrew-weinhaus.com`, `edward-coach-weinhaus.com`. Each becomes an assets-only
Cloudflare Worker (static assets served from Cloudflare's edge, no server, no build step).
Nothing in this repository contains or reads the pages themselves: the files stay on your
machine, and every script reports counts only.

## What is where today (checked 2026-10-03, from public DNS and HTTP headers only)

Common to all four:

- Nameservers are already Cloudflare's (`aliza` / `julio.ns.cloudflare.com`). The zones live on
  your Cloudflare account, so there is no DNS transfer, only a change of origin.
- The origin is one Shinjiru cPanel server, `78.40.143.30` (LiteSpeed), serving plain static
  HTML. Each site is 7 to 16 files, 1 or 2 pages, under 2.5 MB.
- Each site has `robots.txt` and `sitemap.xml`, no `favicon.ico`, no custom 404 page.
- Google Search Console verification is a DNS TXT record on each zone. It is untouched by this
  migration.

| Domain | Canonical URL today | apex -> www redirect | Email on this domain |
|---|---|---|---|
| coach-edward-weinhaus.com | `https://www.coach-edward-weinhaus.com/` | yes, 308 issued by Cloudflare itself (a zone-level rule; it survives the move) | none (no MX) |
| edward-andrew-weinhaus-disbarment.com | `https://edward-andrew-weinhaus-disbarment.com/` (www serves the same site) | no | **yes**: MX via `_dc-mx...` to Shinjiru, SPF, `mail`/`cpanel`/`webmail`/`ftp` records to `78.40.143.x` |
| edward-andrew-weinhaus.com | `https://www.edward-andrew-weinhaus.com/` | yes, 301 issued by the Shinjiru server (**must be recreated**, see cutover) | MX points to `mail.edward-andrew-weinhaus.com`, which does not resolve: email is already not working |
| edward-coach-weinhaus.com | `https://edward-coach-weinhaus.com/` (www serves the same site) | no | none (no MX) |

Other observed behaviour that the configs reproduce:

- `edward-andrew-weinhaus.com` rewrites `/sitemap_index.xml` to `/sitemaps.xml`; that rule is
  in `sites/edward-andrew-weinhaus.com/public/_redirects`.
- `edward-andrew-weinhaus.com`'s apex A record is DNS-only (grey cloud) straight to Shinjiru; the
  others are proxied. After the move all hostnames are served by Cloudflare directly.
- `http://` is **not** redirected to `https://` on `www.coach-edward-weinhaus.com` and on
  `edward-coach-weinhaus.com`. See "Always Use HTTPS" under cutover if you want that fixed.

## Why Workers static assets

It is Cloudflare's current home for static sites (Pages still works, but new features land on
Workers). Requests for static assets are free and unmetered, custom domains attach from the
config file, and `_redirects` / `_headers` files work the same way as on Pages.

## 0. One-time setup (10 minutes)

The scripts need Cloudflare credentials, in one of two forms. Store them as environment
variables (in a cloud session: the environment's settings; on your machine: `export`), never
in the repository or in a chat.

**Option A, a scoped API token (preferred):** dashboard, My Profile, API Tokens, Create Token,
start from the *Edit Cloudflare Workers* template and make sure it has:

- Account: Workers Scripts: Edit, Account Settings: Read
- Zone: Workers Routes: Edit, DNS: Edit, SSL and Certificates: Edit, Zone: Read,
  Cache Purge: Purge, Dynamic Redirect: Edit
- Zone Resources: all zones (or the four)

Variable: `CLOUDFLARE_API_TOKEN`.

**Option B, the Global API Key:** dashboard, My Profile, API Tokens, Global API Key, View
(asks for your password). This key can do anything the account can, so roll it (the "Change"
button next to it) once the migration is done.
Variables: `CLOUDFLARE_EMAIL` (the login email) and `CLOUDFLARE_API_KEY`.

**"Verify your email" when creating a token.** Cloudflare refuses to create API tokens until the
login's email is verified, and the banner sometimes stays even after you clicked the link.
In order: open `dash.cloudflare.com/profile` and check what it says next to your email; if it
offers "Resend verification email", use it and open the link in the same browser you are
logged into; then log out of the dashboard completely and back in; also make sure you are in the
account that holds the four zones (the account switcher is at the top left). If it still blocks
you, use Option B, which has no such gate.

**Known Cloudflare bug (2026): the profile says verified, but tokens, the Global API Key and
Worker deploys all say "verify your email" (API error 10034).** The account's verification
flag is wrong on Cloudflare's side; no credential trick gets around it, because Worker deploys
check the same flag. What has worked for others: the form at `dash.cloudflare.com/login-help`,
choosing "I cannot receive emails from Cloudflare to this address" (it clears their suppression
list and re-sends the verification link); the resend link under the dashboard's notifications
tab; doing it in a private window with no ad blocker, VPN or proxy; and, failing that, a support
ticket (Help Center, your name, My Activities & Requests, Submit a request, category Account).
Account problems get support on the free plan. Community threads: 951825, 948908, 956849.

`CLOUDFLARE_ACCOUNT_ID` is optional: the scripts look it up when the credentials see a single
account. (It is on any zone's Overview page, right column.)

Then, on the machine that will run the deploys (Node 20+, `jq`, `curl`, `wget`):

```sh
git clone https://github.com/Parallax-Defensive-Works/complexitybrain-omega
cd complexitybrain-omega
npm ci
npm run dns      # DNS snapshot + full zone exports into backups/ (your rollback material)
```

`backups/` is gitignored. Keep the `.zone` files somewhere safe.

If the account has never used a `workers.dev` preview address, set one once: dashboard,
Workers & Pages, Overview, "Change" next to the workers.dev subdomain.

## Doing it in one go

Steps 1 to 4 below, as one non-interactive command per site (or `all`), with a safety gate:

```sh
npm run migrate -- edward-coach-weinhaus.com
```

It exports the zone for rollback, deploys a workers.dev preview, compares the preview with the
current site file by file and stops on any difference (`--force` overrides; the gate is
skipped when the old host is down), then attaches the custom domains, purges the zone cache,
re-checks the real hostname and recreates any apex/www redirect the old server used to do.
Everything it prints is counts, status codes and URLs. Logs go to `backups/`.

## 1. Get the site files onto your machine

**Preferred: export from cPanel.** Shinjiru cPanel, File Manager, select `public_html`
(or the addon domain's folder), Compress, download the zip. Then:

```sh
npm run import -- edward-coach-weinhaus.com ~/Downloads/public_html.zip
```

This fills `sites/<domain>/public/`, drops `.htaccess`/`.htpasswd` from it, and saves the
original `.htaccess` as `sites/<domain>/htaccess.orig` (gitignored). Open that file and copy any
`Redirect` / `RewriteRule` lines into `public/_redirects`, one per line as `/from /to 301`.
It also warns if PHP files are present, which would mean the site is not fully static.

**Alternative: mirror the live site.**

```sh
npm run fetch -- edward-coach-weinhaus.com
```

A crawl follows links and the sitemap, so it can miss unlinked files and cannot see
`.htaccess` rules. Use it if you cannot get into cPanel.

`sites/*/public/` is gitignored on purpose: this repository is public and the sites are
proprietary. **Do not commit it.** Deploys run from the machine that holds the files.

## 2. Preview on workers.dev (nothing live changes)

```sh
npm run deploy -- edward-coach-weinhaus.com --preview
```

Wrangler prints a URL like `https://edward-coach-weinhaus-com.<account>.workers.dev`.
Open it and click around. Then compare it with the current site, file by file:

```sh
npm run verify -- edward-coach-weinhaus.com --new https://edward-coach-weinhaus-com.<account>.workers.dev
```

Expected: `identical=<n> differ=0 missing-on-new=0`. Any differing paths are listed in
`backups/verify-<domain>.txt`. (HTML can differ for a harmless reason: the old copy passes
through Cloudflare features such as Rocket Loader or email obfuscation. `--old-ip 78.40.143.30`
compares against the bare origin instead, if Shinjiru's firewall allows direct connections.)

Preview deploys never touch the custom domains: they use a temporary copy of the config with
the `routes` block removed, and wrangler only manages custom domains when the config lists
them. A preview after cutover is safe too; it just re-enables the workers.dev hostname until
the next live deploy switches it off again.

## 3. Before cutover: email

Cutover replaces the apex and `www` DNS records. Two domains need attention first.

**edward-andrew-weinhaus-disbarment.com** has working email on Shinjiru. Its MX points at
`_dc-mx.<hash>.edward-andrew-weinhaus-disbarment.com`, a helper record Cloudflare derives from
the proxied apex record. When the apex becomes a Worker domain that helper can disappear and
mail would bounce. So, in the zone's DNS, **before** cutover:

1. Confirm `mail.edward-andrew-weinhaus-disbarment.com` exists as a DNS-only (grey cloud)
   A record to the mail server (`78.40.143.30` today).
2. Change the MX record's target to `mail.edward-andrew-weinhaus-disbarment.com`, priority 0.
3. Leave `mail`, `cpanel`, `webmail`, `ftp` and the SPF/DMARC TXT records alone until you have
   moved the mailbox elsewhere. Cancelling Shinjiru kills this mailbox.

**edward-andrew-weinhaus.com** has an MX pointing at a hostname with no address, so mail is
already failing. Either add `mail` as a DNS-only A record to `78.40.143.30` (if there is a
mailbox there you want), or delete the MX record.

The other two domains have no email records.

## 4. Cutover (per site, about a minute)

Run it in a real terminal, not piped: wrangler asks a question.

```sh
npm run deploy -- edward-coach-weinhaus.com
```

Wrangler uploads the files, then says
`You already have DNS records that conflict for these Custom Domains ... Update them to point to this script instead?`
Answer `y`. It replaces the apex and `www` records with the Worker's custom domains and issues
certificates. In CI or with output piped, wrangler does this without asking; that is why the
GitHub workflow must stay unused until after cutover (it is inert anyway while the files are
not in the repository).

Right after:

1. **Purge the zone cache**: dashboard, the zone, Caching, Configuration, Purge Everything.
   Cloudflare was caching responses from the old origin under the same URLs.
2. **Check**: `curl -sI https://www.<domain>/` should show `server: cloudflare` and no
   `cf-cache-status: HIT` from the old copy; then
   `npm run verify -- <domain> --new https://www.<domain> --old-ip 78.40.143.30`.
3. **Redirects** that used to come from the Shinjiru server:
   - `edward-andrew-weinhaus.com`: `npm run redirect-rule -- edward-andrew-weinhaus.com apex-to-www`
     recreates the apex to www 301 as a zone Redirect Rule (dashboard alternative: Rules,
     Redirect Rules, template "Redirect from Root to WWW").
   - `coach-edward-weinhaus.com`: its redirect is already a Cloudflare rule; confirm with
     `curl -sI https://coach-edward-weinhaus.com/` (expect 308 to www).
   - The other two serve both apex and www today; add a rule only if you want one canonical host.
4. **Always Use HTTPS** (optional, recommended): dashboard, the zone, SSL/TLS, Edge
   Certificates, Always Use HTTPS: On. Fixes the two zones that still answer on `http://`.

Repeat for each site. Order suggestion: `edward-coach-weinhaus.com` first (no email, no
redirects), then `coach-edward-weinhaus.com`, then the two `edward-andrew-*` domains.

## 5. After cutover

- Search Console needs nothing; the TXT verification records are unchanged. Resubmitting the
  sitemaps is optional.
- Watch the sites for a few days. Then cancel Shinjiru hosting, **but only after** the
  `edward-andrew-weinhaus-disbarment.com` mailbox is moved or confirmed unused.
- Once Shinjiru is gone, delete the leftover records that point at `78.40.143.x`
  (`mail`, `cpanel`, `webmail`, `ftp`, `_dc-mx...`) and tidy the SPF record.
- **Updating a site later**: edit files under `sites/<domain>/public/`, then
  `npm run deploy -- <domain>`. The custom domains are already attached, so no prompt.
- **Automatic deploys** (optional): `.github/workflows/deploy.yml` deploys any site whose files
  are present on a push to `main`, using the `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
  repository secrets. That only makes sense if the site files are committed, which in turn only
  makes sense in a **private** repository. To go that way: make this repo private (or move
  `sites/` to one), remove the `sites/*/public/*` lines from `.gitignore`, add the two secrets.

## If the Cloudflare account cannot be fixed: move the zones to a new account

A domain can be active in only one Cloudflare account, and each account has its own pair of
nameservers, so "moving" a zone means adding it to the new account and pointing the domain's
nameservers at that account's pair. Cloudflare has no button for this; it is done at the
registrar. Registrars as of 2026-10-03 (public RDAP): Tucows for coach-edward-weinhaus.com,
edward-andrew-weinhaus.com and edward-coach-weinhaus.com (a wholesaler: the login is at the
reseller the domains were bought through, probably Shinjiru's client area or Hover), and
Mat Bao for edward-andrew-weinhaus-disbarment.com. None are on Cloudflare Registrar.

Zero-downtime order:

1. Create the new Cloudflare account with a different email address and verify it.
2. In the **old** account, for each zone: DNS, Records, Export. Keep the four files. Also note
   any Redirect Rules or Page Rules (coach-edward-weinhaus.com has an apex-to-www one).
3. In the **new** account: Add a domain, Free plan, then DNS, Records, Import, using the file
   from step 2. Check the records match the old account exactly (proxy status included).
   Cloudflare shows the two new nameservers on the zone's Overview page.
4. At the registrar, change the domain's nameservers to those two. The Tucows domains carry a
   "client update prohibited" lock: if the panel refuses the change, switch the domain lock
   off, change the nameservers, switch it back on.
5. Wait until the zone shows Active in the new account (minutes to a few hours). Universal
   SSL is normally issued within 15 minutes of activation; a short certificate warning in
   that window is possible. The old account's zone then shows as Moved and can be deleted.
6. Create the API token in the new account (section 0) and run the migration as documented.
   The Search Console TXT records travel with the import, so nothing changes there.

## Rollback (while Shinjiru is still active)

1. Dashboard, Workers & Pages, the site's Worker, Settings, Domains & Routes: remove the two
   custom domains.
2. In the zone's DNS, re-create `A @ 78.40.143.30` and `A www 78.40.143.30` with the same
   proxy status they had before (the `.zone` export from `npm run dns` shows the originals).
3. Purge Everything on the zone.

## What has and has not been verified

- Verified in this session: every `wrangler.jsonc` passes `wrangler deploy --dry-run` with the
  real files (live and `--preview` variants); `fetch`, `import`, `verify` and `dns` scripts were
  run end to end against the live sites; the parity checker reports all files identical when
  pointed at the live site. No page content was read; only counts and HTTP headers.
- Not done here: no deploy to Cloudflare (no credentials in this session), no DNS change, and
  `--old-ip` direct-to-origin checks could not be exercised from the sandbox.
