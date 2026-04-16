<template>
  <div :class="['page-layout', { 'page-layout--no-sidebar': !sessions.length }]">
    <aside v-if="!loading && sessions.length" class="page-sidebar">
      <div class="sidebar-header">
        <h3>测试导航</h3>
        <p>{{ sessions.length }} 条记录</p>
      </div>
      <div class="sidebar-list">
        <button
          v-for="s in sessions"
          :key="s.session_id"
          class="sidebar-item"
          @click="scrollToSession(s.session_id)"
        >
          <span class="sidebar-item-title">{{ formatMonth(s.started_at) }} {{ formatDay(s.started_at) }}</span>
          <span class="sidebar-item-meta">#{{ s.session_id }} · {{ s.status === 'completed' ? '已完成' : '进行中' }}</span>
        </button>
      </div>
    </aside>

    <div class="history-page">
      <div class="page-header">
        <div class="page-header-left">
          <h1 class="page-title">测评记录</h1>
          <p class="page-subtitle">共 {{ sessions.length }} 次测评</p>
        </div>
        <button class="btn-new" @click="startNewSession">
          <span class="btn-icon">+</span> 开始新测评
        </button>
      </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="sessions.length === 0" class="empty-state">
      <div class="empty-illustration">
        <div class="empty-circle">
          <span class="empty-icon">📋</span>
        </div>
      </div>
      <h3>暂无测评记录</h3>
      <p>点击下方按钮开始您的第一次心理测评</p>
      <button class="btn-new btn-new-big" @click="startNewSession">
        <span class="btn-icon">+</span> 开始新测评
      </button>
    </div>

    <div v-else class="sessions-grid">
      <div v-for="s in sessions" :key="s.session_id" :id="`session-${s.session_id}`" class="session-card">
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
            <div class="stats-row-top">
              <div class="stat-item">
                <span class="stat-value">{{ s.question_count }}</span>
                <span class="stat-label">题目</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-value">{{ s.total_score }}</span>
                <span class="stat-label">总分</span>
              </div>
            </div>
            <div class="stats-row-bottom">
              <div v-for="dim in atmrDimensions" :key="dim.key" class="stat-item dim-stat">
                <div class="dim-stat-top">
                  <span class="stat-value" :class="'dim-' + dim.key.toLowerCase()">{{ getDimScore(s, dim.key) }}分</span>
                  <span v-if="getDimLevel(s, dim.key)" class="dim-level-dot" :style="{ background: getDimLevelColor(s, dim.key) }" :title="getDimLevelLabel(s, dim.key)"></span>
                </div>
                <span class="stat-label">{{ dim.key }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="s.report_generating" class="report-generating-bar">
          <span class="generating-spinner"></span>
          <span class="generating-text">报告生成中，专家辩论正在进行...</span>
        </div>

        <div class="card-footer">
          <span class="session-time">{{ formatTime(s.started_at) }}</span>
          <div class="card-actions">
            <button v-if="s.has_report" class="btn-view" @click="viewReport(s.session_id)">查看报告 →</button>
            <span v-else-if="s.report_generating" class="btn-generating">生成中...</span>
            <button v-if="s.status === 'completed'" class="btn-edit" @click="editAnswers(s.session_id)">修改答案</button>
            <button v-if="s.has_report" class="btn-chat" @click="goToChat(s.session_id)">咨询</button>
            <button class="btn-delete" @click="deleteSession(s.session_id)">删除记录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()

const sessions = ref([])
const loading = ref(true)
let pollTimer = null

const atmrDimensions = [
  { key: 'A', name: '欣赏型', color: '#6366f1' },
  { key: 'T', name: '目标型', color: '#06b6d4' },
  { key: 'M', name: '包容型', color: '#22c55e' },
  { key: 'R', name: '责任型', color: '#f59e0b' },
]

const getDimScore = (session, key) => {
  const ds = session.dim_scores?.[key]
  if (typeof ds === 'object') return ds.score || 0
  return ds || 0
}

const getDimLevel = (session, key) => session.dim_scores?.[key]?.level || ''
const getDimLevelLabel = (session, key) => session.dim_scores?.[key]?.level_label || ''
const getDimLevelColor = (session, key) => session.dim_scores?.[key]?.level_color || '#94a3b8'

const fetchHistory = async () => {
  try {
    const res = await api.get('/assessment/history')
    sessions.value = res.data.sessions

    const hasGenerating = sessions.value.some(s => s.report_generating)
    if (hasGenerating && !pollTimer) {
      pollTimer = setInterval(pollForReports, 15000)
    } else if (!hasGenerating && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (err) {
    console.error('获取历史记录失败:', err)
  } finally {
    loading.value = false
  }
}

const pollForReports = async () => {
  try {
    const res = await api.get('/assessment/history')
    sessions.value = res.data.sessions

    const hasGenerating = sessions.value.some(s => s.report_generating)
    if (!hasGenerating && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (err) {
    console.error('轮询历史记录失败:', err)
  }
}

const startNewSession = async () => {
  try {
    const res = await api.post('/assessment/start-session', {})
    router.push({ path: '/assessment', query: { sessionId: res.data.session_id } })
  } catch (err) {
    console.error('创建会话失败:', err)
    const detail = err.response?.data?.detail || err.message || '未知错误'
    alert(`创建测评会话失败：${detail}`)
  }
}

const viewReport = (sessionId) => {
  router.push(`/report/${sessionId}`)
}

const goToChat = (sessionId) => {
  router.push({ path: '/chat', query: { assessmentSessionId: sessionId } })
}

const editAnswers = async (sessionId) => {
  try {
    await api.post(`/assessment/reopen-session/${sessionId}`)
    router.push({ path: '/assessment', query: { sessionId, mode: 'edit' } })
  } catch (err) {
    alert(err.response?.data?.detail || '打开编辑模式失败')
  }
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

const scrollToSession = (sessionId) => {
  const el = document.getElementById(`session-${sessionId}`)
  if (el) {
    const navHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 100
    const offset = navHeight + 32
    const elementPosition = el.getBoundingClientRect().top + window.pageYOffset
    const offsetPosition = elementPosition - offset
    window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
  }
}

onMounted(fetchHistory)

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.history-page {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  gap: 16px;
}

.page-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.2;
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.btn-icon {
  font-size: 20px;
  line-height: 1;
  font-weight: 400;
}

.btn-new {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  background: var(--gradient-primary);
  color: white;
  white-space: nowrap;
}

.btn-new:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
}

.loading-state, .empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  min-height: 400px;
  justify-content: center;
}

.empty-illustration {
  margin-bottom: 8px;
}

.empty-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(99, 102, 241, 0.03));
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.7;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-state p {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.btn-new-big {
  margin-top: 8px;
  padding: 14px 36px;
  font-size: 16px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.sessions-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.session-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px 28px;
  transition: all 0.25s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.session-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.12);
  transform: translateY(-1px);
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
  background: linear-gradient(135deg, var(--bg-hover), rgba(99, 102, 241, 0.06));
  border-radius: 12px;
  padding: 12px 16px;
  min-width: 64px;
}

.date-day {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1;
}

.date-month {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
  font-weight: 500;
}

.status-badge {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.completed {
  background: rgba(34, 197, 94, 0.1);
  color: var(--success);
}

.status-badge.active {
  background: rgba(245, 158, 11, 0.1);
  color: var(--warning);
}

.card-body {
  margin-bottom: 16px;
}

.stats-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.stats-row-top,
.stats-row-bottom {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-weight: 500;
}

.dim-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.dim-stat-top {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
}

.dim-level-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 4px rgba(0,0,0,0.15);
}

.stat-divider {
  width: 1px;
  height: 32px;
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
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 500;
}

.dim-a { color: #6366f1; }
.dim-t { color: #06b6d4; }
.dim-m { color: #22c55e; }
.dim-r { color: #f59e0b; }

.btn-view, .btn-edit, .btn-chat, .btn-delete {
  padding: 10px 16px;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-view {
  border: 1px solid var(--primary);
  color: var(--primary);
}

.btn-view:hover {
  background: var(--primary);
  color: white;
}

.btn-edit {
  border: 1px solid var(--warning);
  color: var(--warning);
}

.btn-edit:hover {
  background: var(--warning);
  color: white;
}

.btn-chat {
  border: 1px solid var(--secondary);
  color: var(--secondary);
}

.btn-chat:hover {
  background: var(--secondary);
  color: white;
}

.btn-delete {
  border: 1px solid var(--error);
  color: var(--error);
}

.btn-delete:hover {
  background: var(--error);
  color: white;
}

.report-generating-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(99, 102, 241, 0.1));
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 10px;
  animation: pulse-bg 2s ease-in-out infinite;
}

@keyframes pulse-bg {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.generating-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(99, 102, 241, 0.3);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

.generating-text {
  font-size: 13px;
  color: var(--primary);
  font-weight: 600;
}

.btn-generating {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-hover);
  border: 1px dashed var(--border);
  cursor: default;
}

/* 移动端 */
@media (max-width: 768px) {
  .page-sidebar {
    display: none !important;
  }

  .history-page {
    padding: 16px !important;
  }

  .session-card {
    padding: 18px 14px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
  }

  .page-header .btn-new {
    width: 100%;
    justify-content: center;
  }

  .page-title {
    font-size: 24px;
  }

  .page-subtitle {
    font-size: 14px;
  }

  .session-date {
    min-width: 56px;
    padding: 10px 12px;
  }

  .date-day {
    font-size: 22px;
  }

  .stats-row {
    gap: 14px;
  }

  .stats-row-top,
  .stats-row-bottom {
    gap: 14px;
  }

  .stats-row-bottom {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }

  .stat-divider {
    display: none;
  }

  .stats-row-top .stat-item {
    width: 50%;
  }

  .stat-value {
    font-size: 18px;
  }

  .stats-row-bottom .stat-value {
    font-size: 17px;
  }

  .stats-row-bottom .stat-label {
    font-size: 12px;
  }

  .card-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-actions {
    width: 100%;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn-view, .btn-edit, .btn-chat, .btn-delete, .btn-generating {
    flex: 1 1 calc(50% - 4px);
    text-align: center;
    padding: 10px 0;
    font-size: 13px;
  }

  .empty-state {
    min-height: 300px;
    padding: 40px 20px;
  }

  .empty-circle {
    width: 96px;
    height: 96px;
  }

  .empty-icon {
    font-size: 40px;
  }
}

@media (max-width: 480px) {
  .history-page {
    padding: 12px !important;
  }

  .session-card {
    padding: 14px 12px;
  }

  .page-title {
    font-size: 22px;
  }

  .page-subtitle {
    font-size: 13px;
  }

  .session-date {
    min-width: 48px;
    padding: 8px 10px;
  }

  .date-day {
    font-size: 20px;
  }

  .stats-row {
    gap: 10px;
  }

  .stats-row-top,
  .stats-row-bottom {
    gap: 10px;
  }

  .stats-row-bottom {
    gap: 6px;
  }

  .stat-value {
    font-size: 16px;
  }

  .stats-row-bottom .stat-value {
    font-size: 15px;
  }

  .dim-stat-top {
    gap: 4px;
  }

  .card-footer {
    gap: 10px;
  }

  .card-actions {
    gap: 6px;
  }

  .btn-view, .btn-edit, .btn-chat, .btn-delete, .btn-generating {
    font-size: 12px;
    padding: 8px 0;
  }
}
</style>
