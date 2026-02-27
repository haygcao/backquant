"""Task manager for market data operations."""
import threading
import uuid
from datetime import datetime
from typing import Optional, Callable
from queue import Queue
from pathlib import Path
import sqlite3


class TaskManager:
    """Lightweight task manager for market data operations."""

    def __init__(self, db_path: str, max_workers: int = 1):
        self.db_path = db_path
        self.max_workers = max_workers
        self.task_queue = Queue()
        self.workers = []
        self.lock = threading.Lock()
        self._init_db()
        self._start_workers()

    def _init_db(self):
        """Initialize database tables."""
        from app.market_data.db_init import init_database
        init_database(Path(self.db_path))

    def _start_workers(self):
        """Start worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"TaskWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        """Worker thread main loop."""
        while True:
            task_id, task_func, task_args = self.task_queue.get()
            try:
                self._update_task_status(task_id, 'running', started_at=datetime.utcnow())
                task_func(task_id, *task_args)
                self._update_task_status(task_id, 'success', finished_at=datetime.utcnow())
            except Exception as e:
                self._update_task_status(
                    task_id, 'failed',
                    error=str(e),
                    finished_at=datetime.utcnow()
                )
            finally:
                self.task_queue.task_done()

    def submit_task(self, task_type: str, task_func: Callable,
                    task_args: tuple = (), source: str = 'manual') -> str:
        """Submit a task for execution."""
        with self.lock:
            if self._has_running_task():
                raise RuntimeError("已有任务正在运行，请等待完成后再试")

            task_id = str(uuid.uuid4())
            self._create_task(task_id, task_type, source)
            self.task_queue.put((task_id, task_func, task_args))
            return task_id

    def _has_running_task(self) -> bool:
        """Check if there is a running task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM market_data_tasks WHERE status IN ('pending', 'running')"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def _create_task(self, task_id: str, task_type: str, source: str):
        """Create task record."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO market_data_tasks
               (task_id, task_type, status, source, created_at)
               VALUES (?, ?, 'pending', ?, ?)""",
            (task_id, task_type, source, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def _update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status."""
        conn = sqlite3.connect(self.db_path)

        updates = ["status = ?"]
        params = [status]

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value.isoformat() if isinstance(value, datetime) else value)

        params.append(task_id)
        sql = f"UPDATE market_data_tasks SET {', '.join(updates)} WHERE task_id = ?"
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def update_progress(self, task_id: str, progress: int, stage: str, message: str):
        """Update task progress."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """UPDATE market_data_tasks
               SET progress = ?, stage = ?, message = ?
               WHERE task_id = ?""",
            (progress, stage, message, task_id)
        )
        conn.commit()
        conn.close()

    def log(self, task_id: str, level: str, message: str):
        """Log task message."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO market_data_task_logs
               (task_id, timestamp, level, message)
               VALUES (?, ?, ?, ?)""",
            (task_id, datetime.utcnow().isoformat(), level, message)
        )
        conn.commit()
        conn.close()

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM market_data_tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


# Global singleton
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get task manager singleton."""
    global _task_manager
    if _task_manager is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _task_manager = TaskManager(str(db_path), max_workers=1)
    return _task_manager
