#!/bin/sh
set -eu

BUNDLE_PATH="${RQALPHA_BUNDLE_PATH:-/data/rqalpha/bundle}"
IMAGE_BUNDLE_PATH="${RQALPHA_IMAGE_BUNDLE_PATH:-/opt/rqalpha/bundle}"
BOOTSTRAP="${RQALPHA_BUNDLE_BOOTSTRAP:-1}"
CRON_SCHEDULE="${RQALPHA_BUNDLE_CRON:-0 3 1 * *}"
UPDATE_LOG="${RQALPHA_BUNDLE_LOG:-/data/rqalpha/bundle_update.log}"
STATUS_FILE="${RQALPHA_BUNDLE_STATUS_FILE:-/data/rqalpha/bundle_status.json}"
ASYNC_BOOTSTRAP="${RQALPHA_BUNDLE_ASYNC:-1}"

warn() {
  echo "[entrypoint] $*" >&2
}

write_status() {
  status="$1"
  work_dir="$2"
  message="$3"
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  meta_url="${BUNDLE_META_URL:-}"
  meta_total="${BUNDLE_META_TOTAL_BYTES:-}"
  if [ -n "$meta_total" ] && echo "$meta_total" | grep -qE '^[0-9]+$'; then
    total_json="$meta_total"
  else
    total_json="null"
  fi
  if [ -n "$meta_url" ]; then
    url_json="\"$meta_url\""
  else
    url_json="null"
  fi
  mkdir -p "$(dirname "$STATUS_FILE")"
  cat > "$STATUS_FILE" <<EOF
{"status":"$status","work_dir":"$work_dir","bundle_path":"$BUNDLE_PATH","message":"$message","updated_at":"$timestamp","url":$url_json,"total_bytes":$total_json}
EOF
}

supports_data_path() {
  subcmd="$1"
  if rqalpha "$subcmd" --help 2>&1 | grep -q -- "--data-bundle-path"; then
    echo "--data-bundle-path"
    return 0
  fi
  if rqalpha "$subcmd" --help 2>&1 | grep -q -- " -d "; then
    echo "-d"
    return 0
  fi
  echo ""
}

resolve_bundle_meta() {
  if [ -n "${BUNDLE_META_RESOLVED:-}" ]; then
    return 0
  fi
  BUNDLE_META_RESOLVED="1"
  meta="$(
    python - <<'PY'
import os
from datetime import datetime, timezone, timedelta
import urllib.request

explicit = os.environ.get("RQALPHA_BUNDLE_URL", "").strip()
base = os.environ.get("RQALPHA_BUNDLE_URL_BASE", "http://bundle.assets.ricequant.com/bundles_v4").strip()

def candidates():
    if explicit:
        return [explicit]
    if not base:
        return []
    # Use Beijing time (UTC+8) to determine the correct bundle month
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    year = now.year
    month = now.month
    urls = []
    for _ in range(12):
        urls.append(f"{base}/rqbundle_{year}{month:02d}.tar.bz2")
        month -= 1
        if month <= 0:
            month = 12
            year -= 1
    return urls

def head_length(url):
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=5) as response:
        length = response.headers.get("Content-Length")
    return int(length) if length else None

url = ""
total = ""
for candidate in candidates():
    try:
        length = head_length(candidate)
    except Exception:
        continue
    if length and length > 0:
        url = candidate
        total = str(length)
        break

print(url)
print(total)
PY
  )" || return 0
  BUNDLE_META_URL="$(printf '%s' "$meta" | sed -n '1p')"
  BUNDLE_META_TOTAL_BYTES="$(printf '%s' "$meta" | sed -n '2p')"
}

copy_default_bundle_if_needed() {
  default_bundle="${HOME:-/root}/.rqalpha/bundle"
  if [ "$default_bundle" != "$BUNDLE_PATH" ] && [ -d "$default_bundle" ]; then
    cp -a "$default_bundle"/. "$BUNDLE_PATH"/
  fi
}

bundle_is_ready() {
  bundle_path="$1"
  if [ -z "$bundle_path" ]; then
    return 1
  fi
  if [ ! -d "$bundle_path" ]; then
    return 1
  fi
  if [ -z "$(ls -A "$bundle_path" 2>/dev/null)" ]; then
    return 1
  fi
  for f in future_info.json instruments.pk trading_dates.npy; do
    if [ ! -s "$bundle_path/$f" ]; then
      return 1
    fi
  done
  return 0
}

bundle_needs_bootstrap() {
  if bundle_is_ready "$BUNDLE_PATH"; then
    return 1
  fi
  return 0
}

bundle_arg_for_cli() {
  case "$BUNDLE_PATH" in
    */bundle) echo "$(dirname "$BUNDLE_PATH")" ;;
    *) echo "$BUNDLE_PATH" ;;
  esac
}

prepare_bundle_dir() {
  if [ -d "$BUNDLE_PATH" ] && [ -n "$(ls -A "$BUNDLE_PATH" 2>/dev/null)" ]; then
    warn "RQAlpha bundle incomplete; clearing existing bundle contents before download"
    rm -rf "$BUNDLE_PATH"/* "$BUNDLE_PATH"/.[!.]* "$BUNDLE_PATH"/..?* 2>/dev/null || true
  fi
  mkdir -p "$BUNDLE_PATH"
}

download_bundle() {
  if bundle_needs_bootstrap; then
    if bundle_is_ready "$IMAGE_BUNDLE_PATH"; then
      warn "RQAlpha bundle missing; copying from image bundle at $IMAGE_BUNDLE_PATH."
      prepare_bundle_dir
      cp -a "$IMAGE_BUNDLE_PATH"/. "$BUNDLE_PATH"/
      if bundle_is_ready "$BUNDLE_PATH"; then
        write_status "ready" "" "bundle ready"
        return 0
      fi
    fi
    warn "RQAlpha bundle missing or incomplete; downloading to $BUNDLE_PATH (first start may take a while)."
    flag="$(supports_data_path download-bundle)"
    bundle_arg="$(bundle_arg_for_cli)"
    download_parent="$bundle_arg"
    download_bundle_dir="$bundle_arg/bundle"
    use_temp_download="0"
    if [ -n "$flag" ]; then
      if [ -e "$BUNDLE_PATH" ]; then
        download_parent="$(mktemp -d /tmp/rqalpha-bundle-XXXXXX)"
        download_bundle_dir="$download_parent/bundle"
        use_temp_download="1"
      fi
      resolve_bundle_meta
      write_status "downloading" "$download_bundle_dir" "bundle downloading"
      if ! rqalpha download-bundle "$flag" "$download_parent"; then
        warn "rqalpha download-bundle failed; falling back to default bundle path."
        prepare_bundle_dir
        rqalpha download-bundle
        copy_default_bundle_if_needed
      fi
    else
      prepare_bundle_dir
      resolve_bundle_meta
      write_status "downloading" "$BUNDLE_PATH" "bundle downloading"
      rqalpha download-bundle
      copy_default_bundle_if_needed
    fi
    if [ "$use_temp_download" = "1" ] && [ -d "$download_bundle_dir" ]; then
      prepare_bundle_dir
      cp -a "$download_bundle_dir"/. "$BUNDLE_PATH"/
    fi
    if bundle_needs_bootstrap; then
      warn "RQAlpha bundle download did not complete; exiting."
      write_status "failed" "$download_bundle_dir" "bundle download failed"
      return 1
    fi
    if [ -d "$bundle_arg/bundle" ]; then
      cp -a "$bundle_arg/bundle"/. "$BUNDLE_PATH"/
    fi
    write_status "ready" "" "bundle ready"
  fi
}

update_bundle() {
  update_subcmd="update-bundle"
  if ! rqalpha update-bundle --help >/dev/null 2>&1; then
    update_subcmd="download-bundle"
  fi

  flag="$(supports_data_path "$update_subcmd")"
  bundle_arg="$(bundle_arg_for_cli)"
  if [ -n "$flag" ]; then
    if ! rqalpha "$update_subcmd" "$flag" "$bundle_arg"; then
      warn "rqalpha $update_subcmd failed; falling back to default bundle path."
      rqalpha "$update_subcmd"
      copy_default_bundle_if_needed
    fi
  else
    rqalpha "$update_subcmd"
    copy_default_bundle_if_needed
  fi
}

setup_cron() {
  if [ -z "$CRON_SCHEDULE" ] || [ "$CRON_SCHEDULE" = "off" ] || [ "$CRON_SCHEDULE" = "disabled" ]; then
    return 0
  fi
  if ! command -v cron >/dev/null 2>&1; then
    warn "cron not installed; skip bundle auto-update."
    return 0
  fi

  mkdir -p "$(dirname "$UPDATE_LOG")"
  cat > /etc/cron.d/rqalpha-bundle <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RQALPHA_BUNDLE_PATH=$BUNDLE_PATH
$CRON_SCHEDULE root /app/docker-entrypoint.sh bundle-update >> $UPDATE_LOG 2>&1
EOF
  chmod 0644 /etc/cron.d/rqalpha-bundle
  cron
}

if [ "${1:-}" = "bundle-update" ]; then
  if command -v rqalpha >/dev/null 2>&1; then
    update_bundle
  else
    warn "rqalpha is not installed; skip bundle update."
  fi
  exit 0
fi

if ! command -v rqalpha >/dev/null 2>&1; then
  warn "rqalpha is not installed; skipping bundle bootstrap."
else
  if [ "$BOOTSTRAP" != "0" ] && [ "$BOOTSTRAP" != "false" ]; then
    if [ "$ASYNC_BOOTSTRAP" = "1" ] || [ "$ASYNC_BOOTSTRAP" = "true" ]; then
      download_bundle &
    else
      if ! download_bundle; then
        exit 1
      fi
    fi
  else
    if bundle_is_ready "$BUNDLE_PATH"; then
      write_status "ready" "" "bundle ready"
    fi
  fi
  setup_cron
fi

exec "$@"
