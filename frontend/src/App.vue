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
  --bg-card: #f8fafc;
  --bg-hover: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
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
  height: 64px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 100;
  backdrop-filter: blur(10px);
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
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary-light), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-links {
  display: flex;
  gap: 8px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 10px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 17px;
  font-weight: 500;
  transition: all 0.2s;
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-link.active {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
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
  max-width: 1800px;
  margin: 0 auto;
  padding: 0 24px;
}

.main-content.with-nav {
  padding-top: 64px;
}

/* ========== 通用卡片样式 ========== */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
}

/* ========== 通用按钮样式 ========== */
.btn {
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

.btn-secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.btn-secondary:hover {
  background: var(--border);
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
</style>
