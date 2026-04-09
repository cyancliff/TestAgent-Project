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
          <div class="feature-item"><span class="feature-icon">✨</span><span>智能选题</span></div>
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
        <div v-if="currentModule" class="module-info">
          <span class="module-badge">模块 {{ currentModule }}</span>
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
    const isAnomaly = res.data.status === 'anomaly' && !answersMap.value[currentQuestion.value.id].user_explanation
    anomalyTriggered.value = isAnomaly

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

onMounted(() => {
  hasStarted.value = false
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
