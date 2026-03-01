"""Scheduler for cron jobs."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
from datetime import datetime
import logging

from app.database import DatabaseConfig, get_db_connection

logger = logging.getLogger(__name__)

_scheduler = None

# Serialized DB config stored at init_scheduler() time (Flask context).
# APScheduler callbacks run in background threads without Flask context,
# so this dict is used to reconnect without current_app.
# init_scheduler() is called exactly once during app startup (create_app).
_db_config_dict: dict = None


def get_scheduler():
    """Get scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        logger.info('APScheduler started')
    return _scheduler


def load_cron_config() -> dict:
    """Load cron configuration from database."""
    with get_db_connection(config_dict=_db_config_dict) as db:
        return db.fetchone("SELECT * FROM market_data_cron_config WHERE id = 1")


def cron_job_handler():
    """Cron job handler."""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.tasks import do_full_download, do_incremental_update

    config = load_cron_config()

    if not config or not config['enabled']:
        logger.info('Cron job disabled, skipping')
        _log_cron_run(None, 'skipped', '定时任务未启用')
        return

    tm = get_task_manager()

    # Check for running tasks (mutex)
    if tm._has_running_task():
        logger.warning('Task already running, skipping cron job')
        _log_cron_run(None, 'skipped', '已有任务正在运行')
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
        _log_cron_run(task_id, 'success', f'已提交任务: {task_id}')

    except Exception as e:
        logger.error(f'Cron job failed: {str(e)}')
        _log_cron_run(None, 'failed', str(e))


def _log_cron_run(task_id, status: str, message: str):
    """Log cron run."""
    with get_db_connection(config_dict=_db_config_dict) as db:
        db.execute(
            """INSERT INTO market_data_cron_logs
               (task_id, trigger_time, status, message)
               VALUES (?, ?, ?, ?)""",
            (task_id, datetime.utcnow().isoformat(), status, message)
        )


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
    """Initialize scheduler on app startup.

    Must be called once within a Flask application context (e.g., from create_app).
    Stores the DB connection config so that APScheduler background threads can
    connect without a Flask context.
    """
    global _db_config_dict

    config = DatabaseConfig.from_flask_config('market_data')
    _db_config_dict = config.to_dict()

    cron_config = load_cron_config()

    if cron_config and cron_config['enabled'] and cron_config['cron_expression']:
        update_cron_schedule(cron_config['cron_expression'])
        logger.info(f'Cron schedule loaded: {cron_config["cron_expression"]}')
