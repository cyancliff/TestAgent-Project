<template>
  <div class="login-page">
    <div class="login-card animate-fade-in">
      <div class="brand-header">
        <img :src="atmrLogo" class="login-logo" alt="ATMR logo" />
        <h1 class="app-title">ATMR 测评系统</h1>
        <p class="app-subtitle">多智能体辩论驱动的深度心理画像</p>
      </div>

      <div class="tab-switch">
        <button :class="['tab-btn', { active: isLogin }]" @click="switchMode(true)">
          登录
        </button>
        <button :class="['tab-btn', { active: !isLogin }]" @click="switchMode(false)">
          注册
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div :class="['input-group', { 'input-group--error': fieldErrors.username }]">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
            required
          />
          <p :class="['field-hint', { 'field-hint--error': fieldErrors.username }]">
            {{ fieldErrors.username || usernameHint }}
          </p>
        </div>

        <div :class="['input-group', { 'input-group--error': fieldErrors.password }]">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            :placeholder="isLogin ? '请输入密码' : '至少 8 位密码'"
            :autocomplete="isLogin ? 'current-password' : 'new-password'"
            required
          />
          <p :class="['field-hint', { 'field-hint--error': fieldErrors.password }]">
            {{ fieldErrors.password || passwordHint }}
          </p>
        </div>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '请稍候...' : (isLogin ? '登录' : '注册') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import atmrLogo from '../assets/atmr-logo.png'

const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,20}$/
const MIN_PASSWORD_LENGTH = 8

const router = useRouter()

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const errorMsg = ref('')
const loading = ref(false)
const fieldErrors = ref({
  username: '',
  password: '',
})

const usernameHint = computed(() => (
  isLogin.value
    ? '输入你注册时使用的用户名。'
    : '3-20 位，仅支持字母、数字和下划线。'
))

const passwordHint = computed(() => (
  isLogin.value
    ? '请输入你的登录密码。'
    : `至少 ${MIN_PASSWORD_LENGTH} 位，建议混合字母和数字。`
))

const resetErrors = () => {
  errorMsg.value = ''
  fieldErrors.value = {
    username: '',
    password: '',
  }
}

const switchMode = (loginMode) => {
  isLogin.value = loginMode
  resetErrors()
}

const applyServerError = (err) => {
  const status = err.response?.status
  const detail = String(err.response?.data?.detail || '')

  if (status === 404) {
    fieldErrors.value.username = '这个用户名还没有注册。'
    errorMsg.value = '没有找到对应账号，你可以检查用户名，或先完成注册。'
    return
  }

  if (status === 401) {
    fieldErrors.value.password = '密码不正确，请重新输入。'
    errorMsg.value = '密码不正确，请再试一次。'
    return
  }

  if (status === 400) {
    if (detail.includes('用户名')) {
      fieldErrors.value.username = detail
    }
    if (detail.includes('密码')) {
      fieldErrors.value.password = detail
    }
    errorMsg.value = detail || '请先检查输入内容。'
    return
  }

  errorMsg.value = '暂时无法完成请求，请稍后再试。'
}

const validateForm = () => {
  const normalizedUsername = username.value.trim()
  const normalizedPassword = password.value.trim()

  if (!normalizedUsername) {
    fieldErrors.value.username = '请输入用户名。'
  } else if (!isLogin.value && !USERNAME_PATTERN.test(normalizedUsername)) {
    fieldErrors.value.username = '用户名需为 3-20 位字母、数字或下划线。'
  }

  if (!normalizedPassword) {
    fieldErrors.value.password = '请输入密码。'
  } else if (!isLogin.value && normalizedPassword.length < MIN_PASSWORD_LENGTH) {
    fieldErrors.value.password = `密码至少需要 ${MIN_PASSWORD_LENGTH} 位。`
  }

  return !fieldErrors.value.username && !fieldErrors.value.password
}

const handleSubmit = async () => {
  resetErrors()
  if (!validateForm()) {
    return
  }

  loading.value = true
  const endpoint = isLogin.value ? 'login' : 'register'

  try {
    const res = await api.post(`/auth/${endpoint}`, {
      username: username.value.trim(),
      password: password.value,
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('userId', res.data.user_id)
    localStorage.setItem('username', res.data.username)
    localStorage.setItem('loginAccount', res.data.username)
    localStorage.setItem('nickname', res.data.nickname || res.data.username)
    if (res.data.avatar_url) {
      localStorage.setItem('avatarUrl', res.data.avatar_url)
    } else {
      localStorage.removeItem('avatarUrl')
    }
    router.push('/history')
  } catch (err) {
    applyServerError(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at top, var(--bg-dark) 0%, var(--bg-card) 50%, var(--bg-hover) 100%);
  padding: 20px;
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 56px 48px;
  width: 100%;
  max-width: 600px;
  box-shadow: var(--shadow-lg);
}

.brand-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: min(168px, 48vw);
  height: auto;
  display: block;
  margin: 0 auto 18px;
  filter: drop-shadow(0 10px 24px rgba(17, 24, 39, 0.14));
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

.app-title {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary-light), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 8px 0;
}

.app-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.tab-switch {
  display: flex;
  background: var(--bg-dark);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 28px;
  border: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
}

.auth-form {
  text-align: left;
}

.input-group {
  margin-bottom: 18px;
}

.input-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.input-group input {
  width: 100%;
  padding: 14px 16px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 15px;
  box-sizing: border-box;
  transition: all 0.2s;
}

.input-group input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(17, 17, 17, 0.12);
}

.input-group input::placeholder {
  color: var(--text-muted);
}

.input-group--error input {
  border-color: rgba(239, 68, 68, 0.6);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.08);
}

.field-hint {
  margin: 8px 2px 0;
  font-size: 13px;
  color: var(--text-muted);
}

.field-hint--error {
  color: var(--error);
}

.error-msg {
  color: var(--error);
  font-size: 13px;
  margin: 0 0 16px 0;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.submit-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(17, 17, 17, 0.24);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (max-width: 768px) {
  .login-card {
    padding: 40px 32px;
  }

  .login-logo {
    width: min(144px, 44vw);
  }

  .app-title {
    font-size: 24px;
  }

  .app-subtitle {
    font-size: 14px;
  }

  .input-group input {
    padding: 12px 14px;
    font-size: 14px;
  }

  .submit-btn {
    padding: 12px;
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .login-card {
    padding: 32px 24px;
  }

  .login-logo {
    width: min(128px, 42vw);
  }

  .app-title {
    font-size: 22px;
  }

  .app-subtitle {
    font-size: 13px;
  }

  .input-group input {
    padding: 10px 12px;
    font-size: 13px;
  }

  .submit-btn {
    padding: 10px;
    font-size: 13px;
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: fadeIn 0.5s ease;
}
</style>
