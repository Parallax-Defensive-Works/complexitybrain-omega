from omega_frontier.runner_integration import (
    attach_status,
    build_surface_discovery_event,
    build_surface_discovery_failure,
    compare_range_twin_replay,
    hash_linked_event_chain,
    mission_assurance_bundle,
    range_twin_capsule,
    verify_live_defense_effect,
    write_control_plane_start,
    write_mission_assurance_bundle,
)


def test_control_plane_start_preserves_last_and_refuses_stale_attach(tmp_path):
    control_dir = tmp_path / "control"
    old_state = tmp_path / "old"
    new_state = tmp_path / "new"

    old_manifest = write_control_plane_start(
        control_dir=control_dir,
        state_dir=old_state,
        run_id="run-old",
        pid=100,
        argv=("omega", "--direct"),
        config={"direct_run_default": True, "target": "https://example.test"},
    )
    new_manifest = write_control_plane_start(
        control_dir=control_dir,
        state_dir=new_state,
        run_id="run-new",
        pid=200,
        argv=("omega", "--direct"),
        config={"direct_run_default": True, "target": "https://example.test"},
    )

    assert (control_dir / "current-run.json").exists()
    assert (control_dir / "last-run.json").exists()
    assert (new_state / "omega-run-pointer.json").exists()
    assert new_manifest["command_hash"]
    assert new_manifest["config_hash"]

    stale_decision = attach_status(candidate_manifest=old_manifest, current_manifest=new_manifest, pid_exists=True)
    current_decision = attach_status(candidate_manifest=new_manifest, current_manifest=new_manifest, pid_exists=True)

    assert stale_decision["allowed"] is False
    assert "refusing to attach" in stale_decision["reason"]
    assert current_decision["allowed"] is True


def test_surface_discovery_event_is_not_root_only_or_sitemap_dependent():
    html = """
    <a href="/practice-areas">Practice Areas</a>
    <script>window.__routes = ["/wp-json/", "/feed/"];</script>
    """
    event = build_surface_discovery_event("https://example.test/", html, minimum_eligible=3)

    assert event["eligible_gate"] == "pass"
    assert event["sitemap_dependency"] == "non_blocking"
    assert event["eligible_route_count"] >= 3
    assert any(route["url"].endswith("/practice-areas") for route in event["routes"])
    assert any(route["source"] == "javascript_route_literal" for route in event["routes"])


def test_surface_discovery_failure_returns_gate_payload_for_root_only():
    event = build_surface_discovery_failure("https://example.test/", "", minimum_eligible=9)

    assert event["eligible_gate"] == "fail"
    assert "minimum eligible-route gate failed" in event["failure_reason"]
    assert event["routes"]


def test_mission_assurance_bundle_wires_coverage_detection_defense_range_and_truth():
    observation = {
        "candidate_id": "omega-backup-001",
        "mechanism_family": "backup_cache_log_churn",
        "target_path": "/feed/",
        "target_status": 200,
        "outcome_class": "clean_200",
        "risk_score": 0.82,
        "preapproved_low_risk": True,
        "request_envelope": {"method": "GET", "path": "/feed/"},
        "response_telemetry": {"target_status": 200},
        "body_sha256": "abc123",
    }
    bundle = mission_assurance_bundle(observation, run_manifest={"run_id": "run-1", "config_hash": "cfg"})

    assert bundle["schema"] == "omega.mission_assurance.bundle.v2"
    assert bundle["coverage"]["mission_phase"] == "backup_restore_integrity"
    assert "sigma" in bundle["detection_engineering"]["exports"]
    assert bundle["live_defense"]["state"] == "executed"
    assert bundle["range_twin_replay"]["candidate_id"] == "omega-backup-001"
    assert bundle["backup_restore_truth"]["backup_window_marker"]["route"] == "/feed/"
    assert bundle["sovereign_pack"]["controls"]["no_external_telemetry"] is True
    assert bundle["executive_soc_summary"]["record_count"] == 1
    assert bundle["evidence_chain"][-1]["previous_hash"] == bundle["evidence_chain"][-2]["event_hash"]
    assert bundle["bundle_hash"]


def test_range_twin_comparison_is_deterministic_on_request_and_response_hashes():
    observation = {
        "candidate_id": "omega-001",
        "request_envelope": {"method": "POST", "path": "/"},
        "response_telemetry": {"target_status": 200},
    }
    original = range_twin_capsule(observation)
    same = range_twin_capsule(observation | {"elapsed_ms": 123})
    changed = range_twin_capsule(observation | {"response_telemetry": {"target_status": 500}})

    assert compare_range_twin_replay(original, same)["reproduced"] is True
    assert compare_range_twin_replay(original, changed)["reproduced"] is False


def test_hash_linked_chain_and_live_defense_verification_are_explicit():
    chain = hash_linked_event_chain(
        [
            {"event_type": "coverage", "payload": {"a": 1}},
            {"event_type": "detection", "payload": {"b": 2}},
        ]
    )
    verification = verify_live_defense_effect(
        {"risk_score": 0.8, "blocked": False}, {"risk_score": 0.2, "blocked": True}
    )

    assert chain[0]["previous_hash"] == "GENESIS"
    assert chain[1]["previous_hash"] == chain[0]["event_hash"]
    assert verification["effective"] is True
    assert verification["risk_delta"] < 0
    assert verification["block_state_changed"] is True


def test_write_mission_assurance_bundle_persists_evidence_bundle(tmp_path):
    bundle = write_mission_assurance_bundle(
        tmp_path,
        {
            "candidate_id": "omega-persist-001",
            "mechanism_family": "backup_restore_equivalence",
            "target_path": "/",
            "target_status": 200,
            "request_envelope": {"path": "/"},
            "response_telemetry": {"target_status": 200},
        },
        run_manifest={"run_id": "run-persist", "config_hash": "cfg"},
    )

    assert bundle["path"].endswith(".json")
    assert (tmp_path / "mission-assurance").exists()
