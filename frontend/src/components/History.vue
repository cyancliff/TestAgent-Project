<template>
  <div class="page-layout">
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
            <!-- 第一行：总分和题目 -->
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
            <!-- 第二行：ATMR四个维度 -->
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

    // 如果有报告正在生成中的会话，启动轮询
    const hasGenerating = sessions.value.some(s => s.report_generating)
    if (hasGenerating && !pollTimer) {
      pollTimer = setInterval(pollForReports, 15000) // 每15秒检查一次
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

    // 所有报告都已生成，停止轮询
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
    alert('创建会话失败，请检查后端服务')
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
    // 计算导航栏高度（包括安全区域）
    const navHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 100
    const offset = navHeight + 32 // 额外间距

    const elementPosition = el.getBoundingClientRect().top + window.pageYOffset
    const offsetPosition = elementPosition - offset

    window.scrollTo({
      top: offsetPosition,
      behavior: 'smooth'
    })
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
  margin: 0 auto;
  padding: 32px 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.page-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px 0;
}

.page-subtitle {
  font-size: 17px;
  color: var(--text-secondary);
  margin: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 16px 32px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn span {
  font-size: 22px;
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
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.session-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 28px 32px;
  transition: all 0.25s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.session-card:hover {
  border-color: var(--primary);
  box-shadow: 0 8px 30px rgba(99, 102, 241, 0.15);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.session-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: linear-gradient(135deg, var(--bg-dark), var(--bg-hover));
  border-radius: 14px;
  padding: 14px 18px;
  min-width: 70px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.date-day {
  font-size: 32px;
  font-weight: 700;
  color: var(--primary-light);
  line-height: 1;
}

.date-month {
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-top: 6px;
  font-weight: 500;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 24px;
  font-size: 14px;
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
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.stats-row-top,
.stats-row-bottom {
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
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}


.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-weight: 500;
}

/* 维度等级点 */
.dim-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.dim-stat-top {
  display: flex;
  align-items: center;
  gap: 6px;
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
  height: 40px;
  background: var(--border);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.card-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.session-time {
  font-size: 15px;
  color: var(--text-muted);
  font-weight: 500;
}

/* ATMR 维度分值颜色 */
.dim-a { color: #6366f1; }
.dim-t { color: #06b6d4; }
.dim-m { color: #22c55e; }
.dim-r { color: #f59e0b; }

.btn-view, .btn-edit, .btn-chat, .btn-delete {
  padding: 12px 20px;
  background: transparent;
  border-radius: 10px;
  font-size: 15px;
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

/* 报告生成中状态 */
.report-generating-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(99, 102, 241, 0.12));
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 12px;
  animation: pulse-bg 2s ease-in-out infinite;
}

@keyframes pulse-bg {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.generating-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(99, 102, 241, 0.3);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

.generating-text {
  font-size: 14px;
  color: var(--primary-light);
  font-weight: 600;
}

.btn-generating {
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-hover);
  border: 1px dashed var(--border);
  cursor: default;
}

/* =========================================
   移动端适配样式 (在屏幕宽度 <= 768px 时生效)
   ========================================= */
@media (max-width: 768px) {
  /* 1. 隐藏左侧侧边栏，让正文占满全屏 */
  .page-sidebar {
    display: none !important;
  }

  /* 2. 减小页面和卡片的整体内边距 */
  .history-page {
    padding: 16px !important;
  }
  .session-card {
    padding: 20px 16px;
  }

  /* 3. 顶部标题区域：改为上下排列，新建按钮拉宽 */
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .page-header .btn-primary {
    width: 100%; /* 按钮占满全宽，方便手机单手点击 */
    justify-content: center;
  }

  .page-title {
    font-size: 28px;
  }
  .page-subtitle {
    font-size: 15px;
  }

  /* 4. 卡片头部：微调日期的样式大小 */
  .session-date {
    min-width: 60px;
    padding: 10px 14px;
  }
  .date-day {
    font-size: 24px;
  }

  /* 5. 核心：重排分数区域，防止横向溢出 */
  .stats-row {
    gap: 16px; /* 减小行间距 */
  }
  .stats-row-top,
  .stats-row-bottom {
    gap: 16px; /* 减小项目间距 */
  }
  .stat-divider {
    display: none; /* 手机端隐藏竖线，排版更清爽 */
  }
  .stats-row-top .stat-item {
    width: 50%; /* 第一行两个项目各占50% */
  }
  .stats-row-bottom .stat-item {
    width: 25%; /* 第二行四个项目各占25% */
  }
  .stat-value {
    font-size: 20px; /* 稍微缩小字体 */
  }

  /* 6. 底部操作区域：时间和按钮分行显示 */
  .card-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .card-actions {
    width: 100%;
    flex-wrap: wrap; /* 按钮多时自动换行 */
    gap: 10px;
  }

  /* 将按钮变成类似 App 的网格状，一行两个 */
  .btn-view, .btn-edit, .btn-chat, .btn-delete, .btn-generating {
    flex: 1 1 calc(50% - 5px); /* 平分宽度减去间距 */
    text-align: center;
    padding: 10px 0;
    font-size: 14px;
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .history-page {
    padding: 12px !important;
  }
  .session-card {
    padding: 16px 12px;
  }
  .page-title {
    font-size: 24px;
  }
  .page-subtitle {
    font-size: 14px;
  }
  .session-date {
    min-width: 50px;
    padding: 8px 12px;
  }
  .date-day {
    font-size: 20px;
  }
  .stats-row {
    gap: 12px;
  }
  .stats-row-top,
  .stats-row-bottom {
    gap: 12px;
  }
  .stat-value {
    font-size: 18px;
  }
  .card-footer {
    gap: 12px;
  }
  .card-actions {
    gap: 8px;
  }
  .btn-view, .btn-edit, .btn-chat, .btn-delete, .btn-generating {
    font-size: 13px;
    padding: 8px 0;
  }
}
</style>
