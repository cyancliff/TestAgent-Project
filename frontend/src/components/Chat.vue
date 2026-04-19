<template>
  <div class="chat-workspace">
    <aside :class="['chat-sidebar', { 'chat-sidebar--open': mobileSidebarOpen }]">
      <div class="chat-sidebar-top">
        <div class="chat-home-link">
          <img :src="atmrLogo" class="chat-home-mark" alt="ATMR logo" />
          <span class="chat-home-copy">
            <strong>ATMR AI</strong>
            <small>心理顾问</small>
          </span>
        </div>
        <button class="chat-sidebar-close" type="button" aria-label="关闭会话列表" @click="closeMobileSidebar">✕</button>
      </div>

      <button class="chat-new-button" type="button" @click="createNewSession">+ 新建对话</button>

      <div class="chat-assessment-panel">
        <label class="chat-assessment-label" for="chat-assessment-select">关联测评结果</label>
        <select
          id="chat-assessment-select"
          class="chat-assessment-select"
          :value="currentAssessmentId || 0"
          @change="changeAssessment($event.target.value)"
        >
          <option :value="0">不关联测评</option>
          <option
            v-for="assessment in availableAssessments"
            :key="assessment.session_id"
            :value="assessment.session_id"
          >
            {{ formatAssessmentOptionLabel(assessment) }}
          </option>
        </select>
        <p class="chat-assessment-hint">{{ currentAssessmentLabel }}</p>
      </div>

      <div class="chat-sidebar-section">
        <div class="chat-sidebar-label">最近会话</div>
        <div class="chat-session-list">
          <div
            v-for="session in chatSessions"
            :key="session.id"
            :class="['chat-session-item', { active: activeChatId === session.id, 'chat-session-item--menu-open': openSessionMenuId === session.id }]"
          >
            <button class="chat-session-main" type="button" @click="switchSession(session.id)">
              <span class="chat-session-item-title">{{ session.title || '新对话' }}</span>
              <span class="chat-session-item-meta">
                {{ session.assessment_info?.title || (session.assessment_session_id ? '已关联测评' : '未关联测评') }}
                · {{ session.message_count }} 条消息
              </span>
            </button>

            <div class="chat-session-actions">
              <button
                class="chat-session-menu-trigger"
                type="button"
                :aria-expanded="openSessionMenuId === session.id"
                aria-label="管理对话"
                @click.stop="toggleSessionMenu(session.id)"
              >
                ⋯
              </button>

              <div v-if="openSessionMenuId === session.id" class="chat-session-menu">
                <button class="chat-session-menu-item" type="button" @click.stop="renameSession(session)">
                  重命名
                </button>
                <button class="chat-session-menu-item chat-session-menu-item--danger" type="button" @click.stop="deleteSession(session.id)">
                  删除对话
                </button>
              </div>
            </div>
          </div>

          <div v-if="!chatSessions.length" class="chat-session-empty">
            还没有咨询会话，先新建一个开始吧。
          </div>
        </div>
      </div>

      <div class="chat-sidebar-footer">
        <div class="chat-user-chip">
          <div class="chat-user-avatar">
            <img v-if="userAvatarUrl" :src="userAvatarUrl" alt="" @error="handleAvatarError" />
            <span v-else>{{ usernameInitial }}</span>
          </div>
          <div class="chat-user-copy">
            <strong>{{ nickname }}</strong>
            <span>{{ userHandle }}</span>
          </div>
        </div>
      </div>
    </aside>

    <button
      v-if="mobileSidebarOpen"
      class="chat-sidebar-backdrop"
      type="button"
      aria-label="关闭会话列表"
      @click="closeMobileSidebar"
    ></button>

    <section class="chat-stage">
      <header class="chat-stage-header">
        <div class="chat-stage-heading">
          <button class="chat-mobile-trigger" type="button" aria-label="打开会话列表" @click="toggleMobileSidebar">☰</button>
          <div class="chat-stage-titles">
            <h1>{{ activeSessionTitle }}</h1>
            <p>{{ activeSessionDescription }}</p>
          </div>
        </div>
      </header>

      <div class="chat-thread" ref="messagesRef">
        <div class="chat-thread-inner">
          <div v-if="loadingMessages" class="state-block chat-loading-state">
            <div class="spinner"></div>
            <p>正在加载对话...</p>
          </div>

          <section v-else-if="!activeChatId" class="chat-landing">
            <div class="chat-landing-badge">ATMR AI 心理顾问</div>
            <h2>从一次对话开始</h2>
            <p>新建一个会话后，你可以围绕测评结果、情绪波动、目标压力或人际关系继续追问。</p>

            <div class="chat-landing-actions">
              <button class="chat-primary-button" type="button" @click="createNewSession">新建对话</button>
              <button class="chat-secondary-button" type="button" @click="goToHistory">查看历史</button>
            </div>

            <div class="chat-prompt-grid">
              <button
                v-for="prompt in starterPrompts"
                :key="prompt.title"
                class="chat-prompt-card"
                type="button"
                @click="preparePrompt(prompt.text)"
              >
                <span class="chat-prompt-title">{{ prompt.title }}</span>
                <span class="chat-prompt-text">{{ prompt.text }}</span>
              </button>
            </div>
          </section>

          <section v-else-if="!messages.length" class="chat-landing chat-landing--session">
            <div class="chat-landing-badge">{{ currentAssessmentLabel }}</div>
            <h2>{{ activeSessionTitle }}</h2>
            <p>输入你的第一个问题，或先从下面的快捷提问开始。</p>

            <div class="chat-prompt-grid">
              <button
                v-for="prompt in starterPrompts"
                :key="prompt.title"
                class="chat-prompt-card"
                type="button"
                @click="preparePrompt(prompt.text)"
              >
                <span class="chat-prompt-title">{{ prompt.title }}</span>
                <span class="chat-prompt-text">{{ prompt.text }}</span>
              </button>
            </div>
          </section>

          <div v-else class="chat-feed">
            <div
              v-for="(msg, index) in messages"
              :id="`chat-msg-${index}`"
              :key="index"
              :class="['chat-message-row', msg.role]"
            >
              <div
                :class="[
                  'chat-role-tag',
                  {
                    'chat-role-tag--user': msg.role === 'user',
                    'chat-role-tag--user-avatar': msg.role === 'user' && userAvatarUrl,
                    'chat-role-tag--assistant-avatar': msg.role === 'assistant',
                  },
                ]"
              >
                <img
                  v-if="msg.role === 'assistant'"
                  :src="atmrLogo"
                  alt="ATMR logo"
                />
                <img v-else-if="msg.role === 'user' && userAvatarUrl" :src="userAvatarUrl" alt="" @error="handleAvatarError" />
                <template v-else>{{ usernameInitial }}</template>
              </div>

              <div class="chat-message-card">
                <div
                  v-if="isPendingAssistantMessage(msg, index)"
                  class="typing-dots"
                  aria-label="AI 正在输入"
                  role="status"
                >
                  <span></span><span></span><span></span>
                </div>
                <div v-else class="chat-message-content" v-html="formatMessage(msg.content)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <footer class="chat-composer-shell">
        <div class="chat-composer">
          <textarea
            ref="inputRef"
            v-model="inputMessage"
            :disabled="sending"
            :placeholder="activeChatId ? '给 ATMR AI 发送消息' : '发送第一条消息后自动创建对话'"
            rows="1"
            @keydown="handleInputKeydown"
            @input="autoResize"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
          ></textarea>

          <div class="chat-composer-footer">
            <p class="chat-composer-hint">
              {{ activeChatId ? 'Enter 发送，Shift + Enter 换行' : 'Enter 发送首条消息，并自动创建对话' }}
            </p>
            <button
              class="chat-send-button"
              type="button"
              :disabled="!inputMessage.trim() || sending"
              @click="sendMessage"
            >
              {{ sending ? '思考中…' : '发送' }}
            </button>
          </div>
        </div>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import api from '../api'
import { buildApiUrl, resolveBackendUrl } from '../config'
import atmrLogo from '../assets/atmr-logo.png'
import { showAlertDialog, showConfirmDialog, showPromptDialog } from '../composables/useAppDialog'

const route = useRoute()
const router = useRouter()

const readStoredNickname = () => localStorage.getItem('nickname') || localStorage.getItem('username') || '用户'
const readStoredLoginAccount = () => localStorage.getItem('loginAccount') || localStorage.getItem('username') || 'user'
const readStoredAvatarUrl = () => resolveBackendUrl(localStorage.getItem('avatarUrl') || '')
const nickname = ref(readStoredNickname())
const loginAccount = ref(readStoredLoginAccount())
const userAvatarUrl = ref(readStoredAvatarUrl())
const usernameInitial = computed(() => (nickname.value || '?')[0].toUpperCase())
const userHandle = computed(() => `@${loginAccount.value || 'user'}`)

const chatSessions = ref([])
const activeChatId = ref(null)
const currentAssessmentId = ref(null)
const currentAssessmentInfo = ref(null)
const availableAssessments = ref([])
const messages = ref([])
const inputMessage = ref('')
const loadingMessages = ref(false)
const sending = ref(false)
const isComposing = ref(false)
const messagesRef = ref(null)
const inputRef = ref(null)
const mobileSidebarOpen = ref(false)
const openSessionMenuId = ref(null)

let activeStreamController = null

const starterPrompts = [
  { title: '分析测评结果', text: '请结合我的测评结果，先给我一个整体分析。' },
  { title: '缓解焦虑压力', text: '最近压力比较大，你建议我怎么调整情绪和节奏？' },
  { title: '制定行动计划', text: '请根据我的情况，给我一个未来两周可执行的改善计划。' },
  { title: '关系与沟通', text: '我在人际沟通上容易紧张，你建议我先从哪里改起？' },
]

const ALLOWED_MARKDOWN_TAGS = new Set([
  'a',
  'blockquote',
  'br',
  'code',
  'del',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'li',
  'ol',
  'p',
  'pre',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'ul',
])
const BLOCKED_MARKDOWN_TAGS = new Set(['button', 'embed', 'form', 'iframe', 'input', 'object', 'script', 'select', 'style', 'textarea'])
const SAFE_LINK_PATTERN = /^(https?:|mailto:|tel:|\/|#)/i

const currentSession = computed(() => chatSessions.value.find((session) => session.id === activeChatId.value) || null)
const lookupAssessmentById = (assessmentId) => {
  const normalizedId = Number(assessmentId) || 0
  if (!normalizedId) return null

  return (
    availableAssessments.value.find((assessment) => assessment.session_id === normalizedId)
    || (currentSession.value?.assessment_info?.session_id === normalizedId ? currentSession.value.assessment_info : null)
    || (currentAssessmentInfo.value?.session_id === normalizedId ? currentAssessmentInfo.value : null)
    || null
  )
}
const getAssessmentDisplayName = (assessment) => {
  if (!assessment) return ''
  const title = String(assessment.title || '').trim()
  return title || (assessment.session_id ? `测评 #${assessment.session_id}` : '未命名测评')
}
const currentAssessment = computed(() => lookupAssessmentById(currentAssessmentId.value))
const currentAssessmentLabel = computed(() => (
  !activeChatId.value
    ? currentAssessmentId.value
      ? `首条消息将关联「${getAssessmentDisplayName(currentAssessment.value)}」`
      : '发送首条消息后自动创建对话'
    : currentAssessmentId.value
    ? `已关联「${getAssessmentDisplayName(currentAssessment.value)}」`
    : '未关联测评'
))
const activeSessionTitle = computed(() => {
  if (!activeChatId.value) return 'ATMR AI 心理顾问'
  return currentSession.value?.title || `咨询会话 #${activeChatId.value}`
})
const activeSessionDescription = computed(() => {
  if (!activeChatId.value) {
    return currentAssessmentId.value
      ? `发送第一条消息后会自动创建对话，并关联「${getAssessmentDisplayName(currentAssessment.value)}」`
      : '围绕测评结果、情绪压力和行动建议继续追问'
  }

  const messageCount = messages.value.length || currentSession.value?.message_count || 0
  return `${currentAssessmentLabel.value} · ${messageCount} 条消息`
})

const syncLocalUser = () => {
  nickname.value = readStoredNickname()
  loginAccount.value = readStoredLoginAccount()
  userAvatarUrl.value = readStoredAvatarUrl()
}

const fetchSessions = async () => {
  try {
    const res = await api.get('/chat/sessions')
    chatSessions.value = res.data.sessions
    if (activeChatId.value) {
      currentAssessmentInfo.value = chatSessions.value.find((session) => session.id === activeChatId.value)?.assessment_info || currentAssessmentInfo.value
    }
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

let skipNextRouteLoadChatId = null

const createPersistedSession = async (assessmentSessionId = null) => {
  try {
    const payload = {}
    if (assessmentSessionId && typeof assessmentSessionId === 'number') {
      payload.assessment_session_id = assessmentSessionId
    }
    const res = await api.post('/chat/sessions', payload)
    activeChatId.value = res.data.id
    currentAssessmentId.value = payload.assessment_session_id || null
    currentAssessmentInfo.value = res.data.assessment_info || lookupAssessmentById(payload.assessment_session_id)
    messages.value = []
    skipNextRouteLoadChatId = res.data.id
    await fetchSessions()
    mobileSidebarOpen.value = false
    await router.replace(`/chat/${res.data.id}`)
    return res.data.id
  } catch (err) {
    console.error('创建会话失败:', err)
    const detail = err.response?.data?.detail || err.message || '未知错误'

    if (assessmentSessionId && typeof assessmentSessionId === 'number') {
      try {
        const fallback = await api.post('/chat/sessions', {})
        activeChatId.value = fallback.data.id
        currentAssessmentId.value = null
        currentAssessmentInfo.value = null
        messages.value = []
        skipNextRouteLoadChatId = fallback.data.id
        await fetchSessions()
        mobileSidebarOpen.value = false
        await router.replace(`/chat/${fallback.data.id}`)
        await showAlertDialog(`关联测评失败，已为你创建普通咨询会话：${detail}`, {
          title: '关联失败',
        })
        return fallback.data.id
      } catch (fallbackErr) {
        console.error('普通咨询会话创建也失败:', fallbackErr)
      }
    }

    await showAlertDialog(`创建会话失败：${detail}`, {
      title: '创建失败',
      destructive: true,
    })
    return null
  }
}

const createNewSession = async (assessmentSessionId = null) => {
  cancelActiveStream()
  closeSessionMenu()
  mobileSidebarOpen.value = false
  activeChatId.value = null
  currentAssessmentId.value = assessmentSessionId && typeof assessmentSessionId === 'number' ? assessmentSessionId : null
  currentAssessmentInfo.value = lookupAssessmentById(currentAssessmentId.value)
  messages.value = []
  inputMessage.value = ''
  resetTextarea()

  const nextQuery = currentAssessmentId.value ? { assessmentSessionId: currentAssessmentId.value } : {}
  await router.push({ path: '/chat', query: nextQuery })
  await nextTick()
  inputRef.value?.focus()
}

const preparePrompt = async (prompt) => {
  inputMessage.value = prompt
  await nextTick()
  autoResize()
  inputRef.value?.focus()
}

const switchSession = (id) => {
  openSessionMenuId.value = null
  mobileSidebarOpen.value = false
  router.push(`/chat/${id}`)
}

const toggleMobileSidebar = () => {
  mobileSidebarOpen.value = !mobileSidebarOpen.value
}

const closeMobileSidebar = () => {
  mobileSidebarOpen.value = false
}

const goToHistory = () => {
  mobileSidebarOpen.value = false
  router.push('/history')
}

const closeSessionMenu = () => {
  openSessionMenuId.value = null
}

const toggleSessionMenu = (sessionId) => {
  openSessionMenuId.value = openSessionMenuId.value === sessionId ? null : sessionId
}

const renameSession = async (session) => {
  closeSessionMenu()
  const initialTitle = (session.title || '').trim()
  const nextTitle = await showPromptDialog({
    title: '重命名对话',
    message: '输入新的对话标题',
    inputLabel: '对话标题',
    inputPlaceholder: '请输入新的对话标题',
    initialValue: initialTitle,
    inputMaxLength: 100,
    confirmText: '保存',
  })
  if (nextTitle === null) return

  const normalizedTitle = nextTitle.trim().slice(0, 100)
  if (!normalizedTitle || normalizedTitle === initialTitle) return

  try {
    await api.put(`/chat/sessions/${session.id}`, {
      title: normalizedTitle,
    })
    await fetchSessions()
  } catch (err) {
    console.error('重命名会话失败:', err)
    await showAlertDialog(err.response?.data?.detail || '重命名失败', {
      title: '重命名失败',
      destructive: true,
    })
  }
}

const deleteSession = async (sessionId) => {
  if (!sessionId) return
  closeSessionMenu()
  const shouldDelete = await showConfirmDialog('确定要删除这个咨询会话吗？所有消息将被清除。', {
    title: '删除对话',
    confirmText: '删除',
    cancelText: '取消',
    destructive: true,
  })
  if (!shouldDelete) return

  try {
    await api.delete(`/chat/sessions/${sessionId}`)

    if (activeChatId.value === sessionId) {
      activeChatId.value = null
      currentAssessmentId.value = null
      currentAssessmentInfo.value = null
      messages.value = []
      await router.push('/chat')
    }

    await fetchSessions()
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
    currentAssessmentInfo.value = res.data.assessment_info || lookupAssessmentById(res.data.assessment_session_id)
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

const isPendingAssistantMessage = (msg, index) => (
  sending.value
  && msg.role === 'assistant'
  && index === messages.value.length - 1
  && !String(msg.content || '').trim()
)

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
  localStorage.removeItem('nickname')
  localStorage.removeItem('loginAccount')
  localStorage.removeItem('avatarUrl')
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

const handleCompositionStart = () => {
  isComposing.value = true
}

const handleCompositionEnd = () => {
  isComposing.value = false
}

const handleInputKeydown = (event) => {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  if (event.isComposing || isComposing.value) return

  event.preventDefault()
  sendMessage()
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return

  let chatId = activeChatId.value
  if (!chatId) {
    chatId = await createPersistedSession(currentAssessmentId.value)
    if (!chatId) return
  }

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

    const response = await fetch(buildApiUrl(`/chat/sessions/${chatId}/stream`), {
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
    await loadMessages(chatId)
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

const changeAssessment = async (value) => {
  const newId = parseInt(value, 10) || 0
  if (!activeChatId.value) {
    currentAssessmentId.value = newId || null
    currentAssessmentInfo.value = lookupAssessmentById(newId)
    return
  }

  try {
    const res = await api.put(`/chat/sessions/${activeChatId.value}`, {
      assessment_session_id: newId,
    })
    currentAssessmentId.value = newId || null
    currentAssessmentInfo.value = res.data?.assessment_info || lookupAssessmentById(newId)
    await loadMessages(activeChatId.value)
    await fetchSessions()
  } catch (err) {
    console.error('切换关联测评失败:', err)
    await showAlertDialog('切换失败', {
      title: '关联失败',
      destructive: true,
    })
  }
}

const sanitizeRenderedMarkdown = (html) => {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const nodes = [...doc.body.querySelectorAll('*')]

  for (const node of nodes) {
    const tag = node.tagName.toLowerCase()

    if (BLOCKED_MARKDOWN_TAGS.has(tag)) {
      node.remove()
      continue
    }

    if (!ALLOWED_MARKDOWN_TAGS.has(tag)) {
      node.replaceWith(...Array.from(node.childNodes))
      continue
    }

    for (const attr of [...node.attributes]) {
      const name = attr.name.toLowerCase()
      const value = attr.value.trim()

      if (tag === 'a' && name === 'href') {
        if (SAFE_LINK_PATTERN.test(value)) {
          node.setAttribute('target', '_blank')
          node.setAttribute('rel', 'noopener noreferrer')
        } else {
          node.removeAttribute(attr.name)
        }
        continue
      }

      if (tag === 'a' && (name === 'rel' || name === 'target' || name === 'title')) {
        continue
      }

      node.removeAttribute(attr.name)
    }
  }

  return doc.body.innerHTML
}

const formatMessage = (text) => {
  if (!text) return ''
  return sanitizeRenderedMarkdown(marked.parse(text, { breaks: true, gfm: true }))
}

const formatDate = (isoStr) => {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const formatAssessmentOptionLabel = (assessment) => {
  const title = getAssessmentDisplayName(assessment)
  const dateLabel = formatDate(assessment.started_at)
  const suffix = assessment.has_report ? '' : ' [无报告]'
  return dateLabel ? `${title} · ${dateLabel}${suffix}` : `${title}${suffix}`
}

const autoResize = () => {
  const el = inputRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
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

const handleUserProfileUpdated = () => {
  syncLocalUser()
}

const handleStorageChange = (event) => {
  if (!event.key || ['username', 'nickname', 'loginAccount', 'avatarUrl'].includes(event.key)) {
    syncLocalUser()
  }
}

const handleDocumentClick = (event) => {
  const target = event.target instanceof Element ? event.target : null
  if (!target?.closest('.chat-session-actions')) {
    closeSessionMenu()
  }
}

watch(() => messages.value.length, () => {
  scrollMessagesToBottom()
})

watch(
  () => route.params.chatId,
  async (newId) => {
    cancelActiveStream()
    closeMobileSidebar()
    closeSessionMenu()
    if (newId) {
      const parsedId = parseInt(newId, 10)
      activeChatId.value = parsedId
      if (skipNextRouteLoadChatId === parsedId) {
        skipNextRouteLoadChatId = null
        return
      }
      await loadMessages(activeChatId.value)
    } else {
      activeChatId.value = null
      currentAssessmentId.value = parseInt(route.query.assessmentSessionId, 10) || null
      currentAssessmentInfo.value = lookupAssessmentById(currentAssessmentId.value)
      messages.value = []
    }
  },
  { immediate: true }
)

onMounted(async () => {
  syncLocalUser()
  document.addEventListener('click', handleDocumentClick)
  window.addEventListener('user-profile-updated', handleUserProfileUpdated)
  window.addEventListener('storage', handleStorageChange)
  await Promise.all([fetchSessions(), fetchAssessments()])
})

onBeforeUnmount(() => {
  cancelActiveStream()
  document.removeEventListener('click', handleDocumentClick)
  window.removeEventListener('user-profile-updated', handleUserProfileUpdated)
  window.removeEventListener('storage', handleStorageChange)
})
</script>

<style scoped>
.chat-workspace {
  display: grid;
  grid-template-columns: 296px minmax(0, 1fr);
  height: 100%;
  min-height: 100%;
  max-height: 100%;
  background: #ffffff;
  overflow: hidden;
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  gap: 14px;
  padding: 16px 14px;
  background: #f7f7f8;
  border-right: 1px solid #e5e7eb;
  overflow: hidden;
}

.chat-sidebar-top,
.chat-stage-header,
.chat-stage-heading,
.chat-landing-actions,
.chat-message-row,
.chat-composer-footer,
.chat-user-chip {
  display: flex;
  align-items: center;
}

.chat-sidebar-top {
  justify-content: space-between;
  gap: 12px;
}

.chat-home-link {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: #111827;
  text-align: left;
}

.chat-home-mark,
.chat-role-tag,
.chat-user-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.chat-home-mark {
  width: 46px;
  height: 46px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 6px 14px rgba(17, 24, 39, 0.12));
}

.chat-home-copy,
.chat-user-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-home-copy strong,
.chat-user-copy strong {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.chat-home-copy small,
.chat-user-copy span {
  font-size: 12px;
  color: #6b7280;
}

.chat-sidebar-close,
.chat-mobile-trigger {
  display: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #ffffff;
  color: #111827;
  cursor: pointer;
  flex-shrink: 0;
}

.chat-new-button {
  width: 100%;
  min-height: 48px;
  border: 0;
  border-radius: 16px;
  background: #111827;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.chat-new-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 30px rgba(17, 24, 39, 0.16);
}

.chat-assessment-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #ffffff;
}

.chat-assessment-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #6b7280;
  text-transform: uppercase;
}

.chat-prompt-grid {
  display: grid;
  gap: 12px;
}

.chat-sidebar-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-sidebar-label {
  padding: 0 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #6b7280;
  text-transform: uppercase;
}

.chat-session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.chat-session-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 16px;
  background: transparent;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
  position: relative;
  z-index: 0;
}

.chat-session-item:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: #e5e7eb;
  transform: translateY(-1px);
}

.chat-session-item.active {
  background: #ffffff;
  border-color: #d4d4d8;
  box-shadow: 0 10px 30px rgba(17, 17, 17, 0.08);
}

.chat-session-item--menu-open {
  z-index: 20;
  transform: none;
}

.chat-session-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  border: 0;
  background: transparent;
  color: #111827;
  text-align: left;
  cursor: pointer;
}

.chat-session-item-title {
  font-size: 14px;
  font-weight: 700;
}

.chat-session-actions {
  position: relative;
  flex-shrink: 0;
  z-index: 2;
}

.chat-session-menu-trigger {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #6b7280;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.chat-session-item:hover .chat-session-menu-trigger,
.chat-session-item.active .chat-session-menu-trigger,
.chat-session-item--menu-open .chat-session-menu-trigger {
  opacity: 1;
  pointer-events: auto;
}

.chat-session-menu-trigger:hover,
.chat-session-item--menu-open .chat-session-menu-trigger {
  background: rgba(17, 24, 39, 0.06);
  color: #111827;
}

.chat-session-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 132px;
  padding: 6px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
  z-index: 30;
}

.chat-session-menu-item {
  width: 100%;
  min-height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #111827;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.chat-session-menu-item:hover {
  background: #f3f4f6;
}

.chat-session-menu-item--danger {
  color: #ef4444;
}

.chat-session-menu-item--danger:hover {
  background: rgba(239, 68, 68, 0.08);
}

.chat-session-item-meta,
.chat-session-empty,
.chat-composer-hint,
.chat-stage-titles p,
.chat-landing p,
.chat-prompt-text {
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
}

.chat-session-empty {
  padding: 16px 12px;
  border: 1px dashed #d1d5db;
  border-radius: 16px;
}

.chat-sidebar-footer {
  display: flex;
  flex-direction: column;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.chat-user-chip {
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
}

.chat-user-avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #111827, #374151);
  color: #ffffff;
  font-weight: 700;
  overflow: hidden;
  flex-shrink: 0;
}

.chat-user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-stage {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #fcfcfd 100%);
}

.chat-stage-header {
  justify-content: space-between;
  gap: 18px;
  padding: 20px 24px 18px;
  border-bottom: 1px solid #eceef2;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(14px);
}

.chat-stage-heading {
  gap: 14px;
  min-width: 0;
  flex: 1;
}

.chat-stage-titles {
  min-width: 0;
}

.chat-stage-titles h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.chat-stage-titles p {
  margin: 4px 0 0;
}

.chat-assessment-select {
  width: 100%;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #ffffff;
  color: #111827;
  font-size: 13px;
}

.chat-assessment-select:focus {
  outline: none;
  border-color: #52525b;
  box-shadow: 0 0 0 4px rgba(17, 17, 17, 0.12);
}

.chat-assessment-select:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.chat-assessment-hint {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}

.chat-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 24px;
}

.chat-thread-inner {
  width: min(100%, 880px);
  min-height: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.chat-loading-state,
.chat-landing {
  margin: auto 0;
}

.chat-landing {
  padding: 56px 0 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.chat-landing-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.chat-landing h2 {
  margin: 18px 0 0;
  font-size: clamp(32px, 5vw, 54px);
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #111827;
}

.chat-landing p {
  max-width: 620px;
  margin: 14px 0 0;
  font-size: 16px;
}

.chat-landing-actions {
  gap: 12px;
  margin-top: 24px;
}

.chat-primary-button,
.chat-secondary-button,
.chat-send-button {
  border: 0;
  font-weight: 700;
  cursor: pointer;
}

.chat-primary-button,
.chat-secondary-button {
  min-height: 48px;
  padding: 0 20px;
  border-radius: 16px;
  font-size: 15px;
}

.chat-primary-button,
.chat-send-button {
  background: #111827;
  color: #ffffff;
}

.chat-secondary-button {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #111827;
}

.chat-prompt-grid {
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 26px;
}

.chat-prompt-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 116px;
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 22px;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
}

.chat-prompt-card:hover {
  transform: translateY(-2px);
  border-color: #d4d4d8;
  box-shadow: 0 18px 40px rgba(17, 17, 17, 0.08);
}

.chat-prompt-title {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.chat-feed {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 28px 0 48px;
}

.chat-message-row {
  gap: 16px;
  align-items: flex-start;
}

.chat-message-row.user {
  flex-direction: row-reverse;
}

.chat-role-tag {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: #111827;
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  flex-shrink: 0;
}

.chat-role-tag img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
  display: block;
}

.chat-role-tag--user {
  background: linear-gradient(135deg, #18181b, #000000);
}

.chat-role-tag--user-avatar {
  overflow: hidden;
  background: #e5e7eb;
}

.chat-role-tag--assistant-avatar {
  overflow: hidden;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 6px 14px rgba(17, 24, 39, 0.08);
}

.chat-message-card {
  min-width: 0;
  max-width: min(100%, 760px);
  padding: 18px 20px;
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
}

.chat-message-row.user .chat-message-card {
  max-width: min(82%, 680px);
  background: #111827;
  border-color: #111827;
  color: #ffffff;
  box-shadow: none;
}

.chat-message-content {
  min-width: 0;
  color: inherit;
  font-size: 16px;
  line-height: 1.75;
}

.chat-message-content :deep(p) { margin: 0 0 10px; }
.chat-message-content :deep(p:last-child) { margin-bottom: 0; }
.chat-message-content :deep(ul),
.chat-message-content :deep(ol) { margin: 0 0 10px; padding-left: 22px; }
.chat-message-content :deep(code) { padding: 2px 6px; border-radius: 8px; background: rgba(15, 23, 42, 0.08); }
.chat-message-row.user .chat-message-content :deep(code) { background: rgba(255, 255, 255, 0.14); }
.chat-message-content :deep(pre) { margin: 0 0 10px; padding: 14px 16px; border-radius: 16px; background: #111827; color: #f9fafb; overflow-x: auto; }
.chat-message-content :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.chat-message-content :deep(a) { color: #18181b; text-decoration: underline; }
.chat-message-row.user .chat-message-content :deep(a) { color: #e5e7eb; }
.chat-message-content :deep(blockquote) { margin: 0 0 10px; padding: 8px 14px; border-left: 3px solid #18181b; color: #6b7280; background: rgba(17, 17, 17, 0.06); }
.chat-message-row.user .chat-message-content :deep(blockquote) { color: #e5e7eb; background: rgba(255, 255, 255, 0.08); }

.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #9ca3af;
  animation: bounce 1.4s ease-in-out infinite both;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-composer-shell {
  padding: 0 24px 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, #ffffff 24%, #ffffff 100%);
}

.chat-composer {
  width: min(100%, 880px);
  margin: 0 auto;
  padding: 16px 18px 14px;
  border: 1px solid #dcdfe4;
  border-radius: 28px;
  background: #ffffff;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
}

.chat-composer textarea {
  width: 100%;
  border: 0;
  background: transparent;
  color: #111827;
  font-size: 16px;
  font-family: inherit;
  line-height: 1.6;
  resize: none;
  min-height: 56px;
  max-height: 180px;
}

.chat-composer textarea:focus { outline: none; }
.chat-composer textarea:disabled { cursor: not-allowed; opacity: 0.65; }
.chat-composer textarea::placeholder { color: #9ca3af; }

.chat-composer-footer {
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;
}

.chat-send-button {
  min-width: 88px;
  min-height: 40px;
  padding: 0 18px;
  border-radius: 999px;
  font-size: 14px;
}

.chat-send-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.chat-send-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.chat-sidebar-backdrop {
  display: none;
}

@media (max-width: 960px) {
  .chat-workspace {
    display: block;
  }

  .chat-sidebar {
    position: fixed;
    top: calc(var(--nav-height) + 12px);
    left: 12px;
    bottom: 12px;
    z-index: 40;
    width: min(82vw, 320px);
    transform: translateX(-100%);
    transition: transform 0.24s ease;
    box-shadow: 20px 0 50px rgba(15, 23, 42, 0.14);
    border: 1px solid #e5e7eb;
    border-radius: 22px;
  }

  .chat-sidebar--open {
    transform: translateX(0);
  }

  .chat-sidebar-close,
  .chat-mobile-trigger {
    display: inline-flex;
  }

  .chat-sidebar-backdrop {
    display: block;
    position: fixed;
    inset: var(--nav-height) 0 0 0;
    z-index: 30;
    border: 0;
    background: rgba(15, 23, 42, 0.28);
  }

  .chat-stage-header {
    padding: 16px;
  }

  .chat-thread,
  .chat-composer-shell {
    padding-left: 16px;
    padding-right: 16px;
  }

  .chat-prompt-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .chat-stage-header,
  .chat-landing-actions,
  .chat-composer-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .chat-feed {
    gap: 18px;
    padding: 20px 0 36px;
  }

  .chat-message-row {
    gap: 10px;
  }

  .chat-role-tag {
    width: 34px;
    height: 34px;
    border-radius: 12px;
    font-size: 11px;
  }

  .chat-message-card {
    padding: 14px 16px;
    border-radius: 20px;
  }

  .chat-message-row.user .chat-message-card {
    max-width: 92%;
  }

  .chat-composer {
    padding: 14px;
    border-radius: 24px;
  }

  .chat-send-button,
  .chat-primary-button,
  .chat-secondary-button {
    width: 100%;
  }
}
</style>
