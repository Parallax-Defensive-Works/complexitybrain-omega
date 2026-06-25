import json
import os

from omega_frontier.cli import main
from omega_frontier.ops_scripts import (
    PRODUCTION_ATTACH_SCRIPT,
    PRODUCTION_PREFLIGHT_SCRIPT,
    PRODUCTION_STATUS_SCRIPT,
    repository_guard_manifest,
    repository_guard_scripts,
    render_production_attach_script,
    render_production_preflight_script,
    render_production_status_script,
    write_repository_guard_scripts,
)


def test_repository_guard_scripts_are_guarded_before_tail():
    status = render_production_status_script()
    attach = render_production_attach_script()
    preflight = render_production_preflight_script()

    assert "omega_frontier.cli production-status" in status
    assert "omega_frontier.cli attach" in attach
    assert "omega_frontier.cli preflight" in preflight
    assert "OMEGA_CONTROL_DIR" in attach
    assert "OMEGA_STATE_DIR" in attach
    assert "safe_tail_argv" in attach
    assert "os.execvp" in attach
    assert "tail -F" not in attach


def test_repository_guard_manifest_lists_apply_contract():
    manifest = repository_guard_manifest("bin")

    assert manifest["schema"] == "omega.production.repository_guard_scripts.v1"
    names = {entry["name"] for entry in manifest["scripts"]}
    assert names == {PRODUCTION_STATUS_SCRIPT, PRODUCTION_ATTACH_SCRIPT, PRODUCTION_PREFLIGHT_SCRIPT}
    assert manifest["refusal_exit_code"] == 5
    assert "OMEGA_CONTROL_DIR" in manifest["environment"]
    assert any("omega-attach" in item for item in manifest["safe_apply"])
    assert all(len(entry["sha256"]) == 64 for entry in manifest["scripts"])


def test_write_repository_guard_scripts_sets_executable_mode(tmp_path):
    result = write_repository_guard_scripts(tmp_path / "guarded")

    assert result["schema"] == "omega.production.repository_guard_install.v1"
    for entry in result["scripts"]:
        path = tmp_path / "guarded" / entry["name"]
        assert path.exists()
        assert path.stat().st_mode & 0o111
        assert entry["mode"] == "0o755"


def test_cli_install_scripts_manifest_only(tmp_path, capsys):
    exit_code = main(["install-scripts"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["schema"] == "omega.production.repository_guard_scripts.v1"
    assert len(result["scripts"]) == 3


def test_cli_install_scripts_writes_files(tmp_path, capsys):
    output = tmp_path / "bin"
    exit_code = main(["install-scripts", "--output-dir", str(output)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["schema"] == "omega.production.repository_guard_install.v1"
    assert (output / PRODUCTION_STATUS_SCRIPT).exists()
    assert (output / PRODUCTION_ATTACH_SCRIPT).exists()
    assert (output / PRODUCTION_PREFLIGHT_SCRIPT).exists()
    assert os.access(output / PRODUCTION_ATTACH_SCRIPT, os.X_OK)


def test_repository_guard_scripts_has_stable_script_names():
    scripts = repository_guard_scripts()

    assert set(scripts) == {PRODUCTION_STATUS_SCRIPT, PRODUCTION_ATTACH_SCRIPT, PRODUCTION_PREFLIGHT_SCRIPT}
    assert scripts[PRODUCTION_STATUS_SCRIPT].startswith("#!/bin/sh")
    assert scripts[PRODUCTION_ATTACH_SCRIPT].startswith("#!/bin/sh")
    assert scripts[PRODUCTION_PREFLIGHT_SCRIPT].startswith("#!/bin/sh")
