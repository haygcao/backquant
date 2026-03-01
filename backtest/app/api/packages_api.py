"""Python packages management API endpoints."""
from flask import Blueprint, jsonify
import subprocess
import json
import sqlite3
from pathlib import Path
from datetime import datetime

from app.auth import auth_required

bp_packages = Blueprint('packages', __name__, url_prefix='/api/packages')


def _get_db_path():
    """Get database path."""
    from app.market_data.utils import get_market_data_db_path
    return get_market_data_db_path()


def refresh_packages_cache():
    """Refresh Python packages cache in database."""
    try:
        # Run pip list to get current packages
        result = subprocess.run(
            ['pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False

        packages = json.loads(result.stdout)
        db_path = _get_db_path()
        conn = sqlite3.connect(str(db_path))

        # Clear existing packages
        conn.execute("DELETE FROM python_packages")

        # Insert new packages
        updated_at = datetime.utcnow().isoformat()
        for pkg in packages:
            conn.execute(
                "INSERT INTO python_packages (package_name, version, updated_at) VALUES (?, ?, ?)",
                (pkg['name'], pkg['version'], updated_at)
            )

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Failed to refresh packages cache: {e}")
        return False


@bp_packages.route('/list', methods=['GET'])
@auth_required
def list_packages():
    """List all installed Python packages from cache."""
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT package_name as name, version, updated_at
            FROM python_packages
            ORDER BY package_name
        """)

        packages = [dict(row) for row in cursor.fetchall()]

        # Get the last update time
        updated_at = packages[0]['updated_at'] if packages else None

        conn.close()

        return jsonify({
            'packages': [{'name': p['name'], 'version': p['version']} for p in packages],
            'updated_at': updated_at
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_packages.route('/refresh', methods=['POST'])
@auth_required
def refresh_packages():
    """Manually refresh Python packages cache."""
    try:
        success = refresh_packages_cache()
        if success:
            return jsonify({'message': '包列表已刷新'}), 200
        else:
            return jsonify({'error': '刷新失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
