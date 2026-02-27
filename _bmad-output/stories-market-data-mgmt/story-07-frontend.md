---
story_id: STORY-07
title: 前端实现：导航入口、3个子页面、进度条与弹框
priority: P0
status: TODO
dependencies: [STORY-02, STORY-03, STORY-04, STORY-05, STORY-06]
estimated_effort: 12h
related_docs:
  - arch-market-data-mgmt.md (Section 2, 9, 13)
  - test-plan-market-data-mgmt.md (Section 2, 3, 4, 6)
---

# Story 07: 前端实现：导航入口、3个子页面、进度条与弹框

## 用户故事

作为用户，我需要一个可视化的前端界面来管理行情数据，包括查看数据全景、手动触发下载、配置定时任务，以便方便地管理数据。

## 业务价值

- 提供友好的用户界面，降低使用门槛
- 实时显示任务进度，提升用户体验
- 支持确认弹框，避免误操作
- 提供完整的日志查看功能

## 技术实现

### 1. 导航栏集成

**文件位置**: `frontend/src/components/Navigation.vue` (或类似文件)

**要求**:
- 在"研究工作台"后新增"行情数据管理"入口
- 路由路径: `/market-data`
- 图标: 数据库或下载图标

```vue
<template>
  <nav>
    <!-- 现有导航项 -->
    <router-link to="/backtest">回测工作台</router-link>
    <router-link to="/research">研究工作台</router-link>
    <router-link to="/market-data">行情数据管理</router-link> <!-- 新增 -->
  </nav>
</template>
```

### 2. 路由配置

**文件位置**: `frontend/src/router/index.js` (或类似文件)

```javascript
{
  path: '/market-data',
  component: () => import('@/views/MarketData/Layout.vue'),
  children: [
    {
      path: '',
      redirect: 'overview'
    },
    {
      path: 'overview',
      name: 'MarketDataOverview',
      component: () => import('@/views/MarketData/Overview.vue')
    },
    {
      path: 'download',
      name: 'MarketDataDownload',
      component: () => import('@/views/MarketData/Download.vue')
    },
    {
      path: 'config',
      name: 'MarketDataConfig',
      component: () => import('@/views/MarketData/Config.vue')
    }
  ]
}
```

### 3. 页面1：数据全景 (Overview.vue)

**功能**:
- 显示 bundle 基本信息（下载时间、文件数、总大小、最近修改时间）
- 显示各品种行情条数（股票、基金、期货、指数、债券）
- 提供"手动触发分析"按钮

**API 调用**:
- `GET /api/market-data/overview` - 获取统计数据
- `POST /api/market-data/analyze` - 触发分析

**UI 组件**:
```vue
<template>
  <div class="overview-page">
    <h2>数据全景</h2>

    <!-- 未分析状态 -->
    <div v-if="!data.analyzed" class="empty-state">
      <p>{{ data.message }}</p>
      <button @click="triggerAnalyze">触发数据分析</button>
    </div>

    <!-- 已分析状态 -->
    <div v-else class="stats-grid">
      <div class="stat-card">
        <h3>基本信息</h3>
        <p>下载时间: {{ formatDate(data.data.analyzed_at) }}</p>
        <p>总文件数: {{ data.data.total_files }}</p>
        <p>总大小: {{ formatSize(data.data.total_size_bytes) }}</p>
        <p>最近修改: {{ formatDate(data.data.last_modified) }}</p>
      </div>

      <div class="stat-card">
        <h3>行情数据条数</h3>
        <p>股票: {{ data.data.stock_count }}</p>
        <p>基金: {{ data.data.fund_count }}</p>
        <p>期货: {{ data.data.futures_count }}</p>
        <p>指数: {{ data.data.index_count }}</p>
        <p>债券: {{ data.data.bond_count }}</p>
      </div>

      <button @click="triggerAnalyze">重新分析</button>
    </div>

    <!-- 任务进度显示 -->
    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" />
  </div>
</template>
```

### 4. 页面2：手动下载 (Download.vue)

**功能**:
- 增量更新按钮
- 全量下载按钮
- 实时显示任务进度（进度条 + 阶段提示）
- "当月已最新"确认弹框

**API 调用**:
- `POST /api/market-data/download/incremental` - 增量更新
- `POST /api/market-data/download/full` - 全量下载
- `GET /api/market-data/tasks/{task_id}` - 查询进度

**UI 组件**:
```vue
<template>
  <div class="download-page">
    <h2>手动下载</h2>

    <div class="download-actions">
      <button @click="triggerIncremental" :disabled="hasRunningTask">
        增量更新
      </button>
      <button @click="triggerFull" :disabled="hasRunningTask">
        全量下载
      </button>
    </div>

    <!-- 确认弹框 -->
    <ConfirmDialog
      v-if="showConfirm"
      :message="confirmMessage"
      @confirm="handleConfirm"
      @cancel="showConfirm = false"
    />

    <!-- 任务进度 -->
    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" />
  </div>
</template>

<script>
export default {
  methods: {
    async triggerIncremental() {
      const response = await fetch('/api/market-data/download/incremental', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: false })
      });

      const data = await response.json();

      if (data.need_confirm) {
        this.confirmMessage = data.message;
        this.confirmType = 'incremental';
        this.showConfirm = true;
      } else if (data.task_id) {
        this.currentTaskId = data.task_id;
        this.startPolling();
      }
    },

    async handleConfirm() {
      this.showConfirm = false;
      const endpoint = this.confirmType === 'incremental'
        ? '/api/market-data/download/incremental'
        : '/api/market-data/download/full';

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true })
      });

      const data = await response.json();
      if (data.task_id) {
        this.currentTaskId = data.task_id;
        this.startPolling();
      }
    }
  }
}
</script>
```

### 5. 页面3：下载配置 (Config.vue)

**功能**:
- Cron 表达式可视化配置
- 启用/禁用开关
- 任务类型选择（增量/全量）
- 运行日志列表
- 日志详情查看

**API 调用**:
- `GET /api/market-data/cron/config` - 获取配置
- `PUT /api/market-data/cron/config` - 更新配置
- `GET /api/market-data/cron/logs` - 获取日志列表
- `GET /api/market-data/cron/logs/{log_id}` - 获取日志详情

**UI 组件**:
```vue
<template>
  <div class="config-page">
    <h2>下载配置</h2>

    <!-- 定时任务配置 -->
    <div class="cron-config">
      <h3>定时任务</h3>
      <label>
        <input type="checkbox" v-model="config.enabled" />
        启用定时任务
      </label>

      <div class="form-group">
        <label>Cron 表达式</label>
        <input v-model="config.cron_expression" placeholder="0 2 1 * *" />
        <span class="hint">每月1日凌晨2点</span>
      </div>

      <div class="form-group">
        <label>任务类型</label>
        <select v-model="config.task_type">
          <option value="incremental">增量更新</option>
          <option value="full">全量下载</option>
        </select>
      </div>

      <button @click="saveConfig">保存配置</button>
    </div>

    <!-- 运行日志 -->
    <div class="cron-logs">
      <h3>运行日志</h3>
      <table>
        <thead>
          <tr>
            <th>触发时间</th>
            <th>状态</th>
            <th>任务ID</th>
            <th>消息</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.log_id">
            <td>{{ formatDate(log.trigger_time) }}</td>
            <td>
              <span :class="'status-' + log.status">{{ log.status }}</span>
            </td>
            <td>{{ log.task_id || '-' }}</td>
            <td>{{ log.message }}</td>
            <td>
              <button @click="viewLogDetail(log.log_id)">详情</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

### 6. 通用组件：任务进度 (TaskProgress.vue)

**功能**:
- 显示进度条（0-100%）
- 显示当前阶段（下载/解压/分析）
- 显示状态消息
- 轮询任务状态

```vue
<template>
  <div class="task-progress">
    <h4>任务进度</h4>
    <div class="progress-info">
      <span>阶段: {{ task.stage }}</span>
      <span>状态: {{ task.status }}</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: task.progress + '%' }"></div>
    </div>
    <p class="progress-message">{{ task.message }}</p>
  </div>
</template>

<script>
export default {
  props: ['taskId'],
  data() {
    return {
      task: {},
      pollInterval: null
    };
  },
  mounted() {
    this.startPolling();
  },
  beforeUnmount() {
    this.stopPolling();
  },
  methods: {
    async fetchTaskStatus() {
      const response = await fetch(`/api/market-data/tasks/${this.taskId}`);
      this.task = await response.json();

      // 任务完成或失败时停止轮询
      if (['success', 'failed', 'cancelled'].includes(this.task.status)) {
        this.stopPolling();
        this.$emit('task-complete', this.task);
      }
    },
    startPolling() {
      this.fetchTaskStatus();
      this.pollInterval = setInterval(this.fetchTaskStatus, 1000);
    },
    stopPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
    }
  }
};
</script>
```

### 7. 通用组件：确认弹框 (ConfirmDialog.vue)

```vue
<template>
  <div class="confirm-dialog-overlay">
    <div class="confirm-dialog">
      <h3>确认操作</h3>
      <p>{{ message }}</p>
      <div class="dialog-actions">
        <button @click="$emit('cancel')">取消</button>
        <button @click="$emit('confirm')" class="primary">确定</button>
      </div>
    </div>
  </div>
</template>
```

## 验收标准

### AC-01: 导航栏集成正常
- [ ] "行情数据管理"入口在"研究工作台"后面
- [ ] 点击后跳转到 `/market-data` 页面
- [ ] 图标和文字清晰可见

### AC-02: 数据全景页面正常
- [ ] 未分析时显示提示和"触发分析"按钮
- [ ] 已分析时显示完整统计信息
- [ ] 数据格式化正确（日期、文件大小）
- [ ] "重新分析"按钮正常工作

### AC-03: 手动下载页面正常
- [ ] 增量更新和全量下载按钮可用
- [ ] 有任务运行时按钮禁用
- [ ] "当月已最新"弹框正确显示
- [ ] 用户取消时不发送请求
- [ ] 用户确认时发送 force=true 请求

### AC-04: 进度条实时更新
- [ ] 进度条视觉上平滑递增
- [ ] 百分比数字与进度条一致
- [ ] 阶段提示正确（download/unzip/analyze）
- [ ] 状态消息清晰易懂
- [ ] 任务完成时停止轮询

### AC-05: 下载配置页面正常
- [ ] 配置表单正确显示
- [ ] 启用/禁用开关正常工作
- [ ] Cron 表达式可编辑
- [ ] 任务类型可选择
- [ ] 保存配置成功

### AC-06: 运行日志显示正常
- [ ] 日志列表按时间倒序显示
- [ ] 状态用不同颜色标识
- [ ] 支持分页（如果日志较多）
- [ ] 点击"详情"可查看完整信息

### AC-07: 错误处理正常
- [ ] API 错误时显示友好提示
- [ ] 网络错误时显示重试选项
- [ ] 401 错误时跳转到登录页
- [ ] 409 错误时显示"已有任务运行"提示

### AC-08: 响应式设计
- [ ] 在不同屏幕尺寸下正常显示
- [ ] 移动端可用（如果支持）

## 测试用例

- **TC-REG-004**: 导航栏新增入口
- **TC-CONFIRM-001**: 增量更新 - 当月已更新，显示确认弹框
- **TC-CONFIRM-002**: 增量更新 - 用户取消操作
- **TC-CONFIRM-003**: 增量更新 - 用户确认后强制执行
- **TC-CONFIRM-004**: 全量下载 - 当月已更新，显示确认弹框
- **TC-CONFIRM-005**: 全量下载 - 用户确认后强制执行
- **TC-PROGRESS-006**: 进度条实时更新（前端）
- **TC-CRON-005**: 定时任务日志正确记录

## 技术债务

- 考虑支持暗色主题
- 考虑支持国际化（i18n）
- 考虑添加数据可视化图表

## 注意事项

1. 使用项目现有的 UI 组件库和样式规范
2. 轮询间隔设为 1 秒
3. 任务完成或失败时停止轮询
4. 确认弹框需要明确的"取消"和"确定"按钮
5. 进度条需要平滑动画效果
6. 所有 API 调用需要处理错误情况

## 完成定义 (DoD)

- [ ] 所有页面已实现
- [ ] 所有组件已实现
- [ ] 路由配置已完成
- [ ] 导航栏集成已完成
- [ ] 前端测试通过（单元测试 + E2E 测试）
- [ ] 验收标准全部满足
- [ ] 代码已提交并通过 Code Review
