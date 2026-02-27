<template>
  <div class="market-data-page">
    <div class="page-container">
      <div class="page-header">
        <div class="title-section">
          <h2>行情数据管理</h2>
        </div>
        <div class="nav-section">
          <router-link to="/market-data/overview" class="nav-tab">数据全景</router-link>
          <router-link to="/market-data/download" class="nav-tab">手动下载</router-link>
          <router-link to="/market-data/config" class="nav-tab">下载配置</router-link>
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
  name: 'MarketDataLayout'
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

.page-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
