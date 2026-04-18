const DEV_BACKEND_ORIGIN = 'http://127.0.0.1:8000'

const trimTrailingSlash = (value) => String(value || '').trim().replace(/\/+$/, '')
const ABSOLUTE_URL_PATTERN = /^[a-z][a-z\d+\-.]*:\/\//i

const configuredBackendOrigin = trimTrailingSlash(import.meta.env.VITE_BACKEND_ORIGIN)

export const backendOrigin = configuredBackendOrigin || (import.meta.env.DEV ? DEV_BACKEND_ORIGIN : '')
export const apiBaseUrl = backendOrigin ? `${backendOrigin}/api/v1` : '/api/v1'

export const resolveBackendUrl = (path) => {
  if (!path) return ''
  if (ABSOLUTE_URL_PATTERN.test(path) || path.startsWith('//')) {
    return path
  }
  if (!backendOrigin) {
    return path
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${backendOrigin}${normalizedPath}`
}

export const buildApiUrl = (path) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const normalizedBase = apiBaseUrl.replace(/\/$/, '')

  if (ABSOLUTE_URL_PATTERN.test(normalizedBase)) {
    return `${normalizedBase}${normalizedPath}`
  }

  return `${window.location.origin}${normalizedBase}${normalizedPath}`
}
