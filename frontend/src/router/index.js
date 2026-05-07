import { createRouter, createWebHistory } from 'vue-router'
import Login from '../components/Login.vue'
import History from '../components/History.vue'
import Assessment from '../components/Assessment.vue'
import Report from '../components/Report.vue'
import BigFiveReport from '../components/BigFiveReport.vue'
import Chat from '../components/Chat.vue'
import AdminLayout from '../components/admin/AdminLayout.vue'
import AdminDashboard from '../components/admin/AdminDashboard.vue'
import AdminQuestions from '../components/admin/AdminQuestions.vue'
import AdminReports from '../components/admin/AdminReports.vue'
import AdminExperiments from '../components/admin/AdminExperiments.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/history', component: History },
  { path: '/assessment', component: Assessment },
  { path: '/report/:sessionId', component: Report, props: true },
  { path: '/big-five-report/:reportId', component: BigFiveReport, props: true },
  { path: '/chat', component: Chat },
  { path: '/chat/:chatId', component: Chat, props: true },
  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', component: AdminDashboard },
      { path: 'questions', component: AdminQuestions },
      { path: 'reports', component: AdminReports },
      { path: 'experiments', component: AdminExperiments },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.matched.some(record => record.meta.requiresAdmin) && localStorage.getItem('isAdmin') !== '1' && localStorage.getItem('role') !== 'admin') {
    next('/history')
  } else {
    next()
  }
})

export default router
