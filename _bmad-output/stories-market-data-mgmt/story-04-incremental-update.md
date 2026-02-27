---
story_id: STORY-04
title: 增量更新任务与自动触发分析
priority: P0
status: TODO
dependencies: [STORY-02, STORY-03]
estimated_effort: 6h
related_docs:
  - arch-market-data-mgmt.md (Section 5, 7)
  - test-plan-market-data-mgmt.md (Section 3, 4, 7)
---

# Story 04: 增量更新任务与自动触发分析

## 用户故事

作为用户，我需要能够触发增量更新来追加最新的行情数据，并在更新完成后自动分析数据，以便保持数据的时效性。

## 业务价值

- 支持增量更新，节省下载时间和带宽
- 自动触发分析，减少手动操作
- 实现"当月已最新"检测，避免重复下载

## 技术实现

### 1. 增量更新任务函数

**文件位置**: `backtest/app/market_data/tasks.py`

```python
import subprocess
import os
from pathlib import Path
from app.market_data.task_manager import get_task_manager
from app.market_data.analyzer import analyze_bundle

def do_incremental_update(task_id: str):
    """增量更新任务"""
    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"

    try:
        tm.update_progress(task_id, 0, 'download', '开始增量更新...')

        # 执行 rqalpha update-bundle
        cmd = ['rqalpha', 'update-bundle']
        env = os.environ.copy()
        env['RQALPHA_BUNDLE_PATH'] = str(bundle_path)

        process = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # 读取输出并更新进度
        for line in process.stdout:
            tm.log(task_id, 'INFO', line.strip())
            # 根据输出解析进度
            if 'Downloading' in line:
                tm.update_progress(task_id, 50, 'download', '正在下载更新...')

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f'rqalpha update-bundle 失败，退出码: {process.returncode}')

        tm.update_progress(task_id, 100, 'download', '增量更新完成')

        # 自动触发分析
        tm.log(task_id, 'INFO', '增量更新完成，自动触发数据分析')
        analyze_task_id = tm.submit_task('analyze', analyze_bundle,
                                         task_args=(bundle_path, db_path),
                                         source='auto')
        tm.log(task_id, 'INFO', f'已提交分析任务: {analyze_task_id}')

    except Exception as e:
        tm.log(task_id, 'ERROR', f'增量更新失败: {str(e)}')
        raise
```

### 2. "当月已最新"检测工具

**文件位置**: `backtest/app/market_data/utils.py`

```python
from pathlib import Path
from datetime import datetime

def is_current_month_updated(bundle_path: Path) -> bool:
    """
    判断 bundle 是否在当月已更新

    Returns:
        True: 当月已更新（需要用户确认）
        False: 未更新或非当月（可直接下载）
    """
    if not bundle_path.exists():
        return False

    # 查找最近修改的文件
    latest_mtime = None
    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            mtime = file_path.stat().st_mtime
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime is None:
        return False

    # 比较修改时间与当前月份
    latest_date = datetime.fromtimestamp(latest_mtime)
    current_date = datetime.now()

    return (latest_date.year == current_date.year and
            latest_date.month == current_date.month)
```

### 3. API 端点

**文件位置**: `backtest/app/api/market_data_api.py`

```python
@bp_market_data.route('/download/incremental', methods=['POST'])
@auth_required
def trigger_incremental():
    """触发增量更新"""
    bundle_path = _get_bundle_path()
    force = request.json.get('force', False) if request.json else False

    # 检查是否需要用户确认
    if not force and is_current_month_updated(bundle_path):
        return jsonify({
            'need_confirm': True,
            'message': '检测到当月已有更新，确定要再次更新吗？'
        }), 200

    try:
        tm = get_task_manager()
        from app.market_data.tasks import do_incremental_update
        task_id = tm.submit_task('incremental', do_incremental_update, source='manual')
        return jsonify({'task_id': task_id}), 202

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## 验收标准

### AC-01: 增量更新任务正常执行
- [ ] 调用 rqalpha update-bundle 命令
- [ ] 环境变量 RQALPHA_BUNDLE_PATH 正确传递
- [ ] 命令输出实时记录到日志
- [ ] 进度正确更新（0 → 50 → 100）

### AC-02: 增量更新完成后自动触发分析
- [ ] 更新成功后自动提交分析任务
- [ ] 分析任务的 source='auto'
- [ ] 任务日志记录"已提交分析任务"
- [ ] 分析任务正常执行

### AC-03: "当月已最新"检测正确
- [ ] bundle 不存在时返回 False
- [ ] bundle 为空时返回 False
- [ ] 文件修改时间在当月时返回 True
- [ ] 文件修改时间不在当月时返回 False

### AC-04: API 端点正常工作
- [ ] force=false 时检测"当月已最新"
- [ ] 需要确认时返回 need_confirm=true，HTTP 200
- [ ] force=true 时直接执行，返回 task_id，HTTP 202
- [ ] 有任务运行时返回 409
- [ ] 需要认证（@auth_required）

### AC-05: 前端确认流程正确
- [ ] 用户点击"增量更新"，后端检测当月已更新
- [ ] 前端显示确认弹框
- [ ] 用户取消时不发送请求
- [ ] 用户确认时发送 force=true 请求

### AC-06: 进度追踪正确
- [ ] stage='download'
- [ ] progress 从 0 递增到 100
- [ ] message 显示当前状态
- [ ] 完成时 status='success'

## 测试用例

- **TC-CONFIRM-001**: 增量更新 - 当月已更新，显示确认弹框
- **TC-CONFIRM-002**: 增量更新 - 用户取消操作
- **TC-CONFIRM-003**: 增量更新 - 用户确认后强制执行
- **TC-CONFIRM-006**: 非当月数据，直接执行不弹框
- **TC-PROGRESS-001**: 下载进度百分比单调递增
- **TC-PROGRESS-005**: 增量更新无解压阶段
- **TC-ANALYZE-004**: 增量更新后自动触发分析

## 技术债务

- 考虑支持增量更新的断点续传
- 考虑解析 rqalpha 输出以提供更精确的进度

## 注意事项

1. 增量更新使用 rqalpha update-bundle 命令
2. 数据追加到现有 bundle，不覆盖
3. 完成后必须自动触发分析
4. "当月已最新"判断基于文件修改时间
5. 用户确认后使用 force=true 参数

## 完成定义 (DoD)

- [ ] 增量更新任务函数已实现
- [ ] "当月已最新"检测已实现
- [ ] API 端点已实现
- [ ] 自动触发分析已验证
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
