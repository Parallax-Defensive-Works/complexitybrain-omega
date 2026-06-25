import json
import os

from omega_frontier.cli import main
from omega_frontier.service_units import (
    SYSTEMD_ENV_NAME,
    SYSTEMD_HARDENING_DROPIN_NAME,
    SYSTEMD_README_NAME,
    SYSTEMD_UNIT_NAME,
    render_systemd_environment,
    render_systemd_hardening_dropin,
    render_systemd_readme,
    render_systemd_unit,
    systemd_pack_files,
    systemd_pack_manifest,
    write_systemd_pack,
)


def test_systemd_unit_runs_preflight_before_direct_runner_start():
    unit = render_systemd_unit()

    assert "ExecStartPre=/bin/sh -lc" in unit
    assert "omega_frontier.cli preflight" in unit
    assert "--control-dir" in unit
    assert "--state-dir" in unit
    assert "--html-file" in unit
    assert "ExecStart=/bin/sh -lc" in unit
    assert "complexity_brain_omega.py" in render_systemd_environment()
    assert unit.index("ExecStartPre") < unit.index("ExecStart=/bin/sh -lc")


def test_systemd_environment_has_sovereign_defaults():
    env = render_systemd_environment()

    assert "OMEGA_TELEMETRY=0" in env
    assert "OMEGA_NETWORK_TELEMETRY=0" in env
    assert "OMEGA_DATA_RESIDENCY=local-only" in env
    assert "OMEGA_AUDIT_MODE=append-only" in env
    assert "OMEGA_CONTROL_ACTION_MODE=approval-required" in env
    assert "OMEGA_RANGE_TWIN_MODE=deterministic-replay" in env


def test_systemd_hardening_dropin_limits_raw_write_surface():
    dropin = render_systemd_hardening_dropin()

    assert "NoNewPrivileges=yes" in dropin
    assert "ProtectSystem=strict" in dropin
    assert "ReadWritePaths=/root/.omega /root/omega /var/lib/omega-frontier" in dropin


def test_systemd_readme_documents_safe_start():
    readme = render_systemd_readme()

    assert "systemctl daemon-reload" in readme
    assert "OMEGA_ROOT_HTML_FILE" in readme
    assert "preflight refuses root-only discovery" in readme


def test_systemd_pack_manifest_contract():
    manifest = systemd_pack_manifest("out")

    assert manifest["schema"] == "omega.production.systemd_launch_pack.v1"
    names = {entry["name"] for entry in manifest["files"]}
    assert names == {SYSTEMD_ENV_NAME, SYSTEMD_UNIT_NAME, SYSTEMD_HARDENING_DROPIN_NAME, SYSTEMD_README_NAME}
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    assert manifest["guard_dependency"]["schema"] == "omega.production.repository_guard_scripts.v1"
    assert manifest["sovereign_defaults"]["telemetry"] == "disabled"
    assert any("fresh root HTML" in step for step in manifest["safe_apply"])


def test_write_systemd_pack_creates_operator_files(tmp_path):
    result = write_systemd_pack(tmp_path / "systemd")

    assert result["schema"] == "omega.production.systemd_launch_pack_install.v1"
    for entry in result["files"]:
        path = tmp_path / "systemd" / entry["name"]
        assert path.exists()
        assert entry["mode"] == "0o644"
        assert not os.access(path, os.X_OK)


def test_systemd_pack_files_are_stable_names():
    files = systemd_pack_files()

    assert set(files) == {SYSTEMD_ENV_NAME, SYSTEMD_UNIT_NAME, SYSTEMD_HARDENING_DROPIN_NAME, SYSTEMD_README_NAME}
    assert files[SYSTEMD_UNIT_NAME].startswith("[Unit]")
    assert files[SYSTEMD_ENV_NAME].startswith("# Omega frontier production environment")


def test_cli_systemd_pack_manifest_only(capsys):
    exit_code = main(["systemd-pack"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["schema"] == "omega.production.systemd_launch_pack.v1"
    assert len(result["files"]) == 4


def test_cli_systemd_pack_writes_files(tmp_path, capsys):
    output = tmp_path / "pack"
    exit_code = main(["systemd-pack", "--output-dir", str(output)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["schema"] == "omega.production.systemd_launch_pack_install.v1"
    assert (output / SYSTEMD_UNIT_NAME).exists()
    assert (output / SYSTEMD_ENV_NAME).exists()
    assert (output / SYSTEMD_HARDENING_DROPIN_NAME).exists()
    assert (output / SYSTEMD_README_NAME).exists()
