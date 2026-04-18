import { reactive } from 'vue'

const createDialogDefaults = () => ({
  open: false,
  mode: 'alert',
  title: '提示',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  inputValue: '',
  inputLabel: '',
  inputPlaceholder: '',
  inputMaxLength: 100,
  multiline: false,
  inputRows: 4,
  destructive: false,
  resolve: null,
})

const dialogState = reactive(createDialogDefaults())

const resetDialogState = () => {
  Object.assign(dialogState, createDialogDefaults())
}

const openDialog = (options = {}) => new Promise((resolve) => {
  Object.assign(dialogState, createDialogDefaults(), options, {
    open: true,
    resolve,
  })
})

const handleDialogConfirm = () => {
  const resolve = dialogState.resolve
  const value = dialogState.inputValue
  resetDialogState()
  resolve?.({ confirmed: true, value })
}

const handleDialogCancel = () => {
  const resolve = dialogState.resolve
  const value = dialogState.inputValue
  resetDialogState()
  resolve?.({ confirmed: false, value })
}

const updateDialogInputValue = (value) => {
  dialogState.inputValue = value
}

const showAlertDialog = async (message, options = {}) => {
  await openDialog({
    mode: 'alert',
    title: options.title || '提示',
    message,
    confirmText: options.confirmText || '知道了',
    destructive: options.destructive || false,
  })
}

const showConfirmDialog = async (message, options = {}) => {
  const result = await openDialog({
    mode: 'confirm',
    title: options.title || '确认操作',
    message,
    confirmText: options.confirmText || '确认',
    cancelText: options.cancelText || '取消',
    destructive: options.destructive || false,
  })
  return result.confirmed
}

const showPromptDialog = async (options = {}) => {
  const result = await openDialog({
    mode: 'prompt',
    title: options.title || '输入内容',
    message: options.message || '',
    confirmText: options.confirmText || '保存',
    cancelText: options.cancelText || '取消',
    inputLabel: options.inputLabel || '',
    inputPlaceholder: options.inputPlaceholder || '',
    inputValue: options.initialValue || '',
    inputMaxLength: options.inputMaxLength || 100,
    multiline: options.multiline || false,
    inputRows: options.inputRows || 4,
    destructive: options.destructive || false,
  })
  return result.confirmed ? result.value : null
}

export {
  dialogState,
  handleDialogCancel,
  handleDialogConfirm,
  showAlertDialog,
  showConfirmDialog,
  showPromptDialog,
  updateDialogInputValue,
}
