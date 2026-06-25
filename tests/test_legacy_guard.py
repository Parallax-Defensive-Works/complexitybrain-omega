import json
import os

from omega_frontier.cli import main
from omega_frontier.legacy_guard import (
    PRODUCTION_ATTACH_REFUSED_EXIT,
    legacy_attach_preflight,
    legacy_command_manifest,
    legacy_status_preflight,
    render_legacy_attach_shim,
)
from omega_frontier.runtime_bridge import emit_discovery_runtime, start_campaign_runtime


def _start(control, state, run_id="run-current"):
    return start_campaign_runtime(
        control_dir=control,
        state_dir=state,
        run_id=run_id,
        pid=os.getpid(),
        argv=("omega", "--direct"),
        config={"direct_run_default": True},
    )


def _eligible_html():
    return '<a href="/alpha">A</a><a href="/beta">B</a><script>const api="/wp-json/"</script>'


def test_legacy_attach_preflight_refuses_before_tail_when_discovery_missing(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    _start(control, state)

    result = legacy_attach_preflight(control_dir=control, state_dir=state)

    assert result["allowed"] is False
    assert result["exit_code"] == PRODUCTION_ATTACH_REFUSED_EXIT
    assert result["safe_tail_argv"] is None
    assert result["safe_tail_command"] is None
    assert result["refused_tail_command"].endswith("omega-campaign.jsonl")


def test_legacy_attach_preflight_allows_only_current_run_with_discovery(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    _start(control, state)
    emit_discovery_runtime(
        state,
        base_url="https://example.test/",
        html=_eligible_html(),
        run_id="run-current",
        minimum_eligible=3,
    )

    result = legacy_attach_preflight(control_dir=control, state_dir=state, minimum_eligible=3)

    assert result["allowed"] is True
    assert result["exit_code"] == 0
    assert result["safe_tail_argv"][:2] == ["tail", "-F"]
    assert result["safe_tail_command"].startswith("tail -F")


def test_legacy_status_preflight_uses_same_conservative_predicates(tmp_path):
    control = tmp_path / "control"
    stale = tmp_path / "stale"
    current = tmp_path / "current"
    _start(control, stale, run_id="run-stale")
    emit_discovery_runtime(
        stale,
        base_url="https://example.test/",
        html=_eligible_html(),
        run_id="run-stale",
        minimum_eligible=3,
    )
    _start(control, current, run_id="run-current")

    result = legacy_status_preflight(control_dir=control, state_dir=stale, minimum_eligible=3)

    assert result["allowed"] is False
    assert result["exit_code"] == PRODUCTION_ATTACH_REFUSED_EXIT
    assert result["operator_action"] == "refuse_legacy_status"
    assert result["summary"]["candidate_run_id"] == "run-stale"
    assert result["summary"]["current_run_id"] == "run-current"


def test_legacy_command_manifest_renders_guarded_commands_without_raw_tail_first(tmp_path):
    control = tmp_path / "control"
    state = tmp_path / "state"
    html = tmp_path / "index.html"
    html.write_text(_eligible_html(), encoding="utf-8")

    manifest = legacy_command_manifest(
        control_dir=control,
        state_dir=state,
        base_url="https://example.test/",
        html_file=html,
        minimum_eligible=3,
        python_executable="python3",
    )

    assert manifest["schema"] == "omega.production.legacy_command_manifest.v1"
    assert manifest["refusal_exit_code"] == PRODUCTION_ATTACH_REFUSED_EXIT
    assert manifest["attach_command_hash"].startswith("cmd-")
    assert "python3 -m omega_frontier.cli attach" in manifest["attach_command"]
    assert "tail -F" not in manifest["posix_attach_shim"].splitlines()[2]
    assert "exec $OMEGA_SAFE_TAIL" in manifest["posix_attach_shim"]


def test_render_legacy_attach_shim_contains_exit_gate(tmp_path):
    shim = render_legacy_attach_shim(
        control_dir=tmp_path / "control",
        state_dir=tmp_path / "state",
        minimum_eligible=2,
        python_executable="python3",
    )

    assert "omega_frontier.cli attach" in shim
    assert f"exit {PRODUCTION_ATTACH_REFUSED_EXIT}" in shim
    assert "must run before any raw tail" in shim


def test_cli_legacy_shim_outputs_installable_manifest(tmp_path, capsys):
    control = tmp_path / "control"
    state = tmp_path / "state"
    html = tmp_path / "index.html"
    html.write_text(_eligible_html(), encoding="utf-8")

    rc = main(
        [
            "legacy-shim",
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
            "--python",
            "python3",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["schema"] == "omega.production.legacy_command_manifest.v1"
    assert payload["attach_argv"][:3] == ["python3", "-m", "omega_frontier.cli"]
    assert "posix_attach_shim" in payload
