# Omega Iteration 001 — Mission Assurance Spine

## What changed

This iteration adds a small, testable mission-assurance package under `omega_frontier/`. It is intentionally dependency-free so it can be used by the existing runner, CLI, reports, and later sovereign/offline bundles without adding runtime risk.

## Product upgrades implemented

### Control-plane trust

The new `RunPointer` manifest records the run id, PID, state directory, campaign log, command hash, and config hash. `classify_run_pointer()` separates current, last, stale, and unknown runs. `refuse_stale_attach()` fails closed before an operator attaches to a non-current run.

### Autonomous endpoint discovery gate

`discover_routes_from_html()` extracts same-origin routes from HTML `href`, `src`, and `action` attributes and simple JavaScript route literals. It adds non-blocking well-known candidates for robots, sitemap, feeds, OpenAPI, Swagger, GraphQL, and WordPress REST profiles. `eligible_routes()` enforces a minimum route count so Omega does not silently treat `/` as a complete surface.

### Omega Mission Behavior Graph

`MissionPhase`, `BehaviorNode`, and `default_mission_behavior_graph()` define the proprietary Omega Mission Behavior Graph. The graph exports compatible tactic labels for interoperability while keeping Omega's own behavior vocabulary as the source of truth.

### Coverage engine

`CoverageRecord` and `coverage_for_observation()` map observations to mission phase, compatible tactic, control, evidence, and course of action. Backup and restore observations now map to `backup_restore_integrity` and the `backup_restore_truth_engine` control.

### Live defense action ladder

`choose_live_defense_action()` implements the bounded ladder from observe-only through emergency mission shield. The function only executes low-risk controls without approval when the signal is explicitly preapproved. Higher-risk controls are staged with rollback language.

### Detection engineering exports

`detection_exports()` emits Sigma, Splunk SPL, Microsoft Sentinel KQL, and Elastic query artifacts from a coverage record.

### Backup/restore truth engine

`truth_manifest()` creates pre-backup and post-restore truth manifests. `compare_restore_manifests()` compares them and emits equivalence, changed keys, and a restore fidelity index.

### Sovereign deployment pack

`sovereign_pack_manifest()` records air-gap, offline update, no-telemetry, customer-owned rules, signed package, RBAC/ABAC, multi-person approval, immutable audit, and data-residency controls with a stable control hash.

### Executive/SOC reporting

`executive_summary_payload()` emits a compact mission-readiness payload with covered phases, validated controls, record count, and generation time.

## Validation

Added `tests/test_mission_assurance.py` covering:

- current vs stale run pointer classification;
- stale attach refusal;
- command and config hashing;
- HTML and JavaScript route discovery;
- eligible-route minimum gate;
- proprietary behavior graph export;
- live-defense action ladder decisions;
- coverage mapping and detection exports;
- backup truth manifest equivalence and drift;
- sovereign pack and executive summary payloads.

Run locally:

```bash
python -m pytest tests/test_mission_assurance.py
```

## Safe apply path

This change is additive. It does not alter the existing runner behavior until imported by the runner or CLI.

Recommended integration sequence:

```bash
python -m pytest tests/test_mission_assurance.py
```

Then wire the existing Omega runner in this order:

1. Emit `RunPointer.manifest()` at campaign start.
2. Use `refuse_stale_attach()` in the attach/status path before streaming a campaign log.
3. Pass root HTML through `discover_routes_from_html()` and enforce `eligible_routes()` before running treatment specimens.
4. For every exposure event, emit a `CoverageRecord.export()` payload.
5. For backup/restore campaigns, write `truth_manifest("pre_backup", ...)` and `truth_manifest("post_restore", ...)`, then report `compare_restore_manifests()`.
6. Generate detection exports and executive/SOC summary artifacts from coverage records.

## Known limits

The implementation is a safe spine, not a full runner integration. The next iteration should connect these primitives into the active command/status/attach flow and the web-discovery execution path so the current campaign cannot regress to stale supervisor attachment or root-only eligibility.
