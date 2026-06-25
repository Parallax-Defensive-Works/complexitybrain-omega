from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .mission_assurance import canonical_json, sha256_text, utc_now
from .runner_integration import (
    CONTROL_CURRENT,
    CONTROL_LAST,
    RUN_POINTER,
    attach_status,
    build_surface_discovery_event,
    build_surface_discovery_failure,
    mission_assurance_bundle,
    write_control_plane_start,
)

CAMPAIGN_LOG = "omega-campaign.jsonl"
MISSION_ASSURANCE_DIR = "mission-assurance"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def campaign_log_path(state_dir: str | os.PathLike[str]) -> Path:
    return Path(state_dir) / CAMPAIGN_LOG


def append_campaign_event(
    state_dir: str | os.PathLike[str],
    event_type: str,
    payload: Mapping[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Append one Omega campaign JSONL event with a stable event hash.

    This is the runner-facing bridge from the additive mission-assurance
    package into the active campaign log. It keeps the campaign log append-only
    and gives every emitted payload a hash that can be cross-checked against the
    persisted evidence bundle.
    """

    ts_utc = utc_now()
    body = {
        "schema": "complexitybrain.omega.campaign.jsonl.v2",
        "event_type": event_type,
        "run_id": run_id or payload.get("run_id"),
        "ts_utc": ts_utc,
        "payload": dict(payload),
    }
    body["event_hash"] = sha256_text(canonical_json(body))
    body["event_id"] = "event-" + body["event_hash"][:20]

    path = campaign_log_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def pid_exists_from_system(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_control_plane(control_dir: str | os.PathLike[str]) -> dict[str, Any]:
    root = Path(control_dir)
    return {
        "schema": "omega.control_plane.snapshot.v1",
        "current": _read_json(root / CONTROL_CURRENT),
        "last": _read_json(root / CONTROL_LAST),
    }


def start_campaign_runtime(
    *,
    control_dir: str | os.PathLike[str],
    state_dir: str | os.PathLike[str],
    run_id: str,
    pid: int | None,
    argv: Sequence[str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Wire campaign start into current-run manifests and campaign JSONL."""

    manifest = write_control_plane_start(
        control_dir=control_dir,
        state_dir=state_dir,
        run_id=run_id,
        pid=pid,
        argv=argv,
        config=config,
    )
    event = append_campaign_event(state_dir, "control_plane_start", manifest, run_id=run_id)
    return {"schema": "omega.runtime.start_result.v1", "manifest": manifest, "event": event}


def runtime_status(
    *,
    control_dir: str | os.PathLike[str],
    candidate_state_dir: str | os.PathLike[str] | None = None,
    pid_checker: Callable[[int | None], bool | None] = pid_exists_from_system,
) -> dict[str, Any]:
    """Return truthful current/last/stale status before attach or tail.

    The active CLI can call this before `status` or `attach`. The result refuses
    non-current state directories and separates the current pointer from the last
    pointer so a stale supervisor cannot be mistaken for the live run.
    """

    snapshot = read_control_plane(control_dir)
    current = snapshot["current"]
    last = snapshot["last"]
    candidate = None
    if candidate_state_dir is not None:
        candidate = _read_json(Path(candidate_state_dir) / RUN_POINTER)
    elif current is not None:
        candidate = current

    if candidate is None:
        decision = {
            "schema": "omega.control_plane.attach_decision.v1",
            "allowed": False,
            "reason": "no candidate run pointer found",
            "candidate_state_dir": str(candidate_state_dir) if candidate_state_dir else None,
            "current_state_dir": current.get("state_dir") if current else None,
        }
    else:
        decision = attach_status(
            candidate_manifest=candidate,
            current_manifest=current,
            pid_exists=pid_checker(candidate.get("pid")),
        )

    return {
        "schema": "omega.runtime.status.v1",
        "current": current,
        "last": last,
        "candidate": candidate,
        "attach_decision": decision,
        "current_last_separated": bool(current and last and current.get("state_dir") != last.get("state_dir")),
    }


def emit_discovery_runtime(
    state_dir: str | os.PathLike[str],
    *,
    base_url: str,
    html: str,
    run_id: str | None = None,
    minimum_eligible: int = 2,
) -> dict[str, Any]:
    """Append a discovery pass/fail event and never let root-only pass silently."""

    try:
        payload = build_surface_discovery_event(base_url, html, minimum_eligible=minimum_eligible)
        event_type = "web_discovery_complete"
    except RuntimeError:
        payload = build_surface_discovery_failure(base_url, html, minimum_eligible=minimum_eligible)
        event_type = "web_discovery_gate_failed"
    payload = dict(payload) | {"minimum_eligible": minimum_eligible}
    event = append_campaign_event(state_dir, event_type, payload, run_id=run_id)
    return {"schema": "omega.runtime.discovery_result.v1", "payload": payload, "event": event}


def emit_exposure_runtime(
    state_dir: str | os.PathLike[str],
    observation: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any] | None = None,
    persist_evidence: bool = True,
) -> dict[str, Any]:
    """Build, optionally persist, and append the mission-assurance bundle."""

    bundle = mission_assurance_bundle(observation, run_manifest=run_manifest)
    path: str | None = None
    if persist_evidence:
        out_dir = Path(state_dir) / MISSION_ASSURANCE_DIR
        out_path = out_dir / f"{bundle['candidate_id']}-{bundle['bundle_hash'][:16]}.json"
        _write_json(out_path, bundle)
        path = str(out_path)
        bundle = dict(bundle) | {"path": path}
    event = append_campaign_event(
        state_dir,
        "mission_assurance_bundle",
        bundle,
        run_id=(run_manifest or {}).get("run_id"),
    )
    return {"schema": "omega.runtime.exposure_result.v1", "bundle": bundle, "event": event, "path": path}


def runtime_report(state_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Summarize persisted mission-assurance bundles for operator reports."""

    bundle_dir = Path(state_dir) / MISSION_ASSURANCE_DIR
    bundles: list[dict[str, Any]] = []
    if bundle_dir.exists():
        for path in sorted(bundle_dir.glob("*.json")):
            loaded = _read_json(path)
            if loaded:
                bundles.append(loaded)

    coverage_heatmap: dict[str, int] = {}
    controls: dict[str, int] = {}
    detections = 0
    restore_truth = 0
    for bundle in bundles:
        phase = bundle.get("coverage", {}).get("mission_phase", "unknown")
        control = bundle.get("coverage", {}).get("control", "unknown")
        coverage_heatmap[phase] = coverage_heatmap.get(phase, 0) + 1
        controls[control] = controls.get(control, 0) + 1
        detections += len(bundle.get("detection_engineering", {}).get("exports", {}))
        if bundle.get("backup_restore_truth"):
            restore_truth += 1

    return {
        "schema": "omega.runtime.report.v1",
        "bundle_count": len(bundles),
        "coverage_heatmap": dict(sorted(coverage_heatmap.items())),
        "validated_controls": dict(sorted(controls.items())),
        "detection_export_count": detections,
        "backup_restore_truth_bundle_count": restore_truth,
        "latest_bundle_hashes": [bundle.get("bundle_hash") for bundle in bundles[-10:]],
        "mission_readiness_index": round(min(1.0, len(controls) / 18), 4) if bundles else 0.0,
    }
