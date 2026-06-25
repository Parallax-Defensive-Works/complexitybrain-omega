import json

from omega_frontier.cli import main


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_cli_status_refuses_stale_candidate(tmp_path, capsys):
    control = tmp_path / "control"
    old_run = tmp_path / "old"
    new_run = tmp_path / "new"

    assert main([
        "start",
        "--control-dir",
        str(control),
        "--state-dir",
        str(old_run),
        "--run-id",
        "run-old",
        "--pid",
        "111",
        "--argv",
        "omega",
    ]) == 0
    assert main([
        "start",
        "--control-dir",
        str(control),
        "--state-dir",
        str(new_run),
        "--run-id",
        "run-new",
        "--pid",
        "222",
        "--argv",
        "omega",
    ]) == 0

    exit_code = main([
        "status",
        "--control-dir",
        str(control),
        "--candidate-state-dir",
        str(old_run),
        "--strict-attach",
    ])
    result = json.loads(capsys.readouterr().out.split("\n{", 2)[-1] if False else capsys.readouterr().out or "{}")

    assert exit_code == 2
    assert result["attach_decision"]["allowed"] is False
    assert result["current"]["run_id"] == "run-new"
    assert result["last"]["run_id"] == "run-old"


def test_cli_discovery_strict_gate_and_campaign_event(tmp_path, capsys):
    html = tmp_path / "root.html"
    html.write_text("", encoding="utf-8")

    exit_code = main([
        "discovery",
        "--state-dir",
        str(tmp_path),
        "--base-url",
        "https://example.test/",
        "--html-file",
        str(html),
        "--minimum-eligible",
        "9",
        "--strict-gate",
    ])
    result = json.loads(capsys.readouterr().out)
    events = _read_jsonl(tmp_path / "omega-campaign.jsonl")

    assert exit_code == 3
    assert result["payload"]["eligible_gate"] == "fail"
    assert events[-1]["event_type"] == "web_discovery_gate_failed"


def test_cli_preflight_passes_only_current_run_and_discovery_gate(tmp_path, capsys):
    control = tmp_path / "control"
    state = tmp_path / "state"
    html = tmp_path / "index.html"
    html.write_text('<a href="/alpha">Alpha</a><script>const r="/wp-json/"</script>', encoding="utf-8")

    assert main([
        "start",
        "--control-dir",
        str(control),
        "--state-dir",
        str(state),
        "--run-id",
        "run-current",
        "--pid",
        str(__import__("os").getpid()),
        "--argv",
        "omega",
    ]) == 0
    capsys.readouterr()

    exit_code = main([
        "preflight",
        "--control-dir",
        str(control),
        "--state-dir",
        str(state),
        "--base-url",
        "https://example.test/",
        "--html-file",
        str(html),
        "--minimum-eligible",
        "3",
    ])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["passed"] is True
    assert result["status"]["attach_decision"]["allowed"] is True
    assert result["discovery"]["payload"]["eligible_gate"] == "pass"


def test_cli_exposure_and_report(tmp_path, capsys):
    state = tmp_path / "state"
    observation = tmp_path / "observation.json"
    observation.write_text(
        json.dumps(
            {
                "candidate_id": "omega-cli-001",
                "mechanism_family": "backup_restore_equivalence",
                "target_path": "/feed/",
                "target_status": 200,
                "outcome_class": "clean_200",
                "risk_score": 0.77,
                "preapproved_low_risk": True,
                "request_envelope": {"method": "GET", "path": "/feed/"},
                "response_telemetry": {"target_status": 200},
                "body_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )

    assert main([
        "exposure",
        "--state-dir",
        str(state),
        "--observation-json",
        str(observation),
    ]) == 0
    exposure = json.loads(capsys.readouterr().out)
    assert exposure["path"] is not None

    assert main(["report", "--state-dir", str(state)]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["bundle_count"] == 1
    assert report["coverage_heatmap"] == {"backup_restore_integrity": 1}
    assert report["detection_export_count"] == 4
