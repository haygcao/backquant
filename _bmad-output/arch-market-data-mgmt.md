---
title: 行情数据管理功能 - 架构设计
author: wallace
date: 2026-02-26
version: 1.0
related_docs:
  - prd-market-data-mgmt.md
  - brief-market-data-mgmt.md
---

# 行情数据管理功能 - 架构设计

## 1. 概述

本文档定义行情数据管理功能的技术架构，包括 Flask 路由设计、任务系统、数据库表结构、进度追踪、日志记录、数据分析程序、自动触发机制、路径权限管理和失败恢复策略。

### 1.1 设计原则

- **最小侵入**：不修改现有登录/回测/研究逻辑
- **轻量级任务系统**：使用后台线程 + SQLite 任务表，无需引入 Celery/RQ
- **统一接口**：所有异步任务（下载/解压/分析）使用统一的进度查询 API
- **幂等性**：数据分析可重复执行，不产生脏数据
- **失败恢复**：任务失败可重试，支持断点续传（全量下载）

### 1.2 技术栈

- **后端框架**：Flask 3.1.2
- **数据库**：SQLite3（复用现有方案）
- **任务执行**：Python threading + subprocess
- **数据解析**：rqalpha 6.1.2
- **定时任务**：APScheduler（新增依赖）

## 2. Flask 蓝图与路由设计

### 2.1 新增蓝图

**文件位置**：`backtest/app/api/market_data_api.py`

```python
from flask import Blueprint

bp_market_data = Blueprint('market_data', __name__, url_prefix='/api/market-data')
```

**注册位置**：`backtest/app/__init__.py`

```python
def create_app(config_name):
    from .api.login_api import bp_login
    from .api.backtest_api import bp_backtest
    from .api.research_api import bp_research
    from .api.system_api import bp_system
    from .api.market_data_api import bp_market_data  # 新增
    # ...

    app.register_blueprint(bp_login)
    app.register_blueprint(bp_backtest)
    app.register_blueprint(bp_research)
    app.register_blueprint(bp_system)
    app.register_blueprint(bp_market_data)  # 新增

    return app
```

### 2.2 路由定义

| 路由 | 方法 | 功能 | 返回 |
|------|------|------|------|
| `/api/market-data/overview` | GET | 获取数据全景 | 统计信息 |
| `/api/market-data/analyze` | POST | 触发数据分析 | task_id |
| `/api/market-data/download/incremental` | POST | 触发增量更新 | task_id |
| `/api/market-data/download/full` | POST | 触发全量下载 | task_id |
| `/api/market-data/tasks/{task_id}` | GET | 查询任务进度 | 进度信息 |
| `/api/market-data/cron/config` | GET | 获取定时配置 | cron 配置 |
| `/api/market-data/cron/config` | PUT | 更新定时配置 | 成功/失败 |
| `/api/market-data/cron/logs` | GET | 获取运行日志 | 日志列表 |
| `/api/market-data/cron/logs/{log_id}` | GET | 获取日志详情 | 日志详情 |

## 3. 数据库设计

### 3.1 数据库文件位置

**路径**：`backtest/data/market_data.sqlite3`

**创建时机**：应用启动时自动创建（如不存在）

### 3.2 表结构设计

#### 3.2.1 任务表 (market_data_tasks)

```sql
CREATE TABLE IF NOT EXISTS market_data_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,  -- 'analyze', 'incremental', 'full'
    status TEXT NOT NULL,      -- 'pending', 'running', 'success', 'failed', 'cancelled'
    progress INTEGER DEFAULT 0, -- 0-100
    stage TEXT,                -- 'download', 'unzip', 'analyze'
    message TEXT,
    source TEXT,               -- 'manual', 'cron'
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_created ON market_data_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON market_data_tasks(status);
```

#### 3.2.2 任务日志表 (market_data_task_logs)

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

#### 3.2.3 数据统计表 (market_data_stats)

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

#### 3.2.4 定时任务配置表 (market_data_cron_config)

```sql
CREATE TABLE IF NOT EXISTS market_data_cron_config (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- 单行表
    enabled INTEGER DEFAULT 0,  -- 0=禁用, 1=启用
    cron_expression TEXT,       -- 如 "0 2 1 * *" (每月1日凌晨2点)
    task_type TEXT,             -- 'incremental' 或 'full'
    updated_at TEXT NOT NULL
);
```

#### 3.2.5 定时任务运行日志表 (market_data_cron_logs)

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


## 4. 任务系统实现

### 4.1 轻量级任务系统设计

**不使用 Celery/RQ**，采用后台线程 + SQLite 任务表方案。

**核心组件**：

1. **任务管理器**：`backtest/app/market_data/task_manager.py`
2. **任务执行器**：后台线程池
3. **任务状态存储**：SQLite 数据库

### 4.2 任务管理器实现

```python
# backtest/app/market_data/task_manager.py
import threading
import uuid
from datetime import datetime
from typing import Optional, Callable
from queue import Queue
from pathlib import Path

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
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        # 执行所有 CREATE TABLE 语句（见 3.2 节）
        conn.close()
    
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
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM market_data_tasks WHERE status IN ('pending', 'running')"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def _create_task(self, task_id: str, task_type: str, source: str):
        """创建任务记录"""
        import sqlite3
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
        import sqlite3
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
        import sqlite3
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
        import sqlite3
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
        import sqlite3
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

### 4.3 任务并发与互斥

**互斥策略**：同一时间只允许一个任务运行（下载/解压/分析）

**实现方式**：
1. `submit_task` 时检查数据库中是否有 `status IN ('pending', 'running')` 的任务
2. 如果有，抛出异常 `RuntimeError("已有任务正在运行")`
3. 前端显示友好提示："当前有任务正在执行，请稍后再试"

**工作线程数**：`max_workers=1`，确保串行执行

## 5. 进度追踪实现

### 5.1 统一进度接口

**API**：`GET /api/market-data/tasks/{task_id}`

**响应结构**：

```json
{
  "task_id": "uuid",
  "task_type": "full|incremental|analyze",
  "status": "pending|running|success|failed|cancelled",
  "progress": 75,
  "stage": "download|unzip|analyze",
  "message": "正在下载... (75%)",
  "source": "manual|cron",
  "created_at": "2026-02-26T10:00:00Z",
  "started_at": "2026-02-26T10:00:05Z",
  "finished_at": null,
  "error": null
}
```

### 5.2 进度更新机制

**下载进度**（增量和全量）：

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
                tm.log(task_id, 'INFO', f"已下载 {downloaded}/{total_size} 字节")
```

**解压进度**（仅全量）：

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

**分析进度**：

```python
def analyze_with_progress(task_id: str):
    """带进度的分析"""
    from app.market_data.task_manager import get_task_manager
    
    tm = get_task_manager()
    stages = [
        (10, "正在扫描文件..."),
        (30, "正在解析股票数据..."),
        (50, "正在解析基金数据..."),
        (70, "正在解析期货数据..."),
        (90, "正在写入数据库..."),
        (100, "分析完成")
    ]
    
    for progress, message in stages:
        tm.update_progress(task_id, progress, 'analyze', message)
        # 执行实际分析逻辑...
```

## 6. 数据分析程序

### 6.1 入口函数

**文件位置**：`backtest/app/market_data/analyzer.py`

```python
# backtest/app/market_data/analyzer.py
from pathlib import Path
from datetime import datetime
import sqlite3
from typing import Dict

def analyze_bundle(task_id: str, bundle_path: Path, db_path: Path):
    """
    分析 RQAlpha bundle 数据
    
    Args:
        task_id: 任务ID（用于进度更新）
        bundle_path: bundle 目录路径
        db_path: 数据库路径
    """
    from app.market_data.task_manager import get_task_manager
    
    tm = get_task_manager()
    tm.update_progress(task_id, 0, 'analyze', '开始分析...')
    tm.log(task_id, 'INFO', f'Bundle 路径: {bundle_path}')
    
    try:
        # 1. 扫描文件
        tm.update_progress(task_id, 10, 'analyze', '正在扫描文件...')
        file_stats = _scan_files(bundle_path)
        tm.log(task_id, 'INFO', f'扫描到 {file_stats["total_files"]} 个文件')
        
        # 2. 解析各品种数据
        tm.update_progress(task_id, 30, 'analyze', '正在解析行情数据...')
        data_counts = _parse_bundle_data(bundle_path, tm, task_id)
        
        # 3. 写入数据库
        tm.update_progress(task_id, 90, 'analyze', '正在写入数据库...')
        _save_stats(db_path, bundle_path, file_stats, data_counts)
        
        tm.update_progress(task_id, 100, 'analyze', '分析完成')
        tm.log(task_id, 'INFO', '数据分析完成')
        
    except Exception as e:
        tm.log(task_id, 'ERROR', f'分析失败: {str(e)}')
        raise

def _scan_files(bundle_path: Path) -> Dict:
    """扫描文件统计"""
    total_files = 0
    total_size = 0
    last_modified = None
    
    for file_path in bundle_path.rglob('*'):
        if file_path.is_file():
            total_files += 1
            total_size += file_path.stat().st_size
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if last_modified is None or mtime > last_modified:
                last_modified = mtime
    
    return {
        'total_files': total_files,
        'total_size_bytes': total_size,
        'last_modified': last_modified.isoformat() if last_modified else None
    }

def _parse_bundle_data(bundle_path: Path, tm, task_id: str) -> Dict:
    """解析 bundle 数据，统计各品种条数"""
    import rqalpha
    from rqalpha.data.base_data_source import BaseDataSource
    
    # 使用 rqalpha 库解析 bundle
    # 注意：这里需要根据 rqalpha 实际 API 调整
    
    counts = {
        'stock_count': 0,
        'fund_count': 0,
        'futures_count': 0,
        'index_count': 0,
        'bond_count': 0
    }
    
    try:
        # 股票数据
        tm.update_progress(task_id, 40, 'analyze', '正在解析股票数据...')
        stock_file = bundle_path / 'stocks.bcolz'
        if stock_file.exists():
            import bcolz
            stocks = bcolz.open(str(stock_file))
            counts['stock_count'] = len(stocks)
            tm.log(task_id, 'INFO', f'股票数据: {counts["stock_count"]} 条')
        
        # 基金数据
        tm.update_progress(task_id, 50, 'analyze', '正在解析基金数据...')
        fund_file = bundle_path / 'funds.bcolz'
        if fund_file.exists():
            import bcolz
            funds = bcolz.open(str(fund_file))
            counts['fund_count'] = len(funds)
            tm.log(task_id, 'INFO', f'基金数据: {counts["fund_count"]} 条')
        
        # 期货数据
        tm.update_progress(task_id, 60, 'analyze', '正在解析期货数据...')
        futures_file = bundle_path / 'futures.bcolz'
        if futures_file.exists():
            import bcolz
            futures = bcolz.open(str(futures_file))
            counts['futures_count'] = len(futures)
            tm.log(task_id, 'INFO', f'期货数据: {counts["futures_count"]} 条')
        
        # 指数数据
        tm.update_progress(task_id, 70, 'analyze', '正在解析指数数据...')
        index_file = bundle_path / 'indexes.bcolz'
        if index_file.exists():
            import bcolz
            indexes = bcolz.open(str(index_file))
            counts['index_count'] = len(indexes)
            tm.log(task_id, 'INFO', f'指数数据: {counts["index_count"]} 条')
        
        # 债券数据
        tm.update_progress(task_id, 80, 'analyze', '正在解析债券数据...')
        bond_file = bundle_path / 'bonds.bcolz'
        if bond_file.exists():
            import bcolz
            bonds = bcolz.open(str(bond_file))
            counts['bond_count'] = len(bonds)
            tm.log(task_id, 'INFO', f'债券数据: {counts["bond_count"]} 条')
        
    except Exception as e:
        tm.log(task_id, 'WARNING', f'解析部分数据失败: {str(e)}')
    
    return counts

def _save_stats(db_path: Path, bundle_path: Path, file_stats: Dict, data_counts: Dict):
    """保存统计数据到数据库（幂等）"""
    conn = sqlite3.connect(str(db_path))
    
    # 使用 INSERT OR REPLACE 实现幂等
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
    
    conn.commit()
    conn.close()
```

### 6.2 幂等策略

**单行表设计**：`market_data_stats` 表使用 `id = 1` 约束，确保只有一行数据

**INSERT OR REPLACE**：每次分析都覆盖旧数据，不产生重复记录

**可重复执行**：分析失败后可重新触发，不会产生脏数据


## 7. 自动触发机制与调用链

### 7.1 触发场景

数据分析需要在以下场景自动触发：

1. **全量下载完成后**：解压完成 → 自动触发分析
2. **增量更新完成后**：更新完成 → 自动触发分析
3. **定时任务完成后**：cron 任务完成 → 自动触发分析

### 7.2 调用链设计

#### 7.2.1 全量下载调用链

```
用户点击"全量下载" 
  ↓
POST /api/market-data/download/full
  ↓
检查"当月已最新"（见 9.1）
  ↓
submit_task('full', do_full_download)
  ↓
返回 task_id 给前端
  ↓
后台线程执行 do_full_download(task_id)
  ├─ 阶段1: download_with_progress() → 下载 zip
  ├─ 阶段2: unzip_with_progress() → 解压到 bundle 目录
  └─ 阶段3: 自动触发 → submit_task('analyze', analyze_bundle)
       ↓
     analyze_bundle(task_id) → 分析并写入数据库
```

#### 7.2.2 增量更新调用链

```
用户点击"增量更新"
  ↓
POST /api/market-data/download/incremental
  ↓
检查"当月已最新"（见 9.1）
  ↓
submit_task('incremental', do_incremental_update)
  ↓
返回 task_id 给前端
  ↓
后台线程执行 do_incremental_update(task_id)
  ├─ 执行 rqalpha update-bundle
  └─ 完成后自动触发 → submit_task('analyze', analyze_bundle)
       ↓
     analyze_bundle(task_id) → 分析并写入数据库
```

#### 7.2.3 定时任务调用链

```
APScheduler 触发（按 cron 表达式）
  ↓
cron_job_handler()
  ├─ 检查是否启用
  ├─ 检查是否有正在运行的任务（互斥）
  └─ 根据配置的 task_type 提交任务
       ↓
     submit_task(task_type, task_func, source='cron')
       ↓
     执行下载/更新 → 完成后自动触发分析
       ↓
     记录到 market_data_cron_logs
```

### 7.3 自动触发实现

**文件位置**：`backtest/app/market_data/tasks.py`

```python
# backtest/app/market_data/tasks.py
from pathlib import Path
import subprocess
import os
from app.market_data.task_manager import get_task_manager
from app.market_data.analyzer import analyze_bundle

def do_full_download(task_id: str):
    """全量下载任务"""
    tm = get_task_manager()
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
    
    try:
        # 阶段1: 下载
        tm.update_progress(task_id, 0, 'download', '开始下载...')
        zip_url = "https://bundle.rqalpha.io/bundle.zip"  # 实际 URL
        zip_path = Path("/tmp/rqalpha_bundle.zip")
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
        tm.log(task_id, 'ERROR', f'全量下载失败: {str(e)}')
        raise

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
            # 根据输出解析进度（如果 rqalpha 提供进度信息）
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

## 8. 路径与权限管理

### 8.1 Bundle 路径配置

**环境变量**：`RQALPHA_BUNDLE_PATH`

**容器内路径**：`/data/rqalpha/bundle`

**宿主机挂载**：Docker named volume `rqalpha_bundle`

**配置位置**：`backtest/.env.wsgi`

```bash
RQALPHA_BUNDLE_PATH='/data/rqalpha/bundle'
```

### 8.2 权限要求

**容器内用户**：应用运行用户需要对 bundle 目录有读写权限

**目录权限**：
```bash
# 确保目录存在且有正确权限
mkdir -p /data/rqalpha/bundle
chown -R app:app /data/rqalpha/bundle
chmod 755 /data/rqalpha/bundle
```

**Docker Compose 配置**：

```yaml
services:
  backtest:
    volumes:
      - rqalpha_bundle:/data/rqalpha/bundle
    environment:
      - RQALPHA_BUNDLE_PATH=/data/rqalpha/bundle

volumes:
  rqalpha_bundle:
    driver: local
```

### 8.3 路径验证

应用启动时验证 bundle 路径：

```python
# backtest/app/market_data/__init__.py
import os
from pathlib import Path

def validate_bundle_path():
    """验证 bundle 路径配置"""
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    
    if not bundle_path.exists():
        bundle_path.mkdir(parents=True, exist_ok=True)
    
    if not os.access(bundle_path, os.R_OK | os.W_OK):
        raise PermissionError(f'Bundle 路径无读写权限: {bundle_path}')
    
    return bundle_path

# 在应用启动时调用
validate_bundle_path()
```

## 9. "当月已最新"判断与确认弹框

### 9.1 判断规则

**规则**：检查 bundle 目录中最近修改的文件，如果修改时间在当前月份，则认为"当月已最新"

**实现**：

```python
# backtest/app/market_data/utils.py
from pathlib import Path
from datetime import datetime
import os

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

### 9.2 API 集成

**下载前检查**：

```python
# backtest/app/api/market_data_api.py
from flask import jsonify, request
from app.market_data.utils import is_current_month_updated
from app.market_data.task_manager import get_task_manager
from app.market_data.tasks import do_full_download, do_incremental_update
import os
from pathlib import Path

@bp_market_data.route('/download/full', methods=['POST'])
def trigger_full_download():
    """触发全量下载"""
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    
    # 检查是否需要用户确认
    force = request.json.get('force', False)
    if not force and is_current_month_updated(bundle_path):
        return jsonify({
            'need_confirm': True,
            'message': '检测到当月已有更新，确定要重新下载吗？'
        }), 200
    
    # 提交任务
    try:
        tm = get_task_manager()
        task_id = tm.submit_task('full', do_full_download)
        return jsonify({'task_id': task_id}), 202
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409

@bp_market_data.route('/download/incremental', methods=['POST'])
def trigger_incremental_update():
    """触发增量更新"""
    bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
    
    # 检查是否需要用户确认
    force = request.json.get('force', False)
    if not force and is_current_month_updated(bundle_path):
        return jsonify({
            'need_confirm': True,
            'message': '检测到当月已有更新，确定要再次更新吗？'
        }), 200
    
    # 提交任务
    try:
        tm = get_task_manager()
        task_id = tm.submit_task('incremental', do_incremental_update)
        return jsonify({'task_id': task_id}), 202
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
```

### 9.3 前端交互流程

```
用户点击"全量下载"
  ↓
POST /api/market-data/download/full (force=false)
  ↓
后端检查 is_current_month_updated()
  ↓
如果返回 need_confirm=true
  ↓
前端显示确认弹框："检测到当月已有更新，确定要重新下载吗？"
  ├─ 用户点击"取消" → 不执行
  └─ 用户点击"确定" → POST /api/market-data/download/full (force=true)
       ↓
     后端提交任务，返回 task_id
       ↓
     前端轮询进度 GET /api/market-data/tasks/{task_id}
```

## 10. 失败恢复与重试策略

### 10.1 任务失败处理

**失败状态**：任务执行异常时，状态设为 `failed`，错误信息记录到 `error` 字段

**重试机制**：

```python
# backtest/app/api/market_data_api.py
@bp_market_data.route('/tasks/<task_id>/retry', methods=['POST'])
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
    if task_type == 'full':
        new_task_id = tm.submit_task('full', do_full_download, source='retry')
    elif task_type == 'incremental':
        new_task_id = tm.submit_task('incremental', do_incremental_update, source='retry')
    elif task_type == 'analyze':
        bundle_path = Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
        db_path = Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"
        new_task_id = tm.submit_task('analyze', analyze_bundle,
                                     task_args=(bundle_path, db_path),
                                     source='retry')
    else:
        return jsonify({'error': '未知任务类型'}), 400
    
    return jsonify({'task_id': new_task_id}), 202
```

### 10.2 断点续传（全量下载）

**策略**：下载失败后，下次下载从头开始（不实现断点续传，因为 bundle.zip 通常不大）

**临时文件清理**：

```python
def do_full_download(task_id: str):
    """全量下载任务（带清理）"""
    tm = get_task_manager()
    zip_path = Path("/tmp/rqalpha_bundle.zip")
    
    try:
        # 清理旧的临时文件
        if zip_path.exists():
            zip_path.unlink()
        
        # 下载...
        download_with_progress(task_id, zip_url, zip_path)
        
        # 解压...
        unzip_with_progress(task_id, zip_path, bundle_path)
        
    except Exception as e:
        # 失败时清理临时文件
        if zip_path.exists():
            zip_path.unlink()
        raise
    finally:
        # 确保临时文件被删除
        if zip_path.exists():
            zip_path.unlink()
```

### 10.3 脏状态避免

**原子性操作**：

1. **下载**：先下载到临时文件 `/tmp/rqalpha_bundle.zip`
2. **解压**：解压到 bundle 目录（覆盖旧文件）
3. **失败回滚**：下载或解压失败时，不影响现有 bundle（因为临时文件独立）

**数据库幂等**：

- 使用 `INSERT OR REPLACE` 确保统计数据不重复
- 任务表使用 UUID 主键，不会冲突

### 10.4 任务取消

**取消机制**：

```python
# backtest/app/api/market_data_api.py
@bp_market_data.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id: str):
    """取消正在运行的任务"""
    tm = get_task_manager()
    task = tm.get_task_status(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    if task['status'] not in ('pending', 'running'):
        return jsonify({'error': '任务已完成或失败，无法取消'}), 400
    
    # 标记为取消（实际取消需要任务内部检查）
    tm._update_task_status(task_id, 'cancelled')
    
    return jsonify({'message': '任务已取消'}), 200
```

**注意**：由于使用后台线程，真正的取消需要任务内部定期检查状态。简化实现中，只标记状态为 `cancelled`，任务可能仍会执行完成。


## 11. 定时任务实现（APScheduler）

### 11.1 新增依赖

**requirements.txt**：

```
APScheduler==3.10.4
```

### 11.2 调度器初始化

**文件位置**：`backtest/app/market_data/scheduler.py`

```python
# backtest/app/market_data/scheduler.py
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

### 11.3 应用启动集成

**修改**：`backtest/app/__init__.py`

```python
def create_app(config_name):
    from .api.login_api import bp_login
    from .api.backtest_api import bp_backtest
    from .api.research_api import bp_research
    from .api.system_api import bp_system
    from .api.market_data_api import bp_market_data  # 新增
    from .backtest.services.runner import ensure_default_demo_strategy
    from .market_data.scheduler import init_scheduler  # 新增
    from flask import Flask
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.config.from_object(CONFIG[config_name])

    app.register_blueprint(bp_login)
    app.register_blueprint(bp_backtest)
    app.register_blueprint(bp_research)
    app.register_blueprint(bp_system)
    app.register_blueprint(bp_market_data)  # 新增

    try:
        with app.app_context():
            ensure_default_demo_strategy()
            init_scheduler()  # 新增：初始化定时任务
    except Exception:
        app.logger.exception("failed to initialize app")

    return app
```

## 12. API 实现详情

### 12.1 完整 API 实现

**文件位置**：`backtest/app/api/market_data_api.py`

```python
# backtest/app/api/market_data_api.py
from flask import Blueprint, jsonify, request
from pathlib import Path
import os
import sqlite3
from datetime import datetime

from app.auth import auth_required
from app.market_data.task_manager import get_task_manager
from app.market_data.tasks import do_full_download, do_incremental_update
from app.market_data.analyzer import analyze_bundle
from app.market_data.utils import is_current_month_updated
from app.market_data.scheduler import update_cron_schedule

bp_market_data = Blueprint('market_data', __name__, url_prefix='/api/market-data')

def _get_db_path():
    """获取数据库路径"""
    return Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"

def _get_bundle_path():
    """获取 bundle 路径"""
    return Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))

@bp_market_data.route('/overview', methods=['GET'])
@auth_required
def get_overview():
    """获取数据全景"""
    db_path = _get_db_path()
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM market_data_stats WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({
                'analyzed': False,
                'message': '尚未分析数据，请先触发数据分析'
            }), 200
        
        return jsonify({
            'analyzed': True,
            'data': dict(row)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_market_data.route('/analyze', methods=['POST'])
@auth_required
def trigger_analyze():
    """触发数据分析"""
    try:
        tm = get_task_manager()
        bundle_path = _get_bundle_path()
        db_path = _get_db_path()
        
        task_id = tm.submit_task(
            'analyze', 
            analyze_bundle,
            task_args=(bundle_path, db_path),
            source='manual'
        )
        
        return jsonify({'task_id': task_id}), 202
        
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        task_id = tm.submit_task('incremental', do_incremental_update, source='manual')
        return jsonify({'task_id': task_id}), 202
        
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        task_id = tm.submit_task('full', do_full_download, source='manual')
        return jsonify({'task_id': task_id}), 202
        
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT OR REPLACE INTO market_data_cron_config 
            (id, enabled, cron_expression, task_type, updated_at)
            VALUES (1, ?, ?, ?, ?)
        """, (1 if enabled else 0, cron_expression, task_type, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        # 更新调度器
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

### 12.2 错误码定义

| HTTP 状态码 | 错误场景 | 响应示例 |
|------------|---------|---------|
| 200 | 成功 | `{"data": {...}}` |
| 202 | 任务已提交 | `{"task_id": "uuid"}` |
| 400 | 请求参数错误 | `{"error": "无效的任务类型"}` |
| 404 | 资源不存在 | `{"error": "任务不存在"}` |
| 409 | 冲突（任务互斥） | `{"error": "已有任务正在运行，请等待完成后再试"}` |
| 500 | 服务器内部错误 | `{"error": "数据库连接失败"}` |

## 13. 前端集成指南

### 13.1 导航栏集成

**位置**：在"研究工作台"后新增"行情数据管理"入口

**路由**：`/market-data`

### 13.2 页面结构

```
/market-data
  ├── /overview          # 数据全景
  ├── /download          # 手动下载（增量+全量）
  └── /config            # 下载配置
```

### 13.3 进度条实现示例

```javascript
// 轮询任务进度
async function pollTaskProgress(taskId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/market-data/tasks/${taskId}`);
    const task = await response.json();
    
    // 更新进度条
    updateProgressBar(task.progress, task.stage, task.message);
    
    // 任务完成或失败时停止轮询
    if (['success', 'failed', 'cancelled'].includes(task.status)) {
      clearInterval(interval);
      handleTaskComplete(task);
    }
  }, 1000); // 每秒轮询一次
}
```

### 13.4 确认弹框实现

```javascript
async function triggerDownload(type) {
  const response = await fetch(`/api/market-data/download/${type}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({force: false})
  });
  
  const data = await response.json();
  
  if (data.need_confirm) {
    // 显示确认弹框
    const confirmed = await showConfirmDialog(data.message);
    if (confirmed) {
      // 用户确认，强制执行
      const retryResponse = await fetch(`/api/market-data/download/${type}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({force: true})
      });
      const retryData = await retryResponse.json();
      pollTaskProgress(retryData.task_id);
    }
  } else if (data.task_id) {
    // 直接开始轮询进度
    pollTaskProgress(data.task_id);
  }
}
```

## 14. 部署注意事项

### 14.1 环境变量

确保 `.env.wsgi` 包含：

```bash
RQALPHA_BUNDLE_PATH='/data/rqalpha/bundle'
```

### 14.2 Docker Volume

确保 `docker-compose.yml` 配置了 volume：

```yaml
volumes:
  - rqalpha_bundle:/data/rqalpha/bundle
```

### 14.3 依赖安装

更新 `requirements.txt` 后重新构建镜像：

```bash
pip install -r requirements.txt
```

或在 Dockerfile 中：

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

### 14.4 数据库初始化

应用首次启动时会自动创建数据库表（通过 `TaskManager._init_db()`）

### 14.5 权限检查

确保应用用户对以下路径有读写权限：
- `/data/rqalpha/bundle`
- `backtest/data/market_data.sqlite3`

## 15. 总结

本架构设计实现了行情数据管理功能的完整技术方案：

**核心特性**：
- ✅ 轻量级任务系统（无需 Celery/RQ）
- ✅ 统一进度追踪接口
- ✅ 任务互斥保证（同时只运行一个任务）
- ✅ 自动触发数据分析
- ✅ 幂等的数据统计
- ✅ "当月已最新"智能判断
- ✅ 失败重试机制
- ✅ APScheduler 定时任务
- ✅ 完整的日志记录

**非侵入性**：
- ✅ 新增独立蓝图，不修改现有路由
- ✅ 独立数据库文件，不影响现有数据
- ✅ 独立模块目录结构

**生产就绪**：
- ✅ 错误处理和日志记录
- ✅ 权限验证（@auth_required）
- ✅ 路径和权限管理
- ✅ Docker 环境适配

**下一步**：根据本架构设计文档实施开发。
