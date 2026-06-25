# Iteration 006 — Legacy production guard adapter

## What changed

Iteration 006 closes the operator bypass gap left after the production attach guard. The production guard already refused stale or root-only runs through the new CLI. This iteration adds a legacy adapter so old status and attach scripts can call the same guard before they trust `current-run.json` or tail a campaign log.

Added `omega_frontier.legacy_guard` with:

- `legacy_status_preflight(...)` — guards legacy status paths with the same current-run and discovery predicates used by production attach.
- `legacy_attach_preflight(...)` — returns a safe `tail -F` argv only after the production guard allows attach.
- `legacy_cli_argv(...)` — builds guarded CLI argv for old shell scripts.
- `render_legacy_attach_shim(...)` — renders a POSIX shell block that must run before any raw tail command.
- `legacy_command_manifest(...)` — returns guarded status/attach commands, a command hash, an install note, and the POSIX shim text.

The CLI now includes:

```bash
python -m omega_frontier.cli legacy-shim \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<run> \
  --base-url https://example.test/ \
  --html-file /tmp/root.html
```

The command emits an installable manifest. Legacy scripts should prepend the `posix_attach_shim` before any direct `tail -F`, attach, or status logic that reads a run directory.

## Safety behavior

Legacy attach now has the same conservative predicates as production attach:

1. the requested state directory must be the current live run;
2. the current run pointer must have a live PID when PID data is present;
3. discovery evidence must exist;
4. discovery must prove enough eligible non-root routes;
5. refusal happens before any raw campaign log tailing.

A refused legacy attach exits with code `5`.

## Tests

Added:

```bash
python -m pytest tests/test_legacy_guard.py
```

Full validation for the branch:

```bash
python -m pytest \
  tests/test_mission_assurance.py \
  tests/test_runner_integration.py \
  tests/test_runtime_bridge.py \
  tests/test_cli.py \
  tests/test_active_guard.py \
  tests/test_legacy_guard.py
```

## Safe apply path

No data migration is required. To integrate safely:

1. Generate a shim manifest with `python -m omega_frontier.cli legacy-shim ...`.
2. Extract `posix_attach_shim` from the emitted JSON.
3. Prepend that shell block to any legacy attach/status script before the script reads `current-run.json`, attaches to a supervisor, or tails `omega-campaign.jsonl`.
4. Keep the new `python -m omega_frontier.cli attach` command as the direct operator path.

Older run directories remain readable for forensic use, but production attach should continue to refuse them until they have current-run identity and eligible discovery evidence.
