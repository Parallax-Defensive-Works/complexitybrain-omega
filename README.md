# complexitybrain-omega

Persistent mechanism-potency campaigns for owned sandbox laboratories.

## Production guard entrypoints

Omega production status and attach must pass through the frontier guard before any run log is trusted or tailed. The repository provides guarded POSIX entrypoints:

```bash
export OMEGA_CONTROL_DIR=/root/.omega
export OMEGA_STATE_DIR=/root/.omega/runs/<run>
export OMEGA_BASE_URL=https://example.test/
export OMEGA_ROOT_HTML_FILE=/tmp/omega-root.html
export OMEGA_MINIMUM_ELIGIBLE=2

sh scripts/omega-preflight
sh scripts/omega-production-status
sh scripts/omega-attach
```

`omega-attach` refuses stale or root-only runs before it can exec `tail`. The refusal code is `5`. Use `python -m omega_frontier.cli install-scripts --output-dir <dir>` to install executable copies for service units or operator shells.

## Guarded systemd launch pack

Iteration 008 adds a direct-run systemd pack under `deploy/systemd/`. The unit template runs the same preflight before the runner starts, so a stale `current-run.json` or root-only discovery blocks launch rather than producing a misleading background process.

```bash
python -m omega_frontier.cli systemd-pack --output-dir /tmp/omega-systemd
install -d /etc/omega-frontier /etc/systemd/system/omega-frontier@.service.d /var/lib/omega-frontier
install -m 0644 /tmp/omega-systemd/omega-frontier.env /etc/omega-frontier/omega-frontier.env
install -m 0644 /tmp/omega-systemd/omega-frontier@.service /etc/systemd/system/omega-frontier@.service
install -m 0644 /tmp/omega-systemd/10-omega-frontier-hardening.conf /etc/systemd/system/omega-frontier@.service.d/10-omega-frontier-hardening.conf
systemctl daemon-reload
```

Before starting an instance, capture fresh root HTML into `OMEGA_ROOT_HTML_FILE` and review `/etc/omega-frontier/omega-frontier.env`. The environment template defaults to local evidence, disabled telemetry, append-only audit language, deterministic Range Twin replay, and approval-required live controls.
