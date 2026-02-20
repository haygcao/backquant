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
      return currentPath.startsWith(`${path}/`);
    },
    goHome() {
      this.$router.push(this.isAuthenticated ? '/strategies' : '/login');
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
  --border: #dfe7f2;
  --accent: #1f6feb;
  --accent-soft: #eaf2ff;
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 10% 5%, #eaf2ff 0, rgba(234, 242, 255, 0) 38%),
    radial-gradient(circle at 90% 0%, #fef4e8 0, rgba(254, 244, 232, 0) 28%),
    var(--bg);
}

.app-shell {
  min-height: 100vh;
}

.top-nav {
  position: sticky;
  top: 0;
  z-index: 120;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
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
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: var(--text-primary);
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
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  color: var(--text-secondary);
  text-decoration: none;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.top-link:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

.nav-icon {
  width: 15px;
  height: 15px;
  flex: 0 0 auto;
}

.top-link.is-active {
  color: var(--accent);
  border-color: #cfe1ff;
  background: var(--accent-soft);
}

.top-link.is-disabled {
  opacity: 0.65;
  cursor: default;
  background: #f1f4f8;
}

.link-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid #d5deea;
  color: #7b8798;
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
  height: 26px;
  border-radius: 999px;
  padding: 0 9px;
  font-size: 12px;
  color: #1f6feb;
  background: var(--accent-soft);
  border: 1px solid #cfe1ff;
}

.logout-btn {
  border: 1px solid #d5deea;
  background: #fff;
  color: var(--text-secondary);
  border-radius: 8px;
  height: 32px;
  padding: 0 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.logout-btn:hover {
  color: var(--accent);
  border-color: #bdd5ff;
  background: var(--accent-soft);
}

.app-layout {
  display: flex;
  min-height: calc(100vh - 64px);
}

.sidebar {
  width: 220px;
  border-right: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(4px);
  padding: 14px 12px;
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
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.sidebar-link:hover {
  color: var(--accent);
  border-color: #d6e4ff;
  background: #f4f8ff;
}

.sidebar-link.is-active {
  color: var(--accent);
  border-color: #cfe1ff;
  background: var(--accent-soft);
  font-weight: 600;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: 16px;
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
