<template>
  <div class="assessment-container">
    <div v-if="isCheckingResume" class="start-page">
      <div class="start-card">
        <div class="start-icon"><span class="btn-spinner"></span></div>
        <p class="start-description">正在检查测评进度...</p>
      </div>
    </div>

    <div v-else-if="!hasStarted" class="start-page">
      <div class="start-card">
        <div class="start-icon">📝</div>
        <h1 class="start-title">ATMR 心理测评</h1>
        <p class="start-description">
          本测评包含 42 道题目，预计用时 10-15 分钟<br>
          系统将智能选择最适合您的题目
        </p>
        <div class="start-features">
          <div class="feature-item"><span class="feature-icon">✨</span><span>智能选题</span></div>
          <div class="feature-item"><span class="feature-icon">🔍</span><span>异常检测</span></div>
          <div class="feature-item"><span class="feature-icon">👥</span><span>专家辩论</span></div>
        </div>
        <div v-if="pendingResume" class="resume-section">
          <p class="resume-hint">您有一份未完成的测评（已完成 {{ pendingResume.answered_count }}/{{ maxQuestions }} 题）</p>
          <button class="start-btn resume-btn" @click="resumeSession" :disabled="isStarting">
            继续测评
          </button>
          <button class="start-btn restart-new-btn" @click="startNewSession" :disabled="isStarting">
            <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
            <span v-else>重新开始</span>
          </button>
        </div>
        <div v-else>
          <button class="start-btn" @click="startNewSession" :disabled="isStarting">
            <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
            <span v-else>开始测评</span>
          </button>
        </div>
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
        <div v-if="currentModule" class="module-info">
          <span class="module-badge">模块 {{ currentModule }}</span>
        </div>
      </div>

      <div class="question-nav-toggle" @click="showQuestionNav = !showQuestionNav">
        <span>{{ showQuestionNav ? '收起题目列表' : '展开题目列表' }}</span>
        <span class="toggle-arrow">{{ showQuestionNav ? '▲' : '▼' }}</span>
      </div>
      <div v-if="showQuestionNav" class="question-nav-grid">
        <button
          v-for="i in maxQuestions" :key="i"
          :class="['qnav-item', {
            current: currentIndex === i - 1,
            answered: questions[i - 1] && answersMap[questions[i - 1]?.id],
            locked: !questions[i - 1]
          }]"
          @click="jumpToQuestion(i - 1)"
          :disabled="!questions[i - 1]"
        >{{ i }}</button>
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

      <div v-if="moduleSubmitInfo" class="module-submit-bar">
        <div class="module-submit-info">
          <span class="module-submit-label">模块 {{ moduleSubmitInfo.module }} 已答完</span>
          <span v-if="moduleSubmitInfo.submitted" class="module-submit-status">辩论已启动</span>
        </div>
        <button
          class="module-submit-btn"
          :disabled="moduleSubmitInfo.cooling || isSubmittingModule"
          @click="submitModule(moduleSubmitInfo.module)"
        >
          <span v-if="isSubmittingModule"><span class="btn-spinner"></span></span>
          <span v-else-if="moduleSubmitInfo.cooling">冷却中 ({{ moduleCooldownRemaining }}s)</span>
          <span v-else-if="moduleSubmitInfo.submitted">重新提交 {{ moduleSubmitInfo.module }} 模块</span>
          <span v-else>提交 {{ moduleSubmitInfo.module }} 模块</span>
        </button>
      </div>

      <div class="navigation-actions">
        <button class="nav-btn secondary" @click="prevQuestion" :disabled="currentIndex === 0">上一题</button>
        <button class="nav-btn" v-if="currentIndex < maxQuestions - 1" @click="nextQuestion" :disabled="!canGoNext">下一题</button>
        <button class="nav-btn submit-final" v-if="currentIndex === maxQuestions - 1" @click="submitAllAnswers" :disabled="!canSubmitAll || isSubmittingAll">
          {{ isSubmittingAll ? '提交中...' : (isEditMode ? '重新提交' : '提交答卷') }}
        </button>
        <button class="nav-btn submit-final" v-else-if="isEditMode && canSubmitAll" @click="submitAllAnswers" :disabled="isSubmittingAll">
          {{ isSubmittingAll ? '提交中...' : '重新提交' }}
        </button>
      </div>
    </div>

    <div v-else class="result-page">
      <div v-if="isGenerating" class="debate-loading-section">
        <div class="debate-loading-card">
          <div class="orbit-container">
            <div class="orbit-ring ring-1"></div>
            <div class="orbit-ring ring-2"></div>
            <div class="orbit-ring ring-3"></div>
            <div class="orbit-dot dot-1"></div>
            <div class="orbit-dot dot-2"></div>
            <div class="orbit-dot dot-3"></div>
            <div class="orbit-center-icon">✨</div>
          </div>
          <h2 class="debate-loading-title">专家辩论中</h2>
          <p class="debate-loading-subtitle">多位 AI 专家正在深入分析您的测评数据</p>
          <div class="debate-loading-steps">
            <div :class="['step-item', { active: debateMessages.length === 0 }]">
              <span class="step-dot"></span><span>唤醒评审团</span>
            </div>
            <div :class="['step-item', { active: debateMessages.length > 0 && debateMessages.length <= 2 }]">
              <span class="step-dot"></span><span>正反方交锋</span>
            </div>
            <div :class="['step-item', { active: debateMessages.length > 2 }]">
              <span class="step-dot"></span><span>裁决与生成报告</span>
            </div>
          </div>
          <p v-if="debateError" class="error-text">{{ debateError }}</p>
        </div>
      </div>

      <div v-else class="report-section">
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

const API_BASE = '/api/v1/assessment'
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
const isCheckingResume = ref(true)
const pendingResume = ref(null)
const isEditMode = ref(false)
const isAdaptive = ref(true)
const currentModule = ref(null)
const questionStats = ref(null)
const showQuestionNav = ref(false)
const isSubmittingModule = ref(false)
const moduleSubmitTimes = ref({})  // { A: timestamp, T: timestamp, ... }
const moduleCooldownRemaining = ref(0)
let cooldownTimer = null

// 模块边界定义：索引 2-11=A, 12-21=T, 22-31=M, 32-41=R
const MODULE_RANGES = { A: [2, 11], T: [12, 21], M: [22, 31], R: [32, 41] }
const MODULE_COOLDOWN = 30

const getModuleForIndex = (idx) => {
  for (const [mod, [start, end]] of Object.entries(MODULE_RANGES)) {
    if (idx >= start && idx <= end) return mod
  }
  return null
}

const isModuleComplete = (mod) => {
  const [start, end] = MODULE_RANGES[mod]
  for (let i = start; i <= end; i++) {
    const q = questions.value[i]
    if (!q || !answersMap.value[q.id]) return false
  }
  return true
}

const moduleSubmitInfo = computed(() => {
  // 判断当前位置所在的模块
  const mod = getModuleForIndex(currentIndex.value)
  if (!mod || !isModuleComplete(mod)) return null

  const submitTime = moduleSubmitTimes.value[mod]
  const submitted = !!submitTime
  const cooling = submitted && (Date.now() - submitTime) < MODULE_COOLDOWN * 1000

  return { module: mod, submitted, cooling }
})

const startCooldownTimer = (mod) => {
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    const submitTime = moduleSubmitTimes.value[mod]
    if (!submitTime) { clearInterval(cooldownTimer); return }
    const remaining = Math.ceil(MODULE_COOLDOWN - (Date.now() - submitTime) / 1000)
    if (remaining <= 0) {
      moduleCooldownRemaining.value = 0
      clearInterval(cooldownTimer)
    } else {
      moduleCooldownRemaining.value = remaining
    }
  }, 1000)
}

const submitModule = async (mod) => {
  isSubmittingModule.value = true
  try {
    await api.post('/assessment/submit-module', {
      session_id: sessionId.value,
      module: mod,
    })
    moduleSubmitTimes.value[mod] = Date.now()
    moduleCooldownRemaining.value = MODULE_COOLDOWN
    startCooldownTimer(mod)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 429) {
      // 从错误消息提取剩余时间
      const match = detail?.match(/(\d+)/)
      if (match) {
        moduleSubmitTimes.value[mod] = Date.now() - (MODULE_COOLDOWN - parseInt(match[1])) * 1000
        moduleCooldownRemaining.value = parseInt(match[1])
        startCooldownTimer(mod)
      }
    } else {
      alert(detail || '模块提交失败')
    }
  } finally {
    isSubmittingModule.value = false
  }
}

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
    const isAnomaly = res.data.status === 'anomaly' && !answersMap.value[currentQuestion.value.id].user_explanation
    anomalyTriggered.value = isAnomaly

    // 实时保存到后端（fire-and-forget）
    api.post('/assessment/save-answer', {
      session_id: sessionId.value,
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
      score: res.data.score,
      is_anomaly: isAnomaly ? 1 : 0,
      ai_follow_up: res.data.follow_up_question || null,
      user_explanation: answersMap.value[currentQuestion.value.id]?.user_explanation || null,
    }).catch(err => console.warn('草稿保存失败:', err))

    // 非异常情况下自动跳转下一题
    if (!isAnomaly && currentIndex.value + 1 < maxQuestions) {
      setTimeout(() => {
        nextQuestion()
      }, 300)
    }
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

  // 同步解释到后端
  api.post('/assessment/save-answer', {
    session_id: sessionId.value,
    exam_no: currentQuestion.value.id,
    selected_option: answer.selected_option,
    time_spent: answer.time_spent,
    score: answer.score,
    is_anomaly: 1,
    ai_follow_up: answer.follow_up_question || null,
    user_explanation: userExplanation.value,
  }).catch(err => console.warn('解释保存失败:', err))
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

const jumpToQuestion = async (index) => {
  if (!questions.value[index]) return
  currentIndex.value = index
  currentQuestion.value = questions.value[index]
  currentModule.value = getModuleForIndex(index) || getCurrentModule()
  restoreCurrentState()
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
    evtSource.close()
    // 如果已经收到了辩论结果（isGenerating 已被 debate_complete 设为 false），不报错
    if (isGenerating.value) {
      // 如果已经收到过消息，说明连接中途断了或服务端处理完关闭了连接
      if (debateMessages.value.length > 0) {
        // 给后端一点时间，可能 debate_complete 还没到就断了
        debateError.value = '辩论过程连接中断，请刷新重试或查看历史报告'
      } else {
        debateError.value = '无法连接到辩论服务，请检查后端服务是否正常运行'
      }
      isGenerating.value = false
    }
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

const resumeSession = async () => {
  const data = pendingResume.value
  if (!data) return
  isStarting.value = true
  try {
    sessionId.value = data.session_id
    hasStarted.value = true

    // 恢复 questions 和 answersMap
    data.questions.forEach((q, i) => {
      questions.value[i] = { id: q.examNo, content: q.exam, options: q.options }
    })
    data.answers.forEach(a => {
      answersMap.value[a.exam_no] = {
        exam_no: a.exam_no,
        selected_option: a.selected_option,
        time_spent: a.time_spent,
        score: a.score,
        status: a.is_anomaly ? 'anomaly' : 'normal',
        follow_up_question: a.ai_follow_up || null,
        user_explanation: a.user_explanation || '',
      }
    })

    // 跳转到第一道未答的题
    currentIndex.value = data.answered_count
    router.replace({ query: { ...route.query, sessionId: sessionId.value } })
    await loadQuestionAtIndex(currentIndex.value)
  } catch (error) {
    startError.value = '恢复会话失败，请重新开始'
    hasStarted.value = false
  } finally {
    isStarting.value = false
  }
}

onMounted(async () => {
  const mode = route.query.mode
  const querySid = parseInt(route.query.sessionId) || 0

  // 编辑模式：从历史记录点击"修改答案"进入
  if (mode === 'edit' && querySid) {
    isCheckingResume.value = true
    isEditMode.value = true
    try {
      const res = await api.get('/assessment/resume-session')
      if (res.data.has_active_session && res.data.session_id === querySid) {
        sessionId.value = res.data.session_id
        hasStarted.value = true

        res.data.questions.forEach((q, i) => {
          questions.value[i] = { id: q.examNo, content: q.exam, options: q.options }
        })
        res.data.answers.forEach(a => {
          answersMap.value[a.exam_no] = {
            exam_no: a.exam_no,
            selected_option: a.selected_option,
            time_spent: a.time_spent,
            score: a.score,
            status: a.is_anomaly ? 'anomaly' : 'normal',
            follow_up_question: a.ai_follow_up || null,
            user_explanation: a.user_explanation || '',
          }
        })

        currentIndex.value = 0
        currentQuestion.value = questions.value[0]
        restoreCurrentState()
      } else {
        startError.value = '会话数据加载失败'
        hasStarted.value = false
      }
    } catch (err) {
      startError.value = '加载编辑模式失败'
      hasStarted.value = false
    } finally {
      isCheckingResume.value = false
    }
    return
  }

  // 正常模式：检查是否有未完成会话
  isCheckingResume.value = true
  try {
    const res = await api.get('/assessment/resume-session')
    if (res.data.has_active_session) {
      pendingResume.value = res.data
    }
  } catch (err) {
    console.warn('检查未完成会话失败:', err)
  } finally {
    isCheckingResume.value = false
    hasStarted.value = false
  }
})
</script>

<style scoped>
/* === 容器 === */
.assessment-container { width: 100%; max-width: 1400px; margin: 0 auto; padding: 40px 32px; }

/* === 开始页 === */
.start-page { display: flex; justify-content: center; align-items: center; min-height: 70vh; }
.start-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 28px; padding: 64px 56px; box-shadow: var(--shadow-lg); text-align: center; max-width: 680px; width: 100%; }
.start-icon { font-size: 72px; margin-bottom: 28px; }
.start-title { font-size: 38px; font-weight: 800; color: var(--text-primary); margin: 0 0 20px 0; }
.start-description { font-size: 18px; color: var(--text-secondary); line-height: 1.9; margin-bottom: 36px; }
.start-features { display: flex; justify-content: center; gap: 32px; margin-bottom: 44px; }
.feature-item { display: flex; flex-direction: column; align-items: center; gap: 10px; color: var(--text-secondary); font-size: 16px; font-weight: 500; }
.feature-icon { font-size: 36px; }
.start-btn { width: 100%; padding: 20px 40px; background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; border: none; border-radius: 14px; font-size: 20px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.start-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(99, 102, 241, 0.4); }
.start-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 10px; vertical-align: middle; }
.start-error { margin-top: 18px; color: var(--error); font-size: 16px; }
.resume-section { display: flex; flex-direction: column; gap: 14px; }
.resume-hint { font-size: 17px; color: var(--primary-light); font-weight: 600; margin-bottom: 8px; }
.resume-btn { background: linear-gradient(135deg, var(--success), #16a34a); }
.resume-btn:hover:not(:disabled) { box-shadow: 0 10px 28px rgba(34, 197, 94, 0.4); }
.restart-new-btn { background: var(--bg-dark); color: var(--text-primary); border: 2px solid var(--border); }
.restart-new-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); transform: translateY(-2px); box-shadow: none; }

/* === 答题卡片 === */
.question-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 28px;
  padding: 48px 56px; box-shadow: var(--shadow-lg); min-height: 520px;
  display: flex; flex-direction: column;
}

/* === 头部进度 === */
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; gap: 24px; }
.progress-info { flex: 1; }
.progress-text { display: block; font-size: 18px; color: var(--text-secondary); margin-bottom: 14px; font-weight: 500; }
.progress-bar { width: 100%; height: 10px; background: var(--bg-dark); border-radius: 5px; overflow: hidden; margin-top: 14px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--secondary)); transition: width 0.3s; border-radius: 5px; }
.progress-percent { display: inline-block; margin-top: 10px; font-size: 16px; color: var(--primary-light); font-weight: 700; }
.adaptive-badge, .sequential-badge, .module-badge { display: inline-block; padding: 8px 16px; border-radius: 24px; font-size: 14px; font-weight: 600; margin-right: 8px; }
.adaptive-badge { background: rgba(99, 102, 241, 0.15); color: var(--primary-light); }
.sequential-badge { background: rgba(16, 185, 129, 0.15); color: var(--success); }
.module-badge { background: rgba(245, 158, 11, 0.15); color: var(--warning); }

/* === 题目导航列表 === */
.question-nav-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 18px; margin-bottom: 16px; cursor: pointer;
  background: var(--bg-dark); border: 1px solid var(--border); border-radius: 12px;
  font-size: 15px; color: var(--text-secondary); font-weight: 500; transition: all 0.2s;
}
.question-nav-toggle:hover { border-color: var(--primary); color: var(--primary-light); }
.toggle-arrow { font-size: 12px; }
.question-nav-grid {
  display: grid; grid-template-columns: repeat(14, 1fr); gap: 8px;
  padding: 16px; margin-bottom: 20px;
  background: var(--bg-dark); border: 1px solid var(--border); border-radius: 14px;
}
.qnav-item {
  width: 100%; aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  border: 2px solid var(--border); border-radius: 8px; background: transparent;
  color: var(--text-secondary); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s;
}
.qnav-item:hover:not(:disabled) { border-color: var(--primary); color: var(--primary-light); }
.qnav-item.current { border-color: var(--primary); background: var(--primary); color: white; }
.qnav-item.answered:not(.current) { border-color: var(--success); color: var(--success); background: rgba(34, 197, 94, 0.1); }
.qnav-item.locked { opacity: 0.3; cursor: not-allowed; }

/* === 题目内容 === */
.question-content { margin-bottom: 40px; flex-shrink: 0; }
.question-title { font-size: 32px; font-weight: 700; color: var(--text-primary); line-height: 1.6; }

/* === 选项 === */
.options-container { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.option-btn {
  display: flex; align-items: center; gap: 20px; width: 100%;
  padding: 24px 28px; background: var(--bg-dark); border: 2px solid var(--border);
  border-radius: 16px; cursor: pointer; transition: all 0.2s; text-align: left;
}
.option-btn:hover { border-color: var(--primary); background: rgba(99,102,241,0.06); transform: translateX(4px); }
.option-btn.selected { border-color: var(--primary); background: rgba(99,102,241,0.1); box-shadow: 0 4px 16px rgba(99,102,241,0.15); }
.option-label {
  display: flex; align-items: center; justify-content: center;
  width: 48px; height: 48px; background: var(--primary); color: white;
  border-radius: 50%; font-weight: 700; font-size: 20px; flex-shrink: 0;
}
.option-text { color: var(--text-primary); font-size: 19px; line-height: 1.6; font-weight: 500; }

/* === 异常追问 === */
.anomaly-container { margin-top: 28px; }
.warning-box { display: flex; gap: 14px; align-items: flex-start; padding: 20px 24px; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245,158,11,0.3); border-radius: 14px; margin-bottom: 20px; font-size: 17px; line-height: 1.7; }
.warning-icon { color: var(--warning); font-size: 24px; }
textarea { width: 100%; padding: 18px; background: var(--bg-dark); border: 1px solid var(--border); border-radius: 14px; color: var(--text-primary); font-size: 17px; resize: vertical; box-sizing: border-box; line-height: 1.6; }
.submit-explanation-btn { margin-top: 16px; padding: 16px 28px; border: none; border-radius: 14px; cursor: pointer; font-weight: 600; font-size: 17px; background: linear-gradient(135deg, var(--warning), #d97706); color: white; }

/* === 模块提交栏 === */
.module-submit-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 24px; margin-top: 24px;
  background: rgba(99, 102, 241, 0.06); border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 14px;
}
.module-submit-info { display: flex; flex-direction: column; gap: 4px; }
.module-submit-label { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.module-submit-status { font-size: 14px; color: var(--success); font-weight: 500; }
.module-submit-btn {
  padding: 14px 28px; border: none; border-radius: 12px; cursor: pointer;
  font-weight: 600; font-size: 16px; transition: all 0.2s;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white;
}
.module-submit-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3); }
.module-submit-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* === 导航按钮 === */
.navigation-actions { display: flex; justify-content: space-between; gap: 16px; margin-top: 36px; flex-shrink: 0; }
.nav-btn {
  padding: 18px 36px; border: none; border-radius: 14px; cursor: pointer;
  font-weight: 600; font-size: 18px; transition: all 0.2s;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white;
}
.nav-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3); }
.nav-btn.secondary { background: var(--bg-dark); color: var(--text-primary); border: 2px solid var(--border); }
.nav-btn.secondary:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.nav-btn.submit-final { background: linear-gradient(135deg, var(--success), #16a34a); padding: 18px 48px; }
.nav-btn.submit-final:hover:not(:disabled) { box-shadow: 0 8px 20px rgba(34, 197, 94, 0.3); }
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* === 结果页 === */
.result-page { display: flex; flex-direction: column; gap: 28px; }
.report-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 28px; box-shadow: var(--shadow-lg); overflow: hidden; }
.report-header { padding: 32px 40px; }
.report-title { font-size: 28px; font-weight: 700; color: var(--text-primary); margin: 0 0 10px 0; }
.report-subtitle { color: var(--text-secondary); margin: 0; font-size: 17px; }
.report-divider { height: 1px; background: var(--border); }
.report-content { padding: 40px; color: var(--text-primary); line-height: 2; font-size: 18px; }
.report-actions { display: flex; gap: 16px; padding: 0 40px 36px; }
.restart-btn { padding: 16px 28px; border: none; border-radius: 14px; background: var(--bg-dark); color: var(--text-primary); cursor: pointer; font-size: 17px; font-weight: 600; transition: all 0.2s; }
.restart-btn:hover { background: var(--border); }
.view-report-btn { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; }
.view-report-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3); }
.error-text { color: var(--error); padding: 16px 0 0; font-size: 16px; text-align: center; }

/* === 辩论加载动画 === */
.debate-loading-section { display: flex; justify-content: center; align-items: center; min-height: 60vh; }
.debate-loading-card { text-align: center; padding: 60px 48px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 28px; box-shadow: var(--shadow-lg); max-width: 520px; width: 100%; }
.debate-loading-title { font-size: 32px; font-weight: 800; color: var(--text-primary); margin: 32px 0 12px; }
.debate-loading-subtitle { font-size: 17px; color: var(--text-secondary); margin: 0 0 40px; line-height: 1.7; }

/* 轨道动画 */
.orbit-container { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.orbit-ring {
  position: absolute; inset: 0; border-radius: 50%; border: 2px solid transparent;
}
.orbit-ring.ring-1 { border-top-color: var(--primary); animation: orbit-spin 3s linear infinite; }
.orbit-ring.ring-2 { inset: 16px; border-right-color: var(--secondary, #06b6d4); animation: orbit-spin 2.5s linear infinite reverse; }
.orbit-ring.ring-3 { inset: 32px; border-bottom-color: var(--warning); animation: orbit-spin 2s linear infinite; }
.orbit-dot {
  position: absolute; width: 12px; height: 12px; border-radius: 50%;
}
.orbit-dot.dot-1 { background: var(--primary); top: -6px; left: 50%; transform: translateX(-50%); animation: orbit-spin 3s linear infinite; transform-origin: 50% 86px; }
.orbit-dot.dot-2 { background: var(--secondary, #06b6d4); top: 50%; right: 10px; animation: orbit-spin 2.5s linear infinite reverse; transform-origin: -54px 50%; }
.orbit-dot.dot-3 { background: var(--warning); bottom: 26px; left: 26px; animation: orbit-spin 2s linear infinite; transform-origin: 54px -22px; }
.orbit-center-icon {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  font-size: 48px; animation: pulse-glow 2s ease-in-out infinite;
}

/* 步骤指示器 */
.debate-loading-steps { display: flex; flex-direction: column; gap: 16px; align-items: flex-start; margin: 0 auto; max-width: 240px; }
.step-item { display: flex; align-items: center; gap: 14px; font-size: 16px; color: var(--text-secondary); font-weight: 500; transition: all 0.3s; }
.step-item.active { color: var(--primary-light); font-weight: 700; }
.step-dot {
  width: 10px; height: 10px; border-radius: 50%; background: var(--border); flex-shrink: 0; transition: all 0.3s;
}
.step-item.active .step-dot { background: var(--primary); box-shadow: 0 0 12px rgba(99, 102, 241, 0.6); animation: pulse-dot 1.5s ease-in-out infinite; }

@keyframes orbit-spin { to { transform: rotate(360deg); } }
@keyframes pulse-glow { 0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; } 50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.8; } }
@keyframes pulse-dot { 0%, 100% { box-shadow: 0 0 6px rgba(99, 102, 241, 0.4); } 50% { box-shadow: 0 0 18px rgba(99, 102, 241, 0.8); } }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
