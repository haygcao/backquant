---
story_id: STORY-05
title: 全量下载+解压任务与自动触发分析
priority: P0
status: TODO
dependencies: [STORY-02, STORY-03]
estimated_effort: 8h
related_docs:
  - arch-market-data-mgmt.md (Section 5, 7, 10)
  - test-plan-market-data-mgmt.md (Section 3, 4, 7, 8)
---

# Story 05: 全量下载+解压任务与自动触发分析

## 用户故事

作为用户，我需要能够触发全量下载来获取完整的行情数据包，并在下载解压完成后自动分析数据，以便初始化或重建数据。

## 业务价值

- 支持全量下载，适用于首次安装或数据重建
- 显示下载和解压进度，提升用户体验
- 自动触发分析，减少手动操作
- 实现失败恢复和临时文件清理

## 技术实现

### 1. 全量下载任务函数

**文件位置**: `backtest/app/market_data/tasks.py`

```python
def do_full_download(task_id: str):
    """全量下载任务"""
    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    zip_path = Path("/tmp/rqalpha_bundle.zip")

    try:
        # 清理旧的临时文件
        if zip_path.exists():
            zip_path.unlink()

        # 阶段1: 下载
        tm.update_progress(task_id, 0, 'download', '开始下载...')
        zip_url = "https://bundle.rqalpha.io/bundle.zip"  # 实际 URL
        download_with_progress(task_id, zip_url, zip_path)

        # 阶段2: 解压
        tm.update_progress(task_id, 0, 'unzip', '开始解压...')
        unzip_with_progress(task_id, zip_path, bundle_path)
        zip_path.unlink()  # 删除临时文件

        # 阶段3: 自动触发分析
        tm.log(task_id, 'INFO', '下载解压完成，自动触发数据分析')
        analyze_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='auto')
        tm.log(task_id, 'INFO', f'已提交分析任务: {analyze_task_id}')

    except Exception as e:
        # 失败时清理临时文件
        if zip_path.exists():
            zip_path.unlink()
        tm.log(task_id, 'ERROR', f'全量下载失败: {str(e)}')
        raise
```

### 2. 带进度的下载函数

```python
def download_with_progress(task_id: str, url: str, dest: Path):
    """带进度的下载"""
    import requests
    from app.market_data.task_manager import get_task_manager

    tm = get_task_manager()
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(dest, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                progress = int(downloaded / total_size * 100) if total_size > 0 else 0
                tm.update_progress(
                    task_id, progress, 'download',
                    f"正在下载... ({progress}%)"
                )
                if downloaded % (1024 * 1024) == 0:  # 每 1MB 记录一次日志
                    tm.log(task_id, 'INFO', f"已下载 {downloaded}/{total_size} 字节")
```

### 3. 带进度的解压函数

```python
def unzip_with_progress(task_id: str, zip_path: Path, dest_dir: Path):
    """带进度的解压"""
    import zipfile
    from app.market_data.task_manager import get_task_manager

    tm = get_task_manager()
    with zipfile.ZipFile(zip_path, 'r') as zf:
        members = zf.namelist()
        total = len(members)

        for i, member in enumerate(members):
            zf.extract(member, dest_dir)
            progress = int((i + 1) / total * 100)
            tm.update_progress(
                task_id, progress, 'unzip',
                f"正在解压... ({progress}%)"
            )
            if i % 100 == 0:  # 每100个文件记录一次日志
                tm.log(task_id, 'INFO', f"已解压 {i+1}/{total} 个文件")
```

### 4. API 端点

**文件位置**: `backtest/app/api/market_data_api.py`

```python
@bp_market_data.route('/download/full', methods=['POST'])
@auth_required
def trigger_full():
    """触发全量下载"""
    bundle_path = _get_bundle_path()
    force = request.json.get('force', False) if request.json else False

    # 检查是否需要用户确认
    if not force and is_current_month_updated(bundle_path):
        return jsonify({
            'need_confirm': True,
            'message': '检测到当月已有更新，确定要重新下载吗？'
        }), 200

    try:
        tm = get_task_manager()
        from app.market_data.tasks import do_full_download
        task_id = tm.submit_task('full', do_full_download, source='manual')
        return jsonify({'task_id': task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## 验收标准

### AC-01: 全量下载任务正常执行
- [ ] 下载 bundle.zip 到临时路径
- [ ] 下载进度实时更新（0-100）
- [ ] 下载完成后进入解压阶段
- [ ] 临时文件路径正确（/tmp/rqalpha_bundle.zip）

### AC-02: 解压任务正常执行
- [ ] 解压到 bundle 目录
- [ ] 解压进度实时更新（0-100）
- [ ] 解压完成后删除临时文件
- [ ] 文件权限正确

### AC-03: 阶段切换正确
- [ ] 阶段顺序：download → unzip → analyze
- [ ] 每个阶段的 progress 从 0 开始
- [ ] stage 字段正确更新
- [ ] message 显示当前阶段信息

### AC-04: 自动触发分析
- [ ] 解压完成后自动提交分析任务
- [ ] 分析任务的 source='auto'
- [ ] 任务日志记录"已提交分析任务"
- [ ] 分析任务正常执行

### AC-05: 失败恢复和清理
- [ ] 下载失败时删除临时文件
- [ ] 解压失败时删除临时文件
- [ ] 任务状态设为 'failed'
- [ ] error 字段记录失败原因

### AC-06: "当月已最新"检测
- [ ] force=false 时检测"当月已最新"
- [ ] 需要确认时返回 need_confirm=true
- [ ] force=true 时直接执行

### AC-07: 进度追踪准确性
- [ ] 下载进度单调递增
- [ ] 解压进度单调递增
- [ ] 进度值范围 0-100
- [ ] 日志记录详细信息

## 测试用例

- **TC-CONFIRM-004**: 全量下载 - 当月已更新，显示确认弹框
- **TC-CONFIRM-005**: 全量下载 - 用户确认后强制执行
- **TC-PROGRESS-001**: 下载进度百分比单调递增
- **TC-PROGRESS-002**: 解压进度百分比单调递增
- **TC-PROGRESS-004**: 阶段切换顺序正确
- **TC-ANALYZE-003**: 全量下载后自动触发分析
- **TC-FAIL-001**: 网络中断时下载失败
- **TC-FAIL-002**: 解压失败
- **TC-FAIL-007**: 下载失败后临时文件清理

## 技术债务

- 考虑支持断点续传（下载中断后继续）
- 考虑支持多线程下载以提升速度
- 考虑验证下载文件的完整性（MD5/SHA256）

## 注意事项

1. 临时文件使用 /tmp 目录，确保有足够空间
2. 下载和解压都需要显示进度
3. 失败时必须清理临时文件
4. 完成后必须自动触发分析
5. 使用 requests 库的 stream=True 支持大文件下载
6. 解压时使用 zipfile 标准库

## 完成定义 (DoD)

- [ ] 全量下载任务函数已实现
- [ ] 下载和解压进度函数已实现
- [ ] API 端点已实现
- [ ] 失败恢复和清理已验证
- [ ] 自动触发分析已验证
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
