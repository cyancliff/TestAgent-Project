import { createRouter, createWebHistory } from 'vue-router'
import Login from '../components/Login.vue'
import History from '../components/History.vue'
import Assessment from '../components/Assessment.vue'
import Report from '../components/Report.vue'
import Chat from '../components/Chat.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/history', component: History },
  { path: '/assessment', component: Assessment },
  { path: '/report/:sessionId', component: Report, props: true },
  { path: '/chat', component: Chat },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  const userId = localStorage.getItem('userId')
  if (to.path !== '/login' && !userId) {
    next('/login')
  } else {
    next()
  }
})

export default router
