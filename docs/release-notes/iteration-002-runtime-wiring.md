# Iteration 002: Runtime Mission-Assurance Wiring

## Summary

This iteration wires the mission-assurance spine from Iteration 001 into runner-facing helpers. It remains additive, but it now gives the active Omega runner concrete payload builders for campaign start, attach/status truth, discovery gating, exposure evidence, live defense staging, Range Twin replay, backup truth manifests, detection engineering validation, sovereign controls, and executive/SOC reporting.

## Changes

- Adds `omega_frontier.runner_integration` with control-plane start helpers that write a current run pointer, preserve the prior pointer as `last-run.json`, and write a per-run `omega-run-pointer.json`.
- Adds attach/status decision logic that refuses stale or non-current run manifests before attaching.
- Adds a runner-ready discovery event that extracts same-origin HTML/JS routes, adds non-blocking well-known candidates, and fails the eligible-route gate instead of silently accepting root-only discovery.
- Adds mission-assurance bundle generation for each exposure. The bundle includes coverage, detection exports, live-defense staging, Range Twin replay capsule, backup/restore truth bundle, sovereign controls, executive/SOC summary, and a hash-linked evidence chain.
- Adds deterministic Range Twin replay comparison using request and response hashes.
- Adds live-defense effect verification and staged-control hashing.
- Adds persistence helper for evidence bundles under `mission-assurance/` inside a run state directory.
- Exports the new integration helpers from `omega_frontier.__init__`.
- Adds `tests/test_runner_integration.py` for the new runtime integration layer.

## Validation

Run:

```bash
python -m pytest tests/test_mission_assurance.py tests/test_runner_integration.py
```

## Safe apply path

This iteration does not change existing runner behavior until imported by the active CLI/runner code. Safe integration points:

1. Call `write_control_plane_start(...)` when a new campaign starts.
2. Use `attach_status(...)` in `status` and `attach` commands before opening logs.
3. Use `build_surface_discovery_event(...)` after fetching the target root HTML.
4. Append `mission_assurance_bundle(...)` after each exposure event.
5. Persist bundles with `write_mission_assurance_bundle(...)` when evidence export is enabled.

## Operational note

The backup truth bundle generated from a single exposure is a pipeline proof only. It deliberately says real restore proof still requires pre-backup and post-restore collection across an actual restore window.
