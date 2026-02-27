<template>
  <div class="download-container">
    <div class="actions-grid">
      <div class="action-panel">
        <div class="panel-header">
          <h3>全量下载</h3>
        </div>
        <div class="panel-body">
          <p class="panel-desc">下载完整数据包并解压，适用于首次安装或数据重建</p>
          <button @click="triggerFull" :disabled="hasRunningTask" class="btn btn-primary">
            {{ hasRunningTask ? '下载中...' : '开始全量下载' }}
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-if="showConfirm"
      :message="confirmMessage"
      @confirm="handleConfirm"
      @cancel="showConfirm = false"
    />

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @task-complete="handleTaskComplete" />
  </div>
</template>

<script>
import TaskProgress from '@/components/MarketData/TaskProgress.vue';
import ConfirmDialog from '@/components/MarketData/ConfirmDialog.vue';

export default {
  name: 'MarketDataDownload',
  components: {
    TaskProgress,
    ConfirmDialog
  },
  data() {
    return {
      currentTaskId: null,
      showConfirm: false,
      confirmMessage: '',
      confirmType: null,
      hasRunningTask: false
    };
  },
  mounted() {
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
    async triggerIncremental() {
      try {
        const response = await fetch('/api/market-data/download/incremental', {
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
          this.confirmType = 'incremental';
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
      const endpoint = this.confirmType === 'incremental'
        ? '/api/market-data/download/incremental'
        : '/api/market-data/download/full';

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
        alert('✓ 任务执行成功！');
      } else if (task.status === 'failed') {
        alert('✗ 任务执行失败：' + (task.error || '未知错误'));
      }
    }
  }
};
</script>

<style scoped>
.download-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.action-panel {
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

.badge {
  padding: 2px 6px;
  background: #e3f2fd;
  color: #1976d2;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid #1976d2;
  border-radius: 2px;
}

.panel-body {
  padding: 16px;
}

.panel-desc {
  margin: 0 0 12px 0;
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}

.btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  padding: 8px 16px;
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
</style>
