from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .runtime_bridge import append_campaign_event, campaign_log_path, emit_discovery_runtime, runtime_status

DISCOVERY_EVENT_TYPES = {"web_discovery_complete", "web_discovery_gate_failed"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append(
                {
                    "schema": "omega.production.guard.unreadable_event.v1",
                    "event_type": "unreadable_jsonl_line",
                    "raw_line_sha256_source": line,
                }
            )
    return events


def latest_discovery_event(state_dir: str | Path) -> dict[str, Any] | None:
    """Return the latest discovery gate event already written to a campaign log."""

    for event in reversed(_read_jsonl(campaign_log_path(state_dir))):
        if event.get("event_type") in DISCOVERY_EVENT_TYPES:
            return event
    return None


def discovery_gate_status(
    state_dir: str | Path,
    *,
    base_url: str | None = None,
    html: str | None = None,
    run_id: str | None = None,
    minimum_eligible: int = 2,
) -> dict[str, Any]:
    """Return a discovery gate status, emitting a fresh event when HTML is supplied.

    Production attach should not trust a run that only found `/`. If the caller
    supplies current HTML, this function emits the normal discovery event and
    uses that result. Otherwise it reuses the latest discovery event already in
    the campaign log. Missing discovery is a hard failure by default.
    """

    if html is not None:
        if not base_url:
            raise ValueError("base_url is required when html is supplied")
        result = emit_discovery_runtime(
            state_dir,
            base_url=base_url,
            html=html,
            run_id=run_id,
            minimum_eligible=minimum_eligible,
        )
        return {
            "schema": "omega.production.discovery_gate_status.v1",
            "source": "fresh_html",
            "payload": result["payload"],
            "event": result["event"],
        }

    existing = latest_discovery_event(state_dir)
    if existing:
        return {
            "schema": "omega.production.discovery_gate_status.v1",
            "source": "campaign_log",
            "payload": existing.get("payload", {}),
            "event": existing,
        }

    return {
        "schema": "omega.production.discovery_gate_status.v1",
        "source": "missing",
        "payload": {
            "schema": "omega.discovery.surface_event.v2",
            "eligible_gate": "fail",
            "failure_reason": "no discovery gate event found; production attach requires eligible-route proof",
            "minimum_eligible": minimum_eligible,
        },
        "event": None,
    }


def production_attach_guard(
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html: str | None = None,
    minimum_eligible: int = 2,
    require_discovery: bool = True,
    emit_event: bool = True,
) -> dict[str, Any]:
    """Enforce the production attach/status gate.

    A run may be tailed or attached only when both predicates are true:
    the candidate state directory is the current live run, and the discovery
    gate has proven an eligible surface beyond root-only discovery.
    """

    status = runtime_status(control_dir=control_dir, candidate_state_dir=state_dir)
    candidate = status.get("candidate") or {}
    attach_decision = status.get("attach_decision") or {}

    block_reasons: list[str] = []
    if not attach_decision.get("allowed"):
        block_reasons.append(str(attach_decision.get("reason") or "attach preflight failed"))

    discovery: dict[str, Any] | None = None
    if require_discovery:
        discovery = discovery_gate_status(
            state_dir,
            base_url=base_url,
            html=html,
            run_id=candidate.get("run_id"),
            minimum_eligible=minimum_eligible,
        )
        if discovery.get("payload", {}).get("eligible_gate") != "pass":
            block_reasons.append(
                str(
                    discovery.get("payload", {}).get("failure_reason")
                    or "eligible-route discovery gate failed"
                )
            )

    allowed = not block_reasons
    campaign_log = candidate.get("campaign_log") or str(campaign_log_path(state_dir))
    result = {
        "schema": "omega.production.attach_guard.v1",
        "allowed": allowed,
        "state": "allow_attach" if allowed else "refuse_attach",
        "block_reasons": block_reasons,
        "status": status,
        "discovery": discovery,
        "safe_tail_command": f"tail -F {campaign_log}" if allowed else None,
        "refused_tail_command": None if allowed else f"tail -F {campaign_log}",
        "operator_note": (
            "current live run and eligible-route discovery verified"
            if allowed
            else "attach/status refused before log tailing; fix the listed predicates first"
        ),
    }

    if emit_event:
        event = append_campaign_event(
            state_dir,
            "production_attach_guard",
            {
                "schema": result["schema"],
                "allowed": allowed,
                "state": result["state"],
                "block_reasons": block_reasons,
                "candidate_run_id": candidate.get("run_id"),
                "candidate_state_dir": candidate.get("state_dir"),
                "current_state_dir": (status.get("current") or {}).get("state_dir"),
                "discovery_gate": (discovery or {}).get("payload", {}).get("eligible_gate"),
            },
            run_id=candidate.get("run_id"),
        )
        result = dict(result) | {"event": event}

    return result


def production_status_summary(guard: Mapping[str, Any]) -> dict[str, Any]:
    """Return the operator-facing subset used by production status commands."""

    status = guard.get("status", {})
    return {
        "schema": "omega.production.status_summary.v1",
        "allowed": bool(guard.get("allowed")),
        "state": guard.get("state"),
        "block_reasons": list(guard.get("block_reasons", [])),
        "current_run_id": (status.get("current") or {}).get("run_id"),
        "candidate_run_id": (status.get("candidate") or {}).get("run_id"),
        "last_run_id": (status.get("last") or {}).get("run_id"),
        "discovery_gate": (guard.get("discovery") or {}).get("payload", {}).get("eligible_gate"),
        "safe_tail_command": guard.get("safe_tail_command"),
    }
