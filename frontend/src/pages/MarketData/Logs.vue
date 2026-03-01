<template>
  <div class="logs-container">
    <div class="logs-panel">
      <div class="panel-header">
        <h3>运行日志</h3>
        <div class="header-actions">
          <button @click="loadLogs" class="btn btn-secondary btn-mini" :disabled="logsLoading">
            {{ logsLoading ? '刷新中...' : '刷新' }}
          </button>
          <button @click="showClearConfirm = true" class="btn btn-danger btn-mini" :disabled="logsLoading || logs.length === 0">
            清空
          </button>
        </div>
      </div>
      <div class="panel-body">
        <div v-if="logsLoading" class="loading-state">加载中...</div>
        <div v-else-if="logs.length === 0" class="empty-state">暂无日志</div>
        <div v-else class="table-scroll">
          <table class="table">
            <thead>
              <tr>
                <th style="width: 18%">时间</th>
                <th style="width: 8%">级别</th>
                <th style="width: 12%">任务类型</th>
                <th style="width: 8%">来源</th>
                <th style="width: 54%">消息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.log_id">
                <td class="mono">{{ formatDate(log.timestamp) }}</td>
                <td>
                  <span :class="'level-tag level-' + log.level.toLowerCase()">
                    {{ log.level }}
                  </span>
                </td>
                <td>{{ formatTaskType(log.task_type) }}</td>
                <td>{{ formatSource(log.source) }}</td>
                <td class="log-message">{{ log.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!logsLoading && logs.length > 0" class="pagination">
          <button @click="prevPage" :disabled="currentPage === 1" class="btn btn-secondary btn-mini">
            上一页
          </button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
          <button @click="nextPage" :disabled="currentPage >= totalPages" class="btn btn-secondary btn-mini">
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 清空确认弹框 -->
    <div v-if="showClearConfirm" class="dialog-overlay" @click.self="showClearConfirm = false">
      <div class="dialog">
        <div class="dialog-header">
          <h4>确认清空</h4>
        </div>
        <div class="dialog-body">
          <p>确定要清空所有运行日志吗？此操作不可恢复。</p>
        </div>
        <div class="dialog-footer">
          <button @click="showClearConfirm = false" class="btn btn-secondary">取消</button>
          <button @click="clearLogs" class="btn btn-danger" :disabled="clearing">
            {{ clearing ? '清空中...' : '确认清空' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MarketDataLogs',
  data() {
    return {
      logs: [],
      logsLoading: false,
      currentPage: 1,
      pageSize: 10,
      total: 0,
      showClearConfirm: false,
      clearing: false
    };
  },
  computed: {
    totalPages() {
      return Math.ceil(this.total / this.pageSize);
    }
  },
  mounted() {
    this.loadLogs();
  },
  methods: {
    async loadLogs() {
      this.logsLoading = true;

      try {
        const offset = (this.currentPage - 1) * this.pageSize;
        const response = await fetch(`/api/market-data/logs?limit=${this.pageSize}&offset=${offset}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          this.logs = data.logs;
          this.total = data.total;
        }
      } catch (err) {
        console.error('Failed to load logs:', err);
      } finally {
        this.logsLoading = false;
      }
    },
    async clearLogs() {
      this.clearing = true;
      try {
        const response = await fetch('/api/market-data/logs', {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          this.showClearConfirm = false;
          this.currentPage = 1;
          this.logs = [];
          this.total = 0;
        } else {
          const data = await response.json();
          alert(data.error || '清空失败');
        }
      } catch (err) {
        alert('网络错误，请重试');
      } finally {
        this.clearing = false;
      }
    },
    goToPage(page) {
      if (page >= 1 && page <= this.totalPages) {
        this.currentPage = page;
        this.loadLogs();
      }
    },
    prevPage() {
      this.goToPage(this.currentPage - 1);
    },
    nextPage() {
      this.goToPage(this.currentPage + 1);
    },
    formatDate(dateStr) {
      if (!dateStr) return '-';
      return new Date(dateStr).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    },
    formatTaskType(taskType) {
      const types = {
        full: '全量下载',
        incremental: '增量更新',
        analyze: '数据分析'
      };
      return types[taskType] || taskType || '-';
    },
    formatSource(source) {
      const sources = {
        manual: '手动',
        auto: '自动',
        cron: '定时'
      };
      return sources[source] || source || '-';
    }
  }
};
</script>

<style scoped>
.logs-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.logs-panel {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.panel-body {
  padding: 16px;
}

.loading-state,
.empty-state {
  padding: 20px;
  text-align: center;
  color: #666;
  font-size: 12px;
}

.table-scroll {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  min-width: 800px;
}

.table th,
.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #e0e0e0;
  text-align: left;
  font-size: 12px;
  color: #000;
}

.table th:first-child,
.table td:first-child {
  padding-left: 16px;
}

.table thead th {
  background: #fafafa;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.level-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  border-radius: 2px;
}

.level-info {
  background: #e3f2fd;
  color: #1976d2;
  border-color: #1976d2;
}

.level-warning {
  background: #fff3e0;
  color: #e65100;
  border-color: #ff9800;
}

.level-error {
  background: #ffebee;
  color: #c62828;
  border-color: #ef5350;
}

.log-message {
  word-break: break-word;
  white-space: pre-wrap;
}

.btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  padding: 4px 8px;
  border-radius: 0;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.btn:hover:not(:disabled) {
  border-color: #999;
  background: #f5f5f5;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #fff;
}

.btn-danger {
  background: #fff;
  color: #c62828;
  border-color: #ef5350;
}

.btn-danger:hover:not(:disabled) {
  background: #ffebee;
  border-color: #c62828;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
}

.page-info {
  font-size: 12px;
  color: #666;
}

/* 确认弹框 */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  width: 360px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.dialog-header {
  padding: 14px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.dialog-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.dialog-body {
  padding: 16px;
}

.dialog-body p {
  margin: 0;
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}

.dialog-footer {
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
