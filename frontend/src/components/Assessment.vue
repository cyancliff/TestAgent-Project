<template>
  <div class="assessment-container">
    <div class="card" v-if="currentQuestion">

      <div class="progress-bar">
        第 {{ currentIndex + 1 }} 题 / 共 {{ currentQuestion.total }} 题
      </div>

      <div v-if="!aiFollowUp">
        <span class="exam-no">题目编号: {{ currentQuestion.examNo }}</span>
        <h2 class="question-title">{{ currentQuestion.exam }}</h2>

        <div class="options-container">
          <button
            v-for="(opt, idx) in currentQuestion.options"
            :key="idx"
            class="option-btn"
            @click="handleOptionSelect(opt)"
            :disabled="isSubmitting"
          >
            {{ opt }}
          </button>
        </div>
      </div>

      <div v-else class="ai-box">
        <div class="ai-header">🤖 智能检测提示</div>
        <p class="ai-text">{{ aiFollowUp }}</p>
        <textarea
          v-model="explanation"
          placeholder="检测到您的作答时间较短，请简单补充您的真实想法..."
        ></textarea>
        <button class="next-btn" @click="confirmFollowUp">提交并继续</button>
      </div>

    </div>
    <div v-else class="loading">正在连接数据库，请稍候...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = "http://127.0.0.1:8000/api/v1/assessment"
const currentQuestion = ref(null)
const currentIndex = ref(0)
const startTime = ref(0)
const isSubmitting = ref(false)
const aiFollowUp = ref(null)
const explanation = ref("")

const fetchQuestion = async (index) => {
  try {
    const res = await axios.get(`${API_BASE}/question/${index}`)
    currentQuestion.value = res.data
    startTime.value = Date.now()
  } catch (e) {
    alert("本轮测评已全部结束，感谢您的参与！")
  }
}

const handleOptionSelect = async (opt) => {
  const duration = (Date.now() - startTime.value) / 1000
  isSubmitting.value = true

  try {
    const res = await axios.post(`${API_BASE}/submit`, {
      user_id: 1,
      exam_no: currentQuestion.value.examNo,
      selected_option: opt,
      time_spent: duration
    })

    if (res.data.status === 'anomaly') {
      aiFollowUp.value = res.data.follow_up_question
    } else {
      nextStep()
    }
  } finally {
    isSubmitting.value = false
  }
}

const confirmFollowUp = () => {
  aiFollowUp.value = null
  explanation.value = ""
  nextStep()
}

const nextStep = () => {
  currentIndex.value++
  fetchQuestion(currentIndex.value)
}

onMounted(() => fetchQuestion(0))
</script>

<style scoped>
/* 容器背景改为浅灰色，突出白色卡片 */
.assessment-container {
  display: flex;
  justify-content: center;
  padding-top: 80px;
  background: #f4f7f9;
  min-height: 100vh;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

.card {
  background: white;
  padding: 40px;
  border-radius: 16px;
  width: 500px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.08);
  border: 1px solid #eee;
}

.progress-bar {
  font-size: 14px;
  color: #555;
  margin-bottom: 20px;
  font-weight: 600;
  border-bottom: 2px solid #409eff;
  display: inline-block;
  padding-bottom: 4px;
}

.exam-no {
  color: #888;
  font-size: 13px;
  display: block;
  margin-bottom: 5px;
}

/* 题干颜色：深黑色，字号加大 */
.question-title {
  margin: 0 0 30px 0;
  font-size: 22px;
  line-height: 1.5;
  color: #1a1a1a;
  font-weight: 700;
}

.options-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 选项按钮：深蓝色文字，白色背景，悬浮变蓝 */
.option-btn {
  padding: 16px 20px;
  border: 2px solid #e8e8e8;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  background: #fff;
  color: #333;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.option-btn:hover {
  background: #f0f7ff;
  border-color: #409eff;
  color: #409eff;
  transform: translateY(-2px);
}

/* AI 追问区域：对比度极高 */
.ai-box {
  background: #fffbe6;
  border: 2px solid #ffe58f;
  padding: 20px;
  border-radius: 12px;
}

.ai-header {
  color: #856404;
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 14px;
}

.ai-text {
  color: #1a1a1a;
  font-size: 17px;
  line-height: 1.6;
  margin-bottom: 15px;
}

textarea {
  width: 100%;
  margin: 10px 0;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #ccc;
  font-size: 15px;
  box-sizing: border-box;
}

.next-btn {
  width: 100%;
  padding: 14px;
  background: #1890ff;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
}

.next-btn:hover { background: #40a9ff; }
.loading { color: #666; font-size: 18px; margin-top: 100px; }
</style>