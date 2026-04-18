<template>
  <div :class="['page-layout', 'history-layout', { 'page-layout--no-sidebar': !sessions.length }]">
    <aside v-if="!loading && sessions.length" class="page-sidebar history-sidebar-panel">
      <div class="history-sidebar-top">
        <div class="history-sidebar-home">
          <img :src="atmrLogo" class="history-sidebar-mark" alt="ATMR logo" />
          <span class="history-sidebar-copy">
            <strong>ATMR 档案</strong>
            <small>{{ sessions.length }} 条历史记录</small>
          </span>
        </div>
      </div>

      <div class="history-sidebar-section">
        <div class="history-sidebar-label">历史记录</div>
        <div class="history-sidebar-list">
          <button
            v-for="session in sessions"
            :key="session.session_id"
            :class="['history-sidebar-item', { active: activeHistorySessionId === session.session_id }]"
            @click="scrollToSession(session.session_id)"
          >
            <span class="history-sidebar-item-top">
              <span class="history-sidebar-item-code">{{ formatArchiveCode(session.session_id) }}</span>
              <span :class="['history-sidebar-item-state', session.status]">
                {{ session.status === 'completed' ? '已完成' : '进行中' }}
              </span>
            </span>
            <span class="history-sidebar-item-title">{{ formatShortDate(session.started_at) }}</span>
            <span class="history-sidebar-item-meta">
              {{ session.has_report ? '报告已生成' : '报告生成中' }} · {{ formatFullDate(session.started_at) }}
            </span>
          </button>
        </div>
      </div>
    </aside>

    <div class="history-page">
      <section class="history-command-card">
        <div class="history-command-top">
          <div class="page-header-left">
            <h1 class="page-title">A T M R 档 案</h1>
            <p class="page-subtitle">按时间查看每次测评的分数、报告状态与后续咨询入口。</p>
          </div>

          <div class="history-command-actions">
            <button class="btn-new" @click="startNewSession">
              <span class="btn-icon">+</span>
              <span>开启新测评</span>
            </button>
          </div>
        </div>

        <div class="history-summary-grid">
          <article
            v-for="panel in dashboardPanels"
            :key="panel.label"
            :class="['history-summary-card', { 'history-summary-card--recent': panel.featured }]"
          >
            <span class="history-summary-label">{{ panel.label }}</span>
            <strong :class="['history-summary-value', { 'history-summary-value--recent': panel.featured }]">
              {{ panel.value }}
            </strong>
            <span :class="['history-summary-note', { 'history-summary-note--recent': panel.featured }]">
              {{ panel.note }}
            </span>
          </article>
        </div>
      </section>

      <div v-if="loading" class="loading-state history-state-card">
        <div class="spinner"></div>
        <p>正在加载历史记录...</p>
      </div>

      <div v-else-if="sessions.length === 0" class="empty-state history-state-card">
        <div class="empty-illustration">
          <div class="empty-circle">
            <span class="empty-icon">◎</span>
          </div>
        </div>
        <h3>还没有历史记录</h3>
        <p>完成一次测评后，这里会按时间整理你的测评档案。</p>
        <button class="btn-new btn-new-big" @click="startNewSession">
          <span class="btn-icon">+</span>
          <span>开启新测评</span>
        </button>
      </div>

      <div v-else class="sessions-grid">
        <article
          v-for="session in sessions"
          :key="session.session_id"
          :id="`session-${session.session_id}`"
          class="session-card"
        >
          <div class="card-header">
            <div class="session-identity">
              <div class="session-date-chip">
                <span class="session-archive-label">档案编号</span>
                <span class="session-archive-code">{{ formatArchiveCode(session.session_id) }}</span>
              </div>
            </div>

            <div class="session-header-badges">
              <span v-if="session.has_report" class="intel-badge">报告可查看</span>
              <span :class="['status-badge', session.status]">
                {{ session.status === 'completed' ? '已完成' : '进行中' }}
              </span>
            </div>
          </div>

          <div class="card-body">
            <div class="session-score-block">
              <span class="session-score-label">本次测评总分</span>
              <strong class="session-score-value">{{ session.total_score }}</strong>
              <div class="session-score-meta">
                <span>{{ session.question_count }} 题</span>
              </div>
            </div>

            <div class="session-dim-grid">
              <div
                v-for="dim in atmrDimensions"
                :key="dim.key"
                :class="['dim-panel', { 'dim-panel--dominant': isDominantDimension(session, dim.key) }]"
              >
                <div class="dim-panel-top">
                  <span class="dim-panel-key">{{ dim.key }}</span>
                  <span v-if="isDominantDimension(session, dim.key)" class="dim-panel-badge">主导型</span>
                </div>
                <span class="dim-panel-label">{{ dim.name }}</span>
                <strong class="dim-panel-score">{{ getDimScore(session, dim.key) }}</strong>
              </div>
            </div>
          </div>

          <div v-if="session.report_generating" class="report-generating-bar">
            <span class="generating-spinner"></span>
            <span class="generating-text">报告生成中，稍后会自动更新到这里。</span>
          </div>

          <div class="card-footer">
            <div class="session-time-block">
              <span class="session-time-label">记录时间</span>
              <span class="session-time">{{ formatFullDate(session.started_at) }}</span>
            </div>

            <div class="card-actions">
              <button v-if="session.has_report" class="btn-view" @click="viewReport(session.session_id)">查看报告</button>
              <span v-else-if="session.report_generating" class="btn-generating">生成中</span>
              <button v-if="session.status === 'completed'" class="btn-edit" @click="editAnswers(session.session_id)">修改答案</button>
              <button v-if="session.has_report" class="btn-chat" @click="goToChat(session.session_id)">进入咨询</button>
              <button class="btn-delete" @click="deleteSession(session.session_id)">删除记录</button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import atmrLogo from '../assets/atmr-logo.png'
import { showAlertDialog, showConfirmDialog } from '../composables/useAppDialog'

const router = useRouter()

const sessions = ref([])
const loading = ref(true)
const activeHistorySessionId = ref(null)
let pollTimer = null

const atmrDimensions = [
  { key: 'A', name: '欣赏型' },
  { key: 'T', name: '目标型' },
  { key: 'M', name: '包容型' },
  { key: 'R', name: '责任型' },
]

const getDimScore = (session, key) => {
  const ds = session.dim_scores?.[key]
  if (typeof ds === 'object') return ds.score || 0
  return ds || 0
}

const getDominantDimKeys = (session) => {
  const entries = atmrDimensions.map((dim) => [dim.key, Number(getDimScore(session, dim.key)) || 0])
  const maxScore = Math.max(...entries.map(([, score]) => score), 0)
  if (maxScore <= 0) return []
  return entries.filter(([, score]) => score === maxScore).map(([key]) => key)
}

const isDominantDimension = (session, key) => getDominantDimKeys(session).includes(key)

const archiveCodeMap = computed(() => {
  const total = sessions.value.length
  return new Map(
    sessions.value.map((session, index) => [session.session_id, String(total - index).padStart(3, '0')])
  )
})

const formatArchiveCode = (sessionId) => `#${archiveCodeMap.value.get(sessionId) || '000'}`

const getDateValue = (isoStr) => {
  if (!isoStr) return null
  const date = new Date(isoStr)
  return Number.isNaN(date.getTime()) ? null : date
}

const padDatePart = (value) => String(value).padStart(2, '0')

const formatShortDate = (isoStr) => {
  const date = getDateValue(isoStr)
  if (!date) return '--.--'
  return `${padDatePart(date.getMonth() + 1)}.${padDatePart(date.getDate())}`
}

const formatTime = (isoStr) => {
  const date = getDateValue(isoStr)
  if (!date) return ''
  return `${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}`
}

const formatFullDate = (isoStr) => {
  const date = getDateValue(isoStr)
  if (!date) return '暂无记录'
  return `${date.getFullYear()}.${padDatePart(date.getMonth() + 1)}.${padDatePart(date.getDate())} ${formatTime(isoStr)}`
}

const completedCount = computed(() => sessions.value.filter((session) => session.status === 'completed').length)
const reportReadyCount = computed(() => sessions.value.filter((session) => session.has_report).length)
const generatingCount = computed(() => sessions.value.filter((session) => session.report_generating).length)

const latestSession = computed(() => {
  if (!sessions.value.length) return null

  return sessions.value.reduce((current, session) => {
    if (!current) return session
    return new Date(session.started_at).getTime() > new Date(current.started_at).getTime() ? session : current
  }, null)
})

const latestSessionTime = computed(() => {
  return latestSession.value?.started_at ? formatFullDate(latestSession.value.started_at) : '暂无记录'
})

const latestSessionHeadline = computed(() => {
  if (!latestSession.value?.started_at) return '暂无记录'
  return formatShortDate(latestSession.value.started_at)
})

const dashboardPanels = computed(() => [
  {
    label: '测评总数',
    value: String(sessions.value.length).padStart(2, '0'),
    note: '累计建立的测评档案',
  },
  {
    label: '已完成',
    value: String(completedCount.value).padStart(2, '0'),
    note: '已完成并归档的记录',
  },
  {
    label: '报告数量',
    value: String(reportReadyCount.value).padStart(2, '0'),
    note: generatingCount.value ? `另有 ${generatingCount.value} 份报告生成中` : '已生成的分析报告',
  },
  {
    label: '最近测评',
    value: latestSessionHeadline.value,
    note: sessions.value.length ? latestSessionTime.value : '完成测评后会显示在这里',
    featured: true,
  },
])

const syncActiveHistorySession = () => {
  if (!sessions.value.length) {
    activeHistorySessionId.value = null
    return
  }

  const hasActive = sessions.value.some((session) => session.session_id === activeHistorySessionId.value)
  if (!hasActive) {
    activeHistorySessionId.value = sessions.value[0].session_id
  }
}

const fetchHistory = async () => {
  try {
    const res = await api.get('/assessment/history')
    sessions.value = res.data.sessions
    syncActiveHistorySession()

    const hasGenerating = sessions.value.some((session) => session.report_generating)
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
    syncActiveHistorySession()

    const hasGenerating = sessions.value.some((session) => session.report_generating)
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
    await showAlertDialog(`创建测评会话失败：${detail}`, {
      title: '创建失败',
      destructive: true,
    })
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
    await showAlertDialog(err.response?.data?.detail || '打开编辑模式失败', {
      title: '打开失败',
      destructive: true,
    })
  }
}

const deleteSession = async (sessionId) => {
  const shouldDelete = await showConfirmDialog('确定要删除这次测评记录吗？删除后无法恢复。', {
    title: '删除记录',
    confirmText: '删除',
    cancelText: '取消',
    destructive: true,
  })
  if (!shouldDelete) return
  try {
    await api.delete(`/assessment/session/${sessionId}`)
    sessions.value = sessions.value.filter((session) => session.session_id !== sessionId)
    syncActiveHistorySession()
  } catch (err) {
    console.error('删除记录失败:', err)
    await showAlertDialog(err.response?.data?.detail || '删除失败', {
      title: '删除失败',
      destructive: true,
    })
  }
}

const scrollToSession = (sessionId) => {
  activeHistorySessionId.value = sessionId
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
.history-layout {
  --history-bg: #ffffff;
  --history-panel: #ffffff;
  --history-panel-alt: linear-gradient(180deg, #ffffff, #f8fafc);
  --history-border: #e5e7eb;
  --history-border-strong: #dcdfe4;
  --history-soft: rgba(17, 17, 17, 0.03);
  --history-soft-strong: rgba(17, 17, 17, 0.06);
  --history-copy: #111827;
  --history-muted: #6b7280;
  --history-silver: #4b5563;
  gap: 24px;
  align-items: start;
}

.history-page {
  position: relative;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 8px 0 48px;
  color: var(--history-copy);
  font-family: 'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  isolation: isolate;
}

.history-page::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: 28px;
  background:
    radial-gradient(circle at 12% 0%, rgba(17, 17, 17, 0.04), transparent 30%),
    radial-gradient(circle at 100% 8%, rgba(17, 17, 17, 0.03), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 247, 248, 0.78));
  opacity: 1;
  pointer-events: none;
}

.history-page::after {
  content: '';
  position: absolute;
  inset: 18px 0 auto;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(17, 17, 17, 0.1), transparent);
  z-index: -1;
  pointer-events: none;
}

.page-sidebar.history-sidebar-panel {
  top: calc(var(--nav-height) + 20px);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 14px;
  background: #f7f7f8;
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  box-shadow: none;
  color: var(--history-copy);
  overflow: hidden;
}

.history-sidebar-top,
.history-sidebar-home,
.history-sidebar-item-top {
  display: flex;
  align-items: center;
}

.history-sidebar-top {
  justify-content: space-between;
  gap: 12px;
}

.history-sidebar-home {
  gap: 12px;
  padding: 10px 12px;
  border-radius: 16px;
  background: transparent;
  color: var(--history-copy);
}

.history-sidebar-mark {
  width: 46px;
  height: 46px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 6px 14px rgba(17, 24, 39, 0.12));
}

.history-sidebar-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.history-sidebar-copy strong {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.history-sidebar-copy small {
  font-size: 12px;
  color: #6b7280;
}

.history-sidebar-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-sidebar-label {
  padding: 0 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #6b7280;
  text-transform: uppercase;
}

.history-sidebar-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.history-sidebar-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 16px;
  color: var(--history-copy);
  box-shadow: none;
  text-align: left;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.history-sidebar-item:hover {
  transform: translateY(-1px);
  border-color: #e5e7eb;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.history-sidebar-item.active {
  background: #ffffff;
  border-color: #d4d4d8;
  box-shadow: 0 10px 30px rgba(17, 17, 17, 0.08);
}

.history-sidebar-item-top {
  justify-content: space-between;
  gap: 12px;
}

.history-sidebar-item-code {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #111827;
}

.history-sidebar-item-state {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(17, 17, 17, 0.06);
  color: var(--history-copy);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: none;
}

.history-sidebar-item-state.active {
  color: #a16207;
  background: rgba(245, 158, 11, 0.12);
}

.history-sidebar-item-title {
  color: var(--history-copy);
  font-size: 14px;
  font-weight: 700;
}

.history-sidebar-item-meta {
  color: #6b7280;
  font-size: 12px;
  text-transform: none;
  letter-spacing: 0;
  line-height: 1.6;
}

.history-command-card,
.history-state-card,
.session-card {
  position: relative;
  overflow: hidden;
  background: var(--history-panel);
  border: 1px solid var(--history-border-strong);
  border-radius: 28px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
}

.history-command-card::before,
.session-card::before,
.history-state-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0) 34%);
  pointer-events: none;
}

.history-command-card {
  padding: 30px 32px 26px;
  margin-bottom: 22px;
}

.history-command-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.page-header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.page-title {
  margin: 0;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.04;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: #111827;
  font-family: 'STSong', 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', serif;
}

.page-subtitle {
  margin: 0;
  max-width: 640px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--history-muted);
}

.history-command-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  flex-shrink: 0;
  margin-right: 32px;
}

.btn-icon {
  font-size: 22px;
  line-height: 1;
  font-weight: 500;
}

.btn-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-width: 226px;
  min-height: 70px;
  padding: 0 38px;
  border: 0;
  border-radius: 999px;
  background: #111827;
  color: #ffffff;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
  box-shadow: 0 18px 36px rgba(17, 24, 39, 0.18);
}

.btn-new:hover {
  transform: translateY(-1px);
  background: #1f2937;
  box-shadow: 0 22px 42px rgba(17, 24, 39, 0.22);
}

.history-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 22px;
  align-items: stretch;
}

.history-summary-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 144px;
  padding: 22px 20px 20px;
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.history-summary-card--recent {
  position: relative;
  background:
    radial-gradient(circle at top right, rgba(17, 24, 39, 0.05), transparent 36%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  border-color: var(--history-border-strong);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.history-summary-card--recent::after {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 46px;
  height: 1px;
  background: linear-gradient(90deg, #eef0f3, rgba(238, 240, 243, 0));
  pointer-events: none;
}

.history-summary-label {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: none;
  color: var(--history-muted);
}

.history-summary-value {
  margin-top: auto;
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1.1;
  font-weight: 800;
  color: #111827;
  font-variant-numeric: tabular-nums;
  word-break: break-word;
}

.history-summary-value--recent {
  margin-top: 2px;
  font-size: clamp(26px, 2.4vw, 34px);
  line-height: 1.2;
  font-weight: 700;
}

.history-summary-note {
  font-size: 14px;
  line-height: 1.6;
  color: var(--history-muted);
}

.history-summary-note--recent {
  margin-top: auto;
  padding-top: 12px;
}

.history-state-card {
  padding: 60px 24px;
  text-align: center;
  color: var(--history-muted);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(17, 17, 17, 0.12);
  border-top-color: #111111;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-illustration {
  margin-bottom: 4px;
}

.empty-circle {
  width: 104px;
  height: 104px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(17, 17, 17, 0.08), rgba(17, 17, 17, 0.02) 68%);
  border: 1px solid var(--history-border-strong);
  box-shadow: inset 0 0 24px rgba(17, 17, 17, 0.04);
}

.empty-icon {
  font-size: 40px;
  color: #111111;
}

.empty-state h3 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  color: #111111;
}

.empty-state p {
  margin: 0;
  max-width: 420px;
  line-height: 1.7;
}

.btn-new-big {
  margin-top: 8px;
  min-width: 240px;
}

.sessions-grid {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.session-card {
  padding: 26px 26px 22px;
  transition: transform 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease;
}

.session-card:hover {
  transform: translateY(-2px);
  border-color: #d1d5db;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.1);
}

.card-header,
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.card-header {
  margin-bottom: 20px;
}

.session-identity {
  display: flex;
  align-items: center;
  gap: 14px;
}

.session-date-chip {
  min-width: 96px;
  min-height: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6px;
}

.session-archive-label {
  font-size: 24px;
  line-height: 1;
  font-weight: 800;
  color: #111111;
  letter-spacing: 0.02em;
}

.session-archive-code {
  font-size: 21px;
  line-height: 1.1;
  font-weight: 800;
  color: #111111;
  font-variant-numeric: tabular-nums;
}

.session-time-label,
.session-score-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: none;
  color: var(--history-muted);
}

.session-time {
  color: var(--history-copy);
  font-variant-numeric: tabular-nums;
}

.session-header-badges {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.intel-badge,
.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: none;
}

.intel-badge {
  background: rgba(17, 17, 17, 0.05);
  color: #111111;
  border: 1px solid rgba(17, 17, 17, 0.12);
}

.status-badge.completed {
  background: rgba(34, 197, 94, 0.12);
  color: #166534;
}

.status-badge.active {
  background: rgba(245, 158, 11, 0.12);
  color: #a16207;
}

.card-body {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.session-score-block,
.dim-panel {
  border: 1px solid #111111;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(243, 243, 240, 0.96));
}

.session-score-block {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 180px;
  padding: 20px;
  border-radius: 26px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.session-score-value {
  margin-top: 10px;
  font-size: clamp(44px, 5vw, 64px);
  line-height: 1;
  font-weight: 800;
  color: #111111;
  font-variant-numeric: tabular-nums;
}

.session-score-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--history-muted);
}

.session-dim-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.dim-panel {
  min-height: 180px;
  padding: 18px 16px 16px;
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  position: relative;
}

.dim-panel-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.dim-panel--dominant {
  border-color: #111111;
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
}

.dim-panel-key {
  display: inline-block;
  color: #111111;
  font-size: 38px;
  line-height: 0.9;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.dim-panel-score {
  margin-top: auto;
  align-self: flex-end;
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
  color: #111111;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.dim-panel-label {
  font-size: 14px;
  line-height: 1.6;
  color: var(--history-muted);
}

.dim-panel-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(17, 17, 17, 0.06);
  color: #111111;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.report-generating-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  border: 1px solid #111111;
  border-radius: 20px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.98), rgba(242, 242, 240, 0.96), rgba(255, 255, 255, 0.98));
  animation: signalPulse 3.2s ease-in-out infinite;
}

@keyframes signalPulse {
  0%,
  100% {
    opacity: 0.9;
  }

  50% {
    opacity: 1;
  }
}

.generating-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(17, 17, 17, 0.16);
  border-top-color: #111111;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
  flex-shrink: 0;
}

.generating-text {
  font-size: 13px;
  font-weight: 600;
  color: #111111;
}

.card-footer {
  padding-top: 16px;
  border-top: 1px solid var(--history-border);
}

.session-time-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-time {
  font-size: 13px;
  line-height: 1.6;
}

.card-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.btn-view,
.btn-edit,
.btn-chat,
.btn-delete,
.btn-generating {
  min-height: 42px;
  padding: 0 15px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.btn-view,
.btn-chat,
.btn-edit,
.btn-delete {
  border: 1px solid #111111;
  background: #ffffff;
}

.btn-view {
  color: #111111;
}

.btn-view:hover {
  transform: translateY(-1px);
  background: #f5f5f5;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.07);
}

.btn-chat {
  color: #111111;
}

.btn-chat:hover {
  transform: translateY(-1px);
  background: #f5f5f5;
}

.btn-edit {
  color: #111111;
}

.btn-edit:hover {
  transform: translateY(-1px);
  background: #f5f5f5;
}

.btn-delete {
  color: #f87171;
}

.btn-delete:hover {
  transform: translateY(-1px);
  background: #fff1f2;
}

.btn-generating {
  border: 1px dashed #111111;
  background: #ffffff;
  color: #71717a;
  cursor: default;
}

@media (max-width: 1200px) {
  .history-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card-body {
    grid-template-columns: 1fr;
  }

  .session-score-block,
  .dim-panel {
    min-height: 0;
  }
}

@media (max-width: 960px) {
  .history-page {
    padding: 8px 0 32px;
  }

  .history-command-top {
    flex-direction: column;
  }

  .history-command-actions {
    width: 100%;
    margin-right: 0;
    justify-content: flex-start;
  }

  .btn-new {
    width: 100%;
    max-width: none;
  }
}

@media (max-width: 768px) {
  .page-sidebar.history-sidebar-panel {
    display: none !important;
  }

  .history-page {
    padding: 0 0 20px;
  }

  .history-command-card,
  .history-state-card,
  .session-card {
    border-radius: 24px;
  }

  .history-command-card {
    padding: 22px 18px 18px;
  }

  .page-title {
    font-size: 34px;
  }

  .history-summary-grid {
    grid-template-columns: 1fr;
  }

  .session-card {
    padding: 18px 16px 16px;
  }

  .card-header,
  .card-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .session-identity {
    width: 100%;
  }

  .session-header-badges,
  .card-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .session-dim-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .btn-view,
  .btn-edit,
  .btn-chat,
  .btn-delete,
  .btn-generating {
    flex: 1 1 calc(50% - 5px);
    justify-content: center;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .page-title {
    font-size: 30px;
  }

  .page-subtitle {
    font-size: 14px;
  }

  .history-command-card,
  .history-state-card,
  .session-card {
    border-radius: 20px;
  }

  .history-summary-card {
    min-height: 118px;
    padding: 16px;
  }

  .session-identity {
    gap: 10px;
  }

  .session-date-chip {
    min-width: 84px;
    padding: 0;
    gap: 6px;
  }

  .session-archive-label {
    font-size: 20px;
  }

  .session-archive-code {
    font-size: 18px;
  }

  .session-dim-grid {
    grid-template-columns: 1fr;
  }

  .session-score-value {
    font-size: 48px;
  }

  .dim-panel-score {
    font-size: 30px;
  }

  .dim-panel-key {
    font-size: 32px;
  }

  .dim-panel-badge {
    min-height: 24px;
    padding: 0 8px;
    font-size: 11px;
  }

  .btn-view,
  .btn-edit,
  .btn-chat,
  .btn-delete,
  .btn-generating {
    flex-basis: 100%;
  }
}
</style>
