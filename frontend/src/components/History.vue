<template>
  <div class="history-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">测评记录</h1>
        <p class="page-subtitle">共 {{ sessions.length }} 次测评</p>
      </div>
      <button class="btn btn-primary" @click="startNewSession">
        <span>+</span> 开始新测评
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="sessions.length === 0" class="empty-state">
      <div class="empty-icon">📋</div>
      <h3>暂无测评记录</h3>
      <p>点击上方按钮开始您的第一次心理测评</p>
    </div>

    <div v-else class="sessions-grid">
      <div v-for="s in sessions" :key="s.session_id" class="session-card">
        <div class="card-header">
          <div class="session-date">
            <span class="date-day">{{ formatDay(s.started_at) }}</span>
            <span class="date-month">{{ formatMonth(s.started_at) }}</span>
          </div>
          <span :class="['status-badge', s.status]">
            {{ s.status === 'completed' ? '已完成' : '进行中' }}
          </span>
        </div>

        <div class="card-body">
          <div class="stats-row">
            <div class="stat-item">
              <span class="stat-value">{{ s.question_count }}</span>
              <span class="stat-label">题目</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value">{{ s.total_score }}</span>
              <span class="stat-label">总分</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value" :class="{ warning: s.anomaly_count > 0 }">
                {{ s.anomaly_count }}
              </span>
              <span class="stat-label">异常</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <span class="session-time">{{ formatTime(s.started_at) }}</span>
          <div class="card-actions">
            <button v-if="s.has_report" class="btn-view" @click="viewReport(s.session_id)">查看报告 →</button>
            <button v-if="s.has_report" class="btn-chat" @click="goToChat(s.session_id)">💬 咨询</button>
            <button class="btn-delete" @click="deleteSession(s.session_id)">删除记录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()

const sessions = ref([])
const loading = ref(true)

const fetchHistory = async () => {
  try {
    const res = await api.get('/assessment/history')
    sessions.value = res.data.sessions
  } catch (err) {
    console.error('获取历史记录失败:', err)
  } finally {
    loading.value = false
  }
}

const startNewSession = async () => {
  try {
    const res = await api.post('/assessment/start-session', {})
    router.push({ path: '/assessment', query: { sessionId: res.data.session_id } })
  } catch (err) {
    console.error('创建会话失败:', err)
    alert('创建会话失败，请检查后端服务')
  }
}

const viewReport = (sessionId) => {
  router.push(`/report/${sessionId}`)
}

const goToChat = (sessionId) => {
  router.push({ path: '/chat', query: { sessionId } })
}

const deleteSession = async (sessionId) => {
  if (!confirm('确定要删除这次测评记录吗？删除后无法恢复。')) return
  try {
    await api.delete(`/assessment/session/${sessionId}`)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
  } catch (err) {
    console.error('删除记录失败:', err)
    alert(err.response?.data?.detail || '删除失败')
  }
}

const formatDay = (isoStr) => {
  if (!isoStr) return '--'
  return new Date(isoStr).getDate().toString().padStart(2, '0')
}

const formatMonth = (isoStr) => {
  if (!isoStr) return ''
  const months = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
  return months[new Date(isoStr).getMonth()]
}

const formatTime = (isoStr) => {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchHistory)
</script>

<style scoped>
.history-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

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
  font-size: 16px;
  color: var(--text-secondary);
  margin: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn span {
  font-size: 18px;
  line-height: 1;
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

.loading-state, .empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
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

.sessions-grid {
  display: grid;
  gap: 16px;
}

.session-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.2s;
}

.session-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.session-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--bg-dark);
  border-radius: 12px;
  padding: 12px 16px;
  min-width: 60px;
}

.date-day {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary-light);
  line-height: 1;
}

.date-month {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-top: 4px;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.completed {
  background: rgba(34, 197, 94, 0.15);
  color: var(--success);
}

.status-badge.active {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning);
}

.card-body {
  margin-bottom: 20px;
}

.stats-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.warning {
  color: var(--error);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: var(--border);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.card-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.session-time {
  font-size: 13px;
  color: var(--text-muted);
}

.btn-view, .btn-chat, .btn-delete {
  padding: 8px 16px;
  background: transparent;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-view {
  border: 1px solid var(--primary);
  color: var(--primary-light);
}

.btn-view:hover {
  background: var(--primary);
  color: white;
}

.btn-chat {
  border: 1px solid var(--secondary);
  color: var(--secondary);
}

.btn-chat:hover {
  background: var(--secondary);
  color: var(--bg-dark);
}

.btn-delete {
  border: 1px solid var(--error);
  color: var(--error);
}

.btn-delete:hover {
  background: var(--error);
  color: white;
}

.no-report {
  font-size: 13px;
  color: var(--text-muted);
}
</style>
