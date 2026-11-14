import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8765'

// A closed upstream websocket must not take the dev server down.
const swallowProxyErrors = proxy => { proxy.on('error', () => {}) }

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    // Test runs and screenshots churn files here while the dev server is up;
    // watching them makes the watcher die on transient Windows file locks.
    watch: { ignored: ['**/tests/**', '**/validation/**'] },
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false, configure: swallowProxyErrors },
      '/ws': { target: apiTarget, ws: true, changeOrigin: false, configure: swallowProxyErrors },
    },
  },
})
