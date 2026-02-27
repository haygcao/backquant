<template>
  <div class="config-container">
    <div class="config-panel">
      <div class="panel-header">
        <h3>定时任务配置</h3>
      </div>
      <div class="panel-body">
        <div class="form-section">
          <label class="checkbox-label">
            <input type="checkbox" v-model="config.enabled" class="checkbox" />
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
                placeholder="0 2 1 * *"
                class="text-input"
              />
              <span class="hint-text">示例: 0 2 1 * * (每月1日凌晨2点)</span>
            </div>
            <div class="form-field">
              <label class="field-label">任务类型</label>
              <select v-model="config.task_type" class="select-input">
                <option value="incremental">增量更新</option>
                <option value="full">全量下载</option>
              </select>
            </div>
          </div>
        </div>

        <div class="form-actions">
          <button @click="saveConfig" class="btn btn-primary" :disabled="saving">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
        </div>
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
                <th style="width: 20%">触发时间</th>
                <th style="width: 10%">状态</th>
                <th style="width: 30%">任务ID</th>
                <th style="width: 40%">消息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.log_id">
                <td class="mono">{{ formatDate(log.trigger_time) }}</td>
                <td>
                  <span :class="'status-tag status-' + log.status">
                    {{ log.status }}
                  </span>
                </td>
                <td class="mono">{{ log.task_id || '-' }}</td>
                <td>{{ log.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MarketDataConfig',
  data() {
    return {
      config: {
        enabled: false,
        cron_expression: '0 2 1 * *',
        task_type: 'incremental'
      },
      saving: false,
      logs: [],
      logsLoading: false
    };
  },
  mounted() {
    this.loadConfig();
    this.loadLogs();
  },
  methods: {
    async loadConfig() {
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
        const response = await fetch('/api/market-data/cron/logs?limit=20', {
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
    formatDate(dateStr) {
      if (!dateStr) return '-';
      return new Date(dateStr).toLocaleString('zh-CN');
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

.status-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  border-radius: 2px;
}

.status-success {
  background: #e8f5e9;
  color: #2e7d32;
  border-color: #4caf50;
}

.status-failed {
  background: #ffebee;
  color: #c62828;
  border-color: #ef5350;
}

.status-skipped {
  background: #fff3e0;
  color: #e65100;
  border-color: #ff9800;
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
