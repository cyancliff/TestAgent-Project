<template>
  <div class="admin-page">
    <section class="toolbar">
      <input v-model="filters.keyword" class="input" placeholder="搜索题号、题干或特质标签" @keyup.enter="loadQuestions" />
      <select v-model="filters.dimension_id" class="input" @change="loadQuestions">
        <option value="">全部维度</option>
        <option value="6">A 欣赏型</option>
        <option value="4">T 目标型</option>
        <option value="5">M 包容型</option>
        <option value="7">R 责任型</option>
      </select>
      <select v-model="filters.is_active" class="input" @change="loadQuestions">
        <option value="">全部状态</option>
        <option value="true">启用</option>
        <option value="false">停用</option>
      </select>
      <button class="btn-primary-sm" type="button" @click="loadQuestions">查询</button>
    </section>

    <section class="admin-table">
      <div class="table-head">
        <span>题号</span>
        <span>维度</span>
        <span>题目与特质</span>
        <span>参数</span>
        <span>质量</span>
        <span>操作</span>
      </div>
      <div v-for="item in questions" :key="item.exam_no" class="table-row">
        <span class="mono">{{ item.exam_no }}</span>
        <span>{{ dimensionName(item.dimension_id) }}</span>
        <div>
          <strong>{{ item.trait_label || '未标注特质' }}</strong>
          <p>{{ item.content }}</p>
        </div>
        <div class="compact">
          <span>难度 {{ number(item.difficulty) }}</span>
          <span>区分 {{ number(item.discrimination) }}</span>
          <span>均时 {{ number(item.avg_time) }}s</span>
        </div>
        <div class="compact">
          <span>{{ item.answer_count }} 次作答</span>
          <span>异常率 {{ percent(item.anomaly_rate) }}</span>
          <span>{{ item.is_reverse ? '反向题' : '正向题' }}</span>
        </div>
        <button class="link-btn" type="button" @click="startEdit(item)">编辑</button>
      </div>
      <div v-if="!loading && !questions.length" class="empty">暂无题目</div>
    </section>

    <div class="pager">
      <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
      <span>第 {{ page }} 页，共 {{ total }} 条</span>
      <button type="button" :disabled="page * pageSize >= total" @click="changePage(page + 1)">下一页</button>
    </div>

    <div v-if="editing" class="modal-mask" @click.self="editing = null">
      <form class="edit-panel" @submit.prevent="saveEdit">
        <h2>编辑题库参数</h2>
        <p class="muted">{{ editing.exam_no }} · {{ editing.content }}</p>
        <label>特质标签<input v-model="editForm.trait_label" class="input" /></label>
        <label>难度<input v-model.number="editForm.difficulty" class="input" type="number" min="0" max="1" step="0.001" /></label>
        <label>区分度<input v-model.number="editForm.discrimination" class="input" type="number" min="0" max="1" step="0.001" /></label>
        <label>平均作答时间<input v-model.number="editForm.avg_time" class="input" type="number" min="1" step="0.1" /></label>
        <label class="check-row"><input v-model="editForm.is_reverse" type="checkbox" /> 反向计分</label>
        <label class="check-row"><input v-model="editForm.is_active" type="checkbox" /> 启用题目</label>
        <div class="modal-actions">
          <button class="btn-ghost" type="button" @click="editing = null">取消</button>
          <button class="btn-primary-sm" type="submit" :disabled="saving">保存</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../../api'

const loading = ref(false)
const saving = ref(false)
const questions = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const editing = ref(null)
const editForm = reactive({})
const filters = reactive({
  keyword: '',
  dimension_id: '',
  is_active: '',
})

const dimensionName = (id) => ({ 6: 'A 欣赏型', 4: 'T 目标型', 5: 'M 包容型', 7: 'R 责任型' }[String(id)] || id)
const number = (value) => Number(value || 0).toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

const params = () => {
  const payload = { page: page.value, page_size: pageSize }
  if (filters.keyword.trim()) payload.keyword = filters.keyword.trim()
  if (filters.dimension_id) payload.dimension_id = filters.dimension_id
  if (filters.is_active !== '') payload.is_active = filters.is_active
  return payload
}

const loadQuestions = async () => {
  loading.value = true
  try {
    const res = await api.get('/admin/questions', { params: params() })
    questions.value = res.data.items || []
    total.value = res.data.total || 0
  } finally {
    loading.value = false
  }
}

const changePage = (nextPage) => {
  page.value = nextPage
  loadQuestions()
}

const startEdit = (item) => {
  editing.value = item
  Object.assign(editForm, {
    trait_label: item.trait_label || '',
    difficulty: item.difficulty,
    discrimination: item.discrimination,
    avg_time: item.avg_time,
    is_reverse: item.is_reverse,
    is_active: item.is_active,
  })
}

const saveEdit = async () => {
  if (!editing.value) return
  saving.value = true
  try {
    await api.patch(`/admin/questions/${editing.value.exam_no}`, editForm)
    editing.value = null
    await loadQuestions()
  } finally {
    saving.value = false
  }
}

onMounted(loadQuestions)
</script>

<style scoped>
.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 170px 140px auto;
  gap: 10px;
  margin-bottom: 14px;
}

.btn-primary-sm,
.link-btn,
.pager button {
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.btn-primary-sm {
  min-height: 42px;
  padding: 0 18px;
  color: #fff;
  background: var(--primary);
}

.admin-table {
  background: #fff;
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 8px;
  overflow: hidden;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 110px 110px minmax(260px, 1fr) 150px 150px 80px;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
}

.table-head {
  background: rgba(17, 17, 17, 0.06);
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 800;
}

.table-row {
  border-top: 1px solid rgba(17, 17, 17, 0.06);
}

.table-row p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.compact {
  display: grid;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 13px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.link-btn {
  min-height: 34px;
  color: var(--primary);
  background: rgba(17, 17, 17, 0.06);
}

.pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}

.pager button {
  min-height: 34px;
  padding: 0 12px;
  background: #fff;
}

.pager button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty {
  padding: 32px;
  text-align: center;
  color: var(--text-secondary);
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.edit-panel {
  width: min(560px, 100%);
  background: #fff;
  border-radius: 8px;
  box-shadow: var(--shadow-xl);
  padding: 22px;
  display: grid;
  gap: 12px;
}

.edit-panel h2 {
  margin: 0;
}

.muted {
  margin: 0;
  color: var(--text-secondary);
}

.edit-panel label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

.check-row {
  display: flex !important;
  align-items: center;
  gap: 10px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1080px) {
  .toolbar,
  .table-head,
  .table-row {
    grid-template-columns: 1fr;
  }

  .table-head {
    display: none;
  }
}
</style>
