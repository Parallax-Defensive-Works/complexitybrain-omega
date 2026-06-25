# Iteration 005 — Production attach guard

## What changed

This iteration turns the prior preflight helper into a production attach/status guard. Operators now have a strict default path that refuses to tail or attach a run unless the run is both the current live run and has eligible-route discovery evidence.

## Added

- `omega_frontier.active_guard.latest_discovery_event(...)` reads the latest discovery pass/fail event from `omega-campaign.jsonl`.
- `omega_frontier.active_guard.discovery_gate_status(...)` emits a fresh discovery gate when HTML is supplied, or reuses the latest campaign-log discovery event when it is already present.
- `omega_frontier.active_guard.production_attach_guard(...)` blocks attach/status when:
  - the candidate state directory is stale or not the current run;
  - the candidate PID is not live;
  - discovery is missing; or
  - discovery failed the eligible-route gate.
- `omega_frontier.active_guard.production_status_summary(...)` provides a compact operator-safe status payload.
- `python -m omega_frontier.cli production-status` returns strict production status and exits `5` when attach is refused.
- `python -m omega_frontier.cli attach` returns a safe tail command only after the guard passes and exits `5` when attach is refused.

## Safety behavior

The default production path is conservative. It does not silently tail stale logs. It does not treat `/` as a sufficient surface. It writes a `production_attach_guard` event to the campaign log so refused and allowed attach decisions are auditable.

The `--no-discovery-gate` flag exists only as a development escape hatch. Production use should keep the discovery gate enabled.

## Validation

Run:

```bash
git fetch origin omega-iteration-1-mission-assurance
git checkout omega-iteration-1-mission-assurance
python -m pytest \
  tests/test_mission_assurance.py \
  tests/test_runner_integration.py \
  tests/test_runtime_bridge.py \
  tests/test_cli.py \
  tests/test_active_guard.py
```

## Safe apply commands

Start or refresh a current run pointer:

```bash
python -m omega_frontier.cli start \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<state-dir> \
  --run-id <run-id> \
  --pid <pid> \
  --argv omega --direct
```

Check production status without tailing:

```bash
python -m omega_frontier.cli production-status \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<state-dir>
```

Attach only after current-run and discovery gates pass:

```bash
python -m omega_frontier.cli attach \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<state-dir> \
  --base-url https://example.test/ \
  --html-file /tmp/root.html
```

The command prints `safe_tail_command` only when attach is allowed.

## Migration

No migration is required for old run directories. Old runs that lack a current run pointer or eligible-route discovery event are refused by default until a current run manifest and discovery evidence are present.
