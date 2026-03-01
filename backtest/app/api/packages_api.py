"""Python packages management API endpoints."""
from flask import Blueprint, jsonify
import subprocess
import json
from datetime import datetime

from app.auth import auth_required
from app.database import get_db_connection

bp_packages = Blueprint('packages', __name__, url_prefix='/api/packages')


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
        updated_at = datetime.utcnow().isoformat()

        with get_db_connection('market_data') as db:
            db.begin_transaction()
            db.execute("DELETE FROM python_packages")
            db.executemany(
                "INSERT INTO python_packages (package_name, version, updated_at) VALUES (?, ?, ?)",
                [(pkg['name'], pkg['version'], updated_at) for pkg in packages],
            )
            db.commit()

        return True

    except Exception as e:
        print(f"Failed to refresh packages cache: {e}")
        return False


@bp_packages.route('/list', methods=['GET'])
@auth_required
def list_packages():
    """List all installed Python packages from cache."""
    try:
        with get_db_connection('market_data') as db:
            packages = db.fetchall("""
                SELECT package_name as name, version, updated_at
                FROM python_packages
                ORDER BY package_name
            """)

        updated_at = packages[0]['updated_at'] if packages else None

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
