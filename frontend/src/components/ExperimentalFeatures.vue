<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-card">
        <div class="system-brand">
          <img
            src="@/assets/backquant-logo.svg"
            alt="BackQuant logo"
            class="system-logo"
          >
          <span class="system-name">BackQuant</span>
        </div>

        <form
          class="login-form"
          autocomplete="on"
          method="post"
          action="/api/login"
          @submit.prevent="handleLogin"
        >
        <label class="field-label" for="username">用户名</label>
        <input
          id="username"
          name="username"
          v-model.trim="formData.username"
          type="text"
          placeholder="请输入用户名"
          autocomplete="username"
          autocapitalize="none"
          required
          :disabled="isLoading"
        >

        <label class="field-label" for="password">密码</label>
        <input
          id="password"
          name="password"
          v-model="formData.password"
          type="password"
          placeholder="请输入密码"
          autocomplete="current-password"
          required
          :disabled="isLoading"
        >

        <label class="remember-row">
          <input
            type="checkbox"
            v-model="formData.rememberPassword"
            :disabled="isLoading"
          >
          <span>保存密码</span>
        </label>

        <p v-if="error" class="message error">{{ error }}</p>
        <p v-if="showSuccess" class="message success">
          <svg class="success-icon" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
          </svg>
          登录成功
        </p>

        <button type="submit" :disabled="isLoading">
          {{ isLoading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>

    <div class="system-features">
      <div class="feature-item">
        <span class="feature-icon">🔒</span>
        <span class="feature-text">本地部署</span>
      </div>
      <div class="feature-item">
        <span class="feature-icon">🛡️</span>
        <span class="feature-text">开源安全</span>
      </div>
    </div>
    </div>

    <transition name="modal-fade">
      <div v-if="showBundleModal" class="bundle-modal-overlay">
        <div class="bundle-modal" role="dialog" aria-modal="true" aria-labelledby="bundle-modal-title">
          <div class="bundle-modal-header">
            <div class="bundle-modal-title" id="bundle-modal-title">系统初始化中</div>
          </div>
          <div class="bundle-modal-body">
            <div class="bundle-modal-icon" aria-hidden="true"></div>
            <p class="bundle-modal-message">
              系统首次启动，RQAlpha 行情数据下载中，请稍后...
            </p>
            <p v-if="bundleProgressText" class="bundle-modal-progress">
              {{ bundleProgressText }}
            </p>
            <p v-else class="bundle-modal-progress muted">
              正在获取下载进度...
            </p>
            <div class="bundle-modal-tip">
              请保持页面开启，下载完成后会自动进入登录流程。
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { isAuthenticated } from '@/utils/auth';
import axiosInstance from '@/utils/axios';
import { API_ENDPOINTS, API_BASE_URL } from '@/config/api';

export default {
  name: 'ExperimentalFeatures',
  data() {
    return {
      isAuthenticated: false,
      formData: {
        username: '',
        password: '',
        rememberPassword: false
      },
      isLoading: false,
      error: null,
      showSuccess: false,
      showBundleModal: false,
      bundleProgressText: '',
      bundlePollTimer: null,
      bundlePollFailures: 0,
      pendingRouteAfterBundle: false,
      pendingLoginAfterBundle: false,
      loginInProgress: false
    };
  },
  mounted() {
    this.redirectIfAuthenticated();
    this.checkSavedPassword();
  },
  beforeUnmount() {
    this.stopBundlePolling();
  },
  methods: {
    redirectIfAuthenticated() {
      this.isAuthenticated = isAuthenticated();
      if (this.isAuthenticated) {
        this.$router.replace({ name: 'strategies' });
      }
    },
    checkSavedPassword() {
      const savedUsername = localStorage.getItem('savedUsername');
      if (localStorage.getItem('savedPassword')) {
        localStorage.removeItem('savedPassword');
      }
      if (savedUsername) {
        this.formData.username = savedUsername;
        this.formData.rememberPassword = true;
      }
    },
    openBundleModal() {
      if (this.showBundleModal) return;
      this.showBundleModal = true;
      this.bundleProgressText = '';
      this.bundlePollFailures = 0;
      this.startBundlePolling();
    },
    closeBundleModal() {
      this.showBundleModal = false;
      this.pendingRouteAfterBundle = false;
      this.stopBundlePolling();
    },
    startBundlePolling() {
      this.stopBundlePolling();
      this.fetchBundleProgress();
      this.bundlePollTimer = setInterval(() => {
        this.fetchBundleProgress();
      }, 1000);
    },
    stopBundlePolling() {
      if (this.bundlePollTimer) {
        clearInterval(this.bundlePollTimer);
        this.bundlePollTimer = null;
      }
    },
    formatBytes(value) {
      if (!Number.isFinite(value) || value < 0) return '';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let size = value;
      let unitIndex = 0;
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
      }
      return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
    },
    isBundleReady(payload) {
      if (!payload || typeof payload !== 'object') return false;
      return payload.status === 'ready';
    },
    async fetchBundleProgress() {
      const endpoint = `${API_BASE_URL}/api/system/bundle-status`;
      try {
        const response = await axiosInstance.get(endpoint, { timeout: 5000 });
        const payload = response?.data || {};
        const progress = payload.progress || {};
        const percent = Number(progress.percent);
        const downloaded = Number(progress.downloaded_bytes);
        const total = Number(progress.total_bytes);
        const extracted = Number(progress.extracted_bytes);
        if (payload.status === 'failed') {
          this.bundleProgressText = payload.message || '行情数据下载失败，请检查网络后重试。';
          this.stopBundlePolling();
          return;
        }

        if (typeof payload.message === 'string' && payload.message.trim() === 'bundle extracting') {
          if (Number.isFinite(extracted) && extracted > 0) {
            this.bundleProgressText = `下载完成，正在解压中...（已解压 ${this.formatBytes(extracted)}）`;
          } else {
            this.bundleProgressText = '下载完成，正在解压中...';
          }
        } else if (Number.isFinite(percent)) {
          if (Number.isFinite(downloaded) && Number.isFinite(total) && total > 0) {
            this.bundleProgressText = `下载进度：${percent.toFixed(1)}%（${this.formatBytes(downloaded)} / ${this.formatBytes(total)}）`;
          } else if (Number.isFinite(total) && total > 0) {
            this.bundleProgressText = `下载进度：${percent.toFixed(1)}%（总计 ${this.formatBytes(total)}）`;
          } else {
            this.bundleProgressText = `下载进度：${percent.toFixed(1)}%`;
          }
        } else if (Number.isFinite(downloaded) && Number.isFinite(total) && total > 0) {
          this.bundleProgressText = `已下载 ${this.formatBytes(downloaded)} / ${this.formatBytes(total)}`;
        } else if (Number.isFinite(downloaded) && downloaded > 0) {
          this.bundleProgressText = `已下载 ${this.formatBytes(downloaded)}`;
        } else if (typeof payload.message === 'string' && payload.message.trim()) {
          this.bundleProgressText = payload.message.trim();
        } else {
          this.bundleProgressText = '';
        }
        if (this.isBundleReady(payload)) {
          this.bundleProgressText = '行情数据已准备完成，可以登录。';
          this.stopBundlePolling();
          this.showBundleModal = false;
          if (this.pendingLoginAfterBundle) {
            this.pendingLoginAfterBundle = false;
            await this.performLogin();
          } else if (this.pendingRouteAfterBundle) {
            this.pendingRouteAfterBundle = false;
            await this.$router.replace({ name: 'strategies' });
          }
        }
      } catch (err) {
        this.bundlePollFailures += 1;
        if (this.bundlePollFailures >= 3) {
          this.stopBundlePolling();
          this.bundleProgressText = '';
        }
      }
    },
    async getBundleStatus() {
      const endpoint = `${API_BASE_URL}/api/system/bundle-status`;
      const response = await axiosInstance.get(endpoint, { timeout: 5000 });
      return response?.data || {};
    },
    async performLogin() {
      if (this.loginInProgress) return;
      this.loginInProgress = true;
      this.isLoading = true;
      this.error = null;

      try {
        const formData = new URLSearchParams();
        formData.append('username', this.formData.username);
        formData.append('password', this.formData.password);

        const response = await axiosInstance.post(API_ENDPOINTS.LOGIN, formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        });

        if (response.status === 200 && response.data && response.data.code === 'BUNDLE_NOT_READY') {
          this.showSuccess = false;
          this.pendingRouteAfterBundle = false;
          this.pendingLoginAfterBundle = true;
          this.openBundleModal();
          return;
        }

        if (response.status !== 200 || !response.data || !response.data.token || !response.data.userid) {
          this.error = '登录响应数据格式错误';
          return;
        }

        localStorage.setItem('token', response.data.token);
        localStorage.setItem('userid', response.data.userid);

        if (response.data.is_admin !== undefined) {
          localStorage.setItem('is_admin', response.data.is_admin);
        }

        if (this.formData.rememberPassword) {
          localStorage.setItem('savedUsername', this.formData.username);
        } else {
          localStorage.removeItem('savedUsername');
        }

        axiosInstance.defaults.headers.common.Authorization = response.data.token;

        this.showSuccess = true;
        this.isAuthenticated = true;

        const payload = await this.getBundleStatus();
        if (this.isBundleReady(payload)) {
          await this.$router.replace({ name: 'strategies' });
        } else {
          this.pendingRouteAfterBundle = true;
          this.openBundleModal();
        }
      } catch (err) {
        if (err.response) {
          const status = err.response.status;
          if (status === 401) {
            this.error = '用户名或密码错误';
          } else if (status === 400) {
            this.error = '请求参数错误';
          } else if (status === 502 || status === 503 || status === 504) {
            this.error = '服务暂不可用，请稍后重试';
          } else if (status === 500) {
            this.error = '服务器内部错误';
          } else {
            this.error = `登录失败，状态码：${status}`;
          }
        } else if (err.request) {
          this.error = '网络异常，请稍后重试';
        } else {
          this.error = '登录失败，请稍后重试';
        }
      } finally {
        this.isLoading = false;
        this.loginInProgress = false;
      }
    },
    async handleLogin() {
      if (this.loginInProgress) return;
      this.error = null;
      await this.performLogin();
    }
  }
};
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 64px - 32px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 24px;
}

.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 100%;
  max-width: 480px;
}

.login-card {
  width: 100%;
  background: #ffffff;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid #e0e0e0;
  padding: 32px;
}

.system-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  color: #000;
  font-size: 14px;
  font-weight: 700;
}

.system-logo {
  width: 36px;
  height: 36px;
  display: block;
}

.system-name {
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  font-size: 18px;
  letter-spacing: 0.3px;
}

.system-features {
  display: flex;
  gap: 32px;
  padding: 16px 24px;
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  width: 100%;
  justify-content: center;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.feature-icon {
  font-size: 18px;
}

.feature-text {
  font-weight: 500;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  margin-top: 4px;
  color: #666;
  font-size: 12px;
  font-weight: 500;
}

.login-form input[type='text'],
.login-form input[type='password'] {
  width: 100%;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
  padding: 8px 12px;
  font-size: 13px;
  transition: border-color 0.15s ease;
}

.login-form input:hover {
  border-color: #999;
}

.login-form input:focus {
  outline: none;
  border-color: #1976d2;
}

.remember-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  color: #606266;
  font-size: 13px;
}

.message {
  margin: 0;
  font-size: 12px;
  border-radius: 2px;
  padding: 10px 12px;
  border: 1px solid;
}

.message.error {
  color: #d32f2f;
  background: #ffebee;
  border-color: #ef5350;
}

.message.success {
  color: #2e7d32;
  background: #e8f5e9;
  border-color: #66bb6a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.success-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

button {
  margin-top: 8px;
  height: 38px;
  border: 0;
  border-radius: 2px;
  background: #1976d2;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

button:hover:not(:disabled) {
  background: #1565c0;
}

button:disabled {
  background: #90caf9;
  cursor: not-allowed;
}

.bundle-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 24px;
}

.bundle-modal {
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid #e0e0e0;
  overflow: hidden;
}

.bundle-modal-header {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.bundle-modal-title {
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.bundle-modal-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(31, 111, 235, 0.12);
  color: #1f6feb;
  font-size: 12px;
  font-weight: 600;
}

.bundle-modal-body {
  padding: 20px;
  text-align: center;
}

.bundle-modal-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  margin: 0 auto 12px;
  border: 4px solid rgba(31, 111, 235, 0.2);
  border-top-color: #1f6feb;
  animation: bundle-spin 1.1s linear infinite;
}

.bundle-modal-message {
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.bundle-modal-progress {
  color: #1e40af;
  font-size: 13px;
  margin: 0;
}

.bundle-modal-progress.muted {
  color: #64748b;
}

.bundle-modal-tip {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@keyframes bundle-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .login-page {
    min-height: calc(100vh - 64px - 24px);
  }

  .login-card {
    padding: 20px;
  }
}
</style>
