<template>
  <div class="assessment-container">
    <div v-if="!isFinished" class="question-card">
      <div class="header">
        <span class="progress">题目 {{ currentIndex + 1 }} / {{ maxQuestions }}</span>
      </div>

      <div class="question-content">
        <h2 style="color: #000;">{{ currentQuestion.content }}</h2>
      </div>

      <div v-if="!anomalyTriggered" class="options-container">
        <button
          v-for="(option, index) in currentQuestion.options"
          :key="index"
          class="option-btn"
          @click="selectOption(option)"
        >
          {{ option }}
        </button>
      </div>

      <div v-else class="anomaly-container">
        <div class="warning-box">
          ⚠️ 系统检测到您的作答时间极短，请问您是如何快速得出这个选择的？
        </div>
        <textarea
          v-model="userExplanation"
          placeholder="请输入您的思考过程..."
          rows="4"
        ></textarea>
        <button class="submit-explanation-btn" @click="submitExplanation">提交解释并继续</button>
      </div>
    </div>

    <div v-else-if="isGenerating" class="generating-screen">
      <h2>🎉 完结撒花！答题结束</h2>
      <div class="loader-spinner"></div>
      <p>专家 AI 评审团（DeepSeek, Qwen, GLM-4）正在后台为您进行深度心理画像辩论...</p>
      <p style="font-size: 14px; color: #666;">这通常需要 1-2 分钟，请耐心等待。</p>
    </div>

    <div v-else class="report-screen">
      <h2>📊 您的深度心理测评报告</h2>
      <div class="report-content" v-html="formattedReport"></div>
      <button class="restart-btn" @click="restartTest">重新测评</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import axios from 'axios';

// --- 状态定义 ---
const maxQuestions = 10;
const currentIndex = ref(0);
const currentQuestion = ref({ content: "加载中...", options: [] });
const startTime = ref(0);

// 异常拦截状态
const anomalyTriggered = ref(false);
const userExplanation = ref("");
const tempSelectedOption = ref(null);

// 流程状态
const isFinished = ref(false);
const isGenerating = ref(false);
const finalReport = ref("");

// --- 核心方法 ---

// 1. 获取当前题目
const fetchQuestion = async () => {
  try {
    const res = await axios.get(`/api/question/${currentIndex.value}`);
    currentQuestion.value = res.data;
    startTime.value = Date.now(); // 开始计时
  } catch (error) {
    console.error("获取题目失败:", error);
  }
};

// 2. 用户点击选项
const selectOption = async (option) => {
  const timeSpent = Date.now() - startTime.value;
  tempSelectedOption.value = option;

  try {
    // 提交给后端“快车道”进行初步判别
    const res = await axios.post('/api/submit', {
      user_id: "user_test_001", // 实际应用中替换为真实用户ID
      question_id: currentQuestion.value.id,
      selected_choice: option,
      time_spent: timeSpent
    });

    if (res.data.status === "anomaly") {
      // 触发异常拦截，UI变黄，要求输入解释
      anomalyTriggered.value = true;
    } else {
      // 正常作答，直接进入下一题
      nextQuestion();
    }
  } catch (error) {
    console.error("提交答案失败:", error);
  }
};

// 3. 提交异常解释
const submitExplanation = async () => {
  try {
    await axios.post('/api/submit_explanation', {
      user_id: "user_test_001",
      question_id: currentQuestion.value.id,
      explanation: userExplanation.value
    });

    // 恢复状态并进入下一题
    anomalyTriggered.value = false;
    userExplanation.value = "";
    nextQuestion();
  } catch (error) {
    console.error("提交解释失败:", error);
  }
};

// 4. 下一题逻辑或交卷
const nextQuestion = () => {
  if (currentIndex.value + 1 < maxQuestions) {
    currentIndex.value++;
    fetchQuestion();
  } else {
    // 达到10题，触发交卷与后台多智能体辩论
    finishAssessment();
  }
};

// 5. 交卷触发多智能体辩论 (慢车道)
const finishAssessment = async () => {
  isFinished.value = true;
  isGenerating.value = true;

  try {
    // 调用后端的 finish 接口，后端在这个接口里提取数据库里的作答数据，喂给 debate_manager
    const res = await axios.post('/api/finish', {
      user_id: "user_test_001"
    });

    // 后端生成完毕，返回报告内容
    finalReport.value = res.data.report;
    isGenerating.value = false;
  } catch (error) {
    console.error("生成报告失败:", error);
    finalReport.value = "报告生成超时或出错，请联系系统管理员。";
    isGenerating.value = false;
  }
};

// 重置测试
const restartTest = () => {
  currentIndex.value = 0;
  isFinished.value = false;
  finalReport.value = "";
  fetchQuestion();
};

// 简单格式化报告内容换行
const formattedReport = computed(() => {
  return finalReport.value.replace(/\n/g, '<br>');
});

// 初始化
onMounted(() => {
  fetchQuestion();
});
</script>

<style scoped>
/* 高对比度企业级 UI 配色方案 */
.assessment-container {
  max-width: 800px;
  margin: 40px auto;
  font-family: 'Helvetica Neue', Arial, sans-serif;
}

.question-card {
  background: #fff;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.header {
  margin-bottom: 20px;
  color: #666;
  font-weight: bold;
}

.option-btn {
  display: block;
  width: 100%;
  padding: 16px;
  margin: 12px 0;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: transparent;
  color: #333;
  font-size: 16px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.option-btn:hover {
  border-color: #0056b3;
  background-color: #f0f7ff;
}

.anomaly-container {
  margin-top: 20px;
  padding: 20px;
  background-color: #fffbe6; /* 警告黄 */
  border: 1px solid #ffe58f;
  border-radius: 8px;
}

.warning-box {
  color: #faad14;
  font-weight: bold;
  margin-bottom: 15px;
}

textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  resize: vertical;
}

.submit-explanation-btn, .restart-btn {
  margin-top: 15px;
  background-color: #52c41a; /* 交互绿 */
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
}

.generating-screen, .report-screen {
  text-align: center;
  background: #fff;
  padding: 50px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.report-content {
  text-align: left;
  margin-top: 30px;
  line-height: 1.6;
  color: #333;
}

/* 简易加载动画 */
.loader-spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #0056b3;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 20px auto;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>