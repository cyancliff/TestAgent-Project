<template>
  <div :class="['page-layout', 'chat-page-layout', { 'chat-page-layout--sidebar-open': mobileSidebarOpen }]">
    <!-- 左侧：咨询会话列表 -->
    <aside :class="['page-sidebar', 'chat-sidebar', { 'chat-sidebar--open': mobileSidebarOpen }]">
      <div class="sidebar-header">
        <h3>咨询会话</h3>
        <p>{{ chatSessions.length }} 个会话</p>
      </div>
      <div class="sidebar-actions">
        <button class="btn-new-chat" @click="createNewSession">+ 新建对话</button>
      </div>
      <div class="sidebar-list">
        <button
          v-for="s in chatSessions"
          :key="s.id"
          :class="['sidebar-item', { active: activeChatId === s.id }]"
          @click="switchSession(s.id)"
        >
          <span class="sidebar-item-title">{{ s.title || '新对话' }}</span>
          <span class="sidebar-item-meta">
            {{ s.assessment_session_id ? `测评 #${s.assessment_session_id}` : '未关联测评' }}
            · {{ s.message_count }}条
          </span>
        </button>
      </div>
    </aside>

    <!-- 右侧：聊天主区域 -->
    <button
      v-if="mobileSidebarOpen"
      class="chat-sidebar-backdrop"
      type="button"
      aria-label="close session list"
      @click="closeMobileSidebar"
    ></button>

    <div class="chat-main">
      <div class="chat-mobile-toolbar">
        <button class="btn-ghost chat-mobile-toggle" type="button" @click="toggleMobileSidebar">
          {{ mobileSidebarOpen ? '收起会话' : '会话列表' }}
        </button>
      </div>
      <!-- 未选择会话 -->
      <div v-if="!activeChatId" class="chat-empty-state">
        <div class="empty-icon">💬</div>
        <h3>开始一段咨询对话</h3>
        <p>选择左侧已有的会话，或创建一个新对话</p>
        <button class="btn-new-chat-big" @click="createNewSession">+ 新建对话</button>
      </div>

      <!-- 聊天界面 -->
      <div v-else class="chat-container">
        <div class="chat-header">
          <div class="chat-header-info">
            <span class="chat-avatar">🧑‍⚕️</span>
            <div>
              <h2 class="chat-title">AI心理顾问</h2>
              <p class="chat-subtitle">
                <select
                  class="assessment-select"
                  :value="currentAssessmentId || 0"
                  @change="changeAssessment($event.target.value)"
                >
                  <option :value="0">不关联测评</option>
                  <option
                    v-for="a in availableAssessments"
                    :key="a.session_id"
                    :value="a.session_id"
                  >测评 #{{ a.session_id }} ({{ formatDate(a.started_at) }}){{ a.has_report ? '' : ' [无报告]' }}</option>
                </select>
              </p>
            </div>
          </div>
          <div class="chat-header-actions">
            <button class="btn-ghost" @click="clearCurrentChat" title="清空对话">🗑️</button>
            <button class="btn-ghost" @click="deleteCurrentSession" title="删除会话">✕</button>
          </div>
        </div>

        <div class="chat-messages" ref="messagesRef">
          <div v-if="loadingMessages" class="state-block">
            <div class="spinner"></div>
            <p>正在加载对话...</p>
          </div>

          <template v-else>
            <div
              v-for="(msg, index) in messages"
              :id="`chat-msg-${index}`"
              :key="index"
              :class="['chat-bubble', msg.role]"
            >
              <div class="chat-bubble-avatar">
                <template v-if="msg.role === 'user'">
                  <img v-if="userAvatarUrl" :src="userAvatarUrl" class="bubble-avatar-img" alt="" @error="handleAvatarError" />
                  <span v-else>{{ usernameInitial }}</span>
                </template>
                <template v-else>🧑‍⚕️</template>
              </div>
              <div class="chat-bubble-body">
                <div class="chat-bubble-text" v-html="formatMessage(msg.content)"></div>
              </div>
            </div>

            <div v-if="sending && (!messages.length || messages[messages.length - 1].role !== 'assistant')" class="chat-bubble assistant typing">
              <div class="chat-bubble-avatar">🧑‍⚕️</div>
              <div class="chat-bubble-body">
                <div class="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </div>
          </template>
        </div>

        <div class="chat-input-area">
          <div class="chat-input-row">
            <textarea
              v-model="inputMessage"
              placeholder="输入你的问题或感受..."
              rows="1"
              @keydown.enter.prevent="sendMessage"
              @input="autoResize"
              ref="inputRef"
            ></textarea>
            <button
              class="chat-send-btn"
              :disabled="!inputMessage.trim() || sending"
              @click="sendMessage"
            >➤</button>
          </div>
          <p class="chat-input-hint">按 Enter 发送</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { marked } from 'marked'

const userAvatarUrl = ref(localStorage.getItem('avatarUrl') || '')
const usernameInitial = computed(() => {
  const name = localStorage.getItem('username') || '?'
  return name[0].toUpperCase()
})
const route = useRoute()
const router = useRouter()

const chatSessions = ref([])
const activeChatId = ref(null)
const currentAssessmentId = ref(null)
const availableAssessments = ref([])
const messages = ref([])
const inputMessage = ref('')
const loadingMessages = ref(false)
const sending = ref(false)
const messagesRef = ref(null)
const inputRef = ref(null)
const mobileSidebarOpen = ref(false)
let previousBodyOverflow = ''
let previousHtmlOverflow = ''

let activeStreamController = null

const fetchSessions = async () => {
  try {
    const res = await api.get('/chat/sessions')
    chatSessions.value = res.data.sessions
  } catch (err) {
    console.error('获取咨询会话失败:', err)
  }
}

const fetchAssessments = async () => {
  try {
    const res = await api.get('/chat/available-assessments')
    availableAssessments.value = res.data.assessments
  } catch (err) {
    console.error('获取测评列表失败:', err)
  }
}

const createNewSession = async (assessmentSessionId = null) => {
  try {
    const payload = {}
    if (assessmentSessionId && typeof assessmentSessionId === 'number') {
      payload.assessment_session_id = assessmentSessionId
    }
    const res = await api.post('/chat/sessions', payload)
    await fetchSessions()
    mobileSidebarOpen.value = false
    router.push(`/chat/${res.data.id}`)
  } catch (err) {
    console.error('创建会话失败:', err)
    const detail = err.response?.data?.detail || err.message || '未知错误'

    if (assessmentSessionId && typeof assessmentSessionId === 'number') {
      try {
        const fallback = await api.post('/chat/sessions', {})
        await fetchSessions()
        router.push(`/chat/${fallback.data.id}`)
        alert(`关联测评失败，已为你创建普通咨询会话：${detail}`)
        return
      } catch (fallbackErr) {
        console.error('普通咨询会话创建也失败:', fallbackErr)
      }
    }

    alert(`创建会话失败：${detail}`)
  }
}

const switchSession = (id) => {
  mobileSidebarOpen.value = false
  router.push(`/chat/${id}`)
}

const toggleMobileSidebar = () => {
  mobileSidebarOpen.value = !mobileSidebarOpen.value
}

const closeMobileSidebar = () => {
  mobileSidebarOpen.value = false
}

const lockPageScroll = () => {
  previousBodyOverflow = document.body.style.overflow
  previousHtmlOverflow = document.documentElement.style.overflow
  document.body.style.overflow = 'hidden'
  document.documentElement.style.overflow = 'hidden'
}

const unlockPageScroll = () => {
  document.body.style.overflow = previousBodyOverflow
  document.documentElement.style.overflow = previousHtmlOverflow
}

const deleteCurrentSession = async () => {
  if (!activeChatId.value) return
  if (!confirm('确定要删除这个咨询会话吗？所有消息将被清除。')) return
  try {
    await api.delete(`/chat/sessions/${activeChatId.value}`)
    activeChatId.value = null
    messages.value = []
    await fetchSessions()
    router.push('/chat')
  } catch (err) {
    console.error('删除会话失败:', err)
  }
}

const loadMessages = async (chatId) => {
  if (!chatId) return
  loadingMessages.value = true
  try {
    const res = await api.get(`/chat/sessions/${chatId}/messages`)
    messages.value = res.data.messages || []
    currentAssessmentId.value = res.data.assessment_session_id
  } catch (err) {
    console.error('加载消息失败:', err)
    messages.value = []
  } finally {
    loadingMessages.value = false
  }
}

const scrollMessagesToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const cancelActiveStream = () => {
  if (activeStreamController) {
    activeStreamController.abort()
    activeStreamController = null
  }
}

const buildApiUrl = (path) => {
  const basePath = (api.defaults.baseURL || '/api/v1').replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${window.location.origin}${basePath}${normalizedPath}`
}

const parseSSEEvents = (buffer) => {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const rest = parts.pop() || ''
  const events = []

  for (const part of parts) {
    const lines = part.split('\n')
    let event = 'message'
    const dataLines = []

    for (const line of lines) {
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }

    const rawData = dataLines.join('\n')
    let data = null
    if (rawData) {
      try {
        data = JSON.parse(rawData)
      } catch {
        data = { message: rawData }
      }
    }

    events.push({ event, data })
  }

  return { events, rest }
}

const handleUnauthorized = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('userId')
  localStorage.removeItem('username')
  router.push('/login')
}

const readErrorResponse = async (response) => {
  const text = await response.text()
  if (!text) return `请求失败：${response.status}`

  try {
    const data = JSON.parse(text)
    return data.detail || data.message || text
  } catch {
    return text
  }
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value || !activeChatId.value) return

  const optimistic = [...messages.value, { role: 'user', content: text }]
  const assistantMessage = { role: 'assistant', content: '' }
  messages.value = [...optimistic, assistantMessage]
  inputMessage.value = ''
  sending.value = true
  resetTextarea()
  scrollMessagesToBottom()

  try {
    const token = localStorage.getItem('token')
    activeStreamController = new AbortController()

    const response = await fetch(buildApiUrl(`/chat/sessions/${activeChatId.value}/stream`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message: text }),
      signal: activeStreamController.signal,
    })

    if (response.status === 401) {
      handleUnauthorized()
      return
    }

    if (!response.ok || !response.body) {
      throw new Error(await readErrorResponse(response))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let streamCompleted = false

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSSEEvents(buffer)
      buffer = parsed.rest

      for (const event of parsed.events) {
        if (event.event === 'delta') {
          assistantMessage.content += event.data?.content || ''
          scrollMessagesToBottom()
          continue
        }

        if (event.event === 'done') {
          streamCompleted = true
          messages.value = event.data?.messages?.length
            ? event.data.messages
            : [...optimistic, { role: 'assistant', content: event.data?.reply || assistantMessage.content }]
          break
        }

        if (event.event === 'error') {
          throw new Error(event.data?.message || '流式回复失败')
        }
      }

      if (streamCompleted) {
        break
      }
    }

    if (!streamCompleted) {
      throw new Error('流式响应意外中断')
    }

    await fetchSessions()
  } catch (err) {
    if (err.name === 'AbortError') {
      return
    }

    console.error('发送消息失败:', err)
    await loadMessages(activeChatId.value)
    await fetchSessions()

    if (messages.value.length > optimistic.length) {
      return
    }

    const detail = err.message || '未知错误'
    messages.value = [
      ...optimistic,
      {
        role: 'assistant',
        content: `本次回复失败：${detail}`,
      },
    ]
  } finally {
    activeStreamController = null
    sending.value = false
  }
}

const clearCurrentChat = async () => {
  if (!activeChatId.value) return
  if (!confirm('确定要清空当前对话历史吗？')) return
  try {
    const res = await api.post(`/chat/sessions/${activeChatId.value}/clear`)
    messages.value = res.data.messages || []
  } catch (err) {
    console.error('清空对话失败:', err)
  }
}

const changeAssessment = async (value) => {
  const newId = parseInt(value) || 0
  try {
    await api.put(`/chat/sessions/${activeChatId.value}`, {
      assessment_session_id: newId,
    })
    currentAssessmentId.value = newId || null
    await loadMessages(activeChatId.value)
    await fetchSessions()
  } catch (err) {
    console.error('切换关联测评失败:', err)
    alert('切换失败')
  }
}

const formatMessage = (text) => {
  if (!text) return ''
  return marked.parse(text.replace(/^[ \t]+/gm, ''), { breaks: true })
}

const formatDate = (isoStr) => {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const autoResize = () => {
  const el = inputRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }
}

const resetTextarea = () => {
  const el = inputRef.value
  if (el) el.style.height = 'auto'
}

const handleAvatarError = () => {
  userAvatarUrl.value = ''
  localStorage.removeItem('avatarUrl')
}

watch(() => messages.value.length, () => {
  scrollMessagesToBottom()
})

watch(
  () => route.params.chatId,
  async (newId) => {
    cancelActiveStream()
    closeMobileSidebar()
    if (newId) {
      activeChatId.value = parseInt(newId)
      await loadMessages(activeChatId.value)
    } else {
      activeChatId.value = null
      messages.value = []
    }
  },
  { immediate: true }
)

onMounted(async () => {
  lockPageScroll()
  await Promise.all([fetchSessions(), fetchAssessments()])
  userAvatarUrl.value = localStorage.getItem('avatarUrl') || ''

  const assessmentId = parseInt(route.query.assessmentSessionId)
  if (assessmentId && !route.params.chatId) {
    await createNewSession(assessmentId)
  }
})

onBeforeUnmount(() => {
  cancelActiveStream()
  unlockPageScroll()
})
</script>

<style scoped>
.chat-page-layout {
  position: relative;
  align-items: stretch;
  height: calc(100dvh - var(--nav-height) - 24px);
  max-height: calc(100dvh - var(--nav-height) - 24px);
  overflow: hidden;
}

.chat-page-layout .page-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  min-height: 0;
  transition: transform 0.22s ease, opacity 0.22s ease, box-shadow 0.22s ease;
}

.chat-page-layout .sidebar-list {
  flex: 1;
  min-height: 0;
  max-height: none;
}

.chat-mobile-toolbar,
.chat-sidebar-backdrop {
  display: none;
}
/* 侧边栏 */
.sidebar-item.active {
  background: rgba(99, 102, 241, 0.12);
  border-left: 3px solid var(--primary);
}
.sidebar-item:not(.active) {
  border-left: 3px solid transparent;
}

.btn-new-chat {
  width: 100%;
  padding: 14px 20px;
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-new-chat:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
}

/* 空状态 */
.chat-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: clamp(320px, 56vh, 640px);
  color: var(--text-secondary);
  text-align: center;
}
.chat-empty-state .empty-icon { font-size: 64px; margin-bottom: 16px; opacity: 0.5; }
.chat-empty-state h3 { font-size: 20px; color: var(--text-primary); margin: 0 0 8px; }
.chat-empty-state p { font-size: 15px; margin: 0 0 24px; }
.btn-new-chat-big {
  padding: 16px 32px;
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-new-chat-big:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

/* 测评关联选择器 */
.assessment-select {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  padding: 4px 8px;
  cursor: pointer;
  width: 100%;
  max-width: 280px;
}
.assessment-select:focus {
  outline: none;
  border-color: var(--primary);
}

/* 主聊天区 */
.chat-main {
  width: 100%;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.chat-empty-state,
.chat-container {
  flex: 1;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: auto;
  min-height: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-xl);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 28px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
  gap: 16px;
}

.chat-header-info {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex: 1;
}

.chat-header-info > div {
  min-width: 0;
  flex: 1;
}

.chat-avatar { font-size: 44px; }

.chat-title {
  font-size: 22px;
  font-weight: 800;
  margin: 0 0 4px 0;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.chat-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.chat-header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.chat-header-actions .btn-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 消息区 */
.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: var(--bg-hover);
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

/* 消息气泡 */
.chat-bubble {
  display: flex;
  gap: 14px;
  max-width: min(85%, 900px);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.chat-bubble.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-bubble-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.bubble-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.chat-bubble.user .chat-bubble-avatar {
  background: var(--gradient-primary);
  color: white;
  font-weight: 700;
  font-size: 16px;
}

.chat-bubble-body {
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  font-size: 17px;
  line-height: 1.7;
  max-width: 100%;
  min-width: 0;
  overflow-wrap: break-word;
  text-align: left;
}

.chat-bubble.assistant .chat-bubble-body {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow);
}

.chat-bubble.user .chat-bubble-body {
  background: var(--gradient-primary);
  color: white;
  border-bottom-right-radius: 4px;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.25);
}

/* Markdown */
.chat-bubble-body :deep(h1) { font-size: 1.3em; margin: 0 0 10px; font-weight: 700; }
.chat-bubble-body :deep(h2) { font-size: 1.2em; margin: 0 0 10px; font-weight: 700; }
.chat-bubble-body :deep(h3) { font-size: 1.1em; margin: 0 0 8px; font-weight: 600; }
.chat-bubble-body :deep(p) { margin: 0 0 8px; }
.chat-bubble-body :deep(p:last-child) { margin-bottom: 0; }
.chat-bubble-body :deep(ul), .chat-bubble-body :deep(ol) { margin: 0 0 8px; padding-left: 20px; }
.chat-bubble-body :deep(li) { margin-bottom: 4px; }
.chat-bubble-body :deep(code) { background: rgba(0,0,0,0.08); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.95em; }
.chat-bubble-body :deep(pre) { background: rgba(0,0,0,0.08); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 0 0 8px; }
.chat-bubble-body :deep(pre code) { background: none; padding: 0; }
.chat-bubble-body :deep(blockquote) { border-left: 3px solid var(--primary); margin: 0 0 8px; padding: 4px 12px; color: var(--text-secondary); }
.chat-bubble-body :deep(strong) { font-weight: 600; }

/* 输入中动画 */
.typing-dots { display: flex; gap: 6px; padding: 8px 4px; }
.typing-dots span { width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; animation: bounce 1.4s ease-in-out infinite both; }
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

/* 输入区 */
.chat-input-area {
  padding: 20px 28px 24px;
  border-top: 1px solid var(--border);
  background: var(--bg-card);
}

.chat-input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input-row textarea {
  flex: 1;
  padding: 16px 20px;
  background: var(--bg-card);
  border: 2px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: 17px;
  font-family: inherit;
  resize: none;
  max-height: 120px;
  min-height: 50px;
  line-height: 1.5;
  transition: all var(--transition-normal);
}

.chat-input-row textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.chat-input-row textarea::placeholder { color: var(--text-muted); }

.chat-send-btn {
  width: 50px;
  height: 50px;
  border-radius: var(--radius-lg);
  border: none;
  background: var(--gradient-primary);
  color: white;
  cursor: pointer;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition-normal);
}

.chat-send-btn:hover:not(:disabled) { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(99, 102, 241, 0.35); }
.chat-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.chat-input-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
}

/* 加载状态 */
.state-block {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 响应式 */
@media (max-width: 1200px) {
  .chat-page-layout {
    display: block;
    height: calc(100dvh - var(--nav-height) - 16px);
    max-height: calc(100dvh - var(--nav-height) - 16px);
    min-height: 0;
  }
  .chat-page-layout .page-sidebar {
    position: fixed;
    top: calc(var(--nav-height) + 12px);
    left: 12px;
    right: 12px;
    z-index: 30;
    width: auto;
    height: min(68dvh, 560px);
    max-height: min(68dvh, 560px);
    transform: translateY(-12px);
    opacity: 0;
    pointer-events: none;
    box-shadow: var(--shadow-xl);
  }
  .chat-sidebar--open {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
  .chat-sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 20;
    border: 0;
    background: rgba(15, 23, 42, 0.32);
    backdrop-filter: blur(2px);
  }
  .chat-main { height: 100%; }
  .chat-mobile-toolbar {
    display: flex;
    flex-shrink: 0;
    justify-content: flex-end;
    margin-bottom: 12px;
  }
  .chat-mobile-toggle {
    min-height: 42px;
    padding: 0 14px;
  }
  .chat-header { padding: 16px 20px; flex-direction: column; align-items: stretch; }
  .chat-header-info { width: 100%; align-items: flex-start; }
  .chat-header-actions { width: 100%; justify-content: flex-end; }
  .chat-avatar { font-size: 36px; }
  .chat-title { font-size: 20px; }
  .chat-messages { padding: 20px; gap: 14px; }
  .chat-bubble-body { padding: 14px 16px; font-size: 16px; }
  .chat-input-area { padding: 16px 20px 20px; }
  .chat-input-row textarea { padding: 14px 16px; font-size: 16px; }
  .chat-send-btn { width: 44px; height: 44px; font-size: 20px; }
}

@media (max-width: 480px) {
  .chat-page-layout {
    height: calc(100dvh - var(--nav-height) - 12px);
    max-height: calc(100dvh - var(--nav-height) - 12px);
  }
  .chat-page-layout .page-sidebar {
    top: calc(var(--nav-height) + 8px);
    left: 8px;
    right: 8px;
    height: min(72dvh, 520px);
    max-height: min(72dvh, 520px);
  }
  .chat-container { border-radius: 16px; }
  .chat-header { padding: 12px 16px; }
  .chat-header-info { gap: 12px; }
  .chat-header-actions .btn-ghost { flex: 1 1 calc(50% - 4px); justify-content: center; }
  .chat-avatar { font-size: 32px; }
  .chat-title { font-size: 18px; }
  .assessment-select { max-width: 100%; }
  .chat-empty-state { min-height: 280px; padding: 32px 16px; }
  .chat-messages { padding: 16px; gap: 12px; }
  .chat-bubble { max-width: 100%; gap: 10px; }
  .chat-bubble-body { padding: 12px 14px; font-size: 14px; }
  .chat-input-area { padding: 12px 16px 16px; }
  .chat-input-row { align-items: stretch; }
  .chat-input-row textarea { padding: 12px 14px; font-size: 14px; }
  .chat-send-btn { width: 40px; height: 40px; font-size: 18px; }
  .chat-bubble-avatar { width: 36px; height: 36px; font-size: 20px; }
  .chat-bubble.user .chat-bubble-avatar { font-size: 14px; }
}
</style>
