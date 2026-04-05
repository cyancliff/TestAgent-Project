<template>
  <div class="report-container">
    <div v-if="loading" class="loading-hint">
      <div class="loader-spinner"></div>
      <p>加载报告中...</p>
    </div>

    <template v-else>
      <div class="report-card">
        <div class="report-header">
          <h1 class="report-title">深度心理测评报告</h1>
          <p class="report-meta">
            会话 #{{ sessionId }} | {{ formatTime(reportData.started_at) }}
            <span v-if="reportData.finished_at"> — {{ formatTime(reportData.finished_at) }}</span>
          </p>
        </div>
        <div class="report-divider"></div>
        <div v-if="reportData.report" class="report-body" v-html="formattedReport"></div>
        <div v-else class="no-report-hint">该会话暂无报告内容</div>
      </div>

      <div v-if="reportData.answers && reportData.answers.length" class="answers-card">
        <h2 class="section-title">答题明细</h2>
        <div class="answer-list">
          <div v-for="(a, i) in reportData.answers" :key="i" :class="['answer-item', { anomaly: a.is_anomaly }]">
            <div class="answer-header">
              <span class="answer-no">{{ a.exam_no }}</span>
              <span class="answer-score">{{ a.score }} 分</span>
              <span class="answer-time">{{ a.time_spent }}s</span>
              <span v-if="a.is_anomaly" class="anomaly-badge">异常</span>
            </div>
            <div class="answer-question">{{ a.question }}</div>
            <div class="answer-selected">选择：{{ a.selected_option }}</div>
            <div v-if="a.ai_follow_up" class="answer-followup">AI追问：{{ a.ai_follow_up }}</div>
            <div v-if="a.user_explanation" class="answer-explanation">用户解释：{{ a.user_explanation }}</div>
          </div>
        </div>
      </div>

      <button class="back-btn" @click="$router.push('/history')">返回历史记录</button>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const props = defineProps({ sessionId: String })
const API_BASE = 'http://127.0.0.1:8000/api/v1/assessment'

const reportData = ref({})
const loading = ref(true)

const fetchReport = async () => {
  try {
    const res = await axios.get(`${API_BASE}/report/${props.sessionId}`)
    reportData.value = res.data
  } catch (err) {
    console.error('获取报告失败:', err)
  } finally {
    loading.value = false
  }
}

const formattedReport = computed(() => {
  return reportData.value.report ? reportData.value.report.replace(/\n/g, '<br>') : ''
})

const formatTime = (isoStr) => {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchReport)
</script>

<style scoped>
.report-container {
  max-width: 1000px;
  margin: 48px auto;
  padding: 0 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: var(--text-primary);
}

.report-card, .answers-card {
  background: var(--bg-card);
  padding: 36px 40px;
  border-radius: 16px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
}

.report-header { text-align: center; }

.report-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px 0;
}

.report-meta {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}

.report-divider {
  height: 1px;
  background: var(--border);
  margin: 20px 0 24px 0;
}

.report-body {
  line-height: 1.8;
  color: var(--text-secondary);
  font-size: 15px;
}

.no-report-hint {
  text-align: center;
  color: var(--text-muted);
  padding: 32px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.answer-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.answer-item {
  padding: 16px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.answer-item.anomaly {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.answer-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.answer-no {
  font-weight: 600;
  font-size: 14px;
  color: var(--primary);
}

.answer-score {
  font-size: 13px;
  color: var(--success);
  font-weight: 500;
}

.answer-time {
  font-size: 13px;
  color: var(--text-muted);
}

.anomaly-badge {
  font-size: 11px;
  background: var(--error);
  color: var(--bg-dark);
  padding: 1px 8px;
  border-radius: 4px;
}

.answer-question {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 4px;
  line-height: 1.6;
}

.answer-selected {
  font-size: 13px;
  color: var(--text-secondary);
}

.answer-followup {
  font-size: 13px;
  color: var(--warning);
  margin-top: 4px;
}

.answer-explanation {
  font-size: 13px;
  color: var(--success);
  margin-top: 4px;
}

.back-btn {
  display: block;
  margin: 0 auto 48px;
  padding: 12px 32px;
  background: var(--primary);
  color: var(--bg-dark);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  transition: background 0.2s;
}

.back-btn:hover { background: var(--primary-dark); }

.loading-hint {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}

.loader-spinner {
  border: 3px solid var(--border);
  border-top: 3px solid var(--primary);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
