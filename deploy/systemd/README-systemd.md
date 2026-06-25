# Omega guarded systemd launch pack

This pack starts Omega only after the same current-run and eligible-route preflight used by `omega-preflight` succeeds.
The runner is a direct process under systemd. It does not rely on a stale supervisor pointer or a background shell tail.

## Install

```bash
install -d /etc/omega-frontier /etc/systemd/system/omega-frontier@.service.d /var/lib/omega-frontier
install -m 0644 omega-frontier.env /etc/omega-frontier/omega-frontier.env
install -m 0644 omega-frontier@.service /etc/systemd/system/omega-frontier@.service
install -m 0644 10-omega-frontier-hardening.conf /etc/systemd/system/omega-frontier@.service.d/10-omega-frontier-hardening.conf
systemctl daemon-reload
```

Before starting, capture fresh root HTML into the file named by `OMEGA_ROOT_HTML_FILE`. The preflight refuses root-only discovery.

```bash
python - <<'PY'
from pathlib import Path
from urllib.request import urlopen
url = 'https://example.test/'
Path('/var/lib/omega-frontier').mkdir(parents=True, exist_ok=True)
Path('/var/lib/omega-frontier/root.html').write_text(urlopen(url, timeout=30).read().decode('utf-8', 'replace'), encoding='utf-8')
PY
systemctl start omega-frontier@omega-state-YYYYMMDD-HHMMSS.service
systemctl status omega-frontier@omega-state-YYYYMMDD-HHMMSS.service
```

The environment defaults disable telemetry, keep evidence local, use append-only audit language, and require approval before live control execution.
