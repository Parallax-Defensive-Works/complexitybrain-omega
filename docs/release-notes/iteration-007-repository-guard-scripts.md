# Iteration 007 — Repository-Owned Production Guard Scripts

## What changed

Iteration 007 turns the production attach guard from a helper into repository-owned operator entrypoints. The repository now carries guarded scripts for production status, attach, and preflight. These scripts call the same `omega_frontier.cli` guard path before any raw status or tail behavior can occur.

Added:

- `omega_frontier.ops_scripts` for deterministic rendering, hashing, manifest generation, and local installation of guarded scripts.
- `scripts/omega-production-status` for status that requires the current-run predicate and discovery eligibility.
- `scripts/omega-attach` for attach that refuses stale or root-only runs before it can exec `tail`.
- `scripts/omega-preflight` for launch-time current-run and eligible-route validation.
- `python -m omega_frontier.cli install-scripts` to emit the script manifest or write executable copies into an operator-selected directory.

## Operator behavior

The scripts use explicit environment variables rather than reading ambiguous shell state:

```bash
export OMEGA_CONTROL_DIR=/root/.omega
export OMEGA_STATE_DIR=/root/.omega/runs/<run>
export OMEGA_BASE_URL=https://example.test/
export OMEGA_ROOT_HTML_FILE=/tmp/omega-root.html
export OMEGA_MINIMUM_ELIGIBLE=2
```

`omega-attach` prints the guard JSON, exits `5` when attach is refused, and only execs the safe tail argv returned by the production attach guard after the current-run and discovery gates pass.

## Safe apply path

Use the scripts directly from the repository:

```bash
sh scripts/omega-preflight
sh scripts/omega-production-status
sh scripts/omega-attach
```

Or install executable copies into a controlled operator bin directory:

```bash
python -m omega_frontier.cli install-scripts --output-dir /usr/local/lib/omega-frontier/bin
```

Then place that directory before old raw-tail scripts on `PATH`, or call the scripts by absolute path from service units. No existing run directory requires migration. Runs without eligible discovery evidence continue to be refused by production attach until fresh discovery is emitted.

## Validation

```bash
python -m pytest \
  tests/test_mission_assurance.py \
  tests/test_runner_integration.py \
  tests/test_runtime_bridge.py \
  tests/test_cli.py \
  tests/test_active_guard.py \
  tests/test_legacy_guard.py \
  tests/test_ops_scripts.py
```
