# complexitybrain-omega

Persistent mechanism-potency campaigns for owned sandbox laboratories.

## Production guard entrypoints

Omega production status and attach must pass through the frontier guard before any run log is trusted or tailed. The repository provides guarded POSIX entrypoints:

```bash
export OMEGA_CONTROL_DIR=/root/.omega
export OMEGA_STATE_DIR=/root/.omega/runs/<run>
export OMEGA_BASE_URL=https://example.test/
export OMEGA_ROOT_HTML_FILE=/tmp/omega-root.html
export OMEGA_MINIMUM_ELIGIBLE=2

sh scripts/omega-preflight
sh scripts/omega-production-status
sh scripts/omega-attach
```

`omega-attach` refuses stale or root-only runs before it can exec `tail`. The refusal code is `5`. Use `python -m omega_frontier.cli install-scripts --output-dir <dir>` to install executable copies for service units or operator shells.
