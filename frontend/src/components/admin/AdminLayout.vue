<template>
  <section class="admin-shell">
    <header class="admin-header">
      <div>
        <p class="admin-kicker">ATMR 质量治理后台</p>
        <h1>管理端</h1>
      </div>
      <div class="admin-tabs">
        <router-link to="/admin/dashboard" :class="['admin-tab', { active: route.path === '/admin/dashboard' }]">首页</router-link>
        <router-link to="/admin/questions" :class="['admin-tab', { active: route.path === '/admin/questions' }]">题库质量</router-link>
        <router-link to="/admin/reports" :class="['admin-tab', { active: route.path === '/admin/reports' }]">报告质量</router-link>
        <router-link to="/admin/experiments" :class="['admin-tab', { active: route.path === '/admin/experiments' }]">实验结果</router-link>
      </div>
    </header>
    <router-view />
  </section>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.admin-shell {
  width: min(1440px, 100%);
  margin: 0 auto;
  padding: 12px 0 48px;
}

.admin-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.admin-kicker {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 700;
}

.admin-header h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
}

.admin-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.admin-tab {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  padding: 0 14px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 700;
  border: 1px solid rgba(17, 17, 17, 0.08);
  background: rgba(255, 255, 255, 0.62);
}

.admin-tab.active,
.admin-tab:hover {
  color: #fff;
  background: var(--primary);
}

@media (max-width: 768px) {
  .admin-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .admin-tabs {
    justify-content: flex-start;
  }
}
</style>
