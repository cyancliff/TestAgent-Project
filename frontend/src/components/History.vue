<template>
  <div class="history-workspace">
    <aside :class="['history-sidebar', { 'history-sidebar--open': mobileSidebarOpen }]">
      <div class="history-sidebar-top">
        <div class="history-sidebar-home">
          <img :src="atmrLogo" class="history-sidebar-mark" alt="ATMR logo" />
          <span class="history-sidebar-copy">
            <strong>{{ currentHistoryTitle }}</strong>
            <small>{{ currentSidebarSubtitle }}</small>
          </span>
        </div>
        <button class="history-sidebar-close" type="button" aria-label="关闭测评档案" @click="closeMobileSidebar">×</button>
      </div>

      <button v-if="isAtmrHistory" class="history-new-button" type="button" @click="startNewSession">{{ historyStartLabel }}</button>
      <button v-else class="history-new-button" type="button" @click="openBigFiveUpload">上传大五视频</button>

      <div class="history-sidebar-section">
        <div class="history-sidebar-label">{{ currentSidebarLabel }}</div>
        <div class="history-session-list">
          <div v-if="loading" class="history-session-list-state">
            <div v-for="n in 3" :key="`history-loading-${n}`" class="history-session-skeleton">
              <span class="history-session-skeleton-line history-session-skeleton-line--title"></span>
              <span class="history-session-skeleton-line"></span>
            </div>
          </div>
          <div v-else-if="!hasCurrentSidebarItems" class="history-session-list-state history-session-list-state--empty">
            <strong>{{ currentSidebarEmptyTitle }}</strong>
            <span>{{ currentSidebarEmptyNote }}</span>
          </div>
          <template v-else-if="isAtmrHistory">
            <div v-if="inProgressSessions.length" class="history-session-group">
              <div class="history-session-group-label">进行中</div>
              <div
                v-for="session in inProgressSessions"
                :key="session.session_id"
                :class="[
                  'history-session-item',
                  {
                    active: activeHistorySessionId === session.session_id,
                    'history-session-item--menu-open': openSessionMenuId === atmrMenuKey(session.session_id),
                  },
                ]"
              >
                <button class="history-session-main" type="button" @click="scrollToSession(session.session_id)">
                  <span class="history-session-item-title">{{ displaySessionTitle(session) }}</span>
                  <span class="history-session-item-meta">{{ formatSidebarMeta(session) }}</span>
                </button>

                <div class="history-session-actions">
                  <button
                    class="history-session-menu-trigger"
                    type="button"
                    :aria-expanded="openSessionMenuId === atmrMenuKey(session.session_id)"
                    aria-label="管理测评记录"
                    @click.stop="toggleSessionMenu(atmrMenuKey(session.session_id))"
                  >
                    ⋯
                  </button>

                  <div v-if="openSessionMenuId === atmrMenuKey(session.session_id)" class="history-session-menu">
                    <button class="history-session-menu-item" type="button" @click.stop="continueSession(session.session_id)">
                      继续测评
                    </button>
                    <button class="history-session-menu-item" type="button" @click.stop="renameSession(session)">
                      重命名
                    </button>
                    <button
                      class="history-session-menu-item history-session-menu-item--danger"
                      type="button"
                      @click.stop="deleteSession(session.session_id)"
                    >
                      删除记录
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="completedSessions.length" class="history-session-group">
              <div class="history-session-group-label">已完成</div>
              <div
                v-for="session in completedSessions"
                :key="session.session_id"
                :class="[
                  'history-session-item',
                  {
                    active: activeHistorySessionId === session.session_id,
                    'history-session-item--menu-open': openSessionMenuId === atmrMenuKey(session.session_id),
                  },
                ]"
              >
                <button class="history-session-main" type="button" @click="scrollToSession(session.session_id)">
                  <span class="history-session-item-title">{{ displaySessionTitle(session) }}</span>
                  <span class="history-session-item-meta">{{ formatSidebarMeta(session) }}</span>
                </button>

                <div class="history-session-actions">
                  <button
                    class="history-session-menu-trigger"
                    type="button"
                    :aria-expanded="openSessionMenuId === atmrMenuKey(session.session_id)"
                    aria-label="管理测评记录"
                    @click.stop="toggleSessionMenu(atmrMenuKey(session.session_id))"
                  >
                    ⋯
                  </button>

                  <div v-if="openSessionMenuId === atmrMenuKey(session.session_id)" class="history-session-menu">
                    <button v-if="session.has_report" class="history-session-menu-item" type="button" @click.stop="viewReport(session.session_id)">
                      查看报告
                    </button>
                    <button class="history-session-menu-item" type="button" @click.stop="editAnswers(session.session_id)">
                      修改答案
                    </button>
                    <button class="history-session-menu-item" type="button" @click.stop="renameSession(session)">
                      重命名
                    </button>
                    <button
                      class="history-session-menu-item history-session-menu-item--danger"
                      type="button"
                      @click.stop="deleteSession(session.session_id)"
                    >
                      删除记录
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <template v-else>
            <div v-for="group in bigFiveSidebarGroups" :key="group.key" class="history-session-group">
              <div class="history-session-group-label">{{ group.label }}</div>
              <div
                v-for="report in group.reports"
                :key="`big-five-sidebar-${group.key}-${report.report_id}`"
                :class="[
                  'history-session-item',
                  {
                    active: activeBigFiveReportId === report.report_id,
                    'history-session-item--menu-open': openSessionMenuId === bigFiveMenuKey(report.report_id),
                  },
                ]"
              >
                <button class="history-session-main" type="button" @click="scrollToBigFiveReport(report.report_id)">
                  <span class="history-session-item-title">{{ displayBigFiveReportTitle(report) }}</span>
                  <span class="history-session-item-meta">{{ formatBigFiveSidebarMeta(report) }}</span>
                </button>

                <div class="history-session-actions">
                  <button
                    class="history-session-menu-trigger"
                    type="button"
                    :aria-expanded="openSessionMenuId === bigFiveMenuKey(report.report_id)"
                    aria-label="管理大五人格报告"
                    @click.stop="toggleSessionMenu(bigFiveMenuKey(report.report_id))"
                  >
                    ⋯
                  </button>

                  <div v-if="openSessionMenuId === bigFiveMenuKey(report.report_id)" class="history-session-menu">
                    <button v-if="canRetryBigFive(report)" class="history-session-menu-item" type="button" @click.stop="retryBigFiveReport(report.report_id)">
                      重新生成
                    </button>
                    <button
                      class="history-session-menu-item history-session-menu-item--danger"
                      type="button"
                      @click.stop="deleteBigFiveReport(report.report_id)"
                    >
                      删除报告
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </aside>

    <button
      v-if="mobileSidebarOpen"
      class="history-sidebar-backdrop"
      type="button"
      aria-label="关闭测评档案"
      @click="closeMobileSidebar"
    ></button>

    <section class="history-stage">
      <div class="history-page">
        <section class="history-overview-card">
          <header class="history-stage-header">
            <div class="history-stage-heading">
              <button
                class="history-mobile-trigger"
                type="button"
                aria-label="打开测评档案"
                @click="toggleMobileSidebar"
              >
                ☰
              </button>

              <div class="history-stage-titles">
                <h1>{{ currentHistoryTitle }}</h1>
              </div>
            </div>

            <div class="history-header-actions">
              <button v-if="isBigFiveHistory" class="btn-new" type="button" @click="openBigFiveUpload">
                <span class="btn-icon">+</span>
                <span>上传大五视频</span>
              </button>
              <button v-else class="btn-new" type="button" @click="startNewSession">
                <span class="btn-icon">+</span>
                <span>{{ historyStartLabel }}</span>
              </button>
            </div>
          </header>
          <input
            ref="bigFiveFileInput"
            class="history-file-input"
            type="file"
            accept="video/*"
            @change="handleBigFiveUpload"
          />

          <div class="history-type-tabs" role="tablist" aria-label="历史记录类型">
            <button
              v-for="type in historyTypes"
              :key="type.value"
              :class="['history-type-tab', { active: activeHistoryType === type.value }]"
              type="button"
              role="tab"
              :aria-selected="activeHistoryType === type.value"
              @click="setHistoryType(type.value)"
            >
              <span>{{ type.label }}</span>
              <strong>{{ type.count }}</strong>
            </button>
          </div>

          <section class="history-command-card">
            <div class="history-summary-grid">
              <article
                v-for="panel in currentDashboardPanels"
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
        </section>

        <div v-if="loading" class="history-state-card loading-state">
          <div class="spinner"></div>
          <p>正在加载测评记录...</p>
        </div>

        <div v-else-if="!hasCurrentHistoryItems" class="history-state-card empty-state">
          <div class="empty-circle">◎</div>
          <h3>{{ currentEmptyTitle }}</h3>
          <p>{{ currentEmptyNote }}</p>
          <button v-if="isAtmrHistory" class="btn-new btn-new-big" type="button" @click="startNewSession">
            <span class="btn-icon">+</span>
            <span>{{ historyStartLabel }}</span>
          </button>
          <button v-else class="btn-new btn-new-big" type="button" @click="openBigFiveUpload">
            <span class="btn-icon">+</span>
            <span>上传大五视频</span>
          </button>
        </div>

        <div v-else class="history-sections">
          <template v-if="isAtmrHistory">
            <section v-if="inProgressSessions.length" class="session-section">
              <div class="session-section-header">
                <h2>进行中</h2>
                <p>这些测评还没结束，可以随时继续作答。</p>
              </div>
              <div class="sessions-grid">
                <article
                  v-for="session in inProgressSessions"
                  :key="session.session_id"
                  :id="`session-${session.session_id}`"
                  :class="['session-card', { 'session-card--active': activeHistorySessionId === session.session_id }]"
                >
                <div class="card-header">
                  <div class="session-identity">
                    <div class="session-date-chip">
                      <span class="session-archive-label">档案编号</span>
                      <span class="session-archive-code">{{ formatArchiveCode(session.session_id) }}</span>
                    </div>
                  </div>

                  <div class="session-header-badges">
                    <span class="status-badge active">{{ formatStatusLabel(session.status) }}</span>
                  </div>
                </div>

                <div class="card-body">
                  <div class="session-score-block">
                    <span class="session-score-label">当前进度</span>
                    <strong class="session-score-value">{{ session.question_count }}</strong>
                    <div class="session-score-meta">
                      <span>已答题数</span>
                      <span>当前阶段：{{ getSessionStageLabel(session) }}</span>
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
                        <span v-if="isDominantDimension(session, dim.key)" class="dim-panel-badge">当前偏高</span>
                      </div>
                      <span class="dim-panel-label">{{ dim.name }}</span>
                      <strong class="dim-panel-score">{{ getDimScore(session, dim.key) }}</strong>
                    </div>
                  </div>
                </div>

                <div class="card-footer">
                  <div class="session-time-block">
                    <span class="session-time-label">开始时间</span>
                    <span class="session-time">{{ formatFullDate(session.started_at) }}</span>
                  </div>
                </div>
                </article>
              </div>
            </section>

            <section v-if="completedSessions.length" class="session-section">
              <div class="session-section-header">
                <h2>已完成</h2>
                <p>这里会保留已经提交完成的 ATMR 测评档案和报告。</p>
              </div>
              <div class="sessions-grid">
                <article
                  v-for="session in completedSessions"
                  :key="session.session_id"
                  :id="`session-${session.session_id}`"
                  :class="['session-card', { 'session-card--active': activeHistorySessionId === session.session_id }]"
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
                      {{ formatStatusLabel(session.status) }}
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
                        <span v-if="isDominantDimension(session, dim.key)" class="dim-panel-badge">主导项</span>
                      </div>
                      <span class="dim-panel-label">{{ dim.name }}</span>
                      <strong class="dim-panel-score">{{ getDimScore(session, dim.key) }}</strong>
                    </div>
                  </div>
                </div>

                <div v-if="session.report_generating" class="report-generating-bar">
                  <span class="generating-spinner"></span>
                  <span class="generating-text">报告仍在整理中，记录已经为你保留，稍后会自动刷新到这里。</span>
                </div>

                <div class="card-footer">
                  <div class="session-time-block">
                    <span class="session-time-label">测评时间</span>
                    <span class="session-time">{{ formatFullDate(session.started_at) }}</span>
                  </div>
                </div>
                </article>
              </div>
            </section>
          </template>

          <section v-else class="session-section">
            <div class="session-section-header">
              <p>这里保存从视频生成的独立大五人格报告，可单独查看和管理。</p>
            </div>

            <div v-if="bigFiveUploading" class="report-generating-bar">
              <span class="generating-spinner"></span>
              <span class="generating-text">视频已上传，正在创建大五人格报告。</span>
            </div>

            <div v-if="bigFiveReports.length" class="sessions-grid">
              <article
                v-for="report in bigFiveReports"
                :key="report.report_id"
                :id="`big-five-report-${report.report_id}`"
                :class="['session-card', 'big-five-card', { 'session-card--active': activeBigFiveReportId === report.report_id }]"
              >
                <div class="card-header">
                  <div class="session-identity">
                    <div class="session-date-chip">
                      <span class="session-archive-label">大五人格</span>
                      <span class="session-archive-code">#{{ String(report.report_id).padStart(3, '0') }}</span>
                    </div>
                  </div>

                  <div class="session-header-badges">
                    <span v-if="hasBigFiveInterpretation(report)" class="intel-badge">报告可查看</span>
                    <span :class="['status-badge', bigFiveStatusClass(report)]">{{ bigFiveStatusLabel(report) }}</span>
                  </div>
                </div>

                <div class="card-body big-five-card-body">
                  <div class="session-score-block">
                    <span class="session-score-label">报告状态</span>
                    <strong class="session-score-value big-five-status-value">{{ bigFiveMainValue(report) }}</strong>
                  </div>

                  <div class="session-dim-grid big-five-dim-grid">
                    <div v-for="dim in bigFiveDimensions" :key="dim.key" class="dim-panel">
                      <div class="dim-panel-top">
                        <span class="dim-panel-key">{{ dim.short }}</span>
                      </div>
                      <span class="dim-panel-label">{{ dim.name }}</span>
                      <strong class="dim-panel-score">{{ getBigFiveScore(report, dim.key) }}</strong>
                    </div>
                  </div>
                </div>

                <div v-if="isBigFiveProcessing(report)" class="report-generating-bar">
                  <span class="generating-spinner"></span>
                  <span class="generating-text">{{ bigFiveProcessingText(report) }}</span>
                </div>

                <div class="card-footer">
                  <div class="session-time-block">
                    <span class="session-time-label">生成时间</span>
                    <span class="session-time">{{ formatFullDate(report.created_at) }}</span>
                  </div>
                  <div class="card-actions">
                    <button class="btn-view" type="button" @click="viewBigFiveReport(report.report_id)">查看报告</button>
                    <button
                      v-if="canRetryBigFive(report)"
                      class="btn-edit"
                      type="button"
                      @click="retryBigFiveReport(report.report_id)"
                    >
                      重新生成
                    </button>
                  </div>
                </div>
              </article>
            </div>

            <div v-else-if="!bigFiveUploading" class="history-state-card empty-state big-five-empty-state">
              <div class="empty-circle">◎</div>
              <h3>还没有大五人格报告</h3>
              <p>上传一段视频后，系统会在后台生成独立的大五人格报告。</p>
              <button class="btn-new btn-new-big" type="button" @click="openBigFiveUpload">
                <span class="btn-icon">+</span>
                <span>上传大五视频</span>
              </button>
            </div>
          </section>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import atmrLogo from '../assets/atmr-logo.png'
import { showAlertDialog, showConfirmDialog, showPromptDialog } from '../composables/useAppDialog'
import { formatApiDotDateTime, parseApiDate } from '../utils/dateTime'

const route = useRoute()
const router = useRouter()

const sessions = ref([])
const bigFiveReports = ref([])
const loading = ref(true)
const bigFiveUploading = ref(false)
const activeHistorySessionId = ref(null)
const activeBigFiveReportId = ref(null)
const mobileSidebarOpen = ref(false)
const openSessionMenuId = ref(null)
const bigFiveFileInput = ref(null)
const activeHistoryType = ref(route.query.type === 'big-five' ? 'big-five' : 'atmr')
const historyStartLabel = '开始测评'
let pollTimer = null

const atmrDimensions = [
  { key: 'A', name: '欣赏型' },
  { key: 'T', name: '目标型' },
  { key: 'M', name: '包容型' },
  { key: 'R', name: '责任型' },
]

const bigFiveDimensions = [
  { key: 'openness', short: 'O', name: '开放性' },
  { key: 'conscientiousness', short: 'C', name: '尽责性' },
  { key: 'extraversion', short: 'E', name: '外向性' },
  { key: 'agreeableness', short: 'A', name: '宜人性' },
  { key: 'neuroticism', short: 'N', name: '神经质' },
]

const getDimScore = (session, key) => {
  const score = session.dim_scores?.[key]
  if (typeof score === 'object') return score.score || 0
  return score || 0
}

const getDominantDimKeys = (session) => {
  const entries = atmrDimensions.map((dim) => [dim.key, Number(getDimScore(session, dim.key)) || 0])
  const maxScore = Math.max(...entries.map(([, score]) => score), 0)
  if (maxScore <= 0) return []
  return entries.filter(([, score]) => score === maxScore).map(([key]) => key)
}

const isDominantDimension = (session, key) => getDominantDimKeys(session).includes(key)

const inProgressSessions = computed(() => sessions.value.filter((session) => session.status === 'active'))
const completedCount = computed(() => sessions.value.filter((session) => session.status === 'completed').length)
const completedSessions = computed(() => sessions.value.filter((session) => session.status === 'completed'))
const reportReadyCount = computed(() => sessions.value.filter((session) => session.has_report).length)
const generatingCount = computed(() => sessions.value.filter((session) => session.report_generating).length)
const bigFiveProcessingCount = computed(() => bigFiveReports.value.filter((report) => isBigFiveProcessing(report)).length)
const bigFiveReadyCount = computed(() => bigFiveReports.value.filter((report) => isBigFiveReady(report)).length)
const bigFiveIssueCount = computed(() => bigFiveReports.value.filter((report) => (
  report.status === 'failed'
  || (report.status === 'completed' && !report.is_real_result)
  || report.interpretation_status === 'failed'
)).length)
const isBigFiveIssue = (report) => (
  report.status === 'failed'
  || (report.status === 'completed' && !report.is_real_result)
  || report.interpretation_status === 'failed'
)
const bigFiveProcessingReports = computed(() => bigFiveReports.value.filter((report) => isBigFiveProcessing(report)))
const bigFiveCompletedReports = computed(() => bigFiveReports.value.filter((report) => !isBigFiveProcessing(report) && !isBigFiveIssue(report)))
const bigFiveIssueReports = computed(() => bigFiveReports.value.filter((report) => !isBigFiveProcessing(report) && isBigFiveIssue(report)))
const bigFiveSidebarGroups = computed(() => [
  { key: 'processing', label: '进行中', reports: bigFiveProcessingReports.value },
  { key: 'completed', label: '已完成', reports: bigFiveCompletedReports.value },
  { key: 'issue', label: '需要处理', reports: bigFiveIssueReports.value },
].filter((group) => group.reports.length))
const latestSession = computed(() => sessions.value[0] || null)
const isAtmrHistory = computed(() => activeHistoryType.value === 'atmr')
const isBigFiveHistory = computed(() => activeHistoryType.value === 'big-five')
const currentHistoryTitle = computed(() => (isAtmrHistory.value ? 'ATMR 测评' : '大五人格报告'))
const currentSidebarSubtitle = computed(() => (
  isAtmrHistory.value
    ? `${sessions.value.length} 条测评记录`
    : `${bigFiveReports.value.length} 份视频人格报告`
))
const currentSidebarLabel = computed(() => (isAtmrHistory.value ? 'ATMR 测评档案' : '大五人格报告'))
const hasCurrentSidebarItems = computed(() => (isAtmrHistory.value ? sessions.value.length > 0 : bigFiveReports.value.length > 0))
const hasCurrentHistoryItems = computed(() => (
  isAtmrHistory.value
    ? sessions.value.length > 0
    : bigFiveReports.value.length > 0 || bigFiveUploading.value
))
const currentSidebarEmptyTitle = computed(() => (isAtmrHistory.value ? '暂无测评记录' : '暂无大五人格报告'))
const currentSidebarEmptyNote = computed(() => (
  isAtmrHistory.value
    ? '完成测评后，左侧会显示 ATMR 历史列表'
    : '上传视频后，左侧会显示大五人格报告列表'
))
const currentEmptyTitle = computed(() => (isAtmrHistory.value ? '还没有 ATMR 测评记录' : '还没有大五人格报告'))
const currentEmptyNote = computed(() => (
  isAtmrHistory.value
    ? '完成一次测评后，这里会自动整理你的 ATMR 历史档案。'
    : '上传一段视频后，系统会在后台生成独立的大五人格报告。'
))
const historyTypes = computed(() => [
  { value: 'atmr', label: 'ATMR 测评', count: sessions.value.length },
  { value: 'big-five', label: '大五人格报告', count: bigFiveReports.value.length },
])
const archiveCodeMap = computed(() => {
  const total = sessions.value.length
  return new Map(
    sessions.value.map((session, index) => [session.session_id, String(total - index).padStart(3, '0')])
  )
})

const atmrDashboardPanels = computed(() => [
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
    label: 'ATMR 报告',
    value: String(reportReadyCount.value).padStart(2, '0'),
    note: generatingCount.value ? `另有 ${generatingCount.value} 份报告仍在整理中` : '已整理完成的分析报告',
  },
  {
    label: '生成中',
    value: String(generatingCount.value).padStart(2, '0'),
    note: generatingCount.value ? '正在整理中的 ATMR 报告' : '当前没有等待生成的报告',
    featured: true,
  },
])

const bigFiveDashboardPanels = computed(() => [
  {
    label: '大五人格报告',
    value: String(bigFiveReports.value.length).padStart(2, '0'),
    note: '独立的视频人格报告',
  },
  {
    label: '已完成',
    value: String(bigFiveReadyCount.value).padStart(2, '0'),
    note: '真实模型输出且已完成的报告',
  },
  {
    label: '生成中',
    value: String(bigFiveProcessingCount.value).padStart(2, '0'),
    note: bigFiveProcessingCount.value ? '后台正在分析视频' : '当前没有等待生成的报告',
  },
  {
    label: '失败/参考',
    value: String(bigFiveIssueCount.value).padStart(2, '0'),
    note: '需要重试或仅作参考的报告',
    featured: true,
  },
])

const currentDashboardPanels = computed(() => (
  isAtmrHistory.value ? atmrDashboardPanels.value : bigFiveDashboardPanels.value
))

const getDateValue = (isoStr) => parseApiDate(isoStr)
const formatFullDate = (isoStr) => formatApiDotDateTime(isoStr, '未命名测评')

const formatArchiveCode = (sessionId) => `#${archiveCodeMap.value.get(sessionId) || '000'}`
const formatStatusLabel = (status) => (status === 'completed' ? '已完成' : '进行中')
const formatSessionTitle = (isoStr) => formatFullDate(isoStr)
const displaySessionTitle = (session) => (session.title || '').trim() || formatSessionTitle(session.started_at)
const shouldShowSessionSubtitle = (session) => displaySessionTitle(session) !== formatFullDate(session.started_at)
const latestSessionArchiveHeadline = computed(() => (
  latestSession.value ? formatArchiveCode(latestSession.value.session_id) : '\u6682\u65e0\u8bb0\u5f55'
))

const atmrMenuKey = (sessionId) => `atmr-${sessionId}`
const bigFiveMenuKey = (reportId) => `big-five-${reportId}`

const getReportStatusLabel = (session) => {
  if (session.has_report) return '报告可查看'
  if (session.report_generating) return '报告整理中'
  return session.status === 'completed' ? '待整理报告' : '测评进行中'
}

const hasBigFiveInterpretation = (report) => (
  report.interpretation_status === 'completed' && !!report.interpretation_content
)
const getBigFiveInterpretationStatus = (report) => report.interpretation_status || 'pending'
const isBigFiveInterpretationProcessing = (report) => (
  isBigFiveReady(report) && getBigFiveInterpretationStatus(report) === 'running'
)
const isBigFiveProcessing = (report) => (
  ['pending', 'running'].includes(report.status) || isBigFiveInterpretationProcessing(report)
)
const isBigFiveReady = (report) => report.status === 'completed' && report.is_real_result && report.scores
const canRetryBigFive = (report) => report.status === 'failed' || (report.status === 'completed' && !report.is_real_result)
const bigFiveStatusLabel = (report) => {
  if (isBigFiveReady(report)) return '已完成'
  if (report.status === 'completed') return '仅作参考'
  if (report.status === 'failed') return '生成失败'
  if (report.status === 'running') return '生成中'
  return '等待处理'
}
const bigFiveStatusClass = (report) => {
  if (isBigFiveReady(report)) return 'completed'
  if (report.status === 'failed') return 'failed'
  return 'active'
}
const getBigFiveScore = (report, key) => {
  const value = Number(report.scores?.[key])
  if (!Number.isFinite(value)) return '--'
  return Math.round(Math.max(0, Math.min(1, value)) * 100)
}
const bigFiveMainValue = (report) => {
  if (hasBigFiveInterpretation(report)) return '已解读'
  if (isBigFiveReady(report)) return '可查看'
  if (report.status === 'failed') return '失败'
  if (report.status === 'completed') return '参考'
  return '生成中'
}
const bigFiveProcessingText = (report) => (
  isBigFiveInterpretationProcessing(report)
    ? '视频分析已完成，正在生成 AI 详细解读。'
    : '正在后台分析视频，完成后会自动更新。'
)
const displayBigFiveReportTitle = (report) => {
  const title = (report.title || '').trim()
  if (title) return title
  if (report.original_filename) return report.original_filename
  return `大五人格报告 #${report.report_id}`
}
const formatBigFiveSidebarMeta = (report) => {
  const parts = [bigFiveStatusLabel(report)]
  const dateLabel = formatFullDate(report.created_at)
  if (dateLabel && dateLabel !== '未命名测评') {
    parts.push(dateLabel)
  }
  return parts.join(' · ')
}

const getSessionStageLabel = (session) => session.stage_display_name || session.current_stage || '未开始'

const formatSidebarMeta = (session) => {
  const parts = [getReportStatusLabel(session), `${session.question_count} 题`]
  if (session.status === 'active') {
    parts.push(getSessionStageLabel(session))
  }
  return parts.join(' · ')
}

const formatCardSubtitle = (session) => {
  const parts = [formatStatusLabel(session.status), `${session.question_count} 题`]
  if (session.status === 'active') {
    parts.push(`当前阶段 ${getSessionStageLabel(session)}`)
  }
  return parts.join(' · ')
}

const latestSessionHeadline = computed(() => (
  latestSession.value ? displaySessionTitle(latestSession.value) : '暂无记录'
))

const latestSessionNote = computed(() => (
  latestSession.value ? formatCardSubtitle(latestSession.value) : '完成测评后会显示在这里'
))

const toggleMobileSidebar = () => {
  mobileSidebarOpen.value = !mobileSidebarOpen.value
}

const closeMobileSidebar = () => {
  mobileSidebarOpen.value = false
}

const closeSessionMenu = () => {
  openSessionMenuId.value = null
}

const toggleSessionMenu = (sessionId) => {
  openSessionMenuId.value = openSessionMenuId.value === sessionId ? null : sessionId
}

const setHistoryType = async (type) => {
  const nextType = type === 'big-five' ? 'big-five' : 'atmr'
  if (activeHistoryType.value === nextType) return

  activeHistoryType.value = nextType
  closeSessionMenu()
  closeMobileSidebar()

  await router.replace({
    path: '/history',
    query: {
      ...route.query,
      type: nextType,
    },
  })
}

const syncPollingState = () => {
  const hasGenerating = sessions.value.some((session) => session.report_generating) || bigFiveReports.value.some((report) => isBigFiveProcessing(report))
  if (hasGenerating && !pollTimer) {
    pollTimer = setInterval(pollForReports, 15000)
  } else if (!hasGenerating && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

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

const syncActiveBigFiveReport = () => {
  if (!bigFiveReports.value.length) {
    activeBigFiveReportId.value = null
    return
  }

  const hasActive = bigFiveReports.value.some((report) => report.report_id === activeBigFiveReportId.value)
  if (!hasActive) {
    activeBigFiveReportId.value = bigFiveReports.value[0].report_id
  }
}

const applySessions = (items) => {
  sessions.value = items || []
  if (
    String(openSessionMenuId.value || '').startsWith('atmr-')
    && !sessions.value.some((session) => atmrMenuKey(session.session_id) === openSessionMenuId.value)
  ) {
    closeSessionMenu()
  }
  syncActiveHistorySession()
  syncPollingState()
}

const applyBigFiveReports = (items) => {
  bigFiveReports.value = items || []
  if (
    String(openSessionMenuId.value || '').startsWith('big-five-')
    && !bigFiveReports.value.some((report) => bigFiveMenuKey(report.report_id) === openSessionMenuId.value)
  ) {
    closeSessionMenu()
  }
  syncActiveBigFiveReport()
  syncPollingState()
}

const fetchHistory = async () => {
  try {
    const [historyRes, bigFiveRes] = await Promise.all([
      api.get('/assessment/history'),
      api.get('/multimodal-personality/reports'),
    ])
    applySessions(historyRes.data.sessions)
    applyBigFiveReports(bigFiveRes.data.reports)
  } catch (err) {
    console.error('获取历史记录失败:', err)
  } finally {
    loading.value = false
  }
}

const pollForReports = async () => {
  try {
    const [historyRes, bigFiveRes] = await Promise.all([
      api.get('/assessment/history'),
      api.get('/multimodal-personality/reports'),
    ])
    applySessions(historyRes.data.sessions)
    applyBigFiveReports(bigFiveRes.data.reports)
  } catch (err) {
    console.error('轮询历史记录失败:', err)
  }
}

const getActiveSessionConflict = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail || typeof detail !== 'object' || detail.code !== 'active_session_exists') {
    return null
  }
  return detail
}

const startNewSession = async () => {
  closeSessionMenu()
  closeMobileSidebar()
  try {
    let res
    try {
      res = await api.post('/assessment/start-session', {})
    } catch (err) {
      const conflict = getActiveSessionConflict(err)
      if (!conflict) throw err

      const shouldOverwrite = await showConfirmDialog(conflict.message, {
        title: '发现进行中测评',
        confirmText: '是，覆盖',
        cancelText: '否，继续当前',
        destructive: true,
      })

      if (!shouldOverwrite) {
        router.push({ path: '/assessment', query: { sessionId: conflict.session_id } })
        return
      }

      res = await api.post('/assessment/start-session', {
        force_overwrite: true,
      })
    }

    if (res.data.session_id) {
      router.push({ path: '/assessment', query: { sessionId: res.data.session_id } })
    } else {
      router.push('/assessment')
    }
  } catch (err) {
    console.error('创建会话失败:', err)
    const detail = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || '未知错误'
    await showAlertDialog(`创建测评会话失败：${detail}`, {
      title: '创建失败',
      destructive: true,
    })
  }
}

const viewReport = (sessionId) => {
  closeSessionMenu()
  closeMobileSidebar()
  router.push(`/report/${sessionId}`)
}

const openBigFiveUpload = () => {
  closeMobileSidebar()
  bigFiveFileInput.value?.click()
}

const handleBigFiveUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  if (!isBigFiveHistory.value) {
    await setHistoryType('big-five')
  }
  bigFiveUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await api.post('/multimodal-personality/reports/upload-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    await fetchHistory()
  } catch (err) {
    console.error('上传大五视频失败:', err)
    await showAlertDialog(err.response?.data?.detail || '上传失败，请稍后再试', {
      title: '上传失败',
      destructive: true,
    })
  } finally {
    bigFiveUploading.value = false
  }
}

const viewBigFiveReport = (reportId) => {
  closeSessionMenu()
  closeMobileSidebar()
  router.push(`/big-five-report/${reportId}`)
}

const retryBigFiveReport = async (reportId) => {
  closeSessionMenu()
  closeMobileSidebar()
  try {
    await api.post(`/multimodal-personality/reports/${reportId}/run-background`)
    await fetchHistory()
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || '重新生成失败', {
      title: '操作失败',
      destructive: true,
    })
  }
}

const deleteBigFiveReport = async (reportId) => {
  closeSessionMenu()
  const shouldDelete = await showConfirmDialog('确定要删除这份大五人格报告吗？删除后无法恢复。', {
    title: '删除大五人格报告',
    confirmText: '删除',
    cancelText: '取消',
    destructive: true,
  })
  if (!shouldDelete) return

  try {
    await api.delete(`/multimodal-personality/reports/${reportId}`)
    applyBigFiveReports(bigFiveReports.value.filter((report) => report.report_id !== reportId))
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || '删除失败', {
      title: '删除失败',
      destructive: true,
    })
  }
}

const continueSession = (sessionId) => {
  closeSessionMenu()
  closeMobileSidebar()
  router.push({ path: '/assessment', query: { sessionId } })
}

const editAnswers = async (sessionId) => {
  closeSessionMenu()
  closeMobileSidebar()
  try {
    const res = await api.post(`/assessment/reopen-session/${sessionId}`)
    router.push({ path: '/assessment', query: { sessionId: res.data.session_id, mode: 'edit' } })
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || '打开编辑模式失败', {
      title: '打开失败',
      destructive: true,
    })
  }
}

const renameSession = async (session) => {
  closeSessionMenu()
  const initialTitle = displaySessionTitle(session).trim()
  const nextTitle = await showPromptDialog({
    title: '重命名记录',
    message: '输入新的测评记录名称',
    inputLabel: '记录名称',
    inputPlaceholder: '请输入新的测评记录名称',
    initialValue: initialTitle,
    inputMaxLength: 100,
    confirmText: '保存',
  })
  if (nextTitle === null) return

  const normalizedTitle = nextTitle.trim().slice(0, 100)
  if (!normalizedTitle || normalizedTitle === initialTitle) return

  try {
    const res = await api.put(`/assessment/session/${session.session_id}`, {
      title: normalizedTitle,
    })
    sessions.value = sessions.value.map((item) => (
      item.session_id === session.session_id
        ? { ...item, title: res.data.title || normalizedTitle }
        : item
    ))
  } catch (err) {
    console.error('重命名记录失败:', err)
    await showAlertDialog(err.response?.data?.detail || '重命名失败', {
      title: '重命名失败',
      destructive: true,
    })
  }
}

const deleteSession = async (sessionId) => {
  closeSessionMenu()
  const shouldDelete = await showConfirmDialog('确定要删除这次测评记录吗？删除后无法恢复。', {
    title: '删除记录',
    confirmText: '删除',
    cancelText: '取消',
    destructive: true,
  })
  if (!shouldDelete) return

  try {
    await api.delete(`/assessment/session/${sessionId}`)
    applySessions(sessions.value.filter((session) => session.session_id !== sessionId))
  } catch (err) {
    console.error('删除记录失败:', err)
    await showAlertDialog(err.response?.data?.detail || '删除失败', {
      title: '删除失败',
      destructive: true,
    })
  }
}

const scrollToSession = (sessionId) => {
  closeSessionMenu()
  closeMobileSidebar()
  activeHistorySessionId.value = sessionId
  const el = document.getElementById(`session-${sessionId}`)
  if (!el) return

  const navHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 100
  const offset = navHeight + 112
  const elementPosition = el.getBoundingClientRect().top + window.pageYOffset
  const offsetPosition = elementPosition - offset
  window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
}

const scrollToBigFiveReport = (reportId) => {
  closeSessionMenu()
  closeMobileSidebar()
  activeBigFiveReportId.value = reportId
  const el = document.getElementById(`big-five-report-${reportId}`)
  if (!el) return

  const navHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 100
  const offset = navHeight + 112
  const elementPosition = el.getBoundingClientRect().top + window.pageYOffset
  const offsetPosition = elementPosition - offset
  window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
}

const handleDocumentClick = (event) => {
  const target = event.target instanceof Element ? event.target : null
  if (!target?.closest('.history-session-actions')) {
    closeSessionMenu()
  }
}

watch(
  () => route.query.type,
  (type) => {
    activeHistoryType.value = type === 'big-five' ? 'big-five' : 'atmr'
    closeSessionMenu()
  }
)

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  fetchHistory()
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.history-workspace {
  --history-panel: #ffffff;
  --history-panel-muted: #f7f7f8;
  --history-border: #e5e7eb;
  --history-border-strong: #d4d4d8;
  --history-copy: #111827;
  --history-muted: #6b7280;
  display: grid;
  grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.history-sidebar {
  position: sticky;
  top: calc(var(--nav-height) + 20px);
  max-height: calc(100vh - var(--nav-height) - 40px);
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  gap: 14px;
  padding: 16px 14px;
  background: var(--history-panel-muted);
  border: 1px solid var(--history-border);
  border-radius: 24px;
  color: var(--history-copy);
}

.history-sidebar-top,
.history-sidebar-home,
.history-stage-header,
.history-stage-heading,
.card-header,
.card-footer,
.card-actions {
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
}

.history-sidebar-copy small {
  font-size: 12px;
  color: var(--history-muted);
}

.history-sidebar-close,
.history-mobile-trigger {
  display: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--history-border);
  border-radius: 14px;
  background: #ffffff;
  color: var(--history-copy);
  cursor: pointer;
  flex-shrink: 0;
}

.history-new-button {
  width: 100%;
  min-height: 48px;
  border: 0;
  border-radius: 16px;
  background: #111827;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.history-upload-button {
  width: 100%;
  min-height: 44px;
  border: 1px solid #111827;
  border-radius: 16px;
  background: #ffffff;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.history-new-button:hover,
.btn-new:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 30px rgba(17, 24, 39, 0.16);
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
  color: var(--history-muted);
  text-transform: uppercase;
}

.history-session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.history-session-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-session-group-label {
  padding: 4px 8px 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--history-muted);
}

.history-session-list-state {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-session-list-state--empty {
  padding: 18px 16px;
  border: 1px dashed var(--history-border-strong);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
}

.history-session-list-state--empty strong {
  font-size: 14px;
  font-weight: 700;
  color: var(--history-copy);
}

.history-session-list-state--empty span {
  font-size: 12px;
  line-height: 1.6;
  color: var(--history-muted);
}

.history-session-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 12px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
}

.history-session-skeleton-line {
  display: block;
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(226, 232, 240, 0.9), rgba(241, 245, 249, 1), rgba(226, 232, 240, 0.9));
  background-size: 200% 100%;
  animation: history-shimmer 1.2s ease-in-out infinite;
}

.history-session-skeleton-line--title {
  width: 68%;
  height: 12px;
}

.history-session-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 16px;
  background: transparent;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
  position: relative;
  z-index: 0;
}

.history-session-item:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--history-border);
  transform: translateY(-1px);
}

.history-session-item.active {
  background: #ffffff;
  border-color: var(--history-border-strong);
  box-shadow: 0 10px 30px rgba(17, 17, 17, 0.08);
}

.history-session-item--menu-open {
  z-index: 20;
  transform: none;
}

.history-session-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  border: 0;
  background: transparent;
  color: var(--history-copy);
  text-align: left;
  cursor: pointer;
}

.history-session-item-title {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
}

.history-session-item-meta,
.history-stage-titles p,
.history-summary-note,
.session-subtitle {
  font-size: 13px;
  line-height: 1.6;
  color: var(--history-muted);
}

.history-session-actions {
  position: relative;
  flex-shrink: 0;
  z-index: 2;
}

.history-session-menu-trigger {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--history-muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  opacity: 0.72;
  pointer-events: auto;
  transition: background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.history-session-item:hover .history-session-menu-trigger,
.history-session-item.active .history-session-menu-trigger,
.history-session-item--menu-open .history-session-menu-trigger {
  opacity: 1;
  pointer-events: auto;
}

.history-session-menu-trigger:hover,
.history-session-item--menu-open .history-session-menu-trigger {
  background: rgba(17, 24, 39, 0.06);
  color: var(--history-copy);
}

.history-session-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 148px;
  padding: 6px;
  border: 1px solid var(--history-border);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
  z-index: 30;
}

.history-session-menu-item {
  width: 100%;
  min-height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--history-copy);
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.history-session-menu-item:hover {
  background: #f3f4f6;
}

.history-session-menu-item--danger {
  color: #ef4444;
}

.history-session-menu-item--danger:hover {
  background: rgba(239, 68, 68, 0.08);
}

.history-stage {
  min-width: 0;
}

.history-stage-heading {
  gap: 14px;
  min-width: 0;
  flex: 1;
}

.history-stage-titles {
  min-width: 0;
}

.history-stage-titles h1 {
  margin: 0;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.04;
  font-weight: 600;
  letter-spacing: -0.03em;
  font-family: 'STSong', 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', serif;
  color: var(--history-copy);
}

.history-stage-titles p {
  margin: 6px 0 0;
  max-width: 720px;
}

.history-page {
  position: relative;
  width: 100%;
  color: var(--history-copy);
  font-family: 'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.history-sections {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.session-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.session-section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 0 4px;
}

.session-section-header h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.1;
  font-weight: 700;
}

.session-section-header p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--history-muted);
}

.history-overview-card,
.history-state-card,
.session-card {
  position: relative;
  overflow: hidden;
  background: var(--history-panel);
  border: 1px solid var(--history-border-strong);
  border-radius: 28px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
}

.history-overview-card,
.session-card {
  padding: 28px;
}

.history-overview-card {
  margin-bottom: 22px;
}

.history-stage-header {
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 22px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--history-border);
}

.history-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.history-file-input {
  display: none;
}

.history-type-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
  padding: 6px;
  border: 1px solid var(--history-border);
  border-radius: 18px;
  background: #f7f7f8;
}

.history-type-tab {
  min-width: 0;
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  color: var(--history-muted);
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.history-type-tab strong {
  min-width: 30px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.08);
  color: var(--history-copy);
  font-size: 12px;
  line-height: 1.4;
}

.history-type-tab:hover,
.history-type-tab.active {
  background: #ffffff;
  border-color: var(--history-border-strong);
  color: var(--history-copy);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.history-command-card {
  padding: 0;
  margin-bottom: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.history-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.history-summary-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 144px;
  padding: 22px 20px 20px;
  border: 1px solid var(--history-border);
  border-radius: 24px;
  background: #ffffff;
}

.history-summary-card--recent {
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  border-color: var(--history-border-strong);
}

.history-summary-label {
  font-size: 14px;
  font-weight: 800;
  color: var(--history-muted);
}

.history-summary-value {
  margin-top: auto;
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1.1;
  font-weight: 800;
  word-break: break-word;
}

.history-summary-value--recent {
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1.1;
}

.history-state-card {
  padding: 60px 24px;
  text-align: center;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.spinner,
.generating-spinner {
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(17, 17, 17, 0.12);
  border-top-color: #111111;
}

.empty-circle {
  width: 104px;
  height: 104px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid var(--history-border-strong);
  background: radial-gradient(circle, rgba(17, 17, 17, 0.08), rgba(17, 17, 17, 0.02) 68%);
  font-size: 40px;
}

.empty-state h3 {
  font-size: 28px;
}

.empty-state p {
  max-width: 420px;
  color: var(--history-muted);
}

.sessions-grid {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.session-card {
  transition: transform 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease;
}

.session-card:hover {
  transform: translateY(-2px);
  border-color: #d1d5db;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.1);
}

.session-card--active {
  border-color: #111827;
}

.card-header,
.card-footer {
  justify-content: space-between;
  gap: 18px;
}

.card-header {
  align-items: flex-start;
  margin-bottom: 20px;
}

.session-identity {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  min-width: 0;
  flex: 1;
}

.session-date-chip {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 128px;
  margin-left: 20px;
  padding-top: 8px;
}

.session-archive-label {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--history-muted);
}

.session-archive-code {
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
}

.session-title-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.session-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
  font-weight: 700;
}

.session-subtitle {
  margin: 0;
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
}

.intel-badge {
  background: rgba(17, 17, 17, 0.05);
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
}

.session-score-label,
.session-time-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--history-muted);
}

.session-score-value {
  margin-top: 10px;
  font-size: clamp(44px, 5vw, 64px);
  line-height: 1;
  font-weight: 800;
}

.session-score-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
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
}

.dim-panel-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.dim-panel--dominant {
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
}

.dim-panel-key,
.dim-panel-score {
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
}

.dim-panel-score {
  margin-top: auto;
  align-self: flex-end;
}

.dim-panel-label {
  font-size: 14px;
  line-height: 1.6;
  color: var(--history-muted);
}

.dim-panel-badge {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(17, 17, 17, 0.06);
  font-size: 12px;
  font-weight: 700;
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
}

.generating-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(17, 17, 17, 0.16);
  border-top-color: #111111;
  flex-shrink: 0;
}

.generating-text {
  font-size: 13px;
  font-weight: 600;
}

.card-footer {
  justify-content: space-between;
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
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-icon {
  font-size: 22px;
  line-height: 1;
}

.btn-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 22px;
  border: 0;
  border-radius: 16px;
  background: #111827;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.btn-new--secondary {
  border: 1px solid #111827;
  background: #ffffff;
  color: #111827;
}

.btn-new-big {
  margin-top: 8px;
}

.btn-view,
.btn-edit,
.btn-generating {
  min-height: 42px;
  padding: 0 15px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.btn-edit--danger {
  color: #dc2626;
  border-color: #dc2626;
}

.btn-view,
.btn-edit {
  border: 1px solid #111111;
  background: #ffffff;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.btn-view:hover,
.btn-edit:hover {
  transform: translateY(-1px);
  background: #f5f5f5;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.07);
}

.btn-generating {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #111111;
  background: #ffffff;
  color: #71717a;
}

.big-five-card-body {
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
}

.big-five-dim-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.big-five-status-value {
  font-size: clamp(28px, 4vw, 42px);
}

.big-five-empty-state {
  padding: 40px 24px;
}

.status-badge.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #991b1b;
}

.history-sidebar-backdrop {
  display: none;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes history-shimmer {
  0% {
    background-position: 200% 0;
  }

  100% {
    background-position: -200% 0;
  }
}

@media (max-width: 1200px) {
  .history-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card-body {
    grid-template-columns: 1fr;
  }

  .big-five-dim-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .session-score-block,
  .dim-panel {
    min-height: 0;
  }
}

@media (max-width: 960px) {
  .history-workspace {
    display: block;
  }

  .history-sidebar {
    position: fixed;
    top: calc(var(--nav-height) + 12px);
    left: 12px;
    bottom: 12px;
    z-index: 40;
    width: min(82vw, 320px);
    transform: translateX(-100%);
    transition: transform 0.24s ease;
    box-shadow: 20px 0 50px rgba(15, 23, 42, 0.14);
  }

  .history-sidebar--open {
    transform: translateX(0);
  }

  .history-sidebar-close,
  .history-mobile-trigger {
    display: inline-flex;
  }

  .history-sidebar-backdrop {
    display: block;
    position: fixed;
    inset: var(--nav-height) 0 0 0;
    z-index: 30;
    border: 0;
    background: rgba(15, 23, 42, 0.28);
  }

  .btn-new {
    width: 100%;
  }

  .history-header-actions {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .session-section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .history-stage-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    margin-bottom: 18px;
    padding-bottom: 18px;
  }

  .history-overview-card,
  .history-state-card,
  .session-card {
    padding: 20px 18px;
    border-radius: 24px;
  }

  .history-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .history-summary-card {
    min-height: 120px;
    padding: 16px 14px 14px;
    border-radius: 20px;
    gap: 8px;
  }

  .history-summary-value,
  .history-summary-value--recent {
    font-size: clamp(24px, 7vw, 34px);
  }

  .history-summary-note {
    font-size: 12px;
    line-height: 1.45;
  }

  .card-header {
    flex-direction: row;
    align-items: flex-start;
  }

  .card-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .session-identity,
  .session-time-block,
  .card-actions {
    width: 100%;
  }

  .session-identity {
    flex: 1;
    min-width: 0;
  }

  .session-header-badges {
    width: auto;
    margin-top: 38px;
    margin-left: auto;
    justify-content: flex-end;
    flex-shrink: 0;
  }

  .card-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    justify-content: stretch;
    align-items: stretch;
    gap: 10px;
  }

  .session-dim-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .big-five-dim-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .big-five-dim-grid .dim-panel {
    min-height: 112px;
    padding: 12px 10px 10px;
  }

  .dim-panel {
    min-height: 136px;
    padding: 14px 12px 12px;
    border-radius: 20px;
  }

  .dim-panel-key,
  .dim-panel-score {
    font-size: 30px;
  }

  .dim-panel-label {
    font-size: 12px;
    line-height: 1.45;
  }

  .dim-panel-badge {
    min-height: 24px;
    padding: 0 8px;
    font-size: 10px;
  }

  .card-actions > :only-child,
  .btn-generating {
    grid-column: 1 / -1;
    width: 100%;
    text-align: center;
  }

  .btn-view,
  .btn-edit {
    width: 100%;
    min-width: 0;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .history-overview-card {
    padding: 18px 16px;
  }

  .history-stage-header {
    padding-bottom: 16px;
  }

  .history-stage-titles h1 {
    font-size: 30px;
  }

  .session-identity {
    flex-direction: column;
  }

  .session-date-chip {
    margin-left: 0;
    min-width: 0;
  }

  .history-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .history-summary-card {
    min-height: 108px;
    padding: 14px 12px 12px;
  }

  .history-summary-label {
    font-size: 12px;
  }

  .history-summary-value,
  .history-summary-value--recent {
    font-size: clamp(22px, 8vw, 30px);
  }

  .history-summary-note {
    font-size: 11px;
  }

  .session-dim-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .big-five-dim-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 7px;
  }

  .dim-panel {
    min-height: 124px;
    padding: 12px 10px 10px;
  }

  .big-five-dim-grid .dim-panel {
    min-height: 104px;
    padding: 10px 8px 8px;
    border-radius: 16px;
    gap: 7px;
  }

  .dim-panel-key,
  .dim-panel-score {
    font-size: 26px;
  }

  .big-five-dim-grid .dim-panel-key,
  .big-five-dim-grid .dim-panel-score {
    font-size: 24px;
  }

  .dim-panel-label {
    font-size: 11px;
  }

  .dim-panel-badge {
    min-height: 22px;
    padding: 0 7px;
    font-size: 10px;
  }

  .card-actions {
    gap: 8px;
  }
}
</style>
