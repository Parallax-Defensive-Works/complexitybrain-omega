from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlparse


ISO = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def command_hash(argv: Sequence[str]) -> str:
    return sha256_text(canonical_json(list(argv)))


def config_hash(config: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(config))


class RunState(str, Enum):
    CURRENT = "current"
    LAST = "last"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RunPointer:
    run_id: str
    pid: int | None
    state_dir: str
    campaign_log: str
    argv: tuple[str, ...] = ()
    config: Mapping[str, Any] = field(default_factory=dict)
    started_at_utc: str | None = None

    @property
    def command_hash(self) -> str:
        return command_hash(self.argv)

    @property
    def config_hash(self) -> str:
        return config_hash(self.config)

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "omega.control_plane.run_pointer.v1",
            "run_id": self.run_id,
            "pid": self.pid,
            "state_dir": self.state_dir,
            "campaign_log": self.campaign_log,
            "argv": list(self.argv),
            "command_hash": self.command_hash,
            "config_hash": self.config_hash,
            "started_at_utc": self.started_at_utc,
        }


def classify_run_pointer(
    candidate: RunPointer,
    current: RunPointer | None,
    last: RunPointer | None = None,
    *,
    pid_exists: bool | None = None,
) -> RunState:
    if current and candidate.state_dir == current.state_dir and candidate.run_id == current.run_id:
        if pid_exists is False:
            return RunState.STALE
        return RunState.CURRENT
    if last and candidate.state_dir == last.state_dir and candidate.run_id == last.run_id:
        return RunState.LAST
    if pid_exists is False:
        return RunState.STALE
    return RunState.UNKNOWN


def refuse_stale_attach(candidate: RunPointer, current: RunPointer | None, *, pid_exists: bool | None = None) -> None:
    state = classify_run_pointer(candidate, current, pid_exists=pid_exists)
    if state is not RunState.CURRENT:
        raise RuntimeError(
            "refusing to attach non-current run "
            f"state={state.value} candidate={candidate.state_dir!r} "
            f"current={current.state_dir if current else None!r}"
        )


class MissionPhase(str, Enum):
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_STAGING = "resource_staging"
    ACCESS_PRESSURE = "access_pressure"
    EXECUTION_PRESSURE = "execution_pressure"
    PERSISTENCE_SIMULATION = "persistence_simulation"
    PRIVILEGE_PATH_PRESSURE = "privilege_path_pressure"
    STEALTH_VALIDATION = "stealth_detection_avoidance_validation"
    DEFENSE_IMPAIRMENT_SIMULATION = "defense_impairment_simulation"
    IDENTITY_EXPOSURE_VALIDATION = "identity_credential_exposure_validation"
    DISCOVERY = "discovery"
    LATERAL_PATH_MODELING = "lateral_path_modeling"
    COLLECTION_SIMULATION = "collection_simulation"
    COMMAND_CHANNEL_SIMULATION = "command_channel_simulation"
    EXFILTRATION_SIMULATION = "exfiltration_simulation"
    IMPACT_RECOVERY_DEGRADATION = "impact_recovery_degradation"
    MISSION_RECOVERY = "mission_recovery"
    BACKUP_RESTORE_INTEGRITY = "backup_restore_integrity"
    OPERATOR_DECISION_LATENCY = "operator_decision_latency"


ATTACK_COMPATIBLE_EXPORT = {
    MissionPhase.RECONNAISSANCE: "Reconnaissance",
    MissionPhase.RESOURCE_STAGING: "Resource Development",
    MissionPhase.ACCESS_PRESSURE: "Initial Access",
    MissionPhase.EXECUTION_PRESSURE: "Execution",
    MissionPhase.PERSISTENCE_SIMULATION: "Persistence",
    MissionPhase.PRIVILEGE_PATH_PRESSURE: "Privilege Escalation",
    MissionPhase.STEALTH_VALIDATION: "Defense Evasion",
    MissionPhase.DEFENSE_IMPAIRMENT_SIMULATION: "Defense Evasion",
    MissionPhase.IDENTITY_EXPOSURE_VALIDATION: "Credential Access",
    MissionPhase.DISCOVERY: "Discovery",
    MissionPhase.LATERAL_PATH_MODELING: "Lateral Movement",
    MissionPhase.COLLECTION_SIMULATION: "Collection",
    MissionPhase.COMMAND_CHANNEL_SIMULATION: "Command and Control",
    MissionPhase.EXFILTRATION_SIMULATION: "Exfiltration",
    MissionPhase.IMPACT_RECOVERY_DEGRADATION: "Impact",
    MissionPhase.MISSION_RECOVERY: "Impact",
    MissionPhase.BACKUP_RESTORE_INTEGRITY: "Impact",
    MissionPhase.OPERATOR_DECISION_LATENCY: "Impact",
}


@dataclass(frozen=True)
class BehaviorNode:
    node_id: str
    phase: MissionPhase
    description: str
    safe_validation: str
    compatible_tactic: str | None = None

    def export(self) -> dict[str, Any]:
        return {
            "schema": "omega.mission_behavior.node.v1",
            "node_id": self.node_id,
            "phase": self.phase.value,
            "description": self.description,
            "safe_validation": self.safe_validation,
            "compatible_tactic": self.compatible_tactic or ATTACK_COMPATIBLE_EXPORT.get(self.phase),
        }


def default_mission_behavior_graph() -> list[BehaviorNode]:
    return [
        BehaviorNode(
            node_id=f"ombg.{phase.value}",
            phase=phase,
            description=phase.value.replace("_", " "),
            safe_validation="bounded authorized defensive validation; no credential theft, persistence, exfiltration, or out-of-scope mutation",
        )
        for phase in MissionPhase
    ]


class DefenseActionLevel(int, Enum):
    OBSERVE_ONLY = 0
    RECOMMEND = 1
    DRAFT_CONTROL = 2
    STAGE_PENDING_APPROVAL = 3
    EXECUTE_PREAPPROVED_LOW_RISK = 4
    EMERGENCY_MISSION_SHIELD = 5


@dataclass(frozen=True)
class LiveDefenseDecision:
    level: DefenseActionLevel
    action: str
    target: str
    reason: str
    requires_approval: bool
    rollback: str | None = None

    def export(self) -> dict[str, Any]:
        return {
            "schema": "omega.live_defense.decision.v1",
            "level": int(self.level),
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
            "rollback": self.rollback,
        }


def choose_live_defense_action(signal: Mapping[str, Any]) -> LiveDefenseDecision:
    route = str(signal.get("target_path") or signal.get("route") or "/")
    risk = float(signal.get("risk_score", 0.0))
    blocked = bool(signal.get("blocked", False))
    preapproved = bool(signal.get("preapproved_low_risk", False))
    mission_critical = bool(signal.get("mission_critical", False))

    if blocked:
        return LiveDefenseDecision(
            level=DefenseActionLevel.OBSERVE_ONLY,
            action="continue_observation",
            target=route,
            reason="existing control is already blocking the observed behavior",
            requires_approval=False,
        )
    if risk >= 0.92 and mission_critical:
        return LiveDefenseDecision(
            level=DefenseActionLevel.EMERGENCY_MISSION_SHIELD,
            action="stage_route_shield",
            target=route,
            reason="high mission risk on a critical route",
            requires_approval=not preapproved,
            rollback="remove staged route shield and restore prior WAF/CDN policy hash",
        )
    if risk >= 0.75 and preapproved:
        return LiveDefenseDecision(
            level=DefenseActionLevel.EXECUTE_PREAPPROVED_LOW_RISK,
            action="apply_rate_limit",
            target=route,
            reason="risk exceeds low-risk preapproval threshold",
            requires_approval=False,
            rollback="restore previous rate-limit rule",
        )
    if risk >= 0.55:
        return LiveDefenseDecision(
            level=DefenseActionLevel.STAGE_PENDING_APPROVAL,
            action="stage_waf_rule",
            target=route,
            reason="risk warrants a reversible staged control",
            requires_approval=True,
            rollback="discard staged rule",
        )
    if risk >= 0.30:
        return LiveDefenseDecision(
            level=DefenseActionLevel.DRAFT_CONTROL,
            action="draft_detection_and_control",
            target=route,
            reason="weak but actionable signal requires analyst review",
            requires_approval=True,
        )
    return LiveDefenseDecision(
        level=DefenseActionLevel.RECOMMEND,
        action="recommend_monitoring",
        target=route,
        reason="signal does not justify control staging",
        requires_approval=False,
    )


@dataclass(frozen=True)
class DiscoveredRoute:
    url: str
    source: str
    confidence: float
    reason: str

    def export(self) -> dict[str, Any]:
        return {
            "schema": "omega.discovery.route.v1",
            "url": self.url,
            "source": self.source,
            "confidence": self.confidence,
            "reason": self.reason,
        }


_HREF_RE = re.compile(r"""(?:href|src|action)=[\"']([^\"']+)[\"']""", re.IGNORECASE)
_JS_ROUTE_RE = re.compile(r"""[\"'](/(?:api/|wp-json/|admin/|login|feed/?|sitemap\.xml|[A-Za-z0-9._~!$&'()*+,;=:@/-]{2,}))[\"']""")


def same_origin(base_url: str, maybe_url: str) -> bool:
    base = urlparse(base_url)
    parsed = urlparse(maybe_url)
    return (not parsed.netloc) or (parsed.scheme, parsed.netloc) == (base.scheme, base.netloc)


def normalize_url(base_url: str, candidate: str) -> str | None:
    if not candidate or candidate.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    joined = urljoin(base_url, candidate)
    parsed = urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None
    return parsed._replace(fragment="").geturl()


def discover_routes_from_html(base_url: str, html: str) -> list[DiscoveredRoute]:
    seen: dict[str, DiscoveredRoute] = {}

    def add(raw: str, source: str, confidence: float, reason: str) -> None:
        url = normalize_url(base_url, raw)
        if not url or not same_origin(base_url, url):
            return
        previous = seen.get(url)
        if previous is None or confidence > previous.confidence:
            seen[url] = DiscoveredRoute(url=url, source=source, confidence=confidence, reason=reason)

    add("/", "root", 1.0, "root is always eligible")
    for match in _HREF_RE.finditer(html):
        add(match.group(1), "html_attribute", 0.82, "same-origin href/src/action")
    for match in _JS_ROUTE_RE.finditer(html):
        add(match.group(1), "javascript_route_literal", 0.68, "same-origin route literal")

    for well_known in ("/robots.txt", "/sitemap.xml", "/feed/", "/wp-json/", "/openapi.json", "/swagger.json", "/graphql"):
        add(well_known, "well_known_profile", 0.45, "non-blocking well-known route candidate")

    return sorted(seen.values(), key=lambda r: (-r.confidence, r.url))


def eligible_routes(routes: Iterable[DiscoveredRoute], *, minimum: int = 2) -> list[DiscoveredRoute]:
    eligible = [route for route in routes if route.confidence >= 0.50 or urlparse(route.url).path == "/"]
    if len(eligible) < minimum:
        raise RuntimeError(
            f"minimum eligible-route gate failed: found {len(eligible)} eligible routes; required {minimum}"
        )
    return eligible


@dataclass(frozen=True)
class CoverageRecord:
    scenario_id: str
    candidate_id: str
    mission_phase: MissionPhase
    control: str
    evidence: str
    course_of_action: str

    def export(self) -> dict[str, Any]:
        return {
            "schema": "omega.coverage.record.v1",
            "scenario_id": self.scenario_id,
            "candidate_id": self.candidate_id,
            "mission_phase": self.mission_phase.value,
            "compatible_tactic": ATTACK_COMPATIBLE_EXPORT[self.mission_phase],
            "control": self.control,
            "evidence": self.evidence,
            "course_of_action": self.course_of_action,
        }


def coverage_for_observation(observation: Mapping[str, Any]) -> CoverageRecord:
    family = str(observation.get("mechanism_family") or observation.get("family") or "unknown")
    candidate_id = str(observation.get("candidate_id") or "unknown")
    evidence_state = str(observation.get("honesty_result_class") or observation.get("backup_evidence_state") or "")
    if "restore" in evidence_state or "backup" in family:
        phase = MissionPhase.BACKUP_RESTORE_INTEGRITY
        control = "backup_restore_truth_engine"
        course = "collect_pre_backup_manifest_and_post_restore_manifest"
    elif "identity" in family or "credential" in family:
        phase = MissionPhase.IDENTITY_EXPOSURE_VALIDATION
        control = "identity_conditional_access_review"
        course = "verify_identity_policy_and_token_scope"
    elif "exfil" in family:
        phase = MissionPhase.EXFILTRATION_SIMULATION
        control = "dlp_and_egress_policy_validation"
        course = "validate_synthetic_payload_detection"
    else:
        phase = MissionPhase.RECONNAISSANCE
        control = "surface_observation"
        course = "continue_observation"
    return CoverageRecord(
        scenario_id=f"scenario.{family}",
        candidate_id=candidate_id,
        mission_phase=phase,
        control=control,
        evidence=str(observation.get("evidence") or observation.get("outcome_class") or "pending"),
        course_of_action=course,
    )


def detection_exports(record: CoverageRecord) -> dict[str, str]:
    title = f"Omega {record.mission_phase.value} {record.scenario_id}"
    return {
        "sigma": "\n".join(
            [
                f"title: {title}",
                "status: experimental",
                "logsource:",
                "  product: omega",
                "detection:",
                "  selection:",
                f"    omega.candidate_id: {record.candidate_id}",
                f"    omega.mission_phase: {record.mission_phase.value}",
                "  condition: selection",
            ]
        ),
        "spl": f'index=* omega.candidate_id="{record.candidate_id}" omega.mission_phase="{record.mission_phase.value}"',
        "kql": f'OmegaEvents | where CandidateId == "{record.candidate_id}" and MissionPhase == "{record.mission_phase.value}"',
        "elastic": canonical_json(
            {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"omega.candidate_id": record.candidate_id}},
                            {"term": {"omega.mission_phase": record.mission_phase.value}},
                        ]
                    }
                }
            }
        ),
    }


def truth_manifest(name: str, facts: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "omega.backup_truth.manifest.v1",
        "name": name,
        "facts": dict(facts),
    }
    body["manifest_hash"] = sha256_text(canonical_json(body["facts"]))
    return body


def compare_restore_manifests(pre_backup: Mapping[str, Any], post_restore: Mapping[str, Any]) -> dict[str, Any]:
    pre_facts = dict(pre_backup.get("facts", {}))
    post_facts = dict(post_restore.get("facts", {}))
    changed = {
        key: {"pre": pre_facts.get(key), "post": post_facts.get(key)}
        for key in sorted(set(pre_facts) | set(post_facts))
        if pre_facts.get(key) != post_facts.get(key)
    }
    return {
        "schema": "omega.backup_truth.restore_comparison.v1",
        "pre_manifest_hash": pre_backup.get("manifest_hash"),
        "post_manifest_hash": post_restore.get("manifest_hash"),
        "equivalent": not changed,
        "changed": changed,
        "restore_fidelity_index": 1.0
        if not changed
        else max(0.0, 1.0 - len(changed) / max(1, len(set(pre_facts) | set(post_facts)))),
    }


def sovereign_pack_manifest(*, offline: bool = True, no_telemetry: bool = True) -> dict[str, Any]:
    controls = {
        "air_gapped_install": offline,
        "offline_update_bundles": offline,
        "no_external_telemetry": no_telemetry,
        "customer_owned_rules": True,
        "signed_package_manifests": True,
        "rbac_abac": True,
        "multi_person_approval": True,
        "immutable_audit_logs": True,
        "data_residency_controls": True,
    }
    return {
        "schema": "omega.sovereign_deployment.pack.v1",
        "controls": controls,
        "control_hash": sha256_text(canonical_json(controls)),
    }


def executive_summary_payload(records: Sequence[CoverageRecord]) -> dict[str, Any]:
    phases = sorted({record.mission_phase.value for record in records})
    controls = sorted({record.control for record in records})
    return {
        "schema": "omega.reporting.executive_soc_summary.v1",
        "mission_readiness_index": 0.0 if not records else round(min(1.0, len(controls) / max(1, len(MissionPhase))), 4),
        "covered_phases": phases,
        "validated_controls": controls,
        "record_count": len(records),
        "generated_at_utc": utc_now(),
    }
