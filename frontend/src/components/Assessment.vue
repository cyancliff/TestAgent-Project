<template>
  <div class="assessment-container">

    <div class="card finish-card" v-if="isFinished">
      <h2>🎉 测试完成！</h2>
      <p>恭喜你，极速体验版的题目已全部答完。</p>
      <p class="sub-text">你所有的作答时间、分数、以及针对 AI 追问的解释，都已经安全保存在了本地的数据库中！</p>
      <p class="sub-text">接下来，系统将在后台静默唤醒多智能体，根据你的这些数据展开深度的性格辩论...</p>
    </div>

    <div class="card" v-else-if="currentQuestion">

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
          :disabled="isSubmittingExplanation"
        ></textarea>
        <button class="next-btn" @click="confirmFollowUp" :disabled="isSubmittingExplanation">
          {{ isSubmittingExplanation ? '正在保存...' : '提交并继续' }}
        </button>
      </div>

    </div>

    <div v-else class="loading">正在连接数据库，加载题库中...</div>
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
const isSubmittingExplanation = ref(false)
const aiFollowUp = ref(null)
const explanation = ref("")

// 【新增】标记测试是否彻底结束
const isFinished = ref(false)

const fetchQuestion = async (index) => {
  try {
    const res = await axios.get(`${API_BASE}/question/${index}`)
    currentQuestion.value = res.data
    // 题目渲染出来的瞬间，重置计时器
    startTime.value = Date.now()
  } catch (e) {
    // 后端返回 404 (说明题做完了或者触发了10题限制)，进入完成界面
    isFinished.value = true
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
  } catch (error) {
    console.error("提交异常", error)
    alert("网络请求失败，请检查后端服务是否启动")
  } finally {
    isSubmitting.value = false
  }
}

// 提交对追问的解释
const confirmFollowUp = async () => {
  if (!explanation.value.trim()) {
    alert("补充内容不能为空哦~")
    return
  }

  isSubmittingExplanation.value = true
  try {
    await axios.post(`${API_BASE}/submit_explanation`, {
      user_id: 1,
      exam_no: currentQuestion.value.examNo,
      text: explanation.value
    })

    aiFollowUp.value = null
    explanation.value = ""
    nextStep()
  } catch (error) {
    console.error("保存解释失败", error)
    alert("保存解释失败，请重试")
  } finally {
    isSubmittingExplanation.value = false
  }
}

const nextStep = () => {
  currentIndex.value++
  fetchQuestion(currentIndex.value)
}

// 首次进入页面，加载第 0 题
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
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  border: 1px solid #eee;
}

/* 完结界面专属样式 */
.finish-card {
  text-align: center;
  padding: 60px 40px;
}

.finish-card h2 {
  color: #52c41a;
  font-size: 28px;
  margin-bottom: 20px;
}

.sub-text {
  color: #666;
  font-size: 15px;
  margin-top: 15px;
  line-height: 1.6;
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

.option-btn:hover:not(:disabled) {
  background: #f0f7ff;
  border-color: #409eff;
  color: #409eff;
  transform: translateY(-2px);
}

.option-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

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
  resize: vertical;
  min-height: 80px;
}

textarea:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
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
  transition: background 0.3s;
}

.next-btn:hover:not(:disabled) {
  background: #40a9ff;
}

.next-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading {
  color: #666;
  font-size: 18px;
  margin-top: 100px;
}
</style>