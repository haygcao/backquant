<template>
  <div class="research-notebook-page" :class="{ 'header-collapsed': headerCollapsed, 'is-fullscreen': isFullscreen }">
    <header v-if="!isFullscreen" class="page-header" :class="{ 'is-collapsed': headerCollapsed }">
      <div class="top-line">
        <div class="title-inline">
          <h2>{{ pageTitle }}</h2>
          <div class="sub-inline">
            <span class="meta-item">
              研究 ID：<span class="mono id-muted">{{ researchId || '-' }}</span>
            </span>
            <span class="meta-chip">Kernel：{{ research.kernel || '-' }}</span>
            <span class="meta-chip">最后修改：{{ formatMetaDate(research.updated_at || research.created_at) }}</span>
          </div>
        </div>
        <div class="top-actions">
          <button
            class="header-toggle-btn"
            type="button"
            :class="{ 'is-collapsed': headerCollapsed }"
            :aria-label="headerCollapsed ? '展开顶部信息' : '收起顶部信息'"
            :title="headerCollapsed ? '展开顶部信息' : '收起顶部信息'"
            @click="toggleHeader"
          >
            <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M7 10l5 5 5-5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button class="btn btn-secondary" type="button" @click="goBack">
            返回研究列表
          </button>
        </div>
      </div>

      <div class="header-expandable">
        <div v-if="metaError" class="inline-error header-error">{{ metaError }}</div>

        <div class="session-line">
          <div class="session-meta">
            <div class="session-item">
              <span class="info-label">会话状态</span>
              <span class="info-value">
                <span class="status-chip" :class="statusClass(session?.status)">{{ session?.status || '-' }}</span>
              </span>
            </div>
          </div>
          <div class="actions-row">
            <button class="btn btn-primary" type="button" :disabled="sessionLoading || !researchId" @click="startSession">
              {{ sessionLoading ? '处理中...' : (session ? '重建会话' : '启动会话') }}
            </button>
            <button class="btn btn-danger" type="button" :disabled="sessionLoading || !session" @click="stopSession">
              结束会话
            </button>
          </div>
        </div>
      </div>
    </header>

    <section class="notebook-main">
      <div class="iframe-card">
        <div class="iframe-head">
          <h3>Notebook 会话</h3>
          <button
            class="btn btn-icon"
            type="button"
            :title="isFullscreen ? '退出全屏' : '全屏'"
            @click="toggleFullscreen"
          >
            <svg v-if="!isFullscreen" class="icon" viewBox="0 0 24 24" fill="none">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <svg v-else class="icon" viewBox="0 0 24 24" fill="none">
              <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>

        <div v-if="!hasNotebookSession" class="iframe-empty">
          <p v-if="hasSessionRecord">
            会话已创建（{{ session.session_id }}），正在准备 Notebook 地址，请稍候。
          </p>
          <p v-else>当前没有可用的 Notebook 会话。</p>
          <button class="btn btn-primary" type="button" :disabled="sessionLoading" @click="startSession">
            {{ sessionLoading ? '启动中...' : (hasSessionRecord ? '重建会话' : '立即启动会话') }}
          </button>
        </div>

        <div v-else class="iframe-wrap">
          <div v-if="iframeLoading" class="iframe-loading">Notebook 加载中...</div>
          <iframe
            :key="`notebook-frame-${frameNonce}`"
            ref="notebookFrame"
            class="notebook-iframe"
            :src="notebookUrl"
            frameborder="0"
            @load="handleIframeLoad"
          />
        </div>
      </div>
    </section>

    <transition name="toast">
      <div v-if="showToast" class="toast" :class="toastType">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<script>
import {
  getResearch,
  getNotebookSession,
  createNotebookSession,
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

function normalizeResearch(payload, fallbackId = '') {
  const raw = payload && typeof payload === 'object' ? payload : {};
  const root = raw.research && typeof raw.research === 'object' ? raw.research : raw;
  return {
    id: String(root.id || root.research_id || fallbackId || '').trim(),
    title: String(root.title || root.name || '').trim(),
    description: String(root.description || root.desc || '').trim(),
    notebook_path: String(root.notebook_path || root.notebookPath || root.path || '').trim(),
    kernel: String(root.kernel || root.kernel_name || '').trim(),
    status: String(root.status || 'DRAFT').trim().toUpperCase(),
    tags: normalizeTags(root.tags),
    created_at: root.created_at || root.createdAt || root.ctime || '',
    updated_at: root.updated_at || root.updatedAt || root.mtime || ''
  };
}

function normalizeSession(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const root = payload.session && typeof payload.session === 'object'
    ? payload.session
    : (payload.notebook_session && typeof payload.notebook_session === 'object'
      ? payload.notebook_session
      : payload);

  const sessionId = String(root.session_id || root.id || '').trim();
  const notebookUrl = String(
    root.notebook_url
      || root.url
      || root.jupyter_url
      || root.launch_url
      || root.open_url
      || ''
  ).trim();
  const embedUrl = String(root.iframe_url || root.embed_url || root.notebook_iframe_url || '').trim();

  if (!sessionId && !notebookUrl && !embedUrl) {
    return null;
  }

  return {
    session_id: sessionId,
    notebook_url: notebookUrl,
    embed_url: embedUrl,
    status: String(root.status || '').trim().toUpperCase(),
    started_at: root.started_at || root.created_at || '',
    last_active_at: root.last_active_at || root.updated_at || '',
    expires_at: root.expires_at || ''
  };
}

function toAbsoluteUrl(rawUrl) {
  let raw = String(rawUrl || '').trim();
  if (!raw) {
    return '';
  }

  // 解决 Mac 浏览器跳到 http://localhost:8088/... 的问题
  raw = raw.replace(/^https?:\/\/(localhost|127\.0\.0\.1):8088\/jupyter\/?/i, '/jupyter/');
  raw = raw.replace(/^https?:\/\/(localhost|127\.0\.0\.1):8088\/?/i, '/');

  try {
    if (typeof window !== 'undefined' && window.location) {
      return new URL(raw, window.location.origin).toString();
    }
    return new URL(raw).toString();
  } catch (error) {
    return '';
  }
}

export default {
  name: 'ResearchNotebook',
  data() {
    return {
      research: {
        id: '',
        title: '',
        description: '',
        notebook_path: '',
        kernel: '',
        status: 'DRAFT',
        tags: [],
        created_at: '',
        updated_at: ''
      },
      metaLoading: false,
      metaError: '',
      session: null,
      headerCollapsed: false,
      sessionLoading: false,
      iframeLoading: false,
      frameNonce: 0,
      iframePathRecoveryTried: false,
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null,
      isFullscreen: false
    };
  },
  computed: {
    researchId() {
      return String(this.$route.params?.id || '').trim();
    },
    pageTitle() {
      return String(this.research.title || '').trim() || this.researchId || '研究会话';
    },
    remoteNotebookUrl() {
      return toAbsoluteUrl(
        this.session?.embed_url
          || this.session?.notebook_url
          || ''
      );
    },
    notebookUrl() {
      return this.remoteNotebookUrl;
    },
    hasNotebookSession() {
      return Boolean(this.notebookUrl);
    },
    hasSessionRecord() {
      return Boolean(this.session?.session_id);
    }
  },
  watch: {
    async researchId(nextId, prevId) {
      if (nextId && nextId !== prevId) {
        await this.bootstrap();
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
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return String(value);
      }
      return date.toLocaleString('zh-CN');
    },
    statusClass(status) {
      const text = String(status || '').toUpperCase();
      if (text === 'ACTIVE' || text === 'RUNNING') {
        return 'is-active';
      }
      if (text === 'ARCHIVED' || text === 'STOPPED') {
        return 'is-archived';
      }
      if (text === 'FAILED' || text === 'ERROR') {
        return 'is-error';
      }
      return 'is-draft';
    },
    goBack() {
      this.$router.push({ name: 'research-index' });
    },
    toggleHeader() {
      this.headerCollapsed = !this.headerCollapsed;
    },
    toggleFullscreen() {
      this.isFullscreen = !this.isFullscreen;
      if (this.isFullscreen) {
        this.headerCollapsed = true;
      }
    },
    buildSessionPayload(forceNotebookPath = false) {
      const payload = {};
      const kernel = String(this.research.kernel || 'python3').trim();
      if (kernel) {
        payload.kernel = kernel;
      }
      if (forceNotebookPath) {
        payload.notebook_path = `${this.researchId}.ipynb`;
      }
      return payload;
    },
    isNotebookPathIssue(message) {
      const text = String(message || '').toLowerCase();
      if (!text) {
        return false;
      }
      return (
        text.includes('cannot open')
        || text.includes('could not find path')
        || text.includes('notebook_path')
        || text.includes('路径')
        || text.includes('not found')
      );
    },
    async requestSessionWithFallback() {
      const firstPayload = this.buildSessionPayload(false);
      try {
        const data = await createNotebookSession(this.researchId, firstPayload);
        return normalizeSession(data);
      } catch (error) {
        const message = this.getErrorMessage(error, '');
        if (!this.isNotebookPathIssue(message)) {
          throw error;
        }
        const fallbackPayload = this.buildSessionPayload(true);
        const data = await createNotebookSession(this.researchId, fallbackPayload);
        return normalizeSession(data);
      }
    },
    async recoverSessionAfterPathError() {
      try {
        const session = await this.requestSessionWithFallback();
        if (!session) {
          return false;
        }
        this.session = session;
        this.iframePathRecoveryTried = false;
        this.frameNonce += 1;
        this.iframeLoading = !!this.notebookUrl;
        return this.hasNotebookSession;
      } catch (error) {
        return false;
      }
    },
    async bootstrap() {
      await this.fetchResearch();
      await this.fetchSession(true);
    },
    async fetchResearch() {
      if (!this.researchId) {
        return;
      }
      this.metaLoading = true;
      this.metaError = '';
      try {
        const data = await getResearch(this.researchId);
        this.research = normalizeResearch(data, this.researchId);
      } catch (error) {
        this.metaError = this.getErrorMessage(error, '加载研究信息失败');
      } finally {
        this.metaLoading = false;
      }
    },
    async refreshSessionStatus(silent = true) {
      if (!this.researchId) {
        return;
      }
      try {
        const data = await getNotebookSession(this.researchId);
        this.session = normalizeSession(data);
        this.iframePathRecoveryTried = false;
        this.iframeLoading = !!this.notebookUrl;
      } catch (error) {
        const status = Number(error?.response?.status || 0);
        if (status === 404) {
          this.session = null;
          this.iframeLoading = false;
          if (!silent) {
            this.showMessage('会话不存在/已过期');
          }
          return;
        }
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '刷新会话失败'), 'error');
        }
      }
    },
    async fetchSession(silent = true) {
      if (!this.researchId) {
        return;
      }
      this.sessionLoading = true;
      try {
        this.session = await this.requestSessionWithFallback();
        this.iframePathRecoveryTried = false;
        this.iframeLoading = !!this.notebookUrl;
      } catch (error) {
        const message = this.getErrorMessage(error, '');
        if (this.isNotebookPathIssue(message)) {
          const recovered = await this.recoverSessionAfterPathError();
          if (recovered) {
            return;
          }
        }
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '刷新会话失败'), 'error');
        }
      } finally {
        this.sessionLoading = false;
      }
    },
    sleep(ms) {
      return new Promise((resolve) => {
        setTimeout(resolve, ms);
      });
    },
    async waitForNotebookUrl(maxAttempts = 8, intervalMs = 1000) {
      for (let i = 0; i < maxAttempts; i += 1) {
        if (this.hasNotebookSession) {
          return true;
        }
        await this.sleep(intervalMs);
        try {
          const latest = await this.requestSessionWithFallback();
          if (latest) {
            this.session = latest;
          }
          if (this.hasNotebookSession) {
            return true;
          }
        } catch (error) {
          const message = this.getErrorMessage(error, '');
          if (this.isNotebookPathIssue(message)) {
            const recovered = await this.recoverSessionAfterPathError();
            if (recovered) {
              return true;
            }
          }
          // 后端还在准备会话时可能短暂不可读，继续重试。
        }
      }
      return this.hasNotebookSession;
    },
    async startSession() {
      if (!this.researchId) {
        return;
      }
      this.sessionLoading = true;
      try {
        this.session = await this.requestSessionWithFallback();
        if (!this.session) {
          throw new Error('后端未返回会话信息');
        }

        if (!this.hasNotebookSession) {
          this.showMessage('会话已创建，正在等待 Notebook 地址...');
          const ready = await this.waitForNotebookUrl(10, 1000);
          if (!ready) {
            throw new Error('会话已创建，但后端尚未返回可用的 Notebook 地址');
          }
        }
        this.frameNonce += 1;
        this.iframePathRecoveryTried = false;
        this.iframeLoading = !!this.notebookUrl;
        this.showMessage('Notebook 会话已启动');
      } catch (error) {
        const message = this.getErrorMessage(error, '启动会话失败');
        if (this.isNotebookPathIssue(message)) {
          const recovered = await this.recoverSessionAfterPathError();
          if (recovered) {
            this.showMessage('路径异常已恢复，已使用新的会话地址');
            return;
          }
        }
        this.showMessage(message, 'error');
      } finally {
        this.sessionLoading = false;
      }
    },
    async stopSession() {
      if (!this.researchId || !this.session) {
        return;
      }
      this.sessionLoading = true;
      try {
        const sessionId = String(this.session?.session_id || '').trim();
        const stopPayload = {};
        if (sessionId) {
          stopPayload.session_id = sessionId;
        }
        await stopNotebookSession(this.researchId, stopPayload);
        await this.disconnectNotebookIframe();
        this.session = null;
        this.iframeLoading = false;
        await this.refreshSessionStatus(true);
        this.showMessage('会话已结束');
      } catch (error) {
        this.showMessage(this.getErrorMessage(error, '结束会话失败'), 'error');
      } finally {
        this.sessionLoading = false;
      }
    },
    async disconnectNotebookIframe() {
      const frame = this.$refs.notebookFrame;
      if (!frame) {
        return;
      }
      try {
        frame.src = 'about:blank';
      } catch (error) {
        // Ignore iframe teardown errors.
      }
      await new Promise((resolve) => {
        setTimeout(resolve, 350);
      });
    },
    async handleIframeLoad() {
      this.iframeLoading = false;
      if (this.iframePathRecoveryTried || !this.hasNotebookSession) {
        return;
      }
      const frame = this.$refs.notebookFrame;
      if (!frame) {
        return;
      }
      let pageText = '';
      try {
        const frameDocument = frame.contentDocument || frame.contentWindow?.document;
        pageText = String(
          frameDocument?.body?.innerText
          || frameDocument?.documentElement?.innerText
          || ''
        ).toLowerCase();
      } catch (error) {
        // 跨域 iframe 无法读取内容，直接跳过该检测。
        return;
      }
      if (!this.isNotebookPathIssue(pageText)) {
        return;
      }
      this.iframePathRecoveryTried = true;
      this.showMessage('检测到 Notebook 路径异常，正在重建会话...');
      const recovered = await this.recoverSessionAfterPathError();
      if (recovered) {
        this.showMessage('路径异常已恢复，已使用新的会话地址');
        return;
      }
      this.showMessage('Notebook 路径异常，重建会话失败', 'error');
    }
  },
  async mounted() {
    await this.bootstrap();
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
.research-notebook-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  --notebook-offset: 260px;
}

.research-notebook-page.header-collapsed {
  --notebook-offset: 180px;
}

.research-notebook-page.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #fff;
  gap: 0;
  --notebook-offset: 0;
}

.research-notebook-page.is-fullscreen .notebook-main {
  height: 100vh;
}

.research-notebook-page.is-fullscreen .iframe-card {
  height: 100%;
  border-radius: 0;
  border: none;
}

.research-notebook-page.is-fullscreen .iframe-wrap {
  height: calc(100vh - 50px);
}

.research-notebook-page.is-fullscreen .notebook-iframe {
  height: calc(100vh - 50px);
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 16px;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  overflow: hidden;
}

.top-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-toggle-btn {
  width: 32px;
  height: 32px;
  border-radius: 2px;
  border: 1px solid #d0d0d0;
  background: #ffffff;
  color: #000;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.header-toggle-btn:hover {
  background: #f5f5f5;
  border-color: #999;
}

.header-toggle-btn .toggle-icon {
  display: inline-block;
  width: 18px;
  height: 18px;
  transform: rotate(180deg);
  transition: transform 0.2s ease;
}

.header-toggle-btn.is-collapsed .toggle-icon {
  transform: rotate(0deg);
}

.title-inline {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  min-width: 0;
}

.title-inline h2 {
  margin: 0;
  font-size: 17px;
  line-height: 1.2;
  white-space: nowrap;
}

.sub-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #64748b;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 2px;
  border: 1px solid #d0d0d0;
  background: #f5f5f5;
  color: #666;
  font-size: 12px;
  line-height: 1.4;
}

.id-muted {
  color: #94a3b8;
}

.header-expandable {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 260px;
  opacity: 1;
  transition: max-height 0.24s ease, opacity 0.2s ease, margin-top 0.2s ease;
}

.page-header.is-collapsed .header-expandable {
  max-height: 0;
  opacity: 0;
  margin-top: -4px;
  pointer-events: none;
}

.info-line {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
}

.info-item,
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.info-label {
  color: #64748b;
  font-size: 12px;
  flex-shrink: 0;
}

.info-value {
  color: #1e293b;
  font-size: 12px;
  min-width: 0;
}

.header-error {
  width: 100%;
  margin: 0;
}

.session-line {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding-top: 2px;
}

.session-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  min-width: 0;
}

.actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.notebook-main {
  min-width: 0;
  display: block;
}

.iframe-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.iframe-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.iframe-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid #d0d0d0;
  background: #fff;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.btn-icon:hover {
  background: #f5f5f5;
  border-color: #999;
}

.btn-icon .icon {
  width: 16px;
  height: 16px;
  color: #666;
}

.iframe-wrap {
  position: relative;
  min-height: calc(100vh - var(--notebook-offset));
}

.notebook-iframe {
  width: 100%;
  min-height: calc(100vh - var(--notebook-offset));
  border: 0;
  background: #fff;
}

.iframe-empty {
  min-height: calc(100vh - var(--notebook-offset));
  display: grid;
  place-content: center;
  gap: 10px;
  text-align: center;
  color: #64748b;
}

.iframe-loading {
  position: absolute;
  inset: 0;
  background: rgba(248, 250, 252, 0.82);
  display: grid;
  place-items: center;
  color: #334155;
  font-size: 13px;
  z-index: 2;
}

.inline-error {
  background: #ffebee;
  border: 1px solid #ef5350;
  color: #c62828;
  padding: 10px 12px;
  border-radius: 2px;
  margin-bottom: 10px;
  font-size: 12px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
}

.status-chip.is-draft {
  color: #666;
  background: #f5f5f5;
  border-color: #d0d0d0;
}

.status-chip.is-active {
  color: #2e7d32;
  background: #e8f5e9;
  border-color: #66bb6a;
}

.status-chip.is-archived {
  color: #f57c00;
  background: #fff3e0;
  border-color: #ffb74d;
}

.status-chip.is-error {
  color: #d32f2f;
  background: #ffebee;
  border-color: #ef5350;
}

.btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  padding: 6px 12px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
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

@media (max-width: 1200px) {
  .iframe-wrap,
  .iframe-empty,
  .notebook-iframe {
    min-height: 70vh;
  }
}

@media (max-width: 760px) {
  .top-line {
    width: 100%;
    align-items: flex-start;
  }

  .title-inline {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .session-line {
    flex-direction: column;
    align-items: flex-start;
  }

  .actions-row {
    width: 100%;
    flex-wrap: wrap;
  }

  .top-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
