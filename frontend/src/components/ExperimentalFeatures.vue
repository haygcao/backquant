<template>
  <div class="login-page">
    <div class="login-card">
      <div class="system-brand">
        <img
          src="@/assets/backquant-logo.svg"
          alt="BackQuant logo"
          class="system-logo"
        >
        <span class="system-name">BackQuant</span>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <label class="field-label" for="mobile">手机号</label>
        <input
          id="mobile"
          v-model.trim="formData.mobile"
          type="tel"
          placeholder="请输入手机号"
          required
          :disabled="isLoading"
        >

        <label class="field-label" for="password">密码</label>
        <input
          id="password"
          v-model="formData.password"
          type="password"
          placeholder="请输入密码"
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
        <p v-if="showSuccess" class="message success">登录成功，正在进入 BackQuant...</p>

        <button type="submit" :disabled="isLoading">
          {{ isLoading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { isAuthenticated } from '@/utils/auth';
import axiosInstance from '@/utils/axios';
import { API_ENDPOINTS } from '@/config/api';

export default {
  name: 'ExperimentalFeatures',
  data() {
    return {
      isAuthenticated: false,
      formData: {
        mobile: '',
        password: '',
        rememberPassword: false
      },
      isLoading: false,
      error: null,
      showSuccess: false
    };
  },
  mounted() {
    this.redirectIfAuthenticated();
    this.checkSavedPassword();
  },
  methods: {
    redirectIfAuthenticated() {
      this.isAuthenticated = isAuthenticated();
      if (this.isAuthenticated) {
        this.$router.replace({ name: 'strategies' });
      }
    },
    checkSavedPassword() {
      const savedMobile = localStorage.getItem('savedMobile');
      const savedPassword = localStorage.getItem('savedPassword');

      if (savedMobile && savedPassword) {
        this.formData.mobile = savedMobile;
        this.formData.password = savedPassword;
        this.formData.rememberPassword = true;
      }
    },
    async handleLogin() {
      this.isLoading = true;
      this.error = null;

      try {
        const formData = new URLSearchParams();
        formData.append('mobile', this.formData.mobile);
        formData.append('password', this.formData.password);

        const response = await axiosInstance.post(API_ENDPOINTS.LOGIN, formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        });

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
          localStorage.setItem('savedMobile', this.formData.mobile);
          localStorage.setItem('savedPassword', this.formData.password);
        } else {
          localStorage.removeItem('savedMobile');
          localStorage.removeItem('savedPassword');
        }

        axiosInstance.defaults.headers.common.Authorization = response.data.token;

        this.showSuccess = true;
        this.isAuthenticated = true;

        await this.$router.replace({ name: 'strategies' });
      } catch (err) {
        if (err.response) {
          const status = err.response.status;
          if (status === 401) {
            this.error = '用户名或密码错误';
          } else if (status === 400) {
            this.error = '请求参数错误';
          } else if (status === 500) {
            this.error = '服务器内部错误';
          } else {
            this.error = `登录失败，状态码：${status}`;
          }
        } else if (err.request) {
          this.error = '网络连接失败，请检查网络';
        } else {
          this.error = '登录失败，请稍后重试';
        }
      } finally {
        this.isLoading = false;
      }
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
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
  padding: 28px;
}

.system-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  color: #1f6feb;
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

.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  margin-top: 4px;
  color: #606266;
  font-size: 13px;
}

.login-form input[type='tel'],
.login-form input[type='password'] {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
}

.login-form input:focus {
  outline: none;
  border-color: #409eff;
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
  font-size: 13px;
  border-radius: 6px;
  padding: 8px 10px;
}

.message.error {
  color: #f56c6c;
  background: #fef0f0;
}

.message.success {
  color: #67c23a;
  background: #f0f9eb;
}

button {
  margin-top: 8px;
  height: 40px;
  border: 0;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
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
