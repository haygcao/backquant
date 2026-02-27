---
story_id: STORY-08
title: 回归测试与文档
priority: P1
status: TODO
dependencies: [STORY-01, STORY-02, STORY-03, STORY-04, STORY-05, STORY-06, STORY-07]
estimated_effort: 8h
related_docs:
  - test-plan-market-data-mgmt.md (Section 2, 14, 15)
---

# Story 08: 回归测试与文档

## 用户故事

作为开发团队，我需要确保新功能不影响现有系统，并提供完整的文档，以便用户和维护人员理解和使用该功能。

## 业务价值

- 保证系统稳定性，避免回归问题
- 提供完整文档，降低学习成本
- 建立测试基线，便于后续维护

## 技术实现

### 1. 非回归测试（冒烟测试）

**测试范围**:
- 登录功能
- 回测工作台
- 研究工作台
- 导航栏集成

**测试用例**:

#### TC-REG-001: 登录功能正常
```python
def test_login_functionality():
    """验证登录功能未受影响"""
    response = client.post('/api/login', json={
        'username': 'test_user',
        'password': 'test_password'
    })
    assert response.status_code == 200
    assert 'token' in response.json()
```

#### TC-REG-002: 回测工作台正常
```python
def test_backtest_workspace():
    """验证回测工作台功能正常"""
    # 登录
    login_response = client.post('/api/login', json={
        'username': 'test_user',
        'password': 'test_password'
    })
    token = login_response.json()['token']

    # 访问回测工作台
    response = client.get('/api/backtest/strategies', headers={
        'Authorization': f'Bearer {token}'
    })
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

#### TC-REG-003: 研究工作台正常
```python
def test_research_workspace():
    """验证研究工作台功能正常"""
    # 登录
    login_response = client.post('/api/login', json={
        'username': 'test_user',
        'password': 'test_password'
    })
    token = login_response.json()['token']

    # 访问研究工作台
    response = client.get('/api/research/notebooks', headers={
        'Authorization': f'Bearer {token}'
    })
    assert response.status_code == 200
```

#### TC-REG-004: 导航栏新增入口
```javascript
// E2E 测试
describe('Navigation', () => {
  it('should show market data management entry', () => {
    cy.login('test_user', 'test_password');
    cy.get('nav').should('contain', '行情数据管理');
    cy.contains('行情数据管理').click();
    cy.url().should('include', '/market-data');
  });
});
```

### 2. 集成测试

**测试文件位置**: `backtest/tests/test_market_data_integration.py`

```python
import pytest
from pathlib import Path
from app.market_data.task_manager import get_task_manager
from app.market_data.analyzer import analyze_bundle
from app.market_data.tasks import do_incremental_update, do_full_download

class TestMarketDataIntegration:
    """行情数据管理集成测试"""

    def test_full_workflow(self, test_client, test_db):
        """测试完整工作流：全量下载 → 解压 → 分析"""
        # 1. 触发全量下载
        response = test_client.post('/api/market-data/download/full', json={
            'force': True
        })
        assert response.status_code == 202
        task_id = response.json()['task_id']

        # 2. 等待任务完成
        # ... (轮询任务状态)

        # 3. 验证数据已分析
        response = test_client.get('/api/market-data/overview')
        assert response.status_code == 200
        assert response.json()['analyzed'] == True

    def test_incremental_workflow(self, test_client, test_db):
        """测试增量更新工作流"""
        # ... 类似测试

    def test_cron_workflow(self, test_client, test_db):
        """测试定时任务工作流"""
        # ... 类似测试
```

### 3. E2E 测试

**测试文件位置**: `frontend/tests/e2e/market-data.spec.js`

```javascript
describe('Market Data Management E2E', () => {
  beforeEach(() => {
    cy.login('test_user', 'test_password');
    cy.visit('/market-data');
  });

  it('should display overview page', () => {
    cy.contains('数据全景').should('be.visible');
  });

  it('should trigger incremental update', () => {
    cy.visit('/market-data/download');
    cy.contains('增量更新').click();
    cy.get('.task-progress').should('be.visible');
  });

  it('should show confirm dialog for current month data', () => {
    // Mock API response with need_confirm
    cy.intercept('POST', '/api/market-data/download/incremental', {
      statusCode: 200,
      body: {
        need_confirm: true,
        message: '检测到当月已有更新，确定要再次更新吗？'
      }
    });

    cy.visit('/market-data/download');
    cy.contains('增量更新').click();
    cy.get('.confirm-dialog').should('be.visible');
    cy.contains('检测到当月已有更新').should('be.visible');
  });

  it('should configure cron schedule', () => {
    cy.visit('/market-data/config');
    cy.get('input[type="checkbox"]').check();
    cy.get('input[placeholder*="cron"]').clear().type('0 3 1 * *');
    cy.get('select').select('full');
    cy.contains('保存配置').click();
    cy.contains('配置已更新').should('be.visible');
  });
});
```

### 4. 用户文档

**文件位置**: `docs/market-data-management.md`

```markdown
# 行情数据管理功能使用指南

## 概述

行情数据管理功能为 RQAlpha 行情数据包（bundle）提供可视化管理界面，支持数据查看、手动下载和定时任务配置。

## 功能说明

### 1. 数据全景

查看当前 bundle 的统计信息：
- 下载时间
- 总文件数和总大小
- 最近修改时间
- 各品种行情条数（股票、基金、期货、指数、债券）

**操作步骤**：
1. 点击导航栏"行情数据管理"
2. 默认进入"数据全景"页面
3. 点击"触发分析"按钮手动更新统计数据

### 2. 手动下载

支持两种下载方式：

#### 增量更新
- 使用 `rqalpha update-bundle` 命令
- 数据追加到现有 bundle
- 适用于日常更新

**操作步骤**：
1. 进入"手动下载"页面
2. 点击"增量更新"按钮
3. 如果当月已更新，会弹出确认对话框
4. 确认后开始下载，实时显示进度

#### 全量下载
- 下载完整的 bundle 压缩包
- 解压到 bundle 目录
- 适用于首次安装或数据重建

**操作步骤**：
1. 进入"手动下载"页面
2. 点击"全量下载"按钮
3. 如果当月已更新，会弹出确认对话框
4. 确认后开始下载和解压，实时显示进度

### 3. 下载配置

配置定时任务自动更新数据。

**操作步骤**：
1. 进入"下载配置"页面
2. 勾选"启用定时任务"
3. 设置 Cron 表达式（如 `0 2 1 * *` 表示每月1日凌晨2点）
4. 选择任务类型（增量更新或全量下载）
5. 点击"保存配置"

**Cron 表达式示例**：
- `0 2 1 * *` - 每月1日凌晨2点
- `0 3 * * 0` - 每周日凌晨3点
- `0 4 1,15 * *` - 每月1日和15日凌晨4点

**查看运行日志**：
- 在"下载配置"页面下方查看定时任务运行历史
- 点击"详情"查看任务详细信息

## 注意事项

1. **任务互斥**：同一时间只能运行一个任务（下载/解压/分析）
2. **当月已最新**：如果 bundle 在当月已更新，系统会提示确认
3. **自动分析**：下载或更新完成后会自动触发数据分析
4. **权限要求**：所有操作需要登录后才能执行

## 故障排查

### 问题1：下载失败
- 检查网络连接
- 查看任务日志了解具体错误
- 使用"重试"功能重新执行

### 问题2：解压失败
- 检查磁盘空间是否充足
- 检查 bundle 目录权限
- 查看任务日志了解具体错误

### 问题3：分析失败
- 检查 bundle 目录是否存在
- 检查数据文件格式是否正确
- 查看任务日志了解具体错误

### 问题4：定时任务未执行
- 检查定时任务是否已启用
- 检查 Cron 表达式是否正确
- 查看运行日志了解跳过原因

## API 参考

详见 `arch-market-data-mgmt.md` 文档。
```

### 5. 开发者文档

**文件位置**: `docs/dev/market-data-architecture.md`

```markdown
# 行情数据管理功能 - 开发者文档

## 架构概述

详见 `_bmad-output/arch-market-data-mgmt.md`

## 代码结构

```
backtest/app/market_data/
├── __init__.py
├── db_init.py          # 数据库初始化
├── task_manager.py     # 任务管理器
├── analyzer.py         # 数据分析
├── tasks.py            # 任务函数（下载/更新）
├── utils.py            # 工具函数
└── scheduler.py        # 定时任务调度

backtest/app/api/
└── market_data_api.py  # API 端点

frontend/src/views/MarketData/
├── Layout.vue          # 布局
├── Overview.vue        # 数据全景
├── Download.vue        # 手动下载
└── Config.vue          # 下载配置
```

## 扩展指南

### 添加新的数据品种

1. 修改 `analyzer.py` 中的 `_parse_bundle_data` 函数
2. 在数据库表 `market_data_stats` 中添加新字段
3. 更新前端显示

### 添加新的任务类型

1. 在 `tasks.py` 中实现任务函数
2. 在 `task_manager.py` 中注册任务类型
3. 在 API 中添加触发端点

## 测试指南

运行测试：
```bash
# 单元测试
pytest backtest/tests/test_market_data_*.py

# 集成测试
pytest backtest/tests/test_market_data_integration.py

# E2E 测试
cd frontend && npm run test:e2e
```
```

### 6. 部署文档

**文件位置**: `docs/deployment/market-data-setup.md`

```markdown
# 行情数据管理功能 - 部署指南

## 环境要求

- Python 3.11+
- APScheduler 3.10.4
- Docker（可选）

## 安装步骤

1. 更新依赖
```bash
cd backtest
pip install -r requirements.txt
```

2. 配置环境变量
```bash
# .env.wsgi
RQALPHA_BUNDLE_PATH='/data/rqalpha/bundle'
```

3. 初始化数据库
```bash
# 应用启动时自动创建
python wsgi.py
```

4. 验证安装
```bash
# 访问 http://localhost:54321/market-data
```

## Docker 部署

确保 `docker-compose.yml` 包含：
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

## 权限配置

确保应用用户对 bundle 目录有读写权限：
```bash
mkdir -p /data/rqalpha/bundle
chown -R app:app /data/rqalpha/bundle
chmod 755 /data/rqalpha/bundle
```
```

## 验收标准

### AC-01: 非回归测试全部通过
- [ ] 登录功能测试通过
- [ ] 回测工作台测试通过
- [ ] 研究工作台测试通过
- [ ] 导航栏集成测试通过

### AC-02: 集成测试全部通过
- [ ] 全量下载工作流测试通过
- [ ] 增量更新工作流测试通过
- [ ] 定时任务工作流测试通过
- [ ] 任务互斥测试通过

### AC-03: E2E 测试全部通过
- [ ] 数据全景页面测试通过
- [ ] 手动下载页面测试通过
- [ ] 确认弹框测试通过
- [ ] 下载配置页面测试通过

### AC-04: 用户文档完整
- [ ] 功能说明清晰
- [ ] 操作步骤详细
- [ ] 故障排查指南完整
- [ ] 示例充分

### AC-05: 开发者文档完整
- [ ] 架构说明清晰
- [ ] 代码结构说明完整
- [ ] 扩展指南详细
- [ ] 测试指南完整

### AC-06: 部署文档完整
- [ ] 环境要求明确
- [ ] 安装步骤详细
- [ ] Docker 配置正确
- [ ] 权限配置说明清晰

## 测试用例

- **TC-REG-001**: 登录功能正常
- **TC-REG-002**: 回测工作台正常
- **TC-REG-003**: 研究工作台正常
- **TC-REG-004**: 导航栏新增入口

## 技术债务

无

## 注意事项

1. 回归测试必须在所有功能开发完成后执行
2. 测试环境应与生产环境尽可能一致
3. 文档应随代码变更同步更新
4. 部署文档应包含回滚步骤

## 完成定义 (DoD)

- [ ] 所有非回归测试通过
- [ ] 所有集成测试通过
- [ ] 所有 E2E 测试通过
- [ ] 用户文档已完成
- [ ] 开发者文档已完成
- [ ] 部署文档已完成
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
