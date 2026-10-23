/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const DEMO_BASE = '/qdrant_transparent_news_assistant/'

export default defineConfig(({ mode }) => {
  const isDemo = mode === 'demo'

  return {
    plugins: [react()],
    base: isDemo ? DEMO_BASE : '/',
    server: {
      port: 3000,
      hmr: {
        clientPort: 3000,
      },
      proxy: isDemo
        ? undefined
        : {
            '/api': {
              target: 'http://localhost:8000',
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ''),
            },
          },
    },
    preview: {
      port: 4173,
    },
    test: {
      environment: 'node',
      include: ['src/**/*.test.ts'],
    },
  }
})
