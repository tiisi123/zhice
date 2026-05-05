import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// 后端 API 端口：默认 8000，可通过环境变量 VITE_API_PORT 覆盖
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiPort = env.VITE_API_PORT || '8000'
  return {
    plugins: [react()],
    test: {
      environment: 'happy-dom',
      setupFiles: ['./src/test-setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json-summary'],
        include: ['src/pages/**', 'src/components/**', 'src/api/**'],
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router-dom')) return 'react'
            if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design/icons')) return 'antd'
            if (id.includes('node_modules/echarts')) return 'charts'
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 3001,
      proxy: {
        '/api/ws': {
          target: `ws://127.0.0.1:${apiPort}`,
          ws: true,
        },
        '/api': {
          target: `http://127.0.0.1:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
