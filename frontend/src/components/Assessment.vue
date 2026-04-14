<template>
  <div class="assessment-container">
    <!-- 加载中检查 -->
    <div v-if="isCheckingResume" class="start-page">
      <div class="start-card">
        <div class="start-icon"><span class="btn-spinner"></span></div>
        <p class="start-description">正在检查测评进度...</p>
      </div>
    </div>

    <!-- 开始页 -->
    <div v-else-if="!hasStarted" class="start-page">
      <div class="start-card">
        <div class="start-icon">📝</div>
        <h1 class="start-title">ATMR 心理测评</h1>
        <p class="start-description">
          本测评分为五个阶段，每阶段完成后进入专家评审<br>
          预计总用时 15-20 分钟
        </p>
        <div class="start-features">
          <div class="feature-item"><span class="feature-icon">📖</span><span>序章引导</span></div>
          <div class="feature-item"><span class="feature-icon">🔮</span><span>智能选题</span></div>
          <div class="feature-item"><span class="feature-icon">👥</span><span>专家评审</span></div>
        </div>

        <!-- 有未完成的会话 -->
        <div v-if="pendingResume" class="resume-section">
          <p class="resume-hint">
            您有一份未完成的测评<br>
            <span class="resume-detail">当前阶段：{{ pendingResume.stage_display_name }} · 已答 {{ pendingResume.answered_count }} 题</span>
          </p>
          <button class="start-btn resume-btn" @click="resumeSession" :disabled="isStarting">
            继续测评
          </button>
          <button class="start-btn restart-new-btn" @click="restartFromPending" :disabled="isStarting">
            <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
            <span v-else>重新开始</span>
          </button>
        </div>

        <!-- 有已完成的会话（可以重新作答） -->
        <div v-else-if="lastCompletedSession" class="completed-section">
          <p class="completed-hint">您已完成过一次测评</p>
          <button class="start-btn" @click="startNewSession" :disabled="isStarting">
            <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
            <span v-else>开始新测评</span>
          </button>
          <button class="start-btn restart-new-btn" @click="goToHistory">
            查看历史报告
          </button>
        </div>

        <!-- 首次测评 -->
        <div v-else>
          <button class="start-btn" @click="startNewSession" :disabled="isStarting">
            <span v-if="isStarting"><span class="btn-spinner"></span>准备中...</span>
            <span v-else>开始测评</span>
          </button>
        </div>

        <p v-if="startError" class="start-error">{{ startError }}</p>
      </div>
    </div>

    <!-- 答题页 -->
    <div v-else-if="!isFinished" class="question-card">
      <!-- 阶段头部信息 -->
      <div class="header">
        <div class="progress-info">
          <div class="stage-title">
            <span class="stage-badge">{{ stageDisplay }}</span>
          </div>
          <span class="progress-text">
            题目 {{ currentIndex + 1 }} / {{ stageQuestionCount }}
          </span>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: ((stageAnsweredCount) / stageQuestionCount * 100) + '%' }"
            ></div>
          </div>
          <span class="progress-percent">
            {{ Math.round((stageAnsweredCount) / stageQuestionCount * 100) }}%
          </span>
        </div>
        <div class="total-progress">
          <span class="total-progress-text">总进度：{{ totalAnsweredCount }} / {{ totalQuestions }}</span>
        </div>
      </div>

      <!-- 题目导航 -->
      <div class="question-nav-toggle" @click="showQuestionNav = !showQuestionNav">
        <span>{{ showQuestionNav ? '收起题目列表' : '展开题目列表' }}</span>
        <span class="toggle-arrow">{{ showQuestionNav ? '▲' : '▼' }}</span>
      </div>
      <div v-if="showQuestionNav" class="question-nav-grid">
        <button
          v-for="i in stageQuestionCount" :key="i"
          :class="['qnav-item', {
            current: currentIndex === i - 1,
            answered: stageQuestions[i - 1] && answersMap[stageQuestions[i - 1]?.id],
          }]"
          @click="jumpToQuestion(i - 1)"
        >{{ i }}</button>
      </div>

      <!-- 题目内容 -->
      <div class="question-content">
        <h2 class="question-title">{{ currentQuestion.content }}</h2>
      </div>

      <!-- 选项 -->
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

      <!-- 异常追问 -->
      <div v-else class="anomaly-container">
        <div class="warning-box">
          <span class="warning-icon">&#9888;</span>
          <span>{{ currentAnswer?.follow_up_question || '系统检测到您的作答时间极短，请问您是如何快速得出这个选择的？' }}</span>
        </div>
        <textarea v-model="userExplanation" placeholder="请输入您的思考过程..." rows="4"></textarea>
        <button class="submit-explanation-btn" @click="submitExplanation">保存解释</button>
      </div>

      <!-- 阶段提交按钮 -->
      <div v-if="canSubmitStage" class="module-submit-bar">
        <div class="module-submit-info">
          <span class="module-submit-label">{{ stageDisplay }} 已答完</span>
          <span class="module-submit-status">可以提交进入下一阶段</span>
        </div>
        <button
          class="module-submit-btn"
          :disabled="isSubmittingStage"
          @click="submitCurrentStage"
        >
          <span v-if="isSubmittingStage"><span class="btn-spinner"></span>提交并评审中...</span>
          <span v-else>提交本阶段并进入下一环节</span>
        </button>
      </div>

      <!-- 导航按钮 -->
      <div class="navigation-actions">
        <button class="nav-btn secondary" @click="prevQuestion" :disabled="currentIndex === 0">上一题</button>
        <button
          class="nav-btn"
          v-if="currentIndex < stageQuestionCount - 1"
          @click="nextQuestion"
          :disabled="!canGoNext"
        >下一题</button>
      </div>
    </div>

    <!-- 阶段评审加载页 -->
    <div v-else-if="isStageReviewing" class="result-page">
      <div class="debate-loading-section">
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
          <h2 class="debate-loading-title">专家评审中</h2>
          <p class="debate-loading-subtitle">
            {{ reviewingStage ? `${stageNames[reviewingStage]} 专家评审已在后台进行` : '正在处理评审结果' }}
          </p>
          <div class="debate-loading-steps">
            <div :class="['step-item', { active: reviewStep === 0 }]">
              <span class="step-dot"></span><span>唤醒评审团</span>
            </div>
            <div :class="['step-item', { active: reviewStep === 1 }]">
              <span class="step-dot"></span><span>专家分析中</span>
            </div>
            <div :class="['step-item', { active: reviewStep === 2 }]">
              <span class="step-dot"></span><span>生成阶段结论</span>
            </div>
          </div>
          <p v-if="debateError" class="error-text">{{ debateError }}</p>
        </div>
      </div>
    </div>

    <!-- 全部完成结果页 -->
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
          <h2 class="debate-loading-title">正在生成最终报告</h2>
          <p class="debate-loading-subtitle">所有模块评审已完成，正在生成综合报告</p>
          <div class="debate-loading-steps">
            <div :class="['step-item', { active: true }]">
              <span class="step-dot"></span><span>报告生成中...</span>
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

// 阶段配置
const totalQuestions = 42
const stageNames = {
  intro: '序章',
  A: '欣赏型',
  T: '目标型',
  M: '包容型',
  R: '责任型',
}
const stages = ['intro', 'A', 'T', 'M', 'R']

// 状态变量
const currentIndex = ref(0)
const stageQuestions = ref([])  // 当前阶段的题目列表
const answersMap = ref({})
const allAnsweredExamNos = ref([])  // 所有已答题目编号
const currentQuestion = ref({ id: '', content: '正在加载题目...', options: [] })
const startTime = ref(0)
const anomalyTriggered = ref(false)
const userExplanation = ref('')
const isFinished = ref(false)
const isGenerating = ref(false)
const isStageReviewing = ref(false)
const reviewingStage = ref(null)
const reviewStep = ref(0)
const finalReport = ref('')
const debateMessages = ref([])
const debateError = ref('')
const hasStarted = ref(false)
const isStarting = ref(false)
const startError = ref('')
const isCheckingResume = ref(true)
const pendingResume = ref(null)
const lastCompletedSession = ref(null)
const isSubmittingStage = ref(false)
const showQuestionNav = ref(false)

// 阶段信息（从后端获取）
const stageInfo = ref(null)

// 计算属性
const currentStage = computed(() => stageInfo.value?.current_stage || 'intro')
const stageDisplay = computed(() => {
  const s = currentStage.value
  return stageNames[s] || s
})
const stageQuestionCount = computed(() => stageInfo.value?.question_count || 10)
const stageAnsweredCount = computed(() => {
  // 本地已答数，实时更新
  const local = stageQuestions.value.filter(
    (q) => q && answersMap.value[q.id],
  ).length
  // 兜底使用后端数据（恢复会话等场景）
  return Math.max(local, stageInfo.value?.answered_count || 0)
})
const canSubmitStage = computed(() => {
  // 优先用本地状态判断：当前阶段已缓存且已作答的题目数是否达到本阶段总题数
  const answeredInStage = stageQuestions.value.filter(
    (q) => q && answersMap.value[q.id],
  ).length
  if (answeredInStage >= stageQuestionCount.value) return true
  // 兜底：使用后端状态
  return stageInfo.value?.can_submit || false
})
const totalAnsweredCount = computed(() => Object.keys(answersMap.value).length)

const currentAnswer = computed(() => answersMap.value[currentQuestion.value.id] || null)
const canGoNext = computed(() => {
  if (!currentAnswer.value) return false
  if (anomalyTriggered.value) {
    return !!(currentAnswer.value.user_explanation || userExplanation.value.trim())
  }
  return true
})

const submitStageSnapshot = computed(() => {
  // 构建当前阶段所有答案的快照用于提交
  return stageQuestions.value
    .map((q) => {
      if (!q) return null
      const ans = answersMap.value[q.id]
      if (!ans) return null
      return {
        exam_no: q.id,
        selected_option: ans.selected_option,
        time_spent: ans.time_spent,
        user_explanation: ans.user_explanation || null,
      }
    })
    .filter(Boolean)
})

watch(() => debateMessages.value.length, () => {
  nextTick(() => {
    // auto-scroll logic placeholder
  })
})

// 加载阶段信息
const loadStageInfo = async () => {
  try {
    const res = await api.get('/assessment/stage-info', {
      params: { session_id: sessionId.value },
    })
    stageInfo.value = res.data
    return res.data
  } catch (err) {
    console.warn('加载阶段信息失败:', err)
    return null
  }
}

// 加载当前阶段下一题
const loadNextQuestionInStage = async () => {
  // 确保 currentIndex 不超出本阶段范围
  if (currentIndex.value >= stageQuestionCount.value) {
    currentIndex.value = stageQuestionCount.value - 1
  }

  // 如果已经在缓存列表中，直接使用
  if (stageQuestions.value[currentIndex.value]) {
    currentQuestion.value = stageQuestions.value[currentIndex.value]
    startTime.value = Date.now()
    restoreCurrentState()
    return
  }

  try {
    const res = await api.post('/assessment/adaptive-question', null, {
      params: { session_id: sessionId.value },
    })

    const q = {
      id: res.data.examNo,
      content: res.data.exam,
      options: res.data.options,
    }
    stageQuestions.value[currentIndex.value] = q
    currentQuestion.value = q

    // 更新阶段信息
    await loadStageInfo()
  } catch (error) {
    const detail = error.response?.data?.detail
    if (detail && (detail.includes('请提交') || detail.includes('不足'))) {
      // 题目已全部作答，回退到本阶段最后一题的缓存
      currentIndex.value = stageQuestionCount.value - 1
      const cached = stageQuestions.value[currentIndex.value]
      if (cached) {
        currentQuestion.value = cached
      }
      await loadStageInfo()
      return
    }
    console.error('获取题目失败:', error)
    currentQuestion.value = { id: '', content: '加载失败，请重试', options: [] }
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
    if (!isAnomaly && currentIndex.value + 1 < stageQuestionCount.value && !canSubmitStage.value) {
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
  // 同步边界检查，不依赖异步更新的 canSubmitStage
  if (currentIndex.value + 1 >= stageQuestionCount.value) return
  if (canSubmitStage.value) return
  currentIndex.value++
  await loadNextQuestionInStage()
}

const prevQuestion = async () => {
  if (currentIndex.value === 0) return
  currentIndex.value--
  await loadNextQuestionInStage()
}

const jumpToQuestion = async (index) => {
  currentIndex.value = index
  await loadNextQuestionInStage()
}

// 提交当前阶段
const submitCurrentStage = async () => {
  if (!canSubmitStage.value) return
  isSubmittingStage.value = true
  isStageReviewing.value = true
  reviewStep.value = 0

  try {
    const res = await api.post('/assessment/submit-stage', {
      session_id: sessionId.value,
      answers: submitStageSnapshot.value,
    })

    const data = res.data
    reviewingStage.value = data.current_stage
    reviewStep.value = 1

    // 模拟评审进度（极短动画，辩论已在后台运行）
    setTimeout(() => { reviewStep.value = 2 }, 300)
    setTimeout(() => { reviewStep.value = 3 }, 600)

    // 1.5 秒后自动跳转下一阶段（辩论已在后台异步执行）
    setTimeout(async () => {
      isStageReviewing.value = false

      if (data.all_completed) {
        // 全部完成，进入最终报告页
        isFinished.value = true
        isGenerating.value = true
        pollForReport()
      } else if (data.next_stage) {
        // 进入下一阶段
        await loadStageInfo()
        currentIndex.value = 0
        stageQuestions.value = []
        await loadNextQuestionInStage()
      }
    }, 1500)

  } catch (error) {
    isStageReviewing.value = false
    const detail = error.response?.data?.detail
    alert(detail || '阶段提交失败，请稍后重试')
  } finally {
    isSubmittingStage.value = false
  }
}

// 轮询等待最终报告
const pollForReport = async () => {
  const maxAttempts = 60
  let attempts = 0
  const poll = async () => {
    try {
      const res = await api.get(`/assessment/report/${sessionId.value}`)
      if (res.data.report) {
        finalReport.value = res.data.report
        isGenerating.value = false
        return
      }
    } catch {
      // 忽略
    }
    attempts++
    if (attempts < maxAttempts) {
      setTimeout(poll, 3000)
    } else {
      // 超时，跳转到历史页
      isGenerating.value = false
      debateError.value = '报告生成超时，请查看历史记录'
    }
  }
  setTimeout(poll, 5000)
}

const startNewSession = async () => {
  isStarting.value = true
  startError.value = ''
  try {
    const res = await api.post('/assessment/start-session', {})
    sessionId.value = res.data.session_id
    hasStarted.value = true
    currentIndex.value = 0
    stageQuestions.value = []
    answersMap.value = {}
    allAnsweredExamNos.value = []
    isFinished.value = false
    isStageReviewing.value = false
    finalReport.value = ''
    debateMessages.value = []
    router.replace({ query: { ...route.query, sessionId: sessionId.value } })

    // 加载阶段信息
    await loadStageInfo()
    await loadNextQuestionInStage()
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

    // 恢复所有已答题目
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
    allAnsweredExamNos.value = data.answers.map(a => a.exam_no)

    // 加载当前阶段信息
    await loadStageInfo()

    // currentIndex 应为当前阶段已答数（不超过本阶段最大题目数）
    currentIndex.value = Math.min(stageInfo.value?.answered_count || 0, stageQuestionCount.value - 1)

    router.replace({ query: { ...route.query, sessionId: sessionId.value } })
    await loadNextQuestionInStage()
  } catch (error) {
    startError.value = '恢复会话失败，请重新开始'
    hasStarted.value = false
  } finally {
    isStarting.value = false
  }
}

const restartFromPending = async () => {
  if (!pendingResume.value) return
  isStarting.value = true
  try {
    // 调用 restart-session 重置阶段
    await api.post('/assessment/restart-session', {
      session_id: pendingResume.value.session_id,
    })

    // 然后恢复会话（此时回到了 intro）
    const res = await api.get('/assessment/resume-session')
    if (res.data.has_active_session) {
      pendingResume.value = {
        ...res.data,
        current_stage: 'intro',
        stage_display_name: stageNames.intro,
      }
    } else {
      // 如果没有 active session，直接开始新的
      await startNewSession()
      return
    }
  } catch (error) {
    startError.value = '重新开始失败，请重试'
  } finally {
    isStarting.value = false
  }
}

const restartTest = () => {
  router.push('/history')
}

const goToHistory = () => {
  router.push('/history')
}

const formattedReport = computed(() => {
  if (!finalReport.value) return ''
  const cleaned = finalReport.value
    .replace(/【内部记录[：:].*?】/g, '')
    .replace(/\s*TERMINATE\s*/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  return marked.parse(cleaned)
})

onMounted(async () => {
  const querySid = parseInt(route.query.sessionId) || 0

  isCheckingResume.value = true
  try {
    const res = await api.get('/assessment/resume-session')
    if (res.data.has_active_session) {
      // 有未完成的会话
      pendingResume.value = {
        ...res.data,
        stage_display_name: stageNames[res.data.current_stage] || res.data.current_stage,
      }
    } else {
      // 检查是否有已完成的会话
      try {
        const historyRes = await api.get('/assessment/history')
        if (historyRes.data.sessions && historyRes.data.sessions.length > 0) {
          lastCompletedSession.value = historyRes.data.sessions[0]
        }
      } catch {
        // 无历史记录
      }
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
.assessment-container { width: 100%; margin: 0 auto; padding: 32px 0; }

/* === 开始页 === */
.start-page { display: flex; justify-content: center; align-items: center; min-height: calc(100vh - 200px); }
.start-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); padding: 80px 64px; box-shadow: var(--shadow-xl); text-align: center; max-width: 900px; width: 100%; transition: all var(--transition-normal); }
.start-card:hover { box-shadow: var(--shadow-xl), 0 0 60px rgba(99, 102, 241, 0.08); }
.start-icon { font-size: 84px; margin-bottom: 32px; animation: float 4s ease-in-out infinite; }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
.start-title { font-size: 42px; font-weight: 800; color: var(--text-primary); margin: 0 0 24px 0; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.start-description { font-size: 20px; color: var(--text-secondary); line-height: 1.8; margin-bottom: 40px; }
.start-features { display: flex; justify-content: center; gap: 40px; margin-bottom: 48px; }
.feature-item { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--text-primary); font-size: 17px; font-weight: 600; padding: 16px 24px; border-radius: var(--radius-lg); background: var(--bg-hover); transition: all var(--transition-normal); }
.feature-item:hover { background: var(--border); transform: translateY(-4px); box-shadow: var(--shadow); }
.feature-icon { font-size: 40px; transition: transform var(--transition-normal); }
.feature-item:hover .feature-icon { transform: scale(1.1); }
.start-btn { width: 100%; padding: 24px 48px; background: var(--gradient-primary); color: white; border: none; border-radius: var(--radius-lg); font-size: 22px; font-weight: 700; cursor: pointer; transition: all var(--transition-normal); position: relative; overflow: hidden; }
.start-btn:hover:not(:disabled) { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(99, 102, 241, 0.4); }
.start-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-spinner { display: inline-block; width: 22px; height: 22px; border: 3px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 12px; vertical-align: middle; }
.start-error { margin-top: 20px; color: var(--error); font-size: 17px; padding: 12px 20px; background: rgba(239, 68, 68, 0.08); border-radius: var(--radius-md); }
.resume-section { display: flex; flex-direction: column; gap: 16px; }
.resume-hint { font-size: 18px; color: var(--primary); font-weight: 700; margin-bottom: 12px; padding: 16px 24px; background: rgba(99, 102, 241, 0.08); border-radius: var(--radius-md); }
.resume-detail { font-size: 15px; font-weight: 400; color: var(--text-secondary); }
.completed-section { display: flex; flex-direction: column; gap: 16px; }
.completed-hint { font-size: 18px; color: var(--success); font-weight: 700; margin-bottom: 12px; padding: 16px 24px; background: rgba(34, 197, 94, 0.08); border-radius: var(--radius-md); }
.resume-btn { background: var(--gradient-success); }
.resume-btn:hover:not(:disabled) { box-shadow: 0 16px 40px rgba(34, 197, 94, 0.4); }
.restart-new-btn { background: var(--bg-dark); color: var(--text-primary); border: 2px solid var(--border); }
.restart-new-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); transform: translateY(-4px); box-shadow: var(--shadow); }

/* === 答题卡片 === */
.question-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl);
  padding: 56px 64px; box-shadow: var(--shadow-xl); min-height: 580px;
  display: flex; flex-direction: column; transition: all var(--transition-normal);
}
.question-card:hover { box-shadow: var(--shadow-xl), 0 0 60px rgba(99, 102, 241, 0.05); }

/* === 头部 === */
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 48px; gap: 32px; }
.progress-info { flex: 1; }
.stage-title { margin-bottom: 12px; }
.stage-badge { display: inline-block; padding: 10px 24px; border-radius: 50px; font-size: 18px; font-weight: 700; background: rgba(245, 158, 11, 0.12); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.2); }
.total-progress { text-align: right; }
.total-progress-text { font-size: 16px; color: var(--text-secondary); }
.progress-text { display: block; font-size: 20px; color: var(--text-primary); margin-bottom: 16px; font-weight: 600; }
.progress-bar { width: 100%; height: 12px; background: var(--bg-hover); border-radius: var(--radius-lg); overflow: hidden; margin-top: 16px; box-shadow: var(--shadow-inner); }
.progress-fill { height: 100%; background: var(--gradient-primary); transition: width var(--transition-normal) cubic-bezier(0.34, 1.56, 0.64, 1); border-radius: var(--radius-lg); position: relative; }
.progress-fill::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent); animation: shimmer 2s infinite; }
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
.progress-percent { display: inline-block; margin-top: 12px; font-size: 18px; color: var(--primary); font-weight: 800; }

/* === 题目导航 === */
.question-nav-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; margin-bottom: 20px; cursor: pointer;
  background: var(--bg-hover); border: 1px solid var(--border); border-radius: var(--radius-lg);
  font-size: 17px; color: var(--text-primary); font-weight: 600; transition: all var(--transition-normal);
}
.question-nav-toggle:hover { border-color: var(--primary); color: var(--primary); background: rgba(99, 102, 241, 0.05); transform: translateY(-2px); }
.toggle-arrow { font-size: 14px; transition: transform var(--transition-normal); }
.question-nav-toggle:hover .toggle-arrow { transform: translateY(2px); }
.question-nav-grid {
  display: grid; grid-template-columns: repeat(10, 1fr); gap: 10px;
  padding: 24px; margin-bottom: 24px;
  background: var(--bg-hover); border: 1px solid var(--border); border-radius: var(--radius-lg);
}
.qnav-item {
  width: 100%; aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  border: 2px solid var(--border); border-radius: var(--radius-md); background: transparent;
  color: var(--text-secondary); font-size: 16px; font-weight: 700; cursor: pointer; transition: all var(--transition-normal);
  position: relative; overflow: hidden;
}
.qnav-item:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); transform: translateY(-4px); box-shadow: var(--shadow); }
.qnav-item.current { border-color: var(--primary); background: var(--gradient-primary); color: white; box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4); }
.qnav-item.answered:not(.current) { border-color: var(--success); color: var(--success); background: rgba(34, 197, 94, 0.1); }

/* === 题目内容 === */
.question-content { margin-bottom: 48px; flex-shrink: 0; }
.question-title { font-size: 36px; font-weight: 800; color: var(--text-primary); line-height: 1.6; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); }

/* === 选项 === */
.options-container { display: flex; flex-direction: column; gap: 20px; flex: 1; }
.option-btn {
  display: flex; align-items: center; gap: 24px; width: 100%;
  padding: 28px 32px; background: var(--bg-card); border: 2px solid var(--border);
  border-radius: var(--radius-lg); cursor: pointer; transition: all var(--transition-normal); text-align: left;
  position: relative; overflow: hidden;
}
.option-btn:hover { border-color: var(--primary); background: rgba(99,102,241,0.04); transform: translateX(8px); box-shadow: var(--shadow); }
.option-btn.selected { border-color: var(--primary); background: rgba(99,102,241,0.08); box-shadow: 0 8px 24px rgba(99,102,241,0.15); }
.option-label {
  display: flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; background: var(--gradient-primary); color: white;
  border-radius: 50%; font-weight: 800; font-size: 24px; flex-shrink: 0;
  transition: all var(--transition-normal);
}
.option-btn:hover .option-label { transform: scale(1.1); }
.option-btn.selected .option-label { box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4); }
.option-text { color: var(--text-primary); font-size: 22px; line-height: 1.6; font-weight: 600; }

/* === 异常追问 === */
.anomaly-container { margin-top: 32px; }
.warning-box { display: flex; gap: 16px; align-items: flex-start; padding: 24px 28px; background: rgba(245, 158, 11, 0.1); border: 2px solid rgba(245,158,11,0.3); border-radius: var(--radius-lg); margin-bottom: 24px; font-size: 18px; line-height: 1.7; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { border-color: rgba(245, 158, 11, 0.3); } 50% { border-color: rgba(245, 158, 11, 0.6); } }
.warning-icon { color: var(--warning); font-size: 28px; }
textarea { width: 100%; padding: 20px 24px; background: var(--bg-card); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text-primary); font-size: 18px; resize: vertical; box-sizing: border-box; line-height: 1.7; transition: all var(--transition-normal); min-height: 120px; }
textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2); background: var(--bg-hover); }
.submit-explanation-btn { margin-top: 20px; padding: 20px 32px; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: 700; font-size: 18px; background: var(--gradient-warning); color: white; transition: all var(--transition-normal); }
.submit-explanation-btn:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(245, 158, 11, 0.4); }

/* === 模块提交栏 === */
.module-submit-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 24px 32px; margin-top: 28px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(99, 102, 241, 0.1)); border: 2px solid rgba(99, 102, 241, 0.2);
  border-radius: var(--radius-lg);
}
.module-submit-info { display: flex; flex-direction: column; gap: 6px; }
.module-submit-label { font-size: 18px; font-weight: 700; color: var(--primary); }
.module-submit-status { font-size: 16px; color: var(--success); font-weight: 600; }
.module-submit-btn {
  padding: 18px 36px; border: none; border-radius: var(--radius-md); cursor: pointer;
  font-weight: 700; font-size: 17px; transition: all var(--transition-normal);
  background: var(--gradient-success); color: white; position: relative; overflow: hidden;
}
.module-submit-btn:hover:not(:disabled) { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(34, 197, 94, 0.4); }
.module-submit-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* === 导航按钮 === */
.navigation-actions { display: flex; justify-content: space-between; gap: 20px; margin-top: 40px; flex-shrink: 0; }
.nav-btn {
  padding: 22px 44px; border: none; border-radius: var(--radius-lg); cursor: pointer;
  font-weight: 700; font-size: 20px; transition: all var(--transition-normal);
  background: var(--gradient-primary); color: white; position: relative; overflow: hidden;
}
.nav-btn:hover:not(:disabled) { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(99, 102, 241, 0.4); }
.nav-btn.secondary { background: var(--bg-card); color: var(--text-primary); border: 2px solid var(--border); }
.nav-btn.secondary:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); background: var(--bg-hover); }
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* === 结果页 === */
.result-page { display: flex; flex-direction: column; gap: 32px; }
.report-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); overflow: hidden; transition: all var(--transition-normal); }
.report-header { padding: 40px 48px; background: linear-gradient(135deg, rgba(99, 102, 241, 0.03), rgba(99, 102, 241, 0.08)); }
.report-title { font-size: 32px; font-weight: 800; color: var(--text-primary); margin: 0 0 12px 0; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.report-subtitle { color: var(--text-secondary); margin: 0; font-size: 18px; }
.report-divider { height: 2px; background: linear-gradient(90deg, var(--border), var(--primary), var(--border)); margin: 0; }
.report-content { padding: 48px; color: var(--text-primary); line-height: 2; font-size: 20px; }
.report-actions { display: flex; gap: 20px; padding: 0 48px 40px; }
.restart-btn { padding: 20px 36px; border: none; border-radius: var(--radius-lg); background: var(--bg-hover); color: var(--text-primary); cursor: pointer; font-size: 18px; font-weight: 700; transition: all var(--transition-normal); }
.restart-btn:hover { background: var(--border); transform: translateY(-4px); box-shadow: var(--shadow); }
.view-report-btn { background: var(--gradient-primary); color: white; }
.view-report-btn:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(99, 102, 241, 0.4); }
.error-text { color: var(--error); padding: 20px 0 0; font-size: 17px; text-align: center; }

/* === 辩论加载动画 === */
.debate-loading-section { display: flex; justify-content: center; align-items: center; min-height: 60vh; }
.debate-loading-card { text-align: center; padding: 72px 56px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); max-width: 560px; width: 100%; transition: all var(--transition-normal); }
.debate-loading-title { font-size: 36px; font-weight: 800; color: var(--text-primary); margin: 40px 0 16px; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.debate-loading-subtitle { font-size: 18px; color: var(--text-secondary); margin: 0 0 48px; line-height: 1.7; }
.orbit-container { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.orbit-ring { position: absolute; inset: 0; border-radius: 50%; border: 2px solid transparent; }
.orbit-ring.ring-1 { border-top-color: var(--primary); animation: orbit-spin 3s linear infinite; }
.orbit-ring.ring-2 { inset: 16px; border-right-color: var(--secondary, #06b6d4); animation: orbit-spin 2.5s linear infinite reverse; }
.orbit-ring.ring-3 { inset: 32px; border-bottom-color: var(--warning); animation: orbit-spin 2s linear infinite; }
.orbit-dot { position: absolute; width: 12px; height: 12px; border-radius: 50%; }
.orbit-dot.dot-1 { background: var(--primary); top: -6px; left: 50%; transform: translateX(-50%); animation: orbit-spin 3s linear infinite; transform-origin: 50% 86px; }
.orbit-dot.dot-2 { background: var(--secondary, #06b6d4); top: 50%; right: 10px; animation: orbit-spin 2.5s linear infinite reverse; transform-origin: -54px 50%; }
.orbit-dot.dot-3 { background: var(--warning); bottom: 26px; left: 26px; animation: orbit-spin 2s linear infinite; transform-origin: 54px -22px; }
.orbit-center-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 48px; animation: pulse-glow 2s ease-in-out infinite; }
.debate-loading-steps { display: flex; flex-direction: column; gap: 16px; align-items: flex-start; margin: 0 auto; max-width: 240px; }
.step-item { display: flex; align-items: center; gap: 14px; font-size: 16px; color: var(--text-secondary); font-weight: 500; transition: all 0.3s; }
.step-item.active { color: var(--primary-light); font-weight: 700; }
.step-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--border); flex-shrink: 0; transition: all 0.3s; }
.step-item.active .step-dot { background: var(--primary); box-shadow: 0 0 12px rgba(99, 102, 241, 0.6); animation: pulse-dot 1.5s ease-in-out infinite; }

@keyframes orbit-spin { to { transform: rotate(360deg); } }
@keyframes pulse-glow { 0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; } 50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.8; } }
@keyframes pulse-dot { 0%, 100% { box-shadow: 0 0 6px rgba(99, 102, 241, 0.4); } 50% { box-shadow: 0 0 18px rgba(99, 102, 241, 0.8); } }
@keyframes spin { to { transform: rotate(360deg); } }

/* ========== 响应式设计 ========== */
@media (max-width: 768px) {
  .assessment-container { padding: 28px 14px; }
  .start-card { padding: 40px 28px; }
  .start-title { font-size: 28px; }
  .start-description { font-size: 16px; }
  .start-features { flex-direction: column; gap: 16px; }
  .feature-item { padding: 14px 20px; font-size: 15px; }
  .feature-icon { font-size: 34px; }
  .question-card { padding: 28px 20px; min-height: auto; }
  .question-title { font-size: 24px; }
  .question-nav-toggle { padding: 14px 20px; font-size: 15px; }
  .question-nav-grid { grid-template-columns: repeat(5, 1fr); }
  .progress-bar { height: 8px; }
  .adaptive-badge, .sequential-badge, .module-badge { padding: 7px 16px; font-size: 14px; }
  .option-btn { padding: 15px 18px; gap: 14px; border-radius: 14px; }
  .option-label { width: 44px; height: 44px; font-size: 18px; }
  .option-text { font-size: 15px; line-height: 1.5; }
  .anomaly-container { margin-top: 24px; }
  .warning-box { padding: 20px 24px; font-size: 15px; }
  textarea { padding: 16px 20px; font-size: 15px; }
  .module-submit-bar { flex-direction: column; align-items: flex-start; gap: 16px; padding: 20px 24px; }
  .module-submit-btn { width: 100%; padding: 16px 28px; font-size: 15px; }
  .nav-btn { padding: 16px 28px; font-size: 16px; }
  .header { flex-direction: column; align-items: flex-start; gap: 14px; }
  .progress-text { font-size: 16px; }
}

@media (max-width: 480px) {
  .assessment-container { padding: 20px 10px; }
  .start-card { padding: 24px 20px; }
  .start-title { font-size: 24px; }
  .start-description { font-size: 14px; }
  .start-features { flex-direction: column; gap: 12px; }
  .feature-item { padding: 12px 16px; font-size: 14px; }
  .feature-icon { font-size: 32px; }
  .question-card { padding: 20px 16px; }
  .question-title { font-size: 20px; }
  .question-nav-toggle { padding: 12px 16px; font-size: 14px; }
  .question-nav-grid { grid-template-columns: repeat(5, 1fr); }
  .progress-bar { height: 8px; }
  .progress-text { font-size: 14px; }
  .option-btn { padding: 12px 14px; gap: 10px; border-radius: 12px; }
  .option-label { width: 36px; height: 36px; font-size: 16px; }
  .option-text { font-size: 13px; line-height: 1.45; }
  .anomaly-container { margin-top: 20px; }
  .warning-box { padding: 16px 20px; font-size: 14px; }
  textarea { padding: 14px 16px; font-size: 14px; min-height: 80px; }
  .submit-explanation-btn { padding: 14px 24px; font-size: 14px; }
  .module-submit-bar { flex-direction: column; align-items: flex-start; gap: 12px; padding: 16px 20px; }
  .module-submit-btn { width: 100%; padding: 14px 24px; font-size: 14px; }
  .nav-btn { padding: 14px 20px; font-size: 14px; }
  .navigation-actions { flex-direction: column; gap: 10px; }
  .nav-btn { width: 100%; }
}
</style>
