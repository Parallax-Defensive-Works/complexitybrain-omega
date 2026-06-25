# Iteration 003 — Active Runtime Bridge

## What changed

Iteration 003 moves the mission-assurance spine from passive helper functions toward active campaign runtime use. It adds `omega_frontier.runtime_bridge`, a dependency-free adapter layer that the Omega CLI or campaign runner can import without changing the existing campaign engine first.

The bridge now provides:

- append-only campaign JSONL event emission with event hashes;
- campaign-start wiring that writes `current-run.json`, preserves `last-run.json`, writes the per-run pointer, and appends a `control_plane_start` event;
- truthful status/attach preflight that separates current, last, and candidate state directories before tailing a log;
- discovery event emission that records either `web_discovery_complete` or `web_discovery_gate_failed` and refuses root-only eligibility;
- exposure-level mission-assurance bundle emission and optional persistence under `mission-assurance/`;
- operator report summarization from persisted bundles, including coverage heatmap, validated controls, detection export count, backup truth bundle count, and a mission-readiness index.

## Why this matters

The record from the live runs showed that Omega could generate useful evidence, but the product still needed a clean runtime boundary: one place where campaign start, attach/status, discovery, exposure evidence, and reporting become hashable, append-only events. This iteration supplies that boundary.

The bridge does not perform destructive actions. Live-defense output remains staged or policy-bounded according to the existing action ladder. Backup/restore truth output remains honest: it records pressure and comparison payloads, but it does not claim real restore equivalence without separately collected pre- and post-restore manifests.

## Tests

Run:

```bash
python -m pytest tests/test_mission_assurance.py tests/test_runner_integration.py tests/test_runtime_bridge.py
```

## Safe apply path

This remains additive. To wire into the active runner:

1. Replace direct `current-run.json` writes with `start_campaign_runtime(...)` at campaign start.
2. Run `runtime_status(...)` before any `status` or `attach` command tails a campaign log.
3. After root HTML fetch, call `emit_discovery_runtime(...)` with the discovered HTML and the configured eligible-route minimum.
4. After each exposure event, call `emit_exposure_runtime(...)` with the observation and current run manifest.
5. For operator reports, call `runtime_report(state_dir)` and include the returned coverage heatmap and evidence counts.

No migration is required for older run directories. They simply lack the new `mission-assurance/` bundle directory and will report zero persisted bundles.
