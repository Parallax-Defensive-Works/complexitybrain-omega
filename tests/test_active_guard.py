import json
import os

from omega_frontier.active_guard import latest_discovery_event, production_attach_guard, production_status_summary
from omega_frontier.cli import main
from omega_frontier.runtime_bridge import emit_discovery_runtime, start_campaign_runtime


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _start(control, state, run_id="run-current"):
    return start_campaign_runtime(
        control_dir=control,
        state_dir=state,
        run_id=run_id,
        pid=os.getpid(),
        argv=("omega", "--direct"),
        config={"direct_run_default": True},
    )


def test_production_attach_refuses_missing_discovery_gate(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    _start(control, state)

    guard = production_attach_guard(control_dir=control, state_dir=state)

    assert guard["allowed"] is False
    assert guard["state"] == "refuse_attach"
    assert guard["safe_tail_command"] is None
    assert "no discovery gate event found" in " ".join(guard["block_reasons"])


def test_production_attach_allows_current_run_with_eligible_discovery(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    html = '<a href="/alpha">A</a><a href="/feed/">Feed</a><script>const api="/wp-json/"</script>'
    _start(control, state)

    guard = production_attach_guard(
        control_dir=control,
        state_dir=state,
        base_url="https://example.test/",
        html=html,
        minimum_eligible=3,
    )
    events = _read_jsonl(state / "omega-campaign.jsonl")

    assert guard["allowed"] is True
    assert guard["safe_tail_command"].endswith("omega-campaign.jsonl")
    assert guard["discovery"]["payload"]["eligible_gate"] == "pass"
    assert events[-1]["event_type"] == "production_attach_guard"


def test_production_attach_reuses_latest_discovery_gate(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    _start(control, state)
    emit_discovery_runtime(
        state,
        base_url="https://example.test/",
        html='<a href="/alpha">A</a><a href="/beta">B</a>',
        run_id="run-current",
        minimum_eligible=2,
    )

    guard = production_attach_guard(control_dir=control, state_dir=state, minimum_eligible=2)
    latest = latest_discovery_event(state)

    assert guard["allowed"] is True
    assert guard["discovery"]["source"] == "campaign_log"
    assert latest["event_type"] == "web_discovery_complete"


def test_production_attach_refuses_stale_run_even_with_good_discovery(tmp_path):
    control = tmp_path / "control"
    old_state = tmp_path / "old"
    new_state = tmp_path / "new"
    _start(control, old_state, run_id="run-old")
    emit_discovery_runtime(
        old_state,
        base_url="https://example.test/",
        html='<a href="/alpha">A</a><a href="/beta">B</a>',
        run_id="run-old",
        minimum_eligible=2,
    )
    _start(control, new_state, run_id="run-new")

    guard = production_attach_guard(control_dir=control, state_dir=old_state, minimum_eligible=2)

    assert guard["allowed"] is False
    assert any("stale" in reason or "current" in reason for reason in guard["block_reasons"])
    assert guard["status"]["current"]["run_id"] == "run-new"


def test_production_status_summary_is_operator_safe(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    _start(control, state)
    guard = production_attach_guard(control_dir=control, state_dir=state, emit_event=False)
    summary = production_status_summary(guard)

    assert summary["schema"] == "omega.production.status_summary.v1"
    assert summary["allowed"] is False
    assert "status" not in summary
    assert "event" not in summary


def test_cli_attach_and_production_status_use_strict_guard_by_default(tmp_path, capsys):
    control = tmp_path / "control"
    state = tmp_path / "state"
    html = tmp_path / "index.html"
    html.write_text('<a href="/alpha">A</a><a href="/beta">B</a>', encoding="utf-8")
    _start(control, state)

    assert main([
        "production-status",
        "--control-dir",
        str(control),
        "--state-dir",
        str(state),
    ]) == 5
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["allowed"] is False

    assert main([
        "attach",
        "--control-dir",
        str(control),
        "--state-dir",
        str(state),
        "--base-url",
        "https://example.test/",
        "--html-file",
        str(html),
        "--minimum-eligible",
        "2",
    ]) == 0
    allowed = json.loads(capsys.readouterr().out)
    assert allowed["allowed"] is True
    assert allowed["safe_tail_command"]
