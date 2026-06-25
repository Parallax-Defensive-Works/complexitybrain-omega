# Iteration 004: Operator CLI for Runtime Bridge

## What changed

Iteration 004 adds a small dependency-free CLI around the mission-assurance runtime bridge. Operators can now invoke the runtime bridge without writing Python glue.

New module:

```bash
python -m omega_frontier.cli
```

Commands added:

```bash
python -m omega_frontier.cli start \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<run> \
  --run-id <run-id> \
  --pid <pid> \
  --argv omega --url https://example.test

python -m omega_frontier.cli status \
  --control-dir /root/.omega \
  --candidate-state-dir /root/.omega/runs/<run> \
  --strict-attach

python -m omega_frontier.cli discovery \
  --state-dir /root/.omega/runs/<run> \
  --base-url https://example.test/ \
  --html-file /tmp/root.html \
  --minimum-eligible 3 \
  --strict-gate

python -m omega_frontier.cli exposure \
  --state-dir /root/.omega/runs/<run> \
  --observation-json /tmp/observation.json

python -m omega_frontier.cli report \
  --state-dir /root/.omega/runs/<run>

python -m omega_frontier.cli preflight \
  --control-dir /root/.omega \
  --state-dir /root/.omega/runs/<run> \
  --base-url https://example.test/ \
  --html-file /tmp/root.html \
  --minimum-eligible 3
```

## Safety behavior

`status --strict-attach` exits with code `2` when the candidate state directory is not the current live run. `discovery --strict-gate` exits with code `3` when route discovery fails the eligible-route gate. `preflight` exits with code `4` unless both attach status and discovery gate pass.

The CLI only writes through the existing runtime bridge. It does not add destructive behavior, credential collection, persistence, lateral movement, or out-of-scope actions.

## Tests

Added:

```bash
python -m pytest tests/test_cli.py
```

Full safe validation:

```bash
python -m pytest \
  tests/test_mission_assurance.py \
  tests/test_runner_integration.py \
  tests/test_runtime_bridge.py \
  tests/test_cli.py
```

## Safe apply path

No migration is required. Existing run directories remain readable. The active runner can adopt this iteration by shelling out to `python -m omega_frontier.cli preflight` before attach/report operations, then moving to direct imports once the production CLI is wired.
