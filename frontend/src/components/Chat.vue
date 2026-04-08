<template>
  <div class="chat-page">
    <div class="chat-container">
      <!-- 头部 -->
      <div class="chat-header">
        <div class="header-info">
          <span class="avatar">🧑‍⚕️</span>
          <div>
            <h2 class="chat-title">AI心理顾问</h2>
            <p class="chat-subtitle">基于你的测评结果为你提供心理支持</p>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn-icon" @click="clearChat" title="清空对话">🗑️</button>
          <button class="btn-icon" @click="backToHistory" title="返回">✕</button>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="messages-area" ref="messagesRef">
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>正在连接心理顾问...</p>
        </div>

        <template v-else>
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role]"
          >
            <div class="message-avatar">
              {{ msg.role === 'user' ? '👤' : '🧑‍⚕️' }}
            </div>
            <div class="message-content">
              <div class="message-text" v-html="formatMessage(msg.content)"></div>
            </div>
          </div>

          <div v-if="sending" class="message assistant typing">
            <div class="message-avatar">🧑‍⚕️</div>
            <div class="message-content">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-wrapper">
          <textarea
            v-model="inputMessage"
            placeholder="输入你的问题或感受..."
            rows="1"
            @keydown.enter.prevent="sendMessage"
            @input="autoResize"
            ref="inputRef"
          ></textarea>
          <button
            class="send-btn"
            :disabled="!inputMessage.trim() || sending"
            @click="sendMessage"
          >
            <span>➤</span>
          </button>
        </div>
        <p class="input-hint">按 Enter 发送，Shift + Enter 换行</p>
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

// 初始化对话
const initChat = async () => {
  try {
    const res = await api.post('/chat/start', {
      session_id: sessionId.value,
      message: ''
    })
    messages.value = [{ role: 'assistant', content: res.data.welcome }]
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

// 发送消息
const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  sending.value = true
  resetTextarea()

  try {
    const res = await api.post('/chat/send', {
      session_id: sessionId.value,
      message: text
    })
    messages.value.push({ role: 'assistant', content: res.data.reply })
  } catch (err) {
    console.error('发送消息失败:', err)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我刚才走神了。能再说一遍吗？'
    })
  } finally {
    sending.value = false
  }
}

// 清空对话
const clearChat = async () => {
  if (!confirm('确定要清空对话历史吗？')) return

  try {
    await api.post('/chat/clear', {
      session_id: sessionId.value,
      message: ''
    })
    messages.value = []
    initChat()
  } catch (err) {
    console.error('清空对话失败:', err)
  }
}

// 返回历史记录
const backToHistory = () => {
  router.push('/history')
}

// 格式化消息（支持 Markdown）
const formatMessage = (text) => {
  if (!text) return ''
  // 移除行首缩进，避免被识别为代码块
  const cleanedText = text.replace(/^[ \t]+/gm, '')
  // 使用 marked 渲染 Markdown
  const html = marked.parse(cleanedText, { breaks: true })
  return html
}

// 自动调整输入框高度
const autoResize = () => {
  const textarea = inputRef.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
  }
}

// 重置输入框高度
const resetTextarea = () => {
  const textarea = inputRef.value
  if (textarea) {
    textarea.style.height = 'auto'
  }
}

// 自动滚动到底部
watch(() => messages.value.length, () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
})

onMounted(() => {
  initChat()
})
</script>

<style scoped>
.chat-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  height: calc(100vh - 64px);
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

/* 头部 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-dark);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  font-size: 46px;
}

.chat-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.chat-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: var(--bg-hover);
  border-color: var(--primary);
}

/* 消息区 */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.message-content {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 18px;
  line-height: 1.6;
  max-width: 100%;
  overflow-wrap: break-word;
  text-align: left !important;
}

/* Markdown 样式 */
.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4) {
  margin: 0 0 12px 0;
  color: inherit;
  font-weight: 600;
}

.message-content :deep(h1) { font-size: 1.4em; }
.message-content :deep(h2) { font-size: 1.3em; }
.message-content :deep(h3) { font-size: 1.2em; }

.message-content :deep(p) {
  margin: 0 0 10px 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 0 0 10px 0;
  padding-left: 20px;
}

.message-content :deep(li) {
  margin-bottom: 4px;
}

.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 1em;
}

.message-content :deep(pre) {
  background: rgba(0, 0, 0, 0.1);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0 0 10px 0;
}

.message-content :deep(pre code) {
  background: none;
  padding: 0;
}

.message-content :deep(blockquote) {
  border-left: 3px solid var(--primary);
  margin: 0 0 10px 0;
  padding: 4px 12px;
  color: var(--text-secondary);
}

.message-content :deep(strong) {
  font-weight: 600;
}

.message.assistant .message-content {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.message.user .message-content {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  border-bottom-right-radius: 4px;
}

/* 输入中动画 */
.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 8px 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: bounce 1.4s ease-in-out infinite both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 输入区 */
.input-area {
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-dark);
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper textarea {
  flex: 1;
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  color: var(--text-primary);
  font-size: 18px;
  resize: none;
  max-height: 120px;
  min-height: 48px;
  line-height: 1.5;
  transition: all 0.2s;
}

.input-wrapper textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.input-wrapper textarea::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-btn span {
  font-size: 24px;
}

.input-hint {
  margin: 10px 0 0 0;
  font-size: 15px;
  color: var(--text-muted);
  text-align: center;
}
</style>
