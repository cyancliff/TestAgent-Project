<template>
  <div class="assessment-container">
    <div v-if="!hasStarted" class="start-page">
      <div class="start-card">
        <div class="start-icon">📝</div>
        <h1 class="start-title">ATMR 心理测评</h1>
        <p class="start-description">
          本测评包含 42 道题目，预计用时 10-15 分钟<br>
          系统将智能选择最适合您的题目
        </p>
        <div class="start-features">
          <div class="feature-item"><span class="feature-icon">🧠</span><span>智能选题</span></div>
          <div class="feature-item"><span class="feature-icon">🔍</span><span>异常检测</span></div>
          <div class="feature-item"><span class="feature-icon">👥</span><span>专家辩论</span></div>
        </div>
        <button class="start-btn" @click="startNewSession" :disabled="isStarting">
          <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
          <span v-else>开始测评</span>
        </button>
        <p v-if="startError" class="start-error">{{ startError }}</p>
      </div>
    </div>

    <div v-else-if="!isFinished" class="question-card">
      <div class="header">
        <div class="progress-info">
          <span class="progress-text">题目 {{ currentIndex + 1 }} / {{ maxQuestions }}</span>
          <span v-if="isAdaptive" class="adaptive-badge">🔮 智能选题</span>
          <span v-else class="sequential-badge">📋 顺序选题</span>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: ((answeredCount) / maxQuestions * 100) + '%' }"></div>
          </div>
          <span class="progress-percent">{{ Math.round((answeredCount) / maxQuestions * 100) }}%</span>
        </div>
        <div v-if="currentModule || questionStats" class="module-info">
          <span v-if="currentModule" class="module-badge">模块 {{ currentModule }}</span>
          <div v-if="questionStats" class="stats-grid">
            <span class="stat-item"><span class="stat-icon">📊</span><span class="stat-label">难度</span><span class="stat-value">{{ questionStats.difficulty.toFixed(2) }}</span></span>
            <span class="stat-item"><span class="stat-icon">📈</span><span class="stat-label">区分度</span><span class="stat-value">{{ questionStats.discrimination.toFixed(2) }}</span></span>
          </div>
        </div>
      </div>

      <div class="question-content">
        <h2 class="question-title">{{ currentQuestion.content }}</h2>
      </div>

      <div v-if="!anomalyTriggered" class="options-container">
        <button
          v-for="(option, index) in currentQuestion.options"
          :key="index"
          class="option-btn"
          :class="{ selected: currentAnswer?.selected_option === option }"
          @click="selectOption(option)"
        >
          <span class="option-label">{{ String.fromCharCode(65 + index) }}</span>
          <span class="option-text">{{ option }}</span>
        </button>
      </div>

      <div v-else class="anomaly-container">
        <div class="warning-box">
          <span class="warning-icon">&#9888;</span>
          <span>{{ currentAnswer?.follow_up_question || '系统检测到您的作答时间极短，请问您是如何快速得出这个选择的？' }}</span>
        </div>
        <textarea v-model="userExplanation" placeholder="请输入您的思考过程..." rows="4"></textarea>
        <button class="submit-explanation-btn" @click="submitExplanation">保存解释</button>
      </div>

      <div class="navigation-actions">
        <button class="nav-btn secondary" @click="prevQuestion" :disabled="currentIndex === 0">上一题</button>
        <button class="nav-btn" v-if="currentIndex < maxQuestions - 1" @click="nextQuestion" :disabled="!canGoNext">下一题</button>
        <button class="nav-btn submit-final" v-else @click="submitAllAnswers" :disabled="!canSubmitAll || isSubmittingAll">
          {{ isSubmittingAll ? '提交中...' : '提交答卷' }}
        </button>
      </div>
    </div>

    <div v-else class="result-page">
      <div class="debate-section">
        <div class="debate-header" @click="debateCollapsed = !debateCollapsed">
          <div>
            <h2 class="debate-title">
              AI 评审团辩论
              <span v-if="!isGenerating" class="debate-done-badge">已完成</span>
              <span v-else class="debate-live-badge">进行中</span>
            </h2>
            <p class="debate-subtitle">多位 AI 专家正在就您的答题情况进行深度讨论</p>
          </div>
          <span v-if="!isGenerating" class="collapse-toggle">{{ debateCollapsed ? '展开' : '收起' }}</span>
        </div>

        <div v-show="!debateCollapsed" class="debate-feed" ref="debateFeedRef">
          <div v-for="(msg, i) in debateMessages" :key="i" :class="['debate-msg', agentClass(msg.agent)]">
            <div class="msg-header">
              <span class="agent-avatar">{{ getAgentAvatar(msg.agent) }}</span>
              <span class="agent-name">{{ formatAgentName(msg.agent) }}</span>
            </div>
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div v-if="debateMessages.length === 0" class="waiting-hint">
            <div class="loader-spinner"></div>
            <p>正在唤醒多智能体评审团，请稍候...</p>
          </div>
          <div v-else-if="isGenerating" class="loader-spinner loader-small"></div>
        </div>

        <p v-if="debateError" class="error-text">{{ debateError }}</p>
      </div>

      <div v-if="!isGenerating" class="report-section">
        <div class="report-header">
          <h2 class="report-title">深度心理测评报告</h2>
          <p class="report-subtitle">基于多智能体辩论生成</p>
        </div>
        <div class="report-divider"></div>
        <div class="report-content" v-html="formattedReport"></div>
        <div class="report-actions">
          <button class="restart-btn view-report-btn" @click="$router.push(`/report/${sessionId}`)">查看完整报告</button>
          <button class="restart-btn" @click="restartTest">返回历史记录</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { marked } from 'marked'

const API_BASE = 'http://127.0.0.1:8000/api/v1/assessment'
const route = useRoute()
const router = useRouter()
const sessionId = ref(parseInt(route.query.sessionId) || 0)

const maxQuestions = 42
const currentIndex = ref(0)
const questions = ref([])
const answersMap = ref({})
const currentQuestion = ref({ id: '', content: '正在加载题目...', options: [] })
const startTime = ref(0)
const anomalyTriggered = ref(false)
const userExplanation = ref('')
const isFinished = ref(false)
const isGenerating = ref(false)
const isSubmittingAll = ref(false)
const finalReport = ref('')
const debateMessages = ref([])
const debateError = ref('')
const debateFeedRef = ref(null)
const debateCollapsed = ref(false)
const hasStarted = ref(false)
const isStarting = ref(false)
const startError = ref('')
const isAdaptive = ref(true)
const currentModule = ref(null)
const questionStats = ref(null)

watch(() => debateMessages.value.length, () => {
  nextTick(() => {
    if (debateFeedRef.value) {
      debateFeedRef.value.scrollTop = debateFeedRef.value.scrollHeight
    }
  })
})

const getAgentAvatar = (name) => {
  if (name.includes('Proponent')) return '👨‍⚖️'
  if (name.includes('Opponent')) return '🧑‍⚖️'
  if (name.includes('Judge')) return '👩‍⚖️'
  return '👤'
}

const agentClass = (name) => {
  if (name.includes('Proponent')) return 'proponent'
  if (name.includes('Opponent')) return 'opponent'
  if (name.includes('Judge')) return 'judge'
  return 'admin'
}

const formatAgentName = (name) => {
  if (name.includes('Proponent')) return '正方专家'
  if (name.includes('Opponent')) return '反方专家'
  if (name.includes('Judge')) return '裁决专家'
  return name
}

const currentAnswer = computed(() => answersMap.value[currentQuestion.value.id] || null)
const answeredCount = computed(() => Object.keys(answersMap.value).length)
const canGoNext = computed(() => !!currentAnswer.value && (!anomalyTriggered.value || !!(currentAnswer.value.user_explanation || userExplanation.value.trim())))
const canSubmitAll = computed(() => answeredCount.value === maxQuestions && !anomalyTriggered.value)

const getCurrentModule = () => {
  if (currentIndex.value < 2) return null
  const moduleIndex = Math.floor((currentIndex.value - 2) / 10)
  const modules = ['A', 'T', 'M', 'R']
  return moduleIndex < modules.length ? modules[moduleIndex] : modules[modules.length - 1]
}

const buildAdaptiveAnswerSnapshot = () => {
  const orderedIds = questions.value.map((question) => question?.id).filter(Boolean)
  const remainingIds = Object.keys(answersMap.value).filter((id) => !orderedIds.includes(id))
  return [...orderedIds, ...remainingIds]
    .map((id) => answersMap.value[id])
    .filter((answer) => answer && answer.selected_option)
    .map((answer) => ({
      exam_no: answer.exam_no,
      selected_option: answer.selected_option,
      time_spent: answer.time_spent,
      score: answer.score,
      status: answer.status,
      user_explanation: answer.user_explanation || null,
    }))
}

const loadQuestionAtIndex = async (index) => {
  if (questions.value[index]) {
    currentQuestion.value = questions.value[index]
    restoreCurrentState()
    return
  }

  currentModule.value = getCurrentModule()
  try {
    const res = await api.post('/assessment/adaptive-question', {
      session_id: sessionId.value,
      module: currentModule.value,
      answers: buildAdaptiveAnswerSnapshot(),
    })

    const q = {
      id: res.data.examNo,
      content: res.data.exam,
      options: res.data.options,
    }
    questions.value[index] = q
    currentQuestion.value = q
    isAdaptive.value = res.data.is_adaptive !== false
    questionStats.value = res.data.question_stats || null
  } catch (error) {
    const fallbackRes = await api.get(`/assessment/question/${index}`)
    const q = {
      id: fallbackRes.data.examNo,
      content: fallbackRes.data.exam,
      options: fallbackRes.data.options,
    }
    questions.value[index] = q
    currentQuestion.value = q
    isAdaptive.value = false
    questionStats.value = null
  }

  startTime.value = Date.now()
  restoreCurrentState()
}

const restoreCurrentState = () => {
  const answer = answersMap.value[currentQuestion.value.id]
  anomalyTriggered.value = !!(answer && answer.status === 'anomaly' && !answer.user_explanation)
  userExplanation.value = answer?.user_explanation || ''
  startTime.value = Date.now()
}

const selectOption = async (option) => {
  const timeSpentSeconds = parseFloat(((Date.now() - startTime.value) / 1000).toFixed(2))
  try {
    const res = await api.post('/assessment/check-answer', {
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
    })

    answersMap.value[currentQuestion.value.id] = {
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
      status: res.data.status,
      score: res.data.score,
      follow_up_question: res.data.follow_up_question,
      user_explanation: answersMap.value[currentQuestion.value.id]?.user_explanation || '',
    }

    userExplanation.value = answersMap.value[currentQuestion.value.id].user_explanation || ''
    anomalyTriggered.value = res.data.status === 'anomaly' && !answersMap.value[currentQuestion.value.id].user_explanation
  } catch (error) {
    console.error('检测答案失败:', error)
    alert('检测失败，请检查后端服务')
  }
}

const submitExplanation = () => {
  const answer = answersMap.value[currentQuestion.value.id]
  if (!answer) return
  answersMap.value[currentQuestion.value.id] = {
    ...answer,
    user_explanation: userExplanation.value,
  }
  anomalyTriggered.value = false
}

const nextQuestion = async () => {
  if (!canGoNext.value) return
  if (currentIndex.value + 1 < maxQuestions) {
    currentIndex.value++
    await loadQuestionAtIndex(currentIndex.value)
  }
}

const prevQuestion = async () => {
  if (currentIndex.value === 0) return
  currentIndex.value--
  await loadQuestionAtIndex(currentIndex.value)
}

const startDebateStream = () => {
  isFinished.value = true
  isGenerating.value = true
  debateMessages.value = []
  debateError.value = ''

  const token = localStorage.getItem('token')
  const evtSource = new EventSource(`${API_BASE}/finish-stream?session_id=${sessionId.value}&token=${token}`)

  evtSource.addEventListener('agent_message', (e) => {
    const data = JSON.parse(e.data)
    debateMessages.value.push({ agent: data.agent, content: data.content })
  })

  evtSource.addEventListener('debate_complete', (e) => {
    const data = JSON.parse(e.data)
    finalReport.value = data.report
    isGenerating.value = false
    debateCollapsed.value = true
    evtSource.close()
  })

  evtSource.addEventListener('error', () => {
    if (isGenerating.value) {
      debateError.value = '与服务器的连接已断开，请检查后端服务是否正常运行'
      isGenerating.value = false
    }
    evtSource.close()
  })
}

const submitAllAnswers = async () => {
  if (!canSubmitAll.value) return
  isSubmittingAll.value = true
  try {
    const orderedAnswers = questions.value.map((q) => ({
      exam_no: q.id,
      selected_option: answersMap.value[q.id].selected_option,
      time_spent: answersMap.value[q.id].time_spent,
      user_explanation: answersMap.value[q.id].user_explanation || null,
    }))

    await api.post('/assessment/submit-batch', {
      session_id: sessionId.value,
      answers: orderedAnswers,
    })

    startDebateStream()
  } catch (error) {
    console.error('最终提交失败:', error)
    alert(error.response?.data?.detail || '提交失败，请稍后重试')
  } finally {
    isSubmittingAll.value = false
  }
}

const restartTest = () => {
  router.push('/history')
}

const formattedReport = computed(() => {
  if (!finalReport.value) return ''
  const cleaned = finalReport.value.replace(/【内部记录[：:].*?】/g, '').replace(/\s*TERMINATE\s*/g, '').replace(/\n{3,}/g, '\n\n').trim()
  return marked.parse(cleaned)
})

const startNewSession = async () => {
  isStarting.value = true
  startError.value = ''
  try {
    const res = await api.post('/assessment/start-session', {})
    sessionId.value = res.data.session_id
    hasStarted.value = true
    currentIndex.value = 0
    questions.value = []
    answersMap.value = {}
    isFinished.value = false
    finalReport.value = ''
    debateMessages.value = []
    router.replace({ query: { ...route.query, sessionId: sessionId.value } })
    await loadQuestionAtIndex(0)
  } catch (error) {
    startError.value = error.response?.data?.detail || '网络错误，请检查后端服务'
  } finally {
    isStarting.value = false
  }
}

onMounted(() => {
  hasStarted.value = false
})
</script>

<style scoped>
.assessment-container { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }
.start-page { display: flex; justify-content: center; align-items: center; min-height: 70vh; }
.start-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 24px; padding: 60px 48px; box-shadow: var(--shadow); text-align: center; max-width: 500px; width: 100%; }
.start-icon { font-size: 64px; margin-bottom: 24px; }
.start-title { font-size: 32px; font-weight: 800; color: var(--text-primary); margin: 0 0 16px 0; }
.start-description { font-size: 16px; color: var(--text-secondary); line-height: 1.8; margin-bottom: 32px; }
.start-features { display: flex; justify-content: center; gap: 24px; margin-bottom: 40px; }
.feature-item { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 14px; }
.feature-icon { font-size: 28px; }
.start-btn { width: 100%; padding: 16px 32px; background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.start-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4); }
.start-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; }
.start-error { margin-top: 16px; color: var(--error); font-size: 14px; }
.question-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 24px; padding: 36px; box-shadow: var(--shadow); }
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; gap: 20px; }
.progress-info { flex: 1; }
.progress-text { display: block; font-size: 14px; color: var(--text-secondary); margin-bottom: 12px; }
.progress-bar { width: 100%; height: 8px; background: var(--bg-dark); border-radius: 4px; overflow: hidden; margin-top: 12px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--secondary)); transition: width 0.3s; }
.progress-percent { display: inline-block; margin-top: 8px; font-size: 13px; color: var(--primary-light); font-weight: 600; }
.adaptive-badge, .sequential-badge, .module-badge { display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-right: 8px; }
.adaptive-badge { background: rgba(99, 102, 241, 0.15); color: var(--primary-light); }
.sequential-badge { background: rgba(16, 185, 129, 0.15); color: var(--success); }
.module-badge { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
.stats-grid { display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap; }
.stat-item { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; background: var(--bg-dark); border-radius: 10px; font-size: 12px; }
.stat-label { color: var(--text-secondary); }
.stat-value { color: var(--text-primary); font-weight: 600; }
.question-content { margin-bottom: 32px; }
.question-title { font-size: 28px; font-weight: 700; color: var(--text-primary); line-height: 1.5; }
.options-container { display: flex; flex-direction: column; gap: 14px; }
.option-btn { display: flex; align-items: center; gap: 16px; width: 100%; padding: 20px; background: var(--bg-dark); border: 1px solid var(--border); border-radius: 14px; cursor: pointer; transition: all 0.2s; text-align: left; }
.option-btn:hover, .option-btn.selected { border-color: var(--primary); background: rgba(99,102,241,0.08); }
.option-label { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; background: var(--primary); color: white; border-radius: 50%; font-weight: 700; flex-shrink: 0; }
.option-text { color: var(--text-primary); font-size: 15px; line-height: 1.5; }
.anomaly-container { margin-top: 24px; }
.warning-box { display: flex; gap: 12px; align-items: flex-start; padding: 16px; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245,158,11,0.3); border-radius: 12px; margin-bottom: 16px; }
.warning-icon { color: var(--warning); font-size: 20px; }
textarea { width: 100%; padding: 14px; background: var(--bg-dark); border: 1px solid var(--border); border-radius: 12px; color: var(--text-primary); resize: vertical; box-sizing: border-box; }
.submit-explanation-btn, .nav-btn { margin-top: 14px; padding: 12px 20px; border: none; border-radius: 12px; cursor: pointer; font-weight: 600; }
.navigation-actions { display: flex; justify-content: space-between; gap: 12px; margin-top: 24px; }
.nav-btn { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; }
.nav-btn.secondary { background: var(--bg-dark); color: var(--text-primary); border: 1px solid var(--border); }
.nav-btn.submit-final { background: linear-gradient(135deg, var(--success), #16a34a); }
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.result-page { display: flex; flex-direction: column; gap: 24px; }
.debate-section, .report-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 24px; box-shadow: var(--shadow); overflow: hidden; }
.debate-header, .report-header { padding: 28px 32px; }
.debate-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.debate-title, .report-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 0 0 8px 0; }
.debate-subtitle, .report-subtitle { color: var(--text-secondary); margin: 0; }
.debate-done-badge, .debate-live-badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; margin-left: 10px; }
.debate-done-badge { background: rgba(34,197,94,0.15); color: var(--success); }
.debate-live-badge { background: rgba(245,158,11,0.15); color: var(--warning); }
.collapse-toggle { color: var(--primary-light); font-size: 14px; }
.debate-feed { max-height: 520px; overflow-y: auto; padding: 0 32px 32px; }
.debate-msg { padding: 18px 20px; border-radius: 16px; margin-bottom: 16px; }
.debate-msg.proponent { background: rgba(99,102,241,0.08); }
.debate-msg.opponent { background: rgba(6,182,212,0.08); }
.debate-msg.judge { background: rgba(245,158,11,0.08); }
.msg-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.agent-name { font-weight: 600; color: var(--text-primary); }
.msg-content { color: var(--text-secondary); line-height: 1.8; white-space: pre-wrap; }
.waiting-hint { text-align: center; padding: 48px 0; color: var(--text-secondary); }
.loader-spinner { width: 42px; height: 42px; border: 3px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
.loader-small { width: 28px; height: 28px; margin-top: 12px; }
.error-text { color: var(--error); padding: 0 32px 24px; }
.report-divider { height: 1px; background: var(--border); }
.report-content { padding: 32px; color: var(--text-primary); line-height: 1.9; }
.report-actions { display: flex; gap: 12px; padding: 0 32px 32px; }
.restart-btn { padding: 12px 20px; border: none; border-radius: 12px; background: var(--bg-dark); color: var(--text-primary); cursor: pointer; }
.view-report-btn { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
