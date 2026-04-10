<template>
  <div class="page-layout">
    <!-- 左侧：对话导航 -->
    <aside v-if="!loading && messages.length" class="page-sidebar">
      <div class="sidebar-header">
        <h3>对话记录</h3>
        <p>{{ messages.length }} 条消息</p>
      </div>
      <div class="sidebar-actions">
        <button class="btn-danger" style="width:100%" @click="clearChat">清空当前对话</button>
      </div>
      <div class="sidebar-list">
        <button
          v-for="(msg, index) in messages"
          :key="`nav-${index}`"
          class="sidebar-item"
          :class="{ 'sidebar-item--user': msg.role === 'user' }"
          @click="scrollToMessage(index)"
        >
          <span class="sidebar-item-meta">{{ msg.role === 'user' ? '我' : '顾问' }}</span>
          <span class="sidebar-item-title">{{ previewText(msg.content, index) }}</span>
        </button>
      </div>
    </aside>

    <!-- 右侧：聊天主区域 -->
    <div class="chat-main">
      <div class="chat-container">
        <div class="chat-header">
          <div class="chat-header-info">
            <span class="chat-avatar">🧑‍⚕️</span>
            <div>
              <h2 class="chat-title">AI心理顾问</h2>
              <p class="chat-subtitle">基于你的测评结果为你提供心理支持</p>
            </div>
          </div>
          <div class="chat-header-actions">
            <button class="btn-ghost" @click="clearChat">🗑️</button>
            <button class="btn-ghost" @click="backToHistory">✕</button>
          </div>
        </div>

        <div class="chat-messages" ref="messagesRef">
          <div v-if="loading" class="state-block">
            <div class="spinner"></div>
            <p>正在连接心理顾问...</p>
          </div>

          <template v-else>
            <div
              v-for="(msg, index) in messages"
              :id="`chat-msg-${index}`"
              :key="index"
              :class="['chat-bubble', msg.role]"
            >
              <div class="chat-bubble-avatar">
                {{ msg.role === 'user' ? '👤' : '🧑‍⚕️' }}
              </div>
              <div class="chat-bubble-body">
                <div class="chat-bubble-text" v-html="formatMessage(msg.content)"></div>
              </div>
            </div>

            <div v-if="sending" class="chat-bubble assistant typing">
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
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()
const sessionId = ref(parseInt(route.query.sessionId) || 0)

const messages = ref([])
const inputMessage = ref('')
const loading = ref(true)
const sending = ref(false)
const messagesRef = ref(null)
const inputRef = ref(null)

const initChat = async () => {
  loading.value = true
  try {
    const res = await api.post('/chat/start', { session_id: sessionId.value, message: '' })
    messages.value = res.data.messages?.length
      ? res.data.messages
      : [{ role: 'assistant', content: res.data.welcome }]
  } catch (err) {
    console.error('初始化对话失败:', err)
    messages.value = [{
      role: 'assistant',
      content: '你好！我是你的AI心理顾问。我已经了解了你的测评结果，很高兴能和你交流。有什么想聊的吗？'
    }]
  } finally {
    loading.value = false
  }
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return

  const optimistic = [...messages.value, { role: 'user', content: text }]
  messages.value = optimistic
  inputMessage.value = ''
  sending.value = true
  resetTextarea()

  try {
    const res = await api.post('/chat/send', { session_id: sessionId.value, message: text })
    messages.value = res.data.messages?.length
      ? res.data.messages
      : [...optimistic, { role: 'assistant', content: res.data.reply }]
  } catch (err) {
    console.error('发送消息失败:', err)
    messages.value = [...optimistic, { role: 'assistant', content: '抱歉，我刚才走神了。能再说一遍吗？' }]
  } finally {
    sending.value = false
  }
}

const clearChat = async () => {
  if (!confirm('确定要清空对话历史吗？')) return
  try {
    await api.post('/chat/clear', { session_id: sessionId.value, message: '' })
    messages.value = []
    await initChat()
  } catch (err) {
    console.error('清空对话失败:', err)
  }
}

const backToHistory = () => router.push('/history')

const previewText = (text, index) => {
  const cleaned = (text || '').replace(/\s+/g, ' ').trim()
  if (!cleaned) return `消息 ${index + 1}`
  return cleaned.length > 28 ? `${cleaned.slice(0, 28)}...` : cleaned
}

const scrollToMessage = (index) => {
  const el = document.getElementById(`chat-msg-${index}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const formatMessage = (text) => {
  if (!text) return ''
  return marked.parse(text.replace(/^[ \t]+/gm, ''), { breaks: true })
}

const autoResize = () => {
  const el = inputRef.value
  if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px' }
}

const resetTextarea = () => {
  const el = inputRef.value
  if (el) el.style.height = 'auto'
}

watch(() => messages.value.length, () => {
  nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight })
})

onMounted(() => initChat())
</script>

<style scoped>
/* 侧栏角色区分 */
.sidebar-item--user { border-left: 3px solid rgba(99, 102, 241, 0.5); }
.sidebar-item:not(.sidebar-item--user) { border-left: 3px solid rgba(6, 182, 212, 0.5); }

/* 主聊天区 */
.chat-main {
  width: 100%;
  height: calc(100vh - 100px);
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
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
}

.chat-header-info {
  display: flex;
  align-items: center;
  gap: 16px;
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
}

/* 消息区 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: var(--bg-hover);
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

.chat-bubble-body {
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  font-size: 17px;
  line-height: 1.7;
  max-width: 100%;
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

/* 响应式 */
@media (max-width: 768px) {
  .chat-main { height: calc(100vh - 72px); }
  .chat-header { padding: 16px 20px; }
  .chat-avatar { font-size: 36px; }
  .chat-title { font-size: 20px; }
  .chat-messages { padding: 20px; gap: 14px; }
  .chat-bubble-body { padding: 14px 16px; font-size: 16px; }
  .chat-input-area { padding: 16px 20px 20px; }
  .chat-input-row textarea { padding: 14px 16px; font-size: 16px; }
  .chat-send-btn { width: 44px; height: 44px; font-size: 20px; }
}
</style>
