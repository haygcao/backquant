<template>
  <div class="market-data-page">
    <div class="page-container">
      <div class="page-header">
        <div class="title-section">
          <h2>数据管理</h2>
        </div>
        <div class="nav-section">
          <router-link
            v-for="tab in tabs"
            :key="tab.id"
            :to="tab.path"
            class="nav-tab"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                :d="tab.iconPath"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
            </svg>
            <span>{{ tab.label }}</span>
          </router-link>
        </div>
      </div>

      <div class="page-body">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MarketDataLayout',
  data() {
    return {
      tabs: [
        {
          id: 'overview',
          label: '数据全景',
          path: '/market-data/overview',
          iconPath: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6'
        },
        {
          id: 'config',
          label: '下载配置',
          path: '/market-data/config',
          iconPath: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z'
        },
        {
          id: 'packages',
          label: 'Python包管理',
          path: '/market-data/packages',
          iconPath: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'
        }
      ]
    };
  }
};
</script>

<style scoped>
.market-data-page {
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

.nav-section {
  display: flex;
  gap: 4px;
  align-items: center;
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid transparent;
  border-radius: 2px;
  text-decoration: none;
  color: #666;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.nav-tab:hover {
  background: #f5f5f5;
  color: #000;
}

.nav-tab.router-link-active {
  background: #fff;
  border-color: #d0d0d0;
  color: #000;
}

.nav-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.page-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
