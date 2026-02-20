#!/bin/sh
set -eu

BUNDLE_PATH="${RQALPHA_BUNDLE_PATH:-/data/rqalpha/bundle}"
BOOTSTRAP="${RQALPHA_BUNDLE_BOOTSTRAP:-1}"
CRON_SCHEDULE="${RQALPHA_BUNDLE_CRON:-0 3 1 * *}"
UPDATE_LOG="${RQALPHA_BUNDLE_LOG:-/data/rqalpha/bundle_update.log}"

warn() {
  echo "[entrypoint] $*" >&2
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

copy_default_bundle_if_needed() {
  default_bundle="${HOME:-/root}/.rqalpha/bundle"
  if [ "$default_bundle" != "$BUNDLE_PATH" ] && [ -d "$default_bundle" ]; then
    cp -a "$default_bundle"/. "$BUNDLE_PATH"/
  fi
}

download_bundle() {
  if [ ! -d "$BUNDLE_PATH" ] || [ -z "$(ls -A "$BUNDLE_PATH" 2>/dev/null)" ]; then
    mkdir -p "$BUNDLE_PATH"
    warn "RQAlpha bundle missing; downloading to $BUNDLE_PATH (first start may take a while)."
    flag="$(supports_data_path download-bundle)"
    if [ -n "$flag" ]; then
      rqalpha download-bundle "$flag" "$BUNDLE_PATH"
    else
      rqalpha download-bundle
      copy_default_bundle_if_needed
    fi
  fi
}

update_bundle() {
  update_subcmd="update-bundle"
  if ! rqalpha update-bundle --help >/dev/null 2>&1; then
    update_subcmd="download-bundle"
  fi

  flag="$(supports_data_path "$update_subcmd")"
  if [ -n "$flag" ]; then
    rqalpha "$update_subcmd" "$flag" "$BUNDLE_PATH"
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
    download_bundle
  fi
  setup_cron
fi

exec "$@"
