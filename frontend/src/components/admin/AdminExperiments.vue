<template>
  <div class="experiments-page">
    <aside class="experiment-list">
      <button
        v-for="item in experiments"
        :key="item.title"
        type="button"
        :class="['experiment-item', { active: selected?.title === item.title }]"
        @click="selected = item"
      >
        <strong>{{ item.title }}</strong>
        <span>{{ item.category }} · {{ item.exists ? '已有产物' : '未生成' }}</span>
      </button>
    </aside>

    <section class="experiment-detail">
      <template v-if="selected">
        <header>
          <p>{{ selected.category }}</p>
          <h2>{{ selected.title }}</h2>
          <small>{{ selected.markdown_path || selected.json_path || '无本地产物路径' }}</small>
        </header>
        <div v-if="selected.markdown" class="markdown-body" v-html="renderSafeMarkdown(selected.markdown)"></div>
        <pre v-else-if="selected.metrics">{{ JSON.stringify(selected.metrics, null, 2) }}</pre>
        <p v-else class="empty">没有找到该实验的本地产物。</p>
      </template>
      <div v-else class="state-block">
        <p>请选择一个实验结果。</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../../api'
import { renderSafeMarkdown } from '../../utils/markdown'

const experiments = ref([])
const selected = ref(null)

const loadExperiments = async () => {
  const res = await api.get('/admin/experiments')
  experiments.value = res.data.items || []
  selected.value = experiments.value[0] || null
}

onMounted(loadExperiments)
</script>

<style scoped>
.experiments-page {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.experiment-list,
.experiment-detail {
  background: #fff;
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.experiment-list {
  display: grid;
  gap: 8px;
  padding: 12px;
  position: sticky;
  top: calc(var(--nav-height) + 18px);
}

.experiment-item {
  text-align: left;
  border: 1px solid transparent;
  background: rgba(17, 17, 17, 0.04);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  display: grid;
  gap: 4px;
}

.experiment-item.active,
.experiment-item:hover {
  border-color: var(--primary);
  background: rgba(17, 17, 17, 0.08);
}

.experiment-item span,
.experiment-detail header p,
.experiment-detail header small,
.empty {
  color: var(--text-secondary);
}

.experiment-detail {
  padding: 22px;
  min-height: 520px;
  overflow: auto;
}

.experiment-detail h2 {
  margin: 0 0 4px;
}

.experiment-detail header {
  margin-bottom: 16px;
}

.markdown-body {
  line-height: 1.72;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(17, 17, 17, 0.12);
  padding: 8px;
  text-align: left;
}

pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: rgba(17, 17, 17, 0.06);
  border-radius: 8px;
  padding: 14px;
}

@media (max-width: 900px) {
  .experiments-page {
    grid-template-columns: 1fr;
  }

  .experiment-list {
    position: static;
  }
}
</style>
