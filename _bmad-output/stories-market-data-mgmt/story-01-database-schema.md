---
story_id: STORY-01
title: 数据库表结构设计与初始化
priority: P0
status: TODO
dependencies: []
estimated_effort: 4h
related_docs:
  - arch-market-data-mgmt.md (Section 3)
  - test-plan-market-data-mgmt.md (Section 10)
---

# Story 01: 数据库表结构设计与初始化

## 用户故事

作为系统，我需要创建行情数据管理所需的数据库表结构，以便存储任务状态、进度、日志、统计数据和定时任务配置。

## 业务价值

- 为后续功能提供数据持久化基础
- 支持任务状态追踪和历史查询
- 支持数据统计和可视化展示

## 技术实现

### 1. 数据库文件位置

**路径**: `backtest/data/market_data.sqlite3`

**创建时机**: 应用启动时自动创建（如不存在）

### 2. 表结构定义

#### 2.1 任务表 (market_data_tasks)

```sql
CREATE TABLE IF NOT EXISTS market_data_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,  -- 'analyze', 'incremental', 'full'
    status TEXT NOT NULL,      -- 'pending', 'running', 'success', 'failed', 'cancelled'
    progress INTEGER DEFAULT 0, -- 0-100
    stage TEXT,                -- 'download', 'unzip', 'analyze'
    message TEXT,
    source TEXT,               -- 'manual', 'cron', 'auto', 'retry'
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_created ON market_data_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON market_data_tasks(status);
```

#### 2.2 任务日志表 (market_data_task_logs)

```sql
CREATE TABLE IF NOT EXISTS market_data_task_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,      -- 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    message TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES market_data_tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_logs_task ON market_data_task_logs(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON market_data_task_logs(timestamp DESC);
```

#### 2.3 数据统计表 (market_data_stats)

```sql
CREATE TABLE IF NOT EXISTS market_data_stats (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- 单行表
    bundle_path TEXT NOT NULL,
    last_modified TEXT,        -- bundle 最近修改时间
    total_files INTEGER,
    total_size_bytes INTEGER,
    analyzed_at TEXT NOT NULL,

    -- 各品种行情条数
    stock_count INTEGER DEFAULT 0,
    fund_count INTEGER DEFAULT 0,
    futures_count INTEGER DEFAULT 0,
    index_count INTEGER DEFAULT 0,
    bond_count INTEGER DEFAULT 0
);
```

#### 2.4 定时任务配置表 (market_data_cron_config)

```sql
CREATE TABLE IF NOT EXISTS market_data_cron_config (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- 单行表
    enabled INTEGER DEFAULT 0,  -- 0=禁用, 1=启用
    cron_expression TEXT,       -- 如 "0 2 1 * *" (每月1日凌晨2点)
    task_type TEXT,             -- 'incremental' 或 'full'
    updated_at TEXT NOT NULL
);
```

#### 2.5 定时任务运行日志表 (market_data_cron_logs)

```sql
CREATE TABLE IF NOT EXISTS market_data_cron_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,              -- 关联的任务ID
    trigger_time TEXT NOT NULL,
    status TEXT NOT NULL,      -- 'success', 'failed', 'skipped'
    message TEXT,
    FOREIGN KEY (task_id) REFERENCES market_data_tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_cron_logs_time ON market_data_cron_logs(trigger_time DESC);
```

### 3. 初始化模块

**文件位置**: `backtest/app/market_data/db_init.py`

```python
import sqlite3
from pathlib import Path

def init_database(db_path: Path):
    """初始化数据库表结构"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 执行所有 CREATE TABLE 语句
    # ... (见上述 SQL)

    conn.commit()
    conn.close()
```

### 4. 应用启动集成

在 TaskManager 初始化时调用 `init_database()`。

## 验收标准

### AC-01: 数据库文件自动创建
- [ ] 应用首次启动时，自动创建 `backtest/data/market_data.sqlite3`
- [ ] 目录不存在时自动创建父目录
- [ ] 文件权限正确（可读写）

### AC-02: 所有表正确创建
- [ ] 5 张表全部创建成功
- [ ] 表结构与设计文档一致
- [ ] 字段类型和约束正确

### AC-03: 索引正确创建
- [ ] idx_tasks_created 存在
- [ ] idx_tasks_status 存在
- [ ] idx_logs_task 存在
- [ ] idx_logs_timestamp 存在
- [ ] idx_cron_logs_time 存在

### AC-04: 单行表约束生效
- [ ] market_data_stats 表只能插入 id=1 的记录
- [ ] market_data_cron_config 表只能插入 id=1 的记录
- [ ] 尝试插入 id=2 时返回约束错误

### AC-05: 外键约束生效
- [ ] task_logs 表的 task_id 必须存在于 tasks 表
- [ ] cron_logs 表的 task_id 必须存在于 tasks 表（如果不为 NULL）

## 测试用例

- **TC-DB-001**: 任务表正确记录任务状态
- **TC-DB-002**: 任务日志表正确记录操作日志
- **TC-DB-003**: 统计表单行约束生效
- **TC-DB-004**: 统计表幂等更新
- **TC-DB-005**: 定时任务配置表单行约束
- **TC-DB-006**: 索引正确创建

## 技术债务

无

## 注意事项

1. 使用 SQLite3，无需额外依赖
2. 数据库文件路径可通过环境变量配置
3. 初始化函数需要幂等（可重复执行）
4. 考虑数据库迁移策略（未来版本升级）

## 完成定义 (DoD)

- [ ] 所有表和索引创建成功
- [ ] 初始化代码已实现
- [ ] 单元测试通过
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
