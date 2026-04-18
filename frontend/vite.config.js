import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendOrigin = (env.VITE_BACKEND_ORIGIN || 'http://127.0.0.1:8000').replace(/\/+$/, '')

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true,
        },
        '/uploads': {
          target: backendOrigin,
          changeOrigin: true,
        },
      },
    },
  }
})
