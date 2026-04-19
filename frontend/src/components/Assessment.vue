<template>
  <div
    :class="[
      'assessment-container',
      {
        'assessment-container--start': isCheckingResume || !hasStarted,
      },
    ]"
  >
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
    <template v-else-if="!isFinished && !isStageReviewing">
    <div class="question-card">
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

      <div class="question-main">
        <!-- 题目导航 -->
        <div ref="questionNavRef" class="question-nav-anchor">
          <div class="question-nav-toggle" @click="toggleQuestionNav">
            <span>{{ showQuestionNav ? '收起题目列表' : '展开题目列表' }}</span>
            <span class="toggle-arrow">{{ showQuestionNav ? '▲' : '▼' }}</span>
          </div>

          <transition name="question-nav-dropdown">
            <div v-if="showQuestionNav" class="question-nav-dropdown" role="dialog" aria-label="题目列表">
              <div class="question-nav-grid">
                <button
                  v-for="i in stageQuestionCount" :key="i"
                  :class="['qnav-item', {
                    current: currentIndex === i - 1,
                    answered: stageQuestions[i - 1] && answersMap[stageQuestions[i - 1]?.id],
                  }]"
                  :disabled="!canNavigateToQuestion(i - 1)"
                  @click="jumpToQuestion(i - 1)"
                >{{ i }}</button>
              </div>
            </div>
          </transition>
        </div>

        <!-- 题目内容 -->
        <div class="question-content">
          <h2 class="question-title">{{ currentQuestion.content }}</h2>
        </div>

        <!-- 选项 -->
        <div class="options-container">
          <button
            v-for="(option, index) in currentQuestion.options"
            :key="index"
            :class="[
              'option-btn',
              {
                selected: currentAnswer?.selected_option === option,
                'option-btn--needs-followup': currentAnswer?.selected_option === option && currentAnswerNeedsFollowUp,
              },
            ]"
            @click="selectOption(option)"
          >
            <span class="option-label">{{ String.fromCharCode(65 + index) }}</span>
            <span class="option-text">{{ option }}</span>
          </button>
        </div>

      </div>

      <!-- 阶段提交按钮 -->
      <div v-if="canSubmitStage" class="module-submit-bar">
        <div class="module-submit-info">
          <span class="module-submit-label">{{ stageDisplay }} 已答完</span>
          <span class="module-submit-status">可以提交进入下一阶段</span>
        </div>
        <button
          class="module-submit-btn"
          :class="{ 'is-loading': isSubmittingStage }"
          :disabled="isSubmittingStage"
          @click="submitCurrentStage"
        >
          <span v-if="isSubmittingStage"><span class="btn-spinner"></span>提交并评审中...</span>
          <span v-else>提交本阶段并进入下一环节</span>
        </button>
      </div>

      <!-- 导航按钮 -->
      <div class="navigation-actions">
        <div class="navigation-slot">
          <button class="nav-btn secondary" @click="prevQuestion" :disabled="currentIndex === 0">上一题</button>
        </div>

        <div class="navigation-slot navigation-slot--center">
          <button
            :class="['nav-btn', currentAnswerNeedsFollowUp ? 'nav-btn--follow-up' : 'nav-btn--note']"
            type="button"
            @click="openPendingFollowUp"
          >
            补充说明
          </button>
        </div>

        <div class="navigation-slot">
          <button
            v-if="currentIndex < stageQuestionCount - 1"
            class="nav-btn"
            @click="nextQuestion"
            :disabled="!canGoNext"
          >下一题</button>
        </div>
      </div>
    </div>

    </template>

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
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { marked } from 'marked'
import { showAlertDialog, showConfirmDialog, showPromptDialog } from '../composables/useAppDialog'

const route = useRoute()
const router = useRouter()
const sessionId = ref(parseInt(route.query.sessionId) || 0)
const questionNavRef = ref(null)

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
const stageQuestionCounts = {
  intro: 2,
  A: 10,
  T: 10,
  M: 10,
  R: 10,
}

// 状态变量
const currentIndex = ref(0)
const stageQuestions = ref([])  // 当前阶段的题目列表
const restoredQuestions = ref([])
const answersMap = ref({})
const explanationDrafts = ref({})
const allAnsweredExamNos = ref([])  // 所有已答题目编号
const currentQuestion = ref({ id: '', content: '正在加载题目...', options: [] })
const startTime = ref(0)
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
const stageQuestionCount = computed(() => stageInfo.value?.question_count || stageQuestionCounts[currentStage.value] || 10)
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
const answerNeedsExplanation = (answer) => !!(answer?.status === 'anomaly' && !answer?.explanation_submitted)
const currentAnswerNeedsFollowUp = computed(() => answerNeedsExplanation(currentAnswer.value))
const canGoNext = computed(() => {
  return !!currentAnswer.value
})
const canNavigateToQuestion = (index) => !!stageQuestions.value[index]
const STAGE_REVIEW_DURATION_MS = 3000
const STAGE_REVIEW_STEP_DURATION_MS = 1000
const FINAL_GENERATING_REDIRECT_MS = 10000
const REPORT_POLL_INITIAL_DELAY_MS = 5000
const REPORT_POLL_INTERVAL_MS = 3000
const stageReviewTimers = []
let reportPollTimer = null
let finalGeneratingRedirectTimer = null
const clearStageReviewTimers = () => {
  while (stageReviewTimers.length) {
    clearTimeout(stageReviewTimers.pop())
  }
}
const clearReportPollTimer = () => {
  if (reportPollTimer) {
    clearTimeout(reportPollTimer)
    reportPollTimer = null
  }
}
const clearFinalGeneratingRedirectTimer = () => {
  if (finalGeneratingRedirectTimer) {
    clearTimeout(finalGeneratingRedirectTimer)
    finalGeneratingRedirectTimer = null
  }
}
const clearAsyncTimers = () => {
  clearStageReviewTimers()
  clearReportPollTimer()
  clearFinalGeneratingRedirectTimer()
}

const buildLocalStageInfo = (stage = currentStage.value, submittedStages = stageInfo.value?.submitted_stages || []) => {
  const safeStage = stage || 'intro'
  const answeredCount = stageQuestions.value.filter(
    (q) => q && answersMap.value[q.id],
  ).length
  const questionCount = stageQuestionCounts[safeStage] || 10
  return {
    current_stage: safeStage,
    stage_name: safeStage,
    stage_display_name: stageNames[safeStage] || safeStage,
    question_count: questionCount,
    answered_count: answeredCount,
    can_submit: answeredCount >= questionCount,
    is_stage_complete: answeredCount >= questionCount,
    submitted_stages: submittedStages,
  }
}

const syncSessionQuery = () => {
  const nextQuery = { ...route.query }
  if (sessionId.value) {
    nextQuery.sessionId = sessionId.value
  } else {
    delete nextQuery.sessionId
  }
  router.replace({ query: nextQuery })
}

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
        score: ans.score,
        is_anomaly: ans.status === 'anomaly' ? 1 : 0,
        ai_follow_up: ans.follow_up_question || null,
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
watch(isGenerating, (generating) => {
  clearFinalGeneratingRedirectTimer()
  if (!generating) return

  finalGeneratingRedirectTimer = setTimeout(() => {
    finalGeneratingRedirectTimer = null
    if (isGenerating.value && isFinished.value) {
      router.replace('/history')
    }
  }, FINAL_GENERATING_REDIRECT_MS)
})

const loadStageInfo = async () => {
  if (!sessionId.value) {
    const localStageInfo = buildLocalStageInfo()
    stageInfo.value = localStageInfo
    return localStageInfo
  }
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
    const res = await api.post('/assessment/adaptive-question', {
      session_id: sessionId.value || null,
      current_stage: currentStage.value,
      transient_answers: submitStageSnapshot.value,
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
  startTime.value = Date.now()
}

const closeQuestionNav = () => {
  showQuestionNav.value = false
}

const toggleQuestionNav = () => {
  showQuestionNav.value = !showQuestionNav.value
}

const handleGlobalKeydown = (event) => {
  if (event.key === 'Escape' && showQuestionNav.value) {
    closeQuestionNav()
  }
}

const handleDocumentClick = (event) => {
  if (!showQuestionNav.value) return
  if (questionNavRef.value?.contains(event.target)) return
  closeQuestionNav()
}

const getFollowUpPrompt = (answer) => answer?.follow_up_question || '系统检测到您的作答时间极短，请问您是如何快速得出这个选择的？'
const getOptionalExplanationPrompt = () => '如果你愿意，可以补充说明你选择这个答案时的想法或背景。'
const getStoredExplanation = (examNo) => {
  if (!examNo) return ''
  const answer = answersMap.value[examNo]
  return answer?.user_explanation || explanationDrafts.value[examNo] || ''
}

const persistAnswerExplanation = async (answer, explanation) => {
  if (!answer) return
  delete explanationDrafts.value[answer.exam_no]
  answersMap.value[answer.exam_no] = {
    ...answer,
    user_explanation: explanation,
    explanation_submitted: true,
  }

  try {
    await api.post('/assessment/save-answer', {
      session_id: sessionId.value,
      exam_no: answer.exam_no,
      selected_option: answer.selected_option,
      time_spent: answer.time_spent,
      score: answer.score,
      is_anomaly: answer.status === 'anomaly' ? 1 : 0,
      ai_follow_up: answer.follow_up_question || null,
      user_explanation: explanation,
    })
  } catch (err) {
    console.warn('解释保存失败:', err)
    await showAlertDialog('补充说明保存失败，请稍后重试。', {
      title: '保存失败',
      destructive: true,
    })
  }
}

const applyAnswerExplanationLocally = async (answer, explanation) => {
  if (!answer) return
  delete explanationDrafts.value[answer.exam_no]
  answersMap.value[answer.exam_no] = {
    ...answer,
    user_explanation: explanation,
    explanation_submitted: true,
  }
}

const requestAnswerExplanation = async (examNo = currentQuestion.value.id) => {
  if (!examNo) return false
  const answer = answersMap.value[examNo]
  const explanationRequired = answerNeedsExplanation(answer)

  while (true) {
    const explanation = await showPromptDialog({
      title: '补充说明',
      message: answer?.status === 'anomaly' ? getFollowUpPrompt(answer) : getOptionalExplanationPrompt(),
      inputLabel: '你的思考过程',
      inputPlaceholder: '请输入你的思考过程...',
      initialValue: getStoredExplanation(examNo),
      inputMaxLength: 300,
      confirmText: '保存说明',
      multiline: true,
      inputRows: 5,
    })

    if (explanation === null) {
      if (answer?.status === 'anomaly') {
        await applyAnswerExplanationLocally(answer, '')
        return true
      }
      return false
    }

    const normalized = explanation.trim()

    if (answer) {
      await applyAnswerExplanationLocally(answer, normalized)
    } else if (normalized) {
      explanationDrafts.value = {
        ...explanationDrafts.value,
        [examNo]: normalized,
      }
    } else {
      const nextDrafts = { ...explanationDrafts.value }
      delete nextDrafts[examNo]
      explanationDrafts.value = nextDrafts
    }
    return true
  }
}

const selectOption = async (option) => {
  const timeSpentSeconds = parseFloat(((Date.now() - startTime.value) / 1000).toFixed(2))
  try {
    const res = await api.post('/assessment/check-answer', {
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
    })
    const existingExplanation = getStoredExplanation(currentQuestion.value.id)

    answersMap.value[currentQuestion.value.id] = {
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
      status: res.data.status,
      score: res.data.score,
      follow_up_question: res.data.follow_up_question,
      user_explanation: existingExplanation,
      explanation_submitted: res.data.status === 'anomaly' ? false : true,
    }
    if (existingExplanation) {
      delete explanationDrafts.value[currentQuestion.value.id]
    }

    const isAnomaly = res.data.status === 'anomaly'

    // 实时保存到后端（fire-and-forget）
    api.post('/assessment/save-answer', {
      session_id: sessionId.value,
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds,
      score: res.data.score,
      is_anomaly: isAnomaly ? 1 : 0,
      ai_follow_up: res.data.follow_up_question || null,
      user_explanation: isAnomaly ? null : (answersMap.value[currentQuestion.value.id]?.user_explanation || null),
    }).catch(err => console.warn('草稿保存失败:', err))

    if (isAnomaly) {
      await requestAnswerExplanation(currentQuestion.value.id)
      if (currentIndex.value + 1 < stageQuestionCount.value && !canSubmitStage.value) {
        setTimeout(() => {
          nextQuestion()
        }, 300)
      }
      return
    }

    // 非异常情况下自动跳转下一题
    if (currentIndex.value + 1 < stageQuestionCount.value && !canSubmitStage.value) {
      setTimeout(() => {
        nextQuestion()
      }, 300)
    }
  } catch (error) {
    console.error('检测答案失败:', error)
    await showAlertDialog('检测失败，请检查后端服务', {
      title: '检测失败',
      destructive: true,
    })
  }
}

const openPendingFollowUp = async () => {
  await requestAnswerExplanation()
}

const buildStageQuestion = (question) => ({
  id: question.examNo,
  content: question.exam,
  options: question.options,
})

const getRestoredQuestionsForStage = (stage = currentStage.value) => {
  if (!stage || !restoredQuestions.value.length) return []

  const seen = new Set()
  return restoredQuestions.value
    .filter((question) => question.stage === stage)
    .filter((question) => {
      if (seen.has(question.examNo)) return false
      seen.add(question.examNo)
      return true
    })
    .map(buildStageQuestion)
}

const hydrateStageQuestionsFromResume = (stage = currentStage.value) => {
  stageQuestions.value = getRestoredQuestionsForStage(stage)
}

const nextQuestion = async () => {
  if (!canGoNext.value) return
  // 只做边界检查，允许在本阶段已答完后继续查看已答题目
  if (currentIndex.value + 1 >= stageQuestionCount.value) return
  currentIndex.value++
  await loadNextQuestionInStage()
}

const prevQuestion = async () => {
  if (currentIndex.value === 0) return
  currentIndex.value--
  await loadNextQuestionInStage()
}

const jumpToQuestion = async (index) => {
  if (!canNavigateToQuestion(index)) return
  closeQuestionNav()
  currentIndex.value = index
  await loadNextQuestionInStage()
}

// 提交当前阶段
const submitCurrentStage = async () => {
  if (isSubmittingStage.value) return // 防抖，防止短时间多次点击
  if (!canSubmitStage.value) return
  isSubmittingStage.value = true
  isStageReviewing.value = true
  reviewStep.value = 0
  reviewingStage.value = currentStage.value
  debateError.value = ''

  try {
    clearStageReviewTimers()
    const reviewProgress = new Promise((resolve) => {
      stageReviewTimers.push(setTimeout(() => {
        reviewStep.value = 1
      }, STAGE_REVIEW_STEP_DURATION_MS))
      stageReviewTimers.push(setTimeout(() => {
        reviewStep.value = 2
      }, STAGE_REVIEW_STEP_DURATION_MS * 2))
      stageReviewTimers.push(setTimeout(resolve, STAGE_REVIEW_DURATION_MS))
    })

    const submitRequest = api.post('/assessment/submit-stage', {
      session_id: sessionId.value || null,
      answers: submitStageSnapshot.value,
    })
    const submitResult = submitRequest.then((res) => {
      reviewingStage.value = res.data.current_stage || reviewingStage.value
      return res.data
    })

    const [data] = await Promise.all([submitResult, reviewProgress])
    clearStageReviewTimers()
    if (data.session_id && data.session_id !== sessionId.value) {
      sessionId.value = data.session_id
      syncSessionQuery()
    }

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
      hydrateStageQuestionsFromResume(currentStage.value)
      await loadNextQuestionInStage()
    }

  } catch (error) {
    clearStageReviewTimers()
    isStageReviewing.value = false
    const detail = error.response?.data?.detail
    await showAlertDialog(detail || '阶段提交失败，请稍后重试', {
      title: '提交失败',
      destructive: true,
    })
  } finally {
    isSubmittingStage.value = false
  }
}

// 轮询等待最终报告
const pollForReport = async () => {
  const maxAttempts = 60
  let attempts = 0
  clearReportPollTimer()
  const poll = async () => {
    reportPollTimer = null
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
      reportPollTimer = setTimeout(poll, REPORT_POLL_INTERVAL_MS)
    } else {
      // 超时，跳转到历史页
      isGenerating.value = false
      debateError.value = '报告生成超时，请查看历史记录'
    }
  }
  reportPollTimer = setTimeout(poll, REPORT_POLL_INITIAL_DELAY_MS)
}

const getActiveSessionConflict = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail || typeof detail !== 'object' || detail.code !== 'active_session_exists') {
    return null
  }
  return detail
}

const redirectToExistingAssessment = async (targetSessionId) => {
  try {
    const res = await api.get('/assessment/resume-session', {
      params: { session_id: targetSessionId },
    })
    if (res.data.has_active_session && res.data.session_id === targetSessionId) {
      pendingResume.value = {
        ...res.data,
        stage_display_name: stageNames[res.data.current_stage] || res.data.current_stage,
      }
      await resumeSession(res.data)
      return
    }
  } catch (error) {
    console.warn('跳转进行中测评失败:', error)
  }

  router.replace({ path: '/assessment', query: { sessionId: targetSessionId } })
}

const startNewSession = async () => {
  isStarting.value = true
  startError.value = ''
  try {
    let res
    try {
      res = await api.post('/assessment/start-session', {})
    } catch (error) {
      const conflict = getActiveSessionConflict(error)
      if (!conflict) throw error

      const shouldOverwrite = await showConfirmDialog(conflict.message, {
        title: '发现进行中测评',
        confirmText: '是，覆盖',
        cancelText: '否，继续当前',
        destructive: true,
      })

      if (!shouldOverwrite) {
        await redirectToExistingAssessment(conflict.session_id)
        return
      }

      res = await api.post('/assessment/start-session', {
        force_overwrite: true,
      })
    }

    sessionId.value = Number(res.data.session_id || 0)
    hasStarted.value = true
    currentIndex.value = 0
    stageQuestions.value = []
    restoredQuestions.value = []
    answersMap.value = {}
    allAnsweredExamNos.value = []
    isFinished.value = false
    isStageReviewing.value = false
    finalReport.value = ''
    debateMessages.value = []
    stageInfo.value = buildLocalStageInfo('intro', [])
    syncSessionQuery()

    // 加载阶段信息
    await loadNextQuestionInStage()
  } catch (error) {
    startError.value = error.response?.data?.detail?.message || error.response?.data?.detail || '网络错误，请检查后端服务'
  } finally {
    isStarting.value = false
  }
}

const resumeSession = async (resumeData = pendingResume.value) => {
  const data = resumeData
  if (!data) return
  isStarting.value = true
  try {
    sessionId.value = data.session_id
    hasStarted.value = true
    stageQuestions.value = []
    restoredQuestions.value = data.questions || []
    answersMap.value = {}
    explanationDrafts.value = {}

    // 恢复所有已答题目
    data.answers.forEach(a => {
      answersMap.value[a.exam_no] = {
        exam_no: a.exam_no,
        selected_option: a.selected_option,
        time_spent: a.time_spent,
        score: a.score,
        status: a.is_anomaly ? 'anomaly' : 'normal',
        follow_up_question: a.ai_follow_up || null,
        user_explanation: a.user_explanation ?? '',
        explanation_submitted: a.is_anomaly ? a.user_explanation !== null && a.user_explanation !== undefined : true,
      }
    })
    allAnsweredExamNos.value = data.answers.map(a => a.exam_no)

    // 加载当前阶段信息
    await loadStageInfo()
    hydrateStageQuestionsFromResume(currentStage.value)

    // currentIndex 应为当前阶段已答数（不超过本阶段最大题目数）
    currentIndex.value = Math.min(stageInfo.value?.answered_count || 0, stageQuestionCount.value - 1)

    syncSessionQuery()
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
    const resumeRequest = querySid
      ? api.get('/assessment/resume-session', {
          params: { session_id: querySid },
        })
      : api.get('/assessment/resume-session')
    const res = await resumeRequest
    if (res.data.has_active_session) {
      // 有未完成的会话
      pendingResume.value = {
        ...res.data,
        stage_display_name: stageNames[res.data.current_stage] || res.data.current_stage,
      }
      if (querySid && res.data.session_id === querySid) {
        await resumeSession(res.data)
      }
    } else {
      // 检查是否有已完成的会话
      try {
        const historyRes = await api.get('/assessment/history')
        if (historyRes.data.sessions && historyRes.data.sessions.length > 0) {
          lastCompletedSession.value = historyRes.data.sessions.find((session) => session.status === 'completed') || null
        }
      } catch {
        // 无历史记录
      }
    }
  } catch (err) {
    console.warn('检查未完成会话失败:', err)
  } finally {
    isCheckingResume.value = false
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  clearAsyncTimers()
  window.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
/* === 容器 === */
.assessment-container {
  width: 100%;
  flex: 1 0 auto;
  min-height: 100%;
  height: auto;
  margin: 0 auto;
  padding: 0;
  display: flex;
  flex-direction: column;
}

/* === 开始页 === */
.start-page {
  width: 100%;
  flex: 1 0 auto;
  min-height: 100%;
  height: auto;
  display: flex;
  justify-content: center;
  align-items: center;
}
.start-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); padding: 80px 64px; box-shadow: var(--shadow-xl); text-align: center; max-width: 900px; width: 100%; transition: all var(--transition-normal);
  display: flex; flex-direction: column; justify-content: center;
}
.start-card:hover { box-shadow: var(--shadow-xl), 0 0 60px rgba(17, 17, 17, 0.08); }
.start-icon { font-size: 84px; margin-bottom: 32px; animation: float 4s ease-in-out infinite; }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
.start-title { font-size: 42px; font-weight: 800; color: var(--text-primary); margin: 0 0 24px 0; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.start-description { font-size: 20px; color: var(--text-secondary); line-height: 1.8; margin-bottom: 40px; }
.start-features { display: flex; justify-content: center; gap: 40px; margin-bottom: 48px; }
.feature-item { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--text-primary); font-size: 17px; font-weight: 600; padding: 16px 24px; border-radius: var(--radius-lg); background: var(--bg-hover); transition: all var(--transition-normal); }
.feature-item:hover { background: var(--border); transform: translateY(-4px); box-shadow: var(--shadow); }
.feature-icon { font-size: 40px; transition: transform var(--transition-normal); }
.feature-item:hover .feature-icon { transform: scale(1.1); }
.feature-item span:last-child { white-space: nowrap; }
.start-btn { width: 100%; padding: 24px 48px; background: var(--gradient-primary); color: white; border: none; border-radius: var(--radius-lg); font-size: 22px; font-weight: 700; cursor: pointer; transition: all var(--transition-normal); position: relative; overflow: hidden; }
.start-btn:hover:not(:disabled) { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(17, 17, 17, 0.24); }
.start-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-spinner { display: inline-block; width: 22px; height: 22px; border: 3px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 12px; vertical-align: middle; }
.start-error { margin-top: 20px; color: var(--error); font-size: 17px; padding: 12px 20px; background: rgba(239, 68, 68, 0.08); border-radius: var(--radius-md); }
.resume-section { display: flex; flex-direction: column; gap: 16px; }
.resume-hint { font-size: 18px; color: var(--primary); font-weight: 700; margin-bottom: 12px; padding: 16px 24px; background: rgba(17, 17, 17, 0.06); border-radius: var(--radius-md); }
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
  padding: 56px 64px; box-shadow: var(--shadow-xl); min-height: 0; height: 100%; max-height: 100%;
  display: flex; flex-direction: column; transition: all var(--transition-normal);
}
.question-card:hover { box-shadow: var(--shadow-xl), 0 0 60px rgba(17, 17, 17, 0.05); }
.question-main { display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; }

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
.question-nav-anchor {
  position: relative;
  z-index: 12;
}
.question-nav-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; margin-bottom: 20px; cursor: pointer;
  background: var(--bg-hover); border: 1px solid var(--border); border-radius: var(--radius-lg);
  font-size: 17px; color: var(--text-primary); font-weight: 600; transition: all var(--transition-normal);
}
.question-nav-toggle:hover { border-color: var(--primary); color: var(--primary); background: rgba(17, 17, 17, 0.05); transform: translateY(-2px); }
.toggle-arrow { font-size: 14px; transition: transform var(--transition-normal); }
.question-nav-toggle:hover .toggle-arrow { transform: translateY(2px); }
.question-nav-dropdown {
  position: absolute;
  top: calc(100% - 6px);
  left: 0;
  width: min(720px, calc(100vw - 64px));
  max-height: min(360px, calc(100dvh - var(--nav-height) - 180px));
  padding: 16px;
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.14);
  overflow: auto;
}
.question-nav-grid {
  display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 10px;
  padding: 0; margin-bottom: 0;
  background: transparent; border: 0; border-radius: 0;
}
.qnav-item {
  width: 100%; aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  border: 2px solid var(--border); border-radius: var(--radius-md); background: transparent;
  color: var(--text-secondary); font-size: 16px; font-weight: 700; cursor: pointer; transition: all var(--transition-normal);
  position: relative; overflow: hidden;
}
.qnav-item:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); transform: translateY(-4px); box-shadow: var(--shadow); }
.qnav-item.current { border-color: var(--primary); background: var(--gradient-primary); color: white; box-shadow: 0 8px 20px rgba(17, 17, 17, 0.24); }
.qnav-item.answered:not(.current) { border-color: var(--success); color: var(--success); background: rgba(34, 197, 94, 0.1); }
.qnav-item:disabled {
  cursor: not-allowed;
  opacity: 0.38;
  color: #9ca3af;
  background: rgba(17, 17, 17, 0.03);
  transform: none;
  box-shadow: none;
}
.question-nav-dropdown-enter-active,
.question-nav-dropdown-leave-active {
  transition: opacity 0.18s ease;
}
.question-nav-dropdown-enter-from,
.question-nav-dropdown-leave-to {
  opacity: 0;
}
.question-nav-dropdown-enter-from,
.question-nav-dropdown-leave-to {
  transform: translateY(-8px) scale(0.98);
}

/* === 题目内容 === */
.question-content { margin-bottom: 48px; flex-shrink: 0; }
.question-title { font-size: 36px; font-weight: 800; color: var(--text-primary); line-height: 1.6; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); }

/* === 选项 === */
.options-container { display: flex; flex-direction: column; gap: 20px; flex: 1; min-height: 0; overflow: auto; padding-right: 8px; }
.option-btn {
  display: flex; align-items: center; gap: 24px; width: 100%;
  padding: 28px 32px; background: var(--bg-card); border: 2px solid var(--border);
  border-radius: var(--radius-lg); cursor: pointer; transition: all var(--transition-normal); text-align: left;
  position: relative; overflow: hidden;
}
.option-btn:hover { border-color: var(--primary); background: rgba(17,17,17,0.04); transform: translateX(8px); box-shadow: var(--shadow); }
.option-btn.selected { border-color: var(--primary); background: rgba(17,17,17,0.08); box-shadow: 0 8px 24px rgba(17,17,17,0.12); }
.option-btn--needs-followup {
  border-color: rgba(245, 158, 11, 0.42);
  background: rgba(245, 158, 11, 0.08);
}
.option-label {
  display: flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; background: var(--gradient-primary); color: white;
  border-radius: 50%; font-weight: 800; font-size: 24px; flex-shrink: 0;
  transition: all var(--transition-normal);
}
.option-btn:hover .option-label { transform: scale(1.1); }
.option-btn.selected .option-label { box-shadow: 0 6px 20px rgba(17, 17, 17, 0.24); }
.option-text { color: var(--text-primary); font-size: 22px; line-height: 1.6; font-weight: 600; }

/* === 模块提交栏 === */
.module-submit-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 24px 32px; margin-top: 28px;
  background: linear-gradient(135deg, rgba(17, 17, 17, 0.04), rgba(17, 17, 17, 0.08)); border: 2px solid rgba(17, 17, 17, 0.14);
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
.navigation-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: center;
  gap: 20px;
  margin-top: 40px;
  flex-shrink: 0;
}
.navigation-slot {
  min-width: 0;
}
.navigation-slot--center {
  display: flex;
  justify-content: center;
}
.nav-btn {
  width: 100%;
  padding: 22px 44px; border: none; border-radius: var(--radius-lg); cursor: pointer;
  font-weight: 700; font-size: 20px; transition: all var(--transition-normal);
  background: var(--gradient-primary); color: white; position: relative; overflow: hidden;
}
.nav-btn:hover:not(:disabled) { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(17, 17, 17, 0.24); }
.nav-btn.secondary { background: var(--bg-card); color: var(--text-primary); border: 2px solid var(--border); }
.nav-btn.secondary:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); background: var(--bg-hover); }
.nav-btn--note {
  background: #ffffff;
  color: var(--text-primary);
  border: 2px solid rgba(17, 17, 17, 0.12);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}
.nav-btn--note:hover:not(:disabled) {
  background: #f8fafc;
  border-color: rgba(17, 17, 17, 0.2);
}
.nav-btn--follow-up {
  background: var(--gradient-warning);
  box-shadow: 0 10px 24px rgba(245, 158, 11, 0.22);
}
.nav-btn--follow-up:hover:not(:disabled) {
  box-shadow: 0 12px 28px rgba(245, 158, 11, 0.36);
}
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* === 结果页 === */
.result-page { display: flex; flex-direction: column; gap: 32px; min-height: 0; height: 100%; overflow: auto; padding-right: 6px; }
.report-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); overflow: hidden; transition: all var(--transition-normal); }
.report-header { padding: 40px 48px; background: linear-gradient(135deg, rgba(17, 17, 17, 0.03), rgba(17, 17, 17, 0.08)); }
.report-title { font-size: 32px; font-weight: 800; color: var(--text-primary); margin: 0 0 12px 0; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.report-subtitle { color: var(--text-secondary); margin: 0; font-size: 18px; }
.report-divider { height: 2px; background: linear-gradient(90deg, var(--border), var(--primary), var(--border)); margin: 0; }
.report-content { padding: 48px; color: var(--text-primary); line-height: 2; font-size: 20px; }
.report-actions { display: flex; gap: 20px; padding: 0 48px 40px; }
.restart-btn { padding: 20px 36px; border: none; border-radius: var(--radius-lg); background: var(--bg-hover); color: var(--text-primary); cursor: pointer; font-size: 18px; font-weight: 700; transition: all var(--transition-normal); }
.restart-btn:hover { background: var(--border); transform: translateY(-4px); box-shadow: var(--shadow); }
.view-report-btn { background: var(--gradient-primary); color: white; }
.view-report-btn:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(17, 17, 17, 0.24); }
.error-text { color: var(--error); padding: 20px 0 0; font-size: 17px; text-align: center; }

/* === 辩论加载动画 === */
.debate-loading-section { display: flex; justify-content: center; align-items: center; min-height: 100%; flex: 1 0 auto; }
.debate-loading-card { text-align: center; padding: 72px 56px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); max-width: 560px; width: 100%; transition: all var(--transition-normal); }
.debate-loading-title { font-size: 36px; font-weight: 800; color: var(--text-primary); margin: 40px 0 16px; background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.debate-loading-subtitle { font-size: 18px; color: var(--text-secondary); margin: 0 0 48px; line-height: 1.7; }
.orbit-container { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.orbit-ring { position: absolute; inset: 0; border-radius: 50%; border: 2px solid transparent; }
.orbit-ring.ring-1 { border-top-color: var(--primary); animation: orbit-spin 3s linear infinite; }
.orbit-ring.ring-2 { inset: 16px; border-right-color: var(--secondary, #3f3f46); animation: orbit-spin 2.5s linear infinite reverse; }
.orbit-ring.ring-3 { inset: 32px; border-bottom-color: var(--warning); animation: orbit-spin 2s linear infinite; }
.orbit-dot { position: absolute; width: 12px; height: 12px; border-radius: 50%; }
.orbit-dot.dot-1 { background: var(--primary); top: -6px; left: 50%; transform: translateX(-50%); animation: orbit-spin 3s linear infinite; transform-origin: 50% 86px; }
.orbit-dot.dot-2 { background: var(--secondary, #3f3f46); top: 50%; right: 10px; animation: orbit-spin 2.5s linear infinite reverse; transform-origin: -54px 50%; }
.orbit-dot.dot-3 { background: var(--warning); bottom: 26px; left: 26px; animation: orbit-spin 2s linear infinite; transform-origin: 54px -22px; }
.orbit-center-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 48px; animation: pulse-glow 2s ease-in-out infinite; }
.debate-loading-steps { display: flex; flex-direction: column; gap: 16px; align-items: center; margin: 0 auto; width: fit-content; max-width: 100%; }
.step-item { display: inline-flex; align-items: center; justify-content: center; gap: 14px; font-size: 16px; color: var(--text-secondary); font-weight: 500; transition: all 0.3s; text-align: center; }
.step-item.active { color: var(--primary-light); font-weight: 700; }
.step-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--border); flex-shrink: 0; transition: all 0.3s; }
.step-item.active .step-dot { background: var(--primary); box-shadow: 0 0 12px rgba(17, 17, 17, 0.4); animation: pulse-dot 1.5s ease-in-out infinite; }

@keyframes orbit-spin { to { transform: rotate(360deg); } }
@keyframes pulse-glow { 0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; } 50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.8; } }
@keyframes pulse-dot { 0%, 100% { box-shadow: 0 0 6px rgba(17, 17, 17, 0.24); } 50% { box-shadow: 0 0 18px rgba(17, 17, 17, 0.42); } }
@keyframes spin { to { transform: rotate(360deg); } }

/* ========== 响应式设计 ========== */
@media (min-width: 1024px) {
  .assessment-container {
    padding: 0;
  }

  .assessment-container--start .start-card {
    max-width: 980px;
    padding: clamp(28px, 4.2dvh, 52px) clamp(40px, 4vw, 64px);
    gap: clamp(12px, 1.6dvh, 18px);
  }

  .assessment-container--start .start-icon {
    font-size: clamp(60px, 6.6dvh, 78px);
    margin-bottom: 0;
  }

  .assessment-container--start .start-title {
    font-size: clamp(34px, 4dvh, 44px);
    margin-bottom: 0;
  }

  .assessment-container--start .start-description {
    font-size: clamp(16px, 1.85dvh, 19px);
    line-height: 1.6;
    margin-bottom: 0;
  }

  .assessment-container--start .start-features {
    margin-bottom: 0;
    gap: clamp(14px, 1.4vw, 20px);
  }

  .assessment-container--start .feature-item {
    padding: 12px 18px;
    gap: 8px;
    font-size: 15px;
  }

  .assessment-container--start .feature-icon {
    font-size: 30px;
  }

  .assessment-container--start .resume-hint,
  .assessment-container--start .completed-hint {
    margin-bottom: 0;
    padding: 14px 18px;
    font-size: 16px;
  }

  .assessment-container--start .resume-detail {
    font-size: 14px;
  }

  .assessment-container--start .resume-section,
  .assessment-container--start .completed-section {
    gap: 12px;
  }

  .assessment-container--start .start-btn {
    padding: 18px 28px;
    font-size: 18px;
  }

  .assessment-container--start .start-error {
    margin-top: 12px;
    font-size: 15px;
  }

  .question-card {
    padding: 20px 28px 18px;
    min-height: 100%;
    height: auto;
    max-height: none;
    overflow: visible;
  }

  .header {
    margin-bottom: 14px;
    gap: 16px;
  }

  .stage-title {
    margin-bottom: 8px;
  }

  .stage-badge {
    padding: 7px 14px;
    font-size: 14px;
  }

  .progress-text {
    font-size: 15px;
    margin-bottom: 8px;
  }

  .progress-bar {
    height: 8px;
    margin-top: 8px;
  }

  .progress-percent,
  .total-progress-text {
    font-size: 13px;
  }

  .question-main {
    gap: 8px;
    overflow: visible;
  }

  .question-nav-toggle {
    padding: 10px 14px;
    margin-bottom: 10px;
    font-size: 14px;
  }

  .question-nav-dropdown {
    width: min(640px, calc(100vw - 64px));
    padding: 14px;
  }

  .question-nav-grid {
    grid-template-columns: repeat(8, minmax(0, 1fr));
    gap: 8px;
  }

  .qnav-item {
    font-size: 14px;
  }

  .question-content {
    margin-bottom: 12px;
  }

  .question-title {
    font-size: 24px;
    line-height: 1.35;
  }

  .options-container {
    gap: 10px;
    flex: 0 0 auto;
    overflow: visible;
    padding-right: 0;
  }

  .option-btn {
    padding: 14px 18px;
    gap: 14px;
  }

  .option-label {
    width: 40px;
    height: 40px;
    font-size: 17px;
  }

  .option-text {
    font-size: 16px;
    line-height: 1.4;
  }

  .module-submit-bar {
    padding: 14px 16px;
    margin-top: 12px;
    gap: 12px;
  }

  .module-submit-label {
    font-size: 15px;
  }

  .module-submit-status {
    font-size: 13px;
  }

  .module-submit-btn {
    padding: 12px 20px;
    font-size: 14px;
  }

  .navigation-actions {
    margin-top: 12px;
    gap: 10px;
  }

  .nav-btn {
    padding: 12px 20px;
    font-size: 15px;
  }
}

@media (max-width: 768px) {
  .assessment-container { padding: 0; }
  .start-page { min-height: 100%; }
  .assessment-container--start .start-card {
    justify-content: space-evenly;
    gap: 12px;
  }
  .start-card { padding: 28px 20px; }
  .start-icon { font-size: 56px; margin-bottom: 18px; }
  .start-title { font-size: 28px; margin-bottom: 14px; }
  .start-description { font-size: 15px; line-height: 1.65; margin-bottom: 24px; }
  .start-features {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 20px;
  }
  .feature-item {
    min-width: 0;
    padding: 12px 8px;
    gap: 8px;
    font-size: 13px;
    border-radius: 14px;
  }
  .feature-icon { font-size: 24px; }
  .resume-section,
  .completed-section { gap: 10px; }
  .resume-hint,
  .completed-hint {
    margin-bottom: 6px;
    padding: 12px 16px;
    font-size: 15px;
    line-height: 1.55;
  }
  .resume-detail { font-size: 13px; }
  .start-btn {
    padding: 16px 20px;
    font-size: 17px;
    border-radius: 16px;
  }
  .btn-spinner {
    width: 18px;
    height: 18px;
    margin-right: 8px;
    border-width: 2px;
  }
  .start-error {
    margin-top: 14px;
    padding: 10px 14px;
    font-size: 14px;
  }
  .question-card { padding: 20px 16px 18px; min-height: 0; height: 100%; overflow: hidden; }
  .question-main { gap: 12px; overflow: hidden; }
  .question-title { font-size: 24px; }
  .question-nav-toggle { padding: 14px 20px; font-size: 15px; }
  .question-nav-anchor { z-index: 20; }
  .question-nav-dropdown { top: calc(100% - 4px); width: min(520px, calc(100vw - 28px)); max-height: min(320px, calc(100dvh - var(--nav-height) - 140px)); padding: 14px; border-radius: 20px; }
  .question-nav-grid { grid-template-columns: repeat(5, 1fr); gap: 8px; max-height: none; overflow: visible; }
  .progress-bar { height: 8px; }
  .adaptive-badge, .sequential-badge, .module-badge { padding: 7px 16px; font-size: 14px; }
  .question-content { position: static; margin-bottom: 4px; padding: 0; background: transparent; }
  .options-container { gap: 12px; padding-right: 6px; overflow: auto; }
  .option-btn { padding: 15px 18px; gap: 14px; border-radius: 14px; }
  .option-label { width: 44px; height: 44px; font-size: 18px; }
  .option-text { font-size: 15px; line-height: 1.5; }
  .module-submit-bar { flex-direction: column; align-items: flex-start; gap: 16px; padding: 18px 20px; margin-top: 16px; flex-shrink: 0; }
  .module-submit-btn { width: 100%; padding: 16px 28px; font-size: 15px; }
  .nav-btn { padding: 14px 24px; font-size: 15px; }
  .header { flex-direction: column; align-items: flex-start; gap: 14px; }
  .progress-text { font-size: 16px; margin-bottom: 10px; }
  .stage-title { margin-bottom: 8px; }
  .stage-badge { padding: 8px 16px; font-size: 14px; }
  .progress-percent, .total-progress-text { font-size: 14px; }
  .navigation-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 16px;
    padding-top: 0;
    background: transparent;
    flex-shrink: 0;
    gap: 12px;
    width: 100%;
  }
  .nav-btn {
    width: 100%;
    min-width: 0;
  }
  .report-header { padding: 28px 24px; }
  .report-content { padding: 28px 24px; font-size: 16px; line-height: 1.8; }
  .report-actions { flex-direction: column; padding: 0 24px 24px; }
  .restart-btn { width: 100%; padding: 16px 20px; font-size: 16px; }
}

@media (max-width: 480px) {
  .assessment-container.assessment-container--start {
    min-height: 100%;
    height: auto;
  }

  .assessment-container--start .start-page {
    min-height: 100%;
    height: auto;
    align-items: center;
  }

  .assessment-container--start .start-card {
    padding: clamp(24px, 4.4dvh, 34px) clamp(16px, 4.2vw, 22px);
    display: flex;
    flex-direction: column;
    justify-content: space-evenly;
    gap: clamp(12px, 1.9dvh, 18px);
    margin-block: auto;
  }

  .assessment-container--start .start-icon {
    font-size: clamp(52px, 7.2dvh, 64px);
    margin-bottom: 0;
  }

  .assessment-container--start .start-title {
    font-size: clamp(30px, 4.2dvh, 36px);
    margin-bottom: 0;
  }

  .assessment-container--start .start-description {
    font-size: clamp(15px, 2.15dvh, 17px);
    line-height: 1.6;
    margin-bottom: 0;
  }

  .assessment-container--start .start-features {
    margin-bottom: 0;
    gap: 10px;
  }

  .assessment-container--start .feature-item {
    padding: 12px 6px;
    gap: 7px;
    font-size: clamp(11px, 1.45dvh, 13px);
    border-radius: 14px;
  }

  .assessment-container--start .feature-icon {
    font-size: clamp(22px, 3.2dvh, 28px);
  }

  .assessment-container--start .resume-section,
  .assessment-container--start .completed-section {
    gap: 12px;
  }

  .assessment-container--start .resume-hint,
  .assessment-container--start .completed-hint {
    margin-bottom: 0;
    padding: 14px 16px;
    font-size: clamp(14px, 1.85dvh, 16px);
    line-height: 1.55;
  }

  .assessment-container--start .resume-detail {
    font-size: clamp(12px, 1.45dvh, 14px);
  }

  .assessment-container--start .start-btn {
    padding: clamp(15px, 2dvh, 18px) 18px;
    font-size: clamp(17px, 2.1dvh, 19px);
    border-radius: 16px;
  }

  .assessment-container--start .start-error {
    margin-top: 0;
  }

  .assessment-container { padding: 0; }
  .start-page { min-height: 100%; }
  .start-card { padding: 20px 14px; }
  .start-icon { font-size: 42px; margin-bottom: 12px; }
  .start-title { font-size: 22px; margin-bottom: 10px; }
  .start-description { font-size: 13px; line-height: 1.55; margin-bottom: 16px; }
  .start-features {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    margin-bottom: 16px;
  }
  .feature-item {
    padding: 8px 3px;
    gap: 5px;
    font-size: 10px;
    border-radius: 12px;
  }
  .feature-icon { font-size: 18px; }
  .resume-section,
  .completed-section { gap: 8px; }
  .resume-hint,
  .completed-hint {
    margin-bottom: 4px;
    padding: 10px 12px;
    font-size: 13px;
    line-height: 1.45;
  }
  .resume-detail { font-size: 12px; }
  .start-btn {
    padding: 12px 16px;
    font-size: 15px;
    border-radius: 14px;
  }
  .btn-spinner {
    width: 16px;
    height: 16px;
    margin-right: 6px;
  }
  .start-error {
    margin-top: 10px;
    padding: 8px 10px;
    font-size: 12px;
  }
  .question-card { padding: 16px 12px 14px; min-height: 0; height: 100%; overflow: hidden; }
  .question-title { font-size: 19px; line-height: 1.45; }
  .question-nav-toggle { padding: 12px 16px; font-size: 14px; }
  .question-nav-dropdown { width: min(360px, calc(100vw - 20px)); max-height: min(280px, calc(100dvh - var(--nav-height) - 120px)); padding: 12px; border-radius: 18px; }
  .question-nav-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
  .progress-bar { height: 8px; }
  .progress-text { font-size: 14px; }
  .question-content { padding-bottom: 0; }
  .options-container { gap: 10px; padding-right: 4px; overflow: auto; }
  .option-btn { padding: 12px 14px; gap: 10px; border-radius: 12px; }
  .option-label { width: 36px; height: 36px; font-size: 16px; }
  .option-text { font-size: 13px; line-height: 1.45; }
  .module-submit-bar { flex-direction: column; align-items: flex-start; gap: 12px; padding: 16px; }
  .module-submit-label { font-size: 16px; }
  .module-submit-status { font-size: 14px; }
  .module-submit-btn { width: 100%; padding: 14px 24px; font-size: 14px; }
  .nav-btn { padding: 14px 12px; font-size: 14px; }
  .navigation-actions { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .header { gap: 10px; margin-bottom: 14px; }
  .progress-bar { margin-top: 10px; }
  .report-header { padding: 24px 20px; }
  .report-title { font-size: 24px; }
  .report-subtitle { font-size: 15px; }
  .report-content { padding: 24px 20px; font-size: 15px; }
  .report-actions { padding: 0 20px 20px; }
  .restart-btn { padding: 14px 16px; font-size: 15px; }
}
</style>
