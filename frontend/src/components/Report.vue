<template>
  <div class="report-container">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-hint">
      <div class="loader-spinner"></div>
      <p>加载报告中...</p>
    </div>

    <template v-else>
      <!-- 报告头部 -->
      <div class="report-card header-card">
        <span class="report-kicker">ATMR 深度心理测评报告</span>
        <h1 class="report-title">{{ reportTitle }}</h1>
        <p class="report-meta">
          会话 #{{ sessionId }} | {{ formatTime(reportData.started_at) }}
          <span v-if="reportData.finished_at"> — {{ formatTime(reportData.finished_at) }}</span>
        </p>
      </div>

      <!-- ATMR 雷达图 + 维度分数 -->
      <div v-if="hasDimensionData" class="report-card radar-section">
        <h2 class="section-title">ATMR 特质画像</h2>
        <div class="radar-layout">
          <div class="radar-chart-wrapper">
            <Radar :data="radarData" :options="radarOptions" />
          </div>
          <div class="dimension-scores">
            <div v-for="m in modules" :key="m.key" class="dim-score-item">
              <div class="dim-header">
                <span class="dim-badge" :style="{ background: m.color }">{{ m.key }}</span>
                <span class="dim-name">{{ m.name }}</span>
                <span class="dim-level-badge" :style="{ background: getDimLevelColor(m.key) }">{{ getDimLevelLabel(m.key) }}</span>
                <span class="dim-pct">{{ getDimPercentage(m.key) }}%</span>
              </div>
              <div class="dim-bar-wrapper">
                <div class="dim-bar" :style="{ width: getDimPercentage(m.key) + '%', background: m.color }"></div>
              </div>
              <div class="dim-detail">{{ getDimTotal(m.key) }} / {{ getDimMax(m.key) }} 分 · {{ getEvidenceCount(m.key) }} 题 · {{ getDimAnomalyCount(m.key) }} 异常 · 置信度 {{ getDimConfidencePercent(m.key) }}%<template v-if="getDimBonus(m.key) > 0"> · 加权+{{ getDimBonus(m.key) }}</template></div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="trustSummary.assessment_confidence !== undefined" class="report-card trust-card">
        <h2 class="section-title">测评可信度</h2>
        <div class="trust-overview">
          <div class="trust-score">
            <strong>{{ percent(trustSummary.assessment_confidence) }}%</strong>
            <span>{{ trustSummary.label || '中等' }}</span>
          </div>
          <div class="trust-copy">
            <p v-for="note in trustSummary.notes || []" :key="note">{{ note }}</p>
            <p>ATMR-CAT 覆盖度 {{ percent(adaptiveMetrics.coverage_ratio || 0) }}%，异常作答 {{ trustSummary.anomaly_count || 0 }} 条。</p>
          </div>
        </div>
      </div>

      <div v-if="agentWorkflow" class="report-card agent-workflow-card">
        <div class="agent-workflow-header">
          <div>
            <h2 class="section-title">智能分析过程</h2>
            <p class="section-desc">证据约束型多 Agent 工作流运行摘要</p>
          </div>
          <span :class="['workflow-policy-badge', `policy-${agentState.report_policy || 'pending'}`]">
            {{ workflowPolicyLabel }}
          </span>
        </div>

        <div class="workflow-state-grid">
          <div class="workflow-state-item">
            <span>测评可信度</span>
            <strong>{{ percent(agentState.assessment_confidence || 0) }}%</strong>
          </div>
          <div class="workflow-state-item">
            <span>证据状态</span>
            <strong>{{ evidenceStatusLabel }}</strong>
          </div>
          <div class="workflow-state-item">
            <span>模块分析</span>
            <strong>{{ agentState.module_debate_count || 0 }}/4</strong>
          </div>
          <div class="workflow-state-item">
            <span>安全审查</span>
            <strong>{{ criticStatusLabel }}</strong>
          </div>
        </div>

        <div class="workflow-steps">
          <div v-for="step in agentTraceSteps" :key="step.key" :class="['workflow-step', `step-${step.status}`]">
            <span class="workflow-step-dot"></span>
            <div>
              <strong>{{ step.label }}</strong>
              <p>{{ step.detail }}</p>
            </div>
          </div>
        </div>

        <div v-if="reportCritic.notes?.length" class="critic-notes">
          <strong>审查提示</strong>
          <p v-for="note in reportCritic.notes" :key="note">{{ note }}</p>
        </div>
      </div>

      <!-- 综合心理画像报告（Markdown 渲染） -->
      <div v-if="hasReport" class="report-card">
        <h2 class="section-title">综合心理画像</h2>
        <div class="report-body markdown-body" v-html="formattedReport"></div>
      </div>
      <div v-else-if="reportPending" class="report-card report-card--pending">
        <div class="no-report-hint">报告仍在整理中，已为你保留记录，页面会自动刷新。</div>
        <div class="report-pending-actions">
          <button class="back-btn" @click="fetchReport({ silent: true })">立即刷新</button>
          <button class="back-btn" @click="$router.push('/history')">返回历史记录</button>
        </div>
      </div>
      <div v-else-if="loadError" class="report-card report-card--pending">
        <div class="no-report-hint">{{ loadError }}</div>
        <div class="report-pending-actions">
          <button class="back-btn" @click="fetchReport()">重新加载</button>
        </div>
      </div>
      <div v-else class="report-card report-card--pending">
        <div class="no-report-hint">报告内容还没有准备好，请稍后再回来查看。</div>
      </div>

      <!-- 分维度报告 -->
      <div v-if="hasDimensionData" class="report-card">
        <h2 class="section-title">分维度报告</h2>
        <p class="section-desc">展示各维度的辩论结果、数据分析与结论</p>

        <div class="evidence-modules">
          <div v-for="m in modules" :key="'dim-' + m.key" class="evidence-module">
            <div
              class="ev-module-header"
              :class="{ expanded: expandedDimension[m.key] }"
              @click="toggleDimension(m.key)"
            >
              <div class="ev-module-left">
                <span class="dim-badge" :style="{ background: m.color }">{{ m.key }}</span>
                <span class="ev-module-name">{{ m.name }}</span>
                <span class="dim-level-badge" :style="{ background: getDimLevelColor(m.key) }">{{ getDimLevelLabel(m.key) }}</span>
                <span class="ev-module-stat">{{ getEvidenceCount(m.key) }} 题 · 总分 {{ getDimTotal(m.key) }} · 均分 {{ getDimAvg(m.key) }} · 置信度 {{ getDimConfidencePercent(m.key) }}%</span>
              </div>
              <span class="toggle-arrow" :class="{ open: expandedDimension[m.key] }"></span>
            </div>

            <transition name="slide">
              <div v-if="expandedDimension[m.key]" class="dimension-report-body">
                <div v-if="hasConfidenceWeightedReference(m.key)" class="confidence-reference">
                  <h3 class="dim-subsection-title">可信度加权参考</h3>
                  <p>
                    参考分：{{ getConfidenceWeightedScore(m.key) }} / {{ getDimMax(m.key) }} 分，
                    与主得分差异 {{ formatDelta(getConfidenceWeightedDelta(m.key)) }}。
                    {{ getConfidenceWeightedNote(m.key) }}
                  </p>
                </div>

                <!-- 模块辩论结果 -->
                <div v-if="reportData.module_debates?.[m.key]" class="debate-section">
                  <h3 class="dim-subsection-title">专家辩论结果</h3>
                  <div class="markdown-body" v-html="renderMarkdown(reportData.module_debates[m.key])"></div>
                </div>
                <div v-else class="debate-section loading-debate">
                  <h3 class="dim-subsection-title">专家辩论结果</h3>
                  <p class="no-debate-hint">该模块暂无辩论数据</p>
                </div>

                <!-- 答题明细 -->
                <div class="records-section">
                  <h3 class="dim-subsection-title">答题明细</h3>
                  <div class="ev-records-wrap">
                    <div
                      v-for="(rec, idx) in getEvidenceRecords(m.key)"
                      :key="idx"
                      :class="['ev-record', { 'ev-anomaly': rec.is_anomaly }]"
                    >
                      <div class="ev-top">
                        <span class="ev-no">{{ rec.exam_no }}</span>
                        <span v-if="rec.trait_label" class="ev-trait">{{ rec.trait_label }}</span>
                        <span :class="['ev-score', scoreClass(rec.score)]">{{ rec.score }}分</span>
                        <span class="ev-time">{{ rec.time_spent?.toFixed(1) }}s</span>
                        <span v-if="rec.is_anomaly" class="badge badge-red">异常</span>
                        <span v-if="rec.is_reverse" class="badge badge-cyan">反向</span>
                        <span class="badge badge-gray">可信 {{ Math.round((rec.answer_confidence ?? 1) * 100) }}%</span>
                      </div>
                      <div class="ev-q">{{ rec.question }}</div>
                      <div class="ev-a"><b>选择：</b>{{ rec.selected_option }}</div>
                      <div v-if="rec.risk_reasons?.length" class="ev-followup"><b>风险原因：</b>{{ rec.risk_reasons.join('、') }}</div>
                      <div v-if="behaviorSummary(rec)" class="ev-followup"><b>行为摘要：</b>{{ behaviorSummary(rec) }}</div>
                      <div class="ev-chain">
                        <span class="chain-icon"></span>
                        用户在「{{ rec.trait_label || '该特质' }}」维度选择了「{{ rec.selected_option }}」，得分 {{ rec.score }}/5<template v-if="rec.is_reverse">（反向计分）</template><template v-if="rec.is_anomaly">，后台行为风险模型标记为异常</template>
                        → {{ rec.score >= 4 ? '强烈支持' : rec.score >= 3 ? '适度支持' : rec.score >= 2 ? '弱支持' : '不支持' }}该维度特质
                      </div>
                    </div>
                    <div v-if="getEvidenceRecords(m.key).length === 0" class="ev-empty">该模块暂无答题记录</div>
                  </div>
                </div>
              </div>
            </transition>
          </div>
        </div>
      </div>

      <!-- 全部答题明细 -->
      <div v-if="reportData.answers?.length" class="report-card">
        <div class="collapsible-header" @click="showAllAnswers = !showAllAnswers">
          <h2 class="section-title" style="margin:0">全部答题明细 ({{ reportData.answers.length }}题)</h2>
          <span class="toggle-arrow" :class="{ open: showAllAnswers }"></span>
        </div>
        <transition name="slide">
          <div v-if="showAllAnswers" class="answer-list">
            <div v-for="(a, i) in reportData.answers" :key="i" :class="['answer-item', { 'ev-anomaly': a.is_anomaly }]">
              <div class="ev-top">
                <span class="ev-no">{{ a.exam_no }}</span>
                <span v-if="a.module" class="dim-badge dim-badge-sm" :style="{ background: getModuleColor(a.module) }">{{ a.module }}</span>
                <span :class="['ev-score', scoreClass(a.score)]">{{ a.score }}分</span>
                <span class="ev-time">{{ a.time_spent }}s</span>
                <span v-if="a.is_anomaly" class="badge badge-red">异常</span>
                <span class="badge badge-gray">可信 {{ Math.round((a.answer_confidence ?? 1) * 100) }}%</span>
              </div>
              <div class="ev-q">{{ a.question }}</div>
              <div class="ev-a">选择：{{ a.selected_option }}</div>
            </div>
          </div>
        </transition>
      </div>

      <div class="report-bottom-actions">
        <button class="delete-btn" @click="deleteCurrentSession">删除本次记录</button>
        <button class="back-btn" @click="$router.push('/history')">返回历史记录</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { showAlertDialog, showConfirmDialog } from '../composables/useAppDialog'
import { formatApiDateTime } from '../utils/dateTime'
import { Radar } from 'vue-chartjs'
import { renderReportMarkdown } from '../utils/markdown'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const props = defineProps({ sessionId: String })
const router = useRouter()
const reportData = ref({})
const loading = ref(true)
const loadError = ref('')
const showAllAnswers = ref(false)
const expandedDimension = reactive({ A: false, T: false, M: false, R: false })
let pendingRefreshTimer = null

const modules = [
  { key: 'A', name: '欣赏型', color: '#2563eb' },
  { key: 'T', name: '目标型', color: '#7c3aed' },
  { key: 'M', name: '包容型', color: '#10b981' },
  { key: 'R', name: '责任型', color: '#f59e0b' },
]

const clearPendingRefreshTimer = () => {
  if (pendingRefreshTimer) {
    clearTimeout(pendingRefreshTimer)
    pendingRefreshTimer = null
  }
}

const schedulePendingRefresh = () => {
  clearPendingRefreshTimer()
  pendingRefreshTimer = setTimeout(() => {
    fetchReport({ silent: true })
  }, 4000)
}

// --- 数据获取 ---
const fetchReport = async ({ silent = false } = {}) => {
  clearPendingRefreshTimer()
  if (!silent) {
    loading.value = true
  }

  try {
    const res = await api.get(`/assessment/report/${props.sessionId}`)
    reportData.value = res.data
    loadError.value = ''
  } catch (err) {
    console.error('获取报告失败:', err)
    loadError.value = '报告暂时还没加载出来，请稍后刷新再试。'
  } finally {
    loading.value = false
    if (!loadError.value && reportPending.value) {
      schedulePendingRefresh()
    }
  }
}

// --- Markdown 渲染 ---
const renderMarkdown = (text) => renderReportMarkdown(text)

// --- 计算属性 ---
const hasDimensionData = computed(() => !!reportData.value.dimension_summary)
const hasReport = computed(() => !!reportData.value.report)
const reportPending = computed(() => reportData.value.status === 'completed' && !reportData.value.report)
const hasDebateResults = computed(() => {
  const d = reportData.value.module_debates
  return d && Object.keys(d).length > 0
})
const formattedReport = computed(() => renderMarkdown(reportData.value.report))
const trustSummary = computed(() => reportData.value.trust_summary || {})
const adaptiveMetrics = computed(() => reportData.value.adaptive_metrics || {})
const agentWorkflow = computed(() => reportData.value.agent_workflow || null)
const agentState = computed(() => reportData.value.agent_state || agentWorkflow.value?.state || {})
const agentTrace = computed(() => reportData.value.agent_trace || agentWorkflow.value?.trace || {})
const reportCritic = computed(() => reportData.value.report_critic || agentWorkflow.value?.critic || {})
const agentTraceSteps = computed(() => agentTrace.value.steps || [])

const workflowPolicyLabel = computed(() => {
  const policy = agentState.value.report_policy
  if (policy === 'normal') return '正常策略'
  if (policy === 'conservative') return '保守策略'
  return '生成中'
})

const evidenceStatusLabel = computed(() => {
  const status = agentState.value.evidence_status
  if (status === 'available') return '充分'
  if (status === 'partial') return '部分'
  if (status === 'missing') return '缺失'
  return '未知'
})

const criticStatusLabel = computed(() => {
  const status = reportCritic.value.status || agentState.value.critic_status
  if (status === 'passed') return '通过'
  if (status === 'warning') return '需关注'
  return '待审查'
})
const reportTitle = computed(() => {
  const title = (reportData.value.title || '').trim()
  return title || formatTime(reportData.value.started_at) || '未命名测评'
})

// --- 雷达图 ---
const radarData = computed(() => {
  const ds = reportData.value.dimension_summary
  if (!ds) return { labels: [], datasets: [] }
  return {
    labels: modules.map(m => [m.key, m.name]),
    datasets: [{
      label: 'ATMR 特质分布',
      data: modules.map(m => ds[m.key]?.percentage || 0),
      backgroundColor: 'rgba(79, 70, 229, 0.1)',
      borderColor: '#4f46e5',
      borderWidth: 2,
      pointBackgroundColor: modules.map(m => m.color),
      pointBorderColor: '#fff',
      pointBorderWidth: 2.5,
      pointRadius: 5,
      pointHoverRadius: 8,
      pointHitRadius: 12,
    }],
  }
})

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: 8,
  },
  elements: {
    line: { tension: 0.16 },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      displayColors: false,
      backgroundColor: '#334155',
      titleColor: '#ffffff',
      bodyColor: '#f9fafb',
      padding: 12,
      cornerRadius: 12,
      callbacks: {
        label: (ctx) => {
          const label = Array.isArray(ctx.label) ? ctx.label.join(' ') : ctx.label
          return `${label}: ${ctx.raw}%`
        },
      },
    },
  },
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: {
        display: false,
        stepSize: 20,
        showLabelBackdrop: false,
        font: { size: 10, weight: '600' },
        color: 'rgba(100, 116, 139, 0.52)',
        backdropColor: 'transparent',
      },
      grid: { color: 'rgba(148, 163, 184, 0.2)', circular: false },
      angleLines: { color: 'rgba(148, 163, 184, 0.22)', lineWidth: 1 },
      pointLabels: {
        padding: 10,
        font: { size: 12, weight: '800', lineHeight: 1.2 },
        color: '#334155',
      },
    },
  },
}

// --- 辅助方法 ---
const getDimPercentage = (k) => reportData.value.dimension_summary?.[k]?.percentage || 0
const getDimTotal = (k) => reportData.value.dimension_summary?.[k]?.total_score || 0
const getDimMax = (k) => reportData.value.dimension_summary?.[k]?.max_possible || 0
const getDimAvg = (k) => reportData.value.dimension_summary?.[k]?.avg_score || 0
const getDimAnomalyCount = (k) => reportData.value.dimension_summary?.[k]?.anomaly_count || 0
const getDimLevelLabel = (k) => reportData.value.dimension_summary?.[k]?.level_label || ''
const getDimLevelColor = (k) => reportData.value.dimension_summary?.[k]?.level_color || '#94a3b8'
const getDimBonus = (k) => reportData.value.dimension_summary?.[k]?.weighted_bonus || 0
const getDimConfidencePercent = (k) => Math.round((reportData.value.dimension_summary?.[k]?.confidence?.confidence ?? 0) * 100)
const hasConfidenceWeightedReference = (k) => reportData.value.dimension_summary?.[k]?.confidence_weighted_score !== undefined
const getConfidenceWeightedScore = (k) => reportData.value.dimension_summary?.[k]?.confidence_weighted_score || 0
const getConfidenceWeightedDelta = (k) => reportData.value.dimension_summary?.[k]?.confidence_weighted_delta || 0
const getEvidenceCount = (k) => reportData.value.dimension_summary?.[k]?.question_count || 0
const getEvidenceRecords = (k) => reportData.value.dimension_summary?.[k]?.evidence_records || []
const getModuleColor = (k) => modules.find(m => m.key === k)?.color || '#94a3b8'
const scoreClass = (s) => s >= 4 ? 'score-high' : s >= 3 ? 'score-mid' : 'score-low'
const toggleDimension = (k) => { expandedDimension[k] = !expandedDimension[k] }
const percent = (value) => Math.round((Number(value) || 0) * 100)
const formatDelta = (value) => {
  const delta = Number(value || 0)
  if (Math.abs(delta) < 0.005) return '0.00'
  return `${delta > 0 ? '+' : ''}${delta.toFixed(2)}`
}
const getConfidenceWeightedNote = (k) => {
  const delta = Math.abs(Number(getConfidenceWeightedDelta(k) || 0))
  if (delta < 0.5) return '与主得分基本一致。'
  return '异常或低可信作答可能影响该维度解释。'
}
const behaviorSummary = (record) => {
  const metrics = record?.behavior_metrics || {}
  const parts = []
  if (metrics.first_action_latency !== undefined) {
    parts.push(`首次交互 ${Number(metrics.first_action_latency || 0).toFixed(1)}s`)
  }
  if (metrics.mouse_move_count !== undefined) {
    parts.push(`鼠标移动 ${metrics.mouse_move_count || 0} 次`)
  }
  if (metrics.option_change_count) {
    parts.push(`改选 ${metrics.option_change_count} 次`)
  }
  if (metrics.focus_blur_count) {
    parts.push(`切出 ${metrics.focus_blur_count} 次`)
  }
  if (metrics.rapid_click_flag) {
    parts.push('存在快速连点')
  }
  return parts.join('，')
}

const formatTime = (iso) => {
  return formatApiDateTime(iso)
}

const deleteCurrentSession = async () => {
  const shouldDelete = await showConfirmDialog('确定要删除本次测评记录吗？删除后无法恢复。', {
    title: '删除记录',
    confirmText: '删除',
    cancelText: '取消',
    destructive: true,
  })
  if (!shouldDelete) return
  try {
    await api.delete(`/assessment/session/${props.sessionId}`)
    router.push('/history')
  } catch (err) {
    console.error('删除失败:', err)
    await showAlertDialog(err.response?.data?.detail || '删除失败', {
      title: '删除失败',
      destructive: true,
    })
  }
}

onMounted(() => {
  fetchReport()
})

onBeforeUnmount(() => {
  clearPendingRefreshTimer()
})
</script>

<style scoped>
.report-container {
  width: 100%;
  max-width: 1320px;
  margin: 32px auto 0;
  padding: 0 0 80px;
  color: var(--text-primary);
}

/* === 卡片通用 === */
.report-card {
  background: var(--bg-card);
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  padding: 48px 56px;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg), inset 0 1px 0 0 rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.8);
  margin-bottom: 32px;
  transition: all var(--transition-slow);
}
.report-card:hover { 
  box-shadow: var(--shadow-xl), var(--shadow-glow); 
  border-color: rgba(255, 255, 255, 1);
}

/* === 头部 === */
.header-card {
  text-align: center;
  background: linear-gradient(135deg, rgba(17, 17, 17, 0.03), rgba(17, 17, 17, 0.08));
  padding: 56px 48px;
  border: 2px solid rgba(17, 17, 17, 0.08);
}
.report-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(17, 17, 17, 0.06);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.report-title {
  font-size: 42px;
  font-weight: 800;
  margin: 0 0 12px;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}
.report-meta { font-size: 18px; color: var(--text-secondary); margin: 0; }

/* === 章节 === */
.section-title { font-size: 28px; font-weight: 800; margin: 0 0 20px; color: var(--text-primary); background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.section-desc { font-size: 18px; color: var(--text-secondary); margin: -8px 0 24px; }
.no-report-hint { text-align: center; color: var(--text-muted); padding: 40px; font-size: 20px; }
.report-card--pending { text-align: center; }
.report-pending-actions { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; padding: 0 0 24px; }

/* === 雷达图 === */
.radar-layout { display: flex; gap: 56px; align-items: center; }
.radar-chart-wrapper {
  flex: 0 0 440px;
  width: 440px;
  max-width: 100%;
  aspect-ratio: 1 / 1;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 50% 48%, rgba(15, 23, 42, 0.045), transparent 58%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 26px;
  border-radius: 24px;
  border: 1px solid rgba(203, 213, 225, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.94), 0 14px 34px rgba(15, 23, 42, 0.06);
}
.radar-chart-wrapper canvas {
  width: 100% !important;
  height: 100% !important;
}
.dimension-scores { flex: 1; display: flex; flex-direction: column; gap: 16px; }
.dim-score-item { display: flex; flex-direction: column; gap: 6px; padding: 16px 20px; border-radius: var(--radius-md); background: var(--bg-hover); transition: all var(--transition-normal); }
.dim-score-item:hover { background: var(--border); transform: translateX(8px); }
.dim-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.dim-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: var(--radius-md);
  color: #fff; font-size: 14px; font-weight: 800; flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.dim-badge-sm { width: 24px; height: 24px; font-size: 12px; border-radius: var(--radius-sm); }
.dim-name { font-size: 20px; font-weight: 700; }
.dim-pct { margin-left: auto; font-size: 24px; font-weight: 800; color: var(--primary); }
.dim-level-badge {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 2px 10px; border-radius: 12px;
  color: #fff; font-size: 13px; font-weight: 700;
}
.dim-bar-wrapper { width: 100%; height: 8px; background: var(--bg-card); border-radius: var(--radius-sm); overflow: hidden; box-shadow: var(--shadow-inner); }
.dim-bar { height: 100%; border-radius: var(--radius-sm); transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1); position: relative; }
.dim-bar::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent); animation: shimmer 2s infinite; }
.dim-detail { font-size: 15px; color: var(--text-secondary); }

.trust-card { border-left: 4px solid var(--primary); }
.trust-overview {
  display: grid;
  grid-template-columns: minmax(120px, 180px) 1fr;
  gap: 20px;
  align-items: center;
}
.trust-score {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 18px;
  border-radius: 8px;
  background: var(--bg-hover);
  text-align: center;
}
.trust-score strong { font-size: 34px; color: var(--primary); line-height: 1; }
.trust-score span { font-weight: 700; color: var(--text-primary); }
.trust-copy { color: var(--text-secondary); line-height: 1.7; }
.trust-copy p { margin: 0 0 8px; }

.agent-workflow-card {
  border-left: 4px solid #0f766e;
}
.agent-workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 20px;
}
.workflow-policy-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}
.policy-normal { background: #059669; }
.policy-conservative { background: #d97706; }
.policy-pending { background: #64748b; }
.workflow-state-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.workflow-state-item {
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--bg-hover);
}
.workflow-state-item span {
  display: block;
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 13px;
}
.workflow-state-item strong {
  color: var(--text-primary);
  font-size: 20px;
}
.workflow-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.workflow-step {
  display: flex;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.62);
}
.workflow-step-dot {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 999px;
  background: #059669;
  flex: 0 0 auto;
}
.step-warning .workflow-step-dot { background: #d97706; }
.step-pending .workflow-step-dot { background: #64748b; }
.workflow-step strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.workflow-step p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
.critic-notes {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(15, 118, 110, 0.08);
  color: var(--text-secondary);
}
.critic-notes strong {
  display: block;
  margin-bottom: 6px;
  color: var(--text-primary);
}
.critic-notes p {
  margin: 0 0 6px;
  line-height: 1.6;
}

/* === Markdown 报告渲染 === */
.report-body { padding-top: 12px; text-align: left; }
.markdown-body { line-height: 1.8; font-size: 16px; color: var(--text-secondary); text-align: left; }
.markdown-body :deep(h1) { font-size: 2.25em; font-weight: 800; color: var(--text-primary); margin: 1.5em 0 0.5em; padding-bottom: 0.3em; border-bottom: 3px solid rgba(17, 17, 17, 0.12); text-align: left; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.markdown-body :deep(h2) { font-size: 1.8em; font-weight: 700; color: var(--text-primary); margin: 1.5em 0 0.5em; text-align: left; }
.markdown-body :deep(h3) { font-size: 1.5em; font-weight: 700; color: var(--primary); margin: 1.25em 0 0.5em; text-align: left; }
.markdown-body :deep(h4) { font-size: 1.25em; font-weight: 600; color: var(--text-primary); margin: 1em 0 0.5em; text-align: left; }
.markdown-body :deep(p) { margin: 0 0 1em; text-align: left; font-size: 1em; }
.markdown-body :deep(strong) { color: var(--text-primary); font-weight: 700; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 1.5em; margin: 0 0 1em; }
.markdown-body :deep(li) { margin-bottom: 0.5em; font-size: 1em; }
.markdown-body :deep(li)::marker { color: var(--primary); font-weight: 700; }
.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--primary); padding: 1em 1.25em; margin: 1em 0;
  background: rgba(17, 17, 17, 0.05); border-radius: 0 var(--radius-lg) var(--radius-lg) 0; color: var(--text-secondary);
  font-style: italic; font-size: 1.05em;
}
.markdown-body :deep(hr) { border: none; height: 1px; background: rgba(17, 17, 17, 0.16); margin: 2em 0; }

/* === 分维度报告 === */
.dimension-report-body {
  border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 10px 10px; overflow: hidden;
}
.debate-section {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.debate-section:last-child { border-bottom: none; }
.confidence-reference {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
  background: rgba(17, 17, 17, 0.035);
}
.confidence-reference p {
  margin: 0;
  line-height: 1.7;
  color: var(--text-secondary);
  font-size: 15px;
}
.loading-debate { text-align: center; }
.no-debate-hint { color: var(--text-muted); font-size: 15px; padding: 12px 0; }
.records-section { padding: 0; }
.dim-subsection-title {
  font-size: 18px; font-weight: 700; color: var(--primary);
  margin: 0 0 14px; padding-bottom: 8px;
  border-bottom: 2px solid rgba(17, 17, 17, 0.12);
}

/* === 可折叠模块（分维度报告 & 答题明细共用） === */
.evidence-modules { display: flex; flex-direction: column; gap: 6px; }
.ev-module-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; background: var(--bg-hover); border-radius: 10px;
  cursor: pointer; transition: background 0.15s; user-select: none;
  gap: 12px;
}
.ev-module-header:hover { background: var(--border); }
.ev-module-header.expanded { border-radius: 10px 10px 0 0; }
.ev-module-left { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; flex-wrap: wrap; }
.ev-module-name { font-size: 16px; font-weight: 500; }
.ev-module-stat { font-size: 14px; color: var(--text-muted); }
.collapsible-header {
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; user-select: none;
  gap: 12px;
}
.toggle-arrow {
  width: 8px; height: 8px; border-right: 2px solid var(--text-muted); border-bottom: 2px solid var(--text-muted);
  transform: rotate(-45deg); transition: transform 0.2s; flex-shrink: 0;
}
.toggle-arrow.open { transform: rotate(45deg); }

/* === 答题记录 === */
.ev-records-wrap {
  border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 10px 10px; overflow: hidden;
}
.ev-record {
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  transition: background 0.12s;
}
.ev-record:last-child { border-bottom: none; }
.ev-record:hover { background: rgba(17, 17, 17, 0.02); }
.ev-anomaly { background: rgba(239, 68, 68, 0.025); }
.ev-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.ev-no { font-weight: 700; font-size: 15px; color: var(--primary); }
.ev-trait { font-size: 13px; padding: 2px 7px; background: rgba(17, 17, 17, 0.08); color: var(--primary); border-radius: 4px; }
.ev-score { font-size: 15px; font-weight: 600; }
.score-high { color: var(--success); }
.score-mid { color: var(--warning); }
.score-low { color: var(--error); }
.ev-time { font-size: 14px; color: var(--text-muted); }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 4px; color: #fff; font-weight: 500; }
.badge-red { background: var(--error); }
.badge-cyan { background: var(--secondary); }
.badge-gray { background: #64748b; }
.ev-q { font-size: 16px; color: var(--text-primary); line-height: 1.6; margin-bottom: 4px; }
.ev-a { font-size: 15px; color: var(--text-secondary); }
.ev-a b, .ev-followup b, .ev-explain b { font-weight: 600; color: var(--text-primary); }
.ev-followup { font-size: 15px; color: var(--warning); margin-top: 4px; }
.ev-explain { font-size: 15px; color: var(--success); margin-top: 4px; }
.ev-chain {
  margin-top: 8px; padding: 10px 14px; font-size: 15px; line-height: 1.7;
  background: rgba(17, 17, 17, 0.04); border-left: 3px solid var(--primary);
  border-radius: 0 6px 6px 0; color: var(--text-secondary);
}
.chain-icon::before { content: '🔗 '; }
.ev-empty { padding: 18px; text-align: center; color: var(--text-muted); font-size: 15px; }

/* === 答题明细 === */
.answer-list { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
.answer-item {
  padding: 12px 14px; background: var(--bg-dark);
  border: 1px solid var(--border); border-radius: 8px;
}

/* === 返回按钮 === */
.back-btn {
  display: block; margin: 12px auto 0; padding: 16px 40px;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff; border: none; border-radius: 12px;
  cursor: pointer; font-size: 17px; font-weight: 600; transition: all 0.2s;
}
.back-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(17, 17, 17, 0.24); }

.delete-btn {
  display: block; margin: 12px auto 0; padding: 14px 32px;
  background: transparent; color: var(--error); border: 1px solid var(--error); border-radius: 12px;
  cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.2s;
}
.delete-btn:hover { background: var(--error); color: white; }

.report-bottom-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  margin-top: 24px;
}

.back-btn,
.delete-btn {
  width: min(100%, 320px);
}

/* === 加载 === */
.loading-hint { text-align: center; padding: 80px 20px; color: var(--text-muted); }
.loader-spinner {
  border: 3px solid var(--border); border-top: 3px solid var(--primary);
  border-radius: 50%; width: 32px; height: 32px;
  animation: spin 1s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

/* === 过渡动画 === */
.slide-enter-active, .slide-leave-active { transition: all 0.25s ease; overflow: hidden; }
.slide-enter-from, .slide-leave-to { opacity: 0; max-height: 0; }
.slide-enter-to, .slide-leave-from { opacity: 1; max-height: 2000px; }

/* === 响应式 === */
@media (min-width: 1200px) {
  .markdown-body { font-size: 18px; } /* 大屏基础稍微大一些 */
}

@media (max-width: 768px) {
  .report-container { padding: 32px 16px 60px; }
  .report-card { padding: 32px 24px; }
  .header-card { padding: 40px 24px; }
  .report-title { font-size: 32px; }
  .report-meta { font-size: 16px; line-height: 1.6; }
  .radar-layout { flex-direction: column; gap: 24px; }
  .radar-chart-wrapper { flex: 0 0 auto; width: 100%; max-width: 320px; margin: 0 auto; }
  .dim-name { font-size: 18px; }
  .dim-pct { font-size: 20px; }
  .dim-detail { line-height: 1.6; }
  .ev-module-header { align-items: flex-start; }
  .trust-overview { grid-template-columns: 1fr; }
  .agent-workflow-header { flex-direction: column; }
  .workflow-state-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow-steps { grid-template-columns: 1fr; }
  .ev-module-stat { flex-basis: 100%; }
  .markdown-body { font-size: 15px; } /* 通过调整基础 font-size 自动控制里面的em字体大小 */
}

@media (max-width: 480px) {
  .report-container { padding: 24px 12px 48px; }
  .report-card { padding: 24px 20px; }
  .header-card { padding: 32px 20px; }
  .report-title { font-size: 26px; }
  .report-meta { font-size: 14px; }
  .section-title { font-size: 22px; }
  .radar-chart-wrapper { max-width: 100%; padding: 16px; }
  .dim-header { gap: 8px; }
  .dim-name { font-size: 16px; }
  .dim-pct { margin-left: 0; width: 100%; font-size: 18px; }
  .dim-level-badge { font-size: 12px; }
  .dim-detail { font-size: 13px; }
  .ev-module-header { padding: 12px; }
  .ev-module-name { font-size: 15px; }
  .ev-module-stat { font-size: 13px; line-height: 1.5; }
  .workflow-state-grid { grid-template-columns: 1fr; }
  .ev-record { padding: 12px; }
  .ev-q { font-size: 15px; }
  .ev-a,
  .ev-followup,
  .ev-explain,
  .ev-chain { font-size: 14px; }
  .report-bottom-actions { align-items: stretch; }
  .back-btn,
  .delete-btn { width: 100%; }
  .markdown-body { font-size: 14px; } /* 进一步缩小基础字体 */
}
</style>
