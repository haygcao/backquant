---
story_id: STORY-02
title: 全景统计分析函数与手动触发分析 API
priority: P0
status: TODO
dependencies: [STORY-01]
estimated_effort: 6h
related_docs:
  - arch-market-data-mgmt.md (Section 6)
  - test-plan-market-data-mgmt.md (Section 7)
---

# Story 02: 全景统计分析函数与手动触发分析 API

## 用户故事

作为用户，我需要能够查看 bundle 数据的全景统计信息，并手动触发数据分析，以便了解当前数据状态。

## 业务价值

- 提供数据可见性，用户可以了解 bundle 的基本信息
- 支持手动触发分析，灵活控制数据更新
- 为数据全景页面提供后端支持

## 技术实现

### 1. 数据分析模块

**文件位置**: `backtest/app/market_data/analyzer.py`

#### 1.1 入口函数

```python
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

    try:
        # 1. 扫描文件
        file_stats = _scan_files(bundle_path)

        # 2. 解析各品种数据
        data_counts = _parse_bundle_data(bundle_path, tm, task_id)

        # 3. 写入数据库（幂等）
        _save_stats(db_path, bundle_path, file_stats, data_counts)

        tm.update_progress(task_id, 100, 'analyze', '分析完成')
    except Exception as e:
        tm.log(task_id, 'ERROR', f'分析失败: {str(e)}')
        raise
```

#### 1.2 文件扫描函数

```python
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
```

#### 1.3 数据解析函数

```python
def _parse_bundle_data(bundle_path: Path, tm, task_id: str) -> Dict:
    """解析 bundle 数据，统计各品种条数"""
    counts = {
        'stock_count': 0,
        'fund_count': 0,
        'futures_count': 0,
        'index_count': 0,
        'bond_count': 0
    }

    try:
        # 使用 bcolz 解析各品种数据
        import bcolz

        # 股票数据
        tm.update_progress(task_id, 40, 'analyze', '正在解析股票数据...')
        stock_file = bundle_path / 'stocks.bcolz'
        if stock_file.exists():
            stocks = bcolz.open(str(stock_file))
            counts['stock_count'] = len(stocks)

        # 基金、期货、指数、债券数据...
        # （类似逻辑）

    except Exception as e:
        tm.log(task_id, 'WARNING', f'解析部分数据失败: {str(e)}')

    return counts
```

#### 1.4 数据保存函数（幂等）

```python
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

### 2. API 端点

**文件位置**: `backtest/app/api/market_data_api.py`

#### 2.1 获取数据全景

```python
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
```

#### 2.2 手动触发分析

```python
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
```

### 3. 工具函数

```python
def _get_db_path():
    """获取数据库路径"""
    return Path(__file__).parent.parent.parent / "data" / "market_data.sqlite3"

def _get_bundle_path():
    """获取 bundle 路径"""
    return Path(os.environ.get('RQALPHA_BUNDLE_PATH', '/data/rqalpha/bundle'))
```

## 验收标准

### AC-01: 文件扫描功能正常
- [ ] 能正确扫描 bundle 目录下的所有文件
- [ ] 统计文件总数、总大小
- [ ] 找到最近修改时间
- [ ] 空目录时不报错

### AC-02: 数据解析功能正常
- [ ] 能正确解析股票、基金、期货、指数、债券数据
- [ ] 统计各品种数据条数
- [ ] 文件不存在时返回 0
- [ ] 解析失败时记录警告日志但不中断

### AC-03: 数据保存幂等性
- [ ] 多次分析同一 bundle，统计数据一致
- [ ] 使用 INSERT OR REPLACE，只有一条记录
- [ ] analyzed_at 时间更新
- [ ] 单行表约束生效（id=1）

### AC-04: GET /api/market-data/overview 正常响应
- [ ] 未分析时返回 analyzed=false
- [ ] 已分析时返回 analyzed=true 和完整数据
- [ ] 需要认证（@auth_required）
- [ ] 错误时返回 500

### AC-05: POST /api/market-data/analyze 正常响应
- [ ] 成功提交任务，返回 task_id
- [ ] HTTP 状态码 202
- [ ] 需要认证（@auth_required）
- [ ] 有任务运行时返回 409

### AC-06: 分析进度正确更新
- [ ] 进度从 0 递增到 100
- [ ] stage 为 'analyze'
- [ ] message 显示当前阶段（扫描文件、解析数据、写入数据库）
- [ ] 完成时 progress=100

## 测试用例

- **TC-ANALYZE-001**: 多次触发分析，结果一致（幂等）
- **TC-ANALYZE-002**: 分析后统计数据正确写入数据库
- **TC-ANALYZE-006**: 分析失败不影响现有数据
- **TC-API-002**: GET /api/market-data/overview 正常响应
- **TC-API-003**: GET /api/market-data/overview 未分析时响应
- **TC-API-004**: POST /api/market-data/analyze 正常响应

## 技术债务

- 考虑支持更多数据品种（如可转债、ETF）
- 考虑增加数据质量检查（缺失数据、异常值）

## 注意事项

1. 分析函数需要依赖 TaskManager（STORY-03）
2. 使用 bcolz 库解析 bundle 数据
3. 解析失败时记录警告但不中断整个分析
4. 幂等性通过 INSERT OR REPLACE 实现

## 完成定义 (DoD)

- [ ] 分析函数已实现并通过单元测试
- [ ] API 端点已实现并通过集成测试
- [ ] 幂等性验证通过
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
