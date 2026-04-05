<template>
  <div class="assessment-container">
    <!-- 答题阶段 -->
    <div v-if="!isFinished" class="question-card">
      <div class="header">
        <div class="progress-info">
          <span class="progress-text">题目 {{ currentIndex + 1 }} / {{ maxQuestions }}</span>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: ((currentIndex + 1) / maxQuestions * 100) + '%' }"></div>
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
          @click="selectOption(option)"
        >
          <span class="option-label">{{ String.fromCharCode(65 + index) }}</span>
          <span class="option-text">{{ option }}</span>
        </button>
      </div>

      <div v-else class="anomaly-container">
        <div class="warning-box">
          <span class="warning-icon">&#9888;</span>
          <span>系统检测到您的作答时间极短，请问您是如何快速得出这个选择的？</span>
        </div>
        <textarea
          v-model="userExplanation"
          placeholder="请输入您的思考过程..."
          rows="4"
        ></textarea>
        <button class="submit-explanation-btn" @click="submitExplanation">提交解释并继续</button>
      </div>
    </div>

    <!-- 答题完成：辩论 + 报告在同一页面 -->
    <div v-else class="result-page">
      <!-- 辩论区 -->
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
          <div
            v-for="(msg, i) in debateMessages"
            :key="i"
            :class="['debate-msg', agentClass(msg.agent)]"
          >
            <span class="agent-name">{{ formatAgentName(msg.agent) }}</span>
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

      <!-- 报告区：辩论结束后出现 -->
      <div v-if="!isGenerating" class="report-section">
        <div class="report-header">
          <h2 class="report-title">深度心理测评报告</h2>
          <p class="report-subtitle">基于多智能体辩论生成</p>
        </div>
        <div class="report-divider"></div>
        <div class="report-content" v-html="formattedReport"></div>
        <button class="restart-btn" @click="restartTest">返回历史记录</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api/v1/assessment';
const route = useRoute();
const router = useRouter();

const userId = parseInt(localStorage.getItem('userId') || '0');
const sessionId = ref(parseInt(route.query.sessionId) || 0);

const maxQuestions = 10;
const currentIndex = ref(0);
const currentQuestion = ref({ id: "", content: "正在加载题目...", options: [] });
const startTime = ref(0);
const anomalyTriggered = ref(false);
const userExplanation = ref("");
const isFinished = ref(false);
const isGenerating = ref(false);
const finalReport = ref("");
const debateMessages = ref([]);
const debateError = ref("");
const debateFeedRef = ref(null);
const debateCollapsed = ref(false);

// 自动滚动到辩论消息底部
watch(() => debateMessages.value.length, () => {
  nextTick(() => {
    if (debateFeedRef.value) {
      debateFeedRef.value.scrollTop = debateFeedRef.value.scrollHeight;
    }
  });
});

const formatAgentName = (name) => {
  const map = {
    'Proponent_DeepSeek': '正方专家 (DeepSeek)',
    'Opponent_Qwen': '反方专家 (Qwen)',
    'Judge_GLM4': '主裁决官 (GLM-4)',
    'Human_Admin': '系统管理员'
  };
  return map[name] || name;
};

const agentClass = (name) => {
  if (name.includes('Proponent')) return 'proponent';
  if (name.includes('Opponent')) return 'opponent';
  if (name.includes('Judge')) return 'judge';
  return 'admin';
};

const fetchQuestion = async () => {
  console.log("尝试获取第 " + currentIndex.value + " 题");
  try {
    const res = await axios.get(`${API_BASE}/question/${currentIndex.value}`);
    console.log("获取成功:", res.data);
    currentQuestion.value = {
      id: res.data.examNo,
      content: res.data.exam,
      options: res.data.options
    };
    startTime.value = Date.now();
  } catch (error) {
    console.error("获取题目失败，请检查后端是否开启:", error);
    currentQuestion.value.content = "无法连接后端，请检查后端服务(8000端口)";
  }
};

const selectOption = async (option) => {
  const timeSpentSeconds = parseFloat(((Date.now() - startTime.value) / 1000).toFixed(2));
  console.log("用户选择了:", option, " 耗时:", timeSpentSeconds);

  try {
    const res = await axios.post(`${API_BASE}/submit`, {
      session_id: sessionId.value,
      user_id: userId,
      exam_no: currentQuestion.value.id,
      selected_option: option,
      time_spent: timeSpentSeconds
    });
    console.log("后端返回结果:", res.data);

    if (res.data.status === "anomaly") {
      anomalyTriggered.value = true;
    } else {
      nextQuestion();
    }
  } catch (error) {
    console.error("提交请求失败:", error);
    alert("提交失败，请检查控制台报错！");
  }
};

const submitExplanation = async () => {
  try {
    await axios.post(`${API_BASE}/submit_explanation`, {
      session_id: sessionId.value,
      user_id: userId,
      exam_no: currentQuestion.value.id,
      text: userExplanation.value
    });
    anomalyTriggered.value = false;
    userExplanation.value = "";
    nextQuestion();
  } catch (error) {
    console.error("提交解释失败:", error);
  }
};

const nextQuestion = () => {
  if (currentIndex.value + 1 < maxQuestions) {
    currentIndex.value++;
    fetchQuestion();
  } else {
    finishAssessment();
  }
};

const finishAssessment = () => {
  isFinished.value = true;
  isGenerating.value = true;
  debateMessages.value = [];
  debateError.value = "";

  const evtSource = new EventSource(`${API_BASE}/finish-stream?user_id=${userId}&session_id=${sessionId.value}`);

  evtSource.addEventListener('agent_message', (e) => {
    const data = JSON.parse(e.data);
    debateMessages.value.push({ agent: data.agent, content: data.content });
  });

  evtSource.addEventListener('debate_complete', (e) => {
    const data = JSON.parse(e.data);
    finalReport.value = data.report;
    isGenerating.value = false;
    debateCollapsed.value = true;
    evtSource.close();
  });

  evtSource.addEventListener('error', (e) => {
    if (e.data) {
      // 后端主动发送的自定义 error 事件
      const data = JSON.parse(e.data);
      debateError.value = `辩论出错: ${data.message}`;
      isGenerating.value = false;
      evtSource.close();
    } else if (evtSource.readyState === EventSource.CONNECTING) {
      // 连接中断但 EventSource 正在尝试重连，忽略（心跳会维持连接）
      console.warn("SSE 连接中断，正在重连...");
    } else if (evtSource.readyState === EventSource.CLOSED) {
      // 连接彻底关闭 — 仅在未正常完成时显示错误
      if (isGenerating.value) {
        debateError.value = "与服务器的连接已断开，请检查后端服务是否正常运行";
        isGenerating.value = false;
      }
      evtSource.close();
    }
  });
};

const restartTest = () => {
  router.push('/history');
};

const formattedReport = computed(() => {
  return finalReport.value ? finalReport.value.replace(/\n/g, '<br>') : '';
});

onMounted(() => {
  fetchQuestion();
});
</script>

<style scoped>
.assessment-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* ========== 答题卡片 ========== */
.question-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 40px;
  box-shadow: var(--shadow);
}

/* 进度条 */
.header {
  margin-bottom: 32px;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-text {
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-dark);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  border-radius: 4px;
  transition: width 0.4s ease;
}

/* 题目标题 */
.question-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0 0 32px 0;
}

/* 选项按钮 */
.options-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 18px 24px;
  border: 1px solid var(--border);
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  background: var(--bg-dark);
  font-size: 18px;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.option-btn:hover {
  background: var(--bg-hover);
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
}

.option-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}

.option-btn:hover .option-label {
  background: var(--primary);
  color: white;
}

.option-text {
  line-height: 1.5;
}

/* ========== 异常检测 ========== */
.anomaly-container {
  background: rgba(245, 158, 11, 0.1);
  padding: 28px;
  border-radius: 12px;
  border: 1px solid rgba(245, 158, 11, 0.3);
  margin-top: 20px;
}

.warning-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 16px;
  color: var(--warning);
  line-height: 1.6;
  margin-bottom: 20px;
}

.warning-icon {
  font-size: 30px;
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
  filter: drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3));
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.1); }
}

textarea {
  width: 100%;
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 17px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
  background: var(--bg-dark);
  color: var(--text-primary);
}

textarea:focus {
  outline: none;
  border-color: var(--warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
}

textarea::placeholder {
  color: var(--text-muted);
}

.submit-explanation-btn {
  background: var(--success);
  color: white;
  border: none;
  padding: 14px 28px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  transition: all 0.2s;
}

.submit-explanation-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(34, 197, 94, 0.3);
}

/* ========== 结果页 ========== */
.result-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.debate-section, .report-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 32px;
  box-shadow: var(--shadow);
}

.debate-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  margin-bottom: 20px;
  user-select: none;
}

.debate-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.debate-live-badge {
  font-size: 12px;
  font-weight: 600;
  color: white;
  background: var(--success);
  padding: 4px 10px;
  border-radius: 12px;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.debate-done-badge {
  font-size: 12px;
  font-weight: 600;
  color: white;
  background: var(--text-muted);
  padding: 4px 10px;
  border-radius: 12px;
}

.collapse-toggle {
  font-size: 14px;
  color: var(--primary-light);
  font-weight: 500;
}

.debate-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.debate-feed {
  max-height: 400px;
  overflow-y: auto;
  padding: 20px;
  background: var(--bg-dark);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.debate-msg {
  margin-bottom: 16px;
  padding: 16px 20px;
  border-radius: 12px;
  border-left: 4px solid;
  background: var(--bg-card);
}

.debate-msg .agent-name {
  font-weight: 600;
  font-size: 14px;
  display: block;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.debate-msg .msg-content {
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--text-primary);
  text-align: left;
}

.debate-msg.proponent {
  border-left-color: var(--success);
}
.debate-msg.proponent .agent-name { color: var(--success); }

.debate-msg.opponent {
  border-left-color: var(--error);
}
.debate-msg.opponent .agent-name { color: var(--error); }

.debate-msg.judge {
  border-left-color: var(--warning);
}
.debate-msg.judge .agent-name { color: var(--warning); }

.debate-msg.admin {
  border-left-color: var(--primary);
}
.debate-msg.admin .agent-name { color: var(--primary-light); }

.waiting-hint {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 20px;
}

.waiting-hint p {
  margin-top: 16px;
  font-size: 15px;
}

.error-text {
  color: var(--error);
  font-size: 15px;
  text-align: center;
  margin-top: 16px;
}

/* ========== 报告区 ========== */
.report-header {
  text-align: center;
  margin-bottom: 8px;
}

.report-title {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary-light), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 6px 0;
}

.report-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.report-divider {
  height: 1px;
  background: var(--border);
  margin: 24px 0;
}

.report-content {
  text-align: left;
  line-height: 1.9;
  color: var(--text-primary);
  font-size: 16px;
}

.restart-btn {
  display: block;
  margin: 32px auto 0;
  padding: 14px 36px;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  transition: all 0.2s;
}

.restart-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

/* ========== 加载动画 ========== */
.loader-spinner {
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  animation: spin 1s linear infinite;
  margin: 16px auto;
}

.loader-small {
  width: 24px;
  height: 24px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
