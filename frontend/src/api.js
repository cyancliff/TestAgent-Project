import axios from 'axios'
import router from './router'
import { apiBaseUrl } from './config'

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
})

// 请求拦截器：自动附加 JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：401 时跳转登录
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userId')
      localStorage.removeItem('username')
      localStorage.removeItem('nickname')
      localStorage.removeItem('loginAccount')
      localStorage.removeItem('avatarUrl')
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default api
