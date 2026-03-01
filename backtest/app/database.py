"""Database abstraction layer for SQLite and MariaDB support.

This module provides a unified interface for database operations,
supporting both SQLite (default) and MariaDB backends.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from flask import current_app


class DatabaseConfig:
    """Database configuration holder."""

    def __init__(self):
        self.db_type = 'sqlite'  # 'sqlite' or 'mariadb'
        self.sqlite_path: Optional[Path] = None
        # MariaDB config
        self.host: Optional[str] = None
        self.port: int = 3306
        self.database: Optional[str] = None
        self.user: Optional[str] = None
        self.password: Optional[str] = None

    @classmethod
    def from_flask_config(cls, db_name: str = 'default') -> DatabaseConfig:
        """Create config from Flask app config.

        Args:
            db_name: Database identifier ('auth', 'market_data', 'backtest_meta')

        Returns:
            DatabaseConfig instance
        """
        config = cls()
        config.db_type = current_app.config.get('DB_TYPE', 'sqlite').lower()

        if config.db_type == 'sqlite':
            # SQLite path based on database name
            if db_name == 'auth':
                from app.api.login_api import _auth_db_path
                config.sqlite_path = _auth_db_path()
            elif db_name == 'market_data':
                from app.market_data.utils import get_market_data_db_path
                config.sqlite_path = get_market_data_db_path()
            elif db_name == 'backtest_meta':
                base_dir = Path(str(current_app.config.get("BACKTEST_BASE_DIR", "/tmp")))
                rename_db = current_app.config.get("BACKTEST_RENAME_DB_PATH", "")
                if rename_db:
                    config.sqlite_path = Path(rename_db).expanduser()
                else:
                    config.sqlite_path = base_dir / "backtest_meta.sqlite3"
            else:
                raise ValueError(f"Unknown database name: {db_name}")
        else:
            # MariaDB config
            config.host = current_app.config.get('DB_HOST', 'localhost')
            config.port = current_app.config.get('DB_PORT', 3306)
            config.database = current_app.config.get('DB_NAME', 'backquant')
            config.user = current_app.config.get('DB_USER', 'root')
            config.password = current_app.config.get('DB_PASSWORD', '')

        return config

    def to_dict(self) -> dict:
        """Serialize to a plain dict for cross-thread passing (no Flask context needed).

        Returns:
            dict with all connection parameters
        """
        return {
            'db_type': self.db_type,
            'sqlite_path': str(self.sqlite_path) if self.sqlite_path else None,
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> DatabaseConfig:
        """Reconstruct config from dict (for background threads without Flask context).

        Args:
            config_dict: dict previously produced by to_dict()

        Returns:
            DatabaseConfig instance
        """
        config = cls()
        config.db_type = config_dict.get('db_type', 'sqlite')
        if config.db_type == 'sqlite':
            path = config_dict.get('sqlite_path')
            config.sqlite_path = Path(path) if path else None
        else:
            config.host = config_dict.get('host', 'localhost')
            config.port = config_dict.get('port', 3306)
            config.database = config_dict.get('database')
            config.user = config_dict.get('user')
            config.password = config_dict.get('password')
        return config


class DatabaseConnection:
    """Unified database connection wrapper."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._conn = None

    def connect(self):
        """Establish database connection."""
        if self.config.db_type == 'sqlite':
            self._conn = self._connect_sqlite()
        elif self.config.db_type == 'mariadb':
            self._conn = self._connect_mariadb()
        else:
            raise ValueError(f"Unsupported database type: {self.config.db_type}")
        return self._conn

    def _connect_sqlite(self):
        """Connect to SQLite database."""
        if not self.config.sqlite_path:
            raise ValueError("SQLite path not configured")

        # Ensure parent directory exists
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(self.config.sqlite_path),
            timeout=30,
            isolation_level=None,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_mariadb(self):
        """Connect to MariaDB database."""
        try:
            import pymysql
        except ImportError:
            raise ImportError(
                "pymysql is required for MariaDB support. "
                "Install it with: pip install pymysql"
            )

        conn = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        return conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _normalize_query(self, query: str) -> str:
        """Convert ? placeholders to %s for MariaDB."""
        if self.config.db_type == 'mariadb':
            return query.replace('?', '%s')
        return query

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query and return cursor.

        Automatically converts ? placeholders to %s for MariaDB.

        Args:
            query: SQL query string (use ? as placeholder for both backends)
            params: Query parameters

        Returns:
            Cursor object
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = self._normalize_query(query)
        cursor = self._conn.cursor()
        cursor.execute(query, params)
        return cursor

    def executemany(self, query: str, params_list: list) -> Any:
        """Execute a query with multiple parameter sets.

        Automatically converts ? placeholders to %s for MariaDB.

        Args:
            query: SQL query string (use ? as placeholder)
            params_list: List of parameter tuples

        Returns:
            Cursor object
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = self._normalize_query(query)
        cursor = self._conn.cursor()
        cursor.executemany(query, params_list)
        return cursor

    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and fetch one result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row as dict, or None
        """
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None

        if self.config.db_type == 'sqlite':
            return dict(row)
        else:
            return row

    def fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute query and fetch all results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        cursor = self.execute(query, params)
        rows = cursor.fetchall()

        if self.config.db_type == 'sqlite':
            return [dict(row) for row in rows]
        else:
            return rows

    def replace_into(self, table: str, columns: list[str], values: tuple) -> Any:
        """Cross-database compatible INSERT OR REPLACE.

        SQLite: INSERT OR REPLACE INTO table (...) VALUES (?)
        MariaDB: REPLACE INTO table (...) VALUES (%s)

        execute() handles placeholder conversion automatically.

        Args:
            table: Table name
            columns: List of column names
            values: Tuple of values

        Returns:
            Cursor object
        """
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(values))
        if self.config.db_type == 'sqlite':
            query = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        else:
            query = f"REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        return self.execute(query, values)

    def upsert(self, table: str, insert_cols: list[str], insert_vals: tuple,
               conflict_col: str, update_cols: list[str]) -> Any:
        """Cross-database compatible UPSERT.

        SQLite: INSERT INTO ... ON CONFLICT(col) DO UPDATE SET col=excluded.col, ...
        MariaDB: INSERT INTO ... ON DUPLICATE KEY UPDATE col=VALUES(col), ...

        execute() handles placeholder conversion automatically.

        Args:
            table: Table name
            insert_cols: List of column names to insert
            insert_vals: Tuple of values to insert
            conflict_col: Conflict key column (used by SQLite ON CONFLICT clause)
            update_cols: Columns to update on conflict (excluding primary key)

        Returns:
            Cursor object
        """
        cols = ', '.join(insert_cols)
        placeholders = ', '.join(['?'] * len(insert_vals))
        if self.config.db_type == 'sqlite':
            updates = ', '.join(f"{c} = excluded.{c}" for c in update_cols)
            query = (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                     f"ON CONFLICT({conflict_col}) DO UPDATE SET {updates}")
        else:
            updates = ', '.join(f"{c} = VALUES({c})" for c in update_cols)
            query = (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                     f"ON DUPLICATE KEY UPDATE {updates}")
        return self.execute(query, insert_vals)

    def begin_transaction(self):
        """Begin a transaction.

        SQLite: BEGIN IMMEDIATE (exclusive write lock)
        MariaDB: conn.begin() (pymysql disables autocommit and starts transaction)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")
        if self.config.db_type == 'sqlite':
            self._conn.execute("BEGIN IMMEDIATE")
        else:
            self._conn.begin()

    def commit(self):
        """Commit transaction (works for both SQLite and MariaDB)."""
        if self._conn:
            self._conn.commit()

    def rollback(self):
        """Rollback transaction."""
        if self._conn:
            self._conn.rollback()


@contextmanager
def get_db_connection(
    db_name: str = 'default',
    config_dict: Optional[dict] = None,
) -> Generator[DatabaseConnection, None, None]:
    """Get database connection context manager.

    Can be called with Flask app context (using db_name) or without
    Flask context (using config_dict from DatabaseConfig.to_dict()).

    Usage with Flask context:
        with get_db_connection('market_data') as db:
            result = db.fetchone("SELECT * FROM table WHERE id = ?", (1,))

    Usage in background threads (no Flask context):
        with get_db_connection(config_dict=saved_config_dict) as db:
            result = db.fetchone("SELECT * FROM table WHERE id = ?", (1,))

    Args:
        db_name: Database identifier ('auth', 'market_data', 'backtest_meta')
        config_dict: Pre-serialized config dict from DatabaseConfig.to_dict().
                     When provided, db_name is ignored and Flask context is not required.

    Yields:
        DatabaseConnection instance
    """
    if config_dict is not None:
        config = DatabaseConfig.from_dict(config_dict)
    else:
        config = DatabaseConfig.from_flask_config(db_name)
    conn = DatabaseConnection(config)
    conn.connect()
    try:
        yield conn
    finally:
        conn.close()


def get_db_type() -> str:
    """Get current database type from config.

    Returns:
        'sqlite' or 'mariadb'
    """
    return current_app.config.get('DB_TYPE', 'sqlite').lower()
