<template>
  <div class="workbench-page">
    <header class="workbench-header">
      <div>
        <h2>回测工作台</h2>
        <p>按流程完成策略创建、编辑、回测配置与结果分析。</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="fetchStrategyList()" :disabled="loadingStrategyList">
          {{ loadingStrategyList ? '刷新中...' : '刷新策略' }}
        </button>
        <button class="btn btn-secondary" @click="toggleHistoryPanel">
          {{ showHistoryPanel ? '隐藏历史' : '显示历史' }}
        </button>
      </div>
    </header>

    <div class="stepper-wrap">
      <button
        v-for="item in stepItems"
        :key="`step-${item.step}`"
        class="step-chip"
        :class="{ active: activeStep === item.step, done: item.step < activeStep }"
        @click="goStep(item.step)"
      >
        <span class="num">{{ item.step }}</span>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <div class="workbench-grid">
      <aside class="strategy-rail">
        <div class="panel-title">策略管理</div>
        <div class="field-row">
          <label for="strategy-search">筛选</label>
          <input
            id="strategy-search"
            v-model.trim="strategyKeyword"
            class="text-input"
            type="text"
            placeholder="输入策略 ID"
          >
        </div>

        <div class="create-box">
          <div class="field-row">
            <label for="new-id">新策略 ID</label>
            <input id="new-id" v-model.trim="createForm.id" class="text-input" type="text" placeholder="例如: alpha_demo_1">
          </div>
          <div class="field-row">
            <label for="template-key">模板</label>
            <select id="template-key" v-model="createForm.template" class="text-input">
              <option v-for="tpl in templateOptions" :key="`tpl-${tpl.key}`" :value="tpl.key">
                {{ tpl.label }}
              </option>
            </select>
          </div>
          <button class="btn btn-primary" @click="handleCreateStrategy" :disabled="strategySaving || !createForm.id">
            创建策略
          </button>
        </div>

        <div class="list-wrap">
          <div
            v-for="row in filteredStrategyRows"
            :key="`strategy-row-${row.id}`"
            class="strategy-row"
            :class="{ active: row.id === currentStrategyId }"
            @click="handleSwitchStrategy(row.id)"
          >
            <div class="row-top">
              <span class="mono">{{ row.id }}</span>
              <span class="size">{{ formatCodeSize(row.size) }}</span>
            </div>
            <div class="row-meta">更新：{{ formatMetaDate(row.updated_at) }}</div>
          </div>

          <div v-if="!filteredStrategyRows.length" class="empty-cell">暂无匹配策略</div>
        </div>

        <div class="rail-actions">
          <button class="btn btn-secondary" @click="handleLoadStrategy" :disabled="loadingStrategyDetail || !currentStrategyId">
            {{ loadingStrategyDetail ? '加载中...' : '重新加载' }}
          </button>
          <button class="btn btn-primary" @click="handleSaveStrategy" :disabled="!canSaveStrategy">
            {{ strategySaving ? '保存中...' : (isExistingStrategy ? '更新策略' : '创建策略') }}
          </button>
          <button class="btn btn-danger" @click="handleDeleteStrategy" :disabled="!canDeleteStrategy">
            {{ strategyDeleting ? '删除中...' : '删除策略' }}
          </button>
        </div>
      </aside>

      <section class="main-panel">
        <div class="panel-head">
          <div>
            <h3>{{ stepTitle }}</h3>
            <p>
              当前策略：<strong class="mono">{{ currentStrategyId || '-' }}</strong>
              <span v-if="isDirty" class="dirty-flag">未保存</span>
            </p>
          </div>
          <div class="meta-line">
            <span>创建：{{ formatMetaDate(currentStrategyMeta.created_at) }}</span>
            <span>更新：{{ formatMetaDate(currentStrategyMeta.updated_at) }}</span>
            <span>长度：{{ formatCodeSize(currentStrategyMeta.size) }}</span>
          </div>
        </div>

        <div v-if="activeStep === 1" class="step-panel">
          <h4>创建策略</h4>
          <p class="hint">输入新策略 ID 并选择模板，创建后自动进入编辑步骤。</p>
          <div class="form-grid two-col">
            <div class="field-row">
              <label for="create-id-main">策略 ID</label>
              <input id="create-id-main" v-model.trim="createForm.id" class="text-input" type="text" placeholder="策略 ID 仅支持字母/数字/_/-">
            </div>
            <div class="field-row">
              <label for="create-template-main">模板</label>
              <select id="create-template-main" v-model="createForm.template" class="text-input">
                <option v-for="tpl in templateOptions" :key="`main-tpl-${tpl.key}`" :value="tpl.key">{{ tpl.label }}</option>
              </select>
            </div>
          </div>
          <div class="actions-row">
            <button class="btn btn-primary" @click="handleCreateStrategy" :disabled="strategySaving || !createForm.id">创建并进入编辑</button>
            <button class="btn btn-secondary" @click="goStep(2)" :disabled="!currentStrategyId">直接去编辑</button>
          </div>
          <div class="preview-code">
            <div class="preview-head">模板预览</div>
            <pre>{{ selectedTemplateCode }}</pre>
          </div>
        </div>

        <div v-else-if="activeStep === 2" class="step-panel">
          <h4>编辑策略</h4>
          <p class="hint">建议每次修改后保存，再进入正式回测。</p>
          <div class="actions-row">
            <button class="btn btn-secondary" @click="handleLoadStrategy" :disabled="loadingStrategyDetail || !currentStrategyId">
              {{ loadingStrategyDetail ? '加载中...' : '从后端重新加载' }}
            </button>
            <button class="btn btn-primary" @click="handleSaveStrategy" :disabled="!canSaveStrategy">
              {{ strategySaving ? '保存中...' : '保存策略' }}
            </button>
            <button class="btn btn-secondary" @click="goStep(3)" :disabled="!currentStrategyId">下一步：回测配置</button>
          </div>
          <PythonCodeEditor v-model="strategyCode" :min-height="460" />
          <p v-if="lastSavedAt" class="hint">最近保存时间：{{ lastSavedAt }}</p>
        </div>

        <div v-else-if="activeStep === 3" class="step-panel">
          <h4>回测配置</h4>
          <p class="hint">设置正式回测参数并提交任务。</p>
          <div class="form-grid three-col">
            <div class="field-row">
              <label for="run-start">开始日期</label>
              <input id="run-start" v-model="runConfig.start_date" type="date" class="text-input">
            </div>
            <div class="field-row">
              <label for="run-end">结束日期</label>
              <input id="run-end" v-model="runConfig.end_date" type="date" class="text-input">
            </div>
            <div class="field-row">
              <label for="run-cash">初始资金</label>
              <input id="run-cash" v-model.number="runConfig.cash" type="number" min="0" class="text-input">
            </div>
          </div>
          <div class="form-grid two-col">
            <div class="field-row">
              <label for="run-benchmark">基准</label>
              <input id="run-benchmark" v-model.trim="runConfig.benchmark" type="text" class="text-input">
            </div>
            <div class="field-row">
              <label for="run-frequency">频率</label>
              <select id="run-frequency" v-model="runConfig.frequency" class="text-input">
                <option value="1d">1d</option>
              </select>
            </div>
          </div>
          <div class="actions-row">
            <button class="btn btn-secondary" @click="setRunPresetDays(30)">近1个月</button>
            <button class="btn btn-secondary" @click="setRunPresetDays(90)">近3个月</button>
            <button class="btn btn-secondary" @click="setRunPresetYTD">今年以来</button>
            <button class="btn btn-primary" :disabled="startingRun || !currentStrategyId" @click="handleStartRun">
              {{ startingRun ? '提交中...' : '开始正式回测' }}
            </button>
            <button class="btn btn-secondary" @click="goStep(4)" :disabled="!runJob.id">查看结果</button>
          </div>

          <div class="job-box" v-if="runJob.id">
            <div class="job-row"><span>正式任务：</span><strong class="mono">{{ runJob.id }}</strong></div>
            <div class="job-row"><span>状态：</span><span class="status-tag" :class="statusClass(runJob.status)">{{ runJob.status || '-' }}</span></div>
            <div class="job-row" v-if="runJob.error"><span>错误：</span><span class="error-text">{{ runJob.error }}</span></div>
          </div>
        </div>

        <div v-else-if="activeStep === 4" class="step-panel">
          <h4>回测结果</h4>
          <p class="hint">可查看当前任务结果，或在右侧历史中切换旧任务。</p>
          <div class="result-status-card">
            <div class="result-status-row">
              <span class="status-label">正式回测状态</span>
              <span class="status-tag status-tag-lg" :class="runStatusClass">{{ runStatusDisplay }}</span>
              <span v-if="runJob.id" class="mono">job_id: {{ runJob.id }}</span>
              <button class="btn btn-secondary btn-mini" @click="pollJobStatus" :disabled="!runJob.id || pollingRequesting">
                {{ pollingRequesting ? '刷新中...' : '刷新状态' }}
              </button>
            </div>
            <p class="hint">{{ runStatusHint }}</p>
          </div>
          <div class="actions-row">
            <button class="btn btn-secondary" @click="handleLoadResult(runJob.id, 'run')" :disabled="runJob.status !== 'FINISHED'">加载正式结果</button>
            <button class="btn btn-secondary" @click="handleLoadJobLog(selectedResultJobId || runJob.id)" :disabled="!(selectedResultJobId || runJob.id)">加载日志</button>
          </div>

          <div class="result-top" v-if="selectedResultJobId">
            <span>当前结果来源：{{ selectedResultSource || '-' }}</span>
            <span>job_id：<strong class="mono">{{ selectedResultJobId }}</strong></span>
            <span v-if="selectedResultStatus">
              状态：
              <span class="status-tag" :class="statusClass(selectedResultStatus)">{{ selectedResultStatus }}</span>
            </span>
          </div>

          <p v-if="resultLoading" class="hint">结果加载中...</p>
          <p v-else-if="resultError" class="error-text">{{ resultError }}</p>

          <template v-else-if="resultData">
            <div class="summary-grid" v-if="summaryItems.length">
              <div class="summary-card" v-for="item in summaryItems" :key="item.key">
                <div class="summary-key">{{ item.label }}</div>
                <div class="summary-value">{{ item.value }}</div>
              </div>
            </div>

            <div class="chart-box" v-if="hasEquityData">
              <div class="sub-title">净值曲线（策略 / 基准）</div>
              <div class="equity-canvas-wrap">
                <canvas ref="equityChart" class="equity-canvas"></canvas>
              </div>
            </div>

            <div class="table-wrap" v-if="tradeColumns.length">
              <div class="sub-title">交易明细（前 200 条）</div>
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in tradeColumns" :key="`trade-col-${col}`">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in tradeRows" :key="`trade-row-${idx}`">
                    <td v-for="col in tradeColumns" :key="`trade-${idx}-${col}`">{{ formatCellValue(row[col]) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <div class="log-box" v-if="jobLog">
            <div class="sub-title">任务日志</div>
            <pre>{{ jobLog }}</pre>
          </div>
        </div>
      </section>

      <aside class="history-panel" v-if="showHistoryPanel">
        <div class="panel-title-row">
          <span>回测历史</span>
          <button class="btn btn-secondary btn-mini" @click="fetchHistoryJobs" :disabled="historyLoading || !currentStrategyId">
            {{ historyLoading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div class="field-row">
          <label for="history-status">状态筛选</label>
          <select id="history-status" v-model="historyStatusFilter" class="text-input" @change="fetchHistoryJobs">
            <option value="">全部</option>
            <option value="QUEUED">QUEUED</option>
            <option value="RUNNING">RUNNING</option>
            <option value="FAILED">FAILED</option>
            <option value="CANCELLED">CANCELLED</option>
            <option value="FINISHED">FINISHED</option>
          </select>
        </div>

        <div class="history-list">
          <div
            v-for="job in historyJobs"
            :key="`history-${job.job_id}`"
            class="history-item"
            :class="{ active: selectedHistoryJobId === job.job_id }"
            @click="handleSelectHistoryJob(job)"
          >
            <div class="item-top">
              <span class="mono">{{ job.job_id }}</span>
              <span class="status-tag" :class="statusClass(job.status)">{{ job.status }}</span>
            </div>
            <div class="item-meta">{{ formatMetaDate(job.updated_at) }}</div>
            <div class="item-actions">
              <button class="btn btn-secondary btn-mini" @click.stop="handleApplyHistoryParams(job)">恢复参数</button>
              <button class="btn btn-secondary btn-mini" @click.stop="handleLoadResult(job.job_id, 'history')" :disabled="job.status !== 'FINISHED'">查看结果</button>
            </div>
          </div>

          <div v-if="!historyJobs.length" class="empty-cell">暂无历史任务</div>
        </div>
      </aside>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast" :class="toastType">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="confirmDialog.visible" class="modal-mask" @click.self="closeConfirmDialog(false)">
        <div class="confirm-modal-card" :class="{ danger: confirmDialog.danger }">
          <div class="confirm-modal-head">{{ confirmDialog.title }}</div>
          <div class="confirm-modal-body">{{ confirmDialog.message }}</div>
          <div class="confirm-modal-actions">
            <button class="btn btn-secondary" @click="closeConfirmDialog(false)">{{ confirmDialog.cancelText }}</button>
            <button class="btn" :class="confirmDialog.danger ? 'btn-danger' : 'btn-primary'" @click="closeConfirmDialog(true)">{{ confirmDialog.confirmText }}</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import Chart from 'chart.js/auto';
import PythonCodeEditor from '@/components/PythonCodeEditor.vue';
import {
  listStrategies,
  getStrategy,
  saveStrategy,
  deleteStrategy,
  runBacktest,
  getJob,
  getResult,
  getLog,
  listStrategyJobs
} from '@/api/backtest';
import {
  getLocalStrategyIds,
  mergeLocalStrategyId,
  mergeLocalStrategyIds,
  removeLocalStrategyId
} from '@/utils/backtestStrategies';

const DEFAULT_TEMPLATE = `# 示例策略\ndef init(context):\n    context.s1 = "000001.XSHE"\n\ndef handle_bar(context, bar_dict):\n    pass\n`;
const EMPTY_TEMPLATE = '# 在这里编写你的策略\n';
const MOMENTUM_TEMPLATE = `# 简单动量示例\ndef init(context):\n    context.s1 = "000300.XSHG"\n\ndef handle_bar(context, bar_dict):\n    close = bar_dict[context.s1].close\n    if close is None:\n        return\n`;
const ID_PATTERN = /^[A-Za-z0-9_-]+$/;
const TERMINAL_STATUSES = new Set(['FAILED', 'FINISHED', 'CANCELLED']);

function getTodayDate() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatDate(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return '';
  }
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function addDays(dateStr, days) {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) {
    return dateStr;
  }
  date.setDate(date.getDate() + days);
  return formatDate(date);
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function unwrapDataPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return payload;
  }
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload.data !== undefined && payload.data !== null) {
    return payload.data;
  }
  return payload;
}

function normalizeCodePayload(payload) {
  const data = unwrapDataPayload(payload);
  if (!data) {
    return '';
  }
  if (typeof data === 'string') {
    return data;
  }
  if (typeof data.code === 'string') {
    return data.code;
  }
  if (data.strategy && typeof data.strategy.code === 'string') {
    return data.strategy.code;
  }
  if (data.item && typeof data.item.code === 'string') {
    return data.item.code;
  }
  return '';
}

function normalizeStrategyMeta(item) {
  if (typeof item === 'string') {
    const id = item.trim();
    if (!id) {
      return null;
    }
    return {
      id,
      created_at: '',
      updated_at: '',
      size: null
    };
  }
  if (!item || typeof item !== 'object') {
    return null;
  }

  const id = String(item.id || item.strategy_id || item.name || '').trim();
  if (!id) {
    return null;
  }

  return {
    id,
    created_at: item.created_at || item.create_time || item.ctime || '',
    updated_at: item.updated_at || item.update_time || item.mtime || '',
    size: toNumberOrNull(item.size ?? item.code_size ?? item.bytes)
  };
}

function normalizeStrategyList(payload) {
  const data = unwrapDataPayload(payload);
  const source = Array.isArray(data)
    ? data
    : (Array.isArray(data?.strategies)
      ? data.strategies
      : (Array.isArray(data?.items) ? data.items : []));

  const dedup = new Map();
  source
    .map(normalizeStrategyMeta)
    .filter(Boolean)
    .forEach((item) => {
      dedup.set(item.id, item);
    });

  return Array.from(dedup.values());
}

function normalizeStatus(value) {
  const status = String(value || 'QUEUED').toUpperCase();
  if (status === 'RUNNING' || status === 'FAILED' || status === 'FINISHED' || status === 'CANCELLED') {
    return status;
  }
  return 'QUEUED';
}

function normalizeHistoryJobs(payload) {
  const data = unwrapDataPayload(payload);
  const list = Array.isArray(data?.jobs) ? data.jobs : [];

  return list.map((item) => {
    const params = item?.params || {};
    return {
      job_id: String(item?.job_id || ''),
      strategy_id: String(item?.strategy_id || ''),
      status: normalizeStatus(item?.status),
      error: item?.error || null,
      error_message: item?.error_message || '',
      created_at: item?.created_at || '',
      updated_at: item?.updated_at || '',
      params: {
        start_date: params.start_date || '',
        end_date: params.end_date || '',
        cash: toNumberOrNull(params.cash) || 0,
        benchmark: params.benchmark || '',
        frequency: params.frequency || '1d'
      }
    };
  });
}

function normalizeResultPayload(payload) {
  const data = unwrapDataPayload(payload) || {};
  const summary = data.summary && typeof data.summary === 'object' ? data.summary : {};

  const equityRaw = data.equity && typeof data.equity === 'object' ? data.equity : {};
  const dates = Array.isArray(equityRaw.dates) ? equityRaw.dates : [];
  const nav = Array.isArray(equityRaw.nav) ? equityRaw.nav : [];
  const benchmark = Array.isArray(equityRaw.benchmark_nav)
    ? equityRaw.benchmark_nav
    : (Array.isArray(equityRaw.benchmark) ? equityRaw.benchmark : []);

  const rawColumns = Array.isArray(data.trade_columns)
    ? data.trade_columns
    : (Array.isArray(data.columns) ? data.columns : []);
  const rawTrades = Array.isArray(data.trades) ? data.trades : [];

  const columns = rawColumns.slice(0, 12);
  const rows = rawTrades.slice(0, 200).map((row) => {
    if (Array.isArray(row)) {
      const mapped = {};
      columns.forEach((col, idx) => {
        mapped[col] = row[idx];
      });
      return mapped;
    }
    if (row && typeof row === 'object') {
      return row;
    }
    return { value: row };
  });

  const normalizedColumns = columns.length
    ? columns
    : (rows[0] ? Object.keys(rows[0]).slice(0, 12) : []);

  return {
    summary,
    equity: {
      dates,
      nav,
      benchmark
    },
    trade_columns: normalizedColumns,
    trades: rows
  };
}

function extractLogPayload(payload) {
  const data = unwrapDataPayload(payload);
  if (!data) {
    return '';
  }
  if (typeof data === 'string') {
    return data;
  }
  if (typeof data.log === 'string') {
    return data.log;
  }
  if (typeof data.content === 'string') {
    return data.content;
  }
  return JSON.stringify(data, null, 2);
}

export default {
  name: 'BacktestWorkbench',
  components: {
    PythonCodeEditor
  },
  data() {
    const today = getTodayDate();
    return {
      stepItems: [
        { step: 1, label: '创建策略' },
        { step: 2, label: '编辑策略' },
        { step: 3, label: '回测配置' },
        { step: 4, label: '回测结果' }
      ],
      activeStep: 1,
      strategyKeyword: '',
      strategyOptions: ['demo'],
      strategyMetaMap: {
        demo: {
          id: 'demo',
          created_at: '',
          updated_at: '',
          size: null
        }
      },
      currentStrategyId: 'demo',
      strategyCode: DEFAULT_TEMPLATE,
      suppressDirtyWatch: false,
      isDirty: false,
      lastLoadedAt: '',
      lastSavedAt: '',
      loadingStrategyList: false,
      loadingStrategyDetail: false,
      strategySaving: false,
      strategyDeleting: false,
      createForm: {
        id: '',
        template: 'demo'
      },
      templateOptions: [
        { key: 'demo', label: '示例模板', code: DEFAULT_TEMPLATE },
        { key: 'empty', label: '空白模板', code: EMPTY_TEMPLATE },
        { key: 'momentum', label: '动量模板', code: MOMENTUM_TEMPLATE }
      ],
      runConfig: {
        start_date: '2025-01-01',
        end_date: today,
        cash: 1000000,
        benchmark: '000300.XSHG',
        frequency: '1d'
      },
      startingRun: false,
      runJob: {
        id: '',
        status: '',
        error: ''
      },
      pollingTimer: null,
      pollingRequesting: false,
      selectedResultJobId: '',
      selectedResultSource: '',
      resultLoading: false,
      resultError: '',
      resultData: null,
      jobLog: '',
      logLoading: false,
      historyJobs: [],
      historyLoading: false,
      historyStatusFilter: '',
      selectedHistoryJobId: '',
      showHistoryPanel: true,
      chartInstance: null,
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null,
      confirmDialog: {
        visible: false,
        title: '请确认',
        message: '',
        confirmText: '确认',
        cancelText: '取消',
        danger: false
      },
      confirmResolver: null
    };
  },
  computed: {
    stepTitle() {
      const found = this.stepItems.find((item) => item.step === this.activeStep);
      return found ? found.label : '回测工作台';
    },
    selectedTemplateCode() {
      const found = this.templateOptions.find((item) => item.key === this.createForm.template);
      return found ? found.code : DEFAULT_TEMPLATE;
    },
    filteredStrategyOptions() {
      const keyword = String(this.strategyKeyword || '').trim().toLowerCase();
      if (!keyword) {
        return this.strategyOptions;
      }
      return this.strategyOptions.filter((id) => String(id).toLowerCase().includes(keyword));
    },
    filteredStrategyRows() {
      return this.filteredStrategyOptions.map((id) => this.getStrategyMeta(id));
    },
    currentStrategyMeta() {
      return this.getStrategyMeta(this.currentStrategyId);
    },
    isExistingStrategy() {
      const id = this.normalizeStrategyId(this.currentStrategyId);
      return !!id && this.strategyOptions.includes(id);
    },
    canSaveStrategy() {
      return !!this.currentStrategyId && !this.strategySaving;
    },
    canDeleteStrategy() {
      return !!this.currentStrategyId && this.currentStrategyId !== 'demo' && !this.strategyDeleting;
    },
    runStatusDisplay() {
      if (!this.runJob.id) {
        return '未提交';
      }
      return normalizeStatus(this.runJob.status);
    },
    runStatusClass() {
      if (!this.runJob.id) {
        return 'idle';
      }
      return this.statusClass(this.runJob.status);
    },
    runStatusHint() {
      if (!this.runJob.id) {
        return '还未提交正式回测任务。';
      }
      const status = normalizeStatus(this.runJob.status);
      if (status === 'QUEUED') {
        return '任务排队中，结果暂不可用。';
      }
      if (status === 'RUNNING') {
        return '任务运行中，完成后会自动刷新结果。';
      }
      if (status === 'FAILED') {
        return this.runJob.error || '任务执行失败，请查看日志。';
      }
      if (status === 'CANCELLED') {
        return '任务已取消。';
      }
      return '任务已完成，可加载回测结果。';
    },
    selectedResultStatus() {
      const targetJobId = String(this.selectedResultJobId || '').trim();
      if (!targetJobId) {
        return '';
      }
      if (targetJobId === this.runJob.id) {
        return normalizeStatus(this.runJob.status);
      }
      const found = this.historyJobs.find((item) => item.job_id === targetJobId);
      return found ? normalizeStatus(found.status) : '';
    },
    summaryItems() {
      const summary = this.resultData?.summary || {};
      return Object.keys(summary)
        .slice(0, 12)
        .map((key) => ({
          key,
          label: key,
          value: this.formatMetric(summary[key])
        }));
    },
    tradeColumns() {
      return Array.isArray(this.resultData?.trade_columns) ? this.resultData.trade_columns : [];
    },
    tradeRows() {
      return Array.isArray(this.resultData?.trades) ? this.resultData.trades : [];
    },
    hasEquityData() {
      const equity = this.resultData?.equity || {};
      return Array.isArray(equity.dates) && Array.isArray(equity.nav) && equity.dates.length && equity.nav.length;
    }
  },
  watch: {
    strategyCode() {
      if (this.suppressDirtyWatch) {
        return;
      }
      this.isDirty = true;
    },
    resultData() {
      this.$nextTick(() => {
        this.renderEquityChart();
      });
    }
  },
  methods: {
    normalizeStrategyId(value) {
      return String(value || '').trim();
    },
    askForConfirm(options = {}) {
      if (typeof this.confirmResolver === 'function') {
        this.confirmResolver(false);
        this.confirmResolver = null;
      }

      this.confirmDialog = {
        visible: true,
        title: options.title || '请确认',
        message: options.message || '是否继续执行当前操作？',
        confirmText: options.confirmText || '确认',
        cancelText: options.cancelText || '取消',
        danger: !!options.danger
      };

      return new Promise((resolve) => {
        this.confirmResolver = resolve;
      });
    },
    closeConfirmDialog(confirmed) {
      this.confirmDialog = {
        ...this.confirmDialog,
        visible: false
      };

      if (typeof this.confirmResolver === 'function') {
        this.confirmResolver(Boolean(confirmed));
      }
      this.confirmResolver = null;
    },
    showMessage(message, type = 'success') {
      this.toastType = type;
      this.toastMessage = message;
      this.showToast = true;

      if (this.toastTimer) {
        clearTimeout(this.toastTimer);
      }
      this.toastTimer = setTimeout(() => {
        this.showToast = false;
      }, 2400);
    },
    getErrorMessage(error, fallback) {
      if (error?.response?.data) {
        const data = error.response.data;
        if (typeof data === 'string') {
          return data;
        }
        return data.message || data.error || data.msg || fallback;
      }
      return error?.message || fallback;
    },
    formatMetaDate(value) {
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return String(value);
      }
      return date.toLocaleString('zh-CN');
    },
    formatCodeSize(value) {
      const size = toNumberOrNull(value);
      if (size === null) {
        return '-';
      }
      return `${size} 字符`;
    },
    formatMetric(value) {
      if (value === null || value === undefined || value === '') {
        return '-';
      }
      if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
          return '-';
        }
        return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 });
      }
      if (typeof value === 'object') {
        return JSON.stringify(value);
      }
      return String(value);
    },
    formatCellValue(value) {
      if (value === null || value === undefined || value === '') {
        return '-';
      }
      if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
          return '-';
        }
        return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 });
      }
      if (typeof value === 'object') {
        return JSON.stringify(value);
      }
      return String(value);
    },
    statusClass(status) {
      const normalized = normalizeStatus(status);
      if (normalized === 'FINISHED') {
        return 'ok';
      }
      if (normalized === 'FAILED') {
        return 'error';
      }
      if (normalized === 'CANCELLED') {
        return 'cancelled';
      }
      return 'running';
    },
    getStrategyMeta(id) {
      const strategyId = this.normalizeStrategyId(id);
      if (!strategyId) {
        return {
          id: '',
          created_at: '',
          updated_at: '',
          size: null
        };
      }
      const raw = this.strategyMetaMap[strategyId] || {};
      return {
        id: strategyId,
        created_at: raw.created_at || '',
        updated_at: raw.updated_at || '',
        size: toNumberOrNull(raw.size)
      };
    },
    setStrategyMetadata(metaList = [], allIds = this.strategyOptions) {
      const nextMap = {};
      (allIds || []).forEach((id) => {
        const strategyId = this.normalizeStrategyId(id);
        if (!strategyId) {
          return;
        }
        nextMap[strategyId] = {
          id: strategyId,
          created_at: '',
          updated_at: '',
          size: null
        };
      });

      (metaList || []).forEach((item) => {
        if (!item?.id) {
          return;
        }
        const strategyId = this.normalizeStrategyId(item.id);
        nextMap[strategyId] = {
          ...nextMap[strategyId],
          ...item,
          id: strategyId,
          size: toNumberOrNull(item.size)
        };
      });

      this.strategyMetaMap = nextMap;
    },
    upsertStrategyMeta(meta) {
      if (!meta?.id) {
        return;
      }
      const strategyId = this.normalizeStrategyId(meta.id);
      const previous = this.strategyMetaMap[strategyId] || {
        id: strategyId,
        created_at: '',
        updated_at: '',
        size: null
      };
      this.strategyMetaMap = {
        ...this.strategyMetaMap,
        [strategyId]: {
          ...previous,
          ...meta,
          id: strategyId,
          size: toNumberOrNull(meta.size ?? previous.size)
        }
      };
    },
    removeStrategyMeta(id) {
      const strategyId = this.normalizeStrategyId(id);
      if (!strategyId || !this.strategyMetaMap[strategyId]) {
        return;
      }
      const next = { ...this.strategyMetaMap };
      delete next[strategyId];
      this.strategyMetaMap = next;
    },
    toggleHistoryPanel() {
      this.showHistoryPanel = !this.showHistoryPanel;
    },
    async fetchStrategyList(silent = false) {
      this.loadingStrategyList = true;
      try {
        const data = await listStrategies();
        const fromApi = normalizeStrategyList(data);
        const ids = fromApi.map((item) => item.id);
        const merged = Array.from(new Set(['demo', ...ids, ...getLocalStrategyIds()]));

        this.strategyOptions = merged;
        this.setStrategyMetadata(fromApi, merged);
        mergeLocalStrategyIds(merged);

        if (!merged.includes(this.currentStrategyId)) {
          this.currentStrategyId = merged[0] || '';
        }
      } catch (error) {
        const fallback = Array.from(new Set(['demo', ...getLocalStrategyIds()]));
        this.strategyOptions = fallback;
        this.setStrategyMetadata([], fallback);
        if (!fallback.includes(this.currentStrategyId)) {
          this.currentStrategyId = fallback[0] || '';
        }

        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '策略列表加载失败，已使用本地缓存'), 'error');
        }
      } finally {
        this.loadingStrategyList = false;
      }
    },
    async ensureSavedBeforeRun() {
      if (!this.isDirty) {
        return true;
      }

      const shouldSave = await this.askForConfirm({
        title: '保存提示',
        message: '当前策略有未保存修改，是否先保存后继续？',
        confirmText: '保存并继续'
      });
      if (!shouldSave) {
        return false;
      }

      await this.handleSaveStrategy(true);
      return !this.isDirty;
    },
    async handleSwitchStrategy(id) {
      const strategyId = this.normalizeStrategyId(id);
      if (!strategyId || strategyId === this.currentStrategyId) {
        return;
      }

      if (this.isDirty) {
        const confirmed = await this.askForConfirm({
          title: '切换策略确认',
          message: '当前策略有未保存修改，切换后将保留本地编辑内容但不会自动保存。是否继续切换？',
          confirmText: '继续切换'
        });
        if (!confirmed) {
          return;
        }
      }

      this.currentStrategyId = strategyId;
      await Promise.all([
        this.handleLoadStrategy(true),
        this.fetchHistoryJobs(true)
      ]);
    },
    async handleLoadStrategy(silent = false) {
      const strategyId = this.normalizeStrategyId(this.currentStrategyId);
      if (!strategyId) {
        this.showMessage('请先选择策略', 'error');
        return;
      }

      this.loadingStrategyDetail = true;
      try {
        const data = await getStrategy(strategyId);
        const code = normalizeCodePayload(data) || DEFAULT_TEMPLATE;

        this.suppressDirtyWatch = true;
        this.strategyCode = code;
        this.suppressDirtyWatch = false;
        this.isDirty = false;

        this.lastLoadedAt = new Date().toLocaleString('zh-CN');

        const payload = unwrapDataPayload(data);
        const meta = normalizeStrategyMeta(payload?.strategy || payload?.item || payload);
        const nowIso = new Date().toISOString();
        const prev = this.getStrategyMeta(strategyId);
        this.upsertStrategyMeta({
          id: strategyId,
          created_at: meta?.created_at || prev.created_at || nowIso,
          updated_at: meta?.updated_at || nowIso,
          size: meta?.size ?? code.length
        });

        mergeLocalStrategyId(strategyId);
        if (!this.strategyOptions.includes(strategyId)) {
          this.strategyOptions = Array.from(new Set([...this.strategyOptions, strategyId]));
        }

        if (!silent) {
          this.showMessage('策略加载成功');
        }
      } catch (error) {
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '策略加载失败'), 'error');
        }
      } finally {
        this.loadingStrategyDetail = false;
        this.suppressDirtyWatch = false;
      }
    },
    async handleSaveStrategy(silent = false) {
      const strategyId = this.normalizeStrategyId(this.currentStrategyId);
      if (!strategyId) {
        this.showMessage('请先填写策略 ID', 'error');
        return;
      }

      this.strategySaving = true;
      try {
        await saveStrategy(strategyId, this.strategyCode || '');
        const nowIso = new Date().toISOString();
        const prev = this.getStrategyMeta(strategyId);

        this.upsertStrategyMeta({
          id: strategyId,
          created_at: prev.created_at || nowIso,
          updated_at: nowIso,
          size: (this.strategyCode || '').length
        });

        mergeLocalStrategyId(strategyId);
        if (!this.strategyOptions.includes(strategyId)) {
          this.strategyOptions = Array.from(new Set([...this.strategyOptions, strategyId]));
        }

        this.isDirty = false;
        this.lastSavedAt = new Date().toLocaleString('zh-CN');
        if (!silent) {
          this.showMessage('策略保存成功');
        }
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '策略保存失败'), 'error');
      } finally {
        this.strategySaving = false;
      }
    },
    async handleCreateStrategy() {
      const strategyId = this.normalizeStrategyId(this.createForm.id);
      if (!strategyId) {
        this.showMessage('请输入策略 ID', 'error');
        return;
      }
      if (!ID_PATTERN.test(strategyId)) {
        this.showMessage('策略 ID 仅支持字母、数字、下划线和中划线', 'error');
        return;
      }
      if (this.strategyOptions.includes(strategyId)) {
        this.showMessage('策略 ID 已存在，请更换', 'error');
        return;
      }

      const templateCode = this.selectedTemplateCode || DEFAULT_TEMPLATE;

      this.strategySaving = true;
      try {
        await saveStrategy(strategyId, templateCode);

        this.currentStrategyId = strategyId;
        this.suppressDirtyWatch = true;
        this.strategyCode = templateCode;
        this.suppressDirtyWatch = false;
        this.isDirty = false;

        const nowIso = new Date().toISOString();
        this.upsertStrategyMeta({
          id: strategyId,
          created_at: nowIso,
          updated_at: nowIso,
          size: templateCode.length
        });

        if (!this.strategyOptions.includes(strategyId)) {
          this.strategyOptions = Array.from(new Set([...this.strategyOptions, strategyId]));
        }

        mergeLocalStrategyId(strategyId);
        this.createForm.id = '';
        this.activeStep = 2;

        await this.fetchHistoryJobs(true);
        this.showMessage(`策略 ${strategyId} 创建成功`);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '策略创建失败'), 'error');
      } finally {
        this.strategySaving = false;
      }
    },
    async handleDeleteStrategy() {
      const strategyId = this.normalizeStrategyId(this.currentStrategyId);
      if (!strategyId) {
        return;
      }
      if (strategyId === 'demo') {
        this.showMessage('demo 为内置策略，不允许删除', 'error');
        return;
      }

      const confirmed = await this.askForConfirm({
        title: '删除策略',
        message: `确认删除策略 ${strategyId} 吗？删除后无法恢复。`,
        confirmText: '确认删除',
        danger: true
      });
      if (!confirmed) {
        return;
      }

      this.strategyDeleting = true;
      try {
        await deleteStrategy(strategyId);
        removeLocalStrategyId(strategyId);

        this.strategyOptions = this.strategyOptions.filter((id) => id !== strategyId);
        this.removeStrategyMeta(strategyId);

        if (!this.strategyOptions.length) {
          this.strategyOptions = ['demo'];
          this.upsertStrategyMeta({ id: 'demo' });
        }

        this.currentStrategyId = this.strategyOptions[0] || 'demo';
        await this.handleLoadStrategy(true);
        await this.fetchHistoryJobs(true);

        this.showMessage('策略删除成功');
      } catch (error) {
        const status = error?.response?.status;
        if (status === 404 || status === 405 || status === 501) {
          this.showMessage('后端暂未提供删除接口，请实现 DELETE /api/backtest/strategies/{id}', 'error');
        } else {
          this.showMessage(this.getErrorMessage(error, '策略删除失败'), 'error');
        }
      } finally {
        this.strategyDeleting = false;
      }
    },
    goStep(step) {
      const target = Number(step);
      if (!Number.isFinite(target) || target < 1 || target > 4) {
        return;
      }
      this.activeStep = target;
    },
    setRunPresetDays(days) {
      const today = getTodayDate();
      this.runConfig.end_date = today;
      this.runConfig.start_date = addDays(today, -Math.max(1, Number(days)) + 1);
    },
    setRunPresetYTD() {
      const today = getTodayDate();
      const year = new Date(today).getFullYear();
      this.runConfig.start_date = `${year}-01-01`;
      this.runConfig.end_date = today;
    },
    validateConfig(config) {
      if (!config.start_date || !config.end_date) {
        this.showMessage('开始日期和结束日期不能为空', 'error');
        return false;
      }
      if (config.start_date > config.end_date) {
        this.showMessage('开始日期不能晚于结束日期', 'error');
        return false;
      }
      if (!this.currentStrategyId) {
        this.showMessage('请先选择策略', 'error');
        return false;
      }
      if (!Number.isFinite(Number(config.cash)) || Number(config.cash) <= 0) {
        this.showMessage('初始资金必须大于 0', 'error');
        return false;
      }
      return true;
    },
    async handleStartRun() {
      if (!this.validateConfig(this.runConfig)) {
        return;
      }

      const ready = await this.ensureSavedBeforeRun();
      if (!ready) {
        return;
      }

      this.startingRun = true;
      try {
        const payload = {
          strategy_id: this.currentStrategyId,
          start_date: this.runConfig.start_date,
          end_date: this.runConfig.end_date,
          cash: Number(this.runConfig.cash),
          benchmark: this.runConfig.benchmark,
          frequency: this.runConfig.frequency
        };

        const data = await runBacktest(payload);
        const jobId = data?.job_id || data?.jobId;
        if (!jobId) {
          throw new Error('回测任务返回缺少 job_id');
        }

        this.runJob = {
          id: String(jobId),
          status: 'QUEUED',
          error: ''
        };
        this.selectedResultJobId = '';
        this.selectedResultSource = '';
        this.resultError = '';
        this.resultData = null;
        this.jobLog = '';

        this.startPolling();
        this.goStep(4);
        this.showMessage(`正式回测任务已提交（${jobId}）`);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '正式回测任务提交失败'), 'error');
      } finally {
        this.startingRun = false;
      }
    },
    startPolling() {
      if (this.pollingTimer) {
        return;
      }
      this.pollJobStatus();
      this.pollingTimer = setInterval(() => {
        this.pollJobStatus();
      }, 2000);
    },
    stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer);
        this.pollingTimer = null;
      }
      this.pollingRequesting = false;
    },
    async pollJobStatus() {
      if (this.pollingRequesting) {
        return;
      }

      const active = [];
      if (this.runJob.id && !TERMINAL_STATUSES.has(normalizeStatus(this.runJob.status))) {
        active.push(this.runJob.id);
      }

      if (!active.length) {
        this.stopPolling();
        return;
      }

      this.pollingRequesting = true;
      try {
        const settled = await Promise.all(
          active.map((jobId) => getJob(jobId)
            .then((data) => ({ ok: true, data }))
            .catch(() => ({ ok: false })))
        );

        let shouldRefreshHistory = false;

        settled.forEach((resp) => {
          if (!resp.ok) {
            return;
          }

          const status = normalizeStatus(resp.data?.status);
          const errorText = this.getErrorMessage({ response: { data: resp.data?.error || { message: resp.data?.error_message } } }, '');

          const prev = normalizeStatus(this.runJob.status);
          this.runJob = {
            ...this.runJob,
            status,
            error: status === 'FAILED' ? (errorText || this.runJob.error || '正式回测失败') : ''
          };
          if (prev !== status) {
            shouldRefreshHistory = true;
          }
          if (status === 'FINISHED') {
            this.handleLoadResult(this.runJob.id, 'run', true);
          }
        });

        if (shouldRefreshHistory) {
          this.fetchHistoryJobs(true);
        }
      } finally {
        this.pollingRequesting = false;
      }
    },
    async handleLoadResult(jobId, source = 'manual', silent = false) {
      const targetJobId = String(jobId || '').trim();
      if (!targetJobId) {
        return;
      }

      this.resultLoading = true;
      this.resultError = '';
      try {
        const data = await getResult(targetJobId, { page: 1, page_size: 200 });
        this.resultData = normalizeResultPayload(data);
        this.selectedResultJobId = targetJobId;
        this.selectedResultSource = source;
        this.activeStep = 4;

        if (!silent) {
          this.showMessage('结果加载成功');
        }
      } catch (error) {
        const isNotReady = error?.response?.status === 409;
        this.resultData = null;
        this.resultError = isNotReady
          ? '结果未就绪，请稍后重试。'
          : this.getErrorMessage(error, '结果加载失败');

        if (!silent) {
          this.showMessage(this.resultError, 'error');
        }
      } finally {
        this.resultLoading = false;
      }
    },
    async handleLoadJobLog(jobId) {
      const targetJobId = String(jobId || '').trim();
      if (!targetJobId) {
        this.showMessage('没有可查看日志的任务', 'error');
        return;
      }

      this.logLoading = true;
      try {
        const data = await getLog(targetJobId);
        this.jobLog = extractLogPayload(data);
        if (!this.jobLog) {
          this.jobLog = '暂无日志';
        }
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '日志加载失败'), 'error');
      } finally {
        this.logLoading = false;
      }
    },
    async fetchHistoryJobs(silent = false) {
      if (!this.currentStrategyId) {
        return;
      }

      this.historyLoading = true;
      try {
        const params = {
          limit: 20,
          offset: 0
        };
        if (this.historyStatusFilter) {
          params.status = this.historyStatusFilter;
        }

        const data = await listStrategyJobs(this.currentStrategyId, params);
        const list = normalizeHistoryJobs(data)
          .filter((item) => item.job_id)
          .sort((a, b) => {
            const ta = new Date(a.updated_at || a.created_at || 0).getTime();
            const tb = new Date(b.updated_at || b.created_at || 0).getTime();
            return tb - ta;
          });

        this.historyJobs = list;

        if (this.selectedHistoryJobId && !list.find((item) => item.job_id === this.selectedHistoryJobId)) {
          this.selectedHistoryJobId = '';
        }
      } catch (error) {
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '历史任务加载失败'), 'error');
        }
      } finally {
        this.historyLoading = false;
      }
    },
    async handleSelectHistoryJob(job) {
      if (!job || !job.job_id) {
        return;
      }

      this.selectedHistoryJobId = job.job_id;
      if (job.status === 'FINISHED') {
        await this.handleLoadResult(job.job_id, 'history');
      } else {
        this.selectedResultJobId = job.job_id;
        this.selectedResultSource = 'history';
        this.resultData = null;
        this.resultError = `任务状态为 ${job.status}，结果暂不可用。`;
        this.goStep(4);
      }
    },
    handleApplyHistoryParams(job) {
      if (!job?.params) {
        return;
      }

      this.runConfig = {
        start_date: job.params.start_date || this.runConfig.start_date,
        end_date: job.params.end_date || this.runConfig.end_date,
        cash: toNumberOrNull(job.params.cash) || this.runConfig.cash,
        benchmark: job.params.benchmark || this.runConfig.benchmark,
        frequency: job.params.frequency || this.runConfig.frequency
      };

      this.goStep(3);
      this.showMessage('已恢复历史任务参数，可直接重新回测');
    },
    renderEquityChart() {
      if (!this.$refs.equityChart || !this.hasEquityData) {
        if (this.chartInstance) {
          this.chartInstance.destroy();
          this.chartInstance = null;
        }
        return;
      }

      const canvas = this.$refs.equityChart;
      const dates = this.resultData.equity.dates || [];
      const nav = dates.map((_, idx) => toNumberOrNull(this.resultData.equity.nav?.[idx]));
      const benchmark = dates.map((_, idx) => toNumberOrNull(this.resultData.equity.benchmark?.[idx]));
      const finiteSeries = [...nav, ...benchmark].filter((item) => Number.isFinite(item));

      let yAxisMin;
      let yAxisMax;
      if (finiteSeries.length) {
        const minValue = Math.min(...finiteSeries);
        const maxValue = Math.max(...finiteSeries);
        if (maxValue === minValue) {
          const delta = Math.max(Math.abs(maxValue) * 0.02, 0.01);
          yAxisMin = minValue - delta;
          yAxisMax = maxValue + delta;
        } else if (minValue >= 0.8 && maxValue <= 1.2) {
          yAxisMin = 0.8;
          yAxisMax = 1.2;
        } else {
          const padding = Math.max((maxValue - minValue) * 0.18, 0.01);
          yAxisMin = minValue - padding;
          yAxisMax = maxValue + padding;
        }
      }

      if (this.chartInstance) {
        this.chartInstance.destroy();
        this.chartInstance = null;
      }

      this.chartInstance = new Chart(canvas, {
        type: 'line',
        data: {
          labels: dates,
          datasets: [
            {
              label: '策略净值',
              data: nav,
              borderColor: '#409eff',
              backgroundColor: 'rgba(64, 158, 255, 0.08)',
              borderWidth: 2.2,
              pointRadius: 0,
              pointHoverRadius: 3,
              tension: 0.25,
              spanGaps: true
            },
            {
              label: '基准净值',
              data: benchmark,
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245, 158, 11, 0.08)',
              borderWidth: 2.2,
              pointRadius: 0,
              pointHoverRadius: 3,
              tension: 0.25,
              spanGaps: true,
              borderDash: [6, 4]
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          layout: {
            padding: {
              top: 6,
              right: 6,
              left: 6
            }
          },
          interaction: {
            mode: 'index',
            intersect: false
          },
          plugins: {
            legend: {
              position: 'top',
              align: 'start'
            },
            tooltip: {
              callbacks: {
                label: (context) => {
                  const val = context.parsed.y;
                  const valueText = Number.isFinite(val)
                    ? Number(val).toFixed(4).replace(/\.?0+$/, '')
                    : '-';
                  if (context.dataset?.label === '基准净值') {
                    return `基准净值: ${valueText}`;
                  }
                  return `策略净值: ${valueText}`;
                }
              }
            }
          },
          scales: {
            x: {
              ticks: {
                maxTicksLimit: 8
              }
            },
            y: {
              min: yAxisMin,
              max: yAxisMax
            }
          }
        }
      });
    }
  },
  async mounted() {
    await this.fetchStrategyList(true);

    if (this.$route.query?.strategy_id) {
      this.currentStrategyId = String(this.$route.query.strategy_id);
    }

    if (!this.currentStrategyId && this.strategyOptions.length) {
      this.currentStrategyId = this.strategyOptions[0];
    }

    if (this.currentStrategyId) {
      await Promise.all([
        this.handleLoadStrategy(true),
        this.fetchHistoryJobs(true)
      ]);
    }
  },
  beforeUnmount() {
    this.stopPolling();
    if (typeof this.confirmResolver === 'function') {
      this.confirmResolver(false);
      this.confirmResolver = null;
    }
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }
  }
};
</script>

<style scoped>
.workbench-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workbench-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e7edf5;
  border-radius: 2px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.workbench-header h2 {
  margin: 0;
  font-size: 22px;
  color: #303133;
}

.workbench-header p {
  margin: 6px 0 0;
  font-size: 14px;
  color: #606266;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stepper-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.step-chip {
  border: 1px solid #dcdfe6;
  border-radius: 2px;
  background: #fff;
  color: #606266;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
}

.step-chip .num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  background: #f2f6fc;
}

.step-chip.active {
  color: #fff;
  background: #409eff;
  border-color: #409eff;
}

.step-chip.active .num {
  color: #409eff;
  background: #fff;
}

.step-chip.done {
  border-color: #67c23a;
  color: #67c23a;
}

.workbench-grid {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 320px;
  gap: 12px;
  align-items: start;
}

.strategy-rail,
.main-panel,
.history-panel {
  border: 1px solid #e7edf5;
  border-radius: 2px;
  background: #fff;
  padding: 12px;
  min-height: 620px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 8px;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.field-row label {
  color: #606266;
  font-size: 13px;
}

.text-input {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}

.text-input:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
}

.create-box {
  padding: 10px;
  border: 1px solid #edf2f8;
  border-radius: 2px;
  background: #f9fbff;
}

.list-wrap,
.history-list {
  margin-top: 10px;
  max-height: 420px;
  overflow: auto;
  border: 1px solid #edf2f8;
  border-radius: 8px;
}

.strategy-row,
.history-item {
  border-bottom: 1px solid #edf2f8;
  padding: 10px;
  cursor: pointer;
}

.strategy-row:last-child,
.history-item:last-child {
  border-bottom: none;
}

.strategy-row:hover,
.history-item:hover {
  background: #f7faff;
}

.strategy-row.active,
.history-item.active {
  background: #edf5ff;
}

.row-top,
.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.row-meta,
.item-meta {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}

.size {
  color: #909399;
  font-size: 12px;
}

.rail-actions {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.rail-actions .btn {
  width: 100%;
  padding: 8px 6px;
  font-size: 12px;
  white-space: nowrap;
}

.main-panel {
  display: flex;
  flex-direction: column;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #edf2f8;
  padding-bottom: 10px;
}

.panel-head h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.panel-head p {
  margin: 6px 0 0;
  color: #606266;
}

.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #909399;
  font-size: 12px;
}

.dirty-flag {
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  color: #e6a23c;
  background: #fdf6ec;
  border: 1px solid #faecd8;
}

.step-panel {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-panel h4 {
  margin: 0;
  font-size: 16px;
}

.hint {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.form-grid {
  display: grid;
  gap: 10px;
}

.form-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid.three-col {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.actions-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn {
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-primary {
  color: #fff;
  background: #409eff;
}

.btn-primary:hover:not(:disabled) {
  background: #66b1ff;
}

.btn-secondary {
  border-color: #dcdfe6;
  color: #606266;
  background: #fff;
}

.btn-secondary:hover:not(:disabled) {
  color: #409eff;
  border-color: #409eff;
}

.btn-danger {
  color: #fff;
  background: #f56c6c;
}

.btn-danger:hover:not(:disabled) {
  background: #f78989;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}

.preview-code,
.log-box,
.job-box,
.chart-box,
.table-wrap {
  border: 1px solid #edf2f8;
  border-radius: 2px;
  padding: 10px;
  background: #fafcff;
}

.preview-head,
.sub-title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.preview-code pre,
.log-box pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
  font-size: 12px;
  color: #303133;
  background: #fff;
  border: 1px solid #edf2f8;
  border-radius: 8px;
  padding: 8px;
}

.job-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #606266;
}

.result-status-card {
  border: 1px solid #e8eef8;
  border-radius: 2px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #f8fbff 0%, #fdfefe 100%);
}

.result-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.status-label {
  color: #606266;
  font-size: 13px;
}

.result-top {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #606266;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.summary-card {
  border: 1px solid #edf2f8;
  border-radius: 8px;
  padding: 8px;
  background: #fff;
}

.summary-key {
  color: #909399;
  font-size: 12px;
}

.summary-value {
  color: #303133;
  font-size: 14px;
  font-weight: 600;
  margin-top: 4px;
}

.equity-canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.equity-canvas-wrap {
  position: relative;
  width: 100%;
  height: clamp(260px, 36vh, 360px);
}

.chart-box {
  background: linear-gradient(180deg, #fefefe 0%, #f5f9ff 100%);
  padding: 12px 14px;
  overflow: hidden;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #edf2f8;
  padding: 8px;
  text-align: left;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.data-table th {
  color: #909399;
  background: #fcfdff;
}

.item-actions {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  border: 1px solid transparent;
}

.status-tag.ok {
  color: #67c23a;
  background: #f0f9eb;
  border-color: #e1f3d8;
}

.status-tag.error {
  color: #f56c6c;
  background: #fef0f0;
  border-color: #fde2e2;
}

.status-tag.cancelled {
  color: #909399;
  background: #f4f4f5;
  border-color: #e9e9eb;
}

.status-tag.running {
  color: #409eff;
  background: #ecf5ff;
  border-color: #d9ecff;
}

.status-tag.idle {
  color: #909399;
  background: #f4f4f5;
  border-color: #e9e9eb;
}

.status-tag-lg {
  padding: 4px 10px;
  font-size: 13px;
}

.error-text {
  color: #f56c6c;
}

.empty-cell {
  padding: 12px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

.mono {
  font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 3100;
  color: #fff;
  border-radius: 2px;
  padding: 10px 16px;
  font-size: 13px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.28);
}

.toast.success {
  background: #67c23a;
}

.toast.error {
  background: #f56c6c;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -46%) scale(0.97);
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 3200;
  background: rgba(15, 23, 42, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.confirm-modal-card {
  width: min(460px, 100%);
  border-radius: 2px;
  border: 1px solid #e4ecf8;
  background: #fff;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.18);
  padding: 16px;
}

.confirm-modal-head {
  font-size: 17px;
  font-weight: 600;
  color: #303133;
}

.confirm-modal-body {
  margin-top: 10px;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.confirm-modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.confirm-modal-card.danger .confirm-modal-head {
  color: #d14343;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1400px) {
  .workbench-grid {
    grid-template-columns: 270px minmax(0, 1fr);
  }

  .history-panel {
    grid-column: span 2;
    min-height: auto;
  }
}

@media (max-width: 1000px) {
  .workbench-grid {
    grid-template-columns: 1fr;
  }

  .strategy-rail,
  .history-panel,
  .main-panel {
    min-height: auto;
  }

  .form-grid.two-col,
  .form-grid.three-col,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
  }
}

body.dark-mode .workbench-header,
body.dark-mode .strategy-rail,
body.dark-mode .main-panel,
body.dark-mode .history-panel,
body.dark-mode .create-box,
body.dark-mode .preview-code,
body.dark-mode .log-box,
body.dark-mode .job-box,
body.dark-mode .result-status-card,
body.dark-mode .chart-box,
body.dark-mode .table-wrap {
  background: #2d2d2d;
  border-color: #4c4d4f;
}

body.dark-mode .workbench-header h2,
body.dark-mode .panel-title,
body.dark-mode .panel-head h3,
body.dark-mode .step-panel h4,
body.dark-mode .summary-value,
body.dark-mode .preview-code pre,
body.dark-mode .log-box pre,
body.dark-mode .data-table td,
body.dark-mode .mono {
  color: #f5f7fa;
}

body.dark-mode .workbench-header p,
body.dark-mode .hint,
body.dark-mode .meta-line,
body.dark-mode .field-row label,
body.dark-mode .status-label,
body.dark-mode .row-meta,
body.dark-mode .item-meta,
body.dark-mode .summary-key,
body.dark-mode .data-table th {
  color: #b0b3b8;
}

body.dark-mode .text-input,
body.dark-mode .btn-secondary,
body.dark-mode .preview-code pre,
body.dark-mode .log-box pre,
body.dark-mode .data-table th {
  background: #1f1f1f;
  border-color: #4c4d4f;
}

body.dark-mode .strategy-row:hover,
body.dark-mode .history-item:hover {
  background: #353638;
}

body.dark-mode .strategy-row.active,
body.dark-mode .history-item.active {
  background: rgba(64, 158, 255, 0.18);
}

body.dark-mode .confirm-modal-card {
  background: #2d2d2d;
  border-color: #4c4d4f;
}

body.dark-mode .confirm-modal-head {
  color: #f5f7fa;
}

body.dark-mode .confirm-modal-body {
  color: #d1d5db;
}
</style>
