<template>
  <div class="admin-page reports-page">
    <section class="report-column">
      <div class="panel-head">
        <h2>ATMR 报告</h2>
        <button class="mini-btn" type="button" @click="loadAssessmentReports">刷新</button>
      </div>
      <div class="filters">
        <input v-model="assessmentFilters.username" class="input" placeholder="用户搜索" @keyup.enter="loadAssessmentReports" />
        <select v-model="assessmentFilters.confidence_label" class="input" @change="loadAssessmentReports">
          <option value="">全部可信度</option>
          <option value="较高">较高</option>
          <option value="中等">中等</option>
          <option value="较低">较低</option>
        </select>
      </div>
      <div class="report-list">
        <button v-for="item in assessmentReports" :key="item.session_id" class="report-item" type="button" @click="openAssessment(item.session_id)">
          <strong>{{ item.title || `测评 #${item.session_id}` }}</strong>
          <span>{{ item.nickname || item.username }} · {{ item.status }} · {{ item.confidence_label }} · 异常 {{ item.anomaly_count }}</span>
        </button>
        <p v-if="!assessmentReports.length" class="empty">暂无 ATMR 报告</p>
      </div>
    </section>

    <section class="report-column">
      <div class="panel-head">
        <h2>大五人格报告</h2>
        <button class="mini-btn" type="button" @click="loadBigFiveReports">刷新</button>
      </div>
      <div class="filters">
        <input v-model="bigFiveFilters.username" class="input" placeholder="用户搜索" @keyup.enter="loadBigFiveReports" />
        <select v-model="bigFiveFilters.status" class="input" @change="loadBigFiveReports">
          <option value="">全部状态</option>
          <option value="completed">completed</option>
          <option value="running">running</option>
          <option value="failed">failed</option>
          <option value="pending">pending</option>
        </select>
      </div>
      <div class="report-list">
        <button v-for="item in bigFiveReports" :key="item.report_id" class="report-item" type="button" @click="openBigFive(item.report_id)">
          <strong>{{ item.title || `大五报告 #${item.report_id}` }}</strong>
          <span>{{ item.nickname || item.username }} · {{ item.status }} · {{ item.model_version }}</span>
        </button>
        <p v-if="!bigFiveReports.length" class="empty">暂无大五报告</p>
      </div>
    </section>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <article class="detail-panel">
        <header>
          <div>
            <p>{{ detail.type }}</p>
            <h2>{{ detail.title }}</h2>
          </div>
          <button class="mini-btn" type="button" @click="detail = null">关闭</button>
        </header>
        <div v-if="detail.type === 'ATMR'" class="detail-grid">
          <span>用户</span><strong>{{ detail.data.nickname || detail.data.username }}</strong>
          <span>可信度</span><strong>{{ detail.data.confidence_label }} {{ percent(detail.data.assessment_confidence) }}</strong>
          <span>异常题</span><strong>{{ detail.data.anomaly_count }}</strong>
        </div>
        <div v-else class="detail-grid">
          <span>用户</span><strong>{{ detail.data.owner?.nickname || detail.data.owner?.username }}</strong>
          <span>状态</span><strong>{{ detail.data.status }}</strong>
          <span>模型</span><strong>{{ detail.data.model_version }}</strong>
        </div>
        <div v-if="detail.type === 'ATMR'" class="markdown-body" v-html="renderReportMarkdown(detail.data.report_content || '暂无报告正文')"></div>
        <div v-else class="markdown-body" v-html="renderReportMarkdown(detail.data.interpretation_content || '暂无 AI 解读正文')"></div>
        <details v-if="detail.type === 'ATMR'">
          <summary>答题证据</summary>
          <pre>{{ JSON.stringify(detail.data.answers || [], null, 2) }}</pre>
        </details>
        <details v-else>
          <summary>质量与一致性摘要</summary>
          <pre>{{ JSON.stringify({ quality_summary: detail.data.quality_summary, confidence_summary: detail.data.confidence_summary, consistency_summary: detail.data.consistency_summary }, null, 2) }}</pre>
        </details>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../../api'
import { renderReportMarkdown } from '../../utils/markdown'

const assessmentReports = ref([])
const bigFiveReports = ref([])
const detail = ref(null)
const assessmentFilters = reactive({ username: '', confidence_label: '' })
const bigFiveFilters = reactive({ username: '', status: '' })

const percent = (value) => value === null || value === undefined ? '暂无' : `${Math.round(Number(value) * 100)}%`

const cleanParams = (obj) => Object.fromEntries(Object.entries(obj).filter(([, value]) => String(value || '').trim()))

const loadAssessmentReports = async () => {
  const res = await api.get('/admin/assessment-reports', { params: cleanParams(assessmentFilters) })
  assessmentReports.value = res.data.items || []
}

const loadBigFiveReports = async () => {
  const res = await api.get('/admin/big-five-reports', { params: cleanParams(bigFiveFilters) })
  bigFiveReports.value = res.data.items || []
}

const openAssessment = async (sessionId) => {
  const res = await api.get(`/admin/assessment-reports/${sessionId}`)
  detail.value = {
    type: 'ATMR',
    title: res.data.title || `测评 #${sessionId}`,
    data: res.data,
  }
}

const openBigFive = async (reportId) => {
  const res = await api.get(`/admin/big-five-reports/${reportId}`)
  detail.value = {
    type: '大五人格',
    title: res.data.title || `大五报告 #${reportId}`,
    data: res.data,
  }
}

onMounted(() => {
  loadAssessmentReports()
  loadBigFiveReports()
})
</script>

<style scoped>
.reports-page {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.report-column,
.detail-panel {
  background: #fff;
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.report-column {
  padding: 18px;
}

.panel-head,
.detail-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

h2 {
  margin: 0;
  font-size: 20px;
}

.filters {
  display: grid;
  grid-template-columns: 1fr 140px;
  gap: 8px;
  margin-bottom: 12px;
}

.report-list {
  display: grid;
  gap: 8px;
}

.report-item {
  text-align: left;
  border: 1px solid rgba(17, 17, 17, 0.08);
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  display: grid;
  gap: 4px;
}

.report-item:hover {
  border-color: var(--primary);
}

.report-item span,
.empty,
.detail-panel header p {
  color: var(--text-secondary);
}

.mini-btn {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(17, 17, 17, 0.12);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-weight: 700;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 320;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  padding: 18px;
}

.detail-panel {
  width: min(980px, 100%);
  max-height: 88vh;
  overflow: auto;
  padding: 22px;
  color: var(--text-primary);
}

.detail-grid {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px 14px;
  padding: 12px;
  background: rgba(17, 17, 17, 0.04);
  border-radius: 8px;
  margin-bottom: 14px;
}

.detail-grid span {
  color: var(--text-secondary);
}

.markdown-body {
  line-height: 1.75;
  background: #fff;
  color: var(--text-primary);
}

pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: rgba(17, 17, 17, 0.06);
  border-radius: 8px;
  padding: 12px;
}

@media (max-width: 900px) {
  .reports-page,
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
