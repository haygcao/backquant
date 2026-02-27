"""Database initialization for market data management."""
import sqlite3
from pathlib import Path


def init_database(db_path: Path):
    """Initialize database tables for market data management.

    This function is idempotent and can be called multiple times.

    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. Tasks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            stage TEXT,
            message TEXT,
            source TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_created
        ON market_data_tasks(created_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_status
        ON market_data_tasks(status)
    """)

    # 2. Task logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_task_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES market_data_tasks(task_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_task
        ON market_data_task_logs(task_id, timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp
        ON market_data_task_logs(timestamp DESC)
    """)

    # 3. Stats table (single row)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            bundle_path TEXT NOT NULL,
            last_modified TEXT,
            total_files INTEGER,
            total_size_bytes INTEGER,
            analyzed_at TEXT NOT NULL,
            stock_count INTEGER DEFAULT 0,
            fund_count INTEGER DEFAULT 0,
            futures_count INTEGER DEFAULT 0,
            index_count INTEGER DEFAULT 0,
            bond_count INTEGER DEFAULT 0
        )
    """)

    # 4. Cron config table (single row)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_cron_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 0,
            cron_expression TEXT,
            task_type TEXT,
            updated_at TEXT NOT NULL
        )
    """)

    # 5. Cron logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_cron_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            trigger_time TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            FOREIGN KEY (task_id) REFERENCES market_data_tasks(task_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cron_logs_time
        ON market_data_cron_logs(trigger_time DESC)
    """)

    conn.commit()
    conn.close()
