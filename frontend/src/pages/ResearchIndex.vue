<template>
  <div class="research-page">
    <div class="page-container">
      <div class="page-header">
        <div class="title-section">
          <h2>研究管理</h2>
          <span class="meta">{{ filteredRows.length }} 条</span>
        </div>

        <div class="actions-section">
          <div class="search-wrap">
            <input
              v-model.trim="keyword"
              class="text-input"
              type="text"
              placeholder="搜索研究 ID / 标题"
            >
          </div>

          <button class="btn btn-secondary" :disabled="loading" @click="fetchList(false)">
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
          <button class="btn btn-danger" :disabled="deleteSubmitting || !selectedIds.length" @click="openBatchDeleteModal">
            {{ deleteSubmitting ? '删除中...' : `批量删除（${selectedIds.length}）` }}
          </button>
          <button class="btn btn-primary" @click="handleCreateResearch">
            新建研究
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
                <th style="width: 5%" class="center">
                  <input
                    type="checkbox"
                    :checked="isAllPagedSelected"
                    @change="toggleSelectAllPaged"
                    @click.stop
                  >
                </th>
                <th style="width: 24%">研究名称</th>
                <th style="width: 14%">会话状态</th>
                <th style="width: 14%">创建时间</th>
                <th style="width: 14%">最后修改</th>
                <th style="width: 14%">研究 ID</th>
                <th style="width: 20%">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="editingNewRow" class="new-row">
                <td class="center"></td>
                <td>
                  <input
                    ref="newResearchInput"
                    v-model.trim="newResearchTitle"
                    class="text-input"
                    type="text"
                    placeholder="输入研究名称"
                    @keydown="handleNewResearchKeydown"
                  >
                </td>
                <td colspan="3" class="new-row-hint">
                  <span class="hint-text">输入研究名称后点击确认</span>
                </td>
                <td class="row-actions">
                  <button class="btn btn-mini btn-primary" type="button" @click="confirmNewResearch">确认</button>
                  <button class="btn btn-mini btn-secondary" type="button" @click="cancelNewResearch">取消</button>
                </td>
              </tr>
              <tr v-if="!pagedRows.length && !editingNewRow">
                <td colspan="7" class="empty-cell">
                  {{ loading ? '加载中...' : '暂无研究（可点击"新建研究"）' }}
                </td>
              </tr>
              <tr
                v-for="row in pagedRows"
                :key="row.id"
                class="data-row"
                @click="handleRowClick(row)"
              >
                <td class="center" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isSelected(row.id)"
                    @change="toggleRowSelection(row.id, $event)"
                  >
                </td>
                <td>{{ row.title || '-' }}</td>
                <td>
                  <span
                    v-if="row.session_status"
                    class="session-chip"
                    :class="sessionStatusClass(row.session_status)"
                  >
                    {{ row.session_status }}
                  </span>
                  <span v-else>--</span>
                </td>
                <td>{{ formatMetaDate(row.created_at) }}</td>
                <td>{{ formatMetaDate(row.updated_at || row.created_at) }}</td>
                <td class="mono muted-id">{{ row.id }}</td>
                <td class="row-actions" @click.stop>
                  <button
                    v-if="isSessionRunning(row.session_status)"
                    class="btn btn-mini btn-warning"
                    type="button"
                    :disabled="isTerminating(row.id)"
                    @click.stop="handleTerminateSession(row)"
                  >
                    {{ isTerminating(row.id) ? '结束中...' : '结束会话' }}
                  </button>
                  <button class="btn btn-mini btn-secondary" type="button" @click.stop="goNotebook(row.id)">编辑</button>
                  <button
                    class="btn btn-mini btn-danger"
                    type="button"
                    :disabled="deleteSubmitting || isTerminating(row.id)"
                    @click.stop="handleDelete(row)"
                  >
                    {{ deleteSubmitting && pendingDeleteIds.includes(row.id) ? '删除中...' : '删除' }}
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

    <div v-if="showFormModal" class="dialog-overlay" @click.self="closeFormModal">
      <div class="dialog">
        <div class="dialog-header">
          <h3>新建研究</h3>
          <button class="dialog-close" type="button" @click="closeFormModal">×</button>
        </div>

        <div class="dialog-body">
          <div class="form-grid two-col">
            <div class="field-row">
              <label for="research-title-input">研究名称</label>
              <input
                id="research-title-input"
                v-model.trim="formDraft.title"
                class="text-input"
                type="text"
                placeholder="例如：因子轮动研究"
              >
            </div>
            <div class="field-row">
              <label for="research-id-input">研究 ID（系统生成）</label>
              <input
                id="research-id-input"
                :value="formDraft.id"
                class="text-input id-input"
                type="text"
                disabled
                readonly
              >
            </div>
          </div>

          <div class="field-row">
            <label for="research-desc-input">描述</label>
            <textarea
              id="research-desc-input"
              v-model.trim="formDraft.description"
              class="text-area"
              rows="4"
              placeholder="补充研究目标、调试入口、注意事项"
            ></textarea>
          </div>

          <div v-if="formError" class="inline-error form-error">{{ formError }}</div>
        </div>

        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeFormModal">取消</button>
          <button class="btn btn-primary" type="button" :disabled="formSubmitting" @click="submitForm">
            {{ formSubmitting ? '提交中...' : '创建' }}
          </button>
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
            确认删除研究 <span class="mono">「{{ pendingDeleteIds[0] }}」</span> 吗？删除后不可恢复。
          </p>
          <p v-else>
            确认删除选中的 <span class="mono">{{ pendingDeleteIds.length }}</span> 个研究吗？删除后不可恢复。
          </p>
          <p v-if="pendingDeleteIds.length > 1" class="delete-preview mono">
            {{ pendingDeletePreview }}
          </p>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeDeleteModal">取消</button>
          <button class="btn btn-danger" type="button" :disabled="deleteSubmitting" @click="confirmDelete">
            {{ deleteSubmitting ? '删除中...' : `确认删除（${pendingDeleteIds.length}）` }}
          </button>
        </div>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast" :class="toastType">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<script>
import {
  listResearches,
  createResearch,
  deleteResearch,
  getNotebookSession,
  stopNotebookSession
} from '@/api/research';

function normalizeTags(raw) {
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item || '').trim()).filter(Boolean);
  }
  if (typeof raw === 'string') {
    return raw
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function normalizeResearchRow(item) {
  const raw = item && typeof item === 'object' ? item : {};
  const id = String(raw.id || raw.research_id || raw.key || '').trim();
  if (!id) {
    return null;
  }
  const sessionStatus = String(
    raw.session_status
      || raw.notebook_session_status
      || raw.notebook_status
      || raw.sessionStatus
      || raw.notebookSessionStatus
      || raw.session?.status
      || raw.notebook_session?.status
      || ''
  ).trim().toUpperCase();

  return {
    id,
    title: String(raw.title || raw.name || raw.display_name || '').trim(),
    description: String(raw.description || raw.desc || '').trim(),
    notebook_path: String(raw.notebook_path || raw.notebookPath || raw.path || '').trim(),
    kernel: String(raw.kernel || raw.kernel_name || '').trim(),
    status: String(raw.status || 'DRAFT').trim().toUpperCase(),
    session_id: String(
      raw.session_id
        || raw.notebook_session_id
        || raw.session?.session_id
        || raw.notebook_session?.session_id
        || ''
    ).trim(),
    session_status: sessionStatus,
    tags: normalizeTags(raw.tags),
    created_at: raw.created_at || raw.createdAt || raw.ctime || '',
    updated_at: raw.updated_at || raw.updatedAt || raw.mtime || ''
  };
}

function normalizeResearchList(payload) {
  if (Array.isArray(payload)) {
    return payload.map(normalizeResearchRow).filter(Boolean);
  }

  const root = payload && typeof payload === 'object' ? payload : {};
  const candidates = [
    root.items,
    root.list,
    root.researches,
    root.rows,
    root.data
  ];

  for (let i = 0; i < candidates.length; i += 1) {
    if (Array.isArray(candidates[i])) {
      return candidates[i].map(normalizeResearchRow).filter(Boolean);
    }
  }

  return [];
}

const DEFAULT_KERNEL = 'python3';
const DEFAULT_STATUS = 'DRAFT';
const NOTEBOOK_DIR = 'research/notebooks';

function pad(value, width) {
  return String(value).padStart(width, '0');
}

function buildNotebookPathById(id) {
  return `${NOTEBOOK_DIR}/${id}.ipynb`;
}

function getDateStamp(date = new Date()) {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1, 2),
    pad(date.getDate(), 2)
  ].join('');
}

function parseSequenceByDate(id, dateStamp) {
  const match = new RegExp(`^res_${dateStamp}_(\\d{3})$`).exec(String(id || '').trim());
  if (!match) {
    return null;
  }
  const seq = Number(match[1]);
  return Number.isFinite(seq) ? seq : null;
}

function buildResearchIdByDate(dateStamp, seq) {
  return `res_${dateStamp}_${pad(seq, 3)}`;
}

function createDefaultForm() {
  return {
    id: '',
    title: '',
    description: '',
    notebook_path: '',
    kernel: DEFAULT_KERNEL,
    status: DEFAULT_STATUS,
    tagsText: ''
  };
}

function toTimestamp(value) {
  const ts = new Date(value || '').getTime();
  return Number.isFinite(ts) ? ts : 0;
}

function padDatePart(value) {
  return String(value).padStart(2, '0');
}

function formatDateMinute(value) {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  const year = date.getFullYear();
  const month = padDatePart(date.getMonth() + 1);
  const day = padDatePart(date.getDate());
  const hour = padDatePart(date.getHours());
  const minute = padDatePart(date.getMinutes());
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function extractSessionId(payload) {
  const raw = payload && typeof payload === 'object' ? payload : {};
  const root = raw.session && typeof raw.session === 'object'
    ? raw.session
    : (raw.notebook_session && typeof raw.notebook_session === 'object'
      ? raw.notebook_session
      : raw);
  const direct = String(root.session_id || '').trim();
  if (direct) {
    return direct;
  }
  const nested = String(
    root.session?.session_id
      || root.notebook_session?.session_id
      || raw.session_id
      || raw.notebook_session_id
      || ''
  ).trim();
  if (nested) {
    return nested;
  }
  const legacyId = String(root.id || '').trim();
  return legacyId;
}

export default {
  name: 'ResearchIndex',
  data() {
    return {
      loading: false,
      errorMessage: '',
      keyword: '',
      rows: [],
      currentPage: 1,
      pageSize: 10,
      showFormModal: false,
      formSubmitting: false,
      formDraft: createDefaultForm(),
      formError: '',
      showDeleteModal: false,
      deleteSubmitting: false,
      pendingDeleteIds: [],
      selectedIds: [],
      terminatingIds: [],
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null,
      editingNewRow: false,
      newResearchTitle: ''
    };
  },
  computed: {
    filteredRows() {
      const keyword = String(this.keyword || '').trim().toLowerCase();
      if (!keyword) {
        return this.rows;
      }
      return this.rows.filter((row) => {
        const haystack = [
          row.id,
          row.title,
          row.session_status,
          ...(row.tags || [])
        ]
          .join(' ')
          .toLowerCase();
        return haystack.includes(keyword);
      });
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.filteredRows.length / this.pageSize));
    },
    pagedRows() {
      const page = Math.min(this.currentPage, this.totalPages);
      const start = (Math.max(1, page) - 1) * this.pageSize;
      return this.filteredRows.slice(start, start + this.pageSize);
    },
    pagedRowIds() {
      return this.pagedRows.map((row) => row.id);
    },
    isAllPagedSelected() {
      if (!this.pagedRowIds.length) {
        return false;
      }
      return this.pagedRowIds.every((id) => this.selectedIds.includes(id));
    },
    pendingDeletePreview() {
      if (!this.pendingDeleteIds.length) {
        return '';
      }
      const preview = this.pendingDeleteIds.slice(0, 8).join('、');
      if (this.pendingDeleteIds.length <= 8) {
        return preview;
      }
      return `${preview} 等 ${this.pendingDeleteIds.length} 个`;
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
      }
      return (error && error.message) || fallback;
    },
    formatMetaDate(value) {
      return formatDateMinute(value);
    },
    isSessionRunning(status) {
      return String(status || '').trim().toUpperCase() === 'RUNNING';
    },
    isTerminating(id) {
      const researchId = String(id || '').trim();
      return !!researchId && this.terminatingIds.includes(researchId);
    },
    async handleTerminateSession(row) {
      const researchId = String(row?.id || '').trim();
      if (!researchId || this.isTerminating(researchId)) {
        return;
      }
      this.terminatingIds = [...this.terminatingIds, researchId];
      try {
        let sessionId = String(row?.session_id || '').trim();
        try {
          if (!sessionId) {
            const sessionPayload = await getNotebookSession(researchId);
            sessionId = extractSessionId(sessionPayload);
          }
        } catch (error) {
          const status = Number(error?.response?.status || 0);
          if (status === 404) {
            this.showMessage('会话不存在/已过期');
            await this.fetchList(true);
            return;
          }
          throw error;
        }

        const stopPayload = {};
        if (sessionId) {
          stopPayload.session_id = sessionId;
        }

        await stopNotebookSession(researchId, stopPayload);
        this.showMessage(`研究 ${researchId} 会话已结束`);
        await this.fetchList(true);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '结束会话失败'), 'error');
      } finally {
        this.terminatingIds = this.terminatingIds.filter((id) => id !== researchId);
      }
    },
    sessionStatusClass(status) {
      const text = String(status || '').trim().toUpperCase();
      if (!text) {
        return 'is-idle';
      }
      if (text === 'RUNNING' || text === 'ACTIVE') {
        return 'is-running';
      }
      if (text === 'STOPPED' || text === 'TERMINATED' || text === 'CLOSED' || text === 'INACTIVE') {
        return 'is-stopped';
      }
      if (text === 'FAILED' || text === 'ERROR') {
        return 'is-error';
      }
      if (text === 'STARTING' || text === 'PENDING' || text === 'CREATING') {
        return 'is-pending';
      }
      return 'is-idle';
    },
    goNotebook(id) {
      const researchId = String(id || '').trim();
      if (!researchId) {
        return;
      }
      this.$router.push({ name: 'research-notebook', params: { id: researchId } });
    },
    handleRowClick(row) {
      this.goNotebook(row?.id);
    },
    isIdTaken(id, excludeId = '') {
      const currentId = String(id || '').trim();
      if (!currentId) {
        return false;
      }
      return this.rows.some((row) => row.id === currentId && row.id !== excludeId);
    },
    isNotebookPathTaken(path, excludeId = '') {
      const currentPath = String(path || '').trim();
      if (!currentPath) {
        return false;
      }
      return this.rows.some((row) => row.notebook_path === currentPath && row.id !== excludeId);
    },
    getNextSequenceForDate(dateStamp) {
      let maxSeq = 0;
      this.rows.forEach((row) => {
        const seq = parseSequenceByDate(row.id, dateStamp);
        if (seq && seq > maxSeq) {
          maxSeq = seq;
        }
      });
      return maxSeq + 1;
    },
    generateUniqueIdentity(offset = 0) {
      const dateStamp = getDateStamp(new Date());
      let seq = this.getNextSequenceForDate(dateStamp) + Number(offset || 0);
      for (let attempt = 0; attempt < 999; attempt += 1) {
        const id = buildResearchIdByDate(dateStamp, seq + attempt);
        if (this.isIdTaken(id)) {
          continue;
        }
        const notebookPath = buildNotebookPathById(id);
        if (this.isNotebookPathTaken(notebookPath)) {
          continue;
        }
        return {
          id,
          notebook_path: notebookPath,
          kernel: DEFAULT_KERNEL,
          status: DEFAULT_STATUS
        };
      }
      throw new Error('自动生成研究 ID 失败，请重试');
    },
    refreshGeneratedFields(offset = 0) {
      const generated = this.generateUniqueIdentity(offset);
      this.formDraft = {
        ...this.formDraft,
        ...generated
      };
    },
    handleCreateResearch() {
      this.editingNewRow = true;
      this.newResearchTitle = '';
      this.$nextTick(() => {
        this.$refs.newResearchInput?.focus();
      });
    },
    cancelNewResearch() {
      this.editingNewRow = false;
      this.newResearchTitle = '';
    },
    async confirmNewResearch() {
      const title = String(this.newResearchTitle || '').trim();
      if (!title) {
        this.cancelNewResearch();
        return;
      }

      this.editingNewRow = false;

      // 生成研究ID和路径
      const dateStamp = getDateStamp(new Date());
      const seq = this.getNextSequenceForDate(dateStamp);
      const id = buildResearchIdByDate(dateStamp, seq);
      const notebookPath = buildNotebookPathById(id);

      // 创建研究记录
      try {
        const payload = {
          id,
          title,
          description: '',
          notebook_path: notebookPath,
          kernel: DEFAULT_KERNEL,
          status: DEFAULT_STATUS,
          tags: []
        };
        await createResearch(payload);
        this.showMessage(`研究 ${id} 创建成功`);
        await this.fetchList(true);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '创建研究失败'), 'error');
      }
    },
    handleNewResearchKeydown(event) {
      if (event.key === 'Enter') {
        this.confirmNewResearch();
      } else if (event.key === 'Escape') {
        this.cancelNewResearch();
      }
    },
    openCreateModal() {
      this.formDraft = createDefaultForm();
      this.refreshGeneratedFields();
      this.formError = '';
      this.showFormModal = true;
    },
    closeFormModal() {
      if (this.formSubmitting) {
        return;
      }
      this.showFormModal = false;
      this.formError = '';
    },
    validateForm() {
      const id = String(this.formDraft.id || '').trim();
      if (!id) {
        return '研究 ID 不能为空';
      }
      if (this.isIdTaken(id)) {
        return '系统生成的研究 ID 与已有数据冲突，请重试';
      }
      const notebookPath = String(this.formDraft.notebook_path || '').trim();
      if (!notebookPath) {
        return 'Notebook 路径不能为空';
      }
      if (this.isNotebookPathTaken(notebookPath)) {
        return 'Notebook 路径已存在，请重试';
      }
      return '';
    },
    buildFormPayload() {
      const normalizedStatus = String(this.formDraft.status || DEFAULT_STATUS).trim().toUpperCase() || DEFAULT_STATUS;
      return {
        id: String(this.formDraft.id || '').trim(),
        title: String(this.formDraft.title || '').trim(),
        description: String(this.formDraft.description || '').trim(),
        notebook_path: String(this.formDraft.notebook_path || '').trim(),
        kernel: DEFAULT_KERNEL,
        status: normalizedStatus,
        tags: normalizeTags(this.formDraft.tagsText)
      };
    },
    async submitForm() {
      const validationError = this.validateForm();
      if (validationError) {
        this.formError = validationError;
        return;
      }

      this.formSubmitting = true;
      this.formError = '';
      try {
        let createdPayload = this.buildFormPayload();
        let created = false;
        let lastError = null;
        for (let attempt = 0; attempt < 5; attempt += 1) {
          if (attempt > 0) {
            this.refreshGeneratedFields(attempt);
            createdPayload = this.buildFormPayload();
          }
          try {
            await createResearch(createdPayload);
            created = true;
            break;
          } catch (error) {
            lastError = error;
            const status = Number(error?.response?.status || 0);
            const errorText = this.getErrorMessage(error, '').toLowerCase();
            const duplicated = status === 409 || errorText.includes('已存在') || errorText.includes('duplicate');
            if (!duplicated || attempt >= 4) {
              throw error;
            }
          }
        }
        if (!created) {
          throw lastError || new Error('创建研究失败');
        }
        this.showMessage(`研究 ${createdPayload.id} 创建成功`);

        this.showFormModal = false;
        await this.fetchList(true);
      } catch (error) {
        this.formError = this.getErrorMessage(error, '创建研究失败');
      } finally {
        this.formSubmitting = false;
      }
    },
    isSelected(id) {
      const currentId = String(id || '').trim();
      return currentId && this.selectedIds.includes(currentId);
    },
    toggleRowSelection(id, event) {
      const currentId = String(id || '').trim();
      if (!currentId) {
        return;
      }
      const checked = Boolean(event?.target?.checked);
      if (checked) {
        if (!this.selectedIds.includes(currentId)) {
          this.selectedIds = [...this.selectedIds, currentId];
        }
        return;
      }
      this.selectedIds = this.selectedIds.filter((item) => item !== currentId);
    },
    toggleSelectAllPaged(event) {
      const checked = Boolean(event?.target?.checked);
      const pageIds = this.pagedRowIds;
      if (!pageIds.length) {
        return;
      }
      if (checked) {
        const merged = new Set([...this.selectedIds, ...pageIds]);
        this.selectedIds = [...merged];
        return;
      }
      const pageSet = new Set(pageIds);
      this.selectedIds = this.selectedIds.filter((id) => !pageSet.has(id));
    },
    openBatchDeleteModal() {
      if (!this.selectedIds.length || this.deleteSubmitting) {
        return;
      }
      this.pendingDeleteIds = [...this.selectedIds];
      this.showDeleteModal = true;
    },
    handleDelete(row) {
      const targetId = String(row?.id || '').trim();
      if (!targetId) {
        return;
      }
      this.pendingDeleteIds = [targetId];
      this.showDeleteModal = true;
    },
    closeDeleteModal() {
      if (this.deleteSubmitting) {
        return;
      }
      this.showDeleteModal = false;
      this.pendingDeleteIds = [];
    },
    async confirmDelete() {
      const targetIds = [...new Set(
        this.pendingDeleteIds
          .map((id) => String(id || '').trim())
          .filter(Boolean)
      )];
      if (!targetIds.length) {
        return;
      }

      this.deleteSubmitting = true;
      try {
        const results = await Promise.allSettled(
          targetIds.map((id) => deleteResearch(id))
        );
        const successIds = [];
        const failedIds = [];
        results.forEach((result, idx) => {
          const id = targetIds[idx];
          if (result.status === 'fulfilled') {
            successIds.push(id);
            return;
          }
          failedIds.push(id);
        });

        if (successIds.length) {
          const successSet = new Set(successIds);
          this.rows = this.rows.filter((item) => !successSet.has(item.id));
          this.selectedIds = this.selectedIds.filter((id) => !successSet.has(id));
        }

        this.showDeleteModal = false;
        this.pendingDeleteIds = [];

        if (!failedIds.length) {
          if (successIds.length === 1) {
            this.showMessage(`研究 ${successIds[0]} 已删除`);
          } else {
            this.showMessage(`已删除 ${successIds.length} 个研究`);
          }
          return;
        }

        if (successIds.length) {
          this.showMessage(`已删除 ${successIds.length} 个研究，${failedIds.length} 个删除失败`, 'error');
          return;
        }
        this.showMessage(`删除失败（共 ${failedIds.length} 个）`, 'error');
      } finally {
        this.deleteSubmitting = false;
      }
    },
    async fetchList(silent = true) {
      this.loading = true;
      this.errorMessage = '';
      try {
        const data = await listResearches();
        const list = normalizeResearchList(data);
        // 按最后修改时间倒序排列，最新的在前面
        this.rows = [...list].sort((a, b) => {
          const tsA = toTimestamp(a.updated_at || a.created_at);
          const tsB = toTimestamp(b.updated_at || b.created_at);
          const delta = tsB - tsA;
          if (delta !== 0) {
            return delta;
          }
          return String(a.id).localeCompare(String(b.id));
        });
        const validIds = new Set(this.rows.map((row) => row.id));
        this.selectedIds = this.selectedIds.filter((id) => validIds.has(id));
      } catch (error) {
        if (!silent) {
          this.errorMessage = this.getErrorMessage(error, '获取研究列表失败');
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
.research-page {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.page-container {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
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

.page-body {
  padding: 0;
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

.inline-error {
  background: #ffebee;
  border: 1px solid #ef5350;
  color: #c62828;
  padding: 8px 12px;
  border-radius: 2px;
  margin: 12px 16px;
  font-size: 12px;
}

.table-scroll {
  overflow: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1120px;
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

.table thead th {
  background: #fafafa;
  color: #000;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
  font-size: 12px;
}

.data-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.data-row:hover {
  background: #f5f5f5;
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

.btn-danger {
  color: #d32f2f;
  border-color: #ef5350;
  background: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #ffebee;
  border-color: #e53935;
}

.btn-warning {
  color: #f57c00;
  border-color: #ff9800;
  background: #fff;
}

.btn-warning:hover:not(:disabled) {
  background: #fff3e0;
  border-color: #f57c00;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}

.row-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
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

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.36);
  display: grid;
  place-items: center;
  z-index: 1000;
}

.dialog {
  width: min(740px, calc(100vw - 28px));
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.dialog.danger {
  width: min(460px, calc(100vw - 28px));
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.dialog-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.dialog-close {
  border: 0;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: #666;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-close:hover {
  color: #000;
}

.dialog-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-row label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dialog-footer {
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  background: #fafafa;
}

.text-area {
  width: 100%;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
  padding: 8px;
  font-size: 12px;
  color: #000;
  background: #fff;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.15s ease;
}

.text-area:hover {
  border-color: #999;
}

.text-area:focus {
  outline: none;
  border-color: #1976d2;
}

.session-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
}

.session-chip.is-running {
  color: #2e7d32;
  background: #e8f5e9;
  border-color: #66bb6a;
}

.session-chip.is-stopped {
  color: #666;
  background: #f5f5f5;
  border-color: #d0d0d0;
}

.session-chip.is-error {
  color: #d32f2f;
  background: #ffebee;
  border-color: #ef5350;
}

.session-chip.is-pending {
  color: #f57c00;
  background: #fff3e0;
  border-color: #ffb74d;
}

.session-chip.is-idle {
  color: #666;
  background: #fafafa;
  border-color: #e0e0e0;
}

.toast {
  position: fixed;
  right: 18px;
  bottom: 18px;
  min-width: 180px;
  max-width: 360px;
  border-radius: 10px;
  padding: 10px 12px;
  color: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.24);
  z-index: 1200;
}

.toast.success {
  background: #16a34a;
}

.toast.error {
  background: #dc2626;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .search-wrap {
    min-width: 0;
    flex: 1;
  }

  .form-grid.two-col,
  .form-grid.three-col {
    grid-template-columns: 1fr;
  }
}
</style>
