---
story_id: STORY-06
title: 定时任务配置可视化 API 与日志
priority: P1
status: TODO
dependencies: [STORY-03, STORY-04, STORY-05]
estimated_effort: 6h
related_docs:
  - arch-market-data-mgmt.md (Section 11)
  - test-plan-market-data-mgmt.md (Section 6)
---

# Story 06: 定时任务配置可视化 API 与日志

## 用户故事

作为用户，我需要能够通过可视化界面配置定时任务，并查看定时任务的运行日志，以便自动化数据更新流程。

## 业务价值

- 替代容器内的 crontab，提供可视化配置
- 支持启用/禁用定时任务
- 记录定时任务运行历史，便于问题排查
- 支持灵活的 cron 表达式配置

## 技术实现

### 1. 定时任务调度器

**文件位置**: `backtest/app/market_data/scheduler.py`

**新增依赖**: `requirements.txt` 添加 `APScheduler==3.10.4`

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import sqlite3
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

_scheduler = None

def get_scheduler():
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        logger.info('APScheduler 已启动')
    return _scheduler

def load_cron_config(db_path: Path) -> dict:
    """从数据库加载定时任务配置"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM market_data_cron_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def cron_job_handler():
    """定时任务处理器"""
    from app.market_data.task_manager import get_task_manager
    from app.market_data.tasks import do_full_download, do_incremental_update

    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    config = load_cron_config(db_path)

    if not config or not config['enabled']:
        logger.info('定时任务未启用，跳过执行')
        _log_cron_run(db_path, None, 'skipped', '定时任务未启用')
        return

    tm = get_task_manager()

    # 检查是否有正在运行的任务（互斥）
    if tm._has_running_task():
        logger.warning('已有任务正在运行，跳过本次定时任务')
        _log_cron_run(db_path, None, 'skipped', '已有任务正在运行')
        return

    # 根据配置提交任务
    task_type = config['task_type']
    try:
        if task_type == 'full':
            task_id = tm.submit_task('full', do_full_download, source='cron')
        elif task_type == 'incremental':
            task_id = tm.submit_task('incremental', do_incremental_update, source='cron')
        else:
            raise ValueError(f'未知任务类型: {task_type}')

        logger.info(f'定时任务已提交: {task_id}')
        _log_cron_run(db_path, task_id, 'success', f'已提交任务: {task_id}')

    except Exception as e:
        logger.error(f'定时任务执行失败: {str(e)}')
        _log_cron_run(db_path, None, 'failed', str(e))

def _log_cron_run(db_path: Path, task_id: str, status: str, message: str):
    """记录定时任务运行日志"""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO market_data_cron_logs
           (task_id, trigger_time, status, message)
           VALUES (?, ?, ?, ?)""",
        (task_id, datetime.utcnow().isoformat(), status, message)
    )
    conn.commit()
    conn.close()

def update_cron_schedule(cron_expression: str):
    """更新定时任务调度"""
    scheduler = get_scheduler()

    # 移除旧任务
    scheduler.remove_all_jobs()

    # 添加新任务
    if cron_expression:
        trigger = CronTrigger.from_crontab(cron_expression)
        scheduler.add_job(
            cron_job_handler,
            trigger=trigger,
            id='market_data_cron',
            replace_existing=True
        )
        logger.info(f'定时任务已更新: {cron_expression}')

def init_scheduler():
    """初始化调度器（应用启动时调用）"""
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    config = load_cron_config(db_path)

    if config and config['enabled'] and config['cron_expression']:
        update_cron_schedule(config['cron_expression'])
        logger.info(f'定时任务已加载: {config["cron_expression"]}')
```

### 2. 应用启动集成

**修改**: `backtest/app/__init__.py`

```python
def create_app(config_name):
    # ... 现有代码 ...
    from .market_data.scheduler import init_scheduler

    try:
        with app.app_context():
            ensure_default_demo_strategy()
            init_scheduler()  # 新增：初始化定时任务
    except Exception:
        app.logger.exception("failed to initialize app")

    return app
```

### 3. API 端点

**文件位置**: `backtest/app/api/market_data_api.py`

```python
@bp_market_data.route('/cron/config', methods=['GET'])
@auth_required
def get_cron_config():
    """获取定时配置"""
    db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM market_data_cron_config WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            # 返回默认配置
            return jsonify({
                'enabled': False,
                'cron_expression': '0 2 1 * *',  # 每月1日凌晨2点
                'task_type': 'incremental'
            }), 200

        return jsonify(dict(row)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_market_data.route('/cron/config', methods=['PUT'])
@auth_required
def update_cron_config():
    """更新定时配置"""
    data = request.json
    enabled = data.get('enabled', False)
    cron_expression = data.get('cron_expression', '0 2 1 * *')
    task_type = data.get('task_type', 'incremental')

    if task_type not in ('incremental', 'full'):
        return jsonify({'error': '无效的任务类型'}), 400

    db_path = _get_db_path()

    try:
        # 验证 cron 表达式
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(cron_expression)
        except Exception:
            return jsonify({'error': '无效的 cron 表达式'}), 400

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT OR REPLACE INTO market_data_cron_config
            (id, enabled, cron_expression, task_type, updated_at)
            VALUES (1, ?, ?, ?, ?)
        """, (1 if enabled else 0, cron_expression, task_type, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

        # 更新调度器
        from app.market_data.scheduler import update_cron_schedule
        if enabled:
            update_cron_schedule(cron_expression)
        else:
            update_cron_schedule(None)

        return jsonify({'message': '配置已更新'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_market_data.route('/cron/logs', methods=['GET'])
@auth_required
def get_cron_logs():
    """获取运行日志列表"""
    db_path = _get_db_path()
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT * FROM market_data_cron_logs
            ORDER BY trigger_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        logs = [dict(row) for row in cursor.fetchall()]

        # 获取总数
        cursor = conn.execute("SELECT COUNT(*) FROM market_data_cron_logs")
        total = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            'logs': logs,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_market_data.route('/cron/logs/<int:log_id>', methods=['GET'])
@auth_required
def get_cron_log_detail(log_id: int):
    """获取日志详情"""
    db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM market_data_cron_logs WHERE log_id = ?",
            (log_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'error': '日志不存在'}), 404

        log = dict(row)

        # 如果有关联任务，获取任务详情
        if log['task_id']:
            cursor = conn.execute(
                "SELECT * FROM market_data_tasks WHERE task_id = ?",
                (log['task_id'],)
            )
            task_row = cursor.fetchone()
            if task_row:
                log['task'] = dict(task_row)

        conn.close()

        return jsonify(log), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## 验收标准

### AC-01: APScheduler 正确初始化
- [ ] 应用启动时调度器已启动
- [ ] 调度器为后台线程（daemon=True）
- [ ] 日志记录"APScheduler 已启动"

### AC-02: 定时任务配置读取正常
- [ ] GET /api/cron/config 返回配置
- [ ] 无配置时返回默认值
- [ ] 有配置时返回数据库中的值

### AC-03: 定时任务配置更新正常
- [ ] PUT /api/cron/config 更新配置
- [ ] 数据库中配置已更新
- [ ] 调度器已更新
- [ ] enabled=true 时添加任务
- [ ] enabled=false 时移除任务

### AC-04: Cron 表达式验证
- [ ] 有效的 cron 表达式可以保存
- [ ] 无效的 cron 表达式返回 400 错误
- [ ] 错误消息："无效的 cron 表达式"

### AC-05: 定时任务正确触发
- [ ] 到达 cron 时间时触发 cron_job_handler
- [ ] 检查配置是否启用
- [ ] 检查是否有任务正在运行（互斥）
- [ ] 根据 task_type 提交对应任务

### AC-06: 定时任务日志正确记录
- [ ] 每次触发都记录日志
- [ ] status 正确（success/failed/skipped）
- [ ] task_id 正确关联（如果任务已提交）
- [ ] message 描述清晰

### AC-07: 日志查询 API 正常
- [ ] GET /api/cron/logs 返回日志列表
- [ ] 支持分页（limit/offset）
- [ ] 按时间倒序排列
- [ ] 返回总数

### AC-08: 日志详情 API 正常
- [ ] GET /api/cron/logs/{log_id} 返回详情
- [ ] 包含关联的任务信息
- [ ] 日志不存在时返回 404

### AC-09: 定时任务与手动任务互斥
- [ ] 有手动任务运行时，定时任务跳过
- [ ] 日志记录 status='skipped'
- [ ] message="已有任务正在运行"

## 测试用例

- **TC-CRON-001**: 读取默认定时配置
- **TC-CRON-002**: 更新定时配置
- **TC-CRON-003**: 启用定时任务
- **TC-CRON-004**: 禁用定时任务
- **TC-CRON-005**: 定时任务日志正确记录
- **TC-CRON-006**: 获取日志详情
- **TC-CRON-007**: 定时任务与手动任务互斥
- **TC-CRON-008**: 无效的 cron 表达式
- **TC-ANALYZE-005**: 定时任务完成后自动触发分析

## 技术债务

- 考虑支持多个定时任务配置
- 考虑支持定时任务的暂停/恢复
- 考虑支持定时任务的手动触发

## 注意事项

1. 使用 APScheduler 的 BackgroundScheduler
2. 调度器在应用启动时初始化
3. 定时任务与手动任务互斥
4. Cron 表达式需要验证
5. 定时任务完成后自动触发分析（在 STORY-04/05 中已实现）

## 完成定义 (DoD)

- [ ] APScheduler 已集成
- [ ] 调度器初始化已实现
- [ ] API 端点已实现
- [ ] Cron 表达式验证已实现
- [ ] 日志记录已实现
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
