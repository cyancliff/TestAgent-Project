<template>
  <div class="admin-page">
    <div v-if="loading" class="state-block">
      <div class="spinner"></div>
      <p>正在加载管理概览...</p>
    </div>

    <template v-else>
      <div class="metric-grid">
        <div v-for="card in cards" :key="card.label" class="metric-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.note }}</small>
        </div>
      </div>

      <div class="admin-panel">
        <h2>模型与报告状态</h2>
        <div class="model-row">
          <span>当前 checkpoint</span>
          <code>{{ dashboard.model_summary?.checkpoint_path || '未配置' }}</code>
        </div>
        <div class="version-list">
          <div v-for="(count, version) in dashboard.model_summary?.versions || {}" :key="version">
            <span>{{ version }}</span>
            <strong>{{ count }} 份报告</strong>
          </div>
          <p v-if="!Object.keys(dashboard.model_summary?.versions || {}).length" class="muted">暂无大五人格模型报告。</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../../api'

const loading = ref(true)
const dashboard = ref({})

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`
const fixed = (value) => value === null || value === undefined ? '暂无' : Number(value).toFixed(3)

const cards = computed(() => [
  { label: '用户数', value: dashboard.value.users_count ?? 0, note: '已注册账号' },
  { label: 'ATMR 测评', value: dashboard.value.assessment_count ?? 0, note: `${dashboard.value.completed_report_count ?? 0} 份已完成报告` },
  { label: '平均可信度', value: fixed(dashboard.value.assessment_confidence_avg), note: '整体报告质量' },
  { label: '异常作答率', value: percent(dashboard.value.anomaly_rate), note: `${dashboard.value.anomaly_count ?? 0} 条异常记录` },
  { label: '低可信报告', value: dashboard.value.low_confidence_report_count ?? 0, note: '需要谨慎解释' },
  { label: '大五报告', value: dashboard.value.big_five_report_count ?? 0, note: `${dashboard.value.big_five_failed_count ?? 0} 份失败` },
])

const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await api.get('/admin/dashboard')
    dashboard.value = res.data || {}
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.metric-card,
.admin-panel {
  border: 1px solid rgba(17, 17, 17, 0.08);
  background: #fff;
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.metric-card {
  min-height: 126px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 18px;
}

.metric-card span,
.metric-card small,
.muted {
  color: var(--text-secondary);
}

.metric-card strong {
  font-size: 30px;
  line-height: 1.1;
}

.admin-panel {
  padding: 20px;
}

.admin-panel h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.model-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}

code {
  display: block;
  overflow-wrap: anywhere;
  background: rgba(17, 17, 17, 0.06);
  padding: 10px 12px;
  border-radius: 8px;
}

.version-list {
  display: grid;
  gap: 8px;
}

.version-list div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(17, 17, 17, 0.035);
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .metric-grid,
  .model-row {
    grid-template-columns: 1fr;
  }
}
</style>
