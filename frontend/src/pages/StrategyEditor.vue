<template>
  <div class="editor-page">
    <header class="page-header">
      <div class="title">
        <div class="title-row">
          <h2>策略编辑</h2>
          <span class="tag">Python</span>
          <span class="mono id-chip">{{ strategyId || '-' }}</span>
        </div>
        <div class="sub">
          左侧编辑代码，右侧查看运行输出；点击“运行回测”配置参数并跳转回测结果页。
        </div>
      </div>

      <div class="header-actions">
        <div class="action-group action-group-nav">
          <button class="btn btn-ghost" type="button" @click="goBack">
            返回列表
          </button>
          <button class="btn btn-ghost" type="button" :disabled="!strategyId" @click="goHistory">
            历史回测
          </button>
        </div>
        <div class="action-group action-group-edit">
          <button class="btn btn-secondary" type="button" :disabled="renaming || !strategyId" @click="openRenameModal">
            {{ renaming ? '改名中...' : '修改策略名' }}
          </button>
          <button class="btn btn-secondary" type="button" :disabled="saving" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button class="btn btn-secondary" type="button" :disabled="compiling || !strategyId" @click="handleCompile">
            {{ compiling ? '编译中...' : '编译调试' }}
          </button>
        </div>
        <div class="action-group action-group-run">
          <button class="btn btn-primary btn-run" type="button" :disabled="!strategyId" @click="showParam = true">
            运行回测
          </button>
        </div>
      </div>
    </header>

    <section class="content">
      <div class="left">
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <h3>代码</h3>
              <span class="meta">{{ codeSizeText }}</span>
            </div>
            <div class="meta">
              <span v-if="loading" class="meta">加载中...</span>
            </div>
          </div>
          <div class="card-body">
            <PythonCodeEditor v-model="code" :min-height="560" />
          </div>
        </div>
      </div>

      <div class="right">
        <ResizableSidePanel v-model:width="panelWidth" :collapsed="panelCollapsed" @toggle="panelCollapsed = !panelCollapsed">
          <template #title>
            <div class="panel-title">
              <span>调试 / 输出</span>
              <span v-if="lastRunId" class="mono run-chip" title="最近回测任务 ID">{{ lastRunId }}</span>
            </div>
          </template>

          <div class="output">
            <div class="output-toolbar">
              <button class="btn btn-mini btn-secondary" type="button" :disabled="!lastRunId || loadingLog" @click="fetchLatestLog">
                {{ loadingLog ? '拉取中...' : '拉取日志' }}
              </button>
              <button class="btn btn-mini btn-secondary" type="button" @click="clearOutput">清空</button>
            </div>
            <pre class="log">{{ outputText }}</pre>
          </div>
        </ResizableSidePanel>
      </div>
    </section>

    <BacktestParamModal
      v-if="showParam"
      :submitting="starting"
      :default-params="defaultParams"
      @close="showParam = false"
      @confirm="startBacktest"
    />

    <div v-if="showSaveConfirm" class="dialog-overlay" @click.self="closeSaveConfirm">
      <div class="dialog">
        <div class="dialog-header">
          <h3>保存确认</h3>
          <button class="dialog-close" type="button" @click="closeSaveConfirm">×</button>
        </div>
        <div class="dialog-body">
          <p>确认保存策略 <span class="mono">「{{ strategyId }}」</span> 吗？</p>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeSaveConfirm">取消</button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="confirmSave">
            {{ saving ? '保存中...' : '确认保存' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showRenameModal" class="dialog-overlay">
      <div class="dialog">
        <div class="dialog-header">
          <h3>修改策略名称</h3>
          <button class="dialog-close" type="button" @click="closeRenameModal">×</button>
        </div>
        <div class="dialog-body">
          <label for="rename-strategy-input" class="dialog-label">新策略名称</label>
          <input
            id="rename-strategy-input"
            v-model.trim="renameDraftId"
            class="text-input"
            type="text"
            placeholder="例如：策略A_2026"
            @keyup.enter="confirmRename"
          >
          <div class="dialog-tip">支持中文、字母、数字、下划线和中横线，不能包含空格。</div>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-secondary" type="button" @click="closeRenameModal">取消</button>
          <button class="btn btn-primary" type="button" :disabled="renaming" @click="confirmRename">
            {{ renaming ? '修改中...' : '确认修改' }}
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
import PythonCodeEditor from '@/components/PythonCodeEditor.vue';
import BacktestParamModal from '@/components/BacktestParamModal.vue';
import ResizableSidePanel from '@/components/ResizableSidePanel.vue';
import { getStrategy, saveStrategy, renameStrategy, compileStrategy, runBacktest, getLog } from '@/api/backtest';
import { normalizeCodePayload } from '@/utils/strategyNormalize';
import { mergeLocalStrategyId, renameLocalStrategyId } from '@/utils/backtestStrategies';
import { upsertBacktestRunSummary, renameBacktestRunStrategyId } from '@/stores/backtestRunStore';
import {
  getStrategyRenameMap,
  resolveCurrentStrategyId,
  syncStrategyRenameMap
} from '@/utils/strategyRenameMap';

const DEFAULT_TEMPLATE = `# RQAlpha 默认策略示例
from rqalpha.api import *

def init(context):
    # 选择一个股票（平安银行）
    context.s1 = "000001.XSHE"

def handle_bar(context, bar_dict):
    # 如果当前没有持仓
    position = context.portfolio.positions[context.s1]

    if position.quantity == 0:
        # 用全部资金买入
        order_percent(context.s1, 1.0)
`;
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

function normalizeCompilePayload(payload) {
  const rootPayload = unwrapDataPayload(payload);
  const root = rootPayload && typeof rootPayload === 'object'
    ? (rootPayload.result && typeof rootPayload.result === 'object'
      ? rootPayload.result
      : (rootPayload.compile_result && typeof rootPayload.compile_result === 'object'
        ? rootPayload.compile_result
        : rootPayload))
    : null;

  if (!root || typeof root !== 'object') {
    return {
      ok: false,
      stdout: '',
      stderr: '',
      diagnostics: []
    };
  }

  const diagnosticsSource = Array.isArray(root.diagnostics)
    ? root.diagnostics
    : (Array.isArray(root.errors)
      ? root.errors
      : (Array.isArray(root.messages) ? root.messages : []));

  const diagnostics = diagnosticsSource.map((item) => {
    const line = Number(item?.line ?? item?.lineno ?? item?.line_no ?? item?.row);
    const column = Number(item?.column ?? item?.col ?? item?.column_no);
    const rawLevel = String(item?.level || item?.severity || item?.type || 'INFO').toUpperCase();
    const message = String(item?.message || item?.msg || item?.text || '').trim();
    return {
      line: Number.isFinite(line) ? line : null,
      column: Number.isFinite(column) ? column : null,
      level: rawLevel,
      message
    };
  }).filter((item) => item.message);

  const stdout = typeof root.stdout === 'string'
    ? root.stdout
    : (typeof root.output === 'string'
      ? root.output
      : (typeof root.message === 'string' ? root.message : ''));
  let stderr = '';
  if (typeof root.stderr === 'string') {
    stderr = root.stderr;
  } else if (typeof root.error === 'string') {
    stderr = root.error;
  } else if (root.error && typeof root.error === 'object' && typeof root.error.message === 'string') {
    stderr = root.error.message;
  } else if (typeof root.error_message === 'string') {
    stderr = root.error_message;
  }

  const ok = root.ok !== undefined
    ? root.ok !== false
    : (root.success !== undefined
      ? root.success !== false
      : (!stderr && diagnostics.every((item) => item.level !== 'ERROR')));

  return {
    ok,
    stdout,
    stderr,
    diagnostics
  };
}

export default {
  name: 'StrategyEditor',
  components: {
    PythonCodeEditor,
    BacktestParamModal,
    ResizableSidePanel
  },
  data() {
    return {
      strategyId: '',
      code: DEFAULT_TEMPLATE,
      loading: false,
      saving: false,
      compiling: false,
      starting: false,
      showParam: false,
      showSaveConfirm: false,
      showRenameModal: false,
      renaming: false,
      renameDraftId: '',
      defaultParams: {},
      panelWidth: 440,
      panelCollapsed: false,
      outputText: '未运行\\n',
      lastRunId: '',
      loadingLog: false,
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null
    };
  },
  computed: {
    codeSizeText() {
      return `${(this.code || '').length} 字符`;
    }
  },
  watch: {
    '$route.params.id': {
      immediate: true,
      handler(value) {
        this.strategyId = String(value || '').trim();
        this.loadStrategy();
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
        return data.message || data.error || fallback;
      }
      return (error && error.message) || fallback;
    },
    normalizeStrategyId(value) {
      return String(value || '').trim();
    },
    validateStrategyId(id) {
      if (!id) {
        return '策略 ID 不能为空';
      }
      if (/\s/.test(id)) {
        return '策略 ID 不能包含空白字符';
      }
      if (!/^[A-Za-z0-9_\-\u4E00-\u9FFF]+$/.test(id)) {
        return '策略 ID 仅支持中文、字母、数字、下划线和中横线';
      }
      return '';
    },
    appendOutput(text) {
      const incoming = String(text || '').trim();
      if (!incoming) {
        return;
      }
      const current = String(this.outputText || '').trim();
      if (!current || current === '未运行') {
        this.outputText = `${incoming}\n`;
        return;
      }
      this.outputText = `${current}\n\n${incoming}\n`;
    },
    formatDiagnostics(diagnostics) {
      if (!Array.isArray(diagnostics) || !diagnostics.length) {
        return '无';
      }
      return diagnostics.map((item, index) => {
        const line = Number(item?.line);
        const column = Number(item?.column);
        const level = String(item?.level || 'INFO').toUpperCase();
        const message = String(item?.message || '').trim() || '-';
        const lineText = Number.isFinite(line) && line > 0 ? line : '-';
        const colText = Number.isFinite(column) && column > 0 ? column : '-';
        return `${index + 1}. [${level}] 行 ${lineText}, 列 ${colText}: ${message}`;
      }).join('\n');
    },
    goBack() {
      this.$router.push({ name: 'strategies' });
    },
    goHistory() {
      this.$router.push({
        name: 'backtest-history',
        query: {
          strategy_id: this.strategyId,
          job_id: this.lastRunId || undefined
        }
      });
    },
    async loadStrategy() {
      const rawId = this.normalizeStrategyId(this.strategyId);
      if (!rawId) {
        return;
      }
      await syncStrategyRenameMap();

      const canonicalId = resolveCurrentStrategyId(rawId, getStrategyRenameMap()) || rawId;
      if (canonicalId !== rawId) {
        this.strategyId = canonicalId;
        this.$router.replace({ name: 'strategy-edit', params: { id: canonicalId } });
        return;
      }
      const id = canonicalId;

      this.loading = true;
      try {
        const data = await getStrategy(id);
        const loaded = normalizeCodePayload(data);
        if (loaded) {
          this.code = loaded;
        } else {
          this.code = DEFAULT_TEMPLATE;
        }
        mergeLocalStrategyId(id);
      } catch (error) {
        const status = error && error.response && error.response.status;
        if (status === 404) {
          this.code = DEFAULT_TEMPLATE;
        } else {
          this.code = DEFAULT_TEMPLATE;
          this.showMessage(this.getErrorMessage(error, '策略加载失败，已使用模板'), 'error');
        }
      } finally {
        this.loading = false;
      }
    },
    openRenameModal() {
      const id = this.normalizeStrategyId(this.strategyId);
      if (!id) {
        this.showMessage('缺少策略 ID', 'error');
        return;
      }
      this.renameDraftId = id;
      this.showRenameModal = true;
    },
    closeRenameModal(force = false) {
      if (this.renaming && !force) {
        return;
      }
      this.showRenameModal = false;
      this.renameDraftId = '';
    },
    async confirmRename() {
      const fromId = this.normalizeStrategyId(this.strategyId);
      const toId = this.normalizeStrategyId(this.renameDraftId);

      const invalidReason = this.validateStrategyId(toId);
      if (invalidReason) {
        this.showMessage(invalidReason, 'error');
        return;
      }
      if (fromId === toId) {
        this.showMessage('策略名称未变化');
        this.closeRenameModal();
        return;
      }

      this.renaming = true;
      try {
        let cleanupWarning = '';
        const renameRes = await renameStrategy(fromId, toId, {
          code: this.code || undefined
        });
        const payload = renameRes?.data && typeof renameRes.data === 'object' ? renameRes.data : renameRes;
        if (payload && typeof payload === 'object') {
          const warningText = String(payload.warning || payload.message || '').trim();
          if (warningText) {
            cleanupWarning = warningText;
          }
        }

        await syncStrategyRenameMap();
        renameLocalStrategyId(fromId, toId);
        renameBacktestRunStrategyId(fromId, toId);
        this.strategyId = toId;
        if (this.lastRunId) {
          upsertBacktestRunSummary(this.lastRunId, { strategyId: toId });
        }
        this.closeRenameModal(true);
        this.$router.replace({ name: 'strategy-edit', params: { id: toId } });
        const successMessage = cleanupWarning
          ? `修改成功：策略名称已更新为 ${toId}（${cleanupWarning}）`
          : `修改成功：策略名称已更新为 ${toId}`;
        this.showMessage(successMessage);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '策略名称修改失败'), 'error');
      } finally {
        this.renaming = false;
      }
    },
    handleSave() {
      const id = this.normalizeStrategyId(this.strategyId);
      if (!id) {
        this.showMessage('缺少策略 ID', 'error');
        return;
      }
      this.showSaveConfirm = true;
    },
    closeSaveConfirm() {
      if (this.saving) {
        return;
      }
      this.showSaveConfirm = false;
    },
    async confirmSave() {
      const id = this.normalizeStrategyId(this.strategyId);
      if (!id) return;
      this.saving = true;
      try {
        await saveStrategy(id, this.code || '');
        mergeLocalStrategyId(id);
        this.showSaveConfirm = false;
        this.showMessage('保存成功');
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '保存失败'), 'error');
      } finally {
        this.saving = false;
      }
    },
    async handleCompile() {
      const id = this.normalizeStrategyId(this.strategyId);
      if (!id) {
        this.showMessage('缺少策略 ID', 'error');
        return;
      }

      this.outputText = '';
      this.compiling = true;
      try {
        const data = await compileStrategy(id, { code: this.code || '' });
        const result = normalizeCompilePayload(data);
        const now = new Date().toLocaleString('zh-CN', { hour12: false });

        const diagnosticsText = this.formatDiagnostics(result.diagnostics);
        const section = [
          `[${now}] 编译调试：${id}`,
          `结果：${result.ok ? 'OK' : 'FAILED'}`,
          '',
          'STDOUT:',
          result.stdout || '(空)',
          '',
          'STDERR:',
          result.stderr || '(空)',
          '',
          'DIAGNOSTICS:',
          diagnosticsText
        ].join('\n');
        this.appendOutput(section);

        const hasDiagnostics = Array.isArray(result.diagnostics) && result.diagnostics.length > 0;
        if (!result.ok || result.stderr || hasDiagnostics) {
          this.showMessage('编译完成，发现问题，请查看输出', 'error');
        } else {
          this.showMessage('编译调试成功');
        }
      } catch (error) {
        const status = error && error.response && error.response.status;
        const now = new Date().toLocaleString('zh-CN', { hour12: false });
        const responseData = error && error.response ? error.response.data : null;
        const parsed = normalizeCompilePayload(responseData);
        const diagnosticsText = this.formatDiagnostics(parsed.diagnostics);
        const errorMessage = this.getErrorMessage(error, '编译调试失败');
        const section = [
          `[${now}] 编译调试：${id}`,
          '结果：FAILED',
          `HTTP状态：${Number.isFinite(status) ? status : 'N/A'}`,
          '',
          'ERROR:',
          errorMessage || '(空)',
          '',
          'STDOUT:',
          parsed.stdout || '(空)',
          '',
          'STDERR:',
          parsed.stderr || '(空)',
          '',
          'DIAGNOSTICS:',
          diagnosticsText
        ].join('\n');
        this.appendOutput(section);
        if (status === 404 || status === 405 || status === 501) {
          this.showMessage('后端暂未提供编译接口，请实现 POST /api/backtest/strategies/{id}/compile', 'error');
        } else {
          this.showMessage(errorMessage, 'error');
        }
      } finally {
        this.compiling = false;
      }
    },
    clearOutput() {
      this.outputText = '';
    },
    async fetchLatestLog() {
      if (!this.lastRunId) {
        return;
      }
      this.loadingLog = true;
      try {
        const data = await getLog(this.lastRunId);
        const text = (data && (data.log || data.data || data.text)) || data;
        this.outputText = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '获取日志失败'), 'error');
      } finally {
        this.loadingLog = false;
      }
    },
    async startBacktest(params) {
      const id = this.normalizeStrategyId(this.strategyId);
      if (!id) {
        return;
      }

      this.starting = true;
      try {
        const payload = {
          strategy_id: id,
          ...params
        };
        const data = await runBacktest(payload);
        const jobId = data && (data.job_id || data.jobId);
        if (!jobId) {
          throw new Error('回测任务返回缺少 job_id');
        }

        this.lastRunId = String(jobId);
        this.defaultParams = { ...params };
        this.outputText = `回测任务已提交：${jobId}\\n`;

        upsertBacktestRunSummary(String(jobId), {
          strategyId: id,
          params: { ...params }
        });

        this.showParam = false;
        this.$router.push({ name: 'backtest-result', params: { runId: String(jobId) } });
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '回测启动失败'), 'error');
      } finally {
        this.starting = false;
      }
    }
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
.editor-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(223, 231, 242, 0.7);
}

.title-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.title h2 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin-top: 6px;
  color: #5f6f86;
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.action-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #dbe3ef;
  background: #ffffff;
}

.action-group-nav {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.action-group-edit {
  background: #f8fbff;
  border-color: #dbeafe;
}

.action-group-run {
  padding: 0;
  border: none;
  background: transparent;
}

.content {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: stretch;
}

.left {
  min-width: 0;
}

.right {
  align-self: stretch;
}

.card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.card-header {
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #f6faff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.card-title h3 {
  margin: 0;
  font-size: 16px;
}

.meta {
  font-size: 12px;
  color: #5f6f86;
}

.card-body {
  padding: 12px;
}

.tag {
  display: inline-flex;
  align-items: center;
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 700;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.id-chip {
  background: #0f172a;
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #1f2937;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.16s ease;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn:not(:disabled):hover {
  border-color: #94a3b8;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}

.btn-ghost {
  border-color: #cbd5e1;
  background: #ffffff;
  color: #334155;
}

.btn-secondary {
  border-color: #bcd6ff;
  background: #eff6ff;
  color: #1e3a8a;
}

.btn-primary {
  background: #1f6feb;
  border-color: #1f6feb;
  color: #fff;
}

.btn-primary:not(:disabled):hover {
  border-color: #1d4ed8;
  background: #1d4ed8;
}

.btn-run {
  min-width: 110px;
  padding: 9px 16px;
  border-radius: 12px;
}

.btn-mini {
  padding: 6px 10px;
  border-radius: 9px;
  font-size: 12px;
}

.btn-danger {
  background: #ef4444;
  border-color: #ef4444;
  color: #fff;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 900;
  color: #0f172a;
}

.run-chip {
  background: #ecfeff;
  border: 1px solid #a5f3fc;
  color: #155e75;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.output-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.log {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  color: #0f172a;
  background: #0b1220;
  border-radius: 12px;
  padding: 10px 12px;
  min-height: 260px;
  color: #e5e7eb;
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 10010;
  background: rgba(15, 23, 42, 0.46);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.dialog {
  width: min(460px, 100%);
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 18px 54px rgba(15, 23, 42, 0.25);
  overflow: hidden;
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
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  color: #334155;
}

.dialog-body {
  padding: 14px;
  color: #334155;
  font-size: 13px;
}

.dialog-body p {
  margin: 0;
}

.dialog-label {
  display: block;
  margin-bottom: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.text-input {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
}

.text-input:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.18);
}

.dialog-tip {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
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

.toast {
  position: fixed;
  right: 16px;
  bottom: 18px;
  padding: 10px 12px;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  font-size: 13px;
  z-index: 10020;
  background: #0f172a;
  color: #fff;
}

.toast.error {
  background: #991b1b;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  transform: translateY(6px);
  opacity: 0;
}

@media (max-width: 980px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: flex-start;
    align-items: stretch;
  }

  .action-group {
    width: 100%;
    flex-wrap: wrap;
  }

  .btn-run {
    width: 100%;
  }

  .content {
    grid-template-columns: 1fr;
  }
}
</style>
