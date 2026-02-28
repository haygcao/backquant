<template>
  <div class="config-container">
    <div class="config-panel">
      <div class="panel-header">
        <h3>定时任务配置</h3>
        <span class="header-hint">定时任务每月1号执行，数据来自于RQAlpha</span>
      </div>
      <div class="panel-body">
        <div v-if="configLoading" class="loading-state">加载配置中...</div>
        <div v-else>
          <div class="form-section">
            <label class="checkbox-label">
              <input type="checkbox" v-model="config.enabled" class="checkbox" :disabled="hasRunningTask" />
              <span>启用定时任务</span>
            </label>
          </div>

          <div class="form-section">
            <div class="form-row">
              <div class="form-field">
                <label class="field-label">Cron 表达式</label>
                <input
                  v-model="config.cron_expression"
                  type="text"
                  placeholder="0 4 1 * *"
                  class="text-input"
                  :disabled="hasRunningTask"
                />
                <span class="hint-text">示例: 0 4 1 * * (每月1日凌晨4点)</span>
              </div>
              <div class="form-field">
                <label class="field-label">任务类型</label>
                <div class="text-display">全量下载</div>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button @click="saveConfig" class="btn btn-primary" :disabled="saving || hasRunningTask">
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="download-panel">
      <div class="panel-header">
        <h3>手动下载</h3>
        <span class="header-hint">如有需要可手动触发下载</span>
      </div>
      <div class="panel-body">
        <button @click="triggerFull" :disabled="hasRunningTask" class="btn btn-primary">
          {{ hasRunningTask ? '下载中...' : '开始全量下载' }}
        </button>
      </div>
    </div>

    <div class="logs-panel">
      <div class="panel-header">
        <h3>运行日志</h3>
        <button @click="loadLogs" class="btn btn-secondary btn-mini" :disabled="logsLoading">
          {{ logsLoading ? '刷新中...' : '刷新' }}
        </button>
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
                <th style="width: 10%">任务类型</th>
                <th style="width: 8%">来源</th>
                <th style="width: 56%">消息</th>
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
      </div>
    </div>

    <ConfirmDialog
      v-if="showConfirm"
      :message="confirmMessage"
      @confirm="handleConfirm"
      @cancel="showConfirm = false"
    />

    <SuccessDialog
      v-if="showSuccess"
      :message="successMessage"
      @close="showSuccess = false"
    />

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @task-complete="handleTaskComplete" />
  </div>
</template>

<script>
import TaskProgress from '@/components/MarketData/TaskProgress.vue';
import ConfirmDialog from '@/components/MarketData/ConfirmDialog.vue';
import SuccessDialog from '@/components/MarketData/SuccessDialog.vue';

export default {
  name: 'MarketDataConfig',
  components: {
    TaskProgress,
    ConfirmDialog,
    SuccessDialog
  },
  data() {
    return {
      config: {
        enabled: true,
        cron_expression: '0 4 1 * *',
        task_type: 'full'
      },
      configLoading: true,
      saving: false,
      logs: [],
      logsLoading: false,
      currentTaskId: null,
      showConfirm: false,
      confirmMessage: '',
      confirmType: null,
      hasRunningTask: false,
      showSuccess: false,
      successMessage: ''
    };
  },
  mounted() {
    this.loadConfig();
    this.loadLogs();
    this.checkRunningTask();
  },
  methods: {
    async checkRunningTask() {
      try {
        const response = await fetch('/api/market-data/tasks/running', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.task && ['pending', 'running'].includes(data.task.status)) {
            this.currentTaskId = data.task.task_id;
            this.hasRunningTask = true;
          }
        }
      } catch (err) {
        console.error('Failed to check running task:', err);
      }
    },
    async triggerFull() {
      try {
        const response = await fetch('/api/market-data/download/full', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify({ force: false })
        });

        const data = await response.json();

        if (data.need_confirm) {
          this.confirmMessage = data.message;
          this.confirmType = 'full';
          this.showConfirm = true;
        } else if (data.task_id) {
          this.currentTaskId = data.task_id;
          this.hasRunningTask = true;
        } else if (response.status === 409) {
          alert(data.error || '已有任务正在运行');
        }
      } catch (err) {
        alert('网络错误，请重试');
      }
    },
    async handleConfirm() {
      this.showConfirm = false;
      const endpoint = '/api/market-data/download/full';

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify({ force: true })
        });

        const data = await response.json();
        if (data.task_id) {
          this.currentTaskId = data.task_id;
          this.hasRunningTask = true;
        }
      } catch (err) {
        alert('网络错误，请重试');
      }
    },
    handleTaskComplete(task) {
      this.currentTaskId = null;
      this.hasRunningTask = false;

      // Show result notification
      if (task.status === 'success') {
        this.successMessage = '下载任务已完成';
        this.showSuccess = true;
        this.loadLogs();
      } else if (task.status === 'failed') {
        this.successMessage = '任务执行失败：' + (task.error || '未知错误');
        this.showSuccess = true;
      }
    },
    async loadConfig() {
      this.configLoading = true;
      try {
        const response = await fetch('/api/market-data/cron/config', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          // Convert enabled from integer to boolean
          this.config = {
            ...data,
            enabled: Boolean(data.enabled)
          };
        }
      } catch (err) {
        console.error('Failed to load config:', err);
      } finally {
        this.configLoading = false;
      }
    },
    async saveConfig() {
      this.saving = true;

      try {
        const response = await fetch('/api/market-data/cron/config', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify(this.config)
        });

        if (response.ok) {
          alert('配置已保存');
          this.loadLogs();
        } else {
          const data = await response.json();
          alert(data.error || '保存失败');
        }
      } catch (err) {
        alert('网络错误，请重试');
      } finally {
        this.saving = false;
      }
    },
    async loadLogs() {
      this.logsLoading = true;

      try {
        const response = await fetch('/api/market-data/logs?limit=100', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          this.logs = data.logs;
        }
      } catch (err) {
        console.error('Failed to load logs:', err);
      } finally {
        this.logsLoading = false;
      }
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
    },
    formatDate(dateStr) {
      if (!dateStr) return '-';
      return new Date(dateStr).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    }
  }
};
</script>

<style scoped>
.config-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-panel,
.download-panel,
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

.header-hint {
  font-size: 12px;
  color: #666;
  font-weight: 400;
}

.panel-body {
  padding: 16px;
}

.form-section {
  margin-bottom: 20px;
}

.form-section:last-child {
  margin-bottom: 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #000;
  font-size: 12px;
}

.checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #1976d2;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.text-input,
.select-input {
  width: 100%;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
  padding: 6px 8px;
  font-size: 12px;
  color: #000;
  background: #fff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  transition: border-color 0.15s ease;
}

.text-input:hover,
.select-input:hover {
  border-color: #999;
}

.text-input:focus,
.select-input:focus {
  outline: none;
  border-color: #1976d2;
}

.hint-text {
  font-size: 11px;
  color: #999;
}

.text-display {
  padding: 6px 8px;
  font-size: 12px;
  color: #666;
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.form-actions {
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
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
  padding: 6px 12px;
  border-radius: 2px;
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

.btn-primary {
  background: #1976d2;
  color: #fff;
  border-color: #1976d2;
}

.btn-primary:hover:not(:disabled) {
  background: #1565c0;
  border-color: #1565c0;
}

.btn-secondary {
  background: #fff;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
