"""Utility functions for market data management."""
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
from flask import current_app


def get_market_data_db_path() -> Path:
    """Get market data database path.

    Priority:
    1. MARKET_DATA_DB_PATH environment variable (if set)
    2. <BACKTEST_BASE_DIR>/market_data.sqlite3 (default, persisted in volume)

    Returns:
        Path: Absolute path to market_data.sqlite3
    """
    raw = str(current_app.config.get("MARKET_DATA_DB_PATH", "") or "").strip()
    if raw:
        return Path(raw).expanduser()

    base_dir = Path(str(current_app.config.get("BACKTEST_BASE_DIR", "/tmp"))).expanduser()
    return base_dir / "market_data.sqlite3"


def get_bundle_update_status(bundle_path: Path) -> Tuple[bool, Optional[str]]:
    """Check bundle update status and return confirmation message if needed.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        Tuple of (needs_confirm, message)
        - needs_confirm: True if user confirmation is needed
        - message: Confirmation message to show user, or None
    """
    if not bundle_path.exists():
        return False, None

    # Find most recently modified file
    latest_mtime = None
    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            mtime = file_path.stat().st_mtime
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime is None:
        return False, None

    # Compare modification time with current date
    latest_date = datetime.fromtimestamp(latest_mtime)
    current_date = datetime.now()

    # Check if updated this month
    if latest_date.year == current_date.year and latest_date.month == current_date.month:
        return True, f'检测到当月数据已更新（{latest_date.strftime("%Y-%m-%d")}），确定要重新下载吗？'

    # Check if updated last month
    last_month = current_date.month - 1 if current_date.month > 1 else 12
    last_year = current_date.year if current_date.month > 1 else current_date.year - 1

    if latest_date.year == last_year and latest_date.month == last_month:
        return True, f'检测到上月数据（{latest_date.strftime("%Y-%m-%d")}），确定要更新当月数据吗？'

    # Older data, suggest update
    return True, f'数据较旧（{latest_date.strftime("%Y-%m-%d")}），建议更新到当月数据。'


def is_current_month_updated(bundle_path: Path) -> bool:
    """Check if bundle was updated in the current month.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        True if bundle was updated this month (needs confirmation)
        False if not updated or not current month (can proceed)
    """
    needs_confirm, _ = get_bundle_update_status(bundle_path)
    return needs_confirm
