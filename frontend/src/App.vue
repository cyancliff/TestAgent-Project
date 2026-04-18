<template>
  <div class="app-wrapper">
    <!-- 动态微调光晕背景 -->
    <div class="ambient-background">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <!-- 统一导航栏 -->
    <nav v-if="showNav" ref="navRef" class="navbar">
      <div class="nav-brand">
        <img :src="atmrLogo" class="nav-logo" alt="ATMR logo" />
        <span class="brand-text">ATMR</span>
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
      <div class="nav-user" ref="userMenuRef">
        <button class="user-menu-trigger" type="button" @click="toggleUserMenu" :aria-expanded="showUserMenu">
          <div class="avatar-wrapper" title="用户菜单">
            <img v-if="avatarUrl" :src="avatarUrl" class="nav-avatar" alt="头像" @error="handleAvatarLoadError" />
            <span v-else class="nav-avatar-fallback">{{ usernameInitial }}</span>
          </div>
          <span class="user-menu-caret">{{ showUserMenu ? '▲' : '▼' }}</span>
        </button>

        <transition name="menu-fade">
          <div v-if="showUserMenu" class="user-menu-panel">
            <div class="user-menu-card">
              <div class="user-menu-avatar-shell" @click="triggerAvatarUpload">
                <img v-if="avatarUrl" :src="avatarUrl" class="user-menu-avatar" alt="头像" @error="handleAvatarLoadError" />
                <span v-else class="user-menu-avatar user-menu-avatar-fallback">{{ usernameInitial }}</span>
              </div>
              <div class="user-menu-name">{{ username }}</div>
              <div class="user-menu-subtitle">{{ userSubtitle }}</div>
            </div>

            <div class="user-menu-list">
              <button class="user-menu-item" type="button" @click="triggerAvatarUpload">
                <span class="user-menu-icon">📷</span>
                <span>更换头像</span>
              </button>
              <button class="user-menu-item user-menu-item-danger" type="button" @click="logout">
                <span class="user-menu-icon">🚪</span>
                <span>退出</span>
              </button>
            </div>

            <input
              ref="avatarInput"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              style="display:none"
              @change="handleAvatarUpload"
            />
          </div>
        </transition>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main
      :class="[
        'main-content',
        {
          'with-nav': showNav,
          'main-content--chat': isChatRoute,
          'main-content--assessment': isAssessmentRoute,
        },
      ]"
    >
      <router-view v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <AppDialog
      v-model="dialogState.open"
      :mode="dialogState.mode"
      :title="dialogState.title"
      :message="dialogState.message"
      :confirm-text="dialogState.confirmText"
      :cancel-text="dialogState.cancelText"
      :input-value="dialogState.inputValue"
      :input-label="dialogState.inputLabel"
      :input-placeholder="dialogState.inputPlaceholder"
      :input-max-length="dialogState.inputMaxLength"
      :multiline="dialogState.multiline"
      :input-rows="dialogState.inputRows"
      :destructive="dialogState.destructive"
      @update:input-value="updateDialogInputValue"
      @confirm="handleDialogConfirm"
      @cancel="handleDialogCancel"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from './api'
import atmrLogo from './assets/atmr-logo.png'
import AppDialog from './components/AppDialog.vue'
import {
  dialogState,
  handleDialogCancel,
  handleDialogConfirm,
  showAlertDialog,
  updateDialogInputValue,
} from './composables/useAppDialog'

const route = useRoute()
const router = useRouter()

const isChatRoute = computed(() => route.path.startsWith('/chat'))
const isAssessmentRoute = computed(() => route.path.startsWith('/assessment'))
const showNav = computed(() => route.path !== '/login')
const username = ref(localStorage.getItem('username') || '用户')
const avatarUrl = ref(localStorage.getItem('avatarUrl') || '')
const usernameInitial = computed(() => (username.value || '?')[0].toUpperCase())
const userSubtitle = computed(() => `@${username.value || 'user'}`)
const avatarInput = ref(null)
const navRef = ref(null)
const showUserMenu = ref(false)
const userMenuRef = ref(null)

const closeUserMenu = () => {
  showUserMenu.value = false
}

const emitUserProfileUpdated = () => {
  window.dispatchEvent(new CustomEvent('user-profile-updated'))
}

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const triggerAvatarUpload = () => {
  closeUserMenu()
  avatarInput.value?.click()
}

const handleAvatarUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    await showAlertDialog('图片大小不能超过 2MB', {
      title: '上传失败',
    })
    e.target.value = ''
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
    emitUserProfileUpdated()
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || '头像上传失败', {
      title: '上传失败',
      destructive: true,
    })
  }
  // 重置 input 以便再次选择同一文件
  e.target.value = ''
}

const handleAvatarLoadError = () => {
  avatarUrl.value = ''
  localStorage.removeItem('avatarUrl')
  emitUserProfileUpdated()
}

const syncCurrentUser = async () => {
  const token = localStorage.getItem('token')
  if (!token) return
  try {
    const res = await api.get('/auth/me')
    if (res.data?.username) {
      username.value = res.data.username
      localStorage.setItem('username', res.data.username)
    }
    if (res.data?.avatar_url) {
      avatarUrl.value = res.data.avatar_url
      localStorage.setItem('avatarUrl', res.data.avatar_url)
    } else {
      handleAvatarLoadError()
      return
    }
    emitUserProfileUpdated()
  } catch (err) {
    console.error('同步用户信息失败:', err)
  }
}

const logout = () => {
  closeUserMenu()
  localStorage.removeItem('token')
  localStorage.removeItem('userId')
  localStorage.removeItem('username')
  localStorage.removeItem('avatarUrl')
  username.value = '用户'
  avatarUrl.value = ''
  router.push('/login')
}

const handleClickOutside = (event) => {
  if (!userMenuRef.value?.contains(event.target)) {
    closeUserMenu()
  }
}

const updateNavHeight = () => {
  const navHeight = showNav.value ? Math.ceil(navRef.value?.getBoundingClientRect().height || 0) : 0
  document.documentElement.style.setProperty('--nav-height', `${navHeight}px`)
}

watch(
  [() => route.fullPath, showNav],
  async () => {
    await nextTick()
    updateNavHeight()
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', updateNavHeight)
  syncCurrentUser()
  updateNavHeight()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', updateNavHeight)
  document.documentElement.style.setProperty('--nav-height', '0px')
})
</script>

<style>
/* ========== 全局配色变量 ========== */
:root {
  --nav-height: 0px;
  /* 恢复原版主色与浅色明亮主题 */
  --primary: #18181b;
  --primary-dark: #000000;
  --primary-light: #52525b;
  --secondary: #3f3f46;
  --accent: #71717a;
  
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
  --shadow-glow: 0 0 20px rgba(17, 17, 17, 0.12); /* 柔和的发光阴影 */

  --gradient-primary: linear-gradient(135deg, var(--primary), var(--primary-dark));
  --gradient-success: linear-gradient(135deg, var(--success), #059669);
  --gradient-warning: linear-gradient(135deg, var(--warning), #d97706);
  --gradient-secondary: linear-gradient(135deg, var(--secondary), #18181b);
  
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
  overflow-x: hidden;
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
  background: radial-gradient(circle, rgba(17, 17, 17, 0.16) 0%, rgba(255,255,255,0) 70%);
  animation-delay: 0s;
}

.blob-2 {
  bottom: -20%; right: -10%;
  width: 60vw; height: 60vw;
  background: radial-gradient(circle, rgba(64, 64, 64, 0.14) 0%, rgba(255,255,255,0) 70%);
  animation-delay: -5s;
}

.blob-3 {
  top: 40%; left: 40%;
  width: 40vw; height: 40vw;
  background: radial-gradient(circle, rgba(113, 113, 122, 0.12) 0%, rgba(255,255,255,0) 70%);
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
  overflow-x: clip;
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
  min-width: 0;
}

.nav-logo {
  width: 48px;
  height: 48px;
  object-fit: contain;
  filter: drop-shadow(0 6px 14px rgba(17, 24, 39, 0.12));
  transition: transform 0.3s ease;
}

.nav-logo:hover {
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
  min-width: 0;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 48px;
  padding: 0 28px;
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
  box-shadow: 0 6px 20px rgba(17, 17, 17, 0.22);
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
  position: relative;
  justify-content: flex-end;
  height: 48px;
  flex-shrink: 0;
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

.user-menu-trigger {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 48px;
  padding: 0 12px 0 6px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 999px;
  cursor: pointer;
  transition: all var(--transition-normal);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.user-menu-trigger:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}

.avatar-wrapper:hover .nav-avatar {
  border-color: var(--primary);
}

.user-menu-caret {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1;
}

.user-menu-panel {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  width: min(248px, calc(100vw - 24px));
  max-height: calc(100dvh - var(--nav-height) - 24px);
  padding: 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.96);
  color: var(--text-primary);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
  border: 1px solid rgba(148, 163, 184, 0.18);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  overflow-y: auto;
}

.user-menu-card {
  background: linear-gradient(180deg, rgba(17, 17, 17, 0.05), rgba(255, 255, 255, 0.95));
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 18px;
  padding: 22px 16px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  margin-bottom: 10px;
}

.user-menu-avatar-shell {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(17, 17, 17, 0.1);
  transition: transform var(--transition-normal);
}

.user-menu-avatar-shell:hover {
  transform: scale(1.03);
}

.user-menu-avatar {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid rgba(17, 17, 17, 0.12);
}

.user-menu-avatar-fallback {
  background: var(--gradient-primary);
  color: white;
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-menu-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.user-menu-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.user-menu-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.user-menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 10px;
  background: transparent;
  color: var(--text-primary);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
  transition: background var(--transition-normal), transform var(--transition-normal);
}

.user-menu-item:hover {
  background: rgba(17, 17, 17, 0.06);
  transform: translateX(2px);
}

.user-menu-item-danger {
  color: var(--error);
}

.user-menu-icon {
  width: 20px;
  text-align: center;
  font-size: 16px;
  flex-shrink: 0;
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ========== 主内容区 ========== */
.main-content {
  min-height: 100vh;
  width: 100%;
  max-width: 2400px;
  margin: 0 auto;
  padding: 0 64px;
  min-width: 0;
}

.main-content.with-nav {
  padding-top: 24px;
}

.main-content.main-content--chat {
  max-width: none;
  min-height: calc(100dvh - var(--nav-height));
  height: calc(100dvh - var(--nav-height));
  box-sizing: border-box;
  padding: 0;
  overflow: hidden;
}

.main-content.main-content--assessment {
  max-width: none;
  min-height: calc(100dvh - var(--nav-height));
  height: calc(100dvh - var(--nav-height));
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 12px 20px 14px;
  overflow-x: hidden;
  overflow-y: auto;
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
  box-shadow: 0 4px 15px rgba(17, 17, 17, 0.16);
}

.btn-primary:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 12px 24px rgba(17, 17, 17, 0.24);
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
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02), 0 0 0 3px rgba(17, 17, 17, 0.12);
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

.page-layout > * {
  min-width: 0;
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
  background: rgba(17, 17, 17, 0.05);
  transform: translateX(2px);
}

.sidebar-item.active {
  border-color: var(--primary);
  background: rgba(17, 17, 17, 0.08);
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
    min-height: 68px;
    --nav-height: calc(68px + var(--safe-area-inset-top));
    padding: var(--safe-area-inset-top) 16px 0 16px;
  }

  .nav-logo {
    width: 42px;
    height: 42px;
  }

  .brand-text {
    font-size: 24px;
  }

  .nav-link {
    height: 44px;
    padding: 0 16px;
    font-size: 17px;
  }

  .nav-icon {
    font-size: 18px;
  }

  .main-content {
    padding: 0 12px;
  }

  .main-content.with-nav {
    padding-top: 16px;
  }

  .main-content.main-content--assessment {
    min-height: calc(100dvh - var(--nav-height));
    height: auto;
    padding: 12px;
    overflow: visible;
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
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    min-height: 72px;
    height: auto;
    --nav-height: calc(72px + var(--safe-area-inset-top));
    padding: calc(12px + var(--safe-area-inset-top)) 10px 12px;
    gap: 6px;
  }

  .nav-brand,
  .nav-links,
  .nav-user {
    max-width: 100%;
  }

  .nav-logo {
    width: 32px;
    height: 32px;
  }

  .brand-text {
    font-size: 20px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .nav-brand {
    grid-column: 1;
    justify-self: start;
    min-width: 0;
    max-width: 100%;
    gap: 4px;
  }

  .nav-links {
    grid-column: 2;
    justify-self: stretch;
    width: 100%;
    flex: 0 1 auto;
    justify-content: center;
    flex-wrap: nowrap;
    gap: 4px;
    min-width: 0;
  }

  .nav-link {
    flex: 0 1 auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
    height: 40px;
    padding: 0 10px;
    font-size: 14px;
    gap: 4px;
  }

  .nav-icon {
    font-size: 14px;
  }

  .nav-user {
    grid-column: 3;
    justify-self: end;
    width: auto;
    height: 40px;
    justify-content: flex-end;
    flex: 0 0 auto;
  }

  .user-menu-trigger {
    height: 40px;
    padding: 0 8px 0 4px;
  }

  .avatar-wrapper {
    width: 32px;
    height: 32px;
  }

  .nav-avatar-fallback {
    font-size: 14px;
  }

  .user-menu-caret {
    font-size: 13px;
  }

  .user-menu-panel {
    position: fixed;
    top: calc(var(--nav-height) + 8px);
    right: 12px;
    left: auto;
    width: min(220px, calc(100vw - 24px));
    border-radius: 18px;
    padding: 12px;
  }

  .user-menu-card {
    padding: 18px 14px 14px;
  }

  .user-menu-avatar-shell {
    width: 64px;
    height: 64px;
  }

  .user-menu-avatar {
    width: 52px;
    height: 52px;
  }

  .user-menu-name {
    font-size: 16px;
  }

  .user-menu-subtitle {
    font-size: 12px;
  }

  .user-menu-item {
    padding: 11px 9px;
    font-size: 14px;
  }

  .main-content.with-nav {
    padding-top: 18px;
  }

  .main-content.main-content--assessment {
    min-height: calc(100dvh - var(--nav-height));
    height: auto;
    padding: 8px 6px 10px;
    overflow: visible;
  }
}

@media (max-width: 360px) {
  .navbar {
    grid-template-columns: minmax(0, 1fr) auto auto;
    padding: calc(12px + var(--safe-area-inset-top)) 8px 12px;
    gap: 4px;
  }

  .nav-logo {
    width: 28px;
    height: 28px;
  }

  .brand-text {
    font-size: 18px;
  }

  .nav-links {
    gap: 2px;
  }

  .nav-link {
    padding: 0 8px;
    font-size: 14px;
  }

  .nav-icon {
    display: none;
  }
}
</style>
