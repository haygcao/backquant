"""Utility functions for market data management."""
from pathlib import Path
from datetime import datetime


def is_current_month_updated(bundle_path: Path) -> bool:
    """Check if bundle was updated in the current month.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        True if bundle was updated this month (needs confirmation)
        False if not updated or not current month (can proceed)
    """
    if not bundle_path.exists():
        return False

    # Find most recently modified file
    latest_mtime = None
    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            mtime = file_path.stat().st_mtime
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime is None:
        return False

    # Compare modification time with current month
    latest_date = datetime.fromtimestamp(latest_mtime)
    current_date = datetime.now()

    return (latest_date.year == current_date.year and
            latest_date.month == current_date.month)
