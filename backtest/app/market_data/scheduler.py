"""Scheduler for cron jobs."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import sqlite3
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    """Get scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        logger.info('APScheduler started')
    return _scheduler


def load_cron_config(db_path: Path) -> dict:
    """Load cron configuration from database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM market_data_cron_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def cron_job_handler():
    """Cron job handler."""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.tasks import do_full_download, do_incremental_update

    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    config = load_cron_config(db_path)

    if not config or not config['enabled']:
        logger.info('Cron job disabled, skipping')
        _log_cron_run(db_path, None, 'skipped', '定时任务未启用')
        return

    tm = get_task_manager()

    # Check for running tasks (mutex)
    if tm._has_running_task():
        logger.warning('Task already running, skipping cron job')
        _log_cron_run(db_path, None, 'skipped', '已有任务正在运行')
        return

    # Submit task based on config
    task_type = config['task_type']
    try:
        if task_type == 'full':
            task_id = tm.submit_task('full', do_full_download, source='cron')
        elif task_type == 'incremental':
            task_id = tm.submit_task('incremental', do_incremental_update, source='cron')
        else:
            raise ValueError(f'Unknown task type: {task_type}')

        logger.info(f'Cron job submitted task: {task_id}')
        _log_cron_run(db_path, task_id, 'success', f'已提交任务: {task_id}')

    except Exception as e:
        logger.error(f'Cron job failed: {str(e)}')
        _log_cron_run(db_path, None, 'failed', str(e))


def _log_cron_run(db_path: Path, task_id: str, status: str, message: str):
    """Log cron run."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO market_data_cron_logs
           (task_id, trigger_time, status, message)
           VALUES (?, ?, ?, ?)""",
        (task_id, datetime.utcnow().isoformat(), status, message)
    )
    conn.commit()
    conn.close()


def update_cron_schedule(cron_expression: str):
    """Update cron schedule."""
    scheduler = get_scheduler()

    # Remove old jobs
    scheduler.remove_all_jobs()

    # Add new job
    if cron_expression:
        trigger = CronTrigger.from_crontab(cron_expression)
        scheduler.add_job(
            cron_job_handler,
            trigger=trigger,
            id='market_data_cron',
            replace_existing=True
        )
        logger.info(f'Cron schedule updated: {cron_expression}')


def init_scheduler():
    """Initialize scheduler on app startup."""
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    config = load_cron_config(db_path)

    if config and config['enabled'] and config['cron_expression']:
        update_cron_schedule(config['cron_expression'])
        logger.info(f'Cron schedule loaded: {config["cron_expression"]}')
