<template>
  <div class="app-wrapper">
    <!-- 统一导航栏 -->
    <nav v-if="showNav" class="navbar">
      <div class="nav-brand">
        <span class="logo">✨</span>
        <span class="brand-text">ATMR 心理测评</span>
      </div>
      <div class="nav-links">
        <router-link to="/history" :class="['nav-link', { active: $route.path === '/history' }]">
          <span class="nav-icon">📋</span>
          历史记录
        </router-link>
        <router-link to="/assessment" :class="['nav-link', { active: $route.path === '/assessment' }]">
          <span class="nav-icon">📝</span>
          开始测评
        </router-link>
      </div>
      <div class="nav-user">
        <span class="username">{{ username }}</span>
        <button class="logout-btn" @click="logout">
          <span class="nav-icon">🚪</span>
          退出
        </button>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main :class="['main-content', { 'with-nav': showNav }]">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const showNav = computed(() => route.path !== '/login')
const username = computed(() => localStorage.getItem('username') || '用户')

const logout = () => {
  localStorage.removeItem('userId')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<style>
/* ========== 全局配色变量 ========== */
:root {
  --primary: #6366f1;
  --primary-dark: #4f46e5;
  --primary-light: #818cf8;
  --secondary: #06b6d4;
  --accent: #f472b6;
  --bg-dark: #ffffff;
  --bg-card: #ffffff;
  --bg-hover: #f8fafc;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
  --border: #e5e7eb;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.04);
  --shadow-xl: 0 20px 40px -12px rgba(0, 0, 0, 0.15);
  --shadow-inner: inset 0 2px 4px 0 rgba(0, 0, 0, 0.06);
  --gradient-primary: linear-gradient(135deg, var(--primary), var(--primary-dark));
  --gradient-success: linear-gradient(135deg, var(--success), #059669);
  --gradient-warning: linear-gradient(135deg, var(--warning), #d97706);
  --gradient-secondary: linear-gradient(135deg, var(--secondary), #0891b2);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 350ms ease;
}

/* ========== 全局重置 ========== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-dark);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
}

/* ========== 导航栏 ========== */
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 72px;
  background: rgba(255, 255, 255, 0.85);
  border-bottom: 1px solid rgba(229, 231, 235, 0.6);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  z-index: 100;
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  font-size: 34px;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.logo:hover {
  transform: scale(1.1);
}

.brand-text {
  font-size: 28px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

.nav-links {
  display: flex;
  gap: 8px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 28px;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 18px;
  font-weight: 600;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.nav-link.active {
  background: var(--gradient-primary);
  color: white;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3);
}

.nav-icon {
  font-size: 20px;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
  transition: transform 0.2s ease;
}

.nav-link:hover .nav-icon {
  transform: translateY(-2px);
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 16px;
}

.username {
  color: var(--text-secondary);
  font-size: 17px;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  border-color: var(--error);
  color: var(--error);
  background: rgba(239, 68, 68, 0.1);
}

/* ========== 主内容区 ========== */
.main-content {
  min-height: 100vh;
  width: 100%;
  max-width: 2400px;
  margin: 0 auto;
  padding: 0 64px;
}

.main-content.with-nav {
  padding-top: 88px;
}

/* ========== 通用卡片样式 ========== */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  transition: all var(--transition-normal);
}

.card:hover {
  box-shadow: var(--shadow-xl);
  transform: translateY(-4px);
}

/* ========== 通用按钮样式 ========== */
.btn {
  padding: 16px 32px;
  border-radius: var(--radius-lg);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-normal);
  border: none;
  position: relative;
  overflow: hidden;
}

.btn-primary {
  background: var(--gradient-primary);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 24px rgba(99, 102, 241, 0.3);
}

.btn-primary:active {
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
  border: 2px solid var(--border);
}

.btn-secondary:hover {
  background: var(--border);
  border-color: var(--primary-light);
  transform: translateY(-2px);
}

/* ========== 通用输入框样式 ========== */
.input {
  width: 100%;
  padding: 14px 18px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 15px;
  transition: all 0.2s;
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.input::placeholder {
  color: var(--text-muted);
}

/* ========== 动画 ========== */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: fadeIn 0.4s ease;
}

/* ========== 统一页面壳层 ========== */
.page-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 28px;
  align-items: start;
  width: 100%;
}

.page-layout--no-sidebar {
  display: block;
}

.page-sidebar {
  position: sticky;
  top: 100px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  padding: 20px 16px;
  max-height: calc(100vh - 124px);
  overflow: hidden;
}

.sidebar-header {
  padding: 4px 8px 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}

.sidebar-header h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.sidebar-header p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  max-height: calc(100vh - 220px);
  padding-right: 4px;
}

.sidebar-item {
  width: 100%;
  text-align: left;
  background: var(--bg-hover);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: 12px 14px;
  cursor: pointer;
  transition: all var(--transition-normal);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: inherit;
  font-size: inherit;
}

.sidebar-item:hover {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.06);
  transform: translateX(2px);
}

.sidebar-item.active {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.1);
}

.sidebar-item-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-item-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.sidebar-actions {
  margin-bottom: 12px;
}

/* ========== 统一页面头 ========== */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

/* ========== 统一状态块 ========== */
.state-block {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.state-block .state-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.state-block h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.state-block p {
  font-size: 15px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ========== 统一危险操作按钮 ========== */
.btn-danger {
  padding: 12px 20px;
  background: transparent;
  border: 1px solid var(--error);
  border-radius: var(--radius-md);
  color: var(--error);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.08);
}

.btn-ghost {
  padding: 12px 20px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.btn-ghost:hover {
  border-color: var(--primary);
  color: var(--primary);
  transform: translateY(-2px);
}

/* ========== 大屏幕优化 ========== */
@media (min-width: 1600px) {
  .main-content {
    padding: 0 64px;
  }

  .navbar {
    padding: 0 48px;
  }

  .nav-links {
    gap: 16px;
  }

  .nav-link {
    padding: 16px 32px;
    font-size: 18px;
  }
}

/* ========== 响应式设计 ========== */
@media (max-width: 1200px) {
  .page-layout {
    grid-template-columns: 1fr;
  }

  .page-sidebar {
    position: static;
    max-height: none;
  }

  .sidebar-list {
    max-height: none;
  }
}

@media (max-width: 768px) {
  .navbar {
    height: 60px;
    padding: 0 16px;
  }

  .logo {
    font-size: 28px;
  }

  .brand-text {
    font-size: 20px;
  }

  .nav-link {
    padding: 10px 16px;
    font-size: 16px;
  }

  .nav-icon {
    font-size: 18px;
  }

  .main-content {
    padding: 0 16px;
  }

  .main-content.with-nav {
    padding-top: 72px;
  }
}

@media (max-width: 480px) {
  .navbar {
    flex-direction: column;
    height: auto;
    padding: 12px 16px;
    gap: 12px;
  }

  .nav-links {
    width: 100%;
    justify-content: center;
  }

  .nav-user {
    width: 100%;
    justify-content: center;
  }

  .main-content.with-nav {
    padding-top: 120px;
  }
}
</style>
