<template>
  <div class="strategies-page">
    <div class="page-container">
      <div class="page-header">
        <div class="title-section">
          <h2>策略管理</h2>
          <span class="meta">{{ filteredRows.length }} 条</span>
          <span v-if="selectedIds.length" class="meta selected">已选 {{ selectedIds.length }} 条</span>
        </div>

        <div class="actions-section">
          <div class="search-wrap">
            <input
              v-model.trim="keyword"
              class="text-input"
              type="text"
              placeholder="搜索策略名"
            >
          </div>

          <button class="btn btn-secondary" :disabled="loading" @click="fetchList(false)">
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
          <button class="btn btn-danger" type="button" :disabled="!selectedIds.length || !!deletingId" @click="handleBatchDelete">
            {{ deletingId === '__batch__' ? '删除中...' : `批量删除（${selectedIds.length}）` }}
          </button>
          <button class="btn btn-primary" @click="handleCreateStrategy">
            新建策略
          </button>
        </div>
      </div>

      <div class="page-body">
        <div v-if="errorMessage" class="inline-error">
          {{ errorMessage }}
        </div>

        <div class="table-scroll">
          <table class="table">
            <thead>
              <tr>
                <th class="check-col" style="width: 5%">
                  <input
                    class="row-checkbox"
                    type="checkbox"
                    :checked="isAllPageSelected"
                    :indeterminate.prop="isPageSelectionIndeterminate"
                    :disabled="!pageSelectableRows.length || !!deletingId"
                    title="全选当前页可删除策略"
                    @change="toggleSelectAllOnPage($event)"
                  >
                </th>
                <th style="width: 5%">序号</th>
                <th style="width: 28%">名称</th>
                <th style="width: 18%">创建时间</th>
                <th style="width: 18%">最后修改</th>
                <th style="width: 21%">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="editingNewRow" class="new-row">
                <td class="row-select-cell"></td>
                <td></td>
                <td class="mono">
                  <input
                    ref="newStrategyInput"
                    v-model="newStrategyName"
                    class="inline-input"
                    type="text"
                    placeholder="输入策略名称（支持中文、字母、数字、下划线、中横线）"
                    @keydown="handleNewStrategyKeydown"
                  >
                </td>
                <td colspan="2" class="new-row-hint">
                  <span class="hint-text">输入策略名称后点击确认</span>
                </td>
                <td class="row-actions">
                  <button class="btn btn-mini btn-primary" type="button" @click="confirmNewStrategy">确认</button>
                  <button class="btn btn-mini btn-secondary" type="button" @click="cancelNewStrategy">取消</button>
                </td>
              </tr>
              <tr v-if="!pagedRows.length && !editingNewRow">
                <td colspan="6" class="empty-cell">
                  {{ loading ? '加载中...' : '暂无策略（可点击"新建策略"）' }}
                </td>
              </tr>
              <tr
                v-for="(row, index) in pagedRows"
                :key="row.id"
                class="data-row"
                :class="{ 'is-selected': isRowSelected(row.id) }"
                @click="handleRowClick(row.id)"
              >
                <td class="row-select-cell" @click.stop>
                  <input
                    class="row-checkbox"
                    type="checkbox"
                    :checked="isRowSelected(row.id)"
                    :disabled="!isStrategyDeletable(row) || !!deletingId"
                    :title="getDeleteDisabledReason(row) || '选择策略'"
                    @change="toggleRowSelection(row.id, $event.target.checked)"
                  >
                </td>
                <td>{{ (currentPage - 1) * pageSize + index + 1 }}</td>
                <td class="mono">
                  <button class="link-btn" type="button" @click.stop="goEdit(row.id)">
                    {{ row.id }}
                  </button>
                </td>
                <td>{{ formatMetaDate(row.created_at) }}</td>
                <td>{{ formatMetaDate(row.updated_at || row.created_at) }}</td>
                <td class="row-actions" @click.stop>
                  <button class="btn btn-mini btn-secondary" type="button" @click.stop="goEdit(row.id)">编辑</button>
                  <button
                    class="btn btn-mini btn-danger"
                    type="button"
                    :disabled="!!deletingId"
                    :title="getDeleteDisabledReason(row) || '删除策略'"
                    :class="{ 'is-locked': !isStrategyDeletable(row) }"
                    @click.stop="handleDelete(row.id)"
                  >
                    {{ deletingId === row.id ? '删除中...' : '删除' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pager">
          <button class="btn btn-secondary" :disabled="currentPage <= 1" @click="currentPage -= 1">上一页</button>
          <div class="pager-meta">
            第 {{ currentPage }} / {{ totalPages }} 页
            <span class="pager-split">·</span>
            每页 {{ pageSize }} 条
          </div>
          <button class="btn btn-secondary" :disabled="currentPage >= totalPages" @click="currentPage += 1">下一页</button>
        </div>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast" :class="toastType">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <div v-if="showCreateModal" class="dialog-overlay" @click.self="closeCreateModal">
      <div class="dialog">
        <div class="dialog-header">
          <h3>新建策略</h3>
          <button class="dialog-close" type="button" @click="closeCreateModal">×</button>
        </div>
        <div class="dialog-body">
          <label for="strategy-id-input" class="dialog-label">策略名称</label>
          <input
            id="strategy-id-input"
            v-model.trim="createDraftId"
            class="text-input"
            type="text"
            :placeholder="createSuggestedId"
            @keyup.enter="confirmCreate"
          >
          <div class="dialog-tip">支持中文、字母、数字、下划线和中横线，且不能包含空格。</div>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeCreateModal">取消</button>
          <button class="btn btn-primary" type="button" @click="confirmCreate">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showDeleteModal" class="dialog-overlay" @click.self="closeDeleteModal">
      <div class="dialog danger">
        <div class="dialog-header">
          <h3>删除确认</h3>
          <button class="dialog-close" type="button" @click="closeDeleteModal">×</button>
        </div>
        <div class="dialog-body">
          <p v-if="pendingDeleteIds.length === 1">
            确认删除策略 <span class="mono">「{{ pendingDeleteIds[0] }}」</span> 吗？删除后无法恢复。
          </p>
          <p v-else>
            确认删除已选中的 {{ pendingDeleteIds.length }} 个策略吗？删除后无法恢复。
          </p>
          <p v-if="pendingDeleteIds.length > 1" class="delete-list mono">
            {{ pendingDeleteIds.join('、') }}
          </p>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeDeleteModal">取消</button>
          <button class="btn btn-danger" type="button" :disabled="!!deletingId" @click="confirmDelete">
            {{ deletingId ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { listStrategies, saveStrategy } from '@/api/backtest';
import { mergeLocalStrategyIds, removeLocalStrategyId } from '@/utils/backtestStrategies';
import { normalizeStrategyList } from '@/utils/strategyNormalize';
import { getStrategyRenameMap, resolveCurrentStrategyId, syncStrategyRenameMap } from '@/utils/strategyRenameMap';
import { deleteStrategyCascade } from '@/utils/strategyDeletion';

function getStrategyMetaTimestamp(item) {
  const raw = item?.updated_at || item?.created_at || '';
  const ts = new Date(raw).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

export default {
  name: 'StrategiesIndex',
  data() {
    return {
      loading: false,
      errorMessage: '',
      keyword: '',
      rows: [],
      selectedIds: [],
      currentPage: 1,
      pageSize: 10,
      deletingId: '',
      showCreateModal: false,
      createDraftId: '',
      createSuggestedId: '',
      showDeleteModal: false,
      pendingDeleteIds: [],
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null,
      editingNewRow: false,
      newStrategyName: ''
    };
  },
  computed: {
    filteredRows() {
      const keyword = (this.keyword || '').trim().toLowerCase();
      if (!keyword) {
        return this.rows;
      }
      return this.rows.filter((row) => String(row.id).toLowerCase().includes(keyword));
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.filteredRows.length / this.pageSize));
    },
    pagedRows() {
      const page = Math.min(this.currentPage, this.totalPages);
      const start = (Math.max(1, page) - 1) * this.pageSize;
      return this.filteredRows.slice(start, start + this.pageSize);
    },
    pageSelectableRows() {
      return this.pagedRows.filter((row) => this.isStrategyDeletable(row));
    },
    isAllPageSelected() {
      if (!this.pageSelectableRows.length) {
        return false;
      }
      const selectedSet = new Set(this.selectedIds);
      return this.pageSelectableRows.every((row) => selectedSet.has(row.id));
    },
    isPageSelectionIndeterminate() {
      if (!this.pageSelectableRows.length) {
        return false;
      }
      const selectedSet = new Set(this.selectedIds);
      const selectedCount = this.pageSelectableRows.filter((row) => selectedSet.has(row.id)).length;
      return selectedCount > 0 && selectedCount < this.pageSelectableRows.length;
    }
  },
  watch: {
    keyword() {
      this.currentPage = 1;
    },
    filteredRows() {
      if (this.currentPage > this.totalPages) {
        this.currentPage = this.totalPages;
      }
    },
    rows(nextRows) {
      const idSet = new Set((nextRows || []).map((row) => String(row?.id || '').trim()).filter(Boolean));
      this.selectedIds = this.selectedIds.filter((id) => idSet.has(id));
    }
  },
  methods: {
    showMessage(message, type = 'success') {
      this.toastType = type;
      this.toastMessage = message;
      this.showToast = true;
      if (this.toastTimer) {
        clearTimeout(this.toastTimer);
      }
      this.toastTimer = setTimeout(() => {
        this.showToast = false;
      }, 2200);
    },
    getErrorMessage(error, fallback) {
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
        return fallback;
      }
      return (error && error.message) || fallback;
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
    normalizeCanonicalStrategyRows(rows = [], renameMap = null) {
      const map = renameMap && typeof renameMap === 'object' ? renameMap : getStrategyRenameMap();
      const dedup = new Map();

      (rows || []).forEach((item) => {
        const rawId = String(item?.id || '').trim();
        if (!rawId) {
          return;
        }
        const canonicalId = resolveCurrentStrategyId(rawId, map) || rawId;
        const nextItem = {
          ...(item || {}),
          id: canonicalId
        };

        const previous = dedup.get(canonicalId);
        if (!previous) {
          dedup.set(canonicalId, nextItem);
          return;
        }

        if (getStrategyMetaTimestamp(nextItem) >= getStrategyMetaTimestamp(previous)) {
          dedup.set(canonicalId, { ...previous, ...nextItem, id: canonicalId });
        }
      });

      return Array.from(dedup.values());
    },
    goEdit(id) {
      this.$router.push({ name: 'strategy-edit', params: { id: String(id) } });
    },
    handleRowClick(id) {
      this.goEdit(id);
    },
    isRowSelected(id) {
      const target = String(id || '').trim();
      return !!target && this.selectedIds.includes(target);
    },
    toggleRowSelection(id, checked) {
      const target = String(id || '').trim();
      if (!target) {
        return;
      }
      if (checked) {
        if (!this.selectedIds.includes(target)) {
          this.selectedIds = [...this.selectedIds, target];
        }
        return;
      }
      this.selectedIds = this.selectedIds.filter((item) => item !== target);
    },
    toggleSelectAllOnPage(event) {
      const checked = Boolean(event && event.target && event.target.checked);
      const pageIds = this.pageSelectableRows.map((row) => String(row.id || '').trim()).filter(Boolean);
      if (!pageIds.length) {
        return;
      }
      if (checked) {
        this.selectedIds = Array.from(new Set([...this.selectedIds, ...pageIds]));
        return;
      }
      const pageSet = new Set(pageIds);
      this.selectedIds = this.selectedIds.filter((id) => !pageSet.has(id));
    },
    isStrategyDeletable(row) {
      const target = row || {};
      const strategyId = String(target.id || '').trim();
      if (!strategyId) {
        return false;
      }
      if (strategyId === 'demo' || strategyId === 'golden_cross_demo') {
        return false;
      }
      if (target.read_only) {
        return false;
      }
      if (target.is_builtin) {
        return false;
      }
      if (target.can_delete === false) {
        return false;
      }
      return true;
    },
    getDeleteDisabledReason(row) {
      const target = row || {};
      const strategyId = String(target.id || '').trim();
      if (!strategyId) {
        return '策略 ID 缺失，无法删除';
      }
      if (strategyId === 'demo') {
        return 'demo 为内置示例策略，不支持删除';
      }
      if (strategyId === 'golden_cross_demo') {
        return 'golden_cross_demo 为内置示例策略，不支持删除';
      }
      if (target.read_only) {
        return '只读策略不支持删除';
      }
      if (target.is_builtin) {
        return '系统内置策略不支持删除';
      }
      if (target.can_delete === false) {
        return '后端标记该策略不可删除';
      }
      return '';
    },
    handleBatchDelete() {
      if (!this.selectedIds.length) {
        this.showMessage('请先勾选要删除的策略', 'error');
        return;
      }
      const selectedSet = new Set(this.selectedIds);
      const selectedRows = this.rows.filter((row) => selectedSet.has(String(row?.id || '').trim()));
      if (!selectedRows.length) {
        this.showMessage('未找到可删除的已选策略', 'error');
        return;
      }
      const blocked = selectedRows.find((row) => !this.isStrategyDeletable(row));
      if (blocked) {
        this.showMessage(this.getDeleteDisabledReason(blocked), 'error');
        return;
      }
      this.pendingDeleteIds = selectedRows.map((row) => String(row.id).trim());
      this.showDeleteModal = true;
    },
    handleCreateStrategy() {
      this.editingNewRow = true;
      this.newStrategyName = `strategy_${Date.now()}`;
      this.$nextTick(() => {
        const input = this.$refs.newStrategyInput;
        if (input) {
          input.select();
        }
      });
    },
    cancelNewStrategy() {
      this.editingNewRow = false;
      this.newStrategyName = '';
    },
    async confirmNewStrategy() {
      const id = String(this.newStrategyName || '').trim();
      if (!id) {
        this.cancelNewStrategy();
        return;
      }
      if (/\s/.test(id)) {
        this.showMessage('策略 ID 不能包含空白字符', 'error');
        return;
      }
      if (!/^[A-Za-z0-9_\-\u4E00-\u9FFF]+$/.test(id)) {
        this.showMessage('策略 ID 仅支持中文、字母、数字、下划线和中横线', 'error');
        return;
      }

      this.editingNewRow = false;

      // 创建策略记录，带RQAlpha模板代码
      const templateCode = `from rqalpha.api import *


def init(context):
    # 只订阅一只股票（示例：平安银行）
    context.s1 = "000001.XSHE"


def before_trading(context):
    # 每天开盘前会调用一次
    pass


def handle_bar(context, bar_dict):
    pos = get_position(context.s1)
    # 每个 bar（取决于你设置的频率）都会调用
    # 最简单逻辑：如果没有持仓，就买 100 股
    if pos.quantity == 0:
        order_target_percent(context.s1, 1.0)


def after_trading(context):
    # 每天收盘后会调用一次
    pass
`;

      try {
        await saveStrategy(id, templateCode);
        this.showMessage(`策略 ${id} 创建成功`);
        await this.fetchList(true);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '创建策略失败'), 'error');
      }
    },
    handleNewStrategyKeydown(event) {
      if (event.key === 'Enter') {
        this.confirmNewStrategy();
      } else if (event.key === 'Escape') {
        this.cancelNewStrategy();
      }
    },
    closeCreateModal() {
      this.showCreateModal = false;
      this.createDraftId = '';
      this.createSuggestedId = '';
    },
    confirmCreate() {
      const id = String(this.createDraftId || '').trim();
      if (!id) {
        this.showMessage('策略 ID 不能为空', 'error');
        return;
      }
      if (/\s/.test(id)) {
        this.showMessage('策略 ID 不能包含空白字符', 'error');
        return;
      }
      if (!/^[A-Za-z0-9_\-\u4E00-\u9FFF]+$/.test(id)) {
        this.showMessage('策略 ID 仅支持中文、字母、数字、下划线和中横线', 'error');
        return;
      }

      this.closeCreateModal();
      this.goEdit(id);
    },
    handleDelete(id) {
      const strategyId = String(id || '').trim();
      if (!strategyId) {
        return;
      }
      const row = this.rows.find((item) => item.id === strategyId);
      const reason = this.getDeleteDisabledReason(row || { id: strategyId });
      if (reason) {
        this.showMessage(reason, 'error');
        return;
      }
      this.pendingDeleteIds = [strategyId];
      this.showDeleteModal = true;
    },
    closeDeleteModal() {
      if (this.deletingId) {
        return;
      }
      this.showDeleteModal = false;
      this.pendingDeleteIds = [];
    },
    async confirmDelete() {
      const targetIds = Array.from(
        new Set((this.pendingDeleteIds || []).map((id) => String(id || '').trim()).filter(Boolean))
      );
      if (!targetIds.length) {
        return;
      }

      this.deletingId = targetIds.length > 1 ? '__batch__' : targetIds[0];
      let deletedCount = 0;
      let deletedJobs = 0;
      const failures = [];
      try {
        for (let i = 0; i < targetIds.length; i += 1) {
          const strategyId = targetIds[i];
          try {
            const result = await deleteStrategyCascade(strategyId);
            const deletedId = String(result?.strategyId || strategyId).trim();
            this.rows = this.rows.filter((row) => row.id !== deletedId);
            removeLocalStrategyId(strategyId);
            if (deletedId && deletedId !== strategyId) {
              removeLocalStrategyId(deletedId);
            }
            this.selectedIds = this.selectedIds.filter((id) => id !== strategyId && id !== deletedId);
            deletedJobs += Number(result?.deletedJobs || 0);
            deletedCount += 1;
          } catch (error) {
            failures.push({
              id: strategyId,
              message: this.getErrorMessage(error, '策略删除失败')
            });
          }
        }

        if (!failures.length) {
          if (targetIds.length === 1) {
            this.showMessage(`策略删除成功（同时删除 ${deletedJobs} 条历史任务）`);
          } else {
            this.showMessage(`批量删除成功（策略 ${deletedCount} 条，历史任务 ${deletedJobs} 条）`);
          }
          return;
        }

        if (deletedCount > 0) {
          this.showMessage(`已删除 ${deletedCount} 条，失败 ${failures.length} 条：${failures[0].message}`, 'error');
          return;
        }

        this.showMessage(failures[0].message || '策略删除失败', 'error');
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '策略删除失败'), 'error');
      } finally {
        this.showDeleteModal = false;
        this.pendingDeleteIds = [];
        this.deletingId = '';
      }
    },
    async fetchList(silent = true) {
      this.loading = true;
      this.errorMessage = '';
      try {
        await syncStrategyRenameMap();
        const renameMap = getStrategyRenameMap();
        // 这里优先走后端列表接口；若后端未来支持分页，可在 params 中透传 page/page_size。
        const data = await listStrategies();
        const list = this.normalizeCanonicalStrategyRows(normalizeStrategyList(data), renameMap);
        // 自定义排序：demo 第一，golden_cross_demo 第二，其余按更新时间倒序
        const sorted = [...list].sort((a, b) => {
          const idA = String(a.id || '').trim();
          const idB = String(b.id || '').trim();

          // demo 始终排第一
          if (idA === 'demo') return -1;
          if (idB === 'demo') return 1;

          // golden_cross_demo 排第二
          if (idA === 'golden_cross_demo') return -1;
          if (idB === 'golden_cross_demo') return 1;

          // 其余按更新时间倒序
          const tsA = getStrategyMetaTimestamp(a);
          const tsB = getStrategyMetaTimestamp(b);
          return tsB - tsA;
        });
        this.rows = sorted;
        mergeLocalStrategyIds(sorted.map((item) => item.id));
      } catch (error) {
        if (!silent) {
          this.errorMessage = this.getErrorMessage(error, '获取策略列表失败');
        }
      } finally {
        this.loading = false;
      }
    }
  },
  async mounted() {
    await this.fetchList(true);
  },
  beforeUnmount() {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
  }
};
</script>

<style scoped>
.strategies-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-height: 0;
}

.page-container {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.title-section h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.actions-section {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.search-wrap {
  width: 200px;
}

.meta {
  font-size: 12px;
  color: #666;
}

.text-input {
  width: 100%;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
  padding: 6px 8px;
  font-size: 12px;
  color: #000;
  background: #fff;
  transition: border-color 0.15s ease;
}

.text-input:hover {
  border-color: #999;
}

.text-input:focus {
  outline: none;
  border-color: #1976d2;
}

.meta.selected {
  color: #1976d2;
  font-weight: 600;
}

.page-body {
  padding: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.table-scroll {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.inline-error {
  background: #ffebee;
  border: 1px solid #ef5350;
  color: #c62828;
  padding: 8px 12px;
  border-radius: 2px;
  margin: 12px 16px;
  font-size: 12px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  min-width: 840px;
}

.table th,
.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #e0e0e0;
  text-align: left;
  font-size: 12px;
  color: #000;
  vertical-align: middle;
}

.table th:first-child,
.table td:first-child {
  padding-left: 16px;
}

.table thead th {
  background: #fafafa;
  color: #000;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
  font-size: 12px;
}

.check-col {
  text-align: center;
}

.row-select-cell {
  text-align: center;
}

.row-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #1f6feb;
  transition: transform 0.15s ease;
}

.row-checkbox:hover {
  transform: scale(1.1);
}

.row-checkbox:checked {
  transform: scale(1.05);
}

.data-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.data-row:hover {
  background: #f5f5f5;
}

.data-row.is-selected {
  background: #e3f2fd;
}

.data-row.is-selected:hover {
  background: #bbdefb;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 16px 10px;
}

.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 180px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.tag {
  display: inline-flex;
  align-items: center;
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 2px;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 600;
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

.btn:active:not(:disabled) {
  background: #efefef;
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

.btn-danger {
  color: #d32f2f;
  border-color: #ef5350;
  background: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #ffebee;
  border-color: #e53935;
}

.btn-danger.is-locked {
  opacity: 0.7;
}

.btn-secondary {
  background: #fff;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}

.link-btn {
  border: none;
  padding: 0;
  background: transparent;
  color: #1f6feb;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.link-btn::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -2px;
  width: 0;
  height: 2px;
  background: #1f6feb;
  transition: width 0.2s ease;
}

.link-btn:hover {
  color: #1a5cd7;
}

.link-btn:hover::after {
  width: 100%;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
  flex-shrink: 0;
}

.pager-meta {
  font-size: 12px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pager-split {
  color: #ccc;
}

.toast {
  position: fixed;
  right: 20px;
  bottom: 20px;
  padding: 12px 16px;
  border-radius: 2px;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.2), 0 4px 12px rgba(15, 23, 42, 0.15);
  font-size: 13px;
  font-weight: 600;
  z-index: 9999;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
}

.toast.error {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  border-color: rgba(255, 255, 255, 0.2);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-enter-from {
  transform: translateY(10px) scale(0.95);
  opacity: 0;
}

.inline-input {
  width: 100%;
  border: 2px solid #1f6feb;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  color: #0f172a;
  background: #fff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.1);
}

.inline-input:focus {
  outline: none;
  border-color: #1a5cd7;
}

.new-row {
  background: linear-gradient(90deg, #f0f9ff 0%, #ffffff 100%);
  border-left: 3px solid #1f6feb;
}

.new-row-hint {
  color: #64748b;
  font-size: 12px;
  font-style: italic;
}

.hint-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 10010;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.dialog {
  width: min(520px, 100%);
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.3), 0 8px 24px rgba(15, 23, 42, 0.2);
  overflow: hidden;
  animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.dialog.danger {
  max-width: 460px;
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
  width: 34px;
  height: 34px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  color: #334155;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-close:hover {
  background: #f1f5f9;
  border-color: #94a3b8;
  transform: rotate(90deg);
}

.dialog-body {
  padding: 14px;
  color: #334155;
  font-size: 13px;
}

.delete-list {
  margin-top: 8px;
  color: #475569;
  line-height: 1.5;
  word-break: break-all;
}

.dialog-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: #475569;
  font-weight: 700;
}

.dialog-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }
  .search-wrap {
    width: 100%;
    min-width: 0;
  }
  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
