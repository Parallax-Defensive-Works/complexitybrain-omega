from __future__ import annotations

from pathlib import Path
from typing import Any

from .mission_assurance import sha256_text, utc_now
from .ops_scripts import repository_guard_manifest

SYSTEMD_UNIT_NAME = "omega-frontier@.service"
SYSTEMD_ENV_NAME = "omega-frontier.env"
SYSTEMD_HARDENING_DROPIN_NAME = "10-omega-frontier-hardening.conf"
SYSTEMD_README_NAME = "README-systemd.md"
SYSTEMD_FILE_MODE = 0o644


def _hash(content: str) -> str:
    return sha256_text(content)


def render_systemd_environment() -> str:
    """Render a conservative operator-edited environment file.

    The file is intentionally explicit. It makes the direct-run path, control
    directory, discovery evidence, and sovereign/no-telemetry posture visible
    before a service unit can start a long-running campaign.
    """

    lines = [
        "# Omega frontier production environment.",
        "# Copy to /etc/omega-frontier/omega-frontier.env and edit values before enabling the unit.",
        "OMEGA_PYTHON=python3",
        "OMEGA_WORKDIR=/root/omega",
        "OMEGA_RUNNER=/root/omega/complexity_brain_omega.py",
        "OMEGA_CONTROL_DIR=/root/.omega",
        "OMEGA_BASE_URL=https://example.test/",
        "OMEGA_ROOT_HTML_FILE=/var/lib/omega-frontier/root.html",
        "OMEGA_MINIMUM_ELIGIBLE=2",
        "OMEGA_RUNNER_ARGS=--web-discovery --route-mapper",
        "OMEGA_TELEMETRY=0",
        "OMEGA_NETWORK_TELEMETRY=0",
        "OMEGA_DATA_RESIDENCY=local-only",
        "OMEGA_AUDIT_MODE=append-only",
        "OMEGA_CONTROL_ACTION_MODE=approval-required",
        "OMEGA_RANGE_TWIN_MODE=deterministic-replay",
        "",
    ]
    return "\n".join(lines)


def render_systemd_unit() -> str:
    """Render a guarded systemd template unit.

    The unit is named as a template so the instance name selects the run state
    directory below /root/.omega/runs. ExecStartPre invokes the same production
    preflight used by operator scripts; if the run is stale or discovery is
    root-only, the runner never starts.
    """

    lines = [
        "[Unit]",
        "Description=Omega frontier mission assurance campaign %i",
        "Documentation=https://github.com/Parallax-Defensive-Works/complexitybrain-omega",
        "After=network-online.target",
        "Wants=network-online.target",
        "ConditionPathExists=%E/omega-frontier/omega-frontier.env",
        "",
        "[Service]",
        "Type=simple",
        "EnvironmentFile=%E/omega-frontier/omega-frontier.env",
        'Environment="OMEGA_STATE_DIR=/root/.omega/runs/%i"',
        "WorkingDirectory=${OMEGA_WORKDIR}",
        "ExecStartPre=/bin/sh -lc 'test -n \"$OMEGA_ROOT_HTML_FILE\" && test -s \"$OMEGA_ROOT_HTML_FILE\"'",
        "ExecStartPre=/bin/sh -lc 'exec \"$OMEGA_PYTHON\" -m omega_frontier.cli preflight --control-dir \"$OMEGA_CONTROL_DIR\" --state-dir \"$OMEGA_STATE_DIR\" --base-url \"$OMEGA_BASE_URL\" --html-file \"$OMEGA_ROOT_HTML_FILE\" --minimum-eligible \"$OMEGA_MINIMUM_ELIGIBLE\"'",
        "ExecStart=/bin/sh -lc 'mkdir -p \"$OMEGA_STATE_DIR\" && exec \"$OMEGA_PYTHON\" -u \"$OMEGA_RUNNER\" --url \"$OMEGA_BASE_URL\" --state-dir \"$OMEGA_STATE_DIR\" ${OMEGA_RUNNER_ARGS}'",
        "ExecStopPost=/bin/sh -lc '\"$OMEGA_PYTHON\" -m omega_frontier.cli report --state-dir \"$OMEGA_STATE_DIR\" > \"$OMEGA_STATE_DIR/mission-assurance-runtime-report.json\" 2>/dev/null || true'",
        "Restart=no",
        "KillSignal=SIGINT",
        "TimeoutStopSec=45s",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]
    return "\n".join(lines)


def render_systemd_hardening_dropin() -> str:
    """Render a conservative hardening drop-in for the systemd unit."""

    lines = [
        "[Service]",
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "ProtectSystem=strict",
        "ProtectHome=read-only",
        "ReadWritePaths=/root/.omega /root/omega /var/lib/omega-frontier",
        "RestrictSUIDSGID=yes",
        "LockPersonality=yes",
        "MemoryDenyWriteExecute=yes",
        "SystemCallArchitectures=native",
        "",
    ]
    return "\n".join(lines)


def render_systemd_readme() -> str:
    """Render operator instructions for the guarded launch pack."""

    lines = [
        "# Omega guarded systemd launch pack",
        "",
        "This pack starts Omega only after the same current-run and eligible-route preflight used by `omega-preflight` succeeds.",
        "The runner is a direct process under systemd. It does not rely on a stale supervisor pointer or a background shell tail.",
        "",
        "## Install",
        "",
        "```bash",
        "install -d /etc/omega-frontier /etc/systemd/system/omega-frontier@.service.d /var/lib/omega-frontier",
        "install -m 0644 omega-frontier.env /etc/omega-frontier/omega-frontier.env",
        "install -m 0644 omega-frontier@.service /etc/systemd/system/omega-frontier@.service",
        "install -m 0644 10-omega-frontier-hardening.conf /etc/systemd/system/omega-frontier@.service.d/10-omega-frontier-hardening.conf",
        "systemctl daemon-reload",
        "```",
        "",
        "Before starting, capture fresh root HTML into the file named by `OMEGA_ROOT_HTML_FILE`. The preflight refuses root-only discovery.",
        "",
        "```bash",
        "python - <<'PY'",
        "from pathlib import Path",
        "from urllib.request import urlopen",
        "url = 'https://example.test/'",
        "Path('/var/lib/omega-frontier').mkdir(parents=True, exist_ok=True)",
        "Path('/var/lib/omega-frontier/root.html').write_text(urlopen(url, timeout=30).read().decode('utf-8', 'replace'), encoding='utf-8')",
        "PY",
        "systemctl start omega-frontier@omega-state-YYYYMMDD-HHMMSS.service",
        "systemctl status omega-frontier@omega-state-YYYYMMDD-HHMMSS.service",
        "```",
        "",
        "The environment defaults disable telemetry, keep evidence local, use append-only audit language, and require approval before live control execution.",
        "",
    ]
    return "\n".join(lines)


def systemd_pack_files() -> dict[str, str]:
    return {
        SYSTEMD_ENV_NAME: render_systemd_environment(),
        SYSTEMD_UNIT_NAME: render_systemd_unit(),
        SYSTEMD_HARDENING_DROPIN_NAME: render_systemd_hardening_dropin(),
        SYSTEMD_README_NAME: render_systemd_readme(),
    }


def systemd_pack_manifest(output_dir: str | Path = "deploy/systemd") -> dict[str, Any]:
    root = Path(output_dir)
    files = systemd_pack_files()
    return {
        "schema": "omega.production.systemd_launch_pack.v1",
        "generated_at_utc": utc_now(),
        "output_dir": str(root),
        "files": [
            {
                "name": name,
                "path": str(root / name),
                "sha256": _hash(content),
                "mode": oct(SYSTEMD_FILE_MODE),
                "purpose": {
                    SYSTEMD_ENV_NAME: "operator-edited direct-run environment with sovereign defaults",
                    SYSTEMD_UNIT_NAME: "systemd template that runs preflight before direct runner start",
                    SYSTEMD_HARDENING_DROPIN_NAME: "systemd hardening drop-in with explicit read/write paths",
                    SYSTEMD_README_NAME: "operator install and safe-start instructions",
                }[name],
            }
            for name, content in files.items()
        ],
        "guard_dependency": repository_guard_manifest("scripts"),
        "safe_apply": [
            "review omega-frontier.env and set OMEGA_BASE_URL, OMEGA_RUNNER, and OMEGA_RUNNER_ARGS for the target lab",
            "capture fresh root HTML into OMEGA_ROOT_HTML_FILE before starting a service instance",
            "start omega-frontier@<run-directory-name>.service only after daemon-reload",
            "use scripts/omega-attach or python -m omega_frontier.cli attach for log attachment",
        ],
        "sovereign_defaults": {
            "telemetry": "disabled",
            "data_residency": "local-only",
            "audit": "append-only",
            "live_control_execution": "approval-required",
            "range_twin": "deterministic-replay",
        },
    }


def write_systemd_pack(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in systemd_pack_files().items():
        path = root / name
        path.write_text(content, encoding="utf-8")
        path.chmod(SYSTEMD_FILE_MODE)
        written.append(
            {
                "name": name,
                "path": str(path),
                "sha256": _hash(content),
                "mode": oct(path.stat().st_mode & 0o777),
            }
        )
    return {
        "schema": "omega.production.systemd_launch_pack_install.v1",
        "installed_at_utc": utc_now(),
        "output_dir": str(root),
        "files": written,
        "manifest": systemd_pack_manifest(root),
    }
