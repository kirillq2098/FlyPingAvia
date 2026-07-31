#!/usr/bin/env bash
# Collect one Mini App diagnostic session (BUG-02.5).
# Usage:
#   ./scripts/collect-miniapp-session.sh <session_id>
#   ./scripts/collect-miniapp-session.sh --from "2026-07-31 11:40:00" --to "2026-07-31 11:45:00" --client-prefix "5.44.168"
set -euo pipefail

DIAG_LOG="${MINIAPP_DIAG_LOG_PATH:-/var/log/flyping/miniapp-diagnostic.log}"
NGINX_ACCESS="${NGINX_ACCESS_LOG:-/var/log/nginx/access.log}"
CONTAINER="${FLYPING_CONTAINER:-flyping-app}"

SESSION_ID=""
FROM=""
TO=""
CLIENT_PREFIX=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --client-prefix) CLIENT_PREFIX="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,8p' "$0"
      exit 0
      ;;
    *)
      SESSION_ID="$1"
      shift
      ;;
  esac
done

python3 - "$DIAG_LOG" "$NGINX_ACCESS" "$CONTAINER" "$SESSION_ID" "$FROM" "$TO" "$CLIENT_PREFIX" <<'PY'
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

diag_log, nginx_access, container, session_id, from_s, to_s, client_prefix = sys.argv[1:8]

def parse_ts(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(s.replace("Z", ""), fmt.replace("Z", ""))
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

from_dt = parse_ts(from_s)
to_dt = parse_ts(to_s)

events = []
path = Path(diag_log)
if path.is_file():
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if session_id and obj.get("session_id") != session_id:
            continue
        ts = obj.get("ts") or ""
        if from_dt or to_dt:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                t = None
            if t is not None:
                if from_dt and t.replace(tzinfo=timezone.utc) < from_dt:
                    continue
                if to_dt and t.replace(tzinfo=timezone.utc) > to_dt:
                    continue
        if client_prefix:
            cip = str(obj.get("client_ip_masked") or "")
            if client_prefix not in cip and not cip.startswith(client_prefix.rstrip("…").rstrip(".")):
                # still keep events without IP when filtering by time/session
                if obj.get("kind") == "frontend" and not session_id:
                    pass
        events.append(obj)

# If session unknown but client prefix given, prefer sessions seen with that prefix
if not session_id and client_prefix and events:
    by_sid = {}
    for e in events:
        sid = e.get("session_id") or ""
        cip = str(e.get("client_ip_masked") or "")
        if client_prefix.split(".")[0] in cip or client_prefix in cip:
            by_sid.setdefault(sid, []).append(e)
    if by_sid:
        # pick session with most events
        session_id = max(by_sid.keys(), key=lambda k: len(by_sid[k]))
        events = [e for e in events if e.get("session_id") == session_id]

# Derive time window from session events when only session_id is known
event_times = []
for e in events:
    ts = e.get("ts") or ""
    try:
        event_times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    except Exception:
        pass
if event_times and not from_dt:
    from_dt = min(event_times).replace(tzinfo=timezone.utc)
if event_times and not to_dt:
    to_dt = max(event_times).replace(tzinfo=timezone.utc)
# Widen ±120s for nginx correlation
from datetime import timedelta
nginx_from = (from_dt - timedelta(seconds=120)) if from_dt else None
nginx_to = (to_dt + timedelta(seconds=120)) if to_dt else None

# Client prefix from session events if not provided
if not client_prefix and events:
    for e in events:
        cip = str(e.get("client_ip_masked") or "")
        # e.g. "5.44.168…" → "5.44.168"
        m = re.match(r"^(\d+\.\d+\.\d+)", cip)
        if m:
            client_prefix = m.group(1)
            break

docker_since = from_s
if not docker_since and from_dt:
    docker_since = from_dt.strftime("%Y-%m-%dT%H:%M:%S")
docker_until = to_s
if not docker_until and to_dt:
    docker_until = (to_dt + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")

# Docker app logs snippet
docker_lines = []
try:
    if docker_until:
        cmd = ["docker", "logs", container, "--since", docker_since or "30m", "--until", docker_until]
    else:
        cmd = ["docker", "logs", container, "--since", docker_since or "30m"]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=30)
    for ln in out.splitlines():
        if session_id and session_id in ln:
            docker_lines.append(ln)
        elif (not session_id) and ("miniapp_diag" in ln or "/api/me" in ln or "/api/diag" in ln or "bot_event" in ln):
            if client_prefix and client_prefix not in ln and "miniapp_diag" not in ln and "bot_event" not in ln:
                continue
            docker_lines.append(ln)
except Exception as exc:
    docker_lines.append(f"[docker logs unavailable: {exc}]")

def parse_nginx_ts(line: str):
    # [31/Jul/2026:11:26:17 +0000]
    m = re.search(r"\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}) ([+-]\d{4})\]", line)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%d/%b/%Y:%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

# Nginx (best-effort): filter by time window and optional client prefix
nginx_lines = []
nap = Path(nginx_access)
if nap.is_file():
    try:
        for ln in nap.read_text(encoding="utf-8", errors="replace").splitlines()[-8000:]:
            if "app.flyping.ru" not in ln and "api.flyping.ru" not in ln:
                continue
            if client_prefix and client_prefix not in ln:
                continue
            nts = parse_nginx_ts(ln)
            if nginx_from and nts and nts < nginx_from:
                continue
            if nginx_to and nts and nts > nginx_to:
                continue
            # If we have a tight session window but no client_prefix, still require /api/diag|/api/me|/assets
            if session_id and not client_prefix:
                if not any(x in ln for x in ("/api/diag", "/api/me", "/assets/", "GET / HTTP")):
                    continue
            nginx_lines.append(ln)
    except Exception as exc:
        nginx_lines.append(f"[nginx unavailable: {exc}]")

# Classification
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] if False else "/opt/flyping"))
except Exception:
    pass
# Inline classifier (mirror of server helper)
stages = [str(e.get("event") or e.get("stage") or "") for e in events]
tgdata = any(bool(e.get("has_tgwebappdata")) or int(e.get("tgwebappdata_len") or 0) > 0 for e in events)
extract_ok = any(bool(e.get("extract_ok")) for e in events)
has_init = any(bool(e.get("has_init_data")) or int(e.get("init_data_len") or 0) > 0 for e in events)
has_me_start = any(s in ("api_me_start", "api_me") for s in stages)
has_me_ok = any(s in ("api_me_ok", "api_me_response", "bootstrap_success") for s in stages)
statuses = [int(e.get("http_status") or e.get("status") or 0) for e in events]
assets = sorted({str(e.get("asset")) for e in events if e.get("asset")})
modes = sorted({str(e.get("launch_mode")) for e in events if e.get("launch_mode")})

if any(s in (401, 403) for s in statuses) and has_me_start:
    cls = "D"
elif has_me_ok and 200 in statuses:
    cls = "ok_pending_soak"
elif (has_init or extract_ok) and not has_me_start:
    cls = "C"
elif tgdata and not extract_ok and not has_init:
    cls = "B"
elif not events:
    cls = "F"
elif not tgdata and not has_init:
    cls = "A"
else:
    cls = "A"

labels = {
    "A": "Telegram не передал tgWebAppData",
    "B": "tgWebAppData был в URL, parser не извлёк",
    "C": "parser извлёк, /api/me не вызван",
    "D": "/api/me вызван и получил 401/403",
    "E": "/api/me получил 200, UI сломался после авторизации",
    "F": "запросы не дошли до production",
    "G": "загружен старый asset/cache",
    "H": "открыт не тот бот или не тот URL",
    "ok_pending_soak": "/api/me 200 — успех (нужен soak ≥60с)",
}

print("=== Mini App session report ===")
print(f"session_id: {session_id or '-'}")
print(f"events: {len(events)}")
print(f"assets: {', '.join(assets) or '-'}")
print(f"launch_modes: {', '.join(modes) or '-'}")
print(f"classification: {cls} — {labels.get(cls, cls)}")
print()
print("--- chronological frontend/backend/bot JSONL ---")
for e in sorted(events, key=lambda x: str(x.get("ts") or "")):
    print(json.dumps(e, ensure_ascii=False))
print()
print("--- docker / application snippets ---")
for ln in docker_lines[-80:]:
    # redact obvious secrets
    ln = re.sub(r"(?i)(authorization|tma)\s+\S+", r"\1 [redacted]", ln)
    ln = re.sub(r"\d{8,10}:[A-Za-z0-9_-]{20,}", "[bot_token_redacted]", ln)
    print(ln)
print()
print("--- nginx snippets ---")
for ln in nginx_lines[-40:]:
    print(ln)
print()
print("NOTE: Menu button presses are NOT delivered as bot updates.")
PY
