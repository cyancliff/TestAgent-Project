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
        <button class="restart-btn" @click="restartTest">重新测评</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api/v1/assessment';

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
      user_id: 1,
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
      user_id: 1,
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

  const evtSource = new EventSource(`${API_BASE}/finish-stream?user_id=1`);

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
  currentIndex.value = 0;
  isFinished.value = false;
  isGenerating.value = false;
  finalReport.value = "";
  debateMessages.value = [];
  debateError.value = "";
  debateCollapsed.value = false;
  fetchQuestion();
};

const formattedReport = computed(() => {
  return finalReport.value ? finalReport.value.replace(/\n/g, '<br>') : '';
});

onMounted(() => {
  fetchQuestion();
});
</script>

<style scoped>
/* ========== 全局容器 ========== */
.assessment-container {
  max-width: 780px;
  margin: 48px auto;
  padding: 0 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: #333;
}

/* ========== 答题卡片 ========== */
.question-card {
  background: #fff;
  padding: 36px 40px;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

/* 进度条 */
.header {
  margin-bottom: 28px;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-text {
  color: #666;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: #eee;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f8cff, #1b6ef3);
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* 题目标题 */
.question-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1.6;
  margin: 0 0 24px 0;
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
  gap: 14px;
  width: 100%;
  padding: 16px 20px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  text-align: left;
  cursor: pointer;
  background: #fafbfc;
  font-size: 15px;
  color: #333;
  transition: all 0.2s ease;
}

.option-btn:hover {
  background: #eef4ff;
  border-color: #4f8cff;
  box-shadow: 0 2px 8px rgba(79, 140, 255, 0.1);
}

.option-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e8edf3;
  color: #555;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.option-btn:hover .option-label {
  background: #4f8cff;
  color: #fff;
}

.option-text {
  line-height: 1.5;
}

/* ========== 异常检测 ========== */
.anomaly-container {
  background: #fffbe6;
  padding: 24px;
  border-radius: 10px;
  border: 1px solid #ffe58f;
  margin-top: 20px;
}

.warning-box {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 15px;
  color: #8a6d3b;
  line-height: 1.6;
  margin-bottom: 16px;
}

.warning-icon {
  font-size: 20px;
  color: #faad14;
  flex-shrink: 0;
}

textarea {
  width: 100%;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
}

textarea:focus {
  outline: none;
  border-color: #4f8cff;
  box-shadow: 0 0 0 2px rgba(79, 140, 255, 0.15);
}

.submit-explanation-btn {
  background: #52c41a;
  color: #fff;
  border: none;
  padding: 10px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.submit-explanation-btn:hover {
  background: #45a815;
}

/* ========== 结果页（辩论+报告） ========== */
.result-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.debate-section {
  background: #fff;
  padding: 28px 32px;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

.debate-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  margin-bottom: 16px;
  user-select: none;
}

.debate-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 4px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.debate-live-badge {
  font-size: 12px;
  font-weight: 500;
  color: #fff;
  background: #52c41a;
  padding: 2px 10px;
  border-radius: 10px;
  animation: pulse-badge 1.5s ease-in-out infinite;
}

@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.debate-done-badge {
  font-size: 12px;
  font-weight: 500;
  color: #fff;
  background: #999;
  padding: 2px 10px;
  border-radius: 10px;
}

.collapse-toggle {
  font-size: 13px;
  color: #4f8cff;
  font-weight: 500;
  padding-top: 4px;
  flex-shrink: 0;
}

.debate-subtitle {
  font-size: 14px;
  color: #888;
  margin: 0;
}

.debate-feed {
  max-height: 480px;
  overflow-y: auto;
  text-align: left;
  padding: 16px;
  background: #f7f8fa;
  border-radius: 10px;
  border: 1px solid #eee;
}

.debate-msg {
  margin-bottom: 14px;
  padding: 14px 18px;
  border-radius: 10px;
  border-left: 4px solid #ccc;
  background: #fff;
}

.debate-msg .agent-name {
  font-weight: 600;
  font-size: 13px;
  display: block;
  margin-bottom: 6px;
}

.debate-msg .msg-content {
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: #444;
}

.debate-msg.proponent {
  background: #f0fff0;
  border-left-color: #52c41a;
}
.debate-msg.proponent .agent-name { color: #389e0d; }

.debate-msg.opponent {
  background: #fff1f0;
  border-left-color: #ff4d4f;
}
.debate-msg.opponent .agent-name { color: #cf1322; }

.debate-msg.judge {
  background: #fffbe6;
  border-left-color: #faad14;
}
.debate-msg.judge .agent-name { color: #d48806; }

.debate-msg.admin {
  background: #f0f5ff;
  border-left-color: #1890ff;
}
.debate-msg.admin .agent-name { color: #096dd9; }

.waiting-hint {
  text-align: center;
  color: #888;
  padding: 32px 20px;
}

.waiting-hint p {
  margin-top: 12px;
  font-size: 14px;
}

.error-text {
  color: #ff4d4f;
  font-size: 14px;
  text-align: center;
  margin-top: 12px;
}

/* ========== 报告区 ========== */
.report-section {
  background: #fff;
  padding: 36px 40px;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
  animation: fade-in 0.4s ease;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.report-header {
  text-align: center;
  margin-bottom: 8px;
}

.report-title {
  font-size: 22px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 6px 0;
}

.report-subtitle {
  font-size: 14px;
  color: #999;
  margin: 0;
}

.report-divider {
  height: 1px;
  background: #eee;
  margin: 20px 0 24px 0;
}

.report-content {
  text-align: left;
  line-height: 1.8;
  color: #444;
  font-size: 15px;
}

.restart-btn {
  display: block;
  margin: 32px auto 0;
  padding: 12px 32px;
  background: #4f8cff;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  transition: background 0.2s;
}

.restart-btn:hover {
  background: #3a78e8;
}

/* ========== 加载动画 ========== */
.loader-spinner {
  border: 3px solid #e8edf3;
  border-top: 3px solid #4f8cff;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  animation: spin 1s linear infinite;
  margin: 16px auto;
}

.loader-small {
  width: 20px;
  height: 20px;
  margin: 10px auto;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
