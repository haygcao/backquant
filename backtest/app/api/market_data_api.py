"""Market data management API endpoints."""
from flask import Blueprint, jsonify, request
from pathlib import Path
import os
import sqlite3
from datetime import datetime

from app.auth import auth_required
from app.market_data.task_manager import get_task_manager
from app.market_data.analyzer import analyze_bundle
from app.market_data.tasks import do_incremental_update, do_full_download
from app.market_data.utils import is_current_month_updated

bp_market_data = Blueprint('market_data', __name__, url_prefix='/api/market-data')


def _get_db_path():
    """Get database path."""
    from app.market_data.utils import get_market_data_db_path
    return get_market_data_db_path()


def _get_bundle_path():
    """Get bundle path."""
    return Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))


@bp_market_data.route('/overview', methods=['GET'])
@auth_required
def get_overview():
    """Get data overview."""
    db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM market_data_stats WHERE id = 1")
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({
                'analyzed': False,
                'message': '尚未分析数据，请先触发数据分析'
            }), 200

        result = {
            'analyzed': True,
            'data': dict(row)
        }

        # Get file list
        cursor = conn.execute("""
            SELECT file_name, file_path, file_size, modified_at
            FROM market_data_files
            ORDER BY file_name
        """)
        files = [dict(row) for row in cursor.fetchall()]
        result['files'] = files

        conn.close()
        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/analyze', methods=['POST'])
@auth_required
def trigger_analyze():
    """Trigger data analysis."""
    try:
        tm = get_task_manager()
        bundle_path = _get_bundle_path()
        db_path = _get_db_path()

        # Get source from request body, default to 'manual'
        source = 'manual'
        if request.json:
            source = request.json.get('source', 'manual')

        task_id = tm.submit_task(
            'analyze',
            analyze_bundle,
            task_args=(bundle_path, db_path),
            source=source
        )

        return jsonify({'task_id': task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/download/incremental', methods=['POST'])
@auth_required
def trigger_incremental():
    """Trigger incremental update."""
    bundle_path = _get_bundle_path()
    force = request.json.get('force', False) if request.json else False

    # Check if confirmation needed
    if not force and is_current_month_updated(bundle_path):
        return jsonify({
            'need_confirm': True,
            'message': '检测到当月已有更新，确定要再次更新吗？'
        }), 200

    try:
        tm = get_task_manager()
        task_id = tm.submit_task('incremental', do_incremental_update, source='manual')
        return jsonify({'task_id': task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/download/full', methods=['POST'])
@auth_required
def trigger_full():
    """Trigger full download."""
    from app.market_data.utils import get_bundle_update_status

    bundle_path = _get_bundle_path()
    force = request.json.get('force', False) if request.json else False

    # Check if confirmation needed
    if not force:
        needs_confirm, message = get_bundle_update_status(bundle_path)
        if needs_confirm and message:
            return jsonify({
                'need_confirm': True,
                'message': message
            }), 200

    try:
        tm = get_task_manager()
        task_id = tm.submit_task('full', do_full_download, source='manual')
        return jsonify({'task_id': task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/tasks/running', methods=['GET'])
@auth_required
def get_running_task():
    """Get currently running task."""
    try:
        tm = get_task_manager()
        task = tm.get_running_task()

        if not task:
            return jsonify({'task': None}), 200

        return jsonify({'task': task}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/tasks/<task_id>', methods=['GET'])
@auth_required
def get_task_status(task_id: str):
    """Get task status."""
    try:
        tm = get_task_manager()
        task = tm.get_task_status(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        return jsonify(task), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/tasks/<task_id>/retry', methods=['POST'])
@auth_required
def retry_task(task_id: str):
    """Retry failed task."""
    tm = get_task_manager()
    task = tm.get_task_status(task_id)

    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if task['status'] != 'failed':
        return jsonify({'error': '只能重试失败的任务'}), 400

    # Resubmit based on task type
    task_type = task['task_type']
    try:
        if task_type == 'analyze':
            bundle_path = _get_bundle_path()
            db_path = _get_db_path()
            new_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='retry')
        elif task_type == 'incremental':
            new_task_id = tm.submit_task('incremental', do_incremental_update, source='retry')
        elif task_type == 'full':
            new_task_id = tm.submit_task('full', do_full_download, source='retry')
        else:
            return jsonify({'error': '未知任务类型'}), 400

        return jsonify({'task_id': new_task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/cron/config', methods=['GET'])
@auth_required
def get_cron_config():
    """Get cron configuration."""
    db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM market_data_cron_config WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            # Initialize with default values
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                INSERT INTO market_data_cron_config
                (id, enabled, cron_expression, task_type, updated_at)
                VALUES (1, 1, '0 4 1 * *', 'full', ?)
            """, (datetime.utcnow().isoformat(),))
            conn.commit()
            conn.close()
            return jsonify({
                'enabled': True,
                'cron_expression': '0 4 1 * *',
                'task_type': 'full'
            }), 200

        return jsonify(dict(row)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/cron/config', methods=['PUT'])
@auth_required
def update_cron_config():
    """Update cron configuration."""
    data = request.json
    enabled = data.get('enabled', False)
    cron_expression = data.get('cron_expression', '0 2 1 * *')
    task_type = data.get('task_type', 'incremental')

    if task_type not in ('incremental', 'full'):
        return jsonify({'error': '无效的任务类型'}), 400

    db_path = _get_db_path()

    try:
        # Validate cron expression
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(cron_expression)
        except Exception:
            return jsonify({'error': '无效的 cron 表达式'}), 400

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT OR REPLACE INTO market_data_cron_config
            (id, enabled, cron_expression, task_type, updated_at)
            VALUES (1, ?, ?, ?, ?)
        """, (1 if enabled else 0, cron_expression, task_type, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

        # Update scheduler
        from app.market_data.scheduler import update_cron_schedule
        if enabled:
            update_cron_schedule(cron_expression)
        else:
            update_cron_schedule(None)

        return jsonify({'message': '配置已更新'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/logs', methods=['GET'])
@auth_required
def get_all_logs():
    """Get all task logs (including manual and cron tasks)."""
    db_path = _get_db_path()
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Get task logs with task info
        cursor = conn.execute("""
            SELECT
                tl.log_id,
                tl.task_id,
                tl.timestamp,
                tl.level,
                tl.message,
                t.task_type,
                t.status as task_status,
                t.source
            FROM market_data_task_logs tl
            LEFT JOIN market_data_tasks t ON tl.task_id = t.task_id
            ORDER BY tl.timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        logs = [dict(row) for row in cursor.fetchall()]

        cursor = conn.execute("SELECT COUNT(*) FROM market_data_task_logs")
        total = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            'logs': logs,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/cron/logs', methods=['GET'])
@auth_required
def get_cron_logs():
    """Get cron logs."""
    db_path = _get_db_path()
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT * FROM market_data_cron_logs
            ORDER BY trigger_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        logs = [dict(row) for row in cursor.fetchall()]

        cursor = conn.execute("SELECT COUNT(*) FROM market_data_cron_logs")
        total = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            'logs': logs,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp_market_data.route('/cron/logs/<int:log_id>', methods=['GET'])
@auth_required
def get_cron_log_detail(log_id: int):
    """Get cron log detail."""
    db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM market_data_cron_logs WHERE log_id = ?",
            (log_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'error': '日志不存在'}), 404

        log = dict(row)

        # Get associated task if exists
        if log['task_id']:
            cursor = conn.execute(
                "SELECT * FROM market_data_tasks WHERE task_id = ?",
                (log['task_id'],)
            )
            task_row = cursor.fetchone()
            if task_row:
                log['task'] = dict(task_row)

        conn.close()

        return jsonify(log), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
