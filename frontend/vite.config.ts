import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'
  const needRewrite = env.VITE_API_REWRITE !== 'false'
  const base = env.VITE_BASE_PATH || '/'
  const apiPrefix = `${base.replace(/\/$/, '')}/api`

  return {
    plugins: [vue()],
    base,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      port: 5173,
      proxy: {
        [apiPrefix]: {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
          rewrite: needRewrite ? (path) => path.slice(apiPrefix.length) || '/' : undefined
        },
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
          rewrite: needRewrite ? (path) => path.replace(/^\/api/, '') : undefined
        }
      }
    }
  }
})
