#!/usr/bin/env bash
# Старт watchdog в tmux (безопасно для оболочек с длинным argv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="${SESSION:-flypingavia-supervise}"
TMUX_BIN="${TMUX_BIN:-tmux}"
TMUX_CONF="${TMUX_CONF:-/exec-daemon/tmux.portal.conf}"

if [[ -f "$TMUX_CONF" ]]; then
  TMUX=("$TMUX_BIN" -f "$TMUX_CONF")
else
  TMUX=("$TMUX_BIN")
fi

"${TMUX[@]}" has-session -t "=$SESSION" 2>/dev/null && "${TMUX[@]}" kill-session -t "$SESSION" || true
"${TMUX[@]}" new-session -d -s "$SESSION" -c "$ROOT" -- /bin/bash -lc "$ROOT/scripts/supervise.sh"
echo "started tmux session: $SESSION"
