<template>
  <div class="history-page">
    <section class="panel controls-panel">
      <div class="panel-title-row">
        <div class="panel-title-main">
          <h2>回测历史</h2>
          <span class="panel-tag">按策略查看历史任务</span>
        </div>
        <div class="panel-title-controls">
          <select
            id="history-strategy"
            v-model="selectedStrategyId"
            class="text-input"
            data-testid="strategy-select"
            :disabled="loadingStrategies"
            @change="handleStrategyChange"
          >
            <option v-for="item in strategyOptions" :key="item.id" :value="item.id">
              {{ item.id }}
            </option>
          </select>
          <select
            id="history-status"
            v-model="statusFilter"
            class="text-input"
            data-testid="status-filter"
            @change="handleStatusFilterChange"
          >
            <option value="">全部</option>
            <option value="QUEUED">QUEUED</option>
            <option value="RUNNING">RUNNING</option>
            <option value="FAILED">FAILED</option>
            <option value="CANCELLED">CANCELLED</option>
            <option value="FINISHED">FINISHED</option>
          </select>
          <button class="btn btn-secondary" :disabled="jobsLoading || !selectedStrategyId" @click="handleRefresh">
            {{ jobsLoading ? '查询中...' : '查询' }}
          </button>
        </div>
        <button class="btn btn-secondary btn-mini" type="button" @click="handleGoBack">返回上一页</button>
      </div>

      <p v-if="listError" class="error-line">{{ listError }}</p>
      <p v-if="hasActiveJobs" class="polling-tip">检测到 RUNNING / QUEUED 任务，状态将每 3 秒自动刷新。</p>
    </section>

    <div class="content-grid" :class="{ 'jobs-collapsed': jobsPanelCollapsed }">
      <section v-if="!jobsPanelCollapsed" class="panel jobs-panel">
        <div class="section-header">
          <h3>历史任务列表</h3>
          <div class="section-header-actions">
            <span class="meta-text">共 {{ jobsTotal }} 条</span>
          </div>
        </div>
        <button class="btn btn-secondary btn-mini jobs-panel-toggle" type="button" @click="toggleJobsPanel(true)">&lt;&lt;&lt;</button>

        <div class="table-wrap">
          <table class="data-table" data-testid="jobs-table">
            <thead>
              <tr>
                <th>任务 ID</th>
                <th>状态</th>
                <th>开始日期</th>
                <th>结束日期</th>
                <th>初始资金</th>
                <th>基准</th>
                <th>频率</th>
                <th>更新时间</th>
                <th>错误信息</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="jobsLoading">
                <td colspan="10" class="empty-cell">加载中...</td>
              </tr>
              <tr v-else-if="!jobs.length">
                <td colspan="10" class="empty-cell">暂无历史任务</td>
              </tr>
              <tr
                v-for="job in jobs"
                :key="job.job_id"
                data-testid="job-row"
                class="clickable-row"
                :class="{ 'row-selected': selectedJobId === job.job_id }"
                @click="handleSelectJob(job)"
              >
                <td class="job-id-cell">
                  <span class="mono">{{ job.job_id }}</span>
                  <button class="btn btn-secondary btn-mini" @click.stop="copyJobId(job.job_id)">复制</button>
                </td>
                <td>
                  <span class="status-tag" :class="statusTagClass(job.status)">
                    {{ normalizeStatus(job.status) }}
                  </span>
                </td>
                <td>{{ formatDateTime(job.params.start_date) }}</td>
                <td>{{ formatDateTime(job.params.end_date) }}</td>
                <td>{{ formatNumber(job.params.cash) }}</td>
                <td>{{ job.params.benchmark || '-' }}</td>
                <td>{{ job.params.frequency || '-' }}</td>
                <td>{{ formatDateTime(job.updated_at) }}</td>
                <td class="error-col">{{ extractJobErrorText(job) }}</td>
                <td>
                  <button
                    class="btn btn-danger btn-mini"
                    type="button"
                    :disabled="deletingJobId === job.job_id"
                    @click.stop="openDeleteDialog(job)"
                  >
                    {{ deletingJobId === job.job_id ? '删除中...' : '删除' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pagination" v-if="jobsTotalPages > 1">
          <button class="btn btn-secondary" :disabled="jobsPage <= 1 || jobsLoading" @click="goPrevJobsPage">上一页</button>
          <span>第 {{ jobsPage }} / {{ jobsTotalPages }} 页</span>
          <button class="btn btn-secondary" :disabled="jobsPage >= jobsTotalPages || jobsLoading" @click="goNextJobsPage">下一页</button>
        </div>
      </section>

      <section v-else class="panel jobs-collapsed-panel">
        <button class="btn btn-secondary btn-mini jobs-panel-toggle" type="button" @click="toggleJobsPanel(false)">&gt;&gt;&gt;</button>
      </section>

      <section class="panel detail-panel">
        <div class="section-header">
          <h3>任务详情</h3>
          <span v-if="selectedJob" class="meta-text">
            {{ selectedJob.job_id }}
          </span>
        </div>

        <div v-if="!selectedJob" class="empty-block">点击左侧任务行查看详情。</div>
        <template v-else>
          <div class="detail-top-row">
            <span class="status-tag" :class="statusTagClass(selectedJob.status)">{{ normalizeStatus(selectedJob.status) }}</span>
            <div class="detail-time-row">
              <span class="meta-text">回测时间：{{ formatDateTime(selectedJob.updated_at || selectedJob.created_at) }}</span>
              <span class="meta-text">开始时间：{{ formatDateTime(selectedJob.params.start_date) }}</span>
              <span class="meta-text">结束时间：{{ formatDateTime(selectedJob.params.end_date) }}</span>
            </div>
          </div>

          <div v-if="detailLoading" class="empty-block">详情加载中...</div>
          <div v-else-if="detailError" class="error-line">{{ detailError }}</div>
          <div
            v-else-if="selectedJob.status !== 'FINISHED' || detailNotReady"
            class="empty-block"
            data-testid="result-not-ready"
          >
            结果未就绪，任务完成后会自动加载详情。
          </div>
          <section v-else class="detail-layout">
            <aside class="detail-nav">
              <button
                v-for="item in detailNavItems"
                :key="item.key"
                class="detail-nav-item"
                :class="{ active: activeDetailTab === item.key }"
                type="button"
                @click="setActiveDetailTab(item.key)"
              >
                {{ item.label }}
              </button>
            </aside>

            <main class="detail-content">
              <section v-show="activeDetailTab === 'overview'" class="detail-section">
                <div class="summary-grid">
                  <div v-for="item in summaryCards" :key="item.key" class="summary-card">
                    <div class="summary-key">{{ item.label }}</div>
                    <div class="summary-value">{{ formatMetricValue(item.value, item.percent) }}</div>
                  </div>
                </div>

                <div class="result-section">
                  <div class="section-sub-title">收益曲线（策略 / 基准）</div>
                  <div v-if="hasEquityData" class="chart-wrap">
                    <canvas ref="equityChart" data-testid="equity-chart"></canvas>
                  </div>
                  <div v-else class="empty-block">暂无收益曲线数据</div>
                </div>
              </section>

              <section v-show="activeDetailTab === 'trades'" class="detail-section">
                <div class="section-sub-title section-sub-title-row">
                  <span>交易详情</span>
                  <span class="meta-text">共 {{ detailTradeTotal }} 条</span>
                </div>

                <div v-if="tradeRows.length" class="table-wrap trades-table-wrap">
                  <table class="data-table trades-data-table">
                    <thead>
                      <tr>
                        <th v-for="col in tradeDisplayColumns" :key="`trade-col-${col.key}`">{{ col.label }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in tradeRows" :key="`trade-row-${idx}`">
                        <td v-for="col in tradeDisplayColumns" :key="`trade-cell-${idx}-${col.key}`">
                          {{ formatTradeCellValue(resolveTradeValue(row, col), col) }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="empty-block">暂无交易数据</div>

                <div class="pagination" v-if="detailTradeTotalPages > 1">
                  <button class="btn btn-secondary" :disabled="detailPage <= 1 || detailLoading" @click="goPrevDetailPage">上一页</button>
                  <span>第 {{ detailPage }} / {{ detailTradeTotalPages }} 页（共 {{ detailTradeTotal }} 条）</span>
                  <button class="btn btn-secondary" :disabled="detailPage >= detailTradeTotalPages || detailLoading" @click="goNextDetailPage">下一页</button>
                </div>
              </section>

              <section v-show="activeDetailTab === 'logs'" class="detail-section">
                <div class="section-sub-title section-sub-title-row">
                  <span>任务日志</span>
                  <button
                    class="btn btn-secondary btn-mini"
                    type="button"
                    :disabled="detailLogLoading"
                    @click="fetchDetailLog()"
                  >
                    {{ detailLogLoading ? '加载中...' : '刷新日志' }}
                  </button>
                </div>
                <div v-if="detailLogError" class="error-line">{{ detailLogError }}</div>
                <pre class="log-block">{{ detailLogText || '暂无日志' }}</pre>
              </section>

              <section v-show="activeDetailTab === 'performance'" class="detail-section">
                <div class="section-sub-title section-sub-title-row">
                  <span>性能分析</span>
                  <span class="meta-text">共 {{ performanceRows.length }} 项</span>
                </div>
                <div v-if="performanceRows.length" class="performance-grid">
                  <div v-for="item in performanceRows" :key="item.key" class="summary-card performance-card">
                    <div class="summary-key">{{ item.label }}</div>
                    <div class="summary-value">{{ formatMetricValue(item.value, item.percent) }}</div>
                  </div>
                </div>
                <div v-else class="empty-block">暂无性能指标</div>
              </section>
            </main>
          </section>
        </template>
      </section>
    </div>

    <div v-if="showDeleteDialog" class="dialog-overlay" @click.self="closeDeleteDialog">
      <div class="dialog danger">
        <div class="dialog-header">
          <h3>删除确认</h3>
          <button class="dialog-close" type="button" @click="closeDeleteDialog">×</button>
        </div>
        <div class="dialog-body">
          <p>确认删除回测任务 <span class="mono">「{{ pendingDeleteJobId }}」</span> 吗？删除后不可恢复。</p>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeDeleteDialog">取消</button>
          <button class="btn btn-danger" type="button" :disabled="deletingJobId === pendingDeleteJobId" @click="confirmDeleteJob">
            {{ deletingJobId === pendingDeleteJobId ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Chart from 'chart.js/auto';
import {
  listStrategies,
  listStrategyJobs,
  getJob,
  getResult,
  getLog,
  deleteJob
} from '@/api/backtest';
import {
  getStrategyAliasIds,
  getStrategyRenameMap,
  resolveCurrentStrategyId,
  syncStrategyRenameMap
} from '@/utils/strategyRenameMap';

const ACTIVE_STATUSES = new Set(['QUEUED', 'RUNNING']);
const ALIAS_JOBS_PAGE_LIMIT = 500;
const ALIAS_JOBS_MAX_PAGES = 200;

function normalizeStatus(value) {
  const status = String(value || 'QUEUED').toUpperCase();
  if (status === 'RUNNING' || status === 'FINISHED' || status === 'FAILED' || status === 'CANCELLED') {
    return status;
  }
  return 'QUEUED';
}

function unwrapPayload(payload) {
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

function normalizeStrategyOptions(payload) {
  const root = unwrapPayload(payload);
  const source = Array.isArray(root)
    ? root
    : (Array.isArray(root?.strategies)
      ? root.strategies
      : (Array.isArray(root?.items)
        ? root.items
        : (Array.isArray(root?.strategy_list)
          ? root.strategy_list
          : (Array.isArray(root?.list)
            ? root.list
            : (Array.isArray(root?.rows) ? root.rows : [])))));

  const dedup = new Map();
  source.forEach((item) => {
    if (typeof item === 'string') {
      const id = item.trim();
      if (id) {
        dedup.set(id, { id });
      }
      return;
    }
    if (!item || typeof item !== 'object') {
      return;
    }
    const id = String(item.id || item.strategy_id || item.strategyId || item.name || '').trim();
    if (!id) {
      return;
    }
    dedup.set(id, { ...item, id });
  });

  return Array.from(dedup.values());
}

function normalizeJobs(payload) {
  const list = Array.isArray(payload?.jobs) ? payload.jobs : [];
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
        cash: params.cash || 0,
        benchmark: params.benchmark || '',
        frequency: params.frequency || ''
      }
    };
  });
}

function sortJobsByUpdatedAtDesc(a, b) {
  const timeA = new Date(a?.updated_at || a?.created_at || 0).getTime();
  const timeB = new Date(b?.updated_at || b?.created_at || 0).getTime();
  return timeB - timeA;
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

function getErrorMessage(error, fallback) {
  if (error && error.response && error.response.data) {
    const data = error.response.data;
    if (typeof data === 'string') {
      return data;
    }
    if (data.message) {
      return data.message;
    }
    if (data.error && typeof data.error === 'string') {
      return data.error;
    }
    if (data.error && typeof data.error === 'object' && data.error.message) {
      return data.error.message;
    }
  }
  return (error && error.message) || fallback;
}

function normalizeTrades(payload) {
  if (!payload) {
    return { rows: [], columns: [] };
  }

  const columns = Array.isArray(payload.trade_columns) ? payload.trade_columns : [];
  const rawTrades = Array.isArray(payload.trades)
    ? payload.trades
    : (Array.isArray(payload?.trades?.items)
      ? payload.trades.items
      : (Array.isArray(payload?.trades?.records) ? payload.trades.records : []));

  if (!rawTrades.length) {
    return { rows: [], columns };
  }

  const first = rawTrades.find((item) => item !== null && item !== undefined);
  if (!first) {
    return { rows: [], columns };
  }

  if (Array.isArray(first)) {
    const resolvedColumns = columns.length === first.length
      ? columns
      : first.map((_, index) => `col_${index + 1}`);
    const rows = rawTrades.map((line) => {
      if (!Array.isArray(line)) {
        return {};
      }
      const row = {};
      resolvedColumns.forEach((key, index) => {
        row[key] = line[index];
      });
      return row;
    });
    return { rows, columns: resolvedColumns };
  }

  const rows = rawTrades
    .filter((item) => item && typeof item === 'object' && !Array.isArray(item))
    .map((item) => ({ ...item }));

  const fallbackColumns = columns.length
    ? columns
    : Object.keys(rows[0] || {});

  return { rows, columns: fallbackColumns };
}

function getValueByPath(obj, path) {
  if (!obj || typeof obj !== 'object') {
    return undefined;
  }
  const parts = String(path || '').split('.');
  let cur = obj;
  for (let i = 0; i < parts.length; i += 1) {
    const key = parts[i];
    if (!cur || typeof cur !== 'object') {
      return undefined;
    }
    cur = cur[key];
  }
  return cur;
}

function pickFirstAvailable(sources, keys) {
  for (let i = 0; i < sources.length; i += 1) {
    const source = sources[i];
    if (!source || typeof source !== 'object') {
      continue;
    }
    for (let k = 0; k < keys.length; k += 1) {
      const key = keys[k];
      if (key.includes('.')) {
        const nested = getValueByPath(source, key);
        if (nested !== undefined && nested !== null && nested !== '') {
          return nested;
        }
      } else if (source[key] !== undefined && source[key] !== null && source[key] !== '') {
        return source[key];
      }
    }
  }
  return undefined;
}

function normalizeLogPayload(payload) {
  if (!payload) {
    return '';
  }
  if (typeof payload === 'string') {
    return payload;
  }
  if (payload.data !== undefined && payload.data !== null) {
    return normalizeLogPayload(payload.data);
  }
  if (typeof payload.log === 'string') {
    return payload.log;
  }
  if (typeof payload.text === 'string') {
    return payload.text;
  }
  return JSON.stringify(payload, null, 2);
}

const SUMMARY_KEY_LABEL_MAP = {
  total_returns: '总收益',
  total_return: '总收益',
  annualized_returns: '年化收益',
  annualized_return: '年化收益',
  annual_return: '年化收益',
  benchmark_returns: '基准收益',
  benchmark_return: '基准收益',
  excess_returns: '超额收益',
  excess_return: '超额收益',
  alpha_returns: '超额收益',
  max_drawdown: '最大回撤',
  maximum_drawdown: '最大回撤',
  volatility: '波动率',
  annualized_volatility: '年化波动率',
  annual_volatility: '年化波动率',
  sharpe: '夏普比率',
  sharpe_ratio: '夏普比率',
  sortino: '索提诺比率',
  sortino_ratio: '索提诺比率',
  calmar: '卡玛比率',
  calmar_ratio: '卡玛比率',
  information_ratio: '信息比率',
  ir: '信息比率',
  alpha: '阿尔法',
  beta: '贝塔',
  win_rate: '胜率',
  winning_rate: '胜率',
  profit_factor: '盈亏比',
  turnover: '换手率',
  turnover_rate: '换手率',
  trade_count: '交易次数',
  trades_count: '交易次数',
  trades: '交易次数'
};

const METRIC_TOKEN_LABEL_MAP = {
  annualized: '年化',
  annual: '年化',
  benchmark: '基准',
  excess: '超额',
  total: '总',
  cumulative: '累计',
  return: '收益',
  returns: '收益',
  drawdown: '回撤',
  max: '最大',
  maximum: '最大',
  volatility: '波动率',
  sharpe: '夏普',
  sortino: '索提诺',
  calmar: '卡玛',
  information: '信息',
  ratio: '比率',
  alpha: '阿尔法',
  beta: '贝塔',
  win: '胜',
  winning: '胜',
  rate: '率',
  turnover: '换手率',
  trade: '交易',
  trades: '交易',
  count: '次数',
  profit: '盈利',
  loss: '亏损',
  factor: '因子'
};

function formatMetricKeyLabelZh(key) {
  const raw = String(key || '').trim();
  if (!raw) {
    return '指标';
  }
  const normalized = raw.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
  if (SUMMARY_KEY_LABEL_MAP[normalized]) {
    return SUMMARY_KEY_LABEL_MAP[normalized];
  }
  const parts = normalized.split('_').filter(Boolean);
  if (!parts.length) {
    return `指标（${raw}）`;
  }
  const translated = parts.map((part) => METRIC_TOKEN_LABEL_MAP[part] || null);
  if (translated.every(Boolean)) {
    return translated.join('');
  }
  return `指标（${raw}）`;
}

const PERFORMANCE_METRIC_DEFS = [
  { key: 'total_returns', label: '总收益', paths: ['total_returns', 'total_return', 'returns', 'cumulative_returns', 'cum_returns'], percent: true },
  { key: 'annualized_returns', label: '年化收益', paths: ['annualized_returns', 'annualized_return', 'annual_return'], percent: true },
  { key: 'benchmark_returns', label: '基准收益', paths: ['benchmark_returns', 'benchmark_return'], percent: true },
  { key: 'excess_returns', label: '超额收益', paths: ['excess_returns', 'excess_return', 'alpha_returns'], percent: true },
  { key: 'max_drawdown', label: '最大回撤', paths: ['max_drawdown', 'maximum_drawdown'], percent: true },
  { key: 'volatility', label: '波动率', paths: ['volatility', 'annualized_volatility', 'annual_volatility'], percent: true },
  { key: 'sharpe', label: '夏普比率', paths: ['sharpe', 'sharpe_ratio'], percent: false },
  { key: 'sortino', label: '索提诺比率', paths: ['sortino', 'sortino_ratio'], percent: false },
  { key: 'calmar', label: '卡玛比率', paths: ['calmar', 'calmar_ratio'], percent: false },
  { key: 'information_ratio', label: '信息比率', paths: ['information_ratio', 'ir'], percent: false },
  { key: 'alpha', label: '阿尔法', paths: ['alpha'], percent: true },
  { key: 'beta', label: '贝塔', paths: ['beta'], percent: false },
  { key: 'win_rate', label: '胜率', paths: ['win_rate', 'winning_rate'], percent: true },
  { key: 'profit_factor', label: '盈亏比', paths: ['profit_factor'], percent: false },
  { key: 'turnover', label: '换手率', paths: ['turnover', 'turnover_rate'], percent: true },
  { key: 'trade_count', label: '交易次数', paths: ['trade_count', 'trades_count', 'trades'], percent: false }
];

const TRADE_COLUMN_PRESETS = [
  {
    key: 'trade_time',
    label: '交易时间',
    type: 'datetime',
    paths: ['trading_datetime', 'datetime', 'traded_at', 'created_at', 'time', 'date']
  },
  {
    key: 'order_book_id',
    label: '标的代码',
    type: 'text',
    paths: ['order_book_id', 'symbol', 'instrument', 'security', 'ticker', 'code']
  },
  {
    key: 'side',
    label: '方向',
    type: 'direction',
    paths: ['side', 'position_effect', 'order_side']
  },
  {
    key: 'price',
    label: '成交价',
    type: 'number',
    paths: ['price', 'avg_price', 'last_price', 'close_price']
  },
  {
    key: 'quantity',
    label: '成交数量',
    type: 'number',
    paths: ['quantity', 'filled', 'filled_quantity', 'amount_quantity', 'last_quantity']
  },
  {
    key: 'amount',
    label: '成交金额',
    type: 'number',
    paths: ['amount', 'value', 'notional']
  }
];

function getTradeValueByPath(row, path) {
  if (!row || typeof row !== 'object' || !path) {
    return undefined;
  }
  if (Object.prototype.hasOwnProperty.call(row, path)) {
    return row[path];
  }
  return undefined;
}

function resolveTradePresetValue(row, preset) {
  if (!preset || !Array.isArray(preset.paths)) {
    return undefined;
  }
  for (let i = 0; i < preset.paths.length; i += 1) {
    const value = getTradeValueByPath(row, preset.paths[i]);
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }
  return undefined;
}

export default {
  name: 'BacktestHistory',
  data() {
    return {
      loadingStrategies: false,
      strategyRenameMap: {},
      strategyOptions: [],
      selectedStrategyId: '',

      statusFilter: '',
      jobsPanelCollapsed: false,
      jobsLoading: false,
      jobs: [],
      allAliasJobs: [],
      jobsTotal: 0,
      jobsPage: 1,
      jobsPageSize: 10,
      listError: '',

      selectedJobId: '',
      selectedJobSnapshot: null,

      detailLoading: false,
      detailError: '',
      detailNotReady: false,
      detailResult: null,
      detailPage: 1,
      detailPageSize: 20,
      activeDetailTab: 'overview',
      detailLogLoading: false,
      detailLogText: '',
      detailLogError: '',

      pollingTimer: null,
      pollingRequesting: false,

      chart: null,

      showDeleteDialog: false,
      pendingDeleteJobId: '',
      deletingJobId: ''
    };
  },
  computed: {
    jobsTotalPages() {
      return Math.max(1, Math.ceil(this.jobsTotal / this.jobsPageSize));
    },
    selectedJob() {
      if (!this.selectedJobId) {
        return null;
      }
      return this.jobs.find((item) => item.job_id === this.selectedJobId) || this.selectedJobSnapshot;
    },
    hasActiveJobs() {
      return this.jobs.some((item) => ACTIVE_STATUSES.has(normalizeStatus(item.status)));
    },
    summaryPayload() {
      const result = this.detailResult || {};
      if (result.summary && typeof result.summary === 'object') {
        return result.summary;
      }
      if (result.result && result.result.summary && typeof result.result.summary === 'object') {
        return result.result.summary;
      }
      if (result.data && result.data.summary && typeof result.data.summary === 'object') {
        return result.data.summary;
      }
      return {};
    },
    summaryMetricSources() {
      return [this.summaryPayload, this.detailResult || {}];
    },
    summaryCards() {
      const summary = this.summaryPayload;
      return [
        { key: 'total_returns', label: '总收益', value: summary.total_returns, percent: true },
        { key: 'annualized_returns', label: '年化收益', value: summary.annualized_returns, percent: true },
        { key: 'sharpe', label: '夏普比率', value: summary.sharpe, percent: false },
        { key: 'max_drawdown', label: '最大回撤', value: summary.max_drawdown, percent: true },
        { key: 'alpha', label: 'Alpha', value: summary.alpha, percent: false },
        { key: 'beta', label: 'Beta', value: summary.beta, percent: false }
      ];
    },
    performanceRows() {
      const rows = [];
      const consumedKeys = new Set();
      PERFORMANCE_METRIC_DEFS.forEach((def) => {
        def.paths.forEach((path) => consumedKeys.add(path));
        const value = pickFirstAvailable(this.summaryMetricSources, def.paths);
        if (value === undefined || value === null || value === '') {
          return;
        }
        if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
          return;
        }
        rows.push({
          key: def.key,
          label: def.label,
          value,
          percent: def.percent
        });
      });

      const summary = this.summaryPayload || {};
      Object.keys(summary).forEach((key) => {
        if (consumedKeys.has(key)) {
          return;
        }
        const value = summary[key];
        if (value === undefined || value === null || value === '') {
          return;
        }
        if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
          return;
        }
        const label = this.formatSummaryKeyLabel(key);
        if (label.includes('指标')) {
          return;
        }
        rows.push({
          key: `summary_${key}`,
          label,
          value,
          percent: this.isPercentMetricKey(key)
        });
      });

      return rows;
    },
    equityDates() {
      return Array.isArray(this.detailResult?.equity?.dates) ? this.detailResult.equity.dates : [];
    },
    equityNav() {
      return Array.isArray(this.detailResult?.equity?.nav) ? this.detailResult.equity.nav : [];
    },
    benchmarkNav() {
      return Array.isArray(this.detailResult?.equity?.benchmark_nav) ? this.detailResult.equity.benchmark_nav : [];
    },
    hasEquityData() {
      return this.equityDates.length > 0 && this.equityNav.length > 0;
    },
    normalizedTrades() {
      return normalizeTrades(this.detailResult);
    },
    tradeRows() {
      return this.normalizedTrades.rows;
    },
    tradeColumns() {
      return this.normalizedTrades.columns;
    },
    tradeDisplayColumns() {
      if (!this.tradeRows.length) {
        return [];
      }

      const presetColumns = TRADE_COLUMN_PRESETS.filter((preset) => this.tradeRows.some((row) => {
        const value = resolveTradePresetValue(row, preset);
        return value !== undefined && value !== null && value !== '';
      }));

      if (presetColumns.length) {
        return presetColumns;
      }

      const fallbackSource = this.tradeColumns.length
        ? this.tradeColumns
        : Object.keys(this.tradeRows[0] || {});
      return fallbackSource.slice(0, 6).map((key, index) => ({
        key,
        label: this.getTradeColumnLabel(key, index),
        type: this.guessTradeColumnType(key),
        paths: [key]
      }));
    },
    detailTradeTotal() {
      const total = Number(this.detailResult?.trades_total);
      if (Number.isFinite(total) && total >= 0) {
        return total;
      }
      return this.tradeRows.length;
    },
    detailTradeTotalPages() {
      return Math.max(1, Math.ceil(this.detailTradeTotal / this.detailPageSize));
    },
    detailNavItems() {
      return [
        { key: 'overview', label: '收益概览' },
        { key: 'trades', label: '交易详情' },
        { key: 'logs', label: '日志' },
        { key: 'performance', label: '性能分析' }
      ];
    }
  },
  watch: {
    detailResult() {
      this.$nextTick(() => {
        this.renderChart();
      });
    },
    activeDetailTab(value) {
      if (value === 'logs' && !this.detailLogText && !this.detailLogLoading) {
        this.fetchDetailLog(true);
      }
      if (value === 'overview') {
        this.$nextTick(() => {
          this.renderChart();
        });
      }
    }
  },
  async mounted() {
    await this.fetchStrategies();
  },
  beforeUnmount() {
    this.stopPolling();
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  },
  methods: {
    normalizeStatus,
    formatDateTime,
    handleGoBack() {
      if (window.history.length > 1) {
        this.$router.back();
        return;
      }
      this.$router.push({ name: 'strategies' });
    },
    setActiveDetailTab(tab) {
      this.activeDetailTab = String(tab || 'overview');
    },
    toggleJobsPanel(collapsed) {
      this.jobsPanelCollapsed = !!collapsed;
    },
    statusTagClass(status) {
      const value = normalizeStatus(status).toLowerCase();
      return `status-${value}`;
    },
    formatNumber(value) {
      const num = toNumberOrNull(value);
      if (num === null) {
        return '-';
      }
      return num.toLocaleString('zh-CN');
    },
    formatMetricValue(value, isPercent = false) {
      const num = toNumberOrNull(value);
      if (num === null) {
        return 'N/A';
      }
      if (isPercent) {
        return `${(Math.abs(num) <= 2 ? num * 100 : num).toFixed(2)}%`;
      }
      return num.toFixed(4).replace(/\.?0+$/, '');
    },
    formatSummaryKeyLabel(key) {
      return formatMetricKeyLabelZh(key);
    },
    isPercentMetricKey(key) {
      const val = String(key || '').toLowerCase();
      return (
        val.includes('return')
        || val.includes('drawdown')
        || val.includes('volatility')
        || val.includes('turnover')
        || val.endsWith('_rate')
        || val.includes('ratio_pct')
      );
    },
    getTradeColumnLabel(key, index = 0) {
      const labelMap = {
        datetime: '交易时间',
        trading_datetime: '交易时间',
        traded_at: '交易时间',
        date: '日期',
        time: '时间',
        order_book_id: '标的代码',
        symbol: '标的代码',
        instrument: '标的代码',
        security: '标的代码',
        ticker: '标的代码',
        code: '标的代码',
        side: '方向',
        position_effect: '开平方向',
        price: '成交价',
        avg_price: '成交均价',
        quantity: '成交数量',
        filled: '成交数量',
        filled_quantity: '成交数量',
        amount: '成交金额',
        value: '成交金额',
        commission: '手续费',
        tax: '税费',
        pnl: '盈亏'
      };
      const text = String(key || '');
      if (labelMap[text]) {
        return labelMap[text];
      }
      const colMatch = /^col_(\d+)$/i.exec(text);
      if (colMatch) {
        return `字段${colMatch[1]}`;
      }
      return `字段${index + 1}`;
    },
    guessTradeColumnType(key) {
      const normalized = String(key || '').toLowerCase();
      if (normalized.includes('date') || normalized.includes('time')) {
        return 'datetime';
      }
      if (normalized.includes('side') || normalized.includes('position')) {
        return 'direction';
      }
      if (
        normalized.includes('price')
        || normalized.includes('qty')
        || normalized.includes('quantity')
        || normalized.includes('amount')
        || normalized.includes('value')
        || normalized.includes('pnl')
      ) {
        return 'number';
      }
      return 'text';
    },
    resolveTradeValue(row, column) {
      if (!row || typeof row !== 'object' || !column) {
        return undefined;
      }
      if (Array.isArray(column.paths)) {
        for (let i = 0; i < column.paths.length; i += 1) {
          const value = getTradeValueByPath(row, column.paths[i]);
          if (value !== undefined && value !== null && value !== '') {
            return value;
          }
        }
      }
      return getTradeValueByPath(row, column.key);
    },
    formatTradeDirection(value) {
      const normalized = String(value || '').trim().toUpperCase();
      const map = {
        BUY: '买入',
        SELL: '卖出',
        LONG: '多',
        SHORT: '空',
        OPEN: '开仓',
        CLOSE: '平仓'
      };
      return map[normalized] || (value === null || value === undefined || value === '' ? '-' : String(value));
    },
    formatTradeCellValue(value, column) {
      if (value === null || value === undefined || value === '') {
        return '-';
      }

      const type = column?.type || 'text';
      if (type === 'datetime') {
        return formatDateTime(value);
      }

      if (type === 'direction') {
        return this.formatTradeDirection(value);
      }

      if (type === 'number') {
        const num = toNumberOrNull(value);
        if (num !== null) {
          return num.toLocaleString('zh-CN', { maximumFractionDigits: 6 });
        }
      }

      if (typeof value === 'object') {
        return JSON.stringify(value);
      }
      return String(value);
    },
    extractJobErrorText(job) {
      if (!job) {
        return '-';
      }
      if (job.error && typeof job.error === 'object') {
        return job.error.message || job.error.code || '-';
      }
      if (job.error && typeof job.error === 'string') {
        return job.error;
      }
      if (job.error_message) {
        return job.error_message;
      }
      return '-';
    },
    async copyJobId(jobId) {
      if (!jobId) {
        return;
      }
      try {
        if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(jobId);
          return;
        }
      } catch (error) {
        // fallback below
      }

      const input = document.createElement('textarea');
      input.value = String(jobId);
      input.setAttribute('readonly', '');
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
    },
    refreshRenameMap() {
      this.strategyRenameMap = getStrategyRenameMap();
    },
    normalizeCanonicalStrategyId(id) {
      const normalized = String(id || '').trim();
      if (!normalized) {
        return '';
      }
      return resolveCurrentStrategyId(normalized, this.strategyRenameMap) || normalized;
    },
    normalizeCanonicalOptions(options) {
      const dedup = new Map();
      (options || []).forEach((item) => {
        const rawId = typeof item === 'string'
          ? String(item || '').trim()
          : String(item?.id || item?.strategy_id || item?.strategyId || item?.name || '').trim();
        if (!rawId) {
          return;
        }
        const canonicalId = this.normalizeCanonicalStrategyId(rawId);
        if (!canonicalId || dedup.has(canonicalId)) {
          return;
        }
        if (item && typeof item === 'object' && !Array.isArray(item)) {
          dedup.set(canonicalId, { ...item, id: canonicalId });
        } else {
          dedup.set(canonicalId, { id: canonicalId });
        }
      });
      return Array.from(dedup.values());
    },
    applyPagedJobs(allJobs, total) {
      const source = Array.isArray(allJobs) ? allJobs : [];
      const safeTotal = Number.isFinite(Number(total)) ? Number(total) : source.length;
      const totalPages = Math.max(1, Math.ceil(safeTotal / this.jobsPageSize));
      if (this.jobsPage > totalPages) {
        this.jobsPage = totalPages;
      }
      const start = (this.jobsPage - 1) * this.jobsPageSize;
      this.allAliasJobs = source;
      this.jobsTotal = safeTotal;
      this.jobs = source.slice(start, start + this.jobsPageSize);
    },
    async syncSelectedJobAfterFetch(fullJobs) {
      const routeJobId = String((this.$route && this.$route.query && this.$route.query.job_id) || '').trim();
      if (routeJobId && !this.selectedJobId) {
        const source = Array.isArray(fullJobs) ? fullJobs : this.jobs;
        const routeIndex = source.findIndex((item) => item.job_id === routeJobId);
        if (routeIndex >= 0) {
          const targetPage = Math.floor(routeIndex / this.jobsPageSize) + 1;
          if (targetPage !== this.jobsPage) {
            this.jobsPage = targetPage;
            this.applyPagedJobs(source, source.length);
          }
          const routeJob = this.jobs.find((item) => item.job_id === routeJobId);
          if (routeJob) {
            await this.handleSelectJob(routeJob);
          }
        }
      }

      if (!this.selectedJobId) {
        const firstJob = this.jobs[0];
        if (firstJob) {
          await this.handleSelectJob(firstJob);
          return;
        }
      }

      if (this.selectedJobId) {
        const source = Array.isArray(fullJobs) ? fullJobs : this.jobs;
        const latest = source.find((item) => item.job_id === this.selectedJobId);
        if (latest) {
          const prevStatus = normalizeStatus(this.selectedJobSnapshot?.status);
          const nextStatus = normalizeStatus(latest.status);
          this.selectedJobSnapshot = { ...latest };
          if (prevStatus !== 'FINISHED' && nextStatus === 'FINISHED') {
            await Promise.all([
              this.fetchDetailResult(true),
              this.fetchDetailLog(true)
            ]);
          }
        }
      }
    },
    async fetchStrategies() {
      this.loadingStrategies = true;
      this.listError = '';
      await syncStrategyRenameMap();
      this.refreshRenameMap();
      const routeRawStrategyId = String((this.$route && this.$route.query && this.$route.query.strategy_id) || '').trim();
      const routeStrategyId = this.normalizeCanonicalStrategyId(routeRawStrategyId);
      try {
        const data = await listStrategies({
          q: '',
          limit: 100,
          offset: 0
        });
        const list = this.normalizeCanonicalOptions(normalizeStrategyOptions(data));
        if (routeStrategyId && !list.some((item) => item.id === routeStrategyId)) {
          list.unshift({ id: routeStrategyId });
        }
        this.strategyOptions = list;
        const preferred = routeStrategyId && this.strategyOptions.find((item) => item.id === routeStrategyId);
        this.selectedStrategyId = preferred ? preferred.id : (this.strategyOptions[0]?.id || '');

        if (this.selectedStrategyId) {
          await this.fetchJobs();
        } else {
          this.jobs = [];
          this.allAliasJobs = [];
          this.jobsTotal = 0;
          this.stopPolling();
        }
      } catch (error) {
        if (routeStrategyId) {
          this.strategyOptions = [{ id: routeStrategyId }];
          this.selectedStrategyId = routeStrategyId;
          this.listError = '策略列表加载失败，已按 URL 中的策略 ID 查询历史任务';
          await this.fetchJobs();
          return;
        }
        this.listError = getErrorMessage(error, '策略列表加载失败');
      } finally {
        this.loadingStrategies = false;
      }
    },
    async fetchJobs() {
      if (!this.selectedStrategyId) {
        return;
      }

      this.jobsLoading = true;
      this.listError = '';
      try {
        const aliasIds = getStrategyAliasIds(this.selectedStrategyId, this.strategyRenameMap);
        const shouldMergeAliases = aliasIds.length > 1;
        if (shouldMergeAliases) {
          const fetchAllJobsByStrategyId = async (strategyId) => {
            const allJobs = [];
            let total = Number.NaN;

            for (let page = 0; page < ALIAS_JOBS_MAX_PAGES; page += 1) {
              const params = {
                limit: ALIAS_JOBS_PAGE_LIMIT,
                offset: page * ALIAS_JOBS_PAGE_LIMIT
              };
              if (this.statusFilter) {
                params.status = this.statusFilter;
              }

              const data = await listStrategyJobs(strategyId, params);
              const rows = normalizeJobs(data);
              allJobs.push(...rows);

              const totalNum = Number(data?.total);
              if (Number.isFinite(totalNum) && totalNum >= 0) {
                total = totalNum;
              }

              if (!rows.length) {
                break;
              }
              if (rows.length < ALIAS_JOBS_PAGE_LIMIT) {
                break;
              }
              if (Number.isFinite(total) && allJobs.length >= total) {
                break;
              }
            }

            return allJobs;
          };

          const settled = await Promise.all(
            aliasIds.map((strategyId) => fetchAllJobsByStrategyId(strategyId)
              .then((jobs) => ({ ok: true, jobs }))
              .catch((error) => ({ ok: false, error })))
          );
          const failed = settled.find((item) => !item.ok);
          if (failed) {
            throw failed.error;
          }

          const dedup = new Map();
          settled.forEach((item) => {
            (item.jobs || []).forEach((job) => {
              const key = job.job_id || `${job.strategy_id}-${job.created_at}`;
              if (!key) {
                return;
              }
              const previous = dedup.get(key);
              if (!previous) {
                dedup.set(key, job);
                return;
              }
              if (sortJobsByUpdatedAtDesc(job, previous) < 0) {
                dedup.set(key, job);
              }
            });
          });

          const mergedJobs = Array.from(dedup.values()).sort(sortJobsByUpdatedAtDesc);
          this.applyPagedJobs(mergedJobs, mergedJobs.length);
          await this.syncSelectedJobAfterFetch(mergedJobs);
          this.ensurePollingState();
          return;
        }

        const params = {
          limit: this.jobsPageSize,
          offset: (this.jobsPage - 1) * this.jobsPageSize
        };
        if (this.statusFilter) {
          params.status = this.statusFilter;
        }
        const data = await listStrategyJobs(this.selectedStrategyId, params);
        this.jobs = normalizeJobs(data);
        this.allAliasJobs = this.jobs;
        this.jobsTotal = Number(data?.total) || 0;

        await this.syncSelectedJobAfterFetch();
        this.ensurePollingState();
      } catch (error) {
        this.listError = getErrorMessage(error, '历史任务加载失败');
      } finally {
        this.jobsLoading = false;
      }
    },
    openDeleteDialog(job) {
      const jobId = String(job?.job_id || '').trim();
      if (!jobId) {
        this.listError = '任务 ID 为空，无法删除';
        return;
      }
      this.pendingDeleteJobId = jobId;
      this.showDeleteDialog = true;
    },
    closeDeleteDialog(force = false) {
      if (this.deletingJobId && !force) {
        return;
      }
      this.showDeleteDialog = false;
      this.pendingDeleteJobId = '';
    },
    async confirmDeleteJob() {
      const jobId = String(this.pendingDeleteJobId || '').trim();
      if (!jobId) {
        return;
      }

      this.deletingJobId = jobId;
      this.listError = '';
      try {
        await deleteJob(jobId);
        if (this.selectedJobId === jobId) {
          this.resetDetailState();
        }
        this.closeDeleteDialog(true);
        await this.fetchJobs();
      } catch (error) {
        const status = error?.response?.status;
        if (status === 404) {
          // 任务已不存在时按“已删除”处理，保证前端状态可收敛。
          if (this.selectedJobId === jobId) {
            this.resetDetailState();
          }
          this.closeDeleteDialog(true);
          await this.fetchJobs();
          return;
        }
        if (status === 405 || status === 501) {
          this.listError = '后端暂未提供删除接口，请实现 DELETE /api/backtest/jobs/{id}';
        } else {
          this.listError = getErrorMessage(error, '删除任务失败');
        }
      } finally {
        this.deletingJobId = '';
      }
    },
    ensurePollingState() {
      if (this.hasActiveJobs && !this.pollingTimer) {
        this.pollingTimer = setInterval(() => {
          this.pollActiveJobs();
        }, 3000);
      } else if (!this.hasActiveJobs && this.pollingTimer) {
        this.stopPolling();
      }
    },
    stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer);
        this.pollingTimer = null;
      }
      this.pollingRequesting = false;
    },
    async pollActiveJobs() {
      if (this.pollingRequesting) {
        return;
      }

      const activeJobs = this.jobs.filter((item) => ACTIVE_STATUSES.has(normalizeStatus(item.status)));
      if (!activeJobs.length) {
        this.stopPolling();
        return;
      }

      this.pollingRequesting = true;
      let hasStatusChanged = false;
      try {
        const settled = await Promise.all(
          activeJobs.map((job) => getJob(job.job_id)
            .then((data) => ({ ok: true, data, job }))
            .catch(() => ({ ok: false, job })))
        );

        settled.forEach((item) => {
          if (!item.ok) {
            return;
          }
          const latestStatus = normalizeStatus(item.data?.status);
          const index = this.jobs.findIndex((job) => job.job_id === item.job.job_id);
          if (index < 0) {
            return;
          }

          const prevStatus = normalizeStatus(this.jobs[index].status);
          if (prevStatus !== latestStatus) {
            hasStatusChanged = true;
          }

          const updated = {
            ...this.jobs[index],
            status: latestStatus,
            updated_at: item.data?.updated_at || this.jobs[index].updated_at,
            error: item.data?.error || this.jobs[index].error,
            error_message: item.data?.error_message || this.jobs[index].error_message
          };
          this.jobs.splice(index, 1, updated);

          if (this.selectedJobId && this.selectedJobId === updated.job_id) {
            const selectedPrevStatus = normalizeStatus(this.selectedJobSnapshot?.status);
            this.selectedJobSnapshot = { ...updated };
            if (selectedPrevStatus !== 'FINISHED' && updated.status === 'FINISHED') {
              Promise.all([
                this.fetchDetailResult(true),
                this.fetchDetailLog(true)
              ]).catch(() => {});
            }
          }
        });

        if (hasStatusChanged && this.statusFilter) {
          await this.fetchJobs();
          return;
        }
      } finally {
        this.pollingRequesting = false;
        this.ensurePollingState();
      }
    },
    async handleStrategyChange() {
      this.jobsPage = 1;
      this.resetDetailState();
      await this.fetchJobs();
    },
    async handleStatusFilterChange() {
      this.jobsPage = 1;
      this.resetDetailState();
      await this.fetchJobs();
    },
    async handleRefresh() {
      await this.fetchJobs();
      if (this.selectedJob && normalizeStatus(this.selectedJob.status) === 'FINISHED') {
        await Promise.all([
          this.fetchDetailResult(),
          this.fetchDetailLog()
        ]);
      }
    },
    resetDetailState() {
      this.selectedJobId = '';
      this.selectedJobSnapshot = null;
      this.detailResult = null;
      this.detailError = '';
      this.detailNotReady = false;
      this.detailPage = 1;
      this.activeDetailTab = 'overview';
      this.detailLogLoading = false;
      this.detailLogText = '';
      this.detailLogError = '';
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }
    },
    async handleSelectJob(job) {
      this.selectedJobId = job.job_id;
      this.selectedJobSnapshot = { ...job };
      this.detailError = '';
      this.detailResult = null;
      this.detailNotReady = false;
      this.detailPage = 1;
      this.activeDetailTab = 'overview';
      this.detailLogLoading = false;
      this.detailLogText = '';
      this.detailLogError = '';

      if (normalizeStatus(job.status) !== 'FINISHED') {
        this.detailNotReady = true;
        return;
      }

      await Promise.all([
        this.fetchDetailResult(),
        this.fetchDetailLog(true)
      ]);
    },
    async fetchDetailResult(isAutoRefresh = false) {
      if (!this.selectedJob) {
        return;
      }
      if (normalizeStatus(this.selectedJob.status) !== 'FINISHED') {
        this.detailNotReady = true;
        return;
      }

      this.detailLoading = true;
      this.detailError = '';
      try {
        const data = await getResult(this.selectedJob.job_id, {
          page: this.detailPage,
          page_size: this.detailPageSize
        });
        this.detailResult = data || null;
        this.detailNotReady = false;
      } catch (error) {
        const status = error?.response?.status;
        const code = error?.response?.data?.error?.code || error?.response?.data?.code;
        if (status === 409 && code === 'RESULT_NOT_READY') {
          this.detailNotReady = true;
          this.detailError = '';
          if (!isAutoRefresh) {
            this.detailResult = null;
          }
          return;
        }
        this.detailError = getErrorMessage(error, '任务结果加载失败');
      } finally {
        this.detailLoading = false;
      }
    },
    async fetchDetailLog(silent = false) {
      if (!this.selectedJob || this.detailLogLoading) {
        return;
      }
      this.detailLogLoading = true;
      if (!silent) {
        this.detailLogError = '';
      }
      try {
        const data = await getLog(this.selectedJob.job_id);
        this.detailLogText = normalizeLogPayload(data) || '';
        this.detailLogError = '';
      } catch (error) {
        const status = error?.response?.status;
        if (status === 404 || status === 405 || status === 501) {
          this.detailLogText = '';
          this.detailLogError = '后端暂未提供日志接口，请实现 GET /api/backtest/jobs/{id}/log';
          return;
        }
        this.detailLogError = getErrorMessage(error, '日志加载失败');
      } finally {
        this.detailLogLoading = false;
      }
    },
    async goPrevJobsPage() {
      if (this.jobsPage <= 1 || this.jobsLoading) {
        return;
      }
      this.jobsPage -= 1;
      this.resetDetailState();
      await this.fetchJobs();
    },
    async goNextJobsPage() {
      if (this.jobsPage >= this.jobsTotalPages || this.jobsLoading) {
        return;
      }
      this.jobsPage += 1;
      this.resetDetailState();
      await this.fetchJobs();
    },
    async goPrevDetailPage() {
      if (this.detailPage <= 1 || this.detailLoading) {
        return;
      }
      this.detailPage -= 1;
      await this.fetchDetailResult();
    },
    async goNextDetailPage() {
      if (this.detailPage >= this.detailTradeTotalPages || this.detailLoading) {
        return;
      }
      this.detailPage += 1;
      await this.fetchDetailResult();
    },
    renderChart() {
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }
      if (!this.hasEquityData || !this.$refs.equityChart) {
        return;
      }

      const context = this.$refs.equityChart.getContext('2d');
      if (!context) {
        return;
      }

      const datasets = [
        {
          label: '策略净值',
          data: this.equityNav,
          borderColor: '#1f6feb',
          backgroundColor: 'rgba(31, 111, 235, 0.12)',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
          spanGaps: true
        }
      ];

      if (this.benchmarkNav.length) {
        datasets.push({
          label: '基准净值',
          data: this.benchmarkNav,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
          tension: 0.2,
          spanGaps: true
        });
      }

      this.chart = new Chart(context, {
        type: 'line',
        data: {
          labels: this.equityDates,
          datasets
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false
          }
        }
      });
    }
  }
};
</script>

<style scoped>
.history-page {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.panel {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 0;
}

.controls-panel {
  border-bottom: none;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.panel-title-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-title-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: flex-end;
  margin: 0 12px;
}

.panel-title-controls .text-input {
  width: 180px;
}

.panel-title-row h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.panel-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 2px;
  border: 1px solid #d0d0d0;
  color: #666;
  background: #f5f5f5;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
}

.text-input {
  height: 32px;
  border-radius: 2px;
  border: 1px solid #d0d0d0;
  padding: 0 8px;
  font-size: 12px;
  color: #000;
  transition: border-color 0.15s ease;
}

.text-input:hover {
  border-color: #999;
}

.text-input:focus {
  outline: none;
  border-color: #1976d2;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr);
  gap: 12px;
}

.content-grid.jobs-collapsed {
  grid-template-columns: 120px minmax(0, 1fr);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.section-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1f2937;
}

.meta-text {
  font-size: 12px;
  color: #6b7280;
}

.jobs-collapsed-panel {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  min-height: 72px;
}

.jobs-panel {
  position: relative;
}

.jobs-panel-toggle {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 5;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 2px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 840px;
  font-size: 13px;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
  vertical-align: middle;
}

.data-table th {
  background: #f8fafc;
  color: #334155;
  font-weight: 700;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: #f8fafc;
}

.row-selected {
  background: #eef6ff;
}

.job-id-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mono {
  font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 84px;
  border-radius: 2px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
}

.status-running {
  color: #1d4ed8;
  background: #dbeafe;
}

.status-finished {
  color: #15803d;
  background: #dcfce7;
}

.status-failed {
  color: #b91c1c;
  background: #fee2e2;
}

.status-cancelled {
  color: #6b7280;
  background: #f3f4f6;
}

.status-queued {
  color: #c2410c;
  background: #ffedd5;
}

.btn {
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  padding: 8px 12px;
  font-size: 13px;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}

.btn-secondary {
  color: #334155;
  border-color: #d1d5db;
  background: #fff;
}

.btn-danger {
  color: #fff;
  border-color: #dc2626;
  background: #dc2626;
}

.btn-danger:hover:not(:disabled) {
  border-color: #b91c1c;
  background: #b91c1c;
}

.btn-secondary:hover:not(:disabled) {
  color: #1d4ed8;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.pagination {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.empty-cell,
.empty-block {
  text-align: center;
  color: #6b7280;
  padding: 16px;
}

.detail-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.detail-time-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}

.detail-layout {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.detail-nav {
  background: #fff;
  border: 1px solid #e6edf6;
  border-radius: 2px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
  padding: 10px;
  position: sticky;
  top: 76px;
}

.detail-nav-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  padding: 10px 10px;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 700;
  color: #0f172a;
}

.detail-nav-item + .detail-nav-item {
  margin-top: 6px;
}

.detail-nav-item:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.detail-nav-item.active {
  background: #eaf2ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.detail-content {
  min-width: 0;
}

.detail-section {
  min-width: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.performance-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.performance-card {
  min-height: 86px;
}

.summary-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #fafcff;
}

.summary-key {
  color: #6b7280;
  font-size: 12px;
}

.summary-value {
  margin-top: 6px;
  color: #111827;
  font-size: 17px;
  font-weight: 700;
}

.result-section {
  margin-top: 14px;
}

.trades-data-table {
  min-width: 1200px;
}

.section-sub-title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1f2937;
}

.section-sub-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.log-block {
  margin: 0;
  border: 1px solid #e5e7eb;
  border-radius: 2px;
  padding: 10px;
  background: #f8fafc;
  min-height: 140px;
  max-height: 320px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.dialog {
  width: min(460px, 100%);
  border-radius: 2px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 18px 54px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}

.dialog.danger {
  border-color: #fecaca;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.dialog-header h3 {
  margin: 0;
  font-size: 16px;
}

.dialog-close {
  border: 1px solid #cbd5e1;
  background: #fff;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  color: #334155;
}

.dialog-body {
  padding: 14px;
  font-size: 13px;
  color: #334155;
}

.dialog-body p {
  margin: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid #e2e8f0;
}

.chart-wrap {
  height: 300px;
  border: 1px solid #e5e7eb;
  border-radius: 2px;
  padding: 10px;
}

.error-line {
  margin-top: 8px;
  color: #dc2626;
  font-size: 13px;
}

.error-col {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.polling-tip {
  margin-top: 8px;
  color: #1d4ed8;
  font-size: 12px;
}

@media (max-width: 1180px) {
  .content-grid,
  .content-grid.jobs-collapsed {
    grid-template-columns: 1fr;
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-nav {
    position: static;
    display: flex;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
    white-space: nowrap;
  }

  .detail-nav-item {
    width: auto;
    flex: 0 0 auto;
  }

  .detail-nav-item + .detail-nav-item {
    margin-top: 0;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .performance-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .controls-grid {
    grid-template-columns: 1fr;
  }

  .control-btn-wrap {
    justify-content: flex-start;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .performance-grid {
    grid-template-columns: 1fr;
  }

  .detail-top-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-time-row {
    justify-content: flex-start;
    gap: 8px;
  }

  .detail-nav {
    padding: 8px;
  }

  .detail-nav-item {
    padding: 8px 10px;
    font-size: 12px;
  }
}
</style>
