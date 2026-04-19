<template>
  <div class="login-page">
    <div class="login-card animate-fade-in">
      <div class="brand-header">
        <img :src="atmrLogo" class="login-logo" alt="ATMR logo" />
        <h1 class="app-title">ATMR 测评系统</h1>
        <p class="app-subtitle">多智能体辩论驱动的深度心理画像</p>
      </div>

      <div class="tab-switch">
        <button :class="['tab-btn', { active: isLogin }]" @click="isLogin = true">
          登录
        </button>
        <button :class="['tab-btn', { active: !isLogin }]" @click="isLogin = false">
          注册
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="input-group">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="请输入用户名" required />
        </div>
        <div class="input-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" required />
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import atmrLogo from '../assets/atmr-logo.png'

const router = useRouter()

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const errorMsg = ref('')
const loading = ref(false)

const handleSubmit = async () => {
  errorMsg.value = ''
  loading.value = true
  const endpoint = isLogin.value ? 'login' : 'register'

  try {
    const res = await api.post(`/auth/${endpoint}`, {
      username: username.value,
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
    errorMsg.value = err.response?.data?.detail || '请求失败，请检查后端服务'
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
  margin-bottom: 20px;
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
