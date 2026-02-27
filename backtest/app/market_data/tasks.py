"""Task functions for market data operations."""
import subprocess
import os
from pathlib import Path


def do_incremental_update(task_id: str):
    """Execute incremental update task."""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.analyzer import analyze_bundle

    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"

    try:
        tm.update_progress(task_id, 0, 'download', '开始增量更新...')

        # Execute rqalpha update-bundle
        cmd = ['rqalpha', 'update-bundle']
        env = os.environ.copy()
        env['RQALPHA_BUNDLE_PATH'] = str(bundle_path)

        process = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Read output and update progress
        for line in process.stdout:
            tm.log(task_id, 'INFO', line.strip())
            if 'Downloading' in line:
                tm.update_progress(task_id, 50, 'download', '正在下载更新...')

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f'rqalpha update-bundle 失败，退出码: {process.returncode}')

        tm.update_progress(task_id, 100, 'download', '增量更新完成')

        # Auto-trigger analysis
        tm.log(task_id, 'INFO', '增量更新完成，自动触发数据分析')
        analyze_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='auto')
        tm.log(task_id, 'INFO', f'已提交分析任务: {analyze_task_id}')

    except Exception as e:
        tm.log(task_id, 'ERROR', f'增量更新失败: {str(e)}')
        raise


def do_full_download(task_id: str):
    """Execute full download task using rqalpha download-bundle command."""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.analyzer import analyze_bundle
    import tempfile
    import shutil
    import re

    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    temp_dir = None

    try:
        # Use temporary directory for download (similar to docker-entrypoint.sh)
        tm.update_progress(task_id, 0, 'download', '准备下载环境...')
        temp_dir = tempfile.mkdtemp(prefix='rqalpha-bundle-')
        tm.log(task_id, 'INFO', f'使用临时目录: {temp_dir}')

        # Download to temporary directory
        tm.update_progress(task_id, 5, 'download', '开始下载数据包...')
        tm.log(task_id, 'INFO', '使用 rqalpha download-bundle 命令下载')

        cmd = ['rqalpha', 'download-bundle', '-d', temp_dir]
        env = os.environ.copy()

        process = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Parse output for progress information
        total_size = None
        downloaded_size = 0
        is_downloading = False
        is_extracting = False

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            tm.log(task_id, 'INFO', line)

            # Detect download phase
            if 'Downloading' in line or 'downloading' in line:
                is_downloading = True
                is_extracting = False
                tm.update_progress(task_id, 10, 'download', '正在下载数据包...')

            # Detect extraction phase
            elif 'Extracting' in line or 'extracting' in line or 'Unpack' in line:
                is_downloading = False
                is_extracting = True
                tm.update_progress(task_id, 60, 'extract', '正在解压数据包...')

            # Parse download progress (format: "Downloaded 123.45 MB / 500.00 MB")
            if is_downloading:
                match = re.search(r'(\d+\.?\d*)\s*(MB|GB|KB).*?/\s*(\d+\.?\d*)\s*(MB|GB|KB)', line)
                if match:
                    downloaded = float(match.group(1))
                    downloaded_unit = match.group(2)
                    total = float(match.group(3))
                    total_unit = match.group(4)

                    # Convert to MB for consistency
                    if downloaded_unit == 'GB':
                        downloaded *= 1024
                    elif downloaded_unit == 'KB':
                        downloaded /= 1024

                    if total_unit == 'GB':
                        total *= 1024
                    elif total_unit == 'KB':
                        total /= 1024

                    total_size = total
                    downloaded_size = downloaded

                    # Calculate progress (10-60% for download phase)
                    if total_size > 0:
                        progress = int(10 + (downloaded_size / total_size) * 50)
                        tm.update_progress(
                            task_id, progress, 'download',
                            f'正在下载: {downloaded_size:.1f}MB / {total_size:.1f}MB ({progress-10}%)'
                        )

            # Parse extraction progress
            elif is_extracting:
                # Look for file count or percentage
                match = re.search(r'(\d+)%', line)
                if match:
                    extract_pct = int(match.group(1))
                    # Map extraction progress to 60-80%
                    progress = int(60 + (extract_pct / 100) * 20)
                    tm.update_progress(task_id, progress, 'extract', f'正在解压: {extract_pct}%')

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f'rqalpha download-bundle 失败，退出码: {process.returncode}')

        # Copy from temp directory to target bundle path
        tm.update_progress(task_id, 80, 'copy', '正在复制数据到目标目录...')
        temp_bundle = Path(temp_dir) / 'bundle'

        if not temp_bundle.exists():
            raise RuntimeError(f'下载的 bundle 目录不存在: {temp_bundle}')

        # Calculate total size to copy
        total_copy_size = sum(f.stat().st_size for f in temp_bundle.rglob('*') if f.is_file())
        copied_size = 0

        # Clear target directory contents
        tm.log(task_id, 'INFO', f'清理目标目录: {bundle_path}')
        if bundle_path.exists():
            for item in bundle_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            bundle_path.mkdir(parents=True, exist_ok=True)

        # Copy files from temp to target with progress
        tm.log(task_id, 'INFO', f'复制文件到: {bundle_path}')
        for item in temp_bundle.iterdir():
            dest = bundle_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
                # Update progress
                for f in item.rglob('*'):
                    if f.is_file():
                        copied_size += f.stat().st_size
                        if total_copy_size > 0:
                            progress = int(80 + (copied_size / total_copy_size) * 15)
                            tm.update_progress(task_id, progress, 'copy', f'正在复制: {progress-80}%')
            else:
                shutil.copy2(item, dest)
                copied_size += item.stat().st_size
                if total_copy_size > 0:
                    progress = int(80 + (copied_size / total_copy_size) * 15)
                    tm.update_progress(task_id, progress, 'copy', f'正在复制: {progress-80}%')

        tm.update_progress(task_id, 95, 'complete', '下载完成，准备分析数据...')
        tm.log(task_id, 'INFO', '数据包下载完成')

        # Auto-trigger analysis
        tm.log(task_id, 'INFO', '自动触发数据分析')
        analyze_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='auto')
        tm.log(task_id, 'INFO', f'已提交分析任务: {analyze_task_id}')

    except Exception as e:
        tm.log(task_id, 'ERROR', f'全量下载失败: {str(e)}')
        raise
    finally:
        # Clean up temporary directory
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
                tm.log(task_id, 'INFO', f'已清理临时目录: {temp_dir}')
            except Exception as e:
                tm.log(task_id, 'WARNING', f'清理临时目录失败: {str(e)}')
