import json

from omega_frontier.runtime_bridge import (
    emit_discovery_runtime,
    emit_exposure_runtime,
    read_control_plane,
    runtime_report,
    runtime_status,
    start_campaign_runtime,
)


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_runtime_start_writes_current_pointer_and_campaign_start_event(tmp_path):
    result = start_campaign_runtime(
        control_dir=tmp_path / "control",
        state_dir=tmp_path / "run-a",
        run_id="run-a",
        pid=123,
        argv=("omega", "--url", "https://example.test"),
        config={"direct_run_default": True, "target": "https://example.test"},
    )

    manifest = result["manifest"]
    log = tmp_path / "run-a" / "omega-campaign.jsonl"
    events = _jsonl(log)

    assert manifest["role"] == "current"
    assert manifest["command_hash"]
    assert manifest["config_hash"]
    assert events[0]["event_type"] == "control_plane_start"
    assert events[0]["payload"]["state_dir"].endswith("run-a")


def test_runtime_status_separates_current_last_and_refuses_old_state(tmp_path):
    control_dir = tmp_path / "control"
    start_campaign_runtime(
        control_dir=control_dir,
        state_dir=tmp_path / "run-old",
        run_id="run-old",
        pid=111,
        argv=("omega",),
        config={"direct_run_default": True},
    )
    start_campaign_runtime(
        control_dir=control_dir,
        state_dir=tmp_path / "run-new",
        run_id="run-new",
        pid=222,
        argv=("omega",),
        config={"direct_run_default": True},
    )

    snapshot = read_control_plane(control_dir)
    stale = runtime_status(control_dir=control_dir, candidate_state_dir=tmp_path / "run-old", pid_checker=lambda pid: True)
    current = runtime_status(control_dir=control_dir, candidate_state_dir=tmp_path / "run-new", pid_checker=lambda pid: True)

    assert snapshot["current"]["run_id"] == "run-new"
    assert snapshot["last"]["run_id"] == "run-old"
    assert stale["attach_decision"]["allowed"] is False
    assert current["attach_decision"]["allowed"] is True
    assert current["current_last_separated"] is True


def test_runtime_discovery_appends_pass_and_root_only_failure(tmp_path):
    passed = emit_discovery_runtime(
        tmp_path,
        base_url="https://example.test/",
        html='<a href="/alpha">Alpha</a><script>const r="/wp-json/"</script>',
        run_id="run-1",
        minimum_eligible=3,
    )
    failed = emit_discovery_runtime(
        tmp_path,
        base_url="https://example.test/",
        html="",
        run_id="run-1",
        minimum_eligible=9,
    )
    events = _jsonl(tmp_path / "omega-campaign.jsonl")

    assert passed["payload"]["eligible_gate"] == "pass"
    assert failed["payload"]["eligible_gate"] == "fail"
    assert [event["event_type"] for event in events] == ["web_discovery_complete", "web_discovery_gate_failed"]


def test_runtime_exposure_persists_bundle_and_report(tmp_path):
    run = start_campaign_runtime(
        control_dir=tmp_path / "control",
        state_dir=tmp_path,
        run_id="run-report",
        pid=333,
        argv=("omega",),
        config={"direct_run_default": True},
    )
    exposure = emit_exposure_runtime(
        tmp_path,
        {
            "candidate_id": "omega-report-001",
            "mechanism_family": "backup_restore_equivalence",
            "target_path": "/feed/",
            "target_status": 200,
            "outcome_class": "clean_200",
            "risk_score": 0.81,
            "preapproved_low_risk": True,
            "request_envelope": {"method": "GET", "path": "/feed/"},
            "response_telemetry": {"target_status": 200},
            "body_sha256": "abc123",
        },
        run_manifest=run["manifest"],
    )
    report = runtime_report(tmp_path)
    events = _jsonl(tmp_path / "omega-campaign.jsonl")

    assert exposure["path"] is not None
    assert exposure["bundle"]["schema"] == "omega.mission_assurance.bundle.v2"
    assert events[-1]["event_type"] == "mission_assurance_bundle"
    assert report["bundle_count"] == 1
    assert report["coverage_heatmap"] == {"backup_restore_integrity": 1}
    assert report["detection_export_count"] == 4
    assert report["backup_restore_truth_bundle_count"] == 1
    assert report["mission_readiness_index"] > 0
