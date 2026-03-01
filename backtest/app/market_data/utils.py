"""Utility functions for market data management."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from flask import current_app

_BEIJING_TZ = timezone(timedelta(hours=8))


def get_market_data_db_path() -> Path:
    """Get market data database path."""
    raw = str(current_app.config.get("MARKET_DATA_DB_PATH", "") or "").strip()
    if raw:
        return Path(raw).expanduser()
    base_dir = Path(str(current_app.config.get("BACKTEST_BASE_DIR", "/tmp"))).expanduser()
    return base_dir / "market_data.sqlite3"


def get_bundle_update_status(bundle_path: Path) -> Tuple[bool, Optional[str]]:
    """Check local bundle status and return (needs_confirm, message).

    Returns (True, message) if a local bundle exists; (False, None) otherwise.
    No CDN probing — the actual download will resolve the latest available package.
    """
    if not bundle_path.exists():
        return False, None

    latest_mtime = None
    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            mtime = file_path.stat().st_mtime
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime is None:
        return False, None

    latest_date = datetime.fromtimestamp(latest_mtime, tz=_BEIJING_TZ)
    local_tag = f"rqbundle_{latest_date.year}{latest_date.month:02d}"

    return True, f'当前本地数据包为 {local_tag}，确定要下载最新数据包吗？'


def is_current_month_updated(bundle_path: Path) -> bool:
    """Check if bundle was updated in the current month (Beijing time)."""
    needs_confirm, _ = get_bundle_update_status(bundle_path)
    return needs_confirm
