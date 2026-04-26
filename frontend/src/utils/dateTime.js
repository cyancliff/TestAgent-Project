const hasTimeZoneSuffix = (value) => /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(value)

export const parseApiDate = (value) => {
  if (!value) return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }

  let normalized = String(value).trim()
  if (!normalized) return null

  normalized = normalized.replace(' ', 'T').replace(/(\.\d{3})\d+/, '$1')
  const hasTime = /T\d{2}:\d{2}/.test(normalized)
  if (hasTime && !hasTimeZoneSuffix(normalized)) {
    normalized = `${normalized}Z`
  }

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

const padDatePart = (value) => String(value).padStart(2, '0')

export const formatApiDotDateTime = (value, fallback = '') => {
  const date = parseApiDate(value)
  if (!date) return fallback
  return [
    `${date.getFullYear()}.${padDatePart(date.getMonth() + 1)}.${padDatePart(date.getDate())}`,
    `${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}`,
  ].join(' ')
}

export const formatApiDateTime = (value, fallback = '') => {
  const date = parseApiDate(value)
  if (!date) return fallback
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export const formatApiMonthDay = (value, fallback = '') => {
  const date = parseApiDate(value)
  if (!date) return fallback
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date)
}
