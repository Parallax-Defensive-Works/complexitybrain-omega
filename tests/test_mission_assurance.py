import pytest

from omega_frontier.mission_assurance import (
    DefenseActionLevel,
    MissionPhase,
    RunPointer,
    RunState,
    choose_live_defense_action,
    classify_run_pointer,
    compare_restore_manifests,
    coverage_for_observation,
    default_mission_behavior_graph,
    detection_exports,
    discover_routes_from_html,
    eligible_routes,
    executive_summary_payload,
    refuse_stale_attach,
    sovereign_pack_manifest,
    truth_manifest,
)


def test_run_pointer_hashes_and_refuses_stale_attach():
    current = RunPointer(
        run_id="run-current",
        pid=123,
        state_dir="/state/current",
        campaign_log="/state/current/omega-campaign.jsonl",
        argv=("omega", "--direct"),
        config={"direct_run_default": True},
    )
    stale = RunPointer(
        run_id="run-old",
        pid=456,
        state_dir="/state/old",
        campaign_log="/state/old/omega-campaign.jsonl",
        argv=("omega", "--background"),
        config={"direct_run_default": False},
    )

    manifest = current.manifest()
    assert manifest["command_hash"]
    assert manifest["config_hash"]
    assert classify_run_pointer(current, current, pid_exists=True) is RunState.CURRENT
    assert classify_run_pointer(stale, current, pid_exists=False) is RunState.STALE
    with pytest.raises(RuntimeError, match="refusing to attach"):
        refuse_stale_attach(stale, current, pid_exists=False)


def test_discovery_extracts_same_origin_html_js_and_enforces_gate():
    html = '''
    <a href="/about">About</a>
    <form action="/login"></form>
    <script>const route = "/wp-json/"; const off = "https://evil.example/x";</script>
    '''
    routes = discover_routes_from_html("https://example.com/", html)
    urls = {route.url for route in routes}

    assert "https://example.com/" in urls
    assert "https://example.com/about" in urls
    assert "https://example.com/login" in urls
    assert "https://example.com/wp-json/" in urls
    assert all("evil.example" not in route.url for route in routes)
    assert len(eligible_routes(routes, minimum=3)) >= 3


def test_mission_behavior_graph_is_proprietary_and_attack_compatible():
    graph = default_mission_behavior_graph()
    exported = [node.export() for node in graph]

    assert len(graph) == len(MissionPhase)
    assert any(node["node_id"] == "ombg.backup_restore_integrity" for node in exported)
    assert all("compatible_tactic" in node for node in exported)


def test_live_defense_ladder_stages_and_executes_only_with_preapproval():
    staged = choose_live_defense_action({"target_path": "/admin", "risk_score": 0.80})
    executed = choose_live_defense_action(
        {"target_path": "/api", "risk_score": 0.80, "preapproved_low_risk": True}
    )
    emergency = choose_live_defense_action(
        {"target_path": "/checkout", "risk_score": 0.95, "mission_critical": True}
    )

    assert staged.level is DefenseActionLevel.STAGE_PENDING_APPROVAL
    assert staged.requires_approval is True
    assert executed.level is DefenseActionLevel.EXECUTE_PREAPPROVED_LOW_RISK
    assert executed.requires_approval is False
    assert emergency.level is DefenseActionLevel.EMERGENCY_MISSION_SHIELD
    assert emergency.rollback


def test_coverage_and_detection_exports_for_backup_observation():
    record = coverage_for_observation(
        {
            "candidate_id": "omega-cache-log-001",
            "mechanism_family": "backup_cache_log_churn",
            "outcome_class": "clean_200",
            "honesty_result_class": "restore_unverified_pressure_only",
        }
    )
    exports = detection_exports(record)

    assert record.mission_phase is MissionPhase.BACKUP_RESTORE_INTEGRITY
    assert record.control == "backup_restore_truth_engine"
    assert "omega-cache-log-001" in exports["sigma"]
    assert "OmegaEvents" in exports["kql"]
    assert "omega.candidate_id" in exports["elastic"]


def test_backup_truth_comparison_proves_or_denies_equivalence():
    pre = truth_manifest("pre_backup", {"/": "hash-a", "/feed/": "hash-b"})
    same_post = truth_manifest("post_restore", {"/": "hash-a", "/feed/": "hash-b"})
    changed_post = truth_manifest("post_restore", {"/": "hash-a", "/feed/": "hash-c"})

    same = compare_restore_manifests(pre, same_post)
    changed = compare_restore_manifests(pre, changed_post)

    assert same["equivalent"] is True
    assert same["restore_fidelity_index"] == 1.0
    assert changed["equivalent"] is False
    assert changed["changed"]["/feed/"] == {"pre": "hash-b", "post": "hash-c"}


def test_sovereign_pack_and_executive_summary_payloads_are_hashable():
    pack = sovereign_pack_manifest()
    record = coverage_for_observation(
        {"candidate_id": "c1", "mechanism_family": "backup_restore_equivalence"}
    )
    summary = executive_summary_payload([record])

    assert pack["controls"]["air_gapped_install"] is True
    assert pack["controls"]["no_external_telemetry"] is True
    assert pack["control_hash"]
    assert summary["record_count"] == 1
    assert summary["mission_readiness_index"] > 0
