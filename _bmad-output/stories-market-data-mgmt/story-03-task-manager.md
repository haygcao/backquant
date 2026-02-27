---
story_id: STORY-03
title: 统一任务框架（TaskManager）
priority: P0
status: TODO
dependencies: [STORY-01]
estimated_effort: 8h
related_docs:
  - arch-market-data-mgmt.md (Section 4)
  - test-plan-market-data-mgmt.md (Section 5)
---

# Story 03: 统一任务框架（TaskManager）

## 用户故事

作为系统，我需要一个轻量级的任务管理框架，支持任务提交、进度追踪、日志记录和任务互斥，以便统一管理所有异步任务。

## 业务价值

- 提供统一的任务管理接口
- 支持任务状态追踪和进度更新
- 实现任务互斥，防止资源竞争
- 提供完整的日志记录能力

## 技术实现

### 1. TaskManager 核心类

**文件位置**: `backtest/app/market_data/task_manager.py`

```python
import threading
import uuid
from datetime import datetime
from typing import Optional, Callable
from queue import Queue
from pathlib import Path
import sqlite3

class TaskManager:
    """轻量级任务管理器"""

    def __init__(self, db_path: str, max_workers: int = 1):
        self.db_path = db_path
        self.max_workers = max_workers
        self.task_queue = Queue()
        self.workers = []
        self.lock = threading.Lock()
        self._init_db()
        self._start_workers()

    def _init_db(self):
        """初始化数据库表"""
        # 调用 STORY-01 的初始化函数
        from app.market_data.db_init import init_database
        init_database(Path(self.db_path))

    def _start_workers(self):
        """启动工作线程"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"TaskWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        """工作线程主循环"""
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
        """提交任务"""
        with self.lock:
            # 检查是否有正在运行的任务（互斥）
            if self._has_running_task():
                raise RuntimeError("已有任务正在运行，请等待完成后再试")

            task_id = str(uuid.uuid4())
            self._create_task(task_id, task_type, source)
            self.task_queue.put((task_id, task_func, task_args))
            return task_id

    def _has_running_task(self) -> bool:
        """检查是否有正在运行的任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM market_data_tasks WHERE status IN ('pending', 'running')"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def _create_task(self, task_id: str, task_type: str, source: str):
        """创建任务记录"""
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
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)

        updates = [f"status = ?"]
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
        """更新任务进度"""
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
        """记录任务日志"""
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
        """获取任务状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM market_data_tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

# 全局单例
_task_manager: Optional[TaskManager] = None

def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _task_manager = TaskManager(str(db_path), max_workers=1)
    return _task_manager
```

### 2. API 端点

**文件位置**: `backtest/app/api/market_data_api.py`

```python
@bp_market_data.route('/tasks/<task_id>', methods=['GET'])
@auth_required
def get_task_status(task_id: str):
    """查询任务进度"""
    try:
        tm = get_task_manager()
        task = tm.get_task_status(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        return jsonify(task), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_market_data.route('/tasks/<task_id>/retry', methods=['POST'])
@auth_required
def retry_task(task_id: str):
    """重试失败的任务"""
    tm = get_task_manager()
    task = tm.get_task_status(task_id)

    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if task['status'] != 'failed':
        return jsonify({'error': '只能重试失败的任务'}), 400

    # 根据任务类型重新提交
    task_type = task['task_type']
    if task_type == 'analyze':
        from app.market_data.analyzer import analyze_bundle
        bundle_path = _get_bundle_path()
        db_path = _get_db_path()
        new_task_id = tm.submit_task('analyze', analyze_bundle,
                                     task_args=(bundle_path, db_path),
                                     source='retry')
    # 其他任务类型在后续 story 中实现
    else:
        return jsonify({'error': '未知任务类型'}), 400

    return jsonify({'task_id': new_task_id}), 202
```

## 验收标准

### AC-01: TaskManager 单例正常工作
- [ ] get_task_manager() 返回同一个实例
- [ ] 数据库路径正确
- [ ] 工作线程已启动（max_workers=1）

### AC-02: 任务提交功能正常
- [ ] submit_task() 返回 UUID 格式的 task_id
- [ ] 任务记录已创建，status='pending'
- [ ] 任务进入队列等待执行

### AC-03: 任务互斥正确实现
- [ ] 有任务运行时，submit_task() 抛出 RuntimeError
- [ ] 错误消息："已有任务正在运行，请等待完成后再试"
- [ ] 数据库查询正确（status IN ('pending', 'running')）

### AC-04: 任务执行流程正确
- [ ] 任务从 pending 变为 running
- [ ] started_at 时间已记录
- [ ] 任务函数正常执行
- [ ] 成功时 status='success'，finished_at 已记录
- [ ] 失败时 status='failed'，error 已记录

### AC-05: 进度更新功能正常
- [ ] update_progress() 正确更新 progress、stage、message
- [ ] 进度值范围 0-100
- [ ] stage 值正确（download/unzip/analyze）

### AC-06: 日志记录功能正常
- [ ] log() 正确写入日志表
- [ ] 包含 task_id、timestamp、level、message
- [ ] level 支持 DEBUG/INFO/WARNING/ERROR

### AC-07: 任务状态查询正常
- [ ] get_task_status() 返回完整任务信息
- [ ] 任务不存在时返回 None
- [ ] 字段类型正确

### AC-08: API 端点正常工作
- [ ] GET /api/market-data/tasks/{task_id} 返回任务状态
- [ ] 任务不存在时返回 404
- [ ] 需要认证（@auth_required）

### AC-09: 重试功能正常
- [ ] 只能重试 failed 状态的任务
- [ ] 重试时创建新任务，source='retry'
- [ ] 任务类型与原任务一致

## 测试用例

- **TC-MUTEX-001**: 并发点击下载按钮，只有一个任务执行
- **TC-MUTEX-002**: 下载中再次点击，提示互斥
- **TC-MUTEX-003**: 分析中触发下载，提示互斥
- **TC-MUTEX-004**: 任务完成后可再次提交
- **TC-PROGRESS-001**: 下载进度百分比单调递增
- **TC-PROGRESS-003**: 分析进度百分比单调递增
- **TC-FAIL-005**: 失败任务可重试
- **TC-FAIL-006**: 只能重试失败的任务
- **TC-API-005**: GET /api/market-data/tasks/{task_id} 正常响应
- **TC-API-006**: GET /api/market-data/tasks/{task_id} 任务不存在

## 技术债务

- 考虑支持任务取消功能
- 考虑支持任务优先级
- 考虑支持任务依赖关系

## 注意事项

1. 使用后台线程而非 Celery/RQ，保持轻量级
2. max_workers=1 确保串行执行
3. 使用数据库锁实现互斥
4. 工作线程设置为 daemon，应用退出时自动结束
5. 任务函数的第一个参数必须是 task_id

## 完成定义 (DoD)

- [ ] TaskManager 类已实现并通过单元测试
- [ ] 任务互斥功能验证通过
- [ ] API 端点已实现并通过集成测试
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
