<template>
  <Teleport to="body">
    <transition name="app-dialog-fade">
      <div
        v-if="modelValue"
        class="app-dialog-backdrop"
        role="presentation"
        @click.self="handleCancel"
      >
        <div
          class="app-dialog-panel"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <div class="app-dialog-header">
            <h3 :id="titleId" class="app-dialog-title">{{ title }}</h3>
            <p v-if="message" class="app-dialog-message">{{ message }}</p>
          </div>

          <label v-if="mode === 'prompt'" class="app-dialog-field">
            <span v-if="inputLabel" class="app-dialog-label">{{ inputLabel }}</span>
            <textarea
              v-if="multiline"
              ref="inputRef"
              class="app-dialog-textarea"
              :value="inputValue"
              :placeholder="inputPlaceholder"
              :maxlength="inputMaxLength || null"
              :rows="inputRows"
              @input="updateValue"
              @keydown="handlePromptKeydown"
            ></textarea>
            <input
              v-else
              ref="inputRef"
              class="app-dialog-input"
              :value="inputValue"
              :placeholder="inputPlaceholder"
              :maxlength="inputMaxLength || null"
              @input="updateValue"
              @keydown="handlePromptKeydown"
            />
            <span v-if="multiline" class="app-dialog-shortcut">按 `Ctrl + Enter` 快速保存</span>
          </label>

          <div class="app-dialog-actions">
            <button
              v-if="mode !== 'alert'"
              type="button"
              class="app-dialog-button app-dialog-button--secondary"
              @click="handleCancel"
            >
              {{ cancelText }}
            </button>
            <button
              type="button"
              :class="[
                'app-dialog-button',
                destructive ? 'app-dialog-button--danger' : 'app-dialog-button--primary',
              ]"
              @click="handleConfirm"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'alert' },
  title: { type: String, default: '提示' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
  inputValue: { type: String, default: '' },
  inputLabel: { type: String, default: '' },
  inputPlaceholder: { type: String, default: '' },
  inputMaxLength: { type: Number, default: 0 },
  multiline: { type: Boolean, default: false },
  inputRows: { type: Number, default: 4 },
  destructive: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'update:inputValue', 'confirm', 'cancel'])

const inputRef = ref(null)
const titleId = computed(() => `app-dialog-title-${props.mode}`)

const focusInputIfNeeded = async () => {
  if (!props.modelValue || props.mode !== 'prompt') return
  await nextTick()
  inputRef.value?.focus()
  if (!props.multiline) {
    inputRef.value?.select?.()
  }
}

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
}

const updateValue = (event) => {
  emit('update:inputValue', event.target.value)
}

const handlePromptKeydown = (event) => {
  if (props.mode !== 'prompt') return
  if (!props.multiline && event.key === 'Enter') {
    event.preventDefault()
    handleConfirm()
    return
  }
  if (props.multiline && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    handleConfirm()
  }
}

const handleKeydown = (event) => {
  if (!props.modelValue || event.key !== 'Escape') return
  handleCancel()
}

watch(
  () => props.modelValue,
  async (isOpen) => {
    if (isOpen) {
      await focusInputIfNeeded()
    }
  }
)

watch(
  () => props.mode,
  async () => {
    await focusInputIfNeeded()
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.app-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.18);
}

.app-dialog-panel {
  width: min(100%, 440px);
  padding: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.18);
}

.app-dialog-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.app-dialog-title {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
  color: #111827;
}

.app-dialog-message {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #6b7280;
}

.app-dialog-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 18px;
}

.app-dialog-label {
  font-size: 13px;
  font-weight: 700;
  color: #4b5563;
}

.app-dialog-input {
  width: 100%;
  min-height: 52px;
  padding: 0 16px;
  border: 1px solid #d1d5db;
  border-radius: 16px;
  background: #ffffff;
  color: #111827;
  font-size: 15px;
}

.app-dialog-textarea {
  width: 100%;
  min-height: 132px;
  padding: 14px 16px;
  border: 1px solid #d1d5db;
  border-radius: 16px;
  background: #ffffff;
  color: #111827;
  font-size: 15px;
  line-height: 1.7;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
}

.app-dialog-input:focus,
.app-dialog-textarea:focus {
  outline: none;
  border-color: #52525b;
  box-shadow: 0 0 0 4px rgba(17, 17, 17, 0.08);
}

.app-dialog-shortcut {
  font-size: 12px;
  color: #9ca3af;
}

.app-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.app-dialog-button {
  min-width: 96px;
  min-height: 44px;
  padding: 0 16px;
  border: 0;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.app-dialog-button:hover {
  transform: translateY(-1px);
}

.app-dialog-button--primary {
  background: #111827;
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(17, 24, 39, 0.16);
}

.app-dialog-button--danger {
  background: #ef4444;
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(239, 68, 68, 0.18);
}

.app-dialog-button--secondary {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #111827;
}

.app-dialog-fade-enter-active,
.app-dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.app-dialog-fade-enter-active .app-dialog-panel,
.app-dialog-fade-leave-active .app-dialog-panel {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.app-dialog-fade-enter-from,
.app-dialog-fade-leave-to {
  opacity: 0;
}

.app-dialog-fade-enter-from .app-dialog-panel,
.app-dialog-fade-leave-to .app-dialog-panel {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}

@media (max-width: 640px) {
  .app-dialog-backdrop {
    padding: 16px;
  }

  .app-dialog-panel {
    padding: 20px;
    border-radius: 24px;
  }

  .app-dialog-title {
    font-size: 20px;
  }

  .app-dialog-actions {
    flex-direction: column-reverse;
  }

  .app-dialog-button {
    width: 100%;
  }
}
</style>
