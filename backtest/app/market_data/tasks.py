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
    """Execute full download task."""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.analyzer import analyze_bundle
    import requests
    import zipfile

    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    zip_path = Path("/tmp/rqalpha_bundle.zip")

    try:
        # Clean up old temp file
        if zip_path.exists():
            zip_path.unlink()

        # Stage 1: Download
        tm.update_progress(task_id, 0, 'download', '开始下载...')
        zip_url = "https://bundle.rqalpha.io/bundle.zip"

        tm.log(task_id, 'INFO', f'正在从 {zip_url} 下载数据包...')

        # Add timeout and better error handling
        response = requests.get(zip_url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress = int(downloaded / total_size * 100) if total_size > 0 else 0
                    tm.update_progress(task_id, progress, 'download', f"正在下载... ({progress}%)")
                    if downloaded % (1024 * 1024) == 0:
                        tm.log(task_id, 'INFO', f"已下载 {downloaded}/{total_size} 字节")

        # Stage 2: Unzip
        tm.update_progress(task_id, 0, 'unzip', '开始解压...')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            members = zf.namelist()
            total = len(members)

            for i, member in enumerate(members):
                zf.extract(member, bundle_path)
                progress = int((i + 1) / total * 100)
                tm.update_progress(task_id, progress, 'unzip', f"正在解压... ({progress}%)")
                if i % 100 == 0:
                    tm.log(task_id, 'INFO', f"已解压 {i+1}/{total} 个文件")

        zip_path.unlink()

        # Stage 3: Auto-trigger analysis
        tm.log(task_id, 'INFO', '下载解压完成，自动触发数据分析')
        analyze_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='auto')
        tm.log(task_id, 'INFO', f'已提交分析任务: {analyze_task_id}')

    except Exception as e:
        # Clean up temp file on failure
        if zip_path.exists():
            zip_path.unlink()
        tm.log(task_id, 'ERROR', f'全量下载失败: {str(e)}')
        raise
