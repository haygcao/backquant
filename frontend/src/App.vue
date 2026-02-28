<template>
  <div class="app-shell">
    <header class="top-nav">
      <button class="brand" type="button" @click="goHome">
        <img
          src="@/assets/backquant-logo.svg"
          alt="BackQuant logo"
          class="brand-logo"
        >
        <span class="brand-title">BackQuant</span>
      </button>

      <nav class="top-links">
        <router-link
          v-for="item in visibleTopNavItems"
          :key="item.id"
          :to="item.path"
          class="top-link"
          :class="{ 'is-disabled': item.disabled, 'is-active': isRouteActive(item.path) }"
          @click="handleTopNavClick(item, $event)"
        >
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              :d="item.iconPath"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
            />
          </svg>
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="link-badge">{{ item.badge }}</span>
        </router-link>
      </nav>

      <div class="top-actions">
        <span v-if="isAuthenticated" class="auth-pill">已登录</span>
        <button
          v-if="isAuthenticated"
          type="button"
          class="logout-btn"
          @click="handleLogout"
        >
          退出
        </button>
      </div>
    </header>

    <div class="app-layout">
      <aside v-if="showSidebar" class="sidebar">
        <div class="sidebar-title">回测工作台</div>
        <nav class="sidebar-links">
          <router-link
            v-for="item in sideNavItems"
            :key="item.id"
            :to="item.path"
            class="sidebar-link"
            :class="{ 'is-active': isRouteActive(item.path) }"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                :d="item.iconPath"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
            </svg>
            {{ item.label }}
          </router-link>
        </nav>
      </aside>

      <main class="app-main" :class="{ 'with-sidebar': showSidebar }">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script>
import axiosInstance from '@/utils/axios';

export default {
  name: 'App',
  data() {
    return {
      isAuthenticated: false,
      topNavItems: [
        {
          id: 'login',
          label: '登录',
          path: '/login',
          requireAuth: false,
          iconPath: 'M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4 M10 17l5-5-5-5 M15 12H3'
        },
        {
          id: 'market-data',
          label: '数据管理',
          path: '/market-data',
          requireAuth: true,
          iconPath: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4'
        },
        {
          id: 'workbench',
          label: '回测工作台',
          path: '/strategies',
          requireAuth: true,
          iconPath: 'M4 19h16 M6 15l3-3 3 2 5-6'
        },
        {
          id: 'other',
          label: '研究工作台',
          path: '/research',
          requireAuth: true,
          iconPath: 'M6 8h.01 M12 8h.01 M18 8h.01 M4 16h16'
        }
      ],
      sideNavItems: [
        {
          id: 'strategies',
          label: '策略管理',
          path: '/strategies',
          iconPath: 'M4 6h16 M4 12h12 M4 18h16 M18 12l2 2-2 2'
        }
      ]
    };
  },
  computed: {
    showSidebar() {
      // 新版三页结构内部会自行管理布局（例如回测结果页的左侧导航）。
      // 这里保留侧边栏仅用于旧 backtest 路由，避免历史页面布局被破坏。
      return this.isAuthenticated
        && this.$route.path.startsWith('/backtest/')
        && this.$route.path !== '/backtest/history';
    },
    visibleTopNavItems() {
      if (this.isAuthenticated) {
        return this.topNavItems.filter((item) => item.id !== 'login');
      }
      return this.topNavItems.filter((item) => item.id === 'login');
    }
  },
  watch: {
    $route() {
      this.syncAuth();
    }
  },
  mounted() {
    this.syncAuth();
  },
  methods: {
    syncAuth() {
      this.isAuthenticated = !!localStorage.getItem('token');
    },
    isRouteActive(path) {
      const currentPath = String(this.$route.path || '');
      if (currentPath === path) {
        return true;
      }
      if (currentPath.startsWith(`${path}/`)) {
        return true;
      }
      // 回测历史和策略编辑页面也属于回测工作台
      if (path === '/strategies' && (currentPath.startsWith('/backtest/') || currentPath.startsWith('/backtests/'))) {
        return true;
      }
      return false;
    },
    goHome() {
      this.$router.push(this.isAuthenticated ? '/market-data/overview' : '/login');
    },
    handleTopNavClick(item, event) {
      if (item.disabled) {
        event.preventDefault();
        return;
      }

      if (item.requireAuth && !this.isAuthenticated) {
        event.preventDefault();
        this.$router.push('/login');
      }
    },
    handleLogout() {
      localStorage.removeItem('token');
      localStorage.removeItem('userid');
      localStorage.removeItem('is_admin');
      delete axiosInstance.defaults.headers.common.Authorization;
      this.syncAuth();
      this.$router.replace('/login');
    }
  }
};
</script>

<style>
:root {
  --bg: #f3f6fb;
  --surface: #ffffff;
  --text-primary: #243247;
  --text-secondary: #5f6f86;
  --text-tertiary: #8b95a8;
  --border: #dfe7f2;
  --border-light: #eef3f9;
  --accent: #1f6feb;
  --accent-hover: #1a5cd7;
  --accent-soft: #eaf2ff;
  --accent-softer: #f4f8ff;
  --success: #10b981;
  --success-soft: #d1fae5;
  --warning: #f59e0b;
  --warning-soft: #fef3c7;
  --danger: #ef4444;
  --danger-soft: #fee2e2;
  --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.08);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.1);
  --shadow-lg: 0 10px 30px rgba(15, 23, 42, 0.12);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  margin: 0;
  min-height: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 10% 5%, #eaf2ff 0, rgba(234, 242, 255, 0) 40%),
    radial-gradient(circle at 90% 0%, #fef4e8 0, rgba(254, 244, 232, 0) 30%),
    radial-gradient(circle at 50% 100%, #f0f9ff 0, rgba(240, 249, 255, 0) 35%),
    var(--bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-shell {
  min-height: 100vh;
}

.top-nav {
  position: sticky;
  top: 0;
  z-index: 120;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fff;
}

.brand {
  border: 0;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0;
}

.brand-logo {
  width: 28px;
  height: 28px;
  display: block;
}

.brand-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: #000;
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
}

.top-links {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
}

.top-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 2px;
  border: 1px solid transparent;
  color: #666;
  text-decoration: none;
  white-space: nowrap;
  font-weight: 500;
  font-size: 13px;
}

.top-link:hover {
  color: #000;
  background: #f5f5f5;
}

.nav-icon {
  width: 15px;
  height: 15px;
  flex: 0 0 auto;
}

.top-link.is-active {
  color: #000;
  border-color: #d0d0d0;
  background: #f0f0f0;
  font-weight: 600;
}

.top-link.is-disabled {
  opacity: 0.65;
  cursor: default;
  background: #f1f4f8;
}

.link-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 2px;
  border: 1px solid #d0d0d0;
  color: #666;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
  justify-content: flex-end;
}

.auth-pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  border-radius: 2px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: #000;
  background: #f0f0f0;
  border: 1px solid #d0d0d0;
}

.logout-btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  border-radius: 2px;
  height: 32px;
  padding: 0 12px;
  cursor: pointer;
  font-weight: 500;
  font-size: 12px;
}

.logout-btn:hover {
  color: #000;
  border-color: #b0b0b0;
  background: #f5f5f5;
}

.app-layout {
  display: flex;
  min-height: calc(100vh - 48px);
}

.sidebar {
  width: 220px;
  border-right: 1px solid var(--border-light);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px) saturate(180%);
  padding: 16px 12px;
  box-shadow: inset -1px 0 0 rgba(31, 111, 235, 0.05);
}

.sidebar-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #6a7991;
  margin-bottom: 10px;
  padding: 0 8px;
}

.sidebar-links {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  padding: 11px 14px;
  border: 1px solid transparent;
  font-weight: 500;
  transition: all var(--transition-base);
  position: relative;
  overflow: hidden;
}

.sidebar-link::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
  transition: height var(--transition-base);
}

.sidebar-link:hover {
  color: var(--accent);
  background: var(--accent-softer);
  transform: translateX(2px);
}

.sidebar-link.is-active {
  color: var(--accent);
  background: linear-gradient(135deg, var(--accent-soft) 0%, var(--accent-softer) 100%);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(31, 111, 235, 0.1);
}

.sidebar-link.is-active::before {
  height: 60%;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.app-main.with-sidebar {
  padding: 16px 18px;
}

@media (max-width: 900px) {
  .top-nav {
    padding: 0 12px;
  }

  .brand-title {
    font-size: 15px;
  }

  .app-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    border-right: 0;
    border-bottom: 1px solid var(--border);
    padding: 10px 12px;
  }

  .sidebar-links {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .sidebar-link {
    padding: 8px 10px;
    font-size: 13px;
  }

  .app-main,
  .app-main.with-sidebar {
    padding: 12px;
  }
}
</style>
