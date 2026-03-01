#!/usr/bin/env python3
"""Migrate SQLite data to MariaDB for the BackQuant platform.

Reads all three SQLite databases (auth, market_data, backtest_meta) and
inserts their rows into MariaDB using INSERT IGNORE (idempotent; safe to
re-run multiple times without corrupting existing data).

Usage:
    # Default paths, credentials from env vars
    python migrate_sqlite_to_mariadb.py

    # Explicit paths / credentials
    python migrate_sqlite_to_mariadb.py \\
        --host mariadb --user backquant_user --password backquant_pass

    # Dry-run: print row counts only, do not write
    python migrate_sqlite_to_mariadb.py --dry-run

    # Run from Docker host
    docker exec backquant-backend-1 \\
        python /app/scripts/migrate_sqlite_to_mariadb.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def _to_mariadb_ts(value: Any) -> Optional[str]:
    """Convert a SQLite timestamp value to a MariaDB TIMESTAMP string.

    Returns None for NULL / empty strings.
    Returns 'YYYY-MM-DD HH:MM:SS' strings for parseable timestamps.
    Passes through already-formatted strings if all else fails.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in _TIMESTAMP_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        # Return as-is and let MariaDB parse it; worst case it will error
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# Per-table migration definitions
# ---------------------------------------------------------------------------
#
# Each entry describes one table:
#   db        : source SQLite db alias ('auth', 'market_data', 'backtest_meta')
#   table     : table name (same in SQLite and MariaDB)
#   columns   : tuple of column names to select/insert (omit AUTO_INCREMENT PKs)
#   ts_cols   : set of column names that need timestamp conversion
#   auto_pk   : True when the PK is AUTO_INCREMENT and must be carried over
#               by including it explicitly in the INSERT
#
# Rows are inserted with INSERT IGNORE INTO so duplicate PKs are silently
# skipped.

_MIGRATIONS = [
    # 1. users (auth)
    {
        "db": "auth",
        "table": "users",
        "columns": ("id", "username", "password_hash", "is_admin", "created_at"),
        "ts_cols": {"created_at"},
    },
    # 2. market_data_tasks  (no AUTO_INCREMENT PK — task_id is TEXT)
    {
        "db": "market_data",
        "table": "market_data_tasks",
        "columns": (
            "task_id", "task_type", "status", "progress", "stage",
            "message", "source", "created_at", "started_at", "finished_at", "error",
        ),
        "ts_cols": {"created_at", "started_at", "finished_at"},
    },
    # 3. market_data_stats  (singleton row, id=1)
    {
        "db": "market_data",
        "table": "market_data_stats",
        "columns": (
            "id", "bundle_path", "last_modified", "total_files",
            "total_size_bytes", "analyzed_at",
            "stock_count", "fund_count", "futures_count", "index_count", "bond_count",
        ),
        "ts_cols": {"last_modified", "analyzed_at"},
    },
    # 4. market_data_cron_config  (singleton row, id=1)
    {
        "db": "market_data",
        "table": "market_data_cron_config",
        "columns": ("id", "enabled", "cron_expression", "task_type", "updated_at"),
        "ts_cols": {"updated_at"},
    },
    # 5. market_data_task_logs  (AUTO_INCREMENT log_id — carry it over)
    {
        "db": "market_data",
        "table": "market_data_task_logs",
        "columns": ("log_id", "task_id", "timestamp", "level", "message"),
        "ts_cols": {"timestamp"},
    },
    # 6. market_data_cron_logs  (AUTO_INCREMENT log_id)
    {
        "db": "market_data",
        "table": "market_data_cron_logs",
        "columns": ("log_id", "task_id", "trigger_time", "status", "message"),
        "ts_cols": {"trigger_time"},
    },
    # 7. market_data_files  (AUTO_INCREMENT file_id)
    {
        "db": "market_data",
        "table": "market_data_files",
        "columns": ("file_id", "file_name", "file_path", "file_size", "modified_at"),
        "ts_cols": {"modified_at"},
    },
    # 8. python_packages  (TEXT PK)
    {
        "db": "market_data",
        "table": "python_packages",
        "columns": ("package_name", "version", "updated_at"),
        "ts_cols": {"updated_at"},
    },
    # 9. backtest_strategy_rename_map  (TEXT PK)
    {
        "db": "backtest_meta",
        "table": "backtest_strategy_rename_map",
        "columns": ("from_id", "to_id", "updated_at", "updated_by"),
        "ts_cols": {"updated_at"},
    },
]

# Group by db alias for transaction management
_DB_ORDER = ["auth", "market_data", "backtest_meta"]


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _open_sqlite(path: Path) -> Optional[sqlite3.Connection]:
    """Open SQLite DB; return None if file does not exist."""
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        return cur.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _sqlite_rows(conn: sqlite3.Connection, table: str, columns: tuple) -> list[tuple]:
    cols_str = ", ".join(columns)
    cur = conn.execute(f"SELECT {cols_str} FROM {table}")  # noqa: S608
    return cur.fetchall()


# ---------------------------------------------------------------------------
# MariaDB helpers
# ---------------------------------------------------------------------------

def _open_mariadb(args: argparse.Namespace):
    """Open MariaDB connection; raise on failure."""
    try:
        import pymysql
    except ImportError:
        print(
            "ERROR: pymysql is not installed.\n"
            "       Install it with: pip install pymysql",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    return conn


def _mariadb_row_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")  # noqa: S608
        row = cur.fetchone()
        return row["cnt"] if row else 0


def _mariadb_insert_ignore(conn, table: str, columns: tuple, rows: list[tuple]) -> int:
    """INSERT IGNORE rows into MariaDB table. Returns number of rows attempted."""
    if not rows:
        return 0
    cols_str = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT IGNORE INTO `{table}` ({cols_str}) VALUES ({placeholders})"  # noqa: S608
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Row conversion
# ---------------------------------------------------------------------------

def _convert_row(row: sqlite3.Row, columns: tuple, ts_cols: set) -> tuple:
    """Convert a SQLite row to a tuple ready for MariaDB insertion."""
    result = []
    for col in columns:
        val = row[col]
        if col in ts_cols:
            val = _to_mariadb_ts(val)
        result.append(val)
    return tuple(result)


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

class MigrationResult:
    """Collects per-table statistics."""

    def __init__(self):
        # table -> {"sqlite": int, "mariadb_before": int, "mariadb_after": int, "attempted": int}
        self.stats: dict[str, dict] = {}
        self.skipped_dbs: list[str] = []
        self.failed_dbs: list[str] = []

    def record(self, table: str, sqlite_count: int, before: int, after: int, attempted: int):
        self.stats[table] = {
            "sqlite": sqlite_count,
            "mariadb_before": before,
            "mariadb_after": after,
            "attempted": attempted,
            "inserted": after - before,
        }

    def print_summary(self):
        print()
        print("=" * 76)
        print(f"{'Table':<40} {'SQLite':>7} {'Before':>7} {'Inserted':>9} {'After':>7}")
        print("-" * 76)
        total_sqlite = total_inserted = 0
        for table, s in self.stats.items():
            print(
                f"{table:<40} {s['sqlite']:>7} {s['mariadb_before']:>7} "
                f"{s['inserted']:>9} {s['mariadb_after']:>7}"
            )
            total_sqlite += s["sqlite"]
            total_inserted += s["inserted"]
        print("-" * 76)
        print(f"{'TOTAL':<40} {total_sqlite:>7} {'':>7} {total_inserted:>9}")
        print("=" * 76)

        if self.skipped_dbs:
            print(f"\nSkipped DBs (file not found): {', '.join(self.skipped_dbs)}")
        if self.failed_dbs:
            print(f"\nFailed DBs (rolled back): {', '.join(self.failed_dbs)}")


def _migrate_db(
    db_alias: str,
    sqlite_conn: Optional[sqlite3.Connection],
    mariadb_conn,
    args: argparse.Namespace,
    result: MigrationResult,
):
    """Migrate all tables belonging to one logical DB within a single transaction."""
    if sqlite_conn is None:
        print(f"  [SKIP] {db_alias}: SQLite file not found — skipping")
        result.skipped_dbs.append(db_alias)
        return

    tables_for_db = [m for m in _MIGRATIONS if m["db"] == db_alias]

    print(f"\n--- Migrating '{db_alias}' ({len(tables_for_db)} tables) ---")

    if args.dry_run:
        for migration in tables_for_db:
            table = migration["table"]
            count = _sqlite_row_count(sqlite_conn, table)
            print(f"  [DRY-RUN] {table}: {count} rows in SQLite")
            result.record(table, count, 0, 0, 0)
        return

    # Real migration: wrap all tables in one transaction
    try:
        mariadb_conn.begin()

        for migration in tables_for_db:
            table = migration["table"]
            columns = migration["columns"]
            ts_cols = migration.get("ts_cols", set())

            # Count before
            sqlite_count = _sqlite_row_count(sqlite_conn, table)
            mariadb_before = _mariadb_row_count(mariadb_conn, table)

            # Fetch + convert rows
            raw_rows = _sqlite_rows(sqlite_conn, table, columns)
            converted = [_convert_row(r, columns, ts_cols) for r in raw_rows]

            # Insert
            attempted = _mariadb_insert_ignore(mariadb_conn, table, columns, converted)

            mariadb_after = _mariadb_row_count(mariadb_conn, table)
            result.record(table, sqlite_count, mariadb_before, mariadb_after, attempted)

            print(
                f"  {table}: {sqlite_count} SQLite rows → "
                f"{mariadb_after - mariadb_before} inserted "
                f"({mariadb_before} already existed)"
            )

        mariadb_conn.commit()
        print(f"  [OK] '{db_alias}' committed.")

    except Exception as exc:
        mariadb_conn.rollback()
        print(f"  [FAIL] '{db_alias}' rolled back: {exc}", file=sys.stderr)
        result.failed_dbs.append(db_alias)
        if args.fail_fast:
            raise


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate BackQuant SQLite data to MariaDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # SQLite source paths
    src = parser.add_argument_group("SQLite source")
    src.add_argument(
        "--sqlite-base-dir",
        default=os.environ.get("BACKTEST_BASE_DIR", "/data/backtest"),
        help="Directory containing SQLite files (default: $BACKTEST_BASE_DIR or /data/backtest)",
    )
    src.add_argument(
        "--auth-db",
        default=None,
        help="Explicit path to auth.sqlite3 (overrides --sqlite-base-dir)",
    )
    src.add_argument(
        "--market-db",
        default=None,
        help="Explicit path to market_data.sqlite3 (overrides --sqlite-base-dir)",
    )
    src.add_argument(
        "--backtest-meta-db",
        default=None,
        help="Explicit path to backtest_meta.sqlite3 (overrides --sqlite-base-dir)",
    )

    # MariaDB target
    dst = parser.add_argument_group("MariaDB target")
    dst.add_argument(
        "--host",
        default=os.environ.get("DB_HOST", "localhost"),
        help="MariaDB host (default: $DB_HOST or localhost)",
    )
    dst.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DB_PORT", "3306")),
        help="MariaDB port (default: $DB_PORT or 3306)",
    )
    dst.add_argument(
        "--database",
        default=os.environ.get("DB_NAME", "backquant"),
        help="MariaDB database name (default: $DB_NAME or backquant)",
    )
    dst.add_argument(
        "--user",
        default=os.environ.get("DB_USER", "root"),
        help="MariaDB user (default: $DB_USER or root)",
    )
    dst.add_argument(
        "--password",
        default=os.environ.get("DB_PASSWORD", ""),
        help="MariaDB password (default: $DB_PASSWORD)",
    )

    # Behaviour flags
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read SQLite and print counts only; do not write to MariaDB",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately if any DB migration fails (default: continue with remaining DBs)",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = _parse_args()

    base = Path(args.sqlite_base_dir)

    # Resolve SQLite paths
    auth_path = Path(args.auth_db) if args.auth_db else base / "auth.sqlite3"
    market_path = Path(args.market_db) if args.market_db else base / "market_data.sqlite3"
    meta_path = Path(args.backtest_meta_db) if args.backtest_meta_db else base / "backtest_meta.sqlite3"

    sqlite_paths = {
        "auth": auth_path,
        "market_data": market_path,
        "backtest_meta": meta_path,
    }

    print("BackQuant SQLite → MariaDB Migration")
    print(f"  SQLite base dir : {base}")
    print(f"  auth.sqlite3    : {auth_path}")
    print(f"  market_data     : {market_path}")
    print(f"  backtest_meta   : {meta_path}")
    if args.dry_run:
        print("  MODE            : DRY-RUN (no writes)")
    else:
        print(f"  MariaDB target  : {args.user}@{args.host}:{args.port}/{args.database}")

    # Open SQLite connections (None if file missing)
    sqlite_conns: dict[str, Optional[sqlite3.Connection]] = {}
    for alias, path in sqlite_paths.items():
        conn = _open_sqlite(path)
        if conn is None:
            print(f"  WARNING: {path} not found — '{alias}' will be skipped")
        sqlite_conns[alias] = conn

    # Open MariaDB (skip in dry-run)
    mariadb_conn = None
    if not args.dry_run:
        try:
            mariadb_conn = _open_mariadb(args)
            print(f"\nConnected to MariaDB at {args.host}:{args.port}/{args.database}")
        except Exception as exc:
            print(f"ERROR: Cannot connect to MariaDB: {exc}", file=sys.stderr)
            sys.exit(1)

    result = MigrationResult()

    try:
        for db_alias in _DB_ORDER:
            _migrate_db(
                db_alias=db_alias,
                sqlite_conn=sqlite_conns.get(db_alias),
                mariadb_conn=mariadb_conn,
                args=args,
                result=result,
            )
    finally:
        for conn in sqlite_conns.values():
            if conn:
                conn.close()
        if mariadb_conn:
            mariadb_conn.close()

    result.print_summary()

    if result.failed_dbs:
        print(f"\nMigration completed with errors in: {', '.join(result.failed_dbs)}")
        sys.exit(2)

    if args.dry_run:
        print("\nDry-run complete. Re-run without --dry-run to perform the actual migration.")
    else:
        print(
            "\n迁移完成！切换到 MariaDB：\n"
            "  编辑 .env 或 docker-compose.yml，设置 DB_TYPE=mariadb\n"
            "  重启容器: docker compose restart backend jupyter"
        )


if __name__ == "__main__":
    main()
