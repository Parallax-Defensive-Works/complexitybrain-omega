# complexitybrain-omega
Persistent mechanism-potency campaigns for owned sandbox laboratories.

## Static sites on Cloudflare

`sites/<domain>/` holds the Cloudflare Workers (static assets) config for each site.
`sites/<domain>/public/` holds the site files and is **not committed**: this repository is
public and the sites are proprietary. Deploy from a machine that has the files:

```sh
npm ci
npm run fetch -- <domain>                 # mirror the live site, or:
npm run import -- <domain> public_html.zip   # import a cPanel archive (preferred)
npm run deploy -- <domain> --preview      # workers.dev preview, live site untouched
npm run deploy -- <domain>                # cutover / later updates (CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID)
```

The full runbook, including the cutover from Shinjiru, is in [docs/MIGRATION.md](docs/MIGRATION.md).
