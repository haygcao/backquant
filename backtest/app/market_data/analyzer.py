"""Bundle data analyzer."""
from pathlib import Path
from datetime import datetime
import sqlite3
from typing import Dict


def analyze_bundle(task_id: str, bundle_path: Path, db_path: Path):
    """Analyze RQAlpha bundle data.

    Args:
        task_id: Task ID for progress updates
        bundle_path: Path to bundle directory
        db_path: Path to database
    """
    from app.market_data.task_manager import get_task_manager

    tm = get_task_manager()
    tm.update_progress(task_id, 0, 'analyze', '开始分析...')
    tm.log(task_id, 'INFO', f'Bundle 路径: {bundle_path}')

    try:
        # 1. Scan files
        tm.update_progress(task_id, 10, 'analyze', '正在扫描文件...')
        file_stats = _scan_files(bundle_path)
        tm.log(task_id, 'INFO', f'扫描到 {file_stats["total_files"]} 个文件')

        # 2. Parse bundle data
        tm.update_progress(task_id, 30, 'analyze', '正在解析行情数据...')
        data_counts = _parse_bundle_data(bundle_path, tm, task_id)

        # 3. Save to database
        tm.update_progress(task_id, 90, 'analyze', '正在写入数据库...')
        _save_stats(db_path, bundle_path, file_stats, data_counts)

        tm.update_progress(task_id, 100, 'analyze', '分析完成')
        tm.log(task_id, 'INFO', '数据分析完成')

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
            tm.log(task_id, 'WARNING', 'h5py not available, skipping data parsing')
            return counts

        # Stock data
        tm.update_progress(task_id, 40, 'analyze', '正在解析股票数据...')
        stock_file = bundle_path / 'stocks.h5'
        if stock_file.exists():
            try:
                with h5py.File(str(stock_file), 'r') as f:
                    # Count number of datasets/groups in the file
                    counts['stock_count'] = len(list(f.keys()))
                tm.log(task_id, 'INFO', f'股票数据: {counts["stock_count"]} 条')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'解析股票数据失败: {str(e)}')

        # Fund data
        tm.update_progress(task_id, 50, 'analyze', '正在解析基金数据...')
        fund_file = bundle_path / 'funds.h5'
        if fund_file.exists():
            try:
                with h5py.File(str(fund_file), 'r') as f:
                    counts['fund_count'] = len(list(f.keys()))
                tm.log(task_id, 'INFO', f'基金数据: {counts["fund_count"]} 条')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'解析基金数据失败: {str(e)}')

        # Futures data
        tm.update_progress(task_id, 60, 'analyze', '正在解析期货数据...')
        futures_file = bundle_path / 'futures.h5'
        if futures_file.exists():
            try:
                with h5py.File(str(futures_file), 'r') as f:
                    counts['futures_count'] = len(list(f.keys()))
                tm.log(task_id, 'INFO', f'期货数据: {counts["futures_count"]} 条')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'解析期货数据失败: {str(e)}')

        # Index data
        tm.update_progress(task_id, 70, 'analyze', '正在解析指数数据...')
        index_file = bundle_path / 'indexes.h5'
        if index_file.exists():
            try:
                with h5py.File(str(index_file), 'r') as f:
                    counts['index_count'] = len(list(f.keys()))
                tm.log(task_id, 'INFO', f'指数数据: {counts["index_count"]} 条')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'解析指数数据失败: {str(e)}')

        # Bond data (if exists)
        tm.update_progress(task_id, 80, 'analyze', '正在解析债券数据...')
        bond_file = bundle_path / 'bonds.h5'
        if bond_file.exists():
            try:
                with h5py.File(str(bond_file), 'r') as f:
                    counts['bond_count'] = len(list(f.keys()))
                tm.log(task_id, 'INFO', f'债券数据: {counts["bond_count"]} 条')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'解析债券数据失败: {str(e)}')

    except Exception as e:
        tm.log(task_id, 'WARNING', f'解析部分数据失败: {str(e)}')

    return counts


def _save_stats(db_path: Path, bundle_path: Path, file_stats: Dict, data_counts: Dict):
    """Save statistics to database (idempotent)."""
    conn = sqlite3.connect(str(db_path))

    # Use INSERT OR REPLACE for idempotency
    conn.execute("""
        INSERT OR REPLACE INTO market_data_stats
        (id, bundle_path, last_modified, total_files, total_size_bytes,
         analyzed_at, stock_count, fund_count, futures_count, index_count, bond_count)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(bundle_path),
        file_stats['last_modified'],
        file_stats['total_files'],
        file_stats['total_size_bytes'],
        datetime.utcnow().isoformat(),
        data_counts['stock_count'],
        data_counts['fund_count'],
        data_counts['futures_count'],
        data_counts['index_count'],
        data_counts['bond_count']
    ))

    # Clear old file records and insert new ones
    conn.execute("DELETE FROM market_data_files")
    for file_info in file_stats.get('files', []):
        conn.execute("""
            INSERT INTO market_data_files (file_name, file_path, file_size, modified_at)
            VALUES (?, ?, ?, ?)
        """, (
            file_info['name'],
            file_info['path'],
            file_info['size'],
            file_info['modified']
        ))

    conn.commit()
    conn.close()
