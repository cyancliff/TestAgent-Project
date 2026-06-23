<template>
  <div class="report-container">
    <div v-if="loading" class="loading-hint">
      <div class="loader-spinner"></div>
      <p>正在加载大五人格报告...</p>
    </div>

    <div v-else-if="loadError" class="report-card report-card--pending">
      <div class="no-report-hint">{{ loadError }}</div>
      <div class="report-pending-actions">
        <button class="back-btn" type="button" @click="fetchReport()">重新加载</button>
        <button class="back-btn" type="button" @click="$router.push('/history?type=big-five')">返回历史记录</button>
      </div>
    </div>

    <template v-else>
      <div class="report-card header-card">
        <span class="report-kicker">大五人格视频报告</span>
        <h1 class="report-title">{{ reportTitle }}</h1>
        <p class="report-meta">
          报告 #{{ report.report_id || reportId }} | {{ formatDate(report.created_at) }}
          <span v-if="report.completed_at"> - {{ formatDate(report.completed_at) }}</span>
          <span> | {{ statusLabel }}</span>
        </p>
      </div>

      <div v-if="hasScores" class="report-card radar-section">
        <h2 class="section-title">大五人格画像</h2>
        <div class="radar-layout">
          <div class="radar-chart-wrapper">
            <Radar :data="radarData" :options="radarOptions" />
          </div>
          <div class="dimension-scores">
            <div v-for="dimension in dimensions" :key="dimension.key" class="dim-score-item">
              <div class="dim-header">
                <span class="dim-badge" :style="{ background: dimension.color }">{{ dimension.short }}</span>
                <span class="dim-name">{{ dimension.label }}</span>
                <span class="dim-level-badge" :style="{ background: getDimensionLevelColor(dimension.key) }">
                  {{ getDimensionLevelLabel(dimension.key) }}
                </span>
                <span class="dim-pct">{{ scorePercent(dimension.key) }}%</span>
              </div>
              <div class="dim-bar-wrapper">
                <div
                  class="dim-bar"
                  :style="{ width: `${scorePercent(dimension.key)}%`, background: dimension.color }"
                ></div>
              </div>
              <div class="dim-detail">
                {{ dimension.note }} · {{ dimension.facets.length }} 个 Facet · 视频多模态线索
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="report-card report-card--pending">
        <div class="no-report-hint">{{ emptyTitle }}。{{ emptyNote }}</div>
        <div class="report-pending-actions">
          <button class="back-btn" type="button" @click="fetchReport({ silent: true })">立即刷新</button>
          <button class="back-btn" type="button" @click="$router.push('/history?type=big-five')">返回历史记录</button>
        </div>
      </div>

      <div class="report-card">
        <h2 class="section-title">报告来源</h2>
        <div class="source-grid">
          <div class="source-item">
            <span>视频文件</span>
            <strong>{{ report.original_filename || '未记录' }}</strong>
          </div>
          <div class="source-item">
            <span>模型版本</span>
            <strong>{{ report.model_version || '未知' }}</strong>
          </div>
          <div class="source-item">
            <span>结果性质</span>
            <strong>{{ report.is_real_result ? '真实模型输出' : '不可用于对话' }}</strong>
          </div>
        </div>
      </div>

      <div v-if="hasScores" class="report-card evidence-card">
        <h2 class="section-title">质量与置信度</h2>
        <div class="source-grid evidence-grid">
          <div class="source-item">
            <span>模态质量</span>
            <strong>{{ percent(qualitySummary.overall_quality) }}% · {{ qualitySummary.label || '中等' }}</strong>
          </div>
          <div class="source-item">
            <span>预测置信度</span>
            <strong>{{ percent(confidenceSummary.overall_confidence) }}% · {{ confidenceSummary.label || '中等' }}</strong>
          </div>
        </div>
        <div class="quality-bars">
          <div v-for="item in modalityItems" :key="item.key" class="quality-row">
            <span>{{ item.label }}</span>
            <div class="quality-track">
              <div class="quality-fill" :style="{ width: `${percent(item.value)}%` }"></div>
            </div>
            <strong>{{ percent(item.value) }}%</strong>
          </div>
        </div>
      </div>

      <div v-if="hasInterpretation" class="interpretation-stack">
        <div
          v-for="section in interpretationSections"
          :key="section.key"
          class="report-card interpretation-card"
        >
          <h2 class="section-title">{{ section.title }}</h2>
          <div class="report-body markdown-body compact-markdown" v-html="renderMarkdown(section.content)"></div>
        </div>
      </div>
      <div v-else class="report-card report-card--pending">
        <div class="no-report-hint">
          <strong>{{ interpretationEmptyTitle }}</strong>
          <span>{{ interpretationEmptyNote }}</span>
        </div>
        <div v-if="canRetryInterpretation" class="report-pending-actions">
          <button class="back-btn" type="button" @click="retryInterpretation">{{ interpretationActionLabel }}</button>
        </div>
      </div>

      <div v-if="hasScores" class="report-card">
        <h2 class="section-title">维度简析</h2>
        <p class="section-desc">每个维度保留分数、水平、Facet 线索和一条可执行建议，避免正文里重复堆表格。</p>

        <div class="dimension-brief-grid">
          <article
            v-for="dimension in dimensions"
            :key="`brief-${dimension.key}`"
            class="dimension-brief-card"
            :style="{ '--dimension-color': dimension.color }"
          >
            <div class="brief-header">
              <span class="dim-badge" :style="{ background: dimension.color }">{{ dimension.short }}</span>
              <div class="brief-title">
                <strong>{{ dimension.label }}</strong>
                <span>{{ dimension.note }}</span>
              </div>
              <div class="brief-score">
                <strong>{{ scorePercent(dimension.key) }}%</strong>
                <span>{{ getDimensionLevelLabel(dimension.key) }}</span>
              </div>
            </div>

            <div class="dim-bar-wrapper brief-bar">
              <div
                class="dim-bar"
                :style="{ width: `${scorePercent(dimension.key)}%`, background: dimension.color }"
              ></div>
            </div>

            <p class="brief-summary">{{ getDimensionScoreExplanation(dimension) }}</p>

            <div class="facet-chips" aria-label="Facet 线索">
              <span v-for="facet in dimension.facets" :key="`${dimension.key}-${facet}`">{{ facet }}</span>
            </div>

            <p class="brief-advice"><strong>建议</strong>{{ getDimensionAdvice(dimension) }}</p>
          </article>
        </div>
      </div>

      <div class="report-bottom-actions">
        <button class="back-btn" type="button" @click="$router.push('/history?type=big-five')">返回历史记录</button>
        <button v-if="canRetry" class="back-btn" type="button" @click="retryReport">重新生成</button>
        <button v-if="canRegenerateInterpretation" class="back-btn" type="button" @click="retryInterpretation">
          {{ interpretationActionLabel }}
        </button>
        <button v-if="canUseInChat" class="back-btn" type="button" @click="useInChat">用于对话</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Radar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  PointElement,
  RadialLinearScale,
  Tooltip,
} from 'chart.js'
import api from '../api'
import { showAlertDialog } from '../composables/useAppDialog'
import { formatApiDateTime } from '../utils/dateTime'
import { renderReportMarkdown } from '../utils/markdown'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const props = defineProps({ reportId: String })
const router = useRouter()

const report = ref({})
const loading = ref(true)
const loadError = ref('')
let pollTimer = null

const dimensions = [
  {
    key: 'openness',
    short: 'O',
    label: '开放性',
    color: '#2563eb',
    note: '对新体验、想象力和变化的开放程度',
    facets: ['求知好奇', '审美敏感', '创造想象'],
    high: '更容易被新信息、复杂问题和创造性体验吸引。',
    mid: '能在熟悉框架和新鲜探索之间保持相对平衡。',
    low: '更偏好清晰、稳定、可预期的路径与经验。',
    advice: '给探索留一个小入口，例如每周尝试一个新主题，同时保留熟悉的执行节奏。',
  },
  {
    key: 'conscientiousness',
    short: 'C',
    label: '尽责性',
    color: '#7c3aed',
    note: '计划性、自律性和目标执行稳定度',
    facets: ['组织性', '生产性', '责任性'],
    high: '更容易重视秩序、承诺和长期目标。',
    mid: '通常能完成重要任务，也需要给弹性和恢复留空间。',
    low: '更可能依赖情境动力，面对长期计划时需要外部结构辅助。',
    advice: '把目标拆成下一步动作，用更短的检查周期降低启动成本。',
  },
  {
    key: 'extraversion',
    short: 'E',
    label: '外向性',
    color: '#22c55e',
    note: '社交能量、表达主动性和外部互动倾向',
    facets: ['社交性', '自信表达', '活力水平'],
    high: '更容易从互动、表达和外部反馈中获得能量。',
    mid: '能在独处和社交之间切换，表现会受场景影响。',
    low: '更可能偏好低刺激环境，表达前需要更多准备空间。',
    advice: '根据能量安排沟通密度，把重要表达放在状态更稳定的时间段。',
  },
  {
    key: 'agreeableness',
    short: 'A',
    label: '宜人性',
    color: '#f59e0b',
    note: '合作、信任和关系中的亲和倾向',
    facets: ['同情心', '尊重性', '信任性'],
    high: '更容易体察他人感受，并倾向于维护合作氛围。',
    mid: '能兼顾关系与立场，通常会根据对象和情境调整表达。',
    low: '更重视边界、效率和直接判断，可能不急于妥协。',
    advice: '在照顾关系之前先写清自己的底线，减少过度配合或过度防御。',
  },
  {
    key: 'neuroticism',
    short: 'N',
    label: '神经质',
    color: '#ef4444',
    note: '压力敏感度和情绪波动倾向',
    facets: ['焦虑', '抑郁感', '情绪波动'],
    high: '对压力、风险和不确定性可能更敏感。',
    mid: '情绪反应通常有波动，但仍能在多数场景下恢复。',
    low: '面对压力时更容易保持稳定，但也可能低估某些风险信号。',
    advice: '把压力信号当作提醒而非结论，优先用睡眠、节奏和支持系统降低负荷。',
  },
]

const reportTitle = computed(() => (report.value.title || '').trim() || `大五人格报告 #${props.reportId}`)
const hasScores = computed(() => !!report.value.scores)
const qualitySummary = computed(() => report.value.quality_summary || {})
const confidenceSummary = computed(() => report.value.confidence_summary || {})
const modalityItems = computed(() => {
  const modalities = qualitySummary.value.modalities || {}
  return [
    { key: 'visual', label: '视觉质量', value: modalities.visual || 0 },
    { key: 'audio', label: '音频质量', value: modalities.audio || 0 },
    { key: 'text', label: '文本质量', value: modalities.text || 0 },
    { key: 'background', label: '背景关联特征', value: modalities.background || 0 },
  ]
})
const canUseInChat = computed(() => report.value.status === 'completed' && report.value.is_real_result && hasScores.value)
const canRetry = computed(() => ['failed', 'completed'].includes(report.value.status) && !report.value.is_real_result)
const interpretationStatus = computed(() => report.value.interpretation_status || 'pending')
const hasInterpretation = computed(() => interpretationStatus.value === 'completed' && !!report.value.interpretation_content)
const canRetryInterpretation = computed(() => canUseInChat.value && ['pending', 'failed', 'skipped'].includes(interpretationStatus.value))
const canRegenerateInterpretation = computed(() => canUseInChat.value && (hasInterpretation.value || canRetryInterpretation.value))
const interpretationActionLabel = computed(() => (
  interpretationStatus.value === 'pending' ? '生成 AI 解读' : '重新生成 AI 解读'
))
const statusLabel = computed(() => {
  if (report.value.status === 'completed' && report.value.is_real_result) return '已完成'
  if (report.value.status === 'completed') return '仅作参考'
  if (report.value.status === 'failed') return '生成失败'
  if (report.value.status === 'running') return '生成中'
  return '等待处理'
})
const emptyTitle = computed(() => (report.value.status === 'failed' ? '报告生成失败' : '报告还在生成中'))
const emptyNote = computed(() => (
  report.value.status === 'failed'
    ? '可以稍后重试，或换一段视频重新上传。'
    : '页面会自动刷新，完成后显示五维得分。'
))
const interpretationEmptyTitle = computed(() => {
  if (interpretationStatus.value === 'failed') return 'AI 解读生成失败'
  if (interpretationStatus.value === 'skipped') return '这份报告暂不生成正式 AI 解读'
  if (interpretationStatus.value === 'running') return '正在生成 AI 详细解读'
  return 'AI 详细解读等待生成'
})
const interpretationEmptyNote = computed(() => {
  if (interpretationStatus.value === 'failed') return report.value.interpretation_error || '可以稍后重新生成 AI 解读。'
  if (interpretationStatus.value === 'skipped') return report.value.interpretation_error || '只有真实完成的大五人格报告会生成正式解读。'
  if (interpretationStatus.value === 'running') return '页面会自动刷新，完成后显示完整解读。'
  return canUseInChat.value ? '可以点击下方按钮生成这份 AI 详细解读。' : '视频分析完成后会继续生成。'
})

const cleanInterpretationTitle = (title) => (
  title
    .replace(/^\s*(?:\d+|[一二三四五六七八九十]+)[.\s、-]*/, '')
    .trim()
)

const parseInterpretationSections = (content) => {
  const lines = (content || '').split(/\r?\n/)
  const sections = []
  let current = null
  const introLines = []

  const pushCurrent = () => {
    if (current && current.lines.some((line) => line.trim())) {
      sections.push({
        title: cleanInterpretationTitle(current.title),
        content: current.lines.join('\n').trim(),
      })
    }
  }

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+?)\s*$/)
    if (h2) {
      pushCurrent()
      current = { title: h2[1], lines: [] }
      continue
    }
    if (/^#\s+/.test(line)) continue
    if (current) current.lines.push(line)
    else introLines.push(line)
  }

  pushCurrent()

  if (!sections.length && introLines.some((line) => line.trim())) {
    sections.push({ title: '综合人格画像', content: introLines.join('\n').trim() })
  }

  return sections
}

const buildInterpretationGroup = (sections, keywords) => {
  const matched = sections.filter((section) => (
    keywords.some((keyword) => section.title.includes(keyword))
  ))
  if (!matched.length) return ''
  return matched
    .map((section) => (
      matched.length > 1
        ? `### ${section.title}\n\n${section.content}`
        : section.content
    ))
    .join('\n\n')
    .trim()
}

const interpretationSections = computed(() => {
  const parsed = parseInterpretationSections(report.value.interpretation_content)
  const groups = [
    {
      key: 'profile',
      title: '综合人格画像',
      content: buildInterpretationGroup(parsed, ['报告摘要', '大五人格画像', '综合人格画像']),
    },
    {
      key: 'strengths',
      title: '优势与潜在卡点',
      content: buildInterpretationGroup(parsed, ['优势', '风险', '卡点']),
    },
    {
      key: 'actions',
      title: '行动建议',
      content: buildInterpretationGroup(parsed, ['行动建议']),
    },
    {
      key: 'boundary',
      title: '使用边界',
      content: buildInterpretationGroup(parsed, ['使用边界']),
    },
  ].filter((section) => section.content)

  if (groups.length) return groups
  return [{ key: 'fallback', title: '综合人格画像', content: report.value.interpretation_content || '' }]
})

const renderMarkdown = (content) => renderReportMarkdown(content || '')

const radarData = computed(() => ({
  labels: dimensions.map((dimension) => [dimension.short, dimension.label]),
  datasets: [
    {
      label: '大五人格分布',
      data: dimensions.map((dimension) => scorePercent(dimension.key)),
      backgroundColor: 'rgba(79, 70, 229, 0.1)',
      borderColor: '#4f46e5',
      borderWidth: 2,
      pointBackgroundColor: dimensions.map((dimension) => dimension.color),
      pointBorderColor: '#fff',
      pointBorderWidth: 2.5,
      pointRadius: 5,
      pointHoverRadius: 8,
      pointHitRadius: 12,
    },
  ],
}))

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

const scorePercent = (key) => {
  const raw = Number(report.value.scores?.[key])
  if (!Number.isFinite(raw)) return 0
  return Math.max(0, Math.min(100, Math.round(raw * 100)))
}
const percent = (value) => Math.round((Number(value) || 0) * 100)

const getDimensionLevelLabel = (key) => {
  const score = scorePercent(key)
  if (score >= 65) return '偏高'
  if (score <= 35) return '偏低'
  return '中等'
}

const getDimensionLevelColor = (key) => {
  const score = scorePercent(key)
  if (score >= 65) return '#10b981'
  if (score <= 35) return '#64748b'
  return '#f59e0b'
}

const getDimensionTone = (dimension) => {
  const score = scorePercent(dimension.key)
  if (score >= 65) return dimension.high
  if (score <= 35) return dimension.low
  return dimension.mid
}

const getDimensionScoreExplanation = (dimension) => (
  `${dimension.label}当前为 ${scorePercent(dimension.key)}%，处于${getDimensionLevelLabel(dimension.key)}水平。${getDimensionTone(dimension)}`
)
const getDimensionBehavior = (dimension) => getDimensionTone(dimension)
const getDimensionAdvice = (dimension) => dimension.advice

const formatDate = (iso) => {
  return formatApiDateTime(iso, '时间未记录')
}

const clearPoll = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const syncPoll = () => {
  const shouldPoll = ['pending', 'running'].includes(report.value.status)
    || (canUseInChat.value && interpretationStatus.value === 'running')
  if (shouldPoll && !pollTimer) {
    pollTimer = setInterval(() => fetchReport({ silent: true }), 4000)
  }
  if (!shouldPoll) {
    clearPoll()
  }
}

const fetchReport = async ({ silent = false } = {}) => {
  if (!silent) loading.value = true
  try {
    const res = await api.get(`/multimodal-personality/reports/${props.reportId}`)
    report.value = res.data
    loadError.value = ''
    syncPoll()
  } catch (err) {
    console.error('获取大五人格报告失败:', err)
    loadError.value = err.response?.data?.detail || '报告加载失败，请稍后重试。'
    await showAlertDialog(loadError.value, {
      title: '加载失败',
      destructive: true,
    })
  } finally {
    loading.value = false
  }
}

const retryReport = async () => {
  try {
    const res = await api.post(`/multimodal-personality/reports/${props.reportId}/run-background`)
    report.value = res.data
    syncPoll()
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || '重新生成失败', {
      title: '操作失败',
      destructive: true,
    })
  }
}

const retryInterpretation = async () => {
  try {
    const res = await api.post(`/multimodal-personality/reports/${props.reportId}/interpretation/run-background`)
    report.value = res.data
    syncPoll()
  } catch (err) {
    await showAlertDialog(err.response?.data?.detail || 'AI 解读重新生成失败', {
      title: '操作失败',
      destructive: true,
    })
  }
}

const useInChat = () => {
  router.push({ path: '/chat', query: { bigFiveReportId: report.value.report_id } })
}

onMounted(() => {
  fetchReport()
})

onBeforeUnmount(() => {
  clearPoll()
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

.report-meta {
  font-size: 18px;
  color: var(--text-secondary);
  margin: 0;
}

.section-title {
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 20px;
  color: var(--text-primary);
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.section-desc {
  font-size: 18px;
  color: var(--text-secondary);
  margin: -8px 0 24px;
}

.no-report-hint {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: center;
  color: var(--text-muted);
  padding: 40px;
  font-size: 20px;
}

.no-report-hint strong {
  color: var(--text-primary);
}

.report-card--pending {
  text-align: center;
}

.report-pending-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  justify-content: center;
  padding: 0 0 24px;
}

.radar-layout {
  display: flex;
  gap: 56px;
  align-items: center;
}

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

.dimension-scores {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dim-score-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 20px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  transition: all var(--transition-normal);
}

.dim-score-item:hover {
  background: var(--border);
  transform: translateX(8px);
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.dim-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.dim-name {
  font-size: 20px;
  font-weight: 700;
}

.dim-pct {
  margin-left: auto;
  font-size: 24px;
  font-weight: 800;
  color: var(--primary);
}

.dim-level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 10px;
  border-radius: 12px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.dim-bar-wrapper {
  width: 100%;
  height: 8px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: var(--shadow-inner);
}

.dim-bar {
  height: 100%;
  border-radius: var(--radius-sm);
  transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
  position: relative;
}

.dim-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
  animation: shimmer 2s infinite;
}

.dim-detail {
  font-size: 15px;
  color: var(--text-secondary);
}

.interpretation-stack {
  display: contents;
}

.interpretation-card {
  margin-bottom: 28px;
}

.compact-markdown {
  font-size: 16px;
}

.compact-markdown :deep(h3) {
  font-size: 1.15em;
  margin-top: 1.1em;
}

.dimension-brief-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.dimension-brief-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  padding: 20px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.72));
  border: 1px solid rgba(203, 213, 225, 0.76);
  box-shadow: inset 3px 0 0 var(--dimension-color), 0 10px 26px rgba(15, 23, 42, 0.04);
}

.brief-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.brief-title {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.brief-title strong {
  font-size: 18px;
  color: var(--text-primary);
}

.brief-title span {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.brief-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.brief-score strong {
  color: var(--dimension-color);
  font-size: 24px;
  line-height: 1;
}

.brief-score span {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 700;
}

.brief-bar {
  background: rgba(226, 232, 240, 0.72);
}

.brief-summary {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.facet-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.facet-chips span {
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--dimension-color) 12%, white);
  color: var(--dimension-color);
  font-size: 13px;
  font-weight: 700;
}

.brief-advice {
  margin: auto 0 0;
  padding-top: 12px;
  border-top: 1px solid rgba(203, 213, 225, 0.72);
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.brief-advice strong {
  display: inline-flex;
  margin-right: 8px;
  color: var(--text-primary);
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 18px 20px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
}

.source-item span {
  color: var(--text-secondary);
  font-size: 14px;
}

.source-item strong {
  overflow-wrap: anywhere;
  color: var(--text-primary);
}

.evidence-card {
  border-left: 4px solid var(--primary);
}

.evidence-grid {
  margin-bottom: 18px;
}

.quality-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quality-row {
  display: grid;
  grid-template-columns: 120px 1fr 56px;
  gap: 12px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 14px;
}

.quality-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.9);
}

.quality-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--primary);
}

.report-body {
  padding-top: 12px;
  text-align: left;
}

.markdown-body {
  line-height: 1.8;
  font-size: 16px;
  color: var(--text-secondary);
  text-align: left;
}

.markdown-body :deep(h1) {
  font-size: 2.25em;
  font-weight: 800;
  color: var(--text-primary);
  margin: 1.5em 0 0.5em;
  padding-bottom: 0.3em;
  border-bottom: 3px solid rgba(17, 17, 17, 0.12);
  text-align: left;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.markdown-body :deep(h2) {
  font-size: 1.8em;
  font-weight: 700;
  color: var(--text-primary);
  margin: 1.5em 0 0.5em;
  text-align: left;
}

.markdown-body :deep(h3) {
  font-size: 1.5em;
  font-weight: 700;
  color: var(--primary);
  margin: 1.25em 0 0.5em;
  text-align: left;
}

.markdown-body :deep(h4) {
  font-size: 1.25em;
  font-weight: 600;
  color: var(--text-primary);
  margin: 1em 0 0.5em;
  text-align: left;
}

.markdown-body :deep(p) {
  margin: 0 0 1em;
  text-align: left;
  font-size: 1em;
}

.markdown-body :deep(strong) {
  color: var(--text-primary);
  font-weight: 700;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0 0 1em;
}

.markdown-body :deep(li) {
  margin-bottom: 0.5em;
  font-size: 1em;
}

.markdown-body :deep(li)::marker {
  color: var(--primary);
  font-weight: 700;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--primary);
  padding: 1em 1.25em;
  margin: 1em 0;
  background: rgba(17, 17, 17, 0.05);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
  color: var(--text-secondary);
  font-style: italic;
  font-size: 1.05em;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0 22px;
  overflow: hidden;
  border-radius: 12px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(17, 17, 17, 0.12);
  padding: 10px 12px;
  vertical-align: top;
}

.markdown-body :deep(th) {
  background: rgba(17, 17, 17, 0.06);
  color: var(--text-primary);
}

.markdown-body :deep(hr) {
  border: none;
  height: 1px;
  background: rgba(17, 17, 17, 0.16);
  margin: 2em 0;
}

.evidence-modules {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ev-module-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--bg-hover);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
  gap: 12px;
}

.ev-module-header:hover {
  background: var(--border);
}

.ev-module-header.expanded {
  border-radius: 10px 10px 0 0;
}

.ev-module-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.ev-module-name {
  font-size: 16px;
  font-weight: 500;
}

.ev-module-stat {
  font-size: 14px;
  color: var(--text-muted);
}

.toggle-arrow {
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--text-muted);
  border-bottom: 2px solid var(--text-muted);
  transform: rotate(-45deg);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.toggle-arrow.open {
  transform: rotate(45deg);
}

.dimension-report-body {
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 10px 10px;
  overflow: hidden;
}

.debate-section {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}

.dim-subsection-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  margin: 0 0 14px;
  padding-bottom: 8px;
  border-bottom: 2px solid rgba(17, 17, 17, 0.12);
}

.dimension-copy {
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.7;
}

.dimension-copy p {
  margin: 0 0 10px;
}

.dimension-insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 18px 20px;
}

.dimension-insight-card {
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
}

.dimension-insight-card span {
  display: block;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 14px;
  font-weight: 700;
}

.dimension-insight-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.back-btn {
  display: block;
  margin: 12px auto 0;
  padding: 16px 40px;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 17px;
  font-weight: 600;
  transition: all 0.2s;
}

.back-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(17, 17, 17, 0.24);
}

.report-bottom-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  margin-top: 24px;
}

.back-btn {
  width: min(100%, 320px);
}

.loading-hint {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}

.loader-spinner {
  border: 3px solid var(--border);
  border-top: 3px solid var(--primary);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 1200px;
}

@media (min-width: 1200px) {
  .markdown-body {
    font-size: 18px;
  }
}

@media (max-width: 768px) {
  .report-container {
    padding: 32px 16px 60px;
  }

  .report-card {
    padding: 32px 24px;
  }

  .header-card {
    padding: 40px 24px;
  }

  .report-title {
    font-size: 32px;
  }

  .report-meta {
    font-size: 16px;
    line-height: 1.6;
  }

  .radar-layout {
    flex-direction: column;
    gap: 24px;
  }

  .radar-chart-wrapper {
    flex: 0 0 auto;
    width: 100%;
    max-width: 320px;
    margin: 0 auto;
  }

  .source-grid,
  .evidence-grid,
  .dimension-insight-grid,
  .dimension-brief-grid {
    grid-template-columns: 1fr;
  }

  .quality-row {
    grid-template-columns: 92px 1fr 48px;
  }

  .dim-name {
    font-size: 18px;
  }

  .dim-pct {
    font-size: 20px;
  }

  .dim-detail {
    line-height: 1.6;
  }

  .ev-module-header {
    align-items: flex-start;
  }

  .ev-module-stat {
    flex-basis: 100%;
  }

  .markdown-body {
    font-size: 15px;
  }
}

@media (max-width: 480px) {
  .report-container {
    padding: 24px 12px 48px;
  }

  .report-card {
    padding: 24px 20px;
  }

  .header-card {
    padding: 32px 20px;
  }

  .report-title {
    font-size: 26px;
  }

  .report-meta {
    font-size: 14px;
  }

  .section-title {
    font-size: 22px;
  }

  .radar-chart-wrapper {
    max-width: 100%;
    padding: 16px;
  }

  .dim-header {
    gap: 8px;
  }

  .dim-name {
    font-size: 16px;
  }

  .dim-pct {
    margin-left: 0;
    width: 100%;
    font-size: 18px;
  }

  .dim-level-badge {
    font-size: 12px;
  }

  .dim-detail,
  .ev-module-stat {
    font-size: 13px;
    line-height: 1.5;
  }

  .ev-module-header,
  .ev-module-left {
    align-items: flex-start;
  }

  .ev-module-name {
    font-size: 15px;
  }

  .dimension-insight-grid,
  .debate-section {
    padding: 14px 12px;
  }

  .report-bottom-actions {
    align-items: stretch;
  }

  .back-btn {
    width: 100%;
  }

  .markdown-body {
    font-size: 14px;
  }
}
</style>
