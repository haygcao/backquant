<template>
  <div class="packages-container">
    <div class="packages-panel">
      <div class="panel-header">
        <div class="header-left">
          <h3>已安装的 Python 包</h3>
          <span v-if="updatedAt" class="update-time">更新于: {{ formatDate(updatedAt) }}</span>
        </div>
        <div class="header-right">
          <div class="search-box">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索包名..."
              class="search-input"
            />
          </div>
          <button @click="refreshPackages" class="btn btn-secondary" :disabled="refreshing">
            {{ refreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
      </div>
      <div class="panel-body">
        <div v-if="loading" class="loading-state">加载中...</div>
        <div v-else-if="error" class="error-state">
          <div class="inline-error">{{ error }}</div>
          <button @click="loadPackages" class="btn btn-secondary">重试</button>
        </div>
        <div v-else class="table-scroll">
          <table class="table">
            <thead>
              <tr>
                <th style="width: 60px; text-align: center">#</th>
                <th style="width: 40%">包名</th>
                <th style="width: 60%">版本</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="filteredPackages.length === 0">
                <td colspan="3" class="empty-cell">
                  {{ searchKeyword ? '未找到匹配的包' : '暂无数据' }}
                </td>
              </tr>
              <tr v-for="(pkg, index) in filteredPackages" :key="pkg.name">
                <td class="row-number">{{ index + 1 }}</td>
                <td class="package-name">{{ pkg.name }}</td>
                <td class="package-version">{{ pkg.version }}</td>
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
  name: 'PythonPackages',
  data() {
    return {
      loading: false,
      error: null,
      packages: [],
      searchKeyword: '',
      updatedAt: null,
      refreshing: false
    };
  },
  computed: {
    filteredPackages() {
      if (!this.searchKeyword) {
        return this.packages;
      }
      const keyword = this.searchKeyword.toLowerCase();
      return this.packages.filter(pkg =>
        pkg.name.toLowerCase().includes(keyword)
      );
    }
  },
  mounted() {
    this.loadPackages();
  },
  methods: {
    async loadPackages() {
      this.loading = true;
      this.error = null;

      try {
        const response = await fetch('/api/packages/list', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          const result = await response.json();
          this.packages = result.packages || [];
          this.updatedAt = result.updated_at;
        } else {
          this.error = '加载失败';
        }
      } catch (err) {
        this.error = '网络错误，请重试';
      } finally {
        this.loading = false;
      }
    },
    async refreshPackages() {
      this.refreshing = true;

      try {
        const response = await fetch('/api/packages/refresh', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          await this.loadPackages();
        } else {
          this.error = '刷新失败';
        }
      } catch (err) {
        this.error = '网络错误，请重试';
      } finally {
        this.refreshing = false;
      }
    },
    formatDate(dateStr) {
      if (!dateStr) return '-';
      const date = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}`;
    }
  }
};
</script>

<style scoped>
.packages-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.packages-panel {
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

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.update-time {
  font-size: 11px;
  color: #666;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-box {
  flex: 0 0 300px;
}

.search-input {
  width: 100%;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
  padding: 6px 8px;
  font-size: 12px;
  color: #000;
  background: #fff;
  transition: border-color 0.15s ease;
}

.search-input:hover {
  border-color: #999;
}

.search-input:focus {
  outline: none;
  border-color: #1976d2;
}

.panel-body {
  padding: 0;
}

.loading-state,
.error-state {
  padding: 40px;
  text-align: center;
}

.loading-state {
  color: #666;
  font-size: 12px;
}

.inline-error {
  background: #ffebee;
  border: 1px solid #ef5350;
  color: #c62828;
  padding: 8px 12px;
  border-radius: 2px;
  margin-bottom: 12px;
  font-size: 12px;
}

.table-scroll {
  max-height: calc(100vh - 250px);
  overflow-y: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
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

.table tbody tr:hover {
  background: #f9f9f9;
}

.row-number {
  color: #999;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-align: center;
}

.package-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
}

.package-version {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #666;
}

.empty-cell {
  text-align: center;
  color: #999;
  padding: 40px 10px;
  font-size: 12px;
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

.btn-secondary {
  background: #fff;
}
</style>
