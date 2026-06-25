# Iteration 008 — Guarded systemd launch pack

## What changed

Iteration 008 adds a production launch pack for operators who want Omega supervised by systemd without returning to the stale-background-process ambiguity that the control-plane work removed.

The new pack includes:

- `omega_frontier.service_units`, a deterministic renderer for a systemd unit template, environment file, hardening drop-in, operator README, and install manifest;
- `python -m omega_frontier.cli systemd-pack`, which emits the manifest or writes the launch-pack files into a selected directory;
- committed launch-pack artifacts under `deploy/systemd/`;
- tests covering preflight-before-start ordering, sovereign/no-telemetry defaults, hardening directives, manifest hashes, file modes, and CLI output.

## Production behavior

The systemd unit is a direct-run service. It does not start a background shell that later becomes ambiguous. The unit sets `OMEGA_STATE_DIR` from the instance name and runs the same current-run and eligible-route preflight used by `omega-preflight` before the runner starts.

If the run pointer is stale, the PID/status preflight fails, root HTML is missing, or discovery cannot prove at least the configured number of eligible non-root routes, `ExecStartPre` fails and the campaign does not start.

## Sovereign defaults

The environment template defaults to:

- telemetry disabled;
- network telemetry disabled;
- local-only data residency;
- append-only audit language;
- approval-required live-control execution;
- deterministic Range Twin replay.

These values are defaults for the deployment pack. Operators still must review and edit `/etc/omega-frontier/omega-frontier.env` for the target lab before enabling a service instance.

## Safe apply path

```bash
git fetch origin omega-iteration-1-mission-assurance
git checkout omega-iteration-1-mission-assurance
python -m omega_frontier.cli systemd-pack --output-dir /tmp/omega-systemd
install -d /etc/omega-frontier /etc/systemd/system/omega-frontier@.service.d /var/lib/omega-frontier
install -m 0644 /tmp/omega-systemd/omega-frontier.env /etc/omega-frontier/omega-frontier.env
install -m 0644 /tmp/omega-systemd/omega-frontier@.service /etc/systemd/system/omega-frontier@.service
install -m 0644 /tmp/omega-systemd/10-omega-frontier-hardening.conf /etc/systemd/system/omega-frontier@.service.d/10-omega-frontier-hardening.conf
systemctl daemon-reload
```

Before starting, capture fresh root HTML into the path configured as `OMEGA_ROOT_HTML_FILE`:

```bash
python - <<'PY'
from pathlib import Path
from urllib.request import urlopen
url = 'https://example.test/'
Path('/var/lib/omega-frontier').mkdir(parents=True, exist_ok=True)
Path('/var/lib/omega-frontier/root.html').write_text(urlopen(url, timeout=30).read().decode('utf-8', 'replace'), encoding='utf-8')
PY
```

Then start an instance whose name is the run directory basename:

```bash
systemctl start omega-frontier@omega-state-YYYYMMDD-HHMMSS.service
systemctl status omega-frontier@omega-state-YYYYMMDD-HHMMSS.service
```

## Validation

```bash
python -m pytest \
  tests/test_mission_assurance.py \
  tests/test_runner_integration.py \
  tests/test_runtime_bridge.py \
  tests/test_cli.py \
  tests/test_active_guard.py \
  tests/test_legacy_guard.py \
  tests/test_ops_scripts.py \
  tests/test_service_units.py
```

No migration is required for older run directories. Existing commands remain additive. Production service starts should use the systemd pack only after the environment file is reviewed and fresh discovery evidence is supplied.
