from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .active_guard import production_attach_guard, production_status_summary
from .legacy_guard import legacy_command_manifest
from .ops_scripts import repository_guard_manifest, write_repository_guard_scripts
from .runtime_bridge import (
    emit_discovery_runtime,
    emit_exposure_runtime,
    runtime_report,
    runtime_status,
    start_campaign_runtime,
)
from .service_units import systemd_pack_manifest, write_systemd_pack


def _read_json_file(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _optional_text_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return _read_text_file(path)


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _add_attach_guard_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--control-dir", required=True)
    command.add_argument("--state-dir", required=True)
    command.add_argument("--base-url", default=None)
    command.add_argument("--html-file", default=None)
    command.add_argument("--minimum-eligible", type=int, default=2)
    command.add_argument(
        "--no-discovery-gate",
        action="store_true",
        help="development-only escape hatch; production attach requires discovery by default",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omega-frontier",
        description="Operator CLI for Omega mission-assurance runtime bridge payloads.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="write current/last run pointers and emit control_plane_start")
    start.add_argument("--control-dir", required=True)
    start.add_argument("--state-dir", required=True)
    start.add_argument("--run-id", required=True)
    start.add_argument("--pid", type=int, default=None)
    start.add_argument("--argv", nargs="*", default=[])
    start.add_argument("--config-json", default=None, help="path to a JSON config file")

    status = sub.add_parser("status", help="return current/last/candidate state and attach decision")
    status.add_argument("--control-dir", required=True)
    status.add_argument("--candidate-state-dir", default=None)
    status.add_argument(
        "--strict-attach",
        action="store_true",
        help="return exit code 2 when attach_decision.allowed is false",
    )

    production_status = sub.add_parser(
        "production-status",
        help="run strict production status: current-run attach plus eligible discovery gate",
    )
    _add_attach_guard_args(production_status)

    attach = sub.add_parser(
        "attach",
        help="refuse stale/root-only runs before printing a safe tail command",
    )
    _add_attach_guard_args(attach)

    legacy_shim = sub.add_parser(
        "legacy-shim",
        help="emit guarded status/attach commands and a POSIX shim for legacy scripts",
    )
    _add_attach_guard_args(legacy_shim)
    legacy_shim.add_argument(
        "--python",
        default=sys.executable or "python3",
        help="Python executable legacy scripts should use for the guard CLI",
    )

    install_scripts = sub.add_parser(
        "install-scripts",
        help="emit or install repository-owned guarded production status/attach/preflight scripts",
    )
    install_scripts.add_argument(
        "--output-dir",
        default=None,
        help="directory to write scripts into; omitted means emit a manifest only",
    )

    systemd_pack = sub.add_parser(
        "systemd-pack",
        help="emit or install guarded systemd launch-pack files for direct-run production service units",
    )
    systemd_pack.add_argument(
        "--output-dir",
        default=None,
        help="directory to write systemd launch-pack files into; omitted means emit a manifest only",
    )

    discovery = sub.add_parser("discovery", help="emit a pass/fail discovery gate event")
    discovery.add_argument("--state-dir", required=True)
    discovery.add_argument("--base-url", required=True)
    discovery.add_argument("--html-file", required=True)
    discovery.add_argument("--run-id", default=None)
    discovery.add_argument("--minimum-eligible", type=int, default=2)
    discovery.add_argument(
        "--strict-gate",
        action="store_true",
        help="return exit code 3 when eligible-route gate fails",
    )

    exposure = sub.add_parser("exposure", help="persist and emit a mission-assurance bundle for one exposure")
    exposure.add_argument("--state-dir", required=True)
    exposure.add_argument("--observation-json", required=True)
    exposure.add_argument("--run-manifest-json", default=None)
    exposure.add_argument("--no-persist", action="store_true")

    report = sub.add_parser("report", help="summarize persisted mission-assurance bundles")
    report.add_argument("--state-dir", required=True)

    preflight = sub.add_parser("preflight", help="verify attach and discovery gates before tailing or reporting")
    preflight.add_argument("--control-dir", required=True)
    preflight.add_argument("--state-dir", required=True)
    preflight.add_argument("--base-url", required=True)
    preflight.add_argument("--html-file", required=True)
    preflight.add_argument("--minimum-eligible", type=int, default=2)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        config = _read_json_file(args.config_json)
        result = start_campaign_runtime(
            control_dir=args.control_dir,
            state_dir=args.state_dir,
            run_id=args.run_id,
            pid=args.pid,
            argv=tuple(args.argv),
            config=config,
        )
        _emit(result)
        return 0

    if args.command == "status":
        status = runtime_status(control_dir=args.control_dir, candidate_state_dir=args.candidate_state_dir)
        _emit(status)
        return 2 if args.strict_attach and not status["attach_decision"].get("allowed") else 0

    if args.command == "production-status":
        guard = production_attach_guard(
            control_dir=args.control_dir,
            state_dir=args.state_dir,
            base_url=args.base_url,
            html=_optional_text_file(args.html_file),
            minimum_eligible=args.minimum_eligible,
            require_discovery=not args.no_discovery_gate,
        )
        _emit(production_status_summary(guard))
        return 0 if guard["allowed"] else 5

    if args.command == "attach":
        guard = production_attach_guard(
            control_dir=args.control_dir,
            state_dir=args.state_dir,
            base_url=args.base_url,
            html=_optional_text_file(args.html_file),
            minimum_eligible=args.minimum_eligible,
            require_discovery=not args.no_discovery_gate,
        )
        _emit(guard)
        return 0 if guard["allowed"] else 5

    if args.command == "legacy-shim":
        result = legacy_command_manifest(
            control_dir=args.control_dir,
            state_dir=args.state_dir,
            base_url=args.base_url,
            html_file=args.html_file,
            minimum_eligible=args.minimum_eligible,
            python_executable=args.python,
            require_discovery=not args.no_discovery_gate,
        )
        _emit(result)
        return 0

    if args.command == "install-scripts":
        result = (
            write_repository_guard_scripts(args.output_dir)
            if args.output_dir
            else repository_guard_manifest()
        )
        _emit(result)
        return 0

    if args.command == "systemd-pack":
        result = write_systemd_pack(args.output_dir) if args.output_dir else systemd_pack_manifest()
        _emit(result)
        return 0

    if args.command == "discovery":
        result = emit_discovery_runtime(
            args.state_dir,
            base_url=args.base_url,
            html=_read_text_file(args.html_file),
            run_id=args.run_id,
            minimum_eligible=args.minimum_eligible,
        )
        _emit(result)
        return 3 if args.strict_gate and result["payload"].get("eligible_gate") != "pass" else 0

    if args.command == "exposure":
        observation = _read_json_file(args.observation_json)
        run_manifest = _read_json_file(args.run_manifest_json) if args.run_manifest_json else None
        result = emit_exposure_runtime(
            args.state_dir,
            observation,
            run_manifest=run_manifest,
            persist_evidence=not args.no_persist,
        )
        _emit(result)
        return 0

    if args.command == "report":
        _emit(runtime_report(args.state_dir))
        return 0

    if args.command == "preflight":
        status = runtime_status(
            control_dir=args.control_dir,
            candidate_state_dir=args.state_dir,
        )
        discovery = emit_discovery_runtime(
            args.state_dir,
            base_url=args.base_url,
            html=_read_text_file(args.html_file),
            run_id=(status.get("candidate") or {}).get("run_id"),
            minimum_eligible=args.minimum_eligible,
        )
        passed = bool(status["attach_decision"].get("allowed")) and discovery["payload"].get("eligible_gate") == "pass"
        _emit(
            {
                "schema": "omega.frontier.preflight_result.v1",
                "passed": passed,
                "status": status,
                "discovery": discovery,
            }
        )
        return 0 if passed else 4

    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
