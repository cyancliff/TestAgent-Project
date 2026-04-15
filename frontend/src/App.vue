<template>
  <div class="app-wrapper">
    <!-- 动态微调光晕背景 -->
    <div class="ambient-background">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

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
        <div class="avatar-wrapper" @click="triggerAvatarUpload" title="点击更换头像">
          <img v-if="avatarUrl" :src="avatarUrl" class="nav-avatar" alt="头像" />
          <span v-else class="nav-avatar-fallback">{{ usernameInitial }}</span>
          <div class="avatar-overlay">
            <span>换</span>
          </div>
          <input
            ref="avatarInput"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            style="display:none"
            @change="handleAvatarUpload"
          />
        </div>
        <span class="username">{{ username }}</span>
        <button class="logout-btn" @click="logout">
          <span class="nav-icon">🚪</span>
          退出
        </button>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main :class="['main-content', { 'with-nav': showNav }]">
      <router-view v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from './api'

const route = useRoute()
const router = useRouter()

const showNav = computed(() => route.path !== '/login')
const username = computed(() => localStorage.getItem('username') || '用户')
const avatarUrl = ref(localStorage.getItem('avatarUrl') || '')
const usernameInitial = computed(() => (username.value || '?')[0].toUpperCase())
const avatarInput = ref(null)

const triggerAvatarUpload = () => {
  avatarInput.value?.click()
}

const handleAvatarUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    alert('图片大小不能超过 2MB')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await api.post('/auth/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    avatarUrl.value = res.data.avatar_url
    localStorage.setItem('avatarUrl', res.data.avatar_url)
  } catch (err) {
    alert(err.response?.data?.detail || '头像上传失败')
  }
  // 重置 input 以便再次选择同一文件
  e.target.value = ''
}

const logout = () => {
  localStorage.removeItem('userId')
  localStorage.removeItem('username')
  localStorage.removeItem('avatarUrl')
  router.push('/login')
}
</script>

<style>
/* ========== 全局配色变量 ========== */
:root {
  /* 恢复原版主色与浅色明亮主题 */
  --primary: #6366f1;
  --primary-dark: #4f46e5;
  --primary-light: #818cf8;
  --secondary: #06b6d4;
  --accent: #f472b6;
  
  /* 浅色系环境，保留微透明实现Bright Glassmorphism */
  --bg-base: #f8fafc;       /* 浅灰色底层 */
  --bg-dark: transparent;
  --bg-card: rgba(255, 255, 255, 0.6); /* 卡片半透明白 */
  --bg-hover: rgba(255, 255, 255, 0.9);
  
  /* 恢复深色高对比文案 */
  --text-primary: #111827;
  --text-secondary: #4b5563;
  --text-muted: #9ca3af;
  
  /* 亮色模式折射边框 */
  --border: rgba(255, 255, 255, 0.4);
  
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  
  --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  --shadow-lg: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.02);
  --shadow-xl: 0 20px 40px -12px rgba(0, 0, 0, 0.08);
  --shadow-inner: inset 0 2px 4px 0 rgba(0, 0, 0, 0.02);
  --shadow-glow: 0 0 20px rgba(99, 102, 241, 0.15); /* 柔和的发光阴影 */

  --gradient-primary: linear-gradient(135deg, var(--primary), var(--primary-dark));
  --gradient-success: linear-gradient(135deg, var(--success), #059669);
  --gradient-warning: linear-gradient(135deg, var(--warning), #d97706);
  --gradient-secondary: linear-gradient(135deg, var(--secondary), #0891b2);
  
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1);
  --safe-area-inset-top: env(safe-area-inset-top, 0px);
}

/* ========== 全局重置 ========== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--bg-base); /* 使用浅色底色 */
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ========== 背景动态流光动画 ========== */
.ambient-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: -1;
  background: var(--bg-base);
  pointer-events: none; /* 防止遮挡阻断点击事件 */
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.25; /* 浅色模式下降低透明度更清醒 */
  animation: floatBlobs 20s infinite alternate ease-in-out;
}

.blob-1 {
  top: -10%; left: -10%;
  width: 50vw; height: 50vw;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.5) 0%, rgba(255,255,255,0) 70%);
  animation-delay: 0s;
}

.blob-2 {
  bottom: -20%; right: -10%;
  width: 60vw; height: 60vw;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.4) 0%, rgba(255,255,255,0) 70%);
  animation-delay: -5s;
}

.blob-3 {
  top: 40%; left: 40%;
  width: 40vw; height: 40vw;
  background: radial-gradient(circle, rgba(244, 114, 182, 0.3) 0%, rgba(255,255,255,0) 70%);
  animation-delay: -10s;
}

@keyframes floatBlobs {
  0% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(3%, 5%) scale(1.05); }
  66% { transform: translate(-2%, 8%) scale(0.95); }
  100% { transform: translate(-4%, -2%) scale(1); }
}

/* ========== 路由切换动画 ========== */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(15px) scale(0.98);
}

/* ========== 应用包装器 ========== */
.app-wrapper {
  position: relative;
  min-height: 100vh;
}

/* ========== 导航栏 ========== */
.navbar {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  min-height: 72px;
  --nav-height: calc(72px + var(--safe-area-inset-top));
  padding: var(--safe-area-inset-top) 32px 0 32px;
  background: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 100;
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05);
  overflow: visible;
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

.avatar-wrapper {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  overflow: hidden;
}

.nav-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid var(--border);
  transition: border-color 0.2s;
}

.nav-avatar-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--gradient-primary);
  color: white;
  font-size: 18px;
  font-weight: 700;
  border: 2px solid transparent;
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.avatar-wrapper:hover .avatar-overlay {
  opacity: 1;
}

.avatar-wrapper:hover .nav-avatar {
  border-color: var(--primary);
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
  padding-top: 24px;
}

/* ========== 通用卡片样式 ========== */
.card {
  background: var(--bg-card);
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg), inset 0 1px 0 0 rgba(255, 255, 255, 0.9);
  transition: all var(--transition-slow);
}

.card:hover {
  box-shadow: var(--shadow-xl), var(--shadow-glow);
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 1);
}

/* ========== 通用按钮样式 ========== */
.btn {
  padding: 16px 32px;
  border-radius: var(--radius-lg);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: all var(--transition-normal);
  border: none;
  position: relative;
  overflow: hidden;
}

.btn-primary {
  background: var(--gradient-primary);
  color: white;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
}

.btn-primary:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 12px 24px rgba(99, 102, 241, 0.35);
}

.btn-primary:active {
  transform: translateY(-1px) scale(0.98);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-primary);
  border: 1px solid var(--border);
  backdrop-filter: blur(8px);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.05);
}

/* ========== 通用输入框样式 ========== */
.input {
  width: 100%;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 500;
  transition: all 0.3s ease;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02);
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02), 0 0 0 3px rgba(99, 102, 241, 0.2);
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
  top: calc(var(--nav-height) + 24px);
  background: var(--bg-card);
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg), inset 0 1px 0 0 rgba(255, 255, 255, 0.9);
  padding: 20px 16px;
  max-height: calc(100vh - var(--nav-height) - 48px);
  overflow: hidden;
  transition: all var(--transition-slow);
}

.page-sidebar:hover {
  box-shadow: var(--shadow-xl), var(--shadow-glow);
  border-color: rgba(255, 255, 255, 1);
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
  font-size: 34px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  letter-spacing: -0.02em;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.05); /* 轻微文字投影，防止浅色下重影 */
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  font-weight: 400;
  letter-spacing: 0.01em;
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
    min-height: 60px;
    --nav-height: calc(60px + var(--safe-area-inset-top));
    padding: var(--safe-area-inset-top) 16px 0 16px;
  }

  .logo {
    font-size: 26px;
  }

  .brand-text {
    font-size: 18px;
  }

  .nav-link {
    padding: 8px 14px;
    font-size: 15px;
  }

  .nav-icon {
    font-size: 16px;
  }

  .main-content {
    padding: 0 12px;
  }

  .main-content.with-nav {
    padding-top: 16px;
  }

  .sidebar-item-title {
    font-size: 14px;
  }
  .sidebar-item-meta {
    font-size: 11px;
  }
}

@media (max-width: 480px) {
  .navbar {
    flex-direction: column;
    height: auto;
    --nav-height: calc(100px + var(--safe-area-inset-top));
    padding: calc(12px + var(--safe-area-inset-top)) 12px 12px 12px;
    gap: 12px;
  }

  .nav-brand,
  .nav-links,
  .nav-user {
    max-width: 100%;
  }

  .logo {
    font-size: 24px;
  }

  .brand-text {
    font-size: 18px;
  }

  .nav-links {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .nav-link {
    white-space: nowrap;
    overflow: visible;
    max-width: 100%;
    padding: 8px 12px;
    font-size: 14px;
  }

  .nav-icon {
    font-size: 16px;
  }

  .nav-user {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .username {
    white-space: nowrap;
    overflow: visible;
    max-width: 100%;
    font-size: 14px;
  }

  .logout-btn {
    padding: 8px 12px;
    font-size: 14px;
  }

  .main-content.with-nav {
    padding-top: 20px;
  }
}
</style>
