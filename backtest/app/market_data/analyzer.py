"""Bundle data analyzer."""
from pathlib import Path
from datetime import datetime
from typing import Dict

from app.database import get_db_connection


def analyze_bundle(task_id: str, bundle_path: Path, db_config_dict: dict):
    """Analyze RQAlpha bundle data.

    Args:
        task_id: Task ID for progress updates
        bundle_path: Path to bundle directory
        db_config_dict: Serialized DatabaseConfig dict (from DatabaseConfig.to_dict()).
                        Used instead of a Path so that background threads can connect
                        to the database without a Flask application context.
    """
    from app.market_data.task_manager import get_task_manager

    tm = get_task_manager()
    tm.log(task_id, 'INFO', '开始数据分析任务')
    tm.update_progress(task_id, 0, 'analyze', '开始分析...')

    try:
        # 1. Scan files
        tm.update_progress(task_id, 10, 'analyze', '正在扫描文件...')
        file_stats = _scan_files(bundle_path)

        # 2. Parse bundle data
        tm.update_progress(task_id, 30, 'analyze', '正在解析行情数据...')
        data_counts = _parse_bundle_data(bundle_path, tm, task_id)

        # 3. Save to database
        tm.update_progress(task_id, 90, 'analyze', '正在写入数据库...')
        _save_stats(db_config_dict, bundle_path, file_stats, data_counts)

        tm.update_progress(task_id, 100, 'analyze', '分析完成')
        tm.log(task_id, 'INFO', '数据分析任务完成')

    except Exception as e:
        tm.log(task_id, 'ERROR', f'分析失败: {str(e)}')
        raise


def _scan_files(bundle_path: Path) -> Dict:
    """Scan files and collect statistics."""
    total_files = 0
    total_size = 0
    last_modified = None
    files_list = []

    if not bundle_path.exists():
        return {
            'total_files': 0,
            'total_size_bytes': 0,
            'last_modified': None,
            'files': []
        }

    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            total_files += 1
            file_size = file_path.stat().st_size
            total_size += file_size
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Collect file info
            relative_path = file_path.relative_to(bundle_path)
            files_list.append({
                'name': file_path.name,
                'path': str(relative_path),
                'size': file_size,
                'modified': mtime.isoformat()
            })

            if last_modified is None or mtime > last_modified:
                last_modified = mtime

    return {
        'total_files': total_files,
        'total_size_bytes': total_size,
        'last_modified': last_modified.isoformat() if last_modified else None,
        'files': files_list
    }


def _parse_bundle_data(bundle_path: Path, tm, task_id: str) -> Dict:
    """Parse bundle data and count records by type."""
    counts = {
        'stock_count': 0,
        'fund_count': 0,
        'futures_count': 0,
        'index_count': 0,
        'bond_count': 0
    }

    if not bundle_path.exists():
        return counts

    try:
        # Try to use h5py to parse HDF5 data files
        try:
            import h5py
        except ImportError:
            return counts

        # Stock data
        tm.update_progress(task_id, 40, 'analyze', '正在解析股票数据...')
        stock_file = bundle_path / 'stocks.h5'
        if stock_file.exists():
            try:
                with h5py.File(str(stock_file), 'r') as f:
                    counts['stock_count'] = len(list(f.keys()))
            except Exception:
                pass

        # Fund data
        tm.update_progress(task_id, 50, 'analyze', '正在解析基金数据...')
        fund_file = bundle_path / 'funds.h5'
        if fund_file.exists():
            try:
                with h5py.File(str(fund_file), 'r') as f:
                    counts['fund_count'] = len(list(f.keys()))
            except Exception:
                pass

        # Futures data
        tm.update_progress(task_id, 60, 'analyze', '正在解析期货数据...')
        futures_file = bundle_path / 'futures.h5'
        if futures_file.exists():
            try:
                with h5py.File(str(futures_file), 'r') as f:
                    counts['futures_count'] = len(list(f.keys()))
            except Exception:
                pass

        # Index data
        tm.update_progress(task_id, 70, 'analyze', '正在解析指数数据...')
        index_file = bundle_path / 'indexes.h5'
        if index_file.exists():
            try:
                with h5py.File(str(index_file), 'r') as f:
                    counts['index_count'] = len(list(f.keys()))
            except Exception:
                pass

        # Bond data (if exists)
        tm.update_progress(task_id, 80, 'analyze', '正在解析债券数据...')
        bond_file = bundle_path / 'bonds.h5'
        if bond_file.exists():
            try:
                with h5py.File(str(bond_file), 'r') as f:
                    counts['bond_count'] = len(list(f.keys()))
            except Exception:
                pass

    except Exception:
        pass

    return counts


def _save_stats(db_config_dict: dict, bundle_path: Path, file_stats: Dict, data_counts: Dict):
    """Save statistics to database (idempotent).

    Args:
        db_config_dict: Serialized DatabaseConfig dict for background-thread connection.
        bundle_path: Path to the bundle directory.
        file_stats: File scan results from _scan_files().
        data_counts: Instrument counts from _parse_bundle_data().
    """
    stats_cols = [
        'id', 'bundle_path', 'last_modified', 'total_files', 'total_size_bytes',
        'analyzed_at', 'stock_count', 'fund_count', 'futures_count',
        'index_count', 'bond_count',
    ]
    stats_vals = (
        1,
        str(bundle_path),
        file_stats['last_modified'],
        file_stats['total_files'],
        file_stats['total_size_bytes'],
        datetime.utcnow().isoformat(),
        data_counts['stock_count'],
        data_counts['fund_count'],
        data_counts['futures_count'],
        data_counts['index_count'],
        data_counts['bond_count'],
    )

    file_rows = [
        (f['name'], f['path'], f['size'], f['modified'])
        for f in file_stats.get('files', [])
    ]

    with get_db_connection(config_dict=db_config_dict) as db:
        # Idempotent upsert for the single-row stats table
        db.replace_into('market_data_stats', stats_cols, stats_vals)

        # Refresh file records
        db.execute("DELETE FROM market_data_files")
        if file_rows:
            db.executemany(
                "INSERT INTO market_data_files (file_name, file_path, file_size, modified_at) "
                "VALUES (?, ?, ?, ?)",
                file_rows,
            )
