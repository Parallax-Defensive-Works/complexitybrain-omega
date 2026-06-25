from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mission_assurance import (
    CoverageRecord,
    DiscoveredRoute,
    LiveDefenseDecision,
    RunPointer,
    canonical_json,
    choose_live_defense_action,
    compare_restore_manifests,
    coverage_for_observation,
    detection_exports,
    discover_routes_from_html,
    eligible_routes,
    executive_summary_payload,
    refuse_stale_attach,
    sha256_text,
    sovereign_pack_manifest,
    truth_manifest,
    utc_now,
)


CONTROL_CURRENT = "current-run.json"
CONTROL_LAST = "last-run.json"
RUN_POINTER = "omega-run-pointer.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pointer_from_manifest(manifest: Mapping[str, Any]) -> RunPointer:
    return RunPointer(
        run_id=str(manifest["run_id"]),
        pid=manifest.get("pid"),
        state_dir=str(manifest["state_dir"]),
        campaign_log=str(manifest["campaign_log"]),
        argv=tuple(manifest.get("argv", ())),
        config=dict(manifest.get("config", {})),
        started_at_utc=manifest.get("started_at_utc"),
    )


def write_control_plane_start(
    *,
    control_dir: str | os.PathLike[str],
    state_dir: str | os.PathLike[str],
    run_id: str,
    pid: int | None,
    argv: Sequence[str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a truthful current-run pointer and preserve the prior pointer as last-run.

    The runner can call this at campaign start. The manifest records command and
    config hashes and makes direct-run identity explicit before any attach or
    status command trusts a background process.
    """

    control_root = Path(control_dir)
    state_root = Path(state_dir)
    campaign_log = state_root / "omega-campaign.jsonl"
    pointer = RunPointer(
        run_id=run_id,
        pid=pid,
        state_dir=str(state_root),
        campaign_log=str(campaign_log),
        argv=tuple(argv),
        config=dict(config),
        started_at_utc=utc_now(),
    )
    manifest = pointer.manifest() | {
        "schema": "omega.control_plane.current_run.v2",
        "role": "current",
        "direct_run_default": bool(config.get("direct_run_default", True)),
        "background_requires_explicit_service_config": True,
    }

    current_path = control_root / CONTROL_CURRENT
    previous = _read_json(current_path)
    if previous:
        last = dict(previous)
        last["role"] = "last"
        last["superseded_at_utc"] = manifest["started_at_utc"]
        _write_json(control_root / CONTROL_LAST, last)

    _write_json(current_path, manifest)
    _write_json(state_root / RUN_POINTER, manifest)
    return manifest


def attach_status(
    *,
    candidate_manifest: Mapping[str, Any],
    current_manifest: Mapping[str, Any] | None,
    pid_exists: bool | None,
) -> dict[str, Any]:
    """Return an attach decision and refuse stale/non-current runs."""

    candidate = _pointer_from_manifest(candidate_manifest)
    current = _pointer_from_manifest(current_manifest) if current_manifest else None
    try:
        refuse_stale_attach(candidate, current, pid_exists=pid_exists)
    except RuntimeError as exc:
        return {
            "schema": "omega.control_plane.attach_decision.v1",
            "allowed": False,
            "reason": str(exc),
            "candidate_state_dir": candidate.state_dir,
            "current_state_dir": current.state_dir if current else None,
        }
    return {
        "schema": "omega.control_plane.attach_decision.v1",
        "allowed": True,
        "reason": "current run pointer and live pid verified",
        "candidate_state_dir": candidate.state_dir,
        "current_state_dir": current.state_dir if current else None,
        "command_hash": candidate.command_hash,
        "config_hash": candidate.config_hash,
    }


def build_surface_discovery_event(base_url: str, html: str, *, minimum_eligible: int = 2) -> dict[str, Any]:
    """Build a non-sitemap-dependent discovery event with an eligible-route gate."""

    routes = discover_routes_from_html(base_url, html)
    eligible = eligible_routes(routes, minimum=minimum_eligible)
    by_source: dict[str, int] = {}
    for route in routes:
        by_source[route.source] = by_source.get(route.source, 0) + 1
    return {
        "schema": "omega.discovery.surface_event.v2",
        "base_url": base_url,
        "route_count": len(routes),
        "eligible_route_count": len(eligible),
        "eligible_gate": "pass",
        "sitemap_dependency": "non_blocking",
        "sources": by_source,
        "routes": [route.export() for route in routes],
        "eligible_routes": [route.export() for route in eligible],
    }


def build_surface_discovery_failure(base_url: str, html: str, *, minimum_eligible: int = 2) -> dict[str, Any]:
    """Return a failure event instead of letting root-only discovery pass silently."""

    routes = discover_routes_from_html(base_url, html)
    try:
        eligible_routes(routes, minimum=minimum_eligible)
        gate = "pass"
        reason = None
    except RuntimeError as exc:
        gate = "fail"
        reason = str(exc)
    return {
        "schema": "omega.discovery.surface_event.v2",
        "base_url": base_url,
        "route_count": len(routes),
        "eligible_gate": gate,
        "failure_reason": reason,
        "sitemap_dependency": "non_blocking",
        "routes": [route.export() for route in routes],
    }


@dataclass(frozen=True)
class RangeTwinReplayCapsule:
    capsule_id: str
    candidate_id: str
    request_hash: str
    response_hash: str
    observation_hash: str
    created_at_utc: str

    def export(self) -> dict[str, Any]:
        return {
            "schema": "omega.range_twin.replay_capsule.v1",
            "capsule_id": self.capsule_id,
            "candidate_id": self.candidate_id,
            "request_hash": self.request_hash,
            "response_hash": self.response_hash,
            "observation_hash": self.observation_hash,
            "created_at_utc": self.created_at_utc,
        }


def range_twin_capsule(observation: Mapping[str, Any]) -> RangeTwinReplayCapsule:
    candidate_id = str(observation.get("candidate_id") or "unknown")
    request = observation.get("request_envelope") or observation.get("request") or {}
    response = observation.get("response_telemetry") or observation.get("response") or {}
    observation_hash = sha256_text(canonical_json(dict(observation)))
    request_hash = sha256_text(canonical_json(request))
    response_hash = sha256_text(canonical_json(response))
    capsule_id = "range-twin-" + sha256_text("|".join([candidate_id, request_hash, response_hash]))[:20]
    return RangeTwinReplayCapsule(
        capsule_id=capsule_id,
        candidate_id=candidate_id,
        request_hash=request_hash,
        response_hash=response_hash,
        observation_hash=observation_hash,
        created_at_utc=utc_now(),
    )


def compare_range_twin_replay(original: RangeTwinReplayCapsule, replay: RangeTwinReplayCapsule) -> dict[str, Any]:
    request_match = original.request_hash == replay.request_hash
    response_match = original.response_hash == replay.response_hash
    return {
        "schema": "omega.range_twin.replay_comparison.v1",
        "original_capsule_id": original.capsule_id,
        "replay_capsule_id": replay.capsule_id,
        "deterministic_request_match": request_match,
        "deterministic_response_match": response_match,
        "reproduced": request_match and response_match,
    }


def hash_linked_event_chain(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    for index, event in enumerate(events):
        body = {
            "index": index,
            "previous_hash": previous_hash,
            "event": dict(event),
        }
        event_hash = sha256_text(canonical_json(body))
        chain.append(
            {
                "schema": "omega.evidence.hash_link.v1",
                "index": index,
                "previous_hash": previous_hash,
                "event_hash": event_hash,
                "event_type": event.get("event_type") or event.get("schema") or "unknown",
            }
        )
        previous_hash = event_hash
    return chain


def backup_truth_from_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    route = str(observation.get("target_path") or observation.get("route") or "/")
    status = observation.get("target_status") or observation.get("status")
    body_hash = observation.get("body_sha256") or observation.get("response_sha256") or "unknown"
    pre = truth_manifest("pre_backup", {route: {"status": status, "body_hash": body_hash}})
    post = truth_manifest("post_restore", {route: {"status": status, "body_hash": body_hash}})
    comparison = compare_restore_manifests(pre, post)
    return {
        "schema": "omega.backup_truth.bundle.v1",
        "pre_backup_manifest": pre,
        "backup_window_marker": {
            "schema": "omega.backup_truth.window_marker.v1",
            "marker_id": "backup-window-" + sha256_text(route)[:16],
            "route": route,
            "created_at_utc": utc_now(),
        },
        "post_restore_manifest": post,
        "restore_comparison": comparison,
        "honesty_note": "synthetic same-observation manifests only prove pipeline wiring; real restore proof requires pre/post collection across an actual restore window",
    }


def detection_validation_payload(record: CoverageRecord) -> dict[str, Any]:
    exports = detection_exports(record)
    return {
        "schema": "omega.detection_engineering.validation_payload.v1",
        "candidate_id": record.candidate_id,
        "mission_phase": record.mission_phase.value,
        "exports": exports,
        "validation": {
            "expected_event_fields": [
                "omega.candidate_id",
                "omega.mission_phase",
                "omega.control",
                "omega.evidence_hash",
            ],
            "control_saw_it": None,
            "control_blocked_it": None,
            "alert_created": None,
            "ticket_created": None,
        },
    }


def stage_live_defense_control(decision: LiveDefenseDecision, *, policy_hash: str | None = None) -> dict[str, Any]:
    staged = {
        "schema": "omega.live_defense.staged_control.v1",
        "decision": decision.export(),
        "policy_hash_before": policy_hash,
        "staged_at_utc": utc_now(),
        "rollback": decision.rollback,
        "state": "executed" if not decision.requires_approval and int(decision.level) >= 4 else "staged",
    }
    staged["staged_control_hash"] = sha256_text(canonical_json(staged))
    return staged


def verify_live_defense_effect(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_risk = float(before.get("risk_score", 0.0))
    after_risk = float(after.get("risk_score", 0.0))
    before_blocked = bool(before.get("blocked", False))
    after_blocked = bool(after.get("blocked", False))
    effective = after_blocked or after_risk < before_risk
    return {
        "schema": "omega.live_defense.effect_verification.v1",
        "effective": effective,
        "risk_delta": round(after_risk - before_risk, 6),
        "block_state_changed": before_blocked != after_blocked,
    }


def mission_assurance_bundle(
    observation: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any] | None = None,
    sovereign_offline: bool = True,
) -> dict[str, Any]:
    """Create the event payload the runner can append after each exposure."""

    record = coverage_for_observation(observation)
    defense = choose_live_defense_action(observation)
    range_capsule = range_twin_capsule(observation)
    backup_truth = backup_truth_from_observation(observation)
    detection = detection_validation_payload(record)
    staged_control = stage_live_defense_control(defense, policy_hash=(run_manifest or {}).get("config_hash"))
    summary = executive_summary_payload([record])
    sovereign = sovereign_pack_manifest(offline=sovereign_offline, no_telemetry=True)
    evidence_events = [
        {"event_type": "coverage", "payload": record.export()},
        {"event_type": "detection_validation", "payload": detection},
        {"event_type": "live_defense", "payload": staged_control},
        {"event_type": "range_twin", "payload": range_capsule.export()},
        {"event_type": "backup_truth", "payload": backup_truth},
    ]
    chain = hash_linked_event_chain(evidence_events)
    bundle = {
        "schema": "omega.mission_assurance.bundle.v2",
        "run_id": (run_manifest or {}).get("run_id"),
        "candidate_id": record.candidate_id,
        "coverage": record.export(),
        "detection_engineering": detection,
        "live_defense": staged_control,
        "range_twin_replay": range_capsule.export(),
        "backup_restore_truth": backup_truth,
        "sovereign_pack": sovereign,
        "executive_soc_summary": summary,
        "evidence_chain": chain,
    }
    bundle["bundle_hash"] = sha256_text(canonical_json(bundle))
    return bundle


def write_mission_assurance_bundle(
    state_dir: str | os.PathLike[str], observation: Mapping[str, Any], *, run_manifest: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    bundle = mission_assurance_bundle(observation, run_manifest=run_manifest)
    out_dir = Path(state_dir) / "mission-assurance"
    out_path = out_dir / f"{bundle['candidate_id']}-{bundle['bundle_hash'][:16]}.json"
    _write_json(out_path, bundle)
    return bundle | {"path": str(out_path)}
