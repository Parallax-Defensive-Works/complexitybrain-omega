from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .active_guard import production_attach_guard, production_status_summary
from .mission_assurance import command_hash
from .runtime_bridge import campaign_log_path

PRODUCTION_ATTACH_REFUSED_EXIT = 5


def _argv_to_command(argv: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def _path_text(path: str | Path) -> str:
    return str(Path(path))


def legacy_status_preflight(
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html: str | None = None,
    minimum_eligible: int = 2,
    require_discovery: bool = True,
    emit_event: bool = True,
) -> dict[str, Any]:
    """Guard a legacy status path before it trusts a run directory.

    Legacy status commands are useful only after the same predicates used by the
    production attach guard hold: the run must be the current run, and discovery
    must prove an eligible non-root surface unless discovery is explicitly
    disabled for development.
    """

    guard = production_attach_guard(
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html=html,
        minimum_eligible=minimum_eligible,
        require_discovery=require_discovery,
        emit_event=emit_event,
    )
    summary = production_status_summary(guard)
    allowed = bool(guard.get("allowed"))
    return {
        "schema": "omega.production.legacy_status_preflight.v1",
        "allowed": allowed,
        "exit_code": 0 if allowed else PRODUCTION_ATTACH_REFUSED_EXIT,
        "operator_action": "continue_legacy_status" if allowed else "refuse_legacy_status",
        "summary": summary,
        "event_hash": (guard.get("event") or {}).get("event_hash"),
    }


def legacy_attach_preflight(
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html: str | None = None,
    minimum_eligible: int = 2,
    require_discovery: bool = True,
    emit_event: bool = True,
) -> dict[str, Any]:
    """Guard a legacy attach path and return a safe tail argv only if allowed."""

    guard = production_attach_guard(
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html=html,
        minimum_eligible=minimum_eligible,
        require_discovery=require_discovery,
        emit_event=emit_event,
    )
    allowed = bool(guard.get("allowed"))
    log_path = (guard.get("status", {}).get("candidate") or {}).get("campaign_log") or str(
        campaign_log_path(state_dir)
    )
    safe_tail_argv = ["tail", "-F", log_path] if allowed else None
    return {
        "schema": "omega.production.legacy_attach_preflight.v1",
        "allowed": allowed,
        "exit_code": 0 if allowed else PRODUCTION_ATTACH_REFUSED_EXIT,
        "operator_action": "exec_safe_tail" if allowed else "refuse_legacy_attach",
        "block_reasons": list(guard.get("block_reasons", [])),
        "safe_tail_argv": safe_tail_argv,
        "safe_tail_command": _argv_to_command(safe_tail_argv) if safe_tail_argv else None,
        "refused_tail_command": guard.get("refused_tail_command"),
        "event_hash": (guard.get("event") or {}).get("event_hash"),
    }


def legacy_cli_argv(
    command: str,
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html_file: str | Path | None = None,
    minimum_eligible: int = 2,
    python_executable: str = "python3",
    module: str = "omega_frontier.cli",
    require_discovery: bool = True,
) -> list[str]:
    """Return the guarded CLI argv a legacy shell script should call."""

    if command not in {"attach", "production-status"}:
        raise ValueError("legacy guarded command must be attach or production-status")
    argv = [
        python_executable,
        "-m",
        module,
        command,
        "--control-dir",
        _path_text(control_dir),
        "--state-dir",
        _path_text(state_dir),
        "--minimum-eligible",
        str(minimum_eligible),
    ]
    if base_url is not None:
        argv.extend(["--base-url", base_url])
    if html_file is not None:
        argv.extend(["--html-file", _path_text(html_file)])
    if not require_discovery:
        argv.append("--no-discovery-gate")
    return argv


def render_legacy_attach_shim(
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html_file: str | Path | None = None,
    minimum_eligible: int = 2,
    python_executable: str = "python3",
    require_discovery: bool = True,
) -> str:
    """Render a POSIX shell guard for old attach scripts.

    The shim refuses before any raw tail command executes. It prints the guard
    JSON for auditability and then execs only the safe command returned by the
    production attach guard.
    """

    attach_argv = legacy_cli_argv(
        "attach",
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html_file=html_file,
        minimum_eligible=minimum_eligible,
        python_executable=python_executable,
        require_discovery=require_discovery,
    )
    attach_command = _argv_to_command(attach_argv)
    py = shlex.quote(python_executable)
    return "\n".join(
        [
            "# Omega production attach guard for legacy scripts.",
            "# This block must run before any raw tail/attach command.",
            f"OMEGA_ATTACH_GUARD_JSON=$({attach_command})",
            "OMEGA_ATTACH_GUARD_RC=$?",
            "printf '%s\\n' \"$OMEGA_ATTACH_GUARD_JSON\"",
            "if [ \"$OMEGA_ATTACH_GUARD_RC\" -ne 0 ]; then",
            "  exit \"$OMEGA_ATTACH_GUARD_RC\"",
            "fi",
            "OMEGA_SAFE_TAIL=$(printf '%s\\n' \"$OMEGA_ATTACH_GUARD_JSON\" | "
            + f"{py} -c 'import json,sys; print(json.load(sys.stdin).get(\"safe_tail_command\") or \"\")')",
            "if [ -z \"$OMEGA_SAFE_TAIL\" ]; then",
            f"  exit {PRODUCTION_ATTACH_REFUSED_EXIT}",
            "fi",
            "exec $OMEGA_SAFE_TAIL",
            "",
        ]
    )


def legacy_command_manifest(
    *,
    control_dir: str | Path,
    state_dir: str | Path,
    base_url: str | None = None,
    html_file: str | Path | None = None,
    minimum_eligible: int = 2,
    python_executable: str = "python3",
    require_discovery: bool = True,
) -> dict[str, Any]:
    """Return operator-installable guarded commands for legacy Omega scripts."""

    status_argv = legacy_cli_argv(
        "production-status",
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html_file=html_file,
        minimum_eligible=minimum_eligible,
        python_executable=python_executable,
        require_discovery=require_discovery,
    )
    attach_argv = legacy_cli_argv(
        "attach",
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html_file=html_file,
        minimum_eligible=minimum_eligible,
        python_executable=python_executable,
        require_discovery=require_discovery,
    )
    shim = render_legacy_attach_shim(
        control_dir=control_dir,
        state_dir=state_dir,
        base_url=base_url,
        html_file=html_file,
        minimum_eligible=minimum_eligible,
        python_executable=python_executable,
        require_discovery=require_discovery,
    )
    return {
        "schema": "omega.production.legacy_command_manifest.v1",
        "status_argv": status_argv,
        "status_command": _argv_to_command(status_argv),
        "attach_argv": attach_argv,
        "attach_command": _argv_to_command(attach_argv),
        "attach_command_hash": command_hash(tuple(attach_argv)),
        "posix_attach_shim": shim,
        "refusal_exit_code": PRODUCTION_ATTACH_REFUSED_EXIT,
        "install_note": "prepend posix_attach_shim to any legacy attach/tail script before it reads current-run.json",
    }
